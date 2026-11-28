"""``gzlite freshen``: bring a gzlite adopter to the running release (spec 5.0).

Freshen has three parts. Managed files (host configuration, lock, fragment,
update skill, ADR policy copy) move to this release under the drift rule;
component pins move to this release's bundle with no exceptions; doctrine
conformance that no managed file can fix is reported as findings, each citing
its source, and is never written.

The embedded history ends before gzlite, so a gzlite-era revision is usually
not in it. A gzlite-owned file is therefore judged "save unless proven
untouched": it is unchanged when it equals this release's target; it is
replaced without a copy when it equals what the recorded revision's snapshot
wrote (if the history has it) or this release's template rendered with the
recorded revision; otherwise it is saved under
``.gzlite/migrated/freshen-<12 hex of the recorded revision>/`` first. Text is
compared with line endings normalized. The lock is generated state: when it
changes, the old lock is kept as a record.

Every configured host is freshened, not only the lock's. Preview is the
default; ``--apply`` writes only when the recomputed fingerprint matches.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from gzlite import cli
from gzlite import migrate_hosts as hosts_config
from gzlite import migrate_legacy as legacy
from gzlite.drift import CARRIED_HOST, EDITED, RECORD, DriftBuilder, Plan
from gzlite.fingerprint import fingerprint as compute_fingerprint
from gzlite.history import Release, load_history
from gzlite.migrate import FINGERPRINT, FRAGMENT, PROFILE
from gzlite.native import update_skill_path, update_skill_placement
from gzlite.native_identity import STARTER_SOURCES, marketplace_name
from gzlite.paths import BUNDLE_LOCK, MIGRATED_DIRECTORY, STATE_DIRECTORY, validate_state_directory

# The source cited by findings that are not doctrine (carried keys, host notes).
SPEC = "docs/superpowers/specs/2026-11-27-gzlite-rename-and-tool-split-design.md"
SOURCES = frozenset(STARTER_SOURCES)
# A catalog name no configuration uses: passed as the name to keep, it makes
# every starter catalog retire, including this release's own name when its
# entries were written for another revision.
RETIRE_ALL = ""
WORKFLOW = ".github/workflows/verify-python.yml"


@dataclass(frozen=True)
class Doctrine:
    """One doctrine check: where it ``applies`` and the project does not ``hold`` it."""

    applies: Callable[[Path], bool]
    holds: Callable[[Path], bool]
    finding: str
    source: str


DOCTRINE = (
    Doctrine(
        applies=lambda root: (root / "pyproject.toml").is_file(),
        holds=lambda root: (root / WORKFLOW).is_file(),
        finding=(
            f"pyproject.toml makes this a Python project, but {WORKFLOW} is missing; add "
            "gzlite's shell-only verification workflow "
            "(gzlite/resources/templates/verification/verify-python.yml) and the "
            "gzlite[verification] dev dependency so gzlite verify runs in CI"
        ),
        source="docs/decisions/ADR-0003-001-own-bootstrap-verification-in-the-starter.md",
    ),
)


@dataclass
class FreshenPlan(Plan):
    """Everything one freshen would change, and why."""

    from_version: str = ""
    from_revision: str = ""
    hosts: list[str] = field(default_factory=list)
    doctrine: list[dict[str, str]] = field(default_factory=list)

    def all_findings(self) -> list[dict[str, str]]:
        notes = [{"finding": text, "source": SPEC} for text in self.findings]
        notes += [
            {"finding": f"{item} is the project's own and is carried unchanged", "source": SPEC}
            for item in self.carried
        ]
        return notes + self.doctrine

    def changes(self) -> list[dict[str, str]]:
        return [{"path": n, "action": "write", "reason": self.reasons[n]} for n in self.writes]

    def fingerprinted(self) -> dict:
        """The plan as the fingerprint sees it: every change, payloads by hash."""
        return {
            "from": [self.from_version, self.from_revision],
            "to": [self.to_version, self.to_revision],
            "hosts": self.hosts,
            "writes": [
                [name, hashlib.sha256(payload.encode()).hexdigest()]
                for name, payload in self.writes.items()
            ],
            "replaced": self.replaced,
            "findings": self.all_findings(),
        }

    def result(self) -> dict:
        return {
            "status": self.status,
            "from_version": self.from_version,
            "from_revision": self.from_revision,
            "to_version": self.to_version,
            "hosts": self.hosts,
            "writes": self.changes(),
            "replaced": self.replaced,
            "findings": self.all_findings(),
            "next": self.next,
            "fingerprint": self.fingerprint,
        }


class _Builder(DriftBuilder[FreshenPlan]):
    """Accumulate the freshen plan; the methods run in order."""

    record_label = "recorded state file"

    def __init__(
        self,
        plan: FreshenPlan,
        reader: legacy.Reader,
        lock: legacy.LegacyLock,
        release: Release | None,
        recorded_fragment: str,
    ) -> None:
        super().__init__(
            plan,
            reader,
            lock,
            saves_under=f"{MIGRATED_DIRECTORY}/freshen-{lock.revision[:12]}",
            recorded_version=lock.version,
            recorded_marketplace=marketplace_name(lock.version),
        )
        self.proofs: dict[str, list[str]] = {FRAGMENT: [recorded_fragment]}
        if release is not None:
            # The recorded revision's own snapshot, rendered with that revision.
            self.proofs[FRAGMENT].append(
                legacy.release_fragment(release, lock.revision, lock.adr_mode)
            )
            for name in (update_skill_path("codex"), update_skill_path("claude")):
                template = legacy.skill_template(release, name)
                if template is not None:
                    self.proofs[name] = [template]
            adr = legacy.adr_copy_template(release, STATE_DIRECTORY, lock.adr_mode)
            if adr is not None:
                self.proofs[cli.ADR_POLICY_DESTINATION] = [adr]

    def untouched(self, name: str, existing: str, payload: str) -> bool:
        text = legacy.normalized(existing)
        candidates = [payload, *self.proofs.get(name, ())]
        return any(text == legacy.normalized(proof) for proof in candidates)

    def host_reason(self) -> str:
        if self.recorded_marketplace != self.current:
            return super().host_reason()
        to = self.plan.to_version
        return f"gzlite {to} points {self.current} at {self.plan.to_revision} with the {to} bundle"

    def pins(self) -> None:
        old = {part["name"]: part["revision"] for part in self.lock.components}
        new = {part["name"]: part["revision"] for part in self.parts}
        moved = [
            f"{name} {old.get(name, 'unpinned')} -> {new.get(name, 'removed')}"
            for name in sorted(set(old) | set(new))
            if old.get(name) != new.get(name)
        ]
        if moved:
            self.plan.findings.append(
                f"component pins move to the gzlite {self.plan.to_version} bundle: "
                + "; ".join(moved)
                + f"; the old lock is saved under {self.saves_under}/"
            )

    def managed_targets(self, candidates: dict[str, str], copies: dict[str, str]) -> None:
        to, ref = self.plan.to_version, self.plan.to_revision
        payload = candidates[BUNDLE_LOCK]
        existing = self.reader.text(BUNDLE_LOCK) or ""
        if legacy.normalized(existing) != legacy.normalized(payload):
            self.save(BUNDLE_LOCK, existing, why=RECORD)
            self.pins()
        self.target(
            BUNDLE_LOCK,
            payload,
            f"gzlite {to} records gzlite {to} at {ref}, the {to} component pins and the "
            "carried lock keys",
            replaceable=True,
        )
        self.plan.carried += [f"lock key {key}" for key in self.lock.extras]
        self.owned(FRAGMENT, candidates[FRAGMENT], f"gzlite {to} fragment at {ref}")
        self.update_skills()
        if "AGENTS.md" in candidates:
            self.target(
                "AGENTS.md",
                candidates["AGENTS.md"],
                "AGENTS.md is missing; configure writes the default pointer to the fragment",
            )
        for name, text in copies.items():
            self.owned(name, text, f"gzlite {to} local ADR policy copy")

    def finish(self) -> None:
        plan = self.plan
        candidates = {
            name: payload
            for name, payload in {**self.saved, **self.targets}.items()
            if not self.unchanged(name, payload)
        }
        paths = {name: cli.check_path(self.root, name) for name in candidates}
        plan.writes, plan.before, _ = cli._plan_writes(paths, candidates, self.replaceable)
        plan.inputs = dict(self.reader.inputs)
        to = plan.to_version
        if not plan.writes:
            plan.status = "current"
            plan.next.append(
                f"Nothing to freshen: every managed file and pin matches gzlite {to} at "
                f"{plan.to_revision}."
            )
        else:
            if any(item["why"] == EDITED for item in plan.replaced):
                plan.next.append(
                    f"Review each file saved under {self.saves_under}/; carry any wanted "
                    "local edits into project-owned files, then delete the copies."
                )
            plan.next.append(
                "Start a fresh agent session and confirm gzl-update and the bundle plugins "
                "are discovered; runtime readiness is unverified."
            )
        if plan.doctrine:
            plan.next.append(
                "Work the doctrine findings with Superpowers; each cites its source, and "
                "freshen never fixes them."
            )
        if plan.writes:
            plan.fingerprint = compute_fingerprint(plan.inputs, plan.fingerprinted())

    def unchanged(self, name: str, payload: str) -> bool:
        """A file whose text already equals ``payload`` apart from line endings."""
        existing = self.reader.read(name)
        if existing is None:
            return False
        return legacy.normalized(legacy.decode(name, existing)) == legacy.normalized(payload)


def _doctrine(root: Path) -> list[dict[str, str]]:
    return [
        {"finding": check.finding, "source": check.source}
        for check in DOCTRINE
        if check.applies(root) and not check.holds(root)
    ]


def plan_freshen(project: Path, ref: str) -> FreshenPlan:
    """Read the adopter and plan the whole freshen, refusing what cannot be read safely."""
    cli.validate_bundle()
    if not cli.SHA.fullmatch(ref):
        raise cli.AdoptionError(
            "use a reviewed, published full gzlite commit SHA; moving branches are not pins"
        )
    root = cli._adoption_root(project)
    # Refuses legacy state (naming gzlite migrate) and staged leftovers.
    validate_state_directory(root)
    reader = legacy.Reader(root)
    data = reader.read(BUNDLE_LOCK)
    if data is None:
        raise cli.AdoptionError(
            f"no gzlite adoption: {BUNDLE_LOCK} is missing; adopt with gzlite configure; "
            f"{legacy.UNCHANGED}"
        )
    lock = legacy.parse_lock(BUNDLE_LOCK, data, SOURCES)
    history = load_history()
    release = history.release_for(lock.revision) if lock.revision in history.revisions else None
    plan = FreshenPlan(
        root,
        "preview",
        cli.template_version(),
        ref,
        from_version=lock.version,
        from_revision=lock.revision,
    )
    plan.findings += lock.notes
    mode = lock.adr_mode
    policy, copies, working = cli._policy_candidates(root, ref, mode, check_recorded=False)
    _, _, recorded = cli._policy_candidates(root, lock.revision, mode, check_recorded=False)
    builder = _Builder(plan, reader, lock, release, cli.render_fragment(lock.revision, recorded))
    # Read only to refuse an unsupported profile; it is never written or invented.
    cli.profile_check(cli.check_path(root, PROFILE))
    reader.read(PROFILE)
    kept = builder.current if lock.revision == ref else RETIRE_ALL
    configs = hosts_config.host_configs(reader, lock, lock.version, builder.parts, kept)
    plan.hosts = [config.host for config in configs]
    if "claude" in plan.hosts:
        builder.claude_local_check()
    builder.placement = update_skill_placement(plan.hosts, lock.host)
    cli._check_discovery(root, lock.host, allowed=builder.placement)
    candidates = builder.host_targets(configs, policy, working)
    # Hosts are reported in ``hosts``; ``carried`` keeps only project-owned entries.
    listed = {CARRIED_HOST.format(host=c.host, path=c.path) for c in configs}
    plan.carried = [item for item in plan.carried if item not in listed]
    builder.managed_targets(candidates, copies)
    plan.doctrine = _doctrine(root)
    builder.finish()
    return plan


def freshen(project: Path, *, apply: bool, fingerprint: str | None, ref: str) -> dict:
    """Preview the freshen, or apply it when ``fingerprint`` matches the plan."""
    if apply and (fingerprint is None or not FINGERPRINT.fullmatch(fingerprint)):
        raise cli.AdoptionError(
            "--apply needs --fingerprint with the 64-hex fingerprint of a reviewed preview"
        )
    plan = plan_freshen(project, ref)
    if not apply or plan.status == "current":
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
            saved={item["path"]: item["saved_to"] for item in plan.replaced},
        )
    except cli.RollbackIncomplete:
        raise
    except (cli.AdoptionError, OSError, ValueError) as error:
        kept = "; the saved copies were kept" if plan.replaced else ""
        raise cli.AdoptionError(
            f"freshen failed and was rolled back ({error}){kept}; preview again"
        ) from error
    plan.status = "freshened"
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
        result["findings"].append(
            {"finding": f"post-apply status could not run: {error}", "source": SPEC}
        )
    return result
