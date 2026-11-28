"""Vendor immutable gz-skills snapshots into a project and keep them current.

The gz-skills repository carries skills only. This module copies skill trees out
of a checkout of it, records each copy in a consumer lock (``gz-skills.lock.json``)
with a tree hash, and later replaces a tree only while its hash still matches the
lock, so local edits are never overwritten silently.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Sequence
from pathlib import Path

from gzlite.gitenv import clean_git_env

SOURCE_REPOSITORY = "https://github.com/tvproductions/gz-skills.git"
LOCK_FILENAME = "gz-skills.lock.json"
CACHE_ENV = "GZLITE_VENDOR_CACHE"
REPOSITORY_ENV = "GZLITE_VENDOR_REPOSITORY"
SURFACES = {
    "agents": Path(".agents/skills"),
    "claude": Path(".claude/skills"),
    "codex": Path(".codex/skills"),
    "github": Path(".github/skills"),
}
# Excluded from tree hashes so tool caches never change a snapshot's identity.
TRANSIENT_DIRECTORIES = frozenset(
    {".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
)
# Directories that never hold a consumer lock worth propagating to.
SCAN_IGNORES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "node_modules",
        "site-packages",
        "venv",
    }
)
_FULL_SHA = re.compile(r"[0-9a-f]{40}\Z")
_SAFE_REVISION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
BLOCKING_STATES = frozenset({"changed", "missing"})


class VendorError(ValueError):
    """A safe install or update could not be completed."""


def _git(cwd: Path, *args: str) -> str:
    """Run git aimed at ``cwd`` without inheriting hook-exported ``GIT_*`` variables.

    Both ``cwd`` and ``-C`` pin the directory, and hooks are disabled so a
    global ``core.hooksPath`` cannot run code during a clone or checkout.
    """
    try:
        done = subprocess.run(
            ["git", "-C", str(cwd), "-c", f"core.hooksPath={os.devnull}", *args],
            cwd=cwd,
            env=clean_git_env(),
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as error:
        raise VendorError(f"git {args[0]} failed: {error.stderr.strip()}") from error
    return done.stdout.strip()


def _frontmatter_scalar(text: str, key: str) -> str:
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) != 3:
        return ""
    prefix = f"{key}:"
    in_metadata = False
    for raw_line in parts[1].splitlines():
        if raw_line and not raw_line[0].isspace():
            in_metadata = raw_line.strip() == "metadata:"
        stripped = raw_line.strip()
        if key == "govzero-version" and not in_metadata:
            continue
        if stripped.startswith(prefix):
            value = stripped[len(prefix) :].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            return value
    return ""


def tree_sha256(skill_root: Path) -> str:
    """Hash every durable file in a skill using the provenance contract."""
    digest = hashlib.sha256()
    files: list[tuple[str, Path]] = []
    for path in skill_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(skill_root)
        if any(part in TRANSIENT_DIRECTORIES for part in relative.parts):
            continue
        files.append((relative.as_posix(), path))
    for relative, path in sorted(files, key=lambda item: item[0].encode("utf-8")):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _catalog(source: Path) -> dict[str, dict]:
    root = source.resolve() / "skills"
    if not root.is_dir():
        raise VendorError(f"no skills directory in {source}")
    catalog: dict[str, dict] = {}
    for skill_dir in sorted(root.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_dir.is_dir() or not skill_file.is_file():
            continue
        text = skill_file.read_text(encoding="utf-8")
        name = _frontmatter_scalar(text, "name")
        version = _frontmatter_scalar(text, "govzero-version")
        if name != skill_dir.name:
            raise VendorError(
                f"catalog name mismatch: directory {skill_dir.name!r}, frontmatter {name!r}"
            )
        if not version:
            raise VendorError(f"catalog skill {name!r} has no metadata.govzero-version")
        catalog[name] = {
            "name": name,
            "version": version,
            "description": _frontmatter_scalar(text, "description"),
            "sha256": tree_sha256(skill_dir),
            "path": str(skill_dir),
        }
    return catalog


def list_skills(source: Path) -> list[dict]:
    """List the skills a gz-skills checkout offers."""
    return list(_catalog(source).values())


def cache_root() -> Path:
    """Where fetched gz-skills revisions are kept; ``GZLITE_VENDOR_CACHE`` overrides."""
    override = os.environ.get(CACHE_ENV)
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "gzlite" / "vendor"
    return Path.home() / ".cache" / "gzlite" / "vendor"


def resolve_source(
    revision: str | None,
    *,
    source: Path | None,
    repository: str | None = None,
    cache_root: Path | None = None,
) -> Path:
    """Return a checkout of gz-skills: ``source`` if given, else a cached clone.

    A full commit hash is immutable, so a complete cache entry is reused. Any
    other revision names something that can move (a branch or tag), so it is
    fetched again each time.
    """
    if source is not None:
        return source
    if not revision:
        raise VendorError("no source given and no revision to fetch")
    if not _SAFE_REVISION.fullmatch(revision) or ".." in revision:
        raise VendorError(f"unsafe revision {revision!r}")
    repository = repository or os.environ.get(REPOSITORY_ENV) or SOURCE_REPOSITORY
    root = cache_root_default() if cache_root is None else cache_root
    entry = root / revision
    # The marker sits beside the clone so it never dirties the checkout.
    marker = root / f".{revision}.complete"
    if marker.is_file() and entry.is_dir() and _FULL_SHA.fullmatch(revision):
        return entry
    root.mkdir(parents=True, exist_ok=True)
    staging = root / f".{revision}.staging-{uuid.uuid4().hex}"
    try:
        _git(root, "clone", "--quiet", "--no-checkout", "--", repository, str(staging))
        _git(staging, "checkout", "--quiet", "--detach", revision, "--")
        marker.unlink(missing_ok=True)
        if entry.exists():
            shutil.rmtree(entry, onexc=_make_writable)
        staging.rename(entry)
        marker.write_text(revision + "\n", encoding="utf-8")
    finally:
        if staging.exists():
            shutil.rmtree(staging, onexc=_make_writable)
    return entry


def cache_root_default() -> Path:
    return cache_root()


def _make_writable(function, path, _error) -> None:
    """Git marks object files read-only, which blocks removal on Windows."""
    os.chmod(path, 0o700)
    function(path)


def _source_revision(source: Path) -> str:
    """Return the commit of a source checkout, marked when it has local edits."""
    root = source.resolve()
    try:
        top = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
        if top != root:
            return "unversioned"
        head = _git(root, "rev-parse", "HEAD")
        dirty = _git(root, "status", "--porcelain", "--untracked-files=normal")
    except OSError, VendorError:
        return "unversioned"
    return f"working-tree:{head}" if dirty else head


def resolve_destination(
    *, project: Path | None, user: bool, target: Path | None, surface: str, lock: Path | None
) -> tuple[Path, Path]:
    """Resolve the skills directory and its consumer-owned lock file."""
    selected = sum(value is not None and value is not False for value in (project, user, target))
    if selected != 1:
        raise VendorError("choose exactly one of --project, --user, or --target")
    if surface not in SURFACES:
        raise VendorError(f"unknown surface {surface!r}")
    if project is not None:
        base = project.resolve()
        return base / SURFACES[surface], lock.resolve() if lock else base / LOCK_FILENAME
    if user:
        base = Path.home()
        return (
            base / SURFACES[surface],
            lock.resolve() if lock else base / ".agents" / LOCK_FILENAME,
        )
    assert target is not None
    destination = target.resolve()
    return destination, lock.resolve() if lock else destination.parent / LOCK_FILENAME


def _read_lock(lock_path: Path) -> dict:
    if not lock_path.exists():
        return {"schema_version": 1, "skills": []}
    try:
        document = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VendorError(f"cannot read lock {lock_path}: {error}") from error
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or not isinstance(document.get("skills"), list)
    ):
        raise VendorError(f"unsupported or malformed lock {lock_path}")
    return document


def _write_lock(lock_path: Path, document: dict) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(document, indent=2) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{lock_path.name}.", suffix=".tmp", dir=lock_path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized)
        os.replace(temporary, lock_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _stored_path(path: Path, lock_path: Path) -> str:
    try:
        return path.resolve().relative_to(lock_path.parent.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _resolved_installed_path(value: str, lock_path: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (lock_path.parent / path).resolve()


def _entry_for(document: dict, name: str, installed_path: Path, lock_path: Path) -> dict | None:
    for entry in document["skills"]:
        value = entry.get("installed_path")
        if (
            entry.get("name") == name
            and isinstance(value, str)
            and _resolved_installed_path(value, lock_path) == installed_path
        ):
            return entry
    return None


def _replace_directory(source: Path, destination: Path) -> None:
    """Swap a tree in through a staged copy, restoring the old tree on failure."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.staging-{uuid.uuid4().hex}"
    backup = destination.parent / f".{destination.name}.backup-{uuid.uuid4().hex}"
    shutil.copytree(source, staging)
    try:
        if tree_sha256(staging) != tree_sha256(source):
            raise VendorError(f"staged copy hash mismatch for {destination.name}")
        if destination.exists():
            destination.rename(backup)
        staging.rename(destination)
    except Exception:
        if destination.exists() and backup.exists():
            shutil.rmtree(destination)
        if backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    if backup.exists():
        shutil.rmtree(backup)


