"""Render a project as an earlier gz-starter commit's ``configure`` left it.

The fixtures come from the embedded release history only, so the gate needs no
git and no network. Each managed path of the snapshot is written with the
content the history says that commit's ``configure`` wrote, rendered with the
adopter's recorded revision. Host configuration has no template in the
history; it is rendered in the exact shape those releases produced for an
empty project (checked once against every tag's own ``configure``, see the
Task 10 report).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gzlite.history import Release

# Lock components as configure copied them from that commit's bundle.json. The
# names, repositories and defaults never changed; the revisions are fixtures.
FIXTURE_COMPONENTS = (
    {
        "name": "superpowers",
        "repository": "https://github.com/obra/superpowers",
        "release": "v0.0.1",
        "revision": "1" * 40,
        "status": "fixture",
        "enabled_by_default": True,
    },
    {
        "name": "superpowers-backplane",
        "repository": "https://github.com/tvproductions/superpowers-backplane",
        "release": "v0.0.1",
        "revision": "2" * 40,
        "status": "fixture",
        "enabled_by_default": False,
    },
    {
        "name": "gz-skills",
        "repository": "https://github.com/tvproductions/gz-skills",
        "release": "v0.0.1",
        "revision": "3" * 40,
        "status": "fixture",
        "enabled_by_default": True,
    },
)


def adr_working_source(release: Release, ref: str, mode: str) -> str:
    """What the fragment's working-policy placeholder became at that commit."""
    if mode == "local":
        return f"{release.state_directory}/architectural-decisions.md"
    return adr_url(release, ref)


def adr_url(release: Release, ref: str) -> str:
    assert release.adr_policy_url is not None
    return release.adr_policy_url.replace("{ref}", ref)


def fragment(release: Release, ref: str, mode: str = "link") -> str:
    text = release.fragment_template
    if release.adr_placeholders:
        text = text.replace(
            "{{ADR_POLICY_WORKING_SOURCE}}", adr_working_source(release, ref, mode)
        ).replace("{{ADR_POLICY_CANONICAL_URL}}", adr_url(release, ref))
    return text


def lock(
    release: Release,
    host: str,
    ref: str,
    *,
    mode: str = "link",
    components: tuple[dict, ...] = FIXTURE_COMPONENTS,
) -> str:
    values: dict[str, object] = {
        "schema_version": 1,
        "starter": {"repository": release.origin, "version": release.version, "revision": ref},
        "components": [dict(part) for part in components],
    }
    if "adr_policy" in release.lock_keys:
        assert release.adr_policy_template is not None
        policy = {
            "mode": mode,
            "source_path": release.adr_policy_source,
            "source_sha256": hashlib.sha256(release.adr_policy_template.encode()).hexdigest(),
        }
        if mode == "local":
            policy["local_path"] = f"{release.state_directory}/architectural-decisions.md"
        values["adr_policy"] = policy
    if host != "codex":
        assert "host" in release.lock_keys
        values["host"] = host
    ordered = {key: values[key] for key in release.lock_keys if key in values}
    return json.dumps(ordered, indent=2) + "\n"


def host_config(
    release: Release, host: str, ref: str, components: tuple[dict, ...] = FIXTURE_COMPONENTS
) -> str:
    """The host configuration configure wrote into a project that had none."""
    catalog = release.marketplace
    if host == "codex":
        tables = [
            f"[marketplaces.{json.dumps(catalog)}]\n"
            f'source_type = "git"\nsource = "{release.origin}"\nref = "{ref}"'
        ]
        tables += [
            f"[plugins.{json.dumps(part['name'] + '@' + catalog)}]\n"
            f"enabled = {str(part['enabled_by_default']).lower()}"
            for part in components
        ]
        return "\n" + "\n\n".join(tables) + "\n"
    if host == "claude":
        data = {
            "extraKnownMarketplaces": {
                catalog: {
                    "source": {"source": "git", "url": release.origin, "ref": ref},
                    "autoUpdate": False,
                }
            },
            "enabledPlugins": {
                part["name"] + "@" + catalog: part["enabled_by_default"] for part in components
            },
        }
        return json.dumps(data, indent=2) + "\n"
    plugins = ["-" + part["name"] for part in components]
    plugins += [
        f"git+{part['repository']}.git#{part['revision']}"
        for part in components
        if part["enabled_by_default"]
    ]
    # The first merge wrote {"plugins": [...]}; the scope repair then replaced
    # the value in place, which leaves this two-level indentation.
    return '{\n  "plugins": ' + json.dumps(plugins, indent=2) + "\n}\n"


def managed_files(
    release: Release,
    host: str,
    ref: str | None = None,
    *,
    mode: str = "link",
    components: tuple[dict, ...] = FIXTURE_COMPONENTS,
) -> dict[str, str]:
    """Every file configure wrote at ``release`` for ``host``, by relative path."""
    ref = ref or release.revision
    files: dict[str, str] = {}
    for entry in release.managed_entries(host):
        path, condition = entry.path, entry.condition
        if condition == "merged-if-exists":
            continue  # configure used it only when the project already had it
        if condition == "merged":
            files[path] = host_config(release, host, ref, components)
        elif condition == "adr-local":
            if mode == "local":
                assert release.adr_policy_template is not None
                files[path] = release.adr_policy_template
        elif path == f"{release.state_directory}/bundle.lock.json":
            files[path] = lock(release, host, ref, mode=mode, components=components)
        elif path == "AGENTS.skills-first.md":
            files[path] = fragment(release, ref, mode)
        elif path == "AGENTS.md":
            files[path] = release.agents_md_template
        elif release.update_skill and path.endswith(f"/skills/{release.update_skill}/SKILL.md"):
            assert release.update_skill_template is not None
            files[path] = release.update_skill_template
        elif release.front_door_skill and path.endswith(
            f"/skills/{release.front_door_skill}/SKILL.md"
        ):
            assert release.front_door_skill_template is not None
            files[path] = release.front_door_skill_template
        else:
            raise AssertionError(f"no fixture content rule for {entry}")
    return files


def render_adopter(
    root: Path,
    release: Release,
    host: str,
    ref: str | None = None,
    *,
    mode: str = "link",
    components: tuple[dict, ...] = FIXTURE_COMPONENTS,
) -> dict[str, str]:
    """Write ``managed_files`` under ``root`` as bytes configure wrote (UTF-8, LF)."""
    files = managed_files(release, host, ref, mode=mode, components=components)
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode())
    return files
