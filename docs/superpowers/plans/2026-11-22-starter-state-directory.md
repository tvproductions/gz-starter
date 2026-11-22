# Starter State Directory Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution if selected by the maintainer, or superpowers:subagent-driven-development if selected. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct starter-owned state storage to `.gz-starter/` in patch 0.12.1 and deliver safe migration instructions to both adopter lanes.

**Architecture:** Keep the existing adoption format, preservation-first configure/status contract and reviewed template-update workflow. Share canonical paths and a metadata-only legacy-state guard in the existing filesystem module; invoke it before managed state access or verifier inventory. Add no migration CLI or automatic adopter migration.

**Tech Stack:** Managed CPython 3.14.10, uv >=0.13.5 (observed 0.13.9), unittest, Ruff, ty, pre-commit and the existing optional PyYAML verifier extra.

**Spec:** [Approved directory design](../specs/2026-11-21-starter-state-directory-design.md).

## Global Constraints

- Published 0.12.0 at `7303deff043231d8bcbb789e52efdbdde6b7e2f0` → pending **0.12.1 / patch**, explicitly selected by the maintainer.
- Work on `main`; preserve the current documentation changes and normal hooks. No commits, pushes, native installations, real-adopter changes, tags or releases are authorized by this implementation request.
- `.gz-starter/` is the sole current state directory. Legacy artifacts are root-relative `.skills-first/{bundle.lock.json,architectural-decisions.md,settings.toml}`.
- Preserve local content, actual provenance, component pins, explicit profiles and project activation. Relocation alone changes no starter version/SHA.
- Empty or unrelated legacy directories are permitted; normal verifier checks still apply. Linked, dangling, unreadable or unsupported state entries fail closed without target traversal.
- Keep compatibility IDs/imports/commands, the root `AGENTS.skills-first.md` filename and native configuration/skill locations unchanged.
- Keep Python families, dependency selections, four routine hooks and coverage obligations unchanged. Run substantive Python through `uv run --locked python`.
- Exact-source actual macOS ARM64/Windows x64 qualification is required for changed verifier inputs. Missing proof blocks patch acceptance; cognitive DEFERRED / measurement UNKNOWN remains independent.

## Review Focus

- Canonical-path replacement must update failure/rollback assertions; an assertion against only the abandoned path must not hide partial writes to the new path (Task 1).
- Empty/unrelated legacy directories must remain usable, while malformed managed filenames still trigger migration refusal (Tasks 1–2).
- A dangling link or Windows junction must fail before content access or inventory, preserving both project and external data (Tasks 1–2, 4).
- A moved old-version record must remain truthful and may still conflict with newer generated content; localize must retain its recorded component pins (Tasks 1, 3).
- A verifier fixture without an adoption record must retain valid bootstrap behavior; stale state must never become bootstrap success (Tasks 2, 4).

## Task 1: Canonical helper paths and fail-closed state detection

**Files:** Modify `src/skills_first_starter/paths.py`, `src/skills_first_starter/cli.py`, existing path expectations in `tests/test_starter.py`, `tests/test_adr_policy.py`, `tests/test_native_hosts.py`, `tests/test_native_scope.py`, and `tools/verify_distribution.py`. Create `tests/test_state_directory.py`.

**Interfaces:** In `paths.py`, define string constants `STATE_DIRECTORY`, `BUNDLE_LOCK`, `LOCAL_ADR_POLICY` and `STATE_SETTINGS` with the four canonical paths in the spec. Add `validate_state_directory(root: Path) -> None`, raising `ValueError` with the affected path and migration/conflict reason. It inspects root/managed entry metadata, performs no content reads or mutations, and has no native-manager dependency.