def install(
    source: Path,
    names: Sequence[str],
    target: Path,
    *,
    lock: Path | None = None,
    force: bool = False,
) -> dict:
    """Copy the named skills from ``source`` into ``target`` and record them in the lock."""
    lock_path = (lock or target.parent / LOCK_FILENAME).resolve()
    catalog = _catalog(source)
    selected = list(dict.fromkeys(names))
    unknown = sorted(set(selected) - set(catalog))
    if unknown:
        raise VendorError(f"unknown skill(s): {', '.join(unknown)}")
    document = _read_lock(lock_path)
    revision = _source_revision(source)
    destination = target.resolve()

    # Check the whole request before changing anything, so a blocked skill
    # cannot leave an earlier one partially installed.
    for name in selected:
        installed_path = (destination / name).resolve()
        if installed_path.parent != destination:
            raise VendorError(f"unsafe destination for {name}: {installed_path}")
        entry = _entry_for(document, name, installed_path, lock_path)
        if installed_path.exists() and not force:
            if entry is None:
                raise VendorError(
                    f"{installed_path} exists without a matching lock; use --force to replace it"
                )
            observed = tree_sha256(installed_path)
            if observed != entry.get("sha256"):
                raise VendorError(
                    f"{name} is locally modified ({observed} != {entry.get('sha256')}); "
                    "reconcile or use --force"
                )

    installed: list[dict] = []
    for name in selected:
        skill = catalog[name]
        installed_path = (destination / name).resolve()
        entry = _entry_for(document, name, installed_path, lock_path)
        _replace_directory(Path(skill["path"]), installed_path)
        new_entry = {
            "name": name,
            "version": skill["version"],
            "source": {
                "repository": SOURCE_REPOSITORY,
                "revision": revision,
                "path": f"skills/{name}",
            },
            "sha256": skill["sha256"],
            "installed_path": _stored_path(installed_path, lock_path),
        }
        if entry is None:
            document["skills"].append(new_entry)
        else:
            document["skills"][document["skills"].index(entry)] = new_entry
        document["skills"].sort(key=lambda item: (item["name"], item["installed_path"]))
        # Written per skill so a later filesystem failure leaves a consistent lock.
        _write_lock(lock_path, document)
        installed.append({"name": name, "version": skill["version"], "path": str(installed_path)})
    return {"installed": installed, "lock": str(lock_path)}


