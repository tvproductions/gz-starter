"""Manage one project's minimal work-progression settings.

The settings file records the SP-BP work-progression mode (``lite`` or
``heavy``) selected for a project. These modes are unrelated to the gzlite
tier name. The file is shared with adopters of earlier helpers, so its schema
and bytes must stay stable.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from gzlite.paths import space_free

SETTINGS_DIRECTORY = ".gz-skills"
SETTINGS_FILENAME = "settings.json"
SCHEMA_VERSION = 1
PROFILES = ("lite", "heavy")


class SettingsError(ValueError):
    """The settings are unsupported or the project cannot safely be changed."""


def validate_settings(data: object) -> None:
    """Accept exactly ``{"schema_version": 1, "profile": null|"lite"|"heavy"}``.

    This is the single validator; every reader of the settings file uses it.
    ``bool`` is an ``int`` subclass, so the version check compares types.
    """
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "profile"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != SCHEMA_VERSION
        or data["profile"] not in (None, *PROFILES)
    ):
        raise SettingsError("unsupported settings; reconcile manually")


def _paths(project: Path) -> tuple[Path, Path, Path]:
    root = space_free(project).resolve(strict=True)
    if not root.is_dir():
        raise SettingsError(f"project is not a directory: {root}")
    directory = root / SETTINGS_DIRECTORY
    return root, directory, directory / SETTINGS_FILENAME


def _check_project(root: Path, directory: Path, settings_path: Path) -> None:
    if (root / ".gzkit").exists():
        raise SettingsError(
            f"{root} uses .gzkit; gzkit and gzlite are incompatible here. "
            "Back out and use the gzkit workflow."
        )
    if directory.is_symlink() or settings_path.is_symlink():
        raise SettingsError("refusing a symlinked .gz-skills directory or settings file")
    if directory.exists() and not directory.is_dir():
        raise SettingsError(f"not a directory: {directory}")


def _read(settings_path: Path) -> dict[str, object] | None:
    if not settings_path.exists():
        return None
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SettingsError(f"cannot read valid JSON from {settings_path}: {error}") from error
    try:
        validate_settings(data)
    except SettingsError as error:
        raise SettingsError(
            f"unsupported settings in {settings_path}; reconcile manually"
        ) from error
    return data


def _payload(data: dict[str, object]) -> str:
    return json.dumps(data, indent=2) + "\n"


def _write_new(settings_path: Path, data: dict[str, object]) -> None:
    try:
        with settings_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(_payload(data))
    except FileExistsError as error:
        raise SettingsError(f"settings appeared during setup: {settings_path}") from error


def _replace(settings_path: Path, data: dict[str, object]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=settings_path.parent,
            prefix=".settings-",
            suffix=".json",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(_payload(data))
        os.replace(temporary, settings_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _load(project: Path) -> tuple[dict[str, object], Path, Path, dict[str, object] | None]:
    root, directory, settings_path = _paths(project)
    _check_project(root, directory, settings_path)
    result: dict[str, object] = {"project": str(root), "settings": str(settings_path)}
    return result, directory, settings_path, _read(settings_path)


def inspect(project: Path) -> dict[str, object]:
    """Report whether settings exist and the recorded profile."""
    result, _, _, data = _load(project)
    result.update(
        status="absent" if data is None else "present",
        profile=None if data is None else data["profile"],
    )
    return result


def initialize(project: Path) -> dict[str, object]:
    """Create settings with no profile; an existing valid file is kept."""
    result, directory, settings_path, data = _load(project)
    if data is None:
        directory.mkdir(exist_ok=True)
        data = dict[str, object](schema_version=SCHEMA_VERSION, profile=None)
        _write_new(settings_path, data)
        result["status"] = "created"
    else:
        result["status"] = "present"
    result["profile"] = data["profile"]
    return result


def select(project: Path, profile: str) -> dict[str, object]:
    """Record the work-progression profile; heavy-to-lite is refused."""
    if profile not in PROFILES:
        raise SettingsError("select requires a lite or heavy profile")
    result, _, settings_path, data = _load(project)
    if data is None:
        raise SettingsError("settings are absent; initialize the project first")
    if data["profile"] == "heavy" and profile == "lite":
        raise SettingsError("heavy-to-lite reversal is not supported")
    if data["profile"] != profile:
        data["profile"] = profile
        _replace(settings_path, data)
        result["status"] = "updated"
    else:
        result["status"] = "present"
    result["profile"] = profile
    return result
