"""Resolve adopter pins from the publisher's annotated release tags."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from gzlite.gitenv import clean_git_env

SHA = re.compile(r"[0-9a-f]{40}\Z")
_TAG = re.compile(r"refs/tags/v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")


class ReleaseError(ValueError):
    """Git could not establish a published release for the requested pin."""


@dataclass(frozen=True)
class TaggedRelease:
    tag: str
    version: str
    revision: str
    bundle: dict


def _git(cwd: Path, *args: str) -> str:
    env = clean_git_env()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    ).stdout.strip()


def _published_tags(directory: Path, origin: str, revision: str) -> dict[str, str]:
    advertised: dict[str, str] = {}
    for line in _git(directory, "ls-remote", "--tags", "--", origin, "v*").splitlines():
        oid, separator, name = line.partition("\t")
        if separator and SHA.fullmatch(oid):
            advertised[name] = oid
    return {
        name: oid
        for name, oid in advertised.items()
        if _TAG.fullmatch(name) and advertised.get(f"{name}^{{}}") == revision
    }


def tagged_release(ref: str, *, origin: str) -> TaggedRelease:
    """Verify the peeled commit and its bundle version against the publisher."""
    if not SHA.fullmatch(ref):
        raise ReleaseError(f"use a full starter commit SHA for a published release: {ref!r}")
    try:
        with tempfile.TemporaryDirectory(prefix="gzlite-release-") as temporary:
            directory = Path(temporary)
            tags = _published_tags(directory, origin, ref)
            if not tags:
                raise ReleaseError(
                    f"{ref} is not the commit of an annotated release tag on {origin}"
                )
            _git(directory, "init", "--bare", "--quiet")
            _git(
                directory,
                "fetch",
                "--quiet",
                "--depth=1",
                "--no-tags",
                "--",
                origin,
                *(f"{name}:{name}" for name in tags),
            )
            bundle = json.loads(_git(directory, "show", f"{ref}:bundle.json"))
            version = bundle.get("template_version") if isinstance(bundle, dict) else None
            name = f"refs/tags/v{version}"
            if not isinstance(version, str) or name not in tags:
                raise ReleaseError(
                    f"{ref} on {origin} declares bundle version {version!r}, "
                    "which does not match its annotated release tags"
                )
            actual = _git(
                directory, "rev-parse", f"{name}^{{tag}}", f"{name}^{{commit}}"
            ).splitlines()
            if actual != [tags[name], ref]:
                raise ReleaseError(f"release tag {name} on {origin} changed while checking {ref}")
    except (OSError, subprocess.SubprocessError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseError(
            f"could not verify release {ref} on {origin}; check that Git, the origin, "
            "and the tagged bundle are available"
        ) from error
    return TaggedRelease(name.removeprefix("refs/tags/"), version, ref, bundle)
