"""Check the reviewable project metadata and local documentation references."""

from __future__ import annotations

import json
import re
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from skills_first_starter.native_json import document as read_native_json
from skills_first_starter.paths import BUNDLE_LOCK, STATE_SETTINGS

_JSON_CONFIGS = {
    "bundle.json",
    BUNDLE_LOCK,
    ".gz-skills/settings.json",
    ".agents/plugins/marketplace.json",
    ".claude-plugin/marketplace.json",
    ".claude/settings.json",
    "opencode.json",
    "opencode.jsonc",
}
_TOML_CONFIGS = {".codex/config.toml", STATE_SETTINGS}
_STANDALONE_TOOL_CONFIGS = {"ruff.toml", ".ruff.toml", "ty.toml", "uv.toml"}
_LINK_OPEN = re.compile(r"\]\(\s*")
_MARKDOWN_REFERENCE = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(?:<([^>\n]+)>|(\S+))", re.M)
_ATX_HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_SETEXT_HEADING = re.compile(r"^ {0,3}(?:=+|-+)\s*$")
_HTML_ID = re.compile(r"""\b(?:id|name)=["']([^"']+)["']""", re.I)
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def read_toml(root: Path, relative: Path) -> dict[str, Any]:
    """Parse TOML without logging user configuration text."""
    try:
        return tomllib.loads((root / relative).read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeError) as error:
        raise ValueError(f"{relative}: invalid TOML") from error


def _profile(data: Any) -> None:
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "profile"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["profile"] not in (None, "lite", "heavy")
    ):
        raise ValueError("unsupported GovZero profile")


def _read_json_config(root: Path, path: Path) -> None:
    try:
        text = (root / path).read_text(encoding="utf-8")
        data = (
            read_native_json(text)[0]
            if path.name in {"opencode.json", "opencode.jsonc"}
            else json.loads(text)
        )
        if not isinstance(data, dict):
            raise ValueError("expected a configuration object")
        if path.as_posix() == ".gz-skills/settings.json":
            _profile(data)
    except (ValueError, UnicodeError) as error:
        raise ValueError(f"{path}: invalid or unsupported JSON configuration") from error


def validate_config_files(root: Path, paths: set[Path]) -> None:
    """Inspect recognized native configuration files only."""
    for path in sorted(paths):
        if path.as_posix() in _JSON_CONFIGS:
            _read_json_config(root, path)
        elif path.as_posix() in _TOML_CONFIGS:
            read_toml(root, path)


def project_table(data: dict[str, Any], key: str) -> dict[str, Any]:
    table = data.get(key, {})
    if not isinstance(table, dict):
        raise ValueError(f"pyproject.toml: {key} must be a table")
    return table


def validate_tool_configuration(root: Path, tools: dict[str, Any], paths: set[Path]) -> None:
    """Check the selected tools are owned by the root pyproject."""
    names = {"ruff", "ty", "uv"}
    for name in sorted(names):
        project_table(tools, name)
    for path in sorted(paths):
        if path.name.casefold() in _STANDALONE_TOOL_CONFIGS:
            raise ValueError(f"{path}: use the owning root pyproject.toml for tool settings")
        if path.name == "pyproject.toml" and path.parent != Path("."):
            nested = project_table(read_toml(root, path), "tool")
            if names.intersection(nested):
                raise ValueError(f"{path}: use the owning root pyproject.toml for tool settings")


def declared_readme(project: dict[str, Any], paths: set[Path]) -> None:
    value = project.get("readme")
    if value is None:
        return
    if isinstance(value, dict):
        if "text" in value and "file" not in value and isinstance(value["text"], str):
            return
        value = value.get("file")
    if not isinstance(value, str):
        raise ValueError("pyproject.toml: unsupported readme declaration")
    if Path(value) not in paths:
        raise ValueError(f"pyproject.toml: declared README file is missing: {value}")