- [ ] Add public-helper regressions for configure preview/apply on Codex, Claude and OpenCode: expected lock/policy paths use `.gz-starter/`, no `.skills-first/` artifact is emitted, status succeeds after fresh adoption, and repeated apply has no writes and preserves bytes.
- [ ] Add matrix regressions in `test_state_directory.py` for configure/status/localize: each recognized legacy marker (including malformed content and wrong entry type) refuses before writes; dual state never chooses a winner; empty/unrelated old directories survive. Snapshot existing bytes and external sentinels. Include linked roots/markers, dangling links and a Windows-only junction control using the existing platform-test pattern.
- [ ] Run `uv run --locked python -m unittest discover -s tests -p 'test_state_directory.py' -v`; require reached assertion failures against the old implementation. Preserve that negative-control evidence before editing production code.
- [ ] Implement the shared constants/guard. Use `lstat`, standard-library stat flags and reparse-point metadata; distinguish missing entries from inaccessible ones, and reject unsafe roots before inspecting children. Invoke the guard after project-root validation in configure, status and localize, before `_policy_candidates`, lock reads or file planning. Replace their state-path literals with the constants; retain existing error exits and write/rollback semantics.
- [ ] Update existing owning tests and installed checks to the canonical path, including assertions about partial writes and rollback. Add a moved old-version/local-policy fixture: preserve old starter/version/component/source fields and edited policy bytes; require the existing configure/status conflict rather than overwriting them. Assert localize uses those recorded component revisions and leaves the lock unchanged. A separate fully reconciled target fixture must pass status/no-op checks.
- [ ] Run the new suite and `uv run --locked python -m unittest discover -s tests -p 'test_starter.py' -v`, then the `test_adr_policy.py`, `test_native_hosts.py`, `test_native_scope.py` and `test_path_contract.py` modules with the same discovery command. Require zero failures, with unavailable platform controls explicitly skipped and still pending hosted proof.

## Task 2: Verifier state recognition without weakening bootstrap or tests

**Files:** Modify `src/skills_first_starter/verification.py`, `src/skills_first_starter/verification_artifacts.py`, and `tests/test_verification.py`.

**Interfaces:** Consume Task 1's `validate_state_directory`, `BUNDLE_LOCK` and `STATE_SETTINGS`. Keep `verify_project(project: Path) -> int` and its existing 0/1/2 CLI outcomes unchanged; no new status or metadata schema.

- [ ] Extend the existing `VerificationProject` fixture with canonical JSON/TOML acceptance and parse failures; valid bootstrap without an adoption record; legacy-only/dual-state rejection; and empty/unrelated legacy-directory preservation. An executable unrelated leftover must still trigger the existing adopter test requirement. Reuse its real locked fixture and CLI runner.
- [ ] Add a linked legacy-state control that verifies the affected path is diagnosed before traversal, plus the Windows-only state-junction equivalent. Assert no bootstrap success and unchanged fixture/external bytes on rejection.
- [ ] Run `uv run --locked python -m unittest discover -s tests -p 'test_verification.py' -v`; require the new state-recognition assertions to fail against the old verifier before production edits.
- [ ] Invoke the shared guard immediately after `_project_root`, before `inventory_project`. Update recognized JSON/TOML paths to the canonical constants; leave generic inventory, configuration validation, lock validation, unittest discovery and independent coverage behavior intact.
- [ ] Rerun the full `test_verification.py` and `test_verification_unittest.py` modules. Require the state matrix and all existing bootstrap/implementation negative controls to pass without relaxed assertions or thresholds.

## Task 3: Adopter directive, version mirrors and installed-artifact proof

**Files:** Modify `templates/AGENTS.skills-first.md`, `templates/skills/update-gz-template/SKILL.md`, current path guidance in `README.md`, `docs/adoption-workflow.md`, `docs/adoption.md`, `docs/adoption-0.5.md`, `docs/updating.md`, `docs/structure.md`, `docs/project-configuration.md`, `docs/baseline-policy.md`, `docs/architecture.md`, `docs/rename-gz-starter.md`, `docs/versioning.md`, `CHANGELOG.md`, `ROADMAP.md`, `bundle.json`, `pyproject.toml`, `tools/verify_distribution.py` and generated resource copies. Let uv own changes to `uv.lock`.

**Interfaces:** Consume the unchanged helper commands with Task 1's canonical storage and Task 2's verifier behavior. Extend installed verification with `verify_state_directory(command: Path, directory: Path) -> None`, using actual installed CLI subprocesses and disposable fixtures, without importing the checkout's implementation.

