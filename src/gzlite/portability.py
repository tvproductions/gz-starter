"""Read-only static audit for cross-platform Python portability defects.

Two checks, both safe to run on any platform. Neither needs the defect to
reproduce locally, which matters because these failures are usually invisible
on whichever platform CI runs.

``line-endings``
    A text surface committed with CRLF, or a missing ``.gitattributes``
    normalization directive. It inspects the git index rather than the working
    tree: a Windows checkout renders LF blobs as CRLF on disk and git
    normalizes them away again on commit, so trusting the index lets
    ``.gitattributes`` do the work.

``subprocess-errors``
    A text-mode subprocess capture that decodes child output without
    ``errors=``. Undecodable bytes raise ``UnicodeDecodeError``, a
    ``ValueError``, so ``except OSError`` misses it and the command aborts.
    Bytes-mode calls are never flagged: adding ``errors=`` there would switch
    the call to text mode and change its return type.

Findings carry POSIX-relative artifact paths so output is identical on every
operating system. The audit never writes.
"""

from __future__ import annotations

import ast
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

from gzlite.gitenv import clean_git_env

CHECKS = ("line-endings", "subprocess-errors")

_LF_DIRECTIVE = re.compile(r"^\s*\*\s+text=auto\s+eol=lf\b", re.MULTILINE)

_TEXT_SUFFIXES = frozenset(
    {".cfg", ".feature", ".ini", ".json", ".jsonl", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
)

# Vendored code, build output and caches are never worth walking.
_PRUNED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "site-packages",
        "venv",
    }
)

_CAPTURE_FUNCS = frozenset({"run", "Popen", "check_output"})

_MISSING_MESSAGE = (
    "Missing .gitattributes. Add the LF normalization directive so git normalizes "
    "line endings in the index on every platform, regardless of a clone's local "
    "core.autocrlf setting."
)
_WEAK_MESSAGE = (
    ".gitattributes lacks the LF normalization directive, so line endings depend "
    "on each clone's local core.autocrlf setting."
)
_CRLF_MESSAGE = (
    "Committed with CRLF line endings. Normalize to LF. A text-mode write without "
    "an explicit newline argument emits the platform separator, which is CRLF on "
    "Windows."
)
_ERRORS_MESSAGE = (
    "Text-mode subprocess capture decodes child output but passes no errors=. "
    "Non-UTF-8 output raises UnicodeDecodeError, which is a ValueError, so a "
    "handler catching OSError does not catch it and the command aborts mid-run. "
    "Pass an explicit errors= argument."
)


def _finding(check: str, artifact: str, message: str) -> dict:
    return {"check": check, "artifact": artifact, "message": message}


def _gitattributes(root: Path) -> list[dict]:
    path = root / ".gitattributes"
    if not path.is_file():
        return [_finding("line-endings", ".gitattributes", _MISSING_MESSAGE)]
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        content = ""
    if not _LF_DIRECTIVE.search(content):
        return [_finding("line-endings", ".gitattributes", _WEAK_MESSAGE)]
    return []


def _committed_crlf(root: Path) -> list[dict]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--eol"],
            capture_output=True,
            check=True,
            env=clean_git_env(),
            timeout=30,
            text=True,
            errors="replace",
        )
    except OSError, subprocess.SubprocessError:
        # Not a git work tree; the .gitattributes arm still gates the contract.
        return []
    findings = []
    for entry in result.stdout.splitlines():
        meta, tab, relative = entry.partition("\t")
        fields = meta.split()
        if not tab or not fields or not fields[0].startswith("i/"):
            continue
        if fields[0][2:] not in ("crlf", "mixed"):
            continue
        if Path(relative).suffix.lower() not in _TEXT_SUFFIXES:
            continue
        findings.append(_finding("line-endings", relative, _CRLF_MESSAGE))
    return findings


def _python_files(root: Path, scan_roots: Sequence[Path]) -> list[Path]:
    found: set[Path] = set()
    for base in scan_roots:
        for path in base.rglob("*.py"):
            if not _PRUNED_DIRS.intersection(path.relative_to(root).parts):
                found.add(path)
    return sorted(found)


def _is_true(value: ast.expr | None) -> bool:
    return isinstance(value, ast.Constant) and bool(value.value)


def _capture_name(node: ast.Call) -> str | None:
    func = node.func
    if (
        isinstance(func, ast.Attribute)
        and func.attr in _CAPTURE_FUNCS
        and isinstance(func.value, ast.Name)
        and func.value.id == "subprocess"
    ):
        return func.attr
    return None


def _decodes_text(kwargs: dict[str, ast.expr]) -> bool:
    if _is_true(kwargs.get("text")) or _is_true(kwargs.get("universal_newlines")):
        return True
    encoding = kwargs.get("encoding")
    return encoding is not None and not (
        isinstance(encoding, ast.Constant) and encoding.value is None
    )


def _is_pipe(value: ast.expr | None) -> bool:
    return isinstance(value, ast.Attribute) and value.attr == "PIPE"


def _captures_output(name: str, kwargs: dict[str, ast.expr]) -> bool:
    if name == "check_output" or _is_true(kwargs.get("capture_output")):
        return True
    return _is_pipe(kwargs.get("stdout")) or _is_pipe(kwargs.get("stderr"))


def _subprocess_findings(tree: ast.Module, relative: str) -> list[dict]:
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _capture_name(node)
        if name is None:
            continue
        # A **kwargs expansion has no arg name and is not inspected.
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        if _decodes_text(kwargs) and _captures_output(name, kwargs) and "errors" not in kwargs:
            findings.append(
                _finding("subprocess-errors", f"{relative}:{node.lineno}", _ERRORS_MESSAGE)
            )
    return findings


def _subprocess_errors(root: Path, scan_roots: Sequence[Path]) -> list[dict]:
    findings = []
    for path in _python_files(root, scan_roots):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except OSError, SyntaxError:
            continue
        findings.extend(_subprocess_findings(tree, path.relative_to(root).as_posix()))
    return findings


def _scan_roots(root: Path, paths: Sequence[str]) -> list[Path]:
    if not paths:
        return [root]
    roots = []
    for relative in paths:
        scan_root = (root / relative).resolve()
        if not scan_root.is_dir():
            raise ValueError(f"--path is not a directory: {scan_root}")
        if not scan_root.is_relative_to(root):
            raise ValueError(f"--path escapes the root: {scan_root}")
        roots.append(scan_root)
    return roots


def audit(root: Path, checks: Sequence[str], paths: Sequence[str]) -> list[dict]:
    """Run the named checks under root and return findings.

    Each finding has the keys ``check``, ``artifact`` and ``message``.
    ``paths`` narrows only the source scan; the line-ending contract is
    whole-repository. Raises ValueError for an unknown check, a bad root or a
    bad path.
    """
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"--root is not a directory: {root}")
    unknown = [name for name in checks if name not in CHECKS]
    if unknown:
        raise ValueError(f"unknown check: {', '.join(unknown)}")
    scan_roots = _scan_roots(root, paths)
    findings: list[dict] = []
    for name in checks:
        if name == "line-endings":
            findings.extend(_gitattributes(root) + _committed_crlf(root))
        else:
            findings.extend(_subprocess_errors(root, scan_roots))
    return findings
