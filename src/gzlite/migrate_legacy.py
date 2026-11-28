"""Read and classify a legacy gz-starter or skills-first adopter for ``migrate``.

Everything here only reads. ``migrate`` builds and applies the plan; this
module decides what the adopter holds: where its legacy state is, what its lock
says, which hosts it configured, and which bytes differ from what the recorded
commit's ``configure`` wrote (the drift rule's "edited").

"Edited" compares text with CRLF line endings normalized to LF, so a checkout
with ``core.autocrlf`` is never mistaken for a hand edit.
"""

from __future__ import annotations

import copy
import json
import os
import re
import stat
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from gzlite.cli import AdoptionError, check_path, lock_extras
from gzlite.history import Release
from gzlite.native import HOST_PATHS, configuration_path
from gzlite.native_identity import (
    STARTER_SOURCES,
    is_starter_marketplace,
    retire_claude,
    retire_codex,
)
from gzlite.native_json import TOKENS, document, replace_fields
from gzlite.native_scope import _managed_target, _set_plugin_state
from gzlite.paths import (
    BUNDLE_LOCK,
    LEGACY_DIRECTORIES,
    LOCAL_ADR_POLICY,
    STATE_DIRECTORY,
    STATE_SETTINGS,
    space_free,
)

STATE_FILES = tuple(Path(name).name for name in (BUNDLE_LOCK, LOCAL_ADR_POLICY, STATE_SETTINGS))
ADR_COPY = Path(LOCAL_ADR_POLICY).name
# The three names the starter published under; never gzlite, which has no legacy state.
HISTORICAL_SOURCES = frozenset(source for source in STARTER_SOURCES if "/gzlite" not in source)
VERSION = re.compile(r"v?((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))\Z")
REVISION = re.compile(r"[0-9a-fA-F]{40}\Z")
UNCHANGED = "no files changed"


def normalized(text: str) -> str:
    """Compare text the way git's line-ending conversion leaves it."""
    return text.replace("\r\n", "\n")


