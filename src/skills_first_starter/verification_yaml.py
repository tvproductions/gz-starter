"""Read adopter YAML and check the supported hook and workflow."""

from __future__ import annotations

import re
import shlex
from copy import deepcopy
from importlib.resources import files
from typing import Any

import yaml


class WorkflowLoader(yaml.SafeLoader):
    """Require unique keys and resolve booleans as in YAML 1.2."""

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key == "<<" or key in mapping:
                raise ValueError("expected unique string keys with no YAML merges")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


WorkflowLoader.yaml_implicit_resolvers = {
    char: [(tag, pattern) for tag, pattern in rules if tag != "tag:yaml.org,2002:bool"]
    for char, rules in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
WorkflowLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)

WORKFLOW_PATH = ".github/workflows/verify-python.yml"
HOOK_PATH = ".pre-commit-config.yaml"
HOOK_FIELDS = {
    "id": "unittest",
    "entry": "uv run --locked gz-starter verify --project .",
    "language": "system",
    "pass_filenames": False,
    "always_run": True,
    "stages": ["pre-commit"],
}
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def read_yaml(data: bytes, path: str) -> dict[str, Any]:
    """Return one safe mapping, keeping document content out of errors."""
    try:
        for event in yaml.parse(data, Loader=WorkflowLoader):
            if (
                getattr(event, "anchor", None) is not None
                or getattr(event, "tag", None) is not None
            ):
                raise ValueError("YAML aliases, anchors and explicit tags are unsupported")
        parsed = yaml.load(data, Loader=WorkflowLoader)
        if not isinstance(parsed, dict):
            raise ValueError("expected one YAML mapping")
        return parsed
    except yaml.YAMLError as error:
        raise ValueError(f"{path}: malformed or unsupported YAML") from error
    except (ValueError, RecursionError) as error:
        raise ValueError(f"{path}: invalid YAML structure ({type(error).__name__})") from error


def _hook_is_eligible(hook: dict[str, Any], config: dict[str, Any]) -> bool:
    fields = {key: value for key, value in hook.items() if key != "name"}
    defaults = config.get("default_install_hook_types", ["pre-commit"])
    return (
        fields == HOOK_FIELDS
        and all(type(fields[key]) is bool for key in ("always_run", "pass_filenames"))
        and isinstance(hook.get("name"), str)
        and config.get("files", "") == ""
        and config.get("exclude", "^$") == "^$"
        and isinstance(defaults, list)
        and "pre-commit" in defaults
    )


def validate_hook(data: bytes) -> list[dict[str, Any]]:
    """Require the exact local verifier hook regardless of surrounding categories."""
    config = read_yaml(data, HOOK_PATH)
    repos = config.get("repos")
    if not isinstance(repos, list):
        raise ValueError(f"{HOOK_PATH}: expected a list of hook repositories")
    matches = []
    for repo in repos:
        if not isinstance(repo, dict) or not isinstance(repo.get("hooks"), list):
            raise ValueError(f"{HOOK_PATH}: expected a hooks list")
        for hook in repo["hooks"]:
            if not isinstance(hook, dict) or not isinstance(hook.get("id"), str):
                raise ValueError(f"{HOOK_PATH}: hook entries require a string ID")
            if hook["id"] == "unittest":
                matches.append((repo.get("repo"), hook))
    if len(matches) != 1 or matches[0][0] != "local":
        raise ValueError(f"{HOOK_PATH}: require one local unittest hook")
    if not _hook_is_eligible(matches[0][1], config):
        raise ValueError(f"{HOOK_PATH}: mismatch in the supported unittest hook or its eligibility")
    return repos


def hook_has_inline_tooling(repos: list[dict[str, Any]]) -> bool:
    """Identify local entries beyond the supported verifier and direct routine tools."""
    return any(
        not _routine_entry(hook.get("entry"))
        for repo in repos
        if repo.get("repo") == "local"
        for hook in repo["hooks"]
    )


def _routine_entry(entry: object) -> bool:
    if entry == HOOK_FIELDS["entry"]:
        return True
    if not isinstance(entry, str):
        return False
    argv = shlex.split(entry)
    return argv[:3] == ["uv", "run", "--locked"] and tuple(argv[3:5]) in {
        ("ruff", "check"),
        ("ruff", "format"),
        ("ty", "check"),
    }


def _remove_display_name(section: dict[str, Any]) -> None:
    if "name" in section and not isinstance(section.pop("name"), str):
        raise ValueError("workflow display names must be strings")


def _normalized_recipe(value: dict[str, Any]) -> dict[str, Any]:
    recipe = deepcopy(value)
    _remove_display_name(recipe)
    if not isinstance(recipe["jobs"], dict):
        raise ValueError("expected workflow jobs")
    for job in recipe["jobs"].values():
        if not isinstance(job, dict) or not isinstance(job.get("steps"), list):
            raise ValueError("expected job mapping and steps")
        _remove_display_name(job)
        for step in job["steps"]:
            if not isinstance(step, dict):
                raise ValueError("expected workflow step mapping")
            _remove_display_name(step)
            if isinstance(step.get("run"), str):
                step["run"] = step["run"].removesuffix("\n")
    return recipe


def validate_workflow(data: bytes, python_pin: str, uv_floor: str) -> None:
    """Accept the reviewed workflow shape and version/digest parameters."""
    parsed = read_yaml(data, WORKFLOW_PATH)
    reference = files("skills_first_starter").joinpath(
        "resources/templates/verification/verify-python.yml"
    )
    expected = read_yaml(reference.read_bytes(), WORKFLOW_PATH)
    try:
        version = parsed["env"]["UV_VERSION"]
        _check_workflow_versions(parsed["env"]["PYTHON_VERSION"], python_pin, version, uv_floor)
        expected["env"].update(PYTHON_VERSION=python_pin, UV_VERSION=version)
        for platform in ("macos", "windows"):
            digest = parsed["jobs"][platform]["steps"][1]["env"]["UV_SHA256"]
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
                raise ValueError("expected a SHA-256 digest")
            expected["jobs"][platform]["steps"][1]["env"]["UV_SHA256"] = digest
        matches = _normalized_recipe(parsed) == _normalized_recipe(expected)
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ValueError(
            f"{WORKFLOW_PATH}: invalid runner, version, or digest configuration"
        ) from error
    if not matches:
        raise ValueError(f"{WORKFLOW_PATH}: workflow differs from the supported executable recipe")


def _check_workflow_versions(pin: Any, python_pin: str, version: Any, floor: str) -> None:
    if pin != python_pin or not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise ValueError("expected the exact Python pin and a stable uv version")
    floor_version = floor.removeprefix(">=")
    if tuple(map(int, version.split("."))) < tuple(map(int, floor_version.split("."))):
        raise ValueError("uv version is below the project floor")


def additional_workflow_runs(data: bytes, path: str) -> bool:
    """Detect executable steps and reusable workflow calls in additional files."""
    jobs = read_yaml(data, path).get("jobs")
    if not isinstance(jobs, dict) or any(not isinstance(job, dict) for job in jobs.values()):
        raise ValueError(f"{path}: expected workflow jobs")
    for job in jobs.values():
        steps = job.get("steps", [])
        if not isinstance(steps, list) or any(not isinstance(step, dict) for step in steps):
            raise ValueError(f"{path}: expected a list of workflow steps")
        if "uses" in job or any("run" in step or "uses" in step for step in steps):
            return True
    return False
