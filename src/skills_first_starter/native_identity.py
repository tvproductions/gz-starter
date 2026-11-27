"""Name the native marketplace per starter version and retire earlier names.

Codex keeps one cached checkout per marketplace name. When every adopter used
the same name, projects pinned to different starter revisions overwrote each
other's cache. Each release after 0.12.1 therefore names its own catalog, so
projects on one version share a slot safely and other versions never collide.
"""

import re
import tomllib

LEGACY_MARKETPLACE = "skills-first-starter"
LAST_UNVERSIONED = (0, 12, 1)
_VERSIONED = re.compile(r"gz-starter-[0-9]+-[0-9]+-[0-9]+\Z")
STARTER_SOURCES = tuple(
    f"{prefix}tvproductions/{name}{suffix}"
    for prefix in ("https://github.com/", "git@github.com:")
    for name in ("gz-starter", "gz-skills-first-starter", "skills-first-starter")
    for suffix in (".git", "")
)


def marketplace_name(version: str) -> str:
    """Return the catalog name that the given starter release publishes."""
    numbers = tuple(int(n) for n in version.split("."))
    if numbers <= LAST_UNVERSIONED:
        return LEGACY_MARKETPLACE
    return "gz-starter-" + version.replace(".", "-")


def is_starter_marketplace(name: str) -> bool:
    """Recognize any name a starter release has published."""
    return name == LEGACY_MARKETPLACE or _VERSIONED.fullmatch(name) is not None


def _retired(name: str, current: str) -> bool:
    return name != current and is_starter_marketplace(name)


def _retirable_plugins(plugins: dict, current: str, parts: list[dict]) -> set[str]:
    """Select earlier starter activations that still hold the starter default."""
    defaults = {p["name"]: p["enabled_by_default"] for p in parts}
    found = set()
    for identity, value in plugins.items():
        name, _, source = identity.partition("@")
        # Codex writes a table holding only "enabled"; Claude writes the bare boolean.
        if isinstance(value, dict) and set(value) == {"enabled"}:
            value = value["enabled"]
        if name in defaults and _retired(source, current) and value is defaults[name]:
            found.add(identity)
    return found


def _header(line: str) -> tuple[str, str] | None:
    """Read a single-table header line with the TOML parser."""
    if not line.lstrip().startswith("["):
        return None
    try:
        data = tomllib.loads(line)
    except tomllib.TOMLDecodeError:
        return None
    group = next(iter(data), None)
    if group is None or not isinstance(data[group], dict) or len(data[group]) != 1:
        return None
    return group, next(iter(data[group]))


def retire_codex(text: str, current: str, parts: list[dict]) -> str:
    """Remove earlier starter tables that hold only starter-written values."""
    data = tomllib.loads(text)
    doomed = {
        ("marketplaces", name)
        for name, table in data.get("marketplaces", {}).items()
        if _retired(name, current) and table.get("source") in STARTER_SOURCES
    }
    doomed |= {
        ("plugins", identity)
        for identity in _retirable_plugins(data.get("plugins", {}), current, parts)
    }
    if not doomed:
        return text
    kept, skipping = [], False
    for line in text.splitlines(keepends=True):
        header = _header(line)
        if header is not None or line.lstrip().startswith("["):
            skipping = header in doomed
        if not skipping:
            kept.append(line)
    result = "".join(kept)
    expected = tomllib.loads(text)
    for group, name in doomed:
        del expected[group][name]
        if not expected[group]:
            del expected[group]
    if tomllib.loads(result) != expected:
        raise ValueError("earlier starter tables need manual reconciliation; no files changed")
    return result


def retire_claude(data: dict, current: str, parts: list[dict]) -> None:
    """Drop earlier starter entries from Claude settings in place."""
    known = data.get("extraKnownMarketplaces")
    if isinstance(known, dict):
        for name in [n for n in known if _retired(n, current)]:
            source = known[name].get("source", {}) if isinstance(known[name], dict) else {}
            if isinstance(source, dict) and source.get("url") in STARTER_SOURCES:
                del known[name]
    plugins = data.get("enabledPlugins")
    if isinstance(plugins, dict):
        for identity in _retirable_plugins(plugins, current, parts):
            del plugins[identity]
