"""Check publisher version mirrors, annotated tags and release records."""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from collections.abc import Mapping
from pathlib import Path

from gzlite.gitenv import clean_git_env
from gzlite.native_identity import marketplace_name

_VERSION = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
_TAG = re.compile(rf"v{_VERSION}")
_HEADING = re.compile(
    rf"^## (?P<version>{_VERSION}) (?:—|\u2013|-) "
    r"(?:\d{4}-\d{2}-\d{2}|[A-Z][a-z]+ \d{1,2}, \d{4})[ \t]*$",
    re.MULTILINE,
)
_RELEASE_COMMIT_FLOOR = (0, 14, 0)
_CATALOGS = (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json")
_PUBLISHER = "tvproductions/gzlite"


def git(root: Path, *args: str, check: bool = True) -> str:
    """Read from the named repository with no hook-inherited Git context."""
    return subprocess.run(
        ["git", *args],
        cwd=root,
        env=clean_git_env(),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    ).stdout.strip()


def released_versions(text: str) -> set[str]:
    """Return dated release entries, excluding drafts and abandoned headings."""
    return {match["version"] for match in _HEADING.finditer(text)}


def version_key(version: str) -> tuple[int, ...]:
    return tuple(map(int, version.split(".")))


def local_tags(root: Path) -> dict[str, str]:
    """Map existing version tag names to their peeled commit IDs."""
    return {
        name: git(root, "rev-parse", "--verify", f"refs/tags/{name}^{{commit}}", check=False)
        for name in git(root, "tag", "--list", "v*").splitlines()
        if _TAG.fullmatch(name)
    }


def _version_at(root: Path, commit: str, file: str) -> str | None:
    content = git(root, "show", f"{commit}:{file}", check=False)
    if not content:
        return None
    if file == "bundle.json":
        return json.loads(content).get("template_version")
    return tomllib.loads(content).get("project", {}).get("version")


def _release_commit_findings(root: Path, version: str, revision: str) -> list[dict[str, str]]:
    previous = f"{revision}^"
    mirrors = ("bundle.json", "pyproject.toml")
    current_log = released_versions(git(root, "show", f"{revision}:CHANGELOG.md", check=False))
    previous_log = released_versions(git(root, "show", f"{previous}:CHANGELOG.md", check=False))
    if (
        any(_version_at(root, revision, name) != version for name in mirrors)
        or any(_version_at(root, previous, name) == version for name in mirrors)
        or version not in current_log
        or version in previous_log
    ):
        return [
            _finding(
                "release-commit",
                f"v{version}",
                f"{revision} must first set both version mirrors and date the changelog entry",
            )
        ]
    return []


def _finding(check: str, artifact: str, message: str) -> dict[str, str]:
    return {"check": check, "artifact": artifact, "message": message}


def _working_version(root: Path) -> str:
    version = json.loads((root / "bundle.json").read_text(encoding="utf-8")).get("template_version")
    if not isinstance(version, str) or not re.fullmatch(_VERSION, version):
        raise ValueError("bundle.json must declare a numeric template_version")
    return version


def check_release_integrity(
    root: Path,
    *,
    published: bool,
    tags: Mapping[str, str],
    releases: Mapping[str, str] | None,
) -> list[dict[str, str]]:
    """Return all observed version, tag, and optional publication discrepancies."""
    current = _working_version(root)
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    mirrors = {"pyproject.toml": (project["project"].get("version"), current)}
    for path in _CATALOGS:
        catalog = json.loads((root / path).read_text(encoding="utf-8"))
        mirrors[path] = catalog.get("name"), marketplace_name(current)
    findings = [
        _finding("version-mirror", path, f"expected {expected!r}, found {actual!r}")
        for path, (actual, expected) in mirrors.items()
        if actual != expected
    ]
    versions = released_versions((root / "CHANGELOG.md").read_text(encoding="utf-8"))
    latest = max(versions, key=version_key, default=None)
    if latest is None or version_key(current) > version_key(latest):
        findings.append(_finding("version-ahead", "bundle.json", f"{current} is ahead of {latest}"))
    elif current != latest:
        findings.append(_finding("version-behind", "bundle.json", f"{current} is behind {latest}"))

    for version in sorted(versions, key=version_key):
        tag = f"v{version}"
        ref = f"refs/tags/{tag}"
        revision = tags.get(tag)
        if not revision:
            findings.append(_finding("missing-tag", tag, "dated release needs an annotated tag"))
            continue
        if not git(root, "rev-parse", "--verify", f"{ref}^{{tag}}", check=False):
            findings.append(_finding("annotated-tag", tag, "the tag must be annotated"))
            continue
        if (
            git(root, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False) != revision
            or _version_at(root, revision, "bundle.json") != version
        ):
            findings.append(_finding("tag-version", tag, f"{revision} does not declare {version}"))
            continue
        if version_key(version) >= _RELEASE_COMMIT_FLOOR:
            findings.extend(_release_commit_findings(root, version, revision))
        if published and (releases is None or releases.get(tag) != revision):
            findings.append(_finding("published-target", tag, f"expected a release at {revision}"))
    return findings


def published_targets(root: Path) -> dict[str, str]:
    """Read GitHub release records and verify the remote tag behind historical labels."""
    remote_tags = {
        name.removeprefix("refs/tags/").removesuffix("^{}"): revision
        for revision, name in (
            line.split("\t", 1)
            for line in git(
                root, "ls-remote", "--tags", "--", f"https://github.com/{_PUBLISHER}.git"
            ).splitlines()
        )
        if name.endswith("^{}")
    }
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    results = {}
    for version in sorted(released_versions(changelog), key=version_key):
        tag = f"v{version}"
        record = subprocess.run(
            [
                "gh",
                "release",
                "view",
                tag,
                "--repo",
                _PUBLISHER,
                "--json",
                "tagName,targetCommitish,isDraft,isPrerelease",
            ],
            cwd=root,
            env=clean_git_env(),
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        if record.returncode != 0:
            if "release not found" in record.stderr.lower():
                continue
            raise ValueError(f"could not read GitHub release {tag}: {record.stderr.strip()}")
        data = json.loads(record.stdout)
        if (
            data["tagName"] != tag
            or data["isDraft"]
            or data["isPrerelease"]
            or tag not in remote_tags
        ):
            continue
        target = data["targetCommitish"]
        if version_key(version) < _RELEASE_COMMIT_FLOOR and target == "main":
            # GitHub ignored this label because the annotated tag already existed.
            target = remote_tags[tag]
        if target == remote_tags[tag]:
            results[tag] = target
    return results
