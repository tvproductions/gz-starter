"""The drift rule's plan-building steps, shared by ``migrate`` and ``freshen``.

Both commands compare an adopter's managed files with what this release writes
and follow one rule (spec 5.1): carry forward what gzlite understands, replace
gzlite-owned files after saving each locally edited copy, and refuse what
cannot be read safely. ``Plan`` holds what every plan records and
``DriftBuilder`` the steps both commands take: saving a copy, choosing a
target, retargeting each configured host and placing ``gzl-update``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from gzlite import cli
from gzlite import migrate_hosts as hosts_config
from gzlite import migrate_legacy as legacy
from gzlite.native import (
    SKILL_SURFACES,
    project_json,
    skill_surface,
    uncovered_hosts,
    update_skill_path,
)
from gzlite.paths import MIGRATED_DIRECTORY, is_link

# Why a file was saved (the "why" of each replaced item).
EDITED = "edited"
RECORD = "record"
# How a configured host appears in a plan's ``carried`` list.
CARRIED_HOST = "host {host} ({path})"
FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")
RENAMED_SKILLS = {
    "gzs-cross-platform-python": "gzs-cross-platform",
    "gzs-pythonic-pattern-detect": "gzs-idiomatic-pattern-detect",
    "gzs-pythonic-pattern-apply": "gzs-idiomatic-pattern-apply",
}
OLD_SKILL = re.compile(r"(?<![\w-])(?:" + "|".join(RENAMED_SKILLS) + r")(?![\w-])")


def renamed_skill_findings(reader: legacy.Reader) -> list[str]:
    """Report stale references in project Markdown and fingerprint the inspected bytes."""
    root = reader.root
    docs = root / "docs"
    findings = []

    def unreadable(path: Path, error: Exception) -> None:
        """Record an optional Markdown scan failure with its project-relative path."""
        name = path.relative_to(root).as_posix()
        findings.append(f"{name}: review gz-skills references manually ({error})")

    def walk_error(error: OSError) -> None:
        """Report a directory that the traversal could not enumerate."""
        unreadable(Path(str(error.filename)) if error.filename else docs, error)

    def unlinked(path: Path) -> bool:
        """Allow ordinary entries and report metadata errors without traversing links."""
        try:
            return not is_link(path)
        except FileNotFoundError:
            return False
        except OSError as error:
            unreadable(path, error)
            return False

    paths = [root / "AGENTS.md", root / "CLAUDE.md"]
    if unlinked(docs) and docs.is_dir(follow_symlinks=False):
        for folder, directories, files in docs.walk(on_error=walk_error):
            directories[:] = [name for name in directories if unlinked(folder / name)]
            paths.extend(folder / name for name in files if name.lower().endswith(".md"))
    for path in sorted(paths):
        if not unlinked(path) or not path.is_file(follow_symlinks=False):
            continue
        name = path.relative_to(root).as_posix()
        try:
            data = reader.read(name)
        except (OSError, ValueError, cli.AdoptionError) as error:
            unreadable(path, error)
            continue
        for old in sorted(set(OLD_SKILL.findall((data or b"").decode("utf-8", errors="replace")))):
            findings.append(
                f"{name}: update `{old}` to `{RENAMED_SKILLS[old]}` in project guidance"
            )
    return sorted(findings)


@dataclass
class Plan:
    """What every drift plan records; ``reasons`` explains each planned write."""

    root: Path
    status: str
    to_version: str
    to_revision: str
    writes: dict[str, str] = field(default_factory=dict)
    before: dict[str, bytes | None] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)
    carried: list[str] = field(default_factory=list)
    replaced: list[dict[str, str]] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    next: list[str] = field(default_factory=list)
    inputs: dict[str, bytes] = field(default_factory=dict)
    fingerprint: str | None = None

    def result(self) -> dict:
        """The command's JSON result."""
        raise NotImplementedError

    def finding(self, text: str) -> object:
        """One finding in the shape this command reports."""
        return text


