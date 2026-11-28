"""Validate supplied and effective filesystem paths before content access."""

import os
import stat
from pathlib import Path

STATE_DIRECTORY = ".gzlite"
BUNDLE_LOCK = f"{STATE_DIRECTORY}/bundle.lock.json"
LOCAL_ADR_POLICY = f"{STATE_DIRECTORY}/architectural-decisions.md"
STATE_SETTINGS = f"{STATE_DIRECTORY}/settings.toml"
MIGRATED_DIRECTORY = f"{STATE_DIRECTORY}/migrated"
# Files a change deletes wait here until it succeeds, so a rollback is a rename.
STAGING_DIRECTORY = f"{STATE_DIRECTORY}/staging"
LEGACY_DIRECTORIES = (".gz-starter", ".skills-first")
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


def refuse_staging(root: Path) -> None:
    """Refuse a non-empty staging folder: originals a migration could not put back."""
    if _state_entry(root, STAGING_DIRECTORY) is None:
        return
    staging = root / STAGING_DIRECTORY
    if staging.is_dir() and not any(staging.iterdir()):
        return
    raise ValueError(
        f"{STAGING_DIRECTORY}/ is not empty: a migration's rollback is incomplete. "
        f"Restore the files by hand from {STAGING_DIRECTORY}/ (the originals) and "
        f"{MIGRATED_DIRECTORY}/ (saved copies), then remove {STAGING_DIRECTORY}/; "
        "if the migration had succeeded and only its cleanup failed, delete "
        f"{STAGING_DIRECTORY}/ instead."
    )


def validate_state_directory(
    root: Path, *, allow_legacy: bool = False, allow_staging: bool = False
) -> None:
    """Reject unsafe or legacy state without reading state contents.

    Legacy folders are only reconciled by ``gzlite migrate``; every other
    command refuses them rather than guess which state is authoritative.
    ``migrate`` passes ``allow_legacy`` while it writes: legacy entries are
    still checked for links and readability, but their presence is accepted.
    Staged originals are refused too (``refuse_staging``); only the writer that
    staged them, still running, passes ``allow_staging``.
    """
    if not allow_staging:
        refuse_staging(root)
    legacy = []
    for directory in LEGACY_DIRECTORIES:
        root_mode = _state_entry(root, directory)
        if root_mode is None:
            continue
        if not stat.S_ISDIR(root_mode):
            raise ValueError(f"starter state must be a directory: {directory}")
        for name in _STATE_FILENAMES:
            relative = f"{directory}/{name}"
            if _state_entry(root, relative) is not None:
                legacy.append(relative)
    if legacy and not allow_legacy:
        raise ValueError(
            f"starter state migration required: {', '.join(legacy)}; "
            "run gzlite migrate before retrying."
        )
    root_mode = _state_entry(root, STATE_DIRECTORY)
    if root_mode is None:
        return
    if not stat.S_ISDIR(root_mode):
        raise ValueError(f"starter state must be a directory: {STATE_DIRECTORY}")
    for name in _STATE_FILENAMES:
        relative = f"{STATE_DIRECTORY}/{name}"
        mode = _state_entry(root, relative)
        if mode is not None and not stat.S_ISREG(mode):
            raise ValueError(f"starter state must be a regular file: {relative}")


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
