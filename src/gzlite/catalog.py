"""Read-only maintainer checks for a skills catalog (a repository with ``skills/``).

``check`` reports where a catalog disagrees with itself: skill names against
directories, the discovery-and-fallback floor against its ratchet ledger, the
plugin manifest versions, the marketplace pins, the router table, and the
explicit-only skill sets across hosts. It reads files only and never writes.

Optional catalog data lives in ``<root>/catalog-check.json``::

    {"schema_version": 1, "floor_pending": ["<skill name>", ...]}

``floor_pending`` may only shrink. A skill that lacks the floor section and is
not listed fails; a skill that declares the floor while still listed also fails,
which keeps the exemption a countdown rather than a standing waiver. An absent
file means an empty list and is not itself a finding.

Findings carry POSIX-relative artifact paths so output is identical everywhere.
No YAML or other third-party parser is used: the one key read from
``agents/openai.yaml`` and the OpenCode literal array are matched strictly, and
a shape this module does not recognise is reported rather than guessed at.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

DATA_FILE = "catalog-check.json"
FLOOR_SECTION = "## Discovery and fallback"
VERSION_FILES = ("package.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json")
MARKETPLACES = (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json")
ADAPTER_GLOB = "adapters/opencode/*.js"
# Excluded from tree hashes so tool caches never change a skill's identity.
TRANSIENT = frozenset({".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"})

_EXPLICIT_SET = re.compile(r"\bexplicitOnly\s*=\s*new\s+Set\(\s*\[([^\]]*)\]\s*\)")
_QUOTED = re.compile(r"""\s*(?:"([^"\\]*)"|'([^'\\]*)')\s*(?:,|$)""")
_POLICY_KEY = re.compile(r"^[ \t]+allow_implicit_invocation:[ \t]*(?P<value>\S+)[ \t]*$")


def _finding(check: str, artifact: str, message: str) -> dict[str, str]:
    return {"check": check, "artifact": artifact, "message": message}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _frontmatter_scalar(text: str, key: str) -> str:
    """Read a simple scalar from YAML frontmatter without parsing all YAML."""
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) != 3:
        return ""
    prefix = f"{key}:"
    for raw_line in parts[1].splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            return value
    return ""


