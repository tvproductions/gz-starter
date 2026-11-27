"""Validate an adopter's bootstrap artifacts and enforce test applicability."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from skills_first_starter.paths import space_free, validate_state_directory
from skills_first_starter.verification_artifacts import (
    declared_readme,
    entry_points,
    project_table,
    read_toml,
    validate_config_files,
    validate_markdown,
    validate_tool_configuration,
)
from skills_first_starter.verification_inventory import inventory_project
from skills_first_starter.verification_unittest import discovery_selection, run_adopter_tests
from skills_first_starter.verification_yaml import (
    HOOK_PATH,
    WORKFLOW_PATH,
    additional_workflow_runs,
    hook_has_inline_tooling,
    read_yaml,
    validate_hook,
    validate_workflow,
)

_REQUIRED = {Path(name) for name in ("pyproject.toml", "uv.lock", ".python-version", HOOK_PATH)}


def _project_root(project: Path) -> Path:
    root = space_free(project).resolve(strict=True)
    if not root.is_dir() or project.is_symlink():
        raise ValueError("project must be an existing directory without a linked root")
    if (root / ".gzkit").exists() or (root / ".gzkit").is_symlink():
        raise ValueError("gzkit projects keep their existing verification")
    return root


def _python_pin(root: Path) -> str:
    pin_file = root / ".python-version"
    pin = pin_file.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"3\.14\.(?:0|[1-9][0-9]*)", pin):
        raise ValueError(".python-version: expected an exact CPython 3.14 patch")
    actual = ".".join(map(str, sys.version_info[:3]))
    if sys.implementation.name != "cpython" or pin != actual:
        raise ValueError(
            f".python-version: expected CPython {pin}; current interpreter is {actual}"
        )
    return pin


def _workflows(root: Path, paths: set[Path], pin: str, floor: str) -> set[Path]:
    triggers = set()
    for path in sorted(paths):
        relative = path.as_posix()
        if relative == WORKFLOW_PATH:
            validate_workflow((root / path).read_bytes(), pin, floor)
        elif relative.startswith(".github/workflows/") and path.suffix in {".yml", ".yaml"}:
            if additional_workflow_runs((root / path).read_bytes(), relative):
                triggers.add(path)
        elif relative.startswith(".github/actions/") and path.name in {"action.yml", "action.yaml"}:
            read_yaml((root / path).read_bytes(), relative)
            triggers.add(path)
    return triggers


def _check_lock(root: Path) -> None:
    read_toml(root, Path("uv.lock"))
    check = subprocess.run(
        ["uv", "lock", "--check", "--project", str(root), "--managed-python"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if check.returncode:
        raise ValueError(f"uv.lock: uv lock --check failed (exit {check.returncode})")


def verify_project(project: Path) -> int:
    """Expose one fail-closed verification entry point for the adopter."""
    try:
        root = _project_root(project)
        validate_state_directory(root)
        inventory = inventory_project(root)
        paths = set(inventory.paths)
        missing = _REQUIRED - paths
        if missing:
            raise ValueError(
                "missing required artifacts: "
                + ", ".join(path.as_posix() for path in sorted(missing))
            )
        pin = _python_pin(root)
        metadata = read_toml(root, Path("pyproject.toml"))
        package = project_table(metadata, "project")
        tools = project_table(metadata, "tool")
        uv = project_table(tools, "uv")
        selection = discovery_selection(
            root, project_table(project_table(tools, "gz-starter"), "verify")
        )
        if "workspace" in uv:
            raise ValueError("uv workspace is outside single-project verification support")
        validate_tool_configuration(root, tools, paths)
        floor = uv.get("required-version", ">=0.13.5")
        if not isinstance(floor, str) or not re.fullmatch(r">=\d+\.\d+\.\d+", floor):
            raise ValueError("pyproject.toml: tool.uv.required-version must declare a minimum")
        declared_readme(package, paths)
        validate_config_files(root, paths)
        validate_markdown(root, paths)
        triggers = set(inventory.triggers)
        triggers.update(entry_points(package, paths))
        triggers.update(_workflows(root, paths, pin, floor))
        if hook_has_inline_tooling(validate_hook((root / HOOK_PATH).read_bytes())):
            triggers.add(Path(HOOK_PATH))
        _check_lock(root)
        print(f"inspected {len(paths)} checkout paths", flush=True)
        if triggers:
            print(
                "behavior required: " + ", ".join(path.as_posix() for path in sorted(triggers)),
                flush=True,
            )
            return run_adopter_tests(root, selection, inventory.paths)
        for path in sorted(paths):
            print(f"  {path.as_posix()}")
        print("bootstrap PASS; product tests not applicable: pre-implementation")
        return 0
    except (LookupError, OSError, RuntimeError, ValueError) as error:
        print(f"verification blocked: {error}", file=sys.stderr)
        return 1