def entry_points(project: dict[str, Any], paths: set[Path]) -> set[Path]:
    """Resolve declared local module callables for supported single-project roots."""
    groups = project_table(project, "entry-points")
    tables = [
        project_table(project, "scripts"),
        project_table(project, "gui-scripts"),
        *(project_table(groups, name) for name in groups),
    ]
    declared = set()
    for table in tables:
        for name, reference in table.items():
            if not isinstance(reference, str):
                raise ValueError(f"pyproject.toml: invalid entry point {name}")
            module = reference.split(":", 1)[0]
            if re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", module) is None:
                raise ValueError(f"pyproject.toml: unsupported entry-point module for {name}")
            target = Path(*module.split("."))
            matches = {
                prefix / entry
                for prefix in (Path("."), Path("src"))
                for entry in (target.with_suffix(".py"), target / "__init__.py")
                if prefix / entry in paths
            }
            if len(matches) != 1:
                raise ValueError(f"pyproject.toml: missing or ambiguous local entry point {name}")
            declared.update(matches)
    return declared


def _markdown_lines(text: str):
    fence = ""
    for line in text.splitlines():
        marker = _FENCE.match(line)
        if marker:
            token = marker[1]
            if not fence:
                fence = token
            elif token.startswith(fence):
                fence = ""
            continue
        if not fence:
            yield line


def _markdown_anchors(lines: tuple[str, ...]) -> set[str]:
    seen: Counter[str] = Counter()
    anchors = set()
    previous = ""
    for line in lines:
        heading = _ATX_HEADING.match(line)
        text = heading[1] if heading else previous if _SETEXT_HEADING.fullmatch(line) else ""
        if text:
            label = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
            slug = re.sub(r"[^\w -]", "", label.casefold().strip()).replace(" ", "-")
            index = seen[slug]
            anchors.add(f"{slug}-{index}" if index else slug)
            seen[slug] += 1
        anchors.update(_HTML_ID.findall(line))
        previous = line.strip()
    return anchors


def _local_reference(root: Path, source: Path, address: str) -> tuple[Path, str] | None:
    parsed = urlsplit(address)
    if (parsed.scheme and parsed.scheme != "file") or parsed.netloc:
        return None
    if parsed.scheme == "file":
        raise ValueError(f"{source}: unsupported local file URI")
    literal = unquote(parsed.path)
    if not literal:
        return source, unquote(parsed.fragment)
    if " " in literal or "\\" in literal:
        raise ValueError(f"{source}: invalid local link {address}")
    base = root if literal.startswith("/") else (root / source).parent
    target = (base / literal.lstrip("/")).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"{source}: local link escapes checkout: {address}")
    return target.relative_to(root), unquote(parsed.fragment)


def _inline_address(text: str) -> str:
    if text.startswith("<"):
        boundary = text.find(">")
        return text[1:boundary] if boundary != -1 else ""
    depth = 0
    address = []
    for char in text:
        if (char == ")" and depth == 0) or char.isspace():
            return "".join(address) if depth == 0 else ""
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        address.append(char)
    return ""


def _link_addresses(body: str):
    for link in _LINK_OPEN.finditer(body):
        if address := _inline_address(body[link.end() :]):
            yield address
    for link in _MARKDOWN_REFERENCE.finditer(body):
        yield link[1] or link[2]


def validate_markdown(root: Path, paths: set[Path]) -> None:
    """Check local links and Markdown heading fragments within the inventory."""
    documents = {
        path: tuple(_markdown_lines((root / path).read_text(encoding="utf-8")))
        for path in sorted(paths)
        if path.suffix.casefold() == ".md"
    }
    anchors = {path: _markdown_anchors(lines) for path, lines in documents.items()}
    directories = {parent for path in paths for parent in path.parents}
    for source, lines in documents.items():
        body = "\n".join(re.sub(r"`+[^`]+`+", "", line) for line in lines)
        for address in _link_addresses(body):
            resolved = _local_reference(root, source, address)
            if resolved is None:
                continue
            target, fragment = resolved
            if target not in paths and target not in directories:
                raise ValueError(f"{source}: broken local link {address}")
            if fragment and target in anchors and fragment not in anchors[target]:
                raise ValueError(f"{source}: missing Markdown anchor in {address}")
