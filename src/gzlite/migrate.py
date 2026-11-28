"""``gzlite migrate``: move a legacy gz-starter or skills-first adopter into gzlite.

The plan is built from the adopter's lock and the embedded release history:
the lock's revision names the starter commit whose ``configure`` wrote the
project, and ``History.release_for`` returns that commit's own snapshot. Every
difference from what that commit wrote goes through the drift rule (spec 5.1):

- carry forward what gzlite understands: extra lock keys, extra catalogs and
  plugins in host configuration, and every configured host;
- replace gzlite-owned files with this release's, first saving each locally
  edited copy under ``.gzlite/migrated/<original path>``;
- refuse, changing nothing, what cannot be read safely.

Preview is the default. ``--apply`` recomputes the plan and writes only when
its fingerprint equals the reviewed one; the legacy folder is removed last.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from gzlite import cli
from gzlite import migrate_hosts as hosts_config
from gzlite import migrate_legacy as legacy
from gzlite.fingerprint import fingerprint as compute_fingerprint
from gzlite.history import Release, load_history
from gzlite.native import (
    SKILL_SURFACES,
    project_json,
    skill_surface,
    uncovered_hosts,
    update_skill_path,
    update_skill_placement,
)
from gzlite.paths import BUNDLE_LOCK, MIGRATED_DIRECTORY, refuse_staging

FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")
FRAGMENT = "AGENTS.skills-first.md"
PROFILE = ".gz-skills/settings.json"
PYPROJECT = "pyproject.toml"
# Why a file was saved under .gzlite/migrated/ (the "why" of each replaced item).
EDITED = "edited"
RECORD = "record"


@dataclass
class MigrationPlan:
    """Everything one migration would change, and why."""

    root: Path
    status: str
    to_version: str
    to_revision: str
    from_version: str | None = None
    from_revision: str | None = None
    snapshot: str | None = None
    writes: dict[str, str] = field(default_factory=dict)
    before: dict[str, bytes | None] = field(default_factory=dict)
    deletes: list[str] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    reasons: dict[str, str] = field(default_factory=dict)
    carried: list[str] = field(default_factory=list)
    replaced: list[dict[str, str]] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    next: list[str] = field(default_factory=list)
    inputs: dict[str, bytes] = field(default_factory=dict)
    fingerprint: str | None = None

    def changes(self) -> list[dict[str, str]]:
        listed = [{"path": n, "action": "write", "reason": self.reasons[n]} for n in self.writes]
        return listed + [
            {"path": n, "action": "delete", "reason": self.reasons[n]} for n in self.deletes
        ]

    def fingerprinted(self) -> dict:
        """The plan as the fingerprint sees it: every change, payloads by hash."""
        return {
            "from": [self.from_version, self.from_revision, self.snapshot],
            "to": [self.to_version, self.to_revision],
            "writes": [
                [name, hashlib.sha256(payload.encode()).hexdigest()]
                for name, payload in self.writes.items()
            ],
            "deletes": self.deletes,
            "directories": self.directories,
            "carried": self.carried,
            "replaced": self.replaced,
            "findings": self.findings,
        }

    def result(self) -> dict:
        return {
            "status": self.status,
            "from_version": self.from_version,
            "from_revision": self.from_revision,
            "to_version": self.to_version,
            "writes": self.changes(),
            "carried": self.carried,
            "replaced": self.replaced,
            "findings": self.findings,
            "next": self.next,
            "fingerprint": self.fingerprint,
        }


class _Builder:
    """Accumulate the plan for one adopter; the methods run in order."""

    def __init__(
        self, plan: MigrationPlan, reader: legacy.Reader, release: Release, lock: legacy.LegacyLock
    ) -> None:
        self.plan = plan
        self.reader = reader
        self.release = release
        self.lock = lock
        self.root = plan.root
        self.placement: tuple[str, ...] = ()
        self.working = ""  # the active ADR policy: local copy path or canonical URL
        self.saved: dict[str, str] = {}
        self.saved_from: dict[str, str] = {}
        self.host_candidates: dict[str, dict[str, str]] = {}
        self.targets: dict[str, str] = {}
        self.replaceable: set[str] = set()
        self.delete_bytes: dict[str, bytes] = {}
        self.parts = cli.bundle()["components"]
        self.current = cli.marketplace()

    # Findings about the recorded identity -------------------------------------------

    def identity(self, tagged: set[str], state: str) -> None:
        release, lock, findings = self.release, self.lock, self.plan.findings
        findings += lock.notes
        if lock.revision not in tagged:
            findings.append(
                f"{release.version} at {lock.revision} was never a tagged release; "
                "migrated from that commit's own snapshot"
            )
        if lock.version != release.version:
            findings.append(
                f"the lock records version {lock.version}, but {lock.revision} declares "
                f"{release.version}; the revision decides"
            )
        if state != release.state_directory:
            findings.append(
                f"the lock was found in {state}/, but {release.version} kept state in "
                f"{release.state_directory}/"
            )
        old = {part["name"]: part["revision"] for part in lock.components}
        new = {part["name"]: part["revision"] for part in self.parts}
        moved = [
            f"{name} {old.get(name, 'unpinned')} -> {new.get(name, 'removed')}"
            for name in sorted(set(old) | set(new))
            if old.get(name) != new.get(name)
        ]
        if moved:
            findings.append(
                f"component pins move to the gzlite {self.plan.to_version} bundle: "
                + "; ".join(moved)
                + f"; the old lock is saved under {MIGRATED_DIRECTORY}/{state}/"
            )

    # Saving and retiring ------------------------------------------------------------

    def save(self, name: str, text: str, fate: str = "replaced", why: str = EDITED) -> str:
        """Plan a copy of ``name`` under ``.gzlite/migrated/``; it is never undone.

        ``why`` is ``edited`` (the bytes differ from what the recorded commit
        wrote, or it wrote no such file) or ``record`` (unchanged legacy state,
        kept so the old lock's pins and keys stay readable).
        """
        saved_to = f"{MIGRATED_DIRECTORY}/{name}"
        existing = self.reader.read(saved_to)
        if existing is not None and existing != text.encode():
            # A copy kept by an earlier, rolled-back attempt is never overwritten.
            raise cli.AdoptionError(
                f"{saved_to} already holds a different saved copy; move it aside after "
                f"review; {legacy.UNCHANGED}"
            )
        what = "locally edited" if why == EDITED else "unchanged legacy state file"
        self.saved[saved_to] = text
        self.saved_from[name] = saved_to
        self.plan.reasons[saved_to] = f"saves the {what} {name} before it is {fate}"
        self.plan.replaced.append({"path": name, "saved_to": saved_to, "why": why})
        return saved_to

    def retire(
        self, name: str, expected: str | None, reason: str, record: bool = False
    ) -> str | None:
        """Delete a file the old release owned, saving it when it differs from ``expected``.

        ``expected`` is None when the recorded commit wrote no such file. With
        ``record`` an unchanged file is saved too, as a ``record``. Returns
        the saved copy's path when the file counts as edited.
        """
        data = self.reader.read(name)
        if data is None:
            return None
        text = legacy.decode(name, data)
        edited = expected is None or legacy.normalized(text) != legacy.normalized(expected)
        saved = (
            self.save(name, text, "removed", EDITED if edited else RECORD)
            if edited or record
            else None
        )
        self.delete_bytes[name] = data
        self.plan.deletes.append(name)
        self.plan.reasons[name] = reason
        return saved if edited else None

    def retire_tree(self, folder: str, expected: dict[str, str | None], reason: str) -> None:
        files, directories = legacy.tree(self.root, folder)
        for name in files:
            self.retire(name, expected.get(name), reason)
        self.plan.directories += directories

    def skill_trees(self, hosts: list[str]) -> list[tuple[str, dict[str, str | None]]]:
        """Directories of the old release's starter skills on the configured hosts."""
        trees: dict[str, dict[str, str | None]] = {}
        for host in hosts:
            if host not in self.release.hosts:
                continue
            for entry in self.release.managed_entries(host):
                template = legacy.skill_template(self.release, entry.path)
                folder = Path(entry.path).parent.as_posix()
                if template is not None and os.path.lexists(self.root / folder):
                    if legacy.is_link(self.root / folder):
                        raise cli.AdoptionError(f"{folder} is a link; {legacy.UNCHANGED}")
                    trees.setdefault(folder, {})[entry.path] = template
        return sorted(trees.items())

    def retire_old_state(self, state: str, hosts: list[str]) -> list[str]:
        trees = self.skill_trees(hosts)
        to = self.plan.to_version
        for folder, expected in trees:
            name = Path(folder).name
            why = (
                f"gzlite {to} renames {name} to {cli.UPDATE_SKILL}"
                if name == self.release.update_skill
                else f"{name} is no longer a starter skill"
            )
            self.retire_tree(folder, expected, why)
        # Every legacy file, the lock included, is saved before it is removed, so a
        # failed rollback can never leave the adoption without any record. Files
        # with a template are still judged: an edited one is reported as edited.
        reason = f"gzlite {to} keeps starter state in .gzlite/"
        lock_name = f"{state}/bundle.lock.json"
        adr_name = f"{state}/{legacy.ADR_COPY}"
        adr = legacy.adr_copy_template(self.release, state, self.lock.adr_mode)
        files, directories = legacy.tree(self.root, state)
        for name in files:
            if name == lock_name:
                # Generated, not templated: kept as a record, its changes reported apart.
                self.retire(name, legacy.decode(name, self.reader.read(name) or b""), reason, True)
            elif name == adr_name and adr is not None:
                saved = self.retire(name, adr, reason, record=True)
                if saved is not None:
                    self.plan.findings.append(
                        f"{name} differs from the ADR policy {self.release.version} copied; its "
                        f"local amendments were not carried into the active policy "
                        f"{self.working}, which is the gzlite {to} copy; the amended copy is "
                        f"saved at {saved}"
                    )
            else:
                # configure never wrote it: project content, always edited.
                self.retire(name, None, reason, record=True)
        # Removed last, after the skills: the legacy folder is the migration's marker.
        self.plan.directories += directories
        return [folder for folder, _ in trees]

    # Targets ------------------------------------------------------------------------

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
                saved = f"{MIGRATED_DIRECTORY}/{config.path}"
                self.save(config.path, config.original)
                self.plan.findings.append(
                    f"{config.path}: starter entries differed from what {self.release.version} "
                    f"wrote ({'; '.join(config.edits)}); they were replaced by gzlite {to} "
                    f"entries and the original is saved at {saved}"
                )
                self.plan.findings += config.guidance(saved, self.current)
            self.plan.carried.append(f"host {config.host} ({config.path})")
            self.plan.carried += config.carried
            self.host_candidates[config.host] = candidates
            self.target(
                config.path,
                payload,
                f"gzlite {to} retires the {self.release.marketplace} entries and adds "
                f"{self.current} with the {to} bundle",
            )
            if config.host == self.lock.host:
                found = candidates
        return found

    def managed_targets(self, candidates: dict[str, str], copies: dict[str, str]) -> None:
        to, lock, release = self.plan.to_version, self.lock, self.release
        self.target(
            BUNDLE_LOCK,
            candidates[BUNDLE_LOCK],
            f"gzlite {to} records gzlite {to} at {self.plan.to_revision}, the {to} "
            "component pins and the carried lock keys in .gzlite/",
        )
        self.plan.carried += [f"lock key {key}" for key in lock.extras]
        fragment = candidates[FRAGMENT]
        current = self.reader.text(FRAGMENT)
        expected = legacy.release_fragment(release, lock.revision, lock.adr_mode)
        if current is not None and legacy.normalized(current) not in (
            legacy.normalized(expected),
            legacy.normalized(fragment),
        ):
            self.save(FRAGMENT, current)
        self.target(FRAGMENT, fragment, f"gzlite {to} fragment", replaceable=True)
        self.update_skills()
        if "AGENTS.md" in candidates:
            self.target(
                "AGENTS.md",
                candidates["AGENTS.md"],
                "AGENTS.md is missing; configure writes the default pointer to the fragment",
            )
        for name, payload in copies.items():
            self.target(name, payload, f"gzlite {to} keeps the local ADR policy copy in .gzlite/")

    def update_skills(self) -> None:
        """``gzl-update`` on each configured host's own surface, without duplicates."""
        to, hosts = self.plan.to_version, list(self.host_candidates)
        for surface in self.placement:
            host = next(h for h in hosts if skill_surface(h) == surface)
            skill = update_skill_path(host)
            payload = self.host_candidates[host][skill]
            existing = self.reader.text(skill)
            if existing is not None and legacy.normalized(existing) != legacy.normalized(payload):
                self.save(skill, existing)
            self.target(skill, payload, f"gzlite {to} update skill {cli.UPDATE_SKILL}", True)
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

    def pyproject(self) -> None:
        text = self.reader.text(PYPROJECT)
        if text is None:
            return
        requirement = f"gzlite[verification] @ git+{cli.ORIGIN}@{self.plan.to_revision}"
        renamed = legacy.rename_verification(text, requirement)
        if renamed != text:
            self.target(
                PYPROJECT,
                renamed,
                f"gzlite {self.plan.to_version} renames the verification extra's package "
                "from gz-starter to gzlite",
                replaceable=True,
            )
            self.plan.next.append(
                "Required: run uv lock to relock the renamed gzlite[verification] dependency; "
                "it needs the network and is outside the fingerprint."
            )
        if "gz-starter" in renamed:
            self.plan.findings.append(
                "pyproject.toml still names gz-starter; rename it to gzlite by hand"
            )

    def finish(self) -> None:
        plan = self.plan
        candidates = {**self.saved, **self.targets}
        paths = {name: cli.check_path(self.root, name) for name in candidates}
        replaceable = self.replaceable
        plan.writes, plan.before, _ = cli._plan_writes(paths, candidates, replaceable)
        plan.before.update(self.delete_bytes)
        plan.inputs = dict(self.reader.inputs)
        if any(item["why"] == EDITED for item in plan.replaced):
            plan.next.insert(
                0,
                f"Review each file saved under {MIGRATED_DIRECTORY}/; carry any wanted local "
                "edits into project-owned files, then delete the copies.",
            )
        plan.next += [
            "Run gzlite freshen --project . next and work its findings.",
            "Start a fresh agent session and confirm gzl-update and the bundle plugins are "
            "discovered; runtime readiness is unverified.",
        ]
        plan.fingerprint = compute_fingerprint(plan.inputs, plan.fingerprinted())


def _nothing(root: Path, ref: str, note: str | None) -> MigrationPlan:
    plan = MigrationPlan(root, "nothing to migrate", cli.template_version(), ref)
    if note:
        plan.findings.append(note)
    adopted = (root / BUNDLE_LOCK).exists()
    plan.next.append(
        "Run gzlite freshen --project . to bring this gzlite adopter to the running release."
        if adopted
        else "No starter adoption found; use gzlite configure to adopt gzlite."
    )
    return plan


def plan_migration(project: Path, ref: str) -> MigrationPlan:
    """Read the adopter and plan the whole move, refusing what cannot be read safely."""
    cli.validate_bundle()
    if not cli.SHA.fullmatch(ref):
        raise cli.AdoptionError(
            "use a reviewed, published full gzlite commit SHA; moving branches are not pins"
        )
    root = cli._adoption_root(project)
    legacy.refuse_go_project(root)
    # Only an incomplete rollback (or a failed cleanup) leaves staged originals.
    refuse_staging(root)
    state = legacy.legacy_directory(root)
    if state is None:
        empty = [name for name in legacy.LEGACY_DIRECTORIES if (root / name).is_dir()]
        note = f"{empty[0]}/ holds no starter state and was left in place" if empty else None
        return _nothing(root, ref, note)
    legacy.refuse_gzlite_state(root)
    reader = legacy.Reader(root)
    lock_name = f"{state}/bundle.lock.json"
    data = reader.read(lock_name)
    if data is None:
        raise cli.AdoptionError(
            f"{state}/ holds starter state but no bundle.lock.json; reconcile by hand; "
            f"{legacy.UNCHANGED}"
        )
    lock = legacy.parse_lock(lock_name, data)
    history = load_history()
    release = history.release_for(lock.revision)
    if lock.host not in release.hosts:
        raise cli.AdoptionError(
            f"the lock records host {lock.host}, which {release.version} did not support; "
            f"{legacy.UNCHANGED}"
        )
    plan = MigrationPlan(
        root,
        "preview",
        cli.template_version(),
        ref,
        from_version=release.version,
        from_revision=lock.revision,
        snapshot=release.snapshot,
    )
    builder = _Builder(plan, reader, release, lock)
    builder.identity({item.revision for item in history.releases}, state)
    # Read only to refuse an unsupported profile; it is never written or invented.
    cli.profile_check(cli.check_path(root, PROFILE))
    reader.read(PROFILE)
    configs = hosts_config.host_configs(
        reader, lock, release.version, builder.parts, builder.current
    )
    hosts = [config.host for config in configs]
    if "claude" in hosts:
        builder.claude_local_check()
    policy, copies, working = cli._policy_candidates(root, ref, lock.adr_mode)
    builder.working = working
    retired = builder.retire_old_state(state, hosts)
    builder.placement = update_skill_placement(hosts, lock.host)
    cli._check_discovery(root, lock.host, skip=frozenset(retired), allowed=builder.placement)
    candidates = builder.host_targets(configs, policy, working)
    builder.managed_targets(candidates, copies)
    builder.pyproject()
    builder.finish()
    return plan


def migrate(project: Path, *, apply: bool, fingerprint: str | None, ref: str) -> dict:
    """Preview the migration, or apply it when ``fingerprint`` matches the plan."""
    if apply and (fingerprint is None or not FINGERPRINT.fullmatch(fingerprint)):
        raise cli.AdoptionError(
            "--apply needs --fingerprint with the 64-hex fingerprint of a reviewed preview"
        )
    plan = plan_migration(project, ref)
    if not apply or plan.status == "nothing to migrate":
        return plan.result()
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
            deletes=plan.deletes,
            directories=plan.directories,
            allow_legacy=True,
            saved={item["path"]: item["saved_to"] for item in plan.replaced},
        )
    except cli.RollbackIncomplete:
        raise
    except (cli.AdoptionError, OSError, ValueError) as error:
        kept = f"; the copies saved under {MIGRATED_DIRECTORY}/ were kept" if plan.replaced else ""
        raise cli.AdoptionError(
            f"migration failed and was rolled back ({error}){kept}; preview again"
        ) from error
    plan.status = "migrated"
    if left:
        plan.findings.append(
            "staged originals could not be removed: " + ", ".join(left) + "; delete "
            f"{cli.STAGING_DIRECTORY}/ by hand once nothing holds them open"
        )
    result = plan.result()
    try:
        result["post_apply_status"] = cli.status(plan.root)
    except (cli.AdoptionError, OSError, ValueError, KeyError) as error:
        # The writes succeeded; a failing status check is a finding, not a refusal.
        result["post_apply_status"] = {"status": "unavailable", "error": str(error)}
        result["findings"].append(f"post-apply status could not run: {error}")
    return result