def decode(name: str, data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AdoptionError(
            f"{name} is not UTF-8 text; reconcile it by hand; {UNCHANGED}"
        ) from error


class Reader:
    """Read project files once each and remember their bytes as fingerprint inputs."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.inputs: dict[str, bytes] = {}

    def read(self, name: str) -> bytes | None:
        if name in self.inputs:
            return self.inputs[name]
        path = check_path(self.root, name)
        if not path.exists():
            return None
        data = path.read_bytes()
        self.inputs[name] = data
        return data

    def text(self, name: str) -> str | None:
        data = self.read(name)
        return None if data is None else decode(name, data)


def is_link(path: Path) -> bool:
    """Treat symlinks and Windows reparse points (junctions) alike."""
    info = path.lstat()
    attributes = getattr(info, "st_file_attributes", 0)
    return stat.S_ISLNK(info.st_mode) or bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def refuse_go_project(root: Path) -> None:
    if (root / "go.mod").exists() and not (root / "pyproject.toml").exists():
        raise AdoptionError(
            "this is a Go project (go.mod and no pyproject.toml); migrate it to gzglite, "
            f"the Go tier, not gzlite; {UNCHANGED}"
        )


def legacy_directory(root: Path) -> str | None:
    """Return the one legacy state folder holding starter state, if any.

    Both legacy folders present is dual state (as in ``xplane-webapi``) and is
    refused even when one is empty: which one is authoritative is the
    maintainer's call. A lone folder without any state file is not starter state.
    """
    present = [name for name in LEGACY_DIRECTORIES if os.path.lexists(root / name)]
    if len(present) > 1:
        raise AdoptionError(
            "both .gz-starter/ and .skills-first/ exist; decide by hand which one holds "
            f"the adoption and remove the other; {UNCHANGED}"
        )
    if not present:
        return None
    name = present[0]
    folder = space_free(root / name)
    if is_link(folder):
        raise AdoptionError(
            f"{name} is a link; migrate reads only a real state folder; {UNCHANGED}"
        )
    if not folder.is_dir():
        raise AdoptionError(f"{name} is not a directory; {UNCHANGED}")
    if not any(os.path.lexists(folder / state) for state in STATE_FILES):
        return None
    return name


def refuse_gzlite_state(root: Path) -> None:
    """Legacy state next to files in ``.gzlite/`` cannot be merged safely."""
    folder = root / STATE_DIRECTORY
    if not os.path.lexists(folder):
        return
    if is_link(folder) or not folder.is_dir():
        raise AdoptionError(f"{STATE_DIRECTORY} is a link or not a directory; {UNCHANGED}")
    if any(not item.is_dir() or is_link(item) for item in folder.rglob("*")):
        raise AdoptionError(
            f"{STATE_DIRECTORY}/ already holds files while legacy state exists; "
            f"reconcile by hand; {UNCHANGED}"
        )


def tree(root: Path, name: str) -> tuple[list[str], list[str]]:
    """List a directory's files and subdirectories (innermost first), refusing links."""
    files: list[str] = []
    directories: list[str] = []
    pending = [name]
    while pending:
        current = pending.pop()
        for child in sorted((root / current).iterdir()):
            relative = f"{current}/{child.name}"
            space_free(child)
            if is_link(child):
                raise AdoptionError(f"{relative} is a link; reconcile it by hand; {UNCHANGED}")
            if child.is_dir():
                directories.append(relative)
                pending.append(relative)
            elif child.is_file():
                files.append(relative)
            else:
                raise AdoptionError(f"{relative} is not a regular file; {UNCHANGED}")
    directories.sort(key=lambda item: (-item.count("/"), item))
    return sorted(files), [*directories, name]


@dataclass(frozen=True)
class LegacyLock:
    """What a legacy lock records, normalized; ``notes`` become findings."""

    version: str
    revision: str
    host: str
    adr_mode: str
    components: tuple[dict, ...]
    extras: dict
    notes: tuple[str, ...]


def _version(starter: dict, unreadable) -> tuple[str, list[str]]:
    """Read ``starter.version`` or the hand-written ``starter.release`` ("v0.6.0")."""
    declared = {}
    for key in ("version", "release"):
        value = starter.get(key)
        if value is None:
            continue
        match = VERSION.fullmatch(value) if isinstance(value, str) else None
        if match is None:
            raise unreadable(f"starter.{key} is not a release version")
        declared[key] = match[1]
    if not declared:
        raise unreadable("the starter record names no version")
    if len(set(declared.values())) > 1:
        raise unreadable("starter.version and starter.release disagree")
    version = next(iter(declared.values()))
    notes = []
    if "version" not in declared:
        notes.append(f"starter.release {starter['release']!r} read as version {version}")
    for key in sorted(set(starter) - {"repository", "version", "release", "revision"}):
        notes.append(f"starter.{key} is not carried; gzlite records repository, version, revision")
    return version, notes


def parse_lock(name: str, data: bytes) -> LegacyLock:
    """Read any legacy lock shape from 0.1.0 on, or refuse it as unreadable."""

    def unreadable(why: str) -> AdoptionError:
        return AdoptionError(f"{name} cannot be read safely: {why}; {UNCHANGED}")

    try:
        lock = json.loads(data)
    except ValueError as error:
        raise unreadable(f"not valid JSON ({error})") from error
    if not isinstance(lock, dict):
        raise unreadable("not a JSON object")
    if type(lock.get("schema_version")) is not int or lock["schema_version"] != 1:
        raise unreadable("unsupported schema_version")
    starter = lock.get("starter")
    if not isinstance(starter, dict):
        raise unreadable("no starter record")
    if starter.get("repository") not in HISTORICAL_SOURCES:
        raise unreadable("starter.repository is not a gz-starter repository")
    revision = starter.get("revision")
    if not isinstance(revision, str) or not REVISION.fullmatch(revision):
        raise unreadable("starter.revision is not a full commit SHA")
    version, notes = _version(starter, unreadable)
    components = lock.get("components")
    if not isinstance(components, list) or any(
        not isinstance(part, dict)
        or not all(isinstance(part.get(key), str) for key in ("name", "repository", "revision"))
        for part in components
    ):
        raise unreadable("components must be a list of named, pinned repositories")
    host = lock.get("host", "codex")
    if host not in HOST_PATHS:
        raise unreadable(f"unsupported host {host!r}")
    policy = lock.get("adr_policy")
    if policy is None:
        mode = "link"
    elif isinstance(policy, dict) and policy.get("mode") in ("link", "local"):
        mode = policy["mode"]
    else:
        raise unreadable("adr_policy.mode must be link or local")
    return LegacyLock(
        version=version,
        revision=revision.lower(),
        host=host,
        adr_mode=mode,
        components=tuple(components),
        extras=lock_extras(lock),
        notes=tuple(notes),
    )


# What the recorded commit's configure wrote, by managed path (see ManagedPath).


def release_fragment(release: Release, ref: str, mode: str) -> str:
    text = release.fragment_template
    if not release.adr_placeholders:
        return text
    if release.adr_policy_url is None:
        raise AdoptionError(f"history for {release.revision} lacks its ADR policy URL")
    url = release.adr_policy_url.replace("{ref}", ref)
    working = f"{release.state_directory}/{ADR_COPY}" if mode == "local" else url
    return text.replace("{{ADR_POLICY_WORKING_SOURCE}}", working).replace(
        "{{ADR_POLICY_CANONICAL_URL}}", url
    )


def skill_template(release: Release, path: str) -> str | None:
    """The template of a starter skill path (update skill or front door), else None."""
    for name, template in (
        (release.update_skill, release.update_skill_template),
        (release.front_door_skill, release.front_door_skill_template),
    ):
        if name and path.endswith(f"/skills/{name}/SKILL.md"):
            return template
    return None


def adr_copy_template(release: Release, legacy: str, mode: str) -> str | None:
    """The ADR policy copy configure wrote into ``legacy``, or None if it wrote none."""
    if mode != "local" or release.adr_policy_template is None:
        return None
    wrote = any(
        entry.condition == "adr-local" and entry.path == f"{legacy}/{ADR_COPY}"
        for host in release.hosts
        for entry in release.managed_entries(host)
    )
    return release.adr_policy_template if wrote else None


# Host configuration: retire earlier starter entries and judge whether they were edited.


@dataclass
class HostConfig:
    """One configured host's file before and after retiring starter entries."""

    host: str
    path: str
    original: str | None
    retired: str
    edits: list[str] = field(default_factory=list)
    carried: list[str] = field(default_factory=list)


def _source_is_starter(identity: str) -> bool:
    return is_starter_marketplace(identity.partition("@")[2])


def _codex(config: HostConfig, parts: list[dict], current: str) -> None:
    text = config.retired
    try:
        text = retire_codex(text, current, parts)
    except ValueError as error:
        config.edits.append(str(error).split("; ")[0])
        text = retire_codex(text, current, parts, strict=False)
    names = {part["name"] for part in parts}
    data = tomllib.loads(text)
    for identity, value in data.get("plugins", {}).items():
        name, _, source = identity.partition("@")
        enabled = value.get("enabled") if isinstance(value, dict) else value
        if name in names and source != current and enabled is not False:
            text = _set_plugin_state(text, identity, False)
            config.edits.append(f"{identity} was active outside the bundle; now disabled")
    config.retired = text
    config.carried += [
        f"catalog {name} in {config.path}"
        for name in data.get("marketplaces", {})
        if not is_starter_marketplace(name)
    ]


def _claude(config: HostConfig, parts: list[dict], current: str) -> None:
    text = config.retired
    data, _ = document(text)
    trial = copy.deepcopy(data)
    try:
        retire_claude(trial, current, parts)
        data = trial
    except ValueError as error:
        config.edits.append(str(error).split("; ")[0])
        retire_claude(data, current, parts, strict=False)
    names = {part["name"] for part in parts}
    plugins = data.get("enabledPlugins")
    if isinstance(plugins, dict):
        for identity, active in plugins.items():
            name, _, source = identity.partition("@")
            if name in names and source != current and active is not False:
                plugins[identity] = False
                config.edits.append(f"{identity} was active outside the bundle; now disabled")
    config.retired = replace_fields(text, data)
    known = data.get("extraKnownMarketplaces")
    config.carried += [
        f"catalog {name} in {config.path}"
        for name in (known if isinstance(known, dict) else {})
        if not is_starter_marketplace(name)
    ]


def _opencode_written(lock: LegacyLock) -> list[str]:
    """The OpenCode plugin entries configure wrote for the lock's components."""
    entries = ["-" + part["name"] for part in lock.components]
    return entries + [
        f"git+{part['repository']}.git#{part['revision']}"
        for part in lock.components
        if part.get("enabled_by_default") is True
    ]


def _opencode(config: HostConfig, parts: list[dict], lock: LegacyLock, version: str) -> None:
    text = config.retired
    data, _ = document(text)
    plugins = data.get("plugins", [])
    if not isinstance(plugins, list) or any(not isinstance(p, str) for p in plugins):
        raise AdoptionError(f"{config.path} plugins must be package strings; {UNCHANGED}")
    managed = [p for p in plugins if _managed_target(p, parts)]
    if managed != _opencode_written(lock):
        config.edits.append(f"the bundle's plugin entries differ from what {version} wrote")
    data["plugins"] = [p for p in plugins if not _managed_target(p, parts)]
    config.retired = replace_fields(text, data) if text else ""
    config.carried += [f"plugin {p} in {config.path}" for p in data["plugins"]]


def _configured(host: str, text: str, lock: LegacyLock) -> bool:
    """Whether a host's file carries entries a starter release wrote."""
    if not text:
        return False
    if host == "codex":
        data = tomllib.loads(text)
        names = [*data.get("marketplaces", {}), *data.get("plugins", {})]
        return any(is_starter_marketplace(n) or _source_is_starter(n) for n in names)
    data, _ = document(text)
    if host == "claude":
        known, plugins = data.get("extraKnownMarketplaces"), data.get("enabledPlugins")
        names = [*(known if isinstance(known, dict) else {})]
        names += [*(plugins if isinstance(plugins, dict) else {})]
        return any(is_starter_marketplace(n) or _source_is_starter(n) for n in names)
    plugins = data.get("plugins")
    written = set(_opencode_written(lock))
    return isinstance(plugins, list) and any(p in written for p in plugins)


def host_configs(
    reader: Reader, lock: LegacyLock, version: str, parts: list[dict], current: str
) -> list[HostConfig]:
    """Every configured host, the lock's first: the lock records only the last one."""
    found = []
    for host in sorted(HOST_PATHS, key=lambda item: (item != lock.host, item)):
        path = configuration_path(reader.root, host)
        original = reader.text(path)
        if host != lock.host and not _configured(host, original or "", lock):
            continue
        config = HostConfig(host, path, original, original or "")
        if host == "codex":
            _codex(config, parts, current)
        elif host == "claude":
            _claude(config, parts, current)
        else:
            _opencode(config, parts, lock, version)
        found.append(config)
    return found


def lost_comments(host: str, before: str, after: str) -> bool:
    """Whether a rewrite drops a comment; configure never wrote one, so it is local."""
    if host == "codex":
        comments = [line.strip() for line in before.splitlines() if line.strip().startswith("#")]
        kept = [line.strip() for line in after.splitlines() if line.strip().startswith("#")]
    else:
        comments = [m.group() for m in TOKENS.finditer(before) if m.group()[:2] in ("//", "/*")]
        kept = [m.group() for m in TOKENS.finditer(after) if m.group()[:2] in ("//", "/*")]
    return bool(Counter(comments) - Counter(kept))


# pyproject.toml: the verification extra's dev dependency.

_REQUIREMENT = re.compile(
    r"gz-starter\[verification\]\s*@\s*git\+https://github\.com/tvproductions/"
    r"(?:gz-starter|gz-skills-first-starter|skills-first-starter)(?:\.git)?@[0-9a-fA-F]{40}"
)
_QUOTED = re.compile(r"(?P<q>[\"'])(?P<value>" + _REQUIREMENT.pattern + r")(?P=q)")


def _substituted(value: object, new: str) -> object:
    if isinstance(value, str):
        return new if _REQUIREMENT.fullmatch(value) else value
    if isinstance(value, list):
        return [_substituted(item, new) for item in value]
    if isinstance(value, dict):
        return {key: _substituted(item, new) for key, item in value.items()}
    return value


def rename_verification(text: str, requirement: str) -> str:
    """Rewrite the ``gz-starter[verification] @ git+…@SHA`` string in place.

    The result must parse to the same TOML with only that string changed;
    anything else (an inline table, a uv source) is left for the maintainer.
    """
    renamed = _QUOTED.sub(lambda m: m["q"] + requirement + m["q"], text)
    if renamed == text:
        return text
    if tomllib.loads(renamed) != _substituted(tomllib.loads(text), requirement):
        raise AdoptionError(
            f"pyproject.toml's gz-starter[verification] dependency needs a manual rename; {UNCHANGED}"
        )
    return renamed
