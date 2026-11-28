"""Render repository-owned native settings without invoking global installers."""

import json
from collections.abc import Collection
from pathlib import Path

from gzlite.native_identity import retire_claude
from gzlite.native_json import document, replace_fields
from gzlite.paths import space_free

HOST_PATHS = {
    "codex": ".codex/config.toml",
    "claude": ".claude/settings.json",
    "opencode": "opencode.json",
}


def configuration_path(root: Path, host: str) -> str:
    """Repair existing JSONC in place rather than shadowing project configuration."""
    space_free(root / HOST_PATHS[host])
    if host == "opencode" and space_free(root / "opencode.jsonc").exists():
        if (root / "opencode.json").exists():
            raise ValueError("both OpenCode JSON and JSONC exist; reconcile their precedence first")
        return "opencode.jsonc"
    return HOST_PATHS[host]


def update_skill_path(host: str) -> str:
    """Select the host's native project skill discovery directory."""
    surface = ".claude" if host == "claude" else ".agents"
    return f"{surface}/skills/gzl-update/SKILL.md"


# Project skill directories each host discovers. Claude reads .claude/skills and
# Codex reads .agents/skills (docs/architecture.md). OpenCode reads .agents/skills
# (docs/evidence/2026-10-31-three-host-repo-scope.md) and .claude/skills: the
# scoped launcher `gzlite run-opencode` adds both to OpenCode's skills setting
# (src/gzlite/native_launch.py:39). A plain `opencode` launch reading
# .claude/skills is unverified; it is assumed so that no copy is duplicated.
SKILL_SURFACES = {
    "claude": (".claude/skills",),
    "codex": (".agents/skills",),
    "opencode": (".agents/skills", ".claude/skills"),
}


def skill_surface(host: str) -> str:
    """The discovery directory that holds ``host``'s own update skill."""
    return Path(update_skill_path(host)).parent.parent.as_posix()


def update_skill_placement(hosts: Collection[str], recorded: str) -> tuple[str, ...]:
    """Choose the surfaces that get the update skill for every configured host.

    The recorded host's own surface always gets it. Each other host's surface
    is added unless some configured host would then discover two copies.
    """
    chosen = [skill_surface(recorded)]
    for host in sorted(hosts):
        if skill_surface(host) in chosen:
            continue
        trial = [*chosen, skill_surface(host)]
        if all(sum(s in trial for s in SKILL_SURFACES[h]) <= 1 for h in hosts):
            chosen = trial
    return tuple(chosen)


def uncovered_hosts(hosts: Collection[str], placement: Collection[str]) -> list[str]:
    """Configured hosts that discover no copy of the update skill."""
    return [h for h in sorted(hosts) if not any(s in placement for s in SKILL_SURFACES[h])]


def _merge_object(data: dict, key: str, additions: dict) -> None:
    """Add absent entries while refusing conflicting project decisions."""
    current = data.setdefault(key, {})
    if not isinstance(current, dict):
        raise ValueError(f"{key} must be an object; reconcile without overwriting")
    for name, value in additions.items():
        if name in current and current[name] != value:
            raise ValueError(f"conflicting {key}.{name}; reconcile without overwriting")
        current[name] = value


def _claude_settings(
    data: dict, ref: str, parts: list[dict], marketplace: str, retire: bool
) -> None:
    """Reconcile Claude's project marketplace and activation maps."""
    if retire:
        retire_claude(data, marketplace, parts)
    _merge_object(
        data,
        "extraKnownMarketplaces",
        {
            marketplace: {
                "source": {
                    "source": "git",
                    "url": "https://github.com/tvproductions/gzlite.git",
                    "ref": ref,
                },
                "autoUpdate": False,
            }
        },
    )
    enabled = {p["name"] + "@" + marketplace: p["enabled_by_default"] for p in parts}
    _merge_object(data, "enabledPlugins", enabled)
    names = {p["name"] for p in parts}
    for identity, active in data["enabledPlugins"].items():
        if identity.split("@", 1)[0] in names and identity not in enabled and active:
            raise ValueError(f"duplicate plugin source {identity}; reconcile first")


def _opencode_settings(data: dict, parts: list[dict]) -> None:
    """Preserve unrelated package selections and reconcile the pinned active pair."""
    if "plugin" in data:
        raise ValueError("OpenCode v1 plugin configuration needs explicit v2 reconciliation")
    plugins = data.setdefault("plugins", [])
    if not isinstance(plugins, list) or any(not isinstance(p, str) for p in plugins):
        raise ValueError("OpenCode plugins must be an array of package strings")
    if any("superpowers-backplane" in p and not p.startswith("-") for p in plugins):
        raise ValueError("existing OpenCode Backplane plugin needs explicit readiness review")
    for part in parts:
        if not part["enabled_by_default"]:
            continue
        repository = part["repository"]
        target = f"git+{repository}.git#{part['revision']}"
        if any(repository in p and p != target for p in plugins):
            raise ValueError(f"conflicting OpenCode plugin {part['name']}; reconcile first")
        if target not in plugins:
            plugins.append(target)


def project_json(
    existing: str,
    host: str,
    ref: str,
    parts: list[dict],
    marketplace: str,
    *,
    retire: bool = True,
) -> str:
    """Preserve unrelated JSON settings and require immutable project sources.

    With ``retire`` false, earlier starter activations are judged rather than
    removed, for settings this call only checks and never writes.
    """
    data, _ = document(existing)
    before = json.dumps(data, sort_keys=True)
    if host == "claude":
        _claude_settings(data, ref, parts, marketplace, retire)
    elif host == "opencode":
        _opencode_settings(data, parts)
    else:
        raise ValueError(f"unsupported JSON host: {host}")
    if existing and json.dumps(data, sort_keys=True) == before:
        return existing
    return replace_fields(existing, data)
