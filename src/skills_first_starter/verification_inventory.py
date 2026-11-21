"""Classify actual adopter files independently of Git ignore and tracking."""

from __future__ import annotations

import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from skills_first_starter.paths import space_free

_CODE_SUFFIXES = {".py", ".pyw", ".pyi", ".sh", ".bash", ".ps1", ".cmd", ".bat"}
_SENSITIVE_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".kdbx"}
_OPAQUE_REFERENCES = {".pdf", ".whl", ".zip", ".gz"}
_SKILL_ALIASES = {f"{host}/skills/update-gz-template" for host in (".agents", ".claude")}
_SKILL_REFERENCE = "../../templates/skills/update-gz-template"
_SKILL_TARGET = Path("templates/skills/update-gz-template")
_CACHE_BINARY = re.compile(r"[0-9]+")
_CACHE_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


@dataclass(frozen=True)
class ProjectInventory:
    """Paths are checkout-relative, with executable triggers identified."""

    paths: tuple[Path, ...]
    triggers: tuple[Path, ...]


def _kind(path: Path) -> int:
    info = path.lstat()
    if getattr(
        info, "st_file_attributes", 0
    ) & stat.FILE_ATTRIBUTE_REPARSE_POINT and not stat.S_ISLNK(info.st_mode):
        raise ValueError(f"unsupported reparse point: {path}")
    if os.name != "nt" and info.st_mode & 0o444 == 0:
        raise ValueError(f"unreadable input: {path}")
    return info.st_mode


def _skill_alias(root: Path, relative: Path, mode: int) -> bool:
    if relative.as_posix() not in _SKILL_ALIASES or stat.S_ISDIR(mode):
        return False
    alias = root / relative
    if stat.S_ISLNK(mode):
        target = alias.readlink().as_posix()
    elif stat.S_ISREG(mode):
        with alias.open("rb") as source:
            target = source.read(len(_SKILL_REFERENCE) + 1).decode("utf-8", errors="replace")
    else:
        raise ValueError(f"unsupported skill alias: {relative}")
    if target != _SKILL_REFERENCE or not (root / _SKILL_TARGET).is_dir():
        raise ValueError(f"unsupported skill alias target: {relative}")
    return True


def _managed_environment(path: Path) -> bool:
    config = path / "pyvenv.cfg"
    if not config.exists() and not config.is_symlink():
        return False
    if not stat.S_ISREG(_kind(config)):
        raise ValueError(f"unsupported environment configuration: {config}")
    lines = config.read_text(encoding="utf-8").splitlines()
    executable = path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return any(line.startswith("uv = ") for line in lines) and executable.is_file()


def _generated_file(path: Path) -> bool:
    """Recognize conventional cache data without hiding authored files."""
    if path.parent.name == "__pycache__" and path.suffix == ".pyc":
        return True
    if path.parts[0] == ".ruff_cache":
        return (len(path.parts) == 2 and path.name in {".gitignore", "CACHEDIR.TAG"}) or (
            len(path.parts) == 3
            and _CACHE_VERSION.fullmatch(path.parts[1]) is not None
            and _CACHE_BINARY.fullmatch(path.name) is not None
        )
    return False


def _walk(root: Path, directory: Path = Path(".")):
    for item in sorted((root / directory).iterdir()):
        relative = directory / item.name
        mode = _kind(item)
        alias = _skill_alias(root, relative, mode)
        if not alias and not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError(f"unsupported linked or non-regular input: {relative}")
        if relative == Path(".git"):
            continue
        if not stat.S_ISREG(mode) or relative.suffix.casefold() not in _OPAQUE_REFERENCES:
            _verification_path(root, relative)
        if alias:
            yield relative, 0
        elif stat.S_ISDIR(mode):
            if relative == Path(".venv"):
                if not _managed_environment(item):
                    raise ValueError(f"unrecognized managed environment: {relative}")
            else:
                yield from _walk(root, relative)
        elif not _generated_file(relative):
            yield relative, mode


def _git_executables(root: Path) -> set[Path]:
    if not (root / ".git").exists():
        return set()
    result = subprocess.run(
        ["git", "ls-files", "--stage", "-z"], cwd=root, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise ValueError("could not inspect Git executable modes")
    paths = set()
    for entry in result.stdout.split(b"\0"):
        flags, separator, path = entry.partition(b"\t")
        if separator and flags.startswith(b"100755 "):
            paths.add(Path(os.fsdecode(path)))
    return paths


def _secret_path(path: Path) -> bool:
    return (
        path.suffix.lower() in _SENSITIVE_SUFFIXES
        or path.name.lower().startswith((".env", "secret", "credential"))
        or any(part.lower() in {".ssh", "secrets", "credentials"} for part in path.parts)
    )


def _shebang(root: Path, path: Path) -> bool:
    # Extensionless launchers are portable even when executable mode isn't.
    with (root / path).open("rb") as source:
        return source.read(2) == b"#!"


def _verification_path(root: Path, path: Path) -> None:
    try:
        space_free(root / path)
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error


def _authored(root: Path, path: Path, mode: int, git_executables: set[Path]) -> bool:
    if mode == 0:
        return False
    if path in git_executables or (mode & 0o111 and os.name != "nt"):
        _verification_path(root, path)
        return True
    if path.suffix.lower() in _CODE_SUFFIXES:
        return True
    return not path.suffix and not _secret_path(path) and _shebang(root, path)


def inventory_project(root: Path) -> ProjectInventory:
    """Read entry metadata for the checkout and classify authored executables."""
    items = tuple(_walk(root))
    executables = _git_executables(root)
    return ProjectInventory(
        tuple(relative for relative, _mode in items),
        tuple(relative for relative, mode in items if _authored(root, relative, mode, executables)),
    )