- [ ] Write the mandatory directive: store new state only in `.gz-starter/`; detect old adoption before fresh initialization; inventory/back up and review original/current/target files before moving known state; preserve unrelated leftovers; reconcile policy paths and active references; verify and retain rollback. Explain the relocation-only conflict versus a genuine released-target upgrade and distinguish verifier success from adoption acceptance.
- [ ] Make the updated template skill read the canonical record, inspect the legacy location as migration evidence when the canonical record is absent, and refuse to label a legacy adoption as first adoption. Dual state requires reconciliation; the skill must not choose or overwrite a record. It must not rewrite actual provenance merely to rename a directory.
- [ ] Update current documentation examples and the earlier active stable-directory promise. Keep historical receipts, approval bytes, old release facts and native marketplace IDs unchanged. Do not promise the unreleased 0.12.1 tag exists; keep published adoption pointers truthful.
- [ ] Set bundle/package versions to 0.12.1, record the correction in the unreleased changelog and scope authority, run `uv lock` (without `--upgrade`) to reconcile owner metadata, and regenerate with `uv run --locked python tools/package_resources.py`. Inspect semantic lock changes: only local starter metadata should differ, with package selections/edges/groups retained.
- [ ] Extend the installed seam to prove canonical configure/status/no-op behavior, selected local-policy paths, legacy and dual-state refusal with unchanged bytes, and truthful old-version relocation versus reconciled target fixtures. Run the new check from the existing isolated installed-distribution workflow.
- [ ] Run `uv run --locked pre-commit run --all-files`, `uv run --locked gz-starter validate`, `uv run --locked python tools/package_resources.py --check`, `uv build --no-sources`, and `uv run --locked python tools/verify_distribution.py`. Sync `--locked --all-groups --extra verification` first only if environment state requires it. Verify bundle/package/lock/packaged bundle/CLI version 0.12.1; run fresh changed-doc link/anchor and whitespace checks. No new behavioral tests are required for prose alone.

## Task 4: Source-bound hosted qualification and honest closeout

**Files:** Add the candidate-specific receipt `docs/evidence/2026-11-22-0.12.1-candidate-acceptance.md`; update existing roadmap and continuation records. Extend only an authorized invented private fixture's existing manual workflow; keep its locator and private content out of this public repository.

**Interfaces:** Consume the installed verifier at the exact immutable candidate SHA and Tasks 1–3's unchanged command/hook interface. Candidate publication and fixture repository operations retain their own authorization; the design approval does not grant commit/push permission.

- [ ] Complete and record all independent local implementation checks before requesting any needed candidate-push/fixture authority. Locate the existing private manual qualification workflow through its established owner; do not invent a replacement workflow or claim platform proof from producer CI.
- [ ] Once an immutable candidate and authorized fixture are available, pin that full source SHA and exercise the existing eight expected-outcome assertions on macOS ARM64 and Windows x64 with managed Python 3.14.10 and reviewed uv.
- [ ] Add fixture assertions for canonical state, relocation-only conflict with preserved old provenance, a reconciled target, legacy-only and dual-state refusal, empty/unrelated leftover preservation, and linked state including an actual Windows junction. Run direct verification and the unchanged adopter hook where applicable; capture raw expected exits, path diagnostics and preserved bytes inside the passing qualification jobs.
- [ ] Record candidate/fixture SHAs, runtime/tool provenance, run identities, actual platform outcomes and local gate evidence. If access, authorization or execution is unavailable, mark affected hosted proof UNKNOWN / pending and leave patch acceptance incomplete while retaining completed local work. Do not substitute a green historical run or the cognitive deferral.
- [ ] Review the complete diff against the approved spec and run the appropriate independent change review under the selected execution workflow. Correct in-scope findings, rerun only affected checks, reconcile completed/remaining scope and version mirrors, and report source implementation, local verification, hosted acceptance and publication separately.

## Plan audit and review status

| Intent → scope | Result |
| --- | --- |
| Canonical state, adopter directive, preserved provenance and explicit migration outcomes | Tasks 1 and 3 cover the approved behavior. |
| Legacy matrix, linked-state safety and unchanged bootstrap/test applicability | Tasks 1–2 cover each matrix row and the five review-focus conditions. |
| Installed and actual source-bound macOS/Windows proof, patch version and no incidental publication | Tasks 3–4 retain the required gates and authorization boundaries. |

| Scope → execution steps | Result |
| --- | --- |
| Public helper and verifier changes | Reached-fault tests precede production edits; focused commands follow each owner. |
| Metadata, authored guidance and resources | Owning-tool lock/resource commands and installed proof are explicit. |
| Hosted qualification and closeout | Exact inputs/results are required; unavailable authority/evidence remains pending. |

Self-review found no uncovered spec requirement or interface mismatch. The
maintainer's plan review and execution-method selection remain pending. No
implementation or acceptance is claimed by this plan.