def require_fingerprint(apply: bool, fingerprint: str | None) -> None:
    if apply and (fingerprint is None or not FINGERPRINT.fullmatch(fingerprint)):
        raise cli.AdoptionError(
            "--apply needs --fingerprint with the 64-hex fingerprint of a reviewed preview"
        )


def apply_plan(plan: Plan, fingerprint: str | None, *, failed: str, done: str, **changes) -> dict:
    """Write a reviewed plan when ``fingerprint`` matches, then report ``status``.

    ``changes`` passes deletes and directories through to ``cli._apply_writes``.
    Saved copies are never undone; a failed status check after the writes is a
    finding, not a refusal.
    """
    if fingerprint != plan.fingerprint:
        raise cli.AdoptionError(
            "the fingerprint does not match the current plan; preview again and review it; "
            f"{legacy.UNCHANGED}"
        )
    try:
        left = cli._apply_writes(
            plan.root,
            {name: cli.check_path(plan.root, name) for name in plan.writes},
            plan.writes,
            plan.before,
            saved={item["path"]: item["saved_to"] for item in plan.replaced},
            **changes,
        )
    except cli.RollbackIncomplete:
        raise
    except (cli.AdoptionError, OSError, ValueError) as error:
        kept = f"; the copies saved under {MIGRATED_DIRECTORY}/ were kept" if plan.replaced else ""
        raise cli.AdoptionError(
            f"{failed} failed and was rolled back ({error}){kept}; preview again"
        ) from error
    plan.status = done
    if left:
        plan.findings.append(
            "staged originals could not be removed: " + ", ".join(left) + "; delete "
            f"{cli.STAGING_DIRECTORY}/ by hand once nothing holds them open"
        )
    result = plan.result()
    try:
        result["post_apply_status"] = cli.status(plan.root)
    except (cli.AdoptionError, OSError, ValueError, KeyError) as error:
        result["post_apply_status"] = {"status": "unavailable", "error": str(error)}
        result["findings"].append(plan.finding(f"post-apply status could not run: {error}"))
    return result


