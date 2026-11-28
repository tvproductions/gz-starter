#!/usr/bin/env python3
"""Preview or configure a project-scoped SP + SP-BP + gz-skills bundle.

No dependencies beyond Python 3.14. Native plugin managers own installation;
this tool writes project configuration and never edits their global caches.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Collection, Mapping
from pathlib import Path

from gzlite import catalog as catalog_commands
from gzlite import vendor as vendor_commands
from gzlite.gitenv import clean_git_env
from gzlite.native import (
    HOST_PATHS,
    configuration_path,
    project_json,
    skill_surface,
    update_skill_path,
    update_skill_placement,
)
from gzlite.native_identity import STARTER_SOURCES, marketplace_name, retire_codex
from gzlite.native_json import document as project_document
from gzlite.native_launch import launch as launch_opencode
from gzlite.native_scope import claude_scope, codex_scope, opencode_scope
from gzlite.paths import (
    BUNDLE_LOCK,
    LOCAL_ADR_POLICY,
    STAGING_DIRECTORY,
    is_link,
    space_free,
    validate_state_directory,
)
from gzlite.portability import CHECKS as PORTABILITY_CHECKS
from gzlite.portability import audit as portability_audit
from gzlite.project_settings import (
    SettingsError,
    validate_settings,
)
from gzlite.project_settings import initialize as settings_initialize
from gzlite.project_settings import inspect as settings_inspect
from gzlite.project_settings import select as settings_select
from gzlite.releases import SHA, tagged_release

_SOURCE = Path(__file__).resolve()
_CHECKOUT = _SOURCE.parents[2]
# Editable installs use authoritative checkout files. Wheels carry checked copies.
HERE = (
    _CHECKOUT
    if _SOURCE.parent.parent.name == "src" and (_CHECKOUT / "bundle.json").is_file()
    else _SOURCE.parent / "resources"
)
ORIGIN = "https://github.com/tvproductions/gzlite.git"
UPDATE_SKILL = "gzl-update"
UPDATE_SKILL_SOURCE = f"templates/skills/{UPDATE_SKILL}/SKILL.md"
UPDATE_SKILL_DESTINATION = f".agents/skills/{UPDATE_SKILL}/SKILL.md"
ADR_POLICY_SOURCE = "docs/engineering/architectural-decisions.md"
ADR_POLICY_DESTINATION = LOCAL_ADR_POLICY
# Top-level lock keys configure writes; any other key is project-owned and carried.
MANAGED_LOCK_KEYS = frozenset({"schema_version", "starter", "components", "adr_policy", "host"})


class AdoptionError(Exception):
    """Configuration requires reconciliation before adoption can proceed."""


def bundle() -> dict:
    """Read the authoritative bundle or its installed resource copy."""
    return json.loads(space_free(HERE / "bundle.json").read_text(encoding="utf-8"))


def template_version() -> str:
    """Read the starter-owned version independently of adopter app metadata."""
    version = bundle().get("template_version")
    if not isinstance(version, str) or not re.fullmatch(
        r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version
    ):
        raise AdoptionError("template_version must be a numeric MAJOR.MINOR.PATCH version")
    return version


def require_tagged_release(ref: str, version: str) -> None:
    """Require the publisher's tag to agree with the bundle being used."""
    release = tagged_release(ref, origin=ORIGIN)
    if release.version != version:
        raise AdoptionError(
            f"{ref} is {release.tag}; expected a published release for bundle version {version}"
        )


def marketplace() -> str:
    """Name the native catalog after this starter release."""
    return marketplace_name(template_version())


