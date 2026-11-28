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
LAST_GZ_STARTER = (0, 13)
_VERSIONED = re.compile(r"(gz-starter|gzlite)-[0-9]+-[0-9]+-[0-9]+\Z")
STARTER_SOURCES = tuple(
    f"{prefix}tvproductions/{name}{suffix}"
    for prefix in ("https://github.com/", "git@github.com:")
    for name in ("gzlite", "gz-starter", "gz-skills-first-starter", "skills-first-starter")
    for suffix in (".git", "")
)


def marketplace_name(version: str) -> str:
    """Return the catalog name that the given starter release publishes."""
    numbers = tuple(int(n) for n in version.split("."))
    if numbers <= LAST_UNVERSIONED:
        return LEGACY_MARKETPLACE
    slug = version.replace(".", "-")
    # Releases through 0.13.x published under the gz-starter name; 0.14.0 renamed it.
    if numbers[:2] <= LAST_GZ_STARTER:
        return "gz-starter-" + slug
    return "gzlite-" + slug


def is_starter_marketplace(name: str) -> bool:
    """Recognize any name a starter release has published."""
    return name == LEGACY_MARKETPLACE or _VERSIONED.fullmatch(name) is not None


def _retired(name: str, current: str) -> bool:
    return name != current and is_starter_marketplace(name)


def _codex_entry_is_starter(table: object) -> bool:
    """Match exactly the marketplace table an earlier starter release wrote."""
    return (
        isinstance(table, dict)
        and set(table) == {"source_type", "source", "ref"}
        and table["source_type"] == "git"
        and table["source"] in STARTER_SOURCES
        and isinstance(table["ref"], str)
    )


def _claude_entry_is_starter(entry: object) -> bool:
    """Match exactly the marketplace entry an earlier starter release wrote."""
    if not isinstance(entry, dict) or set(entry) != {"source", "autoUpdate"}:
        return False
    source = entry["source"]
    return (
        entry["autoUpdate"] is False
        and isinstance(source, dict)
        and set(source) == {"source", "url", "ref"}
        and source["source"] == "git"
        and source["url"] in STARTER_SOURCES
        and isinstance(source["ref"], str)
    )


def _owned_earlier(marketplaces: object, current: str, is_starter, strict: bool = True) -> set[str]:
    """Name earlier starter marketplaces declared here; refuse any that differ.

    With ``strict`` false every earlier starter name is owned whatever its
    content; ``migrate`` saves the original file before it retires them.
    """
    owned = set()
    if not isinstance(marketplaces, dict):
        return owned
    for name, entry in marketplaces.items():
        if not _retired(name, current):
            continue
        if strict and not is_starter(entry):
            raise ValueError(
                f"earlier starter marketplace {name} differs from what the starter wrote; "
                "reconcile it first; no files changed"
            )
        owned.add(name)
    return owned


def _retirable_plugins(
    plugins: object, owned: set[str], parts: list[dict], strict: bool = True
) -> set[str]:
    """Select activations of the retired marketplaces; refuse non-default choices.

    Activations naming an earlier starter marketplace that this file does not
    declare are left alone: they suppress a duplicate inherited from user
    settings, and the activation check judges them.
    """
    defaults = {p["name"]: p["enabled_by_default"] for p in parts}
    found = set()
    if not isinstance(plugins, dict):
        return found
    for identity, value in plugins.items():
        name, _, source = identity.partition("@")
        if name not in defaults or source not in owned:
            continue
        # Codex writes a table holding only "enabled"; Claude writes the bare boolean.
        if isinstance(value, dict) and set(value) == {"enabled"}:
            value = value["enabled"]
        if strict and value is not defaults[name]:
            raise ValueError(
                f"{identity} differs from the starter default; reconcile it first; no files changed"
            )
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


def retire_codex(text: str, current: str, parts: list[dict], *, strict: bool = True) -> str:
    """Remove earlier starter tables that hold only starter-written values.

    With ``strict`` false the earlier starter tables are removed even when
    their values differ from what the starter wrote.
    """
    data = tomllib.loads(text)
    owned = _owned_earlier(data.get("marketplaces", {}), current, _codex_entry_is_starter, strict)
    doomed = {("marketplaces", name) for name in owned}
    doomed |= {
        ("plugins", identity)
        for identity in _retirable_plugins(data.get("plugins", {}), owned, parts, strict)
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


def retire_claude(data: dict, current: str, parts: list[dict], *, strict: bool = True) -> None:
    """Drop earlier starter entries from Claude settings in place.

    ``strict`` has the same meaning as for ``retire_codex``.
    """
    known = data.get("extraKnownMarketplaces")
    owned = _owned_earlier(known, current, _claude_entry_is_starter, strict)
    plugins = data.get("enabledPlugins")
    for identity in _retirable_plugins(plugins, owned, parts, strict):
        if isinstance(plugins, dict):
            del plugins[identity]
    for name in owned:
        if isinstance(known, dict):
            del known[name]