class DriftBuilder[P: Plan]:
    """Accumulate one adopter's plan; subclasses add their command's own steps.

    ``saves_under`` is the folder copies are saved in. ``recorded_version`` and
    ``recorded_marketplace`` name the release whose entries are being replaced.
    """

    # How a ``record`` copy is described in the reason for saving it.
    record_label = "unchanged legacy state file"

    def __init__(
        self,
        plan: P,
        reader: legacy.Reader,
        lock: legacy.LegacyLock,
        *,
        saves_under: str,
        recorded_version: str,
        recorded_marketplace: str,
    ) -> None:
        self.plan = plan
        self.reader = reader
        self.lock = lock
        self.root = plan.root
        self.saves_under = saves_under
        self.recorded_version = recorded_version
        self.recorded_marketplace = recorded_marketplace
        self.placement: tuple[str, ...] = ()
        self.saved: dict[str, str] = {}
        self.saved_from: dict[str, str] = {}
        self.host_candidates: dict[str, dict[str, str]] = {}
        self.targets: dict[str, str] = {}
        self.replaceable: set[str] = set()
        self.parts = cli.bundle()["components"]
        self.current = cli.marketplace()

    def save(self, name: str, text: str, fate: str = "replaced", why: str = EDITED) -> str:
        """Plan a copy of ``name`` under ``saves_under``; it is never undone.

        ``why`` is ``edited`` (the bytes differ from what the recorded commit
        wrote, or it wrote no such file) or ``record`` (unchanged state, kept
        so the old lock's pins and keys stay readable).
        """
        saved_to = f"{self.saves_under}/{name}"
        existing = self.reader.read(saved_to)
        if existing is not None and existing != text.encode():
            # A copy kept by an earlier, rolled-back attempt is never overwritten.
            raise cli.AdoptionError(
                f"{saved_to} already holds a different saved copy; move it aside after "
                f"review; {legacy.UNCHANGED}"
            )
        what = "locally edited" if why == EDITED else self.record_label
        self.saved[saved_to] = text
        self.saved_from[name] = saved_to
        self.plan.reasons[saved_to] = f"saves the {what} {name} before it is {fate}"
        self.plan.replaced.append({"path": name, "saved_to": saved_to, "why": why})
        return saved_to

    def untouched(self, name: str, existing: str, payload: str) -> bool:
        """Whether ``existing`` is proven unedited; line endings never count."""
        return legacy.normalized(existing) == legacy.normalized(payload)

    def owned(self, name: str, payload: str, reason: str) -> None:
        """Replace a gzlite-owned file, first saving it unless it is proven untouched."""
        existing = self.reader.text(name)
        if existing is not None and not self.untouched(name, existing, payload):
            self.save(name, existing)
        self.target(name, payload, reason, True)

    def target(self, name: str, payload: str, reason: str, replaceable: bool = False) -> None:
        self.targets[name] = payload
        self.plan.reasons[name] = reason
        if replaceable:
            self.replaceable.add(name)

    def claude_local_check(self) -> None:
        """The check configure runs on Claude local settings, which it never writes."""
        text = self.reader.text(".claude/settings.local.json")
        if text is not None:
            ref = self.plan.to_revision
            project_json(text, "claude", ref, self.parts, self.current, retire=False)

    def host_reason(self) -> str:
        """Why each host's configuration is rewritten."""
        to = self.plan.to_version
        return (
            f"gzlite {to} retires the {self.recorded_marketplace} entries and adds "
            f"{self.current} with the {to} bundle"
        )

    def host_targets(
        self, configs: list[hosts_config.HostConfig], policy, working
    ) -> dict[str, str]:
        to, ref, found = self.plan.to_version, self.plan.to_revision, {}
        for config in configs:
            paths = {
                config.path: cli.check_path(self.root, config.path),
                "AGENTS.md": cli.check_path(self.root, "AGENTS.md"),
            }
            candidates, _ = cli._configuration_candidates(
                paths,
                ref,
                config.host,
                policy=policy,
                working_policy=working,
                old_config=config.retired,
                carried=self.lock.extras,
            )
            payload = candidates[config.path]
            if config.original is not None and hosts_config.lost_comments(
                config.host, config.original, payload
            ):
                config.edits.append("local comments in removed starter entries")
            if config.edits and config.original is not None:
                saved = self.save(config.path, config.original)
                self.plan.findings.append(
                    f"{config.path}: starter entries differed from what {self.recorded_version} "
                    f"wrote ({'; '.join(config.edits)}); they were replaced by gzlite {to} "
                    f"entries and the original is saved at {saved}"
                )
                self.plan.findings += config.guidance(saved, self.current)
            self.plan.carried.append(CARRIED_HOST.format(host=config.host, path=config.path))
            self.plan.carried += config.carried
            self.host_candidates[config.host] = candidates
            self.target(config.path, payload, self.host_reason())
            if config.host == self.lock.host:
                found = candidates
        return found

    def update_skills(self) -> None:
        """``gzl-update`` on each configured host's own surface, without duplicates."""
        to, hosts = self.plan.to_version, list(self.host_candidates)
        for surface in self.placement:
            host = next(h for h in hosts if skill_surface(h) == surface)
            skill = update_skill_path(host)
            payload = self.host_candidates[host][skill]
            self.owned(skill, payload, f"gzlite {to} update skill {cli.UPDATE_SKILL}")
        for host in hosts:
            if host in uncovered_hosts([host], self.placement):
                self.plan.findings.append(
                    f"{host} is configured but gets no {cli.UPDATE_SKILL}: a copy on its "
                    f"surface {skill_surface(host)} would be discovered twice by another "
                    f"configured host; it is installed at {', '.join(self.placement)} only"
                )
            elif skill_surface(host) not in self.placement:
                self.plan.findings.append(
                    f"{host} is expected to discover {cli.UPDATE_SKILL} at "
                    f"{', '.join(s for s in self.placement if s in SKILL_SURFACES[host])} "
                    "(gzlite run-opencode adds that surface to its skills setting, "
                    "src/gzlite/native_launch.py:39); a plain opencode launch reading it is "
                    "unverified"
                )