def validate_bundle() -> None:
    """Require matching immutable component pins in both native catalogs."""
    template_version()
    data = bundle()
    if data.get("schema_version") != 1:
        raise AdoptionError("unsupported bundle schema")
    parts = data.get("components", [])
    if {p["name"] for p in parts} != {"superpowers", "superpowers-backplane", "gz-skills"} or len(
        parts
    ) != 3:
        raise AdoptionError("bundle must contain exactly the three independently owned components")
    expected = {p["name"]: (p["repository"] + ".git", p["revision"]) for p in parts}
    if any(not SHA.fullmatch(p["revision"]) for p in parts):
        raise AdoptionError("every component needs an immutable full commit SHA")
    if any(type(p.get("enabled_by_default")) is not bool for p in parts):
        raise AdoptionError("every component needs an explicit boolean default activation")
    codex = json.loads(
        space_free(HERE / ".agents/plugins/marketplace.json").read_text(encoding="utf-8")
    )
    actual = {p["name"]: (p["source"]["url"], p["source"]["ref"]) for p in codex["plugins"]}
    if actual != expected or codex["name"] != marketplace():
        raise AdoptionError("Codex marketplace does not match bundle pins")
    claude = json.loads(
        space_free(HERE / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
    )
    # Claude Code reads "ref" as a branch or tag; a commit pin must use "sha".
    actual = {p["name"]: (p["source"]["url"], p["source"].get("sha")) for p in claude["plugins"]}
    if actual != expected or claude["name"] != marketplace():
        raise AdoptionError("Claude marketplace does not match bundle pins")


def check_path(root: Path, relative: str) -> Path:
    """Resolve a managed destination while refusing linked files and parents."""
    path = space_free(root / relative)
    for item in (path, *path.parents):
        if item == root:
            break
        if os.path.lexists(item) and is_link(item):
            raise AdoptionError(f"refusing symlinked destination or reparse point: {relative}")
        if item != path and item.exists() and not item.is_dir():
            raise AdoptionError(f"parent is not a directory: {relative}")
    if path.exists() and not path.is_file():
        raise AdoptionError(f"not a regular destination file: {relative}")
    return path


def profile_check(path: Path) -> None:
    """Preserve an existing explicit profile and reject incompatible state."""
    if not path.exists():
        return
    try:
        validate_settings(json.loads(path.read_text(encoding="utf-8")))
    except SettingsError as error:
        raise AdoptionError(
            "existing gz-skills profile is unsupported; reconcile it without overwriting"
        ) from error


def _check_plugin_activation(plugins: dict, parts: list[dict], name: str) -> None:
    """Reject conflicting activation and duplicate sources before adding tables."""
    defaults = {part["name"]: part["enabled_by_default"] for part in parts}
    for key, value in plugins.items():
        part = key.split("@")[0]
        if part not in defaults:
            continue
        if key.endswith("@" + name):
            if value.get("enabled") is not defaults[part]:
                raise AdoptionError(
                    f"{key} conflicts with the default activation; reconcile explicitly"
                )
        elif value.get("enabled") is not False:
            raise AdoptionError(
                f"{key} may create duplicate discovery; adopt the existing source explicitly"
            )


def _missing_config_tables(data: dict, ref: str, parts: list[dict], catalog: str) -> list[str]:
    """Render only absent managed tables; differing existing tables are conflicts."""
    wanted = [("marketplaces", catalog, {"source_type": "git", "source": ORIGIN, "ref": ref})]
    wanted += [
        ("plugins", p["name"] + "@" + catalog, {"enabled": p["enabled_by_default"]}) for p in parts
    ]
    added = []
    for group, name, values in wanted:
        found = data.get(group, {}).get(name)
        if found is not None:
            if found != values:
                raise AdoptionError(f"conflicting [{group}.{name}] configuration; no files changed")
            continue
        lines = [f"[{group}.{json.dumps(name)}]"]
        lines += [f"{key} = " + json.dumps(value) for key, value in values.items()]
        added.append("\n".join(lines))
    return added


def project_config(existing: str, ref: str) -> str:
    """Extend compatible Codex configuration without replacing project settings."""
    parts = bundle()["components"]
    catalog = marketplace()
    try:
        existing = retire_codex(existing, catalog, parts)
    except ValueError as error:
        raise AdoptionError(str(error)) from error
    data = tomllib.loads(existing)
    _check_plugin_activation(data.get("plugins", {}), parts, catalog)
    added = _missing_config_tables(data, ref, parts, catalog)
    if not added:
        return existing
    return (
        existing
        + ("\n" if existing and not existing.endswith("\n") else "")
        + "\n"
        + "\n\n".join(added)
        + "\n"
    )


def _adoption_root(project: Path) -> Path:
    """Resolve the existing project and preserve the separate gzkit ecosystem."""
    root = space_free(project).resolve(strict=True)
    if not root.is_dir():
        raise AdoptionError("project must be an existing directory")
    if (root / ".gzkit").exists() or (root / ".gzkit").is_symlink():
        raise AdoptionError(
            "this is a gzkit project; keep that ecosystem and do not initialize this stack"
        )
    return root


def _check_discovery_entry(
    surface: str, child: Path, allowed: Collection[str] = (".agents/skills",)
) -> None:
    """Preserve legacy and shared skill copies for explicit reconciliation.

    ``allowed`` lists the surfaces that may hold the update skill: one per
    configured host, chosen so no host discovers two copies.
    """
    if child.name == UPDATE_SKILL and surface not in allowed:
        raise AdoptionError(f"duplicate template update skill at {surface}; reconcile first")
    if child.name in ("skills-first-start", "adopt-skills-stack", "python-engineering"):
        raise AdoptionError(
            f"legacy starter skill at {surface}/{child.name}; "
            "reconcile with docs/migration-0.3.md before adoption; no files changed"
        )
    if child.name.startswith("gzs-") or child.name in (
        "superpowers",
        "superpowers-backplane",
        "managing-superpowers-backlog",
        "managing-superpowers-handoffs",
    ):
        raise AdoptionError(
            f"existing shared skill discovery at {surface}/{child.name}; reconcile first"
        )


def configured_hosts(root: Path, recorded: str) -> list[str]:
    """The recorded host, then every other host whose file holds this release's entries."""
    catalog = marketplace()
    targets = {
        f"git+{p['repository']}.git#{p['revision']}"
        for p in bundle()["components"]
        if p["enabled_by_default"]
    }
    found = [recorded]
    for host in sorted(set(HOST_PATHS) - {recorded}):
        try:
            name = configuration_path(root, host)
            path = check_path(root, name)
            text = path.read_text(encoding="utf-8") if path.exists() else ""
            if not text:
                continue
            if host == "codex":
                present = catalog in tomllib.loads(text).get("marketplaces", {})
            else:
                data, _ = project_document(text)
                if host == "claude":
                    known = data.get("extraKnownMarketplaces")
                    present = isinstance(known, dict) and catalog in known
                else:
                    plugins = data.get("plugins")
                    present = isinstance(plugins, list) and bool(targets & set(plugins))
        except AdoptionError, OSError, ValueError:
            # An unreadable file of another host is not this host's concern.
            continue
        if present:
            found.append(host)
    return found


def _check_discovery(
    root: Path,
    host: str = "codex",
    skip: Collection[str] = frozenset(),
    allowed: Collection[str] | None = None,
) -> None:
    """Inspect all supported discovery surfaces without mutating their contents.

    ``skip`` names skill directories (``<surface>/<name>``) the caller removes.
    ``allowed`` defaults to the update-skill placement for the configured hosts.
    """
    if allowed is None:
        allowed = update_skill_placement(configured_hosts(root, host), host)
    for surface in (
        ".agents/skills",
        ".codex/skills",
        ".claude/skills",
        ".github/skills",
        ".opencode/skills",
    ):
        folder = space_free(root / surface)
        if folder.is_symlink():
            raise AdoptionError(f"inspect existing discovery link {surface} before adoption")
        if folder.is_dir():
            for child in folder.iterdir():
                space_free(child)
                if f"{surface}/{child.name}" not in skip:
                    _check_discovery_entry(surface, child, allowed)


def _policy_candidates(
    root: Path, ref: str, requested: str | None, *, check_recorded: bool = True
) -> tuple[dict[str, str], dict[str, str], str]:
    """Resolve policy access and reject unreconciled provenance before writing.

    ``freshen`` passes ``check_recorded=False``: it moves a recorded policy
    from an earlier release to this one instead of refusing the difference.
    """
    lock_path = check_path(root, BUNDLE_LOCK)
    recorded = None
    if lock_path.exists():
        lock = json.loads(lock_path.read_bytes())
        recorded = lock.get("adr_policy") if isinstance(lock, dict) else None
        if not isinstance(recorded, dict) or recorded.get("mode") not in ("link", "local"):
            raise AdoptionError("ADR policy selection is missing or invalid; reconcile the lock")
    mode = requested if requested is not None else recorded["mode"] if recorded else "link"
    if mode not in ("link", "local"):
        raise AdoptionError("unsupported ADR policy mode; reconcile using link or local")
    source = space_free(HERE / ADR_POLICY_SOURCE).read_bytes()
    policy = {
        "mode": mode,
        "source_path": ADR_POLICY_SOURCE,
        "source_sha256": hashlib.sha256(source).hexdigest(),
    }
    if mode == "local":
        policy["local_path"] = ADR_POLICY_DESTINATION
    if check_recorded and recorded is not None and recorded != policy:
        raise AdoptionError(
            "ADR policy provenance or selection differs; reconcile without overwriting"
        )
    url = _adr_policy_url(ref)
    copies = {ADR_POLICY_DESTINATION: source.decode("utf-8")} if mode == "local" else {}
    return policy, copies, ADR_POLICY_DESTINATION if mode == "local" else url


def _adr_policy_url(ref: str) -> str:
    """Return the canonical, ref-pinned URL of the ADR policy in the origin repository."""
    return f"{ORIGIN.removesuffix('.git')}/blob/{ref}/{ADR_POLICY_SOURCE}"


def lock_extras(lock: object) -> dict:
    """Return the lock's project-owned top-level keys, in their recorded order."""
    if not isinstance(lock, dict):
        return {}
    return {key: value for key, value in lock.items() if key not in MANAGED_LOCK_KEYS}


def render_fragment(ref: str, working_policy: str) -> str:
    """This release's instructions fragment with its ADR policy placeholders filled."""
    fragment = space_free(HERE / "templates/AGENTS.skills-first.md").read_text(encoding="utf-8")
    return fragment.replace("{{ADR_POLICY_WORKING_SOURCE}}", working_policy).replace(
        "{{ADR_POLICY_CANONICAL_URL}}", _adr_policy_url(ref)
    )


def _configuration_candidates(
    paths: dict[str, Path],
    ref: str,
    host: str = "codex",
    *,
    policy: dict[str, str],
    working_policy: str,
    old_config: str | None = None,
    carried: Mapping[str, object] | None = None,
) -> tuple[dict[str, str], dict]:
    """Prepare managed payloads without writing or changing existing authorities.

    ``old_config`` replaces the host configuration read from disk (``migrate``
    passes a copy with earlier starter entries already retired). ``carried``
    holds project-owned lock keys, written after the managed ones.
    """
    config_path = "opencode.jsonc" if "opencode.jsonc" in paths else HOST_PATHS[host]
    if old_config is None:
        old_config = (
            paths[config_path].read_text(encoding="utf-8", newline="")
            if paths[config_path].exists()
            else ""
        )
    fragment = render_fragment(ref, working_policy)
    lock = {
        "schema_version": 1,
        "starter": {"repository": ORIGIN, "version": template_version(), "revision": ref},
        "components": bundle()["components"],
        "adr_policy": policy,
    }
    if host != "codex":
        lock["host"] = host
    lock.update({key: value for key, value in (carried or {}).items() if key not in lock})
    config = (
        project_config(old_config, ref)
        if host == "codex"
        else project_json(old_config, host, ref, bundle()["components"], marketplace())
    )
    config = _scoped_config(config, host, ref, bundle()["components"], marketplace())
    candidates = {
        config_path: config,
        BUNDLE_LOCK: json.dumps(lock, indent=2) + "\n",
        "AGENTS.skills-first.md": fragment,
        update_skill_path(host): space_free(HERE / UPDATE_SKILL_SOURCE).read_text(encoding="utf-8"),
    }
    if not paths["AGENTS.md"].exists():
        candidates["AGENTS.md"] = (
            "# Project agent instructions\n\nRead [AGENTS.skills-first.md](AGENTS.skills-first.md) for this project's development stack.\nAdd project-owned rules, verification commands, and operational skill routing here.\n"
        )
    return candidates, lock


def same_text(current: bytes | None, payload: str) -> bool:
    """Whether a file holds ``payload`` apart from CRLF line endings (git autocrlf)."""
    if current is None:
        return False
    if current == payload.encode():
        return True
    try:
        text = current.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return text.replace("\r\n", "\n") == payload.replace("\r\n", "\n")


def _plan_writes(
    paths: dict[str, Path],
    candidates: dict[str, str],
    replaceable: Collection[str] = (),
    *,
    observed: Mapping[str, bytes | None] | None = None,
) -> tuple[dict[str, str], dict[str, bytes | None], list[str]]:
    """Check every candidate and capture rollback bytes before any write.

    Host configuration is merged, so it may differ; ``replaceable`` names other
    files the caller has reviewed and may overwrite (``migrate`` saves them first).
    A file that differs only by CRLF line endings is present, not rewritten.
    """
    writes, before, present = {}, {}, []
    for name, payload in candidates.items():
        path = paths[name]
        current = path.read_bytes() if path.exists() else None
        if observed is not None and name in observed and observed[name] != current:
            raise AdoptionError(f"{name} changed while planning; preview again; no files changed")
        before[name] = current
        if same_text(current, payload):
            present.append(name)
        elif current is not None and name not in (
            *HOST_PATHS.values(),
            "opencode.jsonc",
            *replaceable,
        ):
            raise AdoptionError(
                f"{name} differs from the reviewed template; reconcile without overwriting"
            )
        else:
            writes[name] = payload
    return writes, before, present


def _write_candidate(path: Path, payload: str, current: bytes | None) -> None:
    """Create exclusively or replace through a sibling temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if current is None:
        encoded = payload.encode()
        created = None
        try:
            with path.open("xb") as stream:
                created = os.fstat(stream.fileno())
                stream.write(encoded)
        except BaseException:
            if created is not None:
                try:
                    remaining = path.stat(follow_symlinks=False)
                    matching_content = encoded.startswith(path.read_bytes())
                except FileNotFoundError:
                    pass
                else:
                    # Inodes can be reused after close; identity alone is not ownership.
                    if os.path.samestat(created, remaining) and matching_content:
                        path.unlink()
            raise
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        stream.write(payload.encode())
    try:
        os.chmod(temp, path.stat().st_mode & 0o777)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _missing_parents(root: Path, names: Collection[str]) -> list[Path]:
    """List the directories the writes will create, outermost first."""
    missing: list[Path] = []
    for name in names:
        for parent in reversed(Path(name).parents[:-1]):
            directory = root / parent
            if directory not in missing and not directory.exists():
                missing.append(directory)
    return missing


def _apply_writes(
    root: Path,
    paths: dict[str, Path],
    writes: dict[str, str],
    before: dict[str, bytes | None],
    *,
    deletes: Collection[str] = (),
    directories: Collection[str] = (),
    allow_legacy: bool = False,
    saved: Mapping[str, str] | None = None,
) -> list[str]:
    """Recheck each destination and roll completed writes back on failure.

    After the writes, each of ``deletes`` is moved (``os.replace``) into
    ``STAGING_DIRECTORY`` if it still holds its ``before`` bytes, then each of
    ``directories`` is removed in the given order (each must be empty by then).
    The state folder must be valid at the end, with no legacy state left.
    Staged files are removed last; any that cannot be are returned.

    ``saved`` maps a deleted or replaced file to the copy of it this same call
    writes (``migrate`` saves under ``.gzlite/migrated/``). Those copies are
    never undone, so a failed restore cannot lose the only copy. On failure,
    staged files are renamed back, then writes are undone. If any step of that
    fails, undoing stops, everything left stays where it is, and
    ``RollbackIncomplete`` names each affected file and where its copy is.
    """
    validate_state_directory(root, allow_legacy=allow_legacy)
    saved = saved or {}
    keep = set(saved.values())
    created = _missing_parents(root, writes)
    completed: list[str] = []
    staged: list[tuple[str, Path]] = []
    try:
        for name, payload in writes.items():
            path = check_path(root, name)
            current = path.read_bytes() if path.exists() else None
            if current != before[name]:
                raise AdoptionError(f"{name} changed during preview; retry after review")
            _write_candidate(path, payload, current)
            completed.append(name)
        for name in deletes:
            path = check_path(root, name)
            if not path.exists() or path.read_bytes() != before[name]:
                raise AdoptionError(f"{name} changed during preview; retry after review")
            target = check_path(root, f"{STAGING_DIRECTORY}/{name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(path, target)
            staged.append((name, target))
        for name in directories:
            directory = space_free(root / name)
            if directory.is_symlink():
                raise AdoptionError(f"refusing symlinked directory: {name}")
            os.rmdir(directory)
        # This call's own staged originals are still there until cleanup below.
        validate_state_directory(root, allow_staging=True)
    except BaseException as error:
        problems = _roll_back(root, writes, before, completed, staged, created, keep, saved)
        if problems:
            raise RollbackIncomplete(
                f"the change failed ({error}) and its rollback is incomplete; nothing more "
                "was undone. Restore by hand: " + "; ".join(problems)
            ) from error
        raise
    return _clear_staging(root, staged)


class RollbackIncomplete(AdoptionError):
    """A failed change could not be fully undone; files are left where they are."""


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _roll_back(
    root: Path,
    writes: dict[str, str],
    before: dict[str, bytes | None],
    completed: list[str],
    staged: list[tuple[str, Path]],
    created: list[Path],
    keep: set[str],
    saved: Mapping[str, str],
) -> list[str]:
    """Undo a failed change in reverse; on the first failure, stop and describe the rest."""

    def copies(name: str) -> str:
        return f" (saved copy at {saved[name]})" if name in saved else ""

    for index in range(len(staged) - 1, -1, -1):
        name, target = staged[index]
        try:
            path = check_path(root, name)
            if path.exists():
                raise AdoptionError(f"{name} exists again")
            path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(target, path)
        except (AdoptionError, OSError, ValueError) as error:
            problems = [
                f"{n} was not restored ({error}); its original is at "
                f"{_relative(root, t)}{copies(n)}"
                for n, t in reversed(staged[: index + 1])
            ]
            left = [n for n in completed if n not in keep]
            if left:
                problems.append("new content was left in " + ", ".join(left))
            return problems
    for index in range(len(completed) - 1, -1, -1):
        name = completed[index]
        if name in keep:
            continue
        try:
            path = check_path(root, name)
            if path.read_bytes() != writes[name].encode():
                continue  # changed by someone else since; leave it
            original = before[name]
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)
        except (AdoptionError, OSError, ValueError) as error:
            left = [n for n in completed[: index + 1] if n not in keep]
            return [
                f"{name} could not be undone ({error})",
                "new content was left in " + ", ".join(left),
                *(f"{n} is saved at {s}" for n, s in saved.items()),
            ]
    for directory in reversed(created):
        try:
            directory.rmdir()
        except OSError:
            continue  # it holds a kept copy, or someone else's file
    _remove_empty(root, root / STAGING_DIRECTORY)
    return []


def _remove_empty(root: Path, folder: Path) -> None:
    """Remove empty directories below and including ``folder``, deepest first."""
    if not folder.is_dir() or folder.is_symlink():
        return
    for directory in sorted(folder.rglob("*"), key=lambda p: -len(p.parts)):
        if directory.is_dir() and not directory.is_symlink():
            try:
                directory.rmdir()
            except OSError:
                continue
    with contextlib.suppress(OSError):
        folder.rmdir()


def _clear_staging(root: Path, staged: list[tuple[str, Path]]) -> list[str]:
    """Remove staged files after success; report any that cannot be removed."""
    left = []
    for _, target in staged:
        try:
            target.unlink()
        except OSError:
            left.append(_relative(root, target))
    _remove_empty(root, root / STAGING_DIRECTORY)
    return left


def configure(
    project: Path,
    ref: str,
    *,
    apply: bool = False,
    host: str = "codex",
    adr_policy: str | None = None,
) -> dict:
    """Preview or apply the reviewed adoption plan with conflict preservation."""
    validate_bundle()
    if host not in HOST_PATHS:
        raise AdoptionError(f"unsupported native host: {host}")
    if not SHA.fullmatch(ref):
        raise AdoptionError(
            "use a reviewed, published full starter commit SHA; moving branches are not pins"
        )
    root = _adoption_root(project)
    validate_state_directory(root)
    require_tagged_release(ref, template_version())
    return _configure(root, ref, apply=apply, host=host, adr_policy=adr_policy)


def _configure(
    root: Path,
    ref: str,
    *,
    apply: bool,
    host: str,
    adr_policy: str | None,
) -> dict:
    policy, copies, working_policy = _policy_candidates(root, ref, adr_policy)
    _check_discovery(root, host)
    if host == "claude":
        local = check_path(root, ".claude/settings.local.json")
        if local.exists():
            # Only checked, never written: earlier starter activations here must be
            # reconciled by hand rather than silently left active.
            project_json(
                local.read_text(encoding="utf-8"),
                host,
                ref,
                bundle()["components"],
                marketplace(),
                retire=False,
            )
    paths = {
        name: check_path(root, name)
        for name in (
            configuration_path(root, host),
            BUNDLE_LOCK,
            ".gz-skills/settings.json",
            "AGENTS.skills-first.md",
            "AGENTS.md",
            update_skill_path(host),
        )
    }
    profile_check(paths[".gz-skills/settings.json"])
    paths.update({name: check_path(root, name) for name in copies})
    recorded = paths[BUNDLE_LOCK]
    carried = lock_extras(json.loads(recorded.read_bytes())) if recorded.exists() else {}
    candidates, lock = _configuration_candidates(
        paths, ref, host, policy=policy, working_policy=working_policy, carried=carried
    )
    candidates.update(copies)
    writes, before, present = _plan_writes(paths, candidates)
    if apply:
        _apply_writes(root, paths, writes, before)
    return {
        "status": "configured" if apply else "preview",
        "project": str(root),
        "writes": list(writes),
        "present": present,
        "runtime_readiness": "unverified",
        "host": host,
        "starter": lock["starter"],
        "adr_policy": policy,
        # Project-owned top-level lock keys, kept as recorded.
        "carried_lock_keys": list(carried),
        "next": [
            "Review the project instructions fragment; link it from existing AGENTS.md if needed.",
            "Profile selection belongs to canonical gz-skills setup; no profile is inferred or created.",
            "Follow docs/adoption.md for native installation and a fresh-session discovery check.",
            "Use the project gzl-update skill for released template updates; verify discovery separately.",
            "Review ADR policy/source provenance; configuration does not qualify the portable workflow.",
        ],
    }


def status(project: Path) -> dict:
    """Compare managed project files with this starter's expected content."""
    root = space_free(project).resolve(strict=True)
    validate_state_directory(root)
    path = check_path(root, BUNDLE_LOCK)
    if not path.exists():
        return {"status": "not configured", "runtime_readiness": "unverified"}
    lock = json.loads(path.read_text(encoding="utf-8"))
    ref, host = lock["starter"]["revision"], lock.get("host", "codex")
    version = lock["starter"].get("version")
    if not isinstance(ref, str) or not isinstance(version, str):
        raise AdoptionError("the lock has no valid starter release pin; reconcile its provenance")
    validate_bundle()
    if host not in HOST_PATHS:
        raise AdoptionError(f"unsupported native host: {host}")
    require_tagged_release(ref, version)
    expected = _configure(root, ref, apply=False, host=host, adr_policy=None)
    hosts = configured_hosts(root, host)
    pending = expected["writes"] + _other_host_pending(root, ref, host, hosts)
    return {
        "status": "configured" if not pending else "incomplete",
        "runtime_readiness": "unverified",
        "hosts": hosts,
        "pending_files": pending,
        "starter": lock["starter"],
        "components": lock["components"],
        "adr_policy": lock["adr_policy"],
    }


def _other_host_pending(root: Path, ref: str, recorded: str, hosts: list[str]) -> list[str]:
    """Files of the hosts besides the recorded one that differ from this release's."""
    policy, _, working = _policy_candidates(root, ref, None)
    placement = update_skill_placement(hosts, recorded)
    pending = []
    for host in hosts:
        if host == recorded:
            continue
        name = configuration_path(root, host)
        paths = {name: check_path(root, name), "AGENTS.md": check_path(root, "AGENTS.md")}
        candidates, _ = _configuration_candidates(
            paths, ref, host, policy=policy, working_policy=working
        )
        expected = {name: candidates[name]}
        skill = update_skill_path(host)
        if skill_surface(host) in placement and skill_surface(host) != skill_surface(recorded):
            expected[skill] = candidates[skill]
        for item, payload in expected.items():
            path = check_path(root, item)
            if not path.exists() or not same_text(path.read_bytes(), payload):
                pending.append(item)
    return pending


def _inherited_plugins(host: str) -> dict:
    """Read user activation for project overrides; never edit user settings."""
    home = Path.home()
    if host == "codex":
        path = space_free(Path(os.environ.get("CODEX_HOME", str(home / ".codex"))) / "config.toml")
        return tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if host == "claude":
        path = space_free(
            Path(os.environ.get("CLAUDE_CONFIG_DIR", str(home / ".claude"))) / "settings.json"
        )
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {}


def _scoped_config(existing: str, host: str, ref: str, parts: list[dict], catalog: str) -> str:
    """Apply native project precedence without invoking an installation command."""
    inherited = _inherited_plugins(host)
    if host == "codex":
        return codex_scope(existing, inherited, ref, parts, catalog)
    if host == "claude":
        return claude_scope(existing, inherited, ref, parts, catalog)
    return opencode_scope(existing, parts)


def localize(project: Path, ref: str, *, host: str, apply: bool = False) -> dict:
    """Repair only project activation, preserving global installs and adoption records."""
    validate_bundle()
    if host not in HOST_PATHS or not SHA.fullmatch(ref):
        raise AdoptionError("select a supported host and a full reviewed starter SHA")
    root = _adoption_root(project)
    parts = bundle()["components"]
    version = template_version()
    validate_state_directory(root)
    lock = check_path(root, BUNDLE_LOCK)
    if lock.exists():
        record = json.loads(lock.read_text(encoding="utf-8"))
        parts = record["components"]
        # The pinned catalog keeps the name its own release published.
        version = record.get("starter", {}).get("version")
        if not isinstance(version, str):
            raise AdoptionError(
                "the lock records no starter release; reconcile its provenance before repair"
            )
        if record["starter"].get("revision") != ref:
            raise AdoptionError("use the starter revision recorded in the lock for local repair")
        if {p["name"] for p in parts} != {p["name"] for p in bundle()["components"]}:
            raise AdoptionError("existing adoption components need explicit reconciliation")
        if any(not SHA.fullmatch(p["revision"]) for p in parts):
            raise AdoptionError("existing adoption component pins must be full SHAs")
    require_tagged_release(ref, version)
    catalog = marketplace_name(version)
    names = [configuration_path(root, host)]
    if host == "claude" and (root / ".claude/settings.local.json").exists():
        names.append(".claude/settings.local.json")
    paths = {name: check_path(root, name) for name in names}
    writes, before = {}, {}
    for name, path in paths.items():
        before[name] = path.read_bytes() if path.exists() else None
        existing = before[name].decode("utf-8") if before[name] is not None else ""
        payload = _scoped_config(existing, host, ref, parts, catalog)
        if before[name] != payload.encode("utf-8"):
            writes[name] = payload
    if apply:
        _apply_writes(root, paths, writes, before)
    return {
        "status": "localized" if apply else "preview",
        "project": str(root),
        "host": host,
        "writes": list(writes),
        "runtime_readiness": "unverified",
        "user_settings": "read only; global installations preserved",
        "adoption_record": "unchanged",
    }


def backport(project: Path) -> dict:
    """Assess structure from names only; never read records or move files."""
    root = space_free(project).resolve(strict=True)
    if not root.is_dir():
        raise AdoptionError("project must be an existing directory")
    entries = []
    truncated = False
    with os.scandir(root) as items:
        for entry in items:
            space_free(Path(entry.path))
            if len(entries) >= 200:
                truncated = True
                break
            entries.append(
                {
                    "path": entry.name,
                    "kind": "symlink"
                    if entry.is_symlink()
                    else "directory"
                    if entry.is_dir(follow_symlinks=False)
                    else "file",
                }
            )
    names = {e["path"] for e in entries if e["kind"] != "symlink"}
    targets = [
        ("AGENTS.md", "Agent entry and links to project authorities"),
        ("docs/project/", "Purpose, architecture, and decisions when useful"),
        ("skills/", "Project-owned operational workflows; preserve native discovery"),
        (
            "src/<package>/ for Python",
            "Installed application/library code under the adopted Astral baseline; map existing sources and required refactors",
        ),
        (
            "existing data/evidence layout",
            "Keep inputs, records, and products separate from skills",
        ),
        (
            "existing planning authority",
            "Keep current backlog and handoff practice while SP-BP is deferred",
        ),
    ]
    return {
        "status": "assessment",
        "project": str(root),
        "writes": [],
        "inventory": sorted(entries, key=lambda e: e["path"]),
        "inventory_truncated": truncated,
        "preferred_structure": [{"target": t, "purpose": purpose} for t, purpose in targets],
        "existing_entrypoints": sorted(
            names & {"AGENTS.md", "README.md", "ROADMAP.md", "BACKLOG.md", "skills", "src", "docs"}
        ),
        "next": [
            "Read governing instructions; map existing sources to useful targets with authority and disposition recorded.",
            "Assess Python layout against the adopted Astral baseline; plan required refactors or evidence-backed exceptions while preserving public behavior and project authorities.",
            "Implement authorized changes in small verified steps; update imports, links, discovery, and verification commands for each move.",
        ],
        "backplane": "deferred",
        "assessment_limit": "Top-level names only; not a reviewed migration plan or code audit.",
    }


def source_revision() -> str:
    """Default only to this clean starter checkout, never a parent app's HEAD."""

    def git(*args: str) -> str:
        # Hook-exported GIT_* variables would redirect this to another repository.
        return subprocess.run(
            ["git", "-C", str(HERE), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=HERE,
            env=clean_git_env(),
        ).stdout.strip()

    if Path(git("rev-parse", "--show-toplevel")).resolve() != HERE:
        raise AdoptionError("run from a standalone starter checkout or supply --starter-ref")
    origin = git("remote", "get-url", "origin")
    if origin not in STARTER_SOURCES:
        raise AdoptionError("this is an adopting repo; supply the published starter --starter-ref")
    if git("status", "--porcelain"):
        raise AdoptionError("starter checkout is dirty; use a reviewed clean revision")
    return git("rev-parse", "HEAD")


def _add_vendor_parser(sub) -> None:
    """Register ``vendor`` and its subcommands."""
    vendor_parser = sub.add_parser(
        "vendor", help="vendor pinned gz-skills snapshots and keep them current"
    )
    actions = vendor_parser.add_subparsers(dest="vendor_command", required=True)

    def source_arguments(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--source", type=Path, help="local gz-skills checkout")
        parser.add_argument(
            "--revision",
            help="gz-skills revision to fetch when no --source; default is the bundle.json pin "
            "(a branch or tag name is an explicit opt-in to a moving ref)",
        )

    source_arguments(actions.add_parser("list", help="list the skills a source offers"))
    install_parser = actions.add_parser("install", help="install pinned skill snapshots")
    install_parser.add_argument("skills", nargs="*")
    install_parser.add_argument("--all", action="store_true", help="install every skill")
    install_parser.add_argument("--force", action="store_true")
    install_parser.add_argument(
        "--surface", choices=sorted(vendor_commands.SURFACES), default="agents"
    )
    install_parser.add_argument("--lock", type=Path)
    where = install_parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--project", type=Path)
    where.add_argument("--user", action="store_true")
    where.add_argument("--target", type=Path, help="exact skills directory")
    source_arguments(install_parser)
    actions.add_parser("status", help="compare a lock with its installed trees").add_argument(
        "--lock", type=Path, required=True
    )
    update_parser = actions.add_parser("update", help="preview or apply updates for one lock")
    update_parser.add_argument("--lock", type=Path, required=True)
    update_parser.add_argument("--apply", action="store_true")
    source_arguments(update_parser)
    propagate_parser = actions.add_parser("propagate", help="update every lock below a root")
    propagate_parser.add_argument("root", type=Path)
    propagate_parser.add_argument("--apply", action="store_true")
    source_arguments(propagate_parser)


def _gz_skills_pin() -> str:
    """The gz-skills commit this release pins in bundle.json."""
    for part in bundle()["components"]:
        if part["name"] == "gz-skills":
            return part["revision"]
    raise AdoptionError("bundle.json has no gz-skills component")


def _vendor(args: argparse.Namespace) -> tuple[object, int]:
    """Run a vendor subcommand; return its result and exit status.

    Arguments are validated before any fetch, and the source is resolved only
    when needed. Without --source the pinned gz-skills revision is fetched.
    """
    command = args.vendor_command
    if command == "status":
        report = vendor_commands.status(args.lock)
        return report, 0 if report["current"] else 1
    revision = args.revision or _gz_skills_pin()
    if command == "update":
        report = vendor_commands.update(
            args.lock, apply=args.apply, source=args.source, revision=revision
        )
        return report, 1 if report["blocked"] else 0
    if command == "propagate":
        report = vendor_commands.propagate(
            args.root, apply=args.apply, source=args.source, revision=revision
        )
        return report, 1 if report["blocked"] else 0
    if command == "list":
        source = vendor_commands.resolve_source(revision, source=args.source)
        return vendor_commands.list_skills(source), 0
    if args.all == bool(args.skills):
        raise ValueError("name skills or use --all, not both or neither")
    target, lock = vendor_commands.resolve_destination(
        project=args.project,
        user=args.user,
        target=args.target,
        surface=args.surface,
        lock=args.lock,
    )
    source = vendor_commands.resolve_source(revision, source=args.source)
    names = (
        [skill["name"] for skill in vendor_commands.list_skills(source)]
        if args.all
        else args.skills
    )
    return vendor_commands.install(source, names, target, lock=lock, force=args.force), 0


def _run_check_command(args: argparse.Namespace) -> int:
    """Run read-only check commands and retain their documented exit codes."""
    if args.command == "verify":
        try:
            from gzlite.verification import verify_project
        except ModuleNotFoundError as error:
            if error.name != "yaml":
                raise
            print("verification blocked: install gzlite[verification]", file=sys.stderr)
            return 1
        return verify_project(args.project)
    if args.command == "portability":
        # A check command, not adoption: findings exit 1, usage errors exit 2.
        try:
            findings = portability_audit(
                args.root, args.check or list(PORTABILITY_CHECKS), args.path
            )
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print(json.dumps(findings, indent=2))
        return 1 if findings else 0
    if args.command == "catalog":
        # A check command, not adoption: findings exit 1, usage errors exit 2.
        try:
            run = (
                catalog_commands.check
                if args.catalog_command == "check"
                else catalog_commands.inventory
            )
            result = run(args.root)
        except (OSError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2))
        return 1 if result and args.catalog_command == "check" else 0
    else:
        from gzlite.release_check import check_release_integrity, local_tags, published_targets

        try:
            root = args.project.resolve(strict=True)
            findings = check_release_integrity(
                root,
                published=args.published,
                tags=local_tags(root),
                releases=published_targets(root) if args.published else None,
            )
        except (OSError, ValueError, subprocess.SubprocessError, KeyError, TypeError) as error:
            print(f"release check blocked: {error}", file=sys.stderr)
            return 2
        print(json.dumps(findings, indent=2))
        return int(bool(findings))


def _settings_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict:
    """Validate profile selection before dispatching the settings operation."""
    if (args.action == "select") != (args.profile is not None):
        parser.error("--profile is required for, and only valid with, select")
    if args.action == "select":
        return settings_select(args.project, args.profile)
    if args.action == "initialize":
        return settings_initialize(args.project)
    return settings_inspect(args.project)


def main(argv: list[str] | None = None) -> int:
    """Dispatch the public CLI and render structured outcomes and failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    configure_parser = sub.add_parser(
        "configure", help="preview project configuration; --apply writes it"
    )
    configure_parser.add_argument("--project", type=Path, required=True)
    configure_parser.add_argument(
        "--starter-ref", help="full published starter SHA; defaults to this checkout HEAD"
    )
    configure_parser.add_argument("--apply", action="store_true")
    configure_parser.add_argument("--host", choices=tuple(HOST_PATHS), default="codex")
    configure_parser.add_argument(
        "--adr-policy",
        choices=("link", "local"),
        help="policy access; omitted preserves the recorded choice, otherwise defaults to link",
    )
    localize_parser = sub.add_parser(
        "localize",
        help="preview repo activation repair; preserve user installs and adoption records",
    )
    localize_parser.add_argument("--project", type=Path, required=True)
    localize_parser.add_argument("--host", choices=tuple(HOST_PATHS), required=True)
    localize_parser.add_argument("--starter-ref", required=True)
    localize_parser.add_argument("--apply", action="store_true")
    migrate_parser = sub.add_parser(
        "migrate",
        help="preview moving legacy gz-starter or skills-first state into gzlite; "
        "--apply --fingerprint writes the reviewed plan",
    )
    migrate_parser.add_argument("--project", type=Path, required=True)
    migrate_parser.add_argument(
        "--starter-ref", help="full published gzlite SHA; defaults to this checkout HEAD"
    )
    migrate_parser.add_argument("--apply", action="store_true")
    migrate_parser.add_argument("--fingerprint", help="the fingerprint of the reviewed preview")
    freshen_parser = sub.add_parser(
        "freshen",
        help="preview bringing a gzlite adopter to this release; "
        "--apply --fingerprint writes the reviewed plan",
    )
    freshen_parser.add_argument("--project", type=Path, required=True)
    freshen_parser.add_argument(
        "--starter-ref", help="full published gzlite SHA; defaults to this checkout HEAD"
    )
    freshen_parser.add_argument("--apply", action="store_true")
    freshen_parser.add_argument("--fingerprint", help="the fingerprint of the reviewed preview")
    launch_parser = sub.add_parser(
        "run-opencode", help="run a private OpenCode server with project-only plugin selection"
    )
    launch_parser.add_argument("--project", type=Path, required=True)
    launch_parser.add_argument("arguments", nargs=argparse.REMAINDER)
    status_parser = sub.add_parser(
        "status", help="inspect configuration without claiming runtime installation"
    )
    status_parser.add_argument("--project", type=Path, required=True)
    backport_parser = sub.add_parser("backport", help="read-only preferred-structure assessment")
    backport_parser.add_argument("--project", type=Path, required=True)
    verify_parser = sub.add_parser("verify", help="check adopter artifacts and run required tests")
    verify_parser.add_argument("--project", type=Path, required=True)
    settings_parser = sub.add_parser(
        "project-settings", help="inspect, initialize or select the project work-progression mode"
    )
    settings_parser.add_argument("action", choices=("inspect", "initialize", "select"))
    settings_parser.add_argument("--project", type=Path, required=True)
    settings_parser.add_argument("--profile", choices=("lite", "heavy"))
    portability_parser = sub.add_parser(
        "portability", help="read-only line-ending and subprocess-decoding audit"
    )
    portability_parser.add_argument("--root", type=Path, default=Path.cwd())
    portability_parser.add_argument("--check", action="append", choices=PORTABILITY_CHECKS)
    portability_parser.add_argument("--path", action="append", default=[])
    catalog_parser = sub.add_parser(
        "catalog", help="read-only maintainer checks for a skills catalog"
    )
    catalog_actions = catalog_parser.add_subparsers(dest="catalog_command", required=True)
    for action, text in (
        ("check", "report where a skills catalog disagrees with itself"),
        ("inventory", "list a catalog's authored skills"),
    ):
        catalog_actions.add_parser(action, help=text).add_argument(
            "--root", type=Path, default=Path.cwd()
        )
    release_parser = sub.add_parser("release", help="inspect publisher release integrity")
    release_commands = release_parser.add_subparsers(dest="release_command", required=True)
    release_check = release_commands.add_parser("check", help="verify versions, changelog and tags")
    release_check.add_argument("--project", type=Path, default=Path.cwd())
    release_check.add_argument(
        "--published", action="store_true", help="also verify GitHub releases"
    )

    _add_vendor_parser(sub)
    sub.add_parser("validate", help="validate the three bundle pins and both native catalogs")
    sub.add_parser("version", help="show this checkout's template version; not a release receipt")
    args = parser.parse_args(argv)
    if args.command in {"verify", "portability", "catalog", "release"}:
        return _run_check_command(args)
    try:
        if args.command == "vendor":
            result, code = _vendor(args)
            print(json.dumps(result, indent=2))
            return code
        if args.command == "run-opencode":
            root = _adoption_root(args.project)
            arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
            return launch_opencode(root, arguments)
        if args.command == "configure":
            result = configure(
                args.project,
                args.starter_ref or source_revision(),
                apply=args.apply,
                host=args.host,
                adr_policy=args.adr_policy,
            )
        elif args.command == "localize":
            result = localize(args.project, args.starter_ref, host=args.host, apply=args.apply)
        elif args.command == "migrate":
            # Imported here: migrate builds on this module's configure machinery.
            from gzlite.migrate import migrate

            result = migrate(
                args.project,
                apply=args.apply,
                fingerprint=args.fingerprint,
                ref=args.starter_ref or source_revision(),
            )
        elif args.command == "freshen":
            # Imported here: freshen builds on this module's configure machinery.
            from gzlite.freshen import freshen

            result = freshen(
                args.project,
                apply=args.apply,
                fingerprint=args.fingerprint,
                ref=args.starter_ref or source_revision(),
            )
        elif args.command == "backport":
            result = backport(args.project)
        elif args.command == "status":
            result = status(args.project)
        elif args.command == "project-settings":
            result = _settings_command(args, parser)
        elif args.command == "version":
            result = {"template_version": template_version()}
        else:
            validate_bundle()
            result = {
                "status": "valid",
                "template_version": template_version(),
                "components": bundle()["components"],
            }
        print(json.dumps(result, indent=2))
        return 0
    except (AdoptionError, OSError, ValueError, subprocess.SubprocessError, KeyError) as error:
        print(f"adoption blocked: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
