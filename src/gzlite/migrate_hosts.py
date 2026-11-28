"""Classify a legacy adopter's host configuration for ``gzlite migrate``.

For every configured host (Codex, Claude Code, OpenCode) this retires the
entries earlier starter releases wrote and judges whether they were edited:
strict retirement failing, an outside activation of a bundle component, OpenCode
plugin entries other than the ones configure wrote, or a comment the rewrite
would drop. Only reads; ``migrate`` saves edited originals before writing.
"""

from __future__ import annotations

import copy
import json
import re
import tomllib
from collections import Counter
from dataclasses import dataclass, field

from gzlite.cli import AdoptionError
from gzlite.migrate_legacy import UNCHANGED, LegacyLock, Reader
from gzlite.native import HOST_PATHS, configuration_path
from gzlite.native_identity import (
    _claude_entry_is_starter,
    _codex_entry_is_starter,
    is_starter_marketplace,
    retire_claude,
    retire_codex,
)
from gzlite.native_json import TOKENS, document, replace_fields
from gzlite.native_scope import _managed_target, _set_plugin_state

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
    # Starter-named catalogs whose entry was not the starter's: name -> where it pointed.
    repurposed: dict[str, str] = field(default_factory=dict)
    # Activations of bundle components from another catalog, now disabled.
    disabled: list[str] = field(default_factory=list)

    def guidance(self, saved: str, current: str) -> list[str]:
        """Tell the maintainer how to undo each retirement or disabled activation."""
        notes = []
        for name, where in self.repurposed.items():
            notes.append(
                f"{self.path}: catalog {name} pointed at {where}, not at the starter; it was "
                "retired with the starter's entries under that name. To keep that catalog, "
                "re-add it in this file under a new name that no starter release uses (not "
                "skills-first-starter, gz-starter-* or gzlite-*), with the source and ref from "
                f"{saved}, and rename its plugin keys from @{name} to the new name"
            )
        for identity in self.disabled:
            component = identity.partition("@")[0]
            how = (
                f'set enabled = true in [plugins."{identity}"]'
                if self.host == "codex"
                else f'set "{identity}": true under enabledPlugins'
            )
            notes.append(
                f"{self.path}: {identity} was active and is now disabled, so the {current} "
                f"bundle is the only source of {component}. To re-enable it, {how} in "
                f"{self.path}; while gzlite's bundle provides {component}, configure and "
                "status then refuse it as duplicate discovery"
            )
        return notes


def _source_is_starter(identity: str) -> bool:
    return is_starter_marketplace(identity.partition("@")[2])


def _repurposed(marketplaces: object, current: str, is_starter) -> dict[str, str]:
    """Starter-named catalog entries that are not what a starter release wrote."""
    found = {}
    if isinstance(marketplaces, dict):
        for name, entry in marketplaces.items():
            if name != current and is_starter_marketplace(name) and not is_starter(entry):
                found[name] = json.dumps(entry, sort_keys=True)
    return found


def _disable_outside(names: set[str], current: str, identity: str, enabled: object) -> bool:
    name, _, source = identity.partition("@")
    return name in names and source != current and enabled is not False


def _codex(config: HostConfig, parts: list[dict], current: str) -> None:
    text = config.retired
    config.repurposed = _repurposed(
        tomllib.loads(text).get("marketplaces"), current, _codex_entry_is_starter
    )
    try:
        text = retire_codex(text, current, parts)
    except ValueError as error:
        config.edits.append(str(error).split("; ")[0])
        text = retire_codex(text, current, parts, strict=False)
    names = {part["name"] for part in parts}
    data = tomllib.loads(text)
    for identity, value in data.get("plugins", {}).items():
        enabled = value.get("enabled") if isinstance(value, dict) else value
        if _disable_outside(names, current, identity, enabled):
            text = _set_plugin_state(text, identity, False)
            config.edits.append(f"{identity} was active outside the bundle; now disabled")
            config.disabled.append(identity)
    config.retired = text
    config.carried += [
        f"catalog {name} in {config.path}"
        for name in data.get("marketplaces", {})
        if not is_starter_marketplace(name)
    ]


def _claude(config: HostConfig, parts: list[dict], current: str) -> None:
    text = config.retired
    data, _ = document(text)
    config.repurposed = _repurposed(
        data.get("extraKnownMarketplaces"), current, _claude_entry_is_starter
    )
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
            if _disable_outside(names, current, identity, active):
                plugins[identity] = False
                config.edits.append(f"{identity} was active outside the bundle; now disabled")
                config.disabled.append(identity)
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
    # Any bundle-component entry counts, whatever pin it names: pins move to the bundle.
    parts = [dict(part) for part in lock.components]
    return isinstance(plugins, list) and any(
        isinstance(p, str) and _managed_target(p, parts) for p in plugins
    )


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


_TOML_STRING = re.compile(r'"(?:\\.|[^"\\])*"|\'[^\']*\'')


def _toml_comments(text: str) -> list[str]:
    """Every ``#`` comment outside a single-line string, whole-line or inline."""
    comments = []
    for line in text.splitlines():
        bare = _TOML_STRING.sub('""', line)
        if "#" in bare:
            comments.append(bare.split("#", 1)[1].strip())
    return comments


def lost_comments(host: str, before: str, after: str) -> bool:
    """Whether a rewrite drops a comment; configure never wrote one, so it is local."""
    if host == "codex":
        comments, kept = _toml_comments(before), _toml_comments(after)
    else:
        comments = [m.group() for m in TOKENS.finditer(before) if m.group()[:2] in ("//", "/*")]
        kept = [m.group() for m in TOKENS.finditer(after) if m.group()[:2] in ("//", "/*")]
    return bool(Counter(comments) - Counter(kept))
