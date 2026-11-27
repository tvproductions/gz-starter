"""Read the embedded history of what each gz-starter release's ``configure`` wrote.

``migrate`` uses this to tell untouched managed files from local edits in a project
that adopted an earlier gz-starter (or skills-first-starter) release. The data file
``resources/release_history.json`` is generated from the immutable tags
``v0.1.0`` to ``v0.13.0`` by ``tools/build_release_history.py``; its format is
documented in ``resources/schemas/release-history.schema.json``. Nothing here runs
git: a project's recorded revision is resolved through the embedded revision map.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from importlib.resources import files

SCHEMA_VERSION = 1
HISTORY_RESOURCE = "resources/release_history.json"
# A managed path entry is "<marker>:<path>" or a bare path (marker "always").
# Repository-relative paths never contain ":", which Windows forbids in names.
MARKERS = frozenset({"always", "if-absent", "merged", "merged-if-exists", "adr-local"})


class HistoryError(ValueError):
    """The history is unreadable or does not contain the requested revision."""


@dataclass(frozen=True, slots=True)
class ManagedPath:
    """One path a release's ``configure`` wrote, and the condition it wrote it under.

    ``always``: whole file, always written, content equals the release's template.
    ``if-absent``: written only when the file did not exist; project-owned after.
    ``merged``: host configuration; starter entries merged into existing content.
    ``merged-if-exists``: used instead of the host's ``merged`` path when it
    already existed (OpenCode ``opencode.jsonc``).
    ``adr-local``: written only when the lock's ``adr_policy.mode`` is ``local``.
    """

    path: str
    condition: str


@dataclass(frozen=True, slots=True)
class Release:
    """What one tagged starter release's ``configure`` wrote.

    Templates are raw text with ``{{...}}`` placeholders left in place; a caller
    renders them with the adopter's recorded revision.
    """

    version: str
    tag: str
    revision: str
    origin: str
    state_directory: str
    marketplace: str
    fragment_template: str
    update_skill: str | None
    update_skill_template: str | None
    adr_placeholders: bool
    hosts: list[str]
    managed_paths: dict[str, list[str]]
    front_door_skill: str | None
    front_door_skill_template: str | None
    agents_md_template: str
    lock_keys: list[str]
    adr_policy_source: str | None
    adr_policy_template: str | None
    adr_policy_url: str | None

    def managed_entries(self, host: str) -> list[ManagedPath]:
        """Parse this release's managed paths for ``host`` into path and condition."""
        if host not in self.managed_paths:
            raise HistoryError(f"{self.tag} did not support host {host}")
        entries = []
        for entry in self.managed_paths[host]:
            condition, separator, path = entry.partition(":")
            entries.append(
                ManagedPath(path, condition) if separator else ManagedPath(entry, "always")
            )
        return entries


@dataclass(frozen=True, slots=True)
class History:
    """Every starter release and the map from each starter commit to its release."""

    releases: list[Release]
    revisions: dict[str, str]

    def release_for(self, revision: str) -> Release:
        """Return the release at or nearest before ``revision`` in the starter's history."""
        tag = self.revisions.get(revision)
        if tag is None:
            raise HistoryError(f"revision {revision} is not in the starter's release history")
        for release in self.releases:
            if release.tag == tag:
                return release
        raise HistoryError(f"revision {revision} maps to unknown release {tag}")


_RELEASE_FIELDS = frozenset(field.name for field in fields(Release))


def _release(data: object) -> Release:
    if not isinstance(data, dict) or set(data) != _RELEASE_FIELDS:
        raise HistoryError("release history entry has unexpected fields")
    release = Release(**data)
    for host in release.hosts:
        for entry in release.managed_entries(host):
            if entry.condition not in MARKERS:
                raise HistoryError(f"{release.tag} has unknown managed path marker {entry}")
    return release


def parse_history(text: str) -> History:
    """Validate the history document's shape and build the lookup objects."""
    try:
        data = json.loads(text)
    except ValueError as error:
        raise HistoryError(f"release history is not valid JSON: {error}") from error
    if not isinstance(data, dict) or set(data) != {"schema_version", "releases", "revisions"}:
        raise HistoryError("release history has unexpected top-level keys")
    if data["schema_version"] != SCHEMA_VERSION:
        raise HistoryError("unsupported release history schema")
    releases = [_release(item) for item in data["releases"]]
    tags = {release.tag for release in releases}
    revisions = data["revisions"]
    if not isinstance(revisions, dict) or not set(revisions.values()) <= tags:
        raise HistoryError("release history maps revisions to unknown releases")
    return History(releases, revisions)


def load_history() -> History:
    """Load the history embedded in this installed package."""
    text = files("gzlite").joinpath(HISTORY_RESOURCE).read_text(encoding="utf-8")
    return parse_history(text)
