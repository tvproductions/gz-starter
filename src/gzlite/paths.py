"""Validate supplied and effective filesystem paths before content access."""

import os
import stat
from pathlib import Path

STATE_DIRECTORY = ".gz-starter"
BUNDLE_LOCK = f"{STATE_DIRECTORY}/bundle.lock.json"
LOCAL_ADR_POLICY = f"{STATE_DIRECTORY}/architectural-decisions.md"
STATE_SETTINGS = f"{STATE_DIRECTORY}/settings.toml"
_LEGACY_DIRECTORY = ".skills-first"
_STATE_FILENAMES = tuple(
    Path(name).name for name in (BUNDLE_LOCK, LOCAL_ADR_POLICY, STATE_SETTINGS)
)


def _state_entry(root: Path, relative: str) -> int | None:
    try:
        info = (root / relative).lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ValueError(f"cannot inspect starter state {relative}: {error}") from error
    mode = info.st_mode
    if stat.S_ISLNK(mode) or (
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise ValueError(f"starter state symlink or unsupported reparse point: {relative}")
    directory = stat.S_ISDIR(mode)
    access = os.R_OK | (os.X_OK if directory and os.name != "nt" else 0)
    if not os.access(root / relative, access) or (os.name != "nt" and not mode & 0o444):
        raise ValueError(f"unreadable starter state: {relative}")
    return mode


def validate_state_directory(root: Path) -> None:
    """Reject unsafe or unreconciled state without reading state contents."""
    legacy = []
    current = []
    for directory, entries in ((_LEGACY_DIRECTORY, legacy), (STATE_DIRECTORY, current)):
        root_mode = _state_entry(root, directory)
        if root_mode is None:
            continue
        if not stat.S_ISDIR(root_mode):
            raise ValueError(f"starter state must be a directory: {directory}")
        for name in _STATE_FILENAMES:
            relative = f"{directory}/{name}"
            mode = _state_entry(root, relative)
            if mode is None:
                continue
            if directory == STATE_DIRECTORY and not stat.S_ISREG(mode):
                raise ValueError(f"starter state must be a regular file: {relative}")
            entries.append(relative)
    if legacy:
        existing = f"; current state also present: {', '.join(current)}" if current else ""
        raise ValueError(
            f"starter state migration required: {', '.join(legacy)}{existing}. "
            "Follow docs/updating.md to reconcile before retrying."
        )


def space_free(path: Path) -> Path:
    """Keep the caller's spelling while rejecting spaced aliases and targets."""
    pending = [path.absolute()]
    inspected = set()
    while pending:
        candidate = pending.pop()
        if candidate in inspected:
            continue
        inspected.add(candidate)
        if " " in str(candidate):
            raise ValueError(
                "paths containing spaces are unsupported; select an explicit space-free path"
            )
        for item in (candidate, *candidate.parents):
            if item.is_symlink():
                target = item.readlink()
                pending.append(target if target.is_absolute() else item.parent / target)
    if " " in str(path.resolve()):
        raise ValueError("resolved path contains spaces; select an explicit space-free path")
    return path