def _states(lock_path: Path, catalog: dict[str, dict] | None) -> list[dict]:
    rows: list[dict] = []
    for entry in _read_lock(lock_path)["skills"]:
        name = str(entry.get("name", ""))
        installed_path = _resolved_installed_path(str(entry.get("installed_path", "")), lock_path)
        available = catalog.get(name) if catalog is not None else None
        if not installed_path.exists():
            state = "missing"
        elif tree_sha256(installed_path) != entry.get("sha256"):
            state = "changed"
        elif catalog is None:
            state = "current"
        elif available is None:
            state = "unavailable"
        elif available["sha256"] != entry.get("sha256") or available["version"] != entry.get(
            "version"
        ):
            state = "update-available"
        else:
            state = "current"
        row = {
            "name": name,
            "state": state,
            "installed_version": str(entry.get("version", "")),
            "installed_path": str(installed_path),
        }
        if catalog is not None:
            row["available_version"] = available["version"] if available else None
        rows.append(row)
    return rows


def status(lock: Path) -> dict:
    """Compare each locked installation with the hash recorded for it."""
    lock_path = lock.resolve()
    rows = _states(lock_path, None)
    return {
        "lock": str(lock_path),
        "skills": rows,
        "current": all(row["state"] == "current" for row in rows),
    }


def update(
    lock: Path,
    *,
    apply: bool,
    source: Path | None = None,
    revision: str | None = None,
    repository: str | None = None,
) -> dict:
    """Preview, or with ``apply`` perform, every safe update a lock represents.

    A tree is replaced only while it still matches the lock; a changed or
    missing installation blocks the whole apply before anything is written.
    """
    lock_path = lock.resolve()
    checkout = resolve_source(revision, source=source, repository=repository)
    observed = _states(lock_path, _catalog(checkout))
    if apply:
        blocked = [row for row in observed if row["state"] in BLOCKING_STATES]
        if blocked:
            details = ", ".join(f"{row['name']}:{row['state']}" for row in blocked)
            raise VendorError(f"lock contains blocked installations: {details}")
        for row in observed:
            if row["state"] == "update-available":
                install(checkout, [row["name"]], Path(row["installed_path"]).parent, lock=lock_path)
        observed = _states(lock_path, _catalog(checkout))
    return {
        "lock": str(lock_path),
        "applied": apply,
        "skills": observed,
        "blocked": any(row["state"] not in {"current", "update-available"} for row in observed),
    }


def find_locks(root: Path) -> list[Path]:
    """Find consumer lock files below a repository collection."""
    found: list[Path] = []
    for directory, directory_names, file_names in os.walk(root.resolve()):
        directory_names[:] = [name for name in directory_names if name not in SCAN_IGNORES]
        if LOCK_FILENAME in file_names:
            found.append(Path(directory) / LOCK_FILENAME)
    return sorted(found)


def propagate(
    root: Path,
    *,
    apply: bool,
    source: Path | None = None,
    revision: str | None = None,
    repository: str | None = None,
) -> dict:
    """Preview or apply updates for every consumer lock below ``root``."""
    lock_paths = find_locks(root)
    checkout = (
        resolve_source(revision, source=source, repository=repository) if lock_paths else None
    )
    results: list[dict] = []
    for lock_path in lock_paths:
        try:
            results.append(update(lock_path, apply=apply, source=checkout))
        except VendorError as error:
            results.append({"lock": str(lock_path), "error": str(error), "blocked": True})
    return {
        "root": str(root.resolve()),
        "locks": results,
        "blocked": any(result["blocked"] for result in results),
    }