def _tree_sha256(skill_root: Path) -> str:
    """Hash a skill directory: sorted POSIX paths and bytes, caches excluded."""
    digest = hashlib.sha256()
    files = []
    for path in skill_root.rglob("*"):
        relative = path.relative_to(skill_root)
        if path.is_file() and not any(part in TRANSIENT for part in relative.parts):
            files.append((relative.as_posix(), path))
    for relative, path in sorted(files, key=lambda item: item[0].encode("utf-8")):
        digest.update(relative.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def _declares_floor(text: str) -> bool:
    """Return True when the skill carries a non-empty floor section.

    Witnesses that the section exists and says something, never that what it
    says is a good fallback; that is a reading, not a state to model here.
    """
    _, marker, rest = text.partition(f"\n{FLOOR_SECTION}")
    return bool(marker) and bool(rest.split("\n## ", 1)[0].strip())


def _implicit_policy(path: Path) -> bool | None:
    """Read ``policy.allow_implicit_invocation``: True, False, or None if absent.

    Raises ``ValueError`` when the key sits outside a top-level ``policy:``
    block or holds anything but ``true``/``false``.
    """
    in_policy = False
    found: bool | None = None
    for raw in _read(path).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw[0].isspace():
            in_policy = raw.rstrip() == "policy:"
            continue
        match = _POLICY_KEY.match(raw)
        if match is None:
            continue
        if not in_policy:
            raise ValueError("allow_implicit_invocation appears outside a top-level policy block")
        if match["value"] not in ("true", "false"):
            raise ValueError(f"unrecognised value {match['value']!r}")
        found = match["value"] == "true"
    return found


def _skill_dirs(root: Path) -> list[Path]:
    skills = root / "skills"
    if not skills.is_dir():
        return []
    return sorted(p for p in skills.iterdir() if (p / "SKILL.md").is_file())


def inventory(root: Path) -> list[dict]:
    """List the authored skills below ``<root>/skills`` as plain records."""
    root = Path(root)
    records = []
    for directory in _skill_dirs(root):
        skill_file = directory / "SKILL.md"
        text = _read(skill_file)
        records.append(
            {
                "name": _frontmatter_scalar(text, "name"),
                "directory": directory.name,
                "path": skill_file.relative_to(root).as_posix(),
                "description": _frontmatter_scalar(text, "description"),
                "declares_floor": _declares_floor(text),
                "skill_sha256": hashlib.sha256(skill_file.read_bytes()).hexdigest(),
                "tree_sha256": _tree_sha256(directory),
            }
        )
    return records


def _load_json(root: Path, relative: str, findings: list, check: str) -> dict | None:
    """Load a JSON object, or report and return None. A missing file returns None silently."""
    path = root / relative
    if not path.is_file():
        return None
    try:
        data = json.loads(_read(path))
    except ValueError as error:
        findings.append(_finding(check, relative, f"Not valid JSON: {error}."))
        return None
    if not isinstance(data, dict):
        findings.append(_finding(check, relative, "Expected a JSON object."))
        return None
    return data


def _floor_pending(root: Path, findings: list) -> set[str]:
    data = _load_json(root, DATA_FILE, findings, "catalog-data")
    if data is None:
        return set()
    pending = data.get("floor_pending")
    if data.get("schema_version") != 1 or not (
        isinstance(pending, list) and all(isinstance(name, str) for name in pending)
    ):
        findings.append(
            _finding(
                "catalog-data",
                DATA_FILE,
                'Expected {"schema_version": 1, "floor_pending": [<skill names>]}.',
            )
        )
        return set()
    return set(pending)


def _check_names(records: list[dict], findings: list) -> None:
    for record in records:
        if record["name"] != record["directory"]:
            findings.append(
                _finding(
                    "skill-name",
                    record["path"],
                    f"Frontmatter name {record['name']!r} differs from directory "
                    f"{record['directory']!r}.",
                )
            )


def _check_floor(root: Path, records: list[dict], findings: list) -> None:
    pending = _floor_pending(root, findings)
    names = {record["directory"] for record in records}
    for name in sorted(pending - names):
        findings.append(
            _finding("floor", DATA_FILE, f"floor_pending names {name}, which is not a skill.")
        )
    for record in records:
        name = record["directory"]
        if record["declares_floor"] and name in pending:
            findings.append(
                _finding(
                    "floor",
                    record["path"],
                    f"{name} declares a floor: remove it from floor_pending.",
                )
            )
        elif not record["declares_floor"] and name not in pending:
            findings.append(
                _finding(
                    "floor",
                    record["path"],
                    f"{name} states no floor: add a non-empty '{FLOOR_SECTION}' section "
                    "naming what to run when no project surface is found.",
                )
            )


def _check_versions(root: Path, findings: list) -> None:
    versions: dict[str, object] = {}
    for relative in VERSION_FILES:
        data = _load_json(root, relative, findings, "versions")
        if data is not None:
            versions[relative] = data.get("version")
    if len({repr(version) for version in versions.values()}) > 1:
        detail = ", ".join(f"{path}={version!r}" for path, version in versions.items())
        findings.append(_finding("versions", ".", f"Plugin manifest versions differ: {detail}."))


def _marketplace_refs(root: Path, relative: str, findings: list) -> dict[str, object] | None:
    data = _load_json(root, relative, findings, "pins")
    if data is None:
        return None
    refs: dict[str, object] = {}
    for entry in data.get("plugins") or []:
        source = entry.get("source") if isinstance(entry, dict) else None
        if not isinstance(source, dict) or not isinstance(entry.get("name"), str):
            findings.append(_finding("pins", relative, "Unrecognised plugin entry shape."))
            continue
        refs[entry["name"]] = source.get("ref") or source.get("sha")
    return refs


def _check_pins(root: Path, findings: list) -> None:
    first = _marketplace_refs(root, MARKETPLACES[0], findings)
    second = _marketplace_refs(root, MARKETPLACES[1], findings)
    if first is None or second is None:
        return
    for name in sorted(set(first) | set(second)):
        if first.get(name) != second.get(name):
            findings.append(
                _finding(
                    "pins",
                    MARKETPLACES[0],
                    f"Marketplace pins for {name} differ: "
                    f"{MARKETPLACES[0]}={first.get(name)!r}, "
                    f"{MARKETPLACES[1]}={second.get(name)!r}.",
                )
            )


def _check_router(root: Path, records: list[dict], findings: list) -> None:
    """Require every other skill in a table row of each ``*-router`` skill."""
    for router in (r for r in records if r["directory"].endswith("-router")):
        rows = [
            line
            for line in _read(root / router["path"]).splitlines()
            if line.lstrip().startswith("|")
        ]
        for record in records:
            name = record["directory"]
            if name != router["directory"] and not any(f"`{name}`" in row for row in rows):
                findings.append(
                    _finding(
                        "router",
                        router["path"],
                        f"{name} is missing from the catalog table in {router['directory']}.",
                    )
                )


def _adapter_names(text: str) -> set[str] | None:
    """Return the literal explicitOnly array, or None when its shape is unrecognised."""
    match = _EXPLICIT_SET.search(text)
    if match is None:
        return None
    literal, position, names = match[1].strip(), 0, set()
    while position < len(literal):
        item = _QUOTED.match(literal, position)
        if item is None:
            return None
        names.add(item[1] if item[1] is not None else item[2])
        position = item.end()
    return names


def _check_explicit_only(root: Path, records: list[dict], findings: list) -> None:
    adapters = sorted(root.glob(ADAPTER_GLOB))
    if not adapters:
        return
    codex: set[str] = set()
    for record in records:
        relative = f"skills/{record['directory']}/agents/openai.yaml"
        if not (root / relative).is_file():
            continue
        try:
            if _implicit_policy(root / relative) is False:
                codex.add(record["directory"])
        except ValueError as error:
            findings.append(_finding("explicit-only", relative, f"Cannot read policy: {error}."))
            return
    for adapter in adapters:
        relative = adapter.relative_to(root).as_posix()
        names = _adapter_names(_read(adapter))
        if names is None:
            findings.append(
                _finding(
                    "explicit-only",
                    relative,
                    "Unrecognised adapter shape: expected "
                    "'explicitOnly = new Set([\"name\", ...])'.",
                )
            )
        elif names != codex:
            findings.append(
                _finding(
                    "explicit-only",
                    relative,
                    f"Explicit-only sets differ: openai.yaml={sorted(codex)}, "
                    f"{relative}={sorted(names)}.",
                )
            )


def check(root: Path) -> list[dict]:
    """Return the catalog's findings; an empty list means it is consistent.

    Raises ``ValueError`` when ``root`` has no ``skills/`` directory.
    """
    root = Path(root)
    if not (root / "skills").is_dir():
        raise ValueError(f"no skills/ directory under {root}")
    findings: list[dict] = []
    records = inventory(root)
    _check_names(records, findings)
    _check_floor(root, records, findings)
    _check_versions(root, findings)
    _check_pins(root, findings)
    _check_router(root, records, findings)
    _check_explicit_only(root, records, findings)
    return findings
