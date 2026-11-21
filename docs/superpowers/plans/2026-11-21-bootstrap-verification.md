# Bootstrap Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal.** Let a Python adopter save preparatory work through real checks, then
require its meaningful unittest suite through the same hook when authored assets
appear.

**Architecture.** Add `gz-starter verify --project <root>` to the starter's
installed development tooling. Validate the adopter's metadata and executable
verification contract, inventory its actual files, and run unittest with
adopter-owned collection and result accounting. Test the producer, installed
distribution and adopter workflow at their own boundaries.

**Tech stack.** Managed CPython 3.14, uv, unittest, pre-commit, and explicitly
declared PyYAML in the verification extra. GitHub Actions orchestration uses Bash
and PowerShell and direct `gh`, `git` and uv commands.

**Spec.** [Bootstrap verifier design edition 3](../specs/2026-11-21-bootstrap-verification-design-edition-3.md).
The [approval record](../../decisions/ADR-0003-001-own-bootstrap-verification-in-the-starter.md#approval-evidence)
identifies the approved design bytes and ADR-0003 edition 1.

## Global constraints

- Governing [0.12.0 scope](../../../ROADMAP.md#selected-correction--pre-implementation-verification-november-17-2026)
  advances published `v0.11.6` at `6a44715f5fc40048c9767497a313a279dfc3a12a`.
  Reconcile `bundle.json`, `pyproject.toml`, `uv.lock`, packaged bundle and
  unreleased changelog together. Keep component pins and both catalogs aligned.
- Use uv `>=0.13.5`; the supported workflow example pins uv `0.13.9`, managed
  CPython `3.14.10`, `macos-15` ARM64 and `windows-2025` x64. Keep exact Python
  and locked commands. XPPython3 `3.12.x` and uv workspaces retain their owning
  checks and are outside this verifier's initial support.
- Keep the base helper standard-library-only, current configure semantics,
  native activation scope and all four producer hooks. Use invented fixtures.
  Existing adopter coverage, lane, native settings, provenance, requirements,
  failed evidence and runtime-design approval retain their authority.
- Never derive applicability from a stage switch, ignored files, `package =
  false`, placeholder assertions, skipped hooks or exit-code suppression.
  Use public CLI negatives with a reached fault. Keep Git operations direct
  and use `uv run --locked python` for substantive project Python.
- Run the actual installed path on both operating systems before release
  acceptance. Record unavailable platform cases as UNKNOWN. Git sync,
  candidate fixture publication and release publication have separate authority.

## File boundaries

| Files | Responsibility |
| --- | --- |
| `src/skills_first_starter/cli.py`, `verification.py` | Public command dispatch, validation order, reporting and exit status. Load verification dependencies only for `verify`. |
| `src/skills_first_starter/verification_inventory.py` | Filesystem and Git mode inventory, authored triggers, supported path rules and test candidate paths. |
| `src/skills_first_starter/verification_yaml.py`, `src/skills_first_starter/resources/templates/verification/verify-python.yml` | Parse hook/workflow YAML safely and validate the supported recipe against the bundled runnable workflow. |
| `src/skills_first_starter/verification_unittest.py` | Resolve discovery selection; collect adopter-owned modules; account for real unittest success and preserve diagnostics. |
| `tests/test_verification.py`, `tests/test_verification_unittest.py` | Public CLI state transition and artifact negatives, plus selector/result regressions. |
| `tools/verify_distribution.py`, `pyproject.toml`, `uv.lock`, `.github/workflows/check.yml` | Declare and exercise the extra, qualify base and extra installs, and run the existing producer gate with the extra selected. |
| `docs/engineering/{verification-policy,python,astral-migrations}.md`, `docs/{adoption-workflow,adoption,updating}.md`, `templates/AGENTS.skills-first.md`, canonical update skill | Bind the adopted behavior and migration through the existing authorities. Generate wheel copies using the current resource tool. |

## Review focus

- Root packages may start with `[tool.uv] package = false`; adding a source
  file to that state must fail through the unchanged hook until tests exist.
- An invalid link can sit at a name normally excluded from inventory. Check
  file kind before pruning `.venv` or a cache; address Windows junctions.
- Nested `load_tests` may return cases owned by a different local module.
  Attribute the cases correctly and detect an omitted sibling.
- A working hook may become ineligible through stage, filters or an overridden
  CI step. A direct verification invocation must catch those changes.
- A valid adopter may already have a failing coverage gate or an unsupported
  workspace. Preserve its current command and show its actual result.

## Task 1 — Validate the preparatory checkout through the public command

**Files.** `cli.py`, `verification.py`, `verification_inventory.py`,
`verification_yaml.py`, the bundled `verify-python.yml`, `pyproject.toml`,
`uv.lock`, producer workflow, and `tests/test_verification.py`.

**Interfaces.** `verification.verify_project(root: Path) -> int` is the command
boundary. `verification_inventory.inventory_project(root: Path) -> ProjectInventory`
returns verified relative files, authored triggers and candidate test paths.
`verification_yaml.validate_hook(data: bytes) -> None` and
`verification_yaml.validate_workflow(data: bytes, python_pin: str, uv_floor: str) -> None`
validate present contracts without running workflow content. Report input errors
from `verify_project` to stderr and exit `1`. Let argparse retain exit `2` for
invalid command syntax.

- [x] Add public CLI tests in `VerificationCliTests` that assert bootstrap status
  includes paths and `not applicable: pre-implementation`. The fixture has a
  real uv lock, exact `.python-version`, canonical hook, README and optional
  canonical workflow. Create the lock via direct uv before invoking verify.
- [x] Add artifact negatives for missing or stale lock without rewriting it,
  broken declared README/local Markdown target, malformed JSON/TOML/YAML,
  quoted or plain `on` in the good workflow, duplicate keys, merge/alias/tag
  rejection, wrong workflow shell/order/required arguments, and suppression by
  `if`, filters or `continue-on-error`. Remove, duplicate, stage-gate and
  filter the `unittest` hook and require direct-command exit `1` for each.
- [x] Add first-source negatives for ignored and untracked files outside `src/`,
  extensionless shebang or recorded Git executable mode, `package = false`,
  extension-based tools, and authored logic in an additional workflow. Assert
  the triggering path appears and no bootstrap success appears. Assert workspace
  input fails without installing anything or rewriting its owning checks.
- [x] Add path cases for unreadable input, symlinked source, symlinked cache or
  managed-environment lookalike, and a junction on Windows. Assert paths to the
  starter's two exact skill aliases and Git plain-file equivalents are allowed
  and other forms fail. Exercise the inventory of the actual producer checkout
  as implementation-bearing; keep its existing producer tests applicable. An
  invented secret-store fixture should prove verification inventories only the
  path and never reads its bytes or displays them in diagnostics.
- [x] Run `uv run --locked python -m unittest discover -s tests -p
  'test_verification.py' -v`. Confirm an assertion-level failure on the missing
  public command before adding the entry point.
- [x] Add the optional `verification = ["pyyaml==6.0.4"]` extra and refresh the
  owning lock. Select `--extra verification` in the producer's exact sync and
  local qualification setup. Keep `[project].dependencies = []`. Implement
  the CLI, inventory and YAML validation. Keep the workflow recipe from the
  approved design under packaged resources as the implementation reference.
  Compare parsed structural fields and complete run bodies. Allow only the
  design's presentation/version/digest variation. Validate authority files
  before emitting bootstrap success; run `uv lock --check` in the target.
- [x] Rerun the public CLI suite with `uv run --locked --extra verification
  python -m unittest discover -s tests -p 'test_verification.py' -v`. Confirm
  the positive bootstrap and all Task 1 controls pass. Leave implementation
  inputs requiring the suite wired by Task 2, with failure in the interim.

## Task 2 — Require discovered, successful adopter tests

**Files.** `verification.py`, `verification_inventory.py`,
`verification_unittest.py`, `tests/test_verification.py`, and
`tests/test_verification_unittest.py`.

**Interfaces.** `verification_unittest.run_adopter_tests(root: Path, selection:
DiscoverySelection, candidates: Collection[Path]) -> int`. `DiscoverySelection`
holds the documented `start`, `pattern` and `top_level`. Candidate paths are
checkout-relative. Check loaded origins against the actual checkout. Preserve
unittest's diagnostics and state which inventoried modules were omitted.

- [x] Add `test_unchanged_hook_moves_from_bootstrap_to_owned_suite`. Use a real
  pre-commit hook to pass on locked docs/config, reject first source with no
  tests, fail on a reached bad assertion, and pass when the owning assertion
  succeeds. Assert hook bytes stayed identical and reject any bootstrap result
  after adding the first source file.
- [x] Add `test_passing_sibling_does_not_mask_omitted_module` and cases for custom
  pattern/path selection outside scope, empty modules, empty `load_tests`,
  a package-only aggregator with inventoried local children, and a test suite
  returned entirely from an installed package. Assert affected module paths
  or the ownership error and the source of a passing local case.
- [x] Add `test_only_successful_adopter_cases_count` and reached-fault cases.
  Require exit `1` for all skips, skipped subtest only, expected-failure only,
  unexpected success, an assertion, syntax or import error, or a failing
  `load_tests`. Assert original failure details survive. Include a successful
  case using subtests and an existing coverage fixture that remains red when
  the standalone verifier passes. Pin coverage in the fixture's own dev lock
  and run the fixture's existing coverage command separately at its regular
  cadence.
- [x] Run `uv run --locked --extra verification python -m unittest discover
  -s tests -p 'test_verification*.py' -v`. Confirm the good implementation and
  aggregator fail without the new behavior and the missing-test case stays red.
- [x] Implement selection validation in `[tool.gz-starter.verify]`, module
  inventory/discovery accounting and standard unittest result instrumentation.
  Run the suite with the managed project interpreter and preserve the caller
  working directory, module path and environment scope. Report counts only
  from the observed runner. Maintain duplicate CI invocations and coverage.
- [x] Rerun the Task 2 command and verify the full lifecycle and negative
  controls. Apply `gzs-cross-platform-python` to subprocesses, path resolution,
  Windows reparse points, failure delivery and environment handling.

## Task 3 — Deliver and prove the installed adopter contract

**Files.** Worked migration and Python policy docs, adopter fragment and its
packaged copy, canonical update skill, the bundled workflow and distribution
verifier. Use the roadmap and handoff for ongoing results.

- [x] Extend `tools/verify_distribution.py` with separate clean base and
  `verification` installs. Assert wheel metadata names the extra and parser,
  base configure still works without PyYAML, the wheel contains the workflow
  and excludes producer tests, and verify works from an adopter checkout after
  source-independent install. Use invented bootstrap, missing tests and healthy
  reached behavior. Run the distribution check before final packaging changes
  and confirm a missing acceptance deliverable fails when exercised.
- [x] Add the exact `uv add --dev` immutable Git-source example, lock update,
  `package = false` preparatory case, canonical hook and bundled CI example to
  project guidance. Explain return codes, optional CI, same-hook transition,
  direct CI verification, actual test relevance and existing coverage. Keep
  workspaces and XPPython3 on their explicit paths.
- [x] Document v0.9.0 and later migration preview, preservation and rollback.
  Retain private repo authentication, exact event SHA, pending runtime-design
  approval, prior failed evidence, manual reconciliation of stale requirements
  and handoffs, and current dependency/lane/native state. Keep ordinary
  configure behavior idempotent. Assert in the installed fixture that its
  original hook, CI, pyproject, handoff and adoption/source data survive.
- [x] Generate wheel mirrors with `uv run --locked python
  tools/package_resources.py` and run the same command with `--check`. Verify
  version parity through `uv run --locked gz-starter version` and the lock
  entry. Exercise both host catalogs with `uv run --locked gz-starter validate`.
- [x] Run `uv sync --locked --all-groups --extra verification`, `uv run --locked
  pre-commit run --all-files`, `uv build --no-sources` and `uv run --locked
  python tools/verify_distribution.py`. Check installed output from outside the
  source tree. Run scoped Ruff C901/Lizard and required release checks at the
  applicable checkpoint. Keep cognitive measurement UNKNOWN under its standing
  deferral. Review the complete diff and run `gzs-intent-audit` at the installed
  adopter entry point.

## Task 4 — Run the actual macOS and Windows acceptance

Local macOS installed-wheel behavior is recorded in the
[handoff](../../handoffs/2026-11-17-bootstrap-verification-handoff.md#installed-verifier-intent-audit).
The hosted run and Windows evidence remain open for an accessible exact
candidate SHA and authorized private adopter fixture.

- [ ] Bind the invented qualification adopter to the candidate's full Git SHA
  and record its dev lock and installed version. Use an authorized private
  fixture repository for credentialed CI evidence. Capture GitHub run links
  with `gh run view`/`gh run watch`; identify actual runner OS and architecture,
  expected and checked-out event SHAs, and uv/Python versions. A missing event
  SHA must exit before any gate runs. Keep credentials out of evidence.
- [ ] On macOS ARM64 use `bash`; on Windows x64 use `pwsh`. On each run the
  approved workflow steps, `uv sync --locked`, the direct `uv run --locked
  gz-starter verify --project .`, and `uv run --locked pre-commit run
  --all-files`. Exercise the unchanged hook across valid bootstrap, first
  source with missing tests, a reached failure and a reached passing owning
  case. Run the omitted-module, skips-only, and pre-existing coverage-failure
  controls on both platforms. Assert real exit states and diagnostics.
- [ ] Record exact candidate test results and all pending evidence in the
  bootstrap handoff and release scope. Keep unavailable runner/credential or
  candidate-source results UNKNOWN. Before a release decision, verify exact
  candidate freshness, installed evidence and affected consumer gates. Obtain
  separate authorization for Git sync or release publication when needed.

## Plan audit

The audit compares [approved intent](../specs/2026-11-21-bootstrap-verification-design-edition-3.md),
the [selected roadmap scope](../../../ROADMAP.md#selected-correction--pre-implementation-verification-november-17-2026),
and the tasks above. Line references below identify the approved spec.

| Intent to release scope | Result |
| --- | --- |
| Spec lines 28–46 and 71–100 require a valid preparatory save, automatic test applicability and separate producer/adopter proof. Roadmap includes all three obligations. | Aligned |
| Spec lines 102–289 and ADR-0003 own the installed command, optional extra and shell-only supported CI. Roadmap includes the development interface and migration. | Aligned |
| Spec lines 376–454 require reviewed migration, old evidence preservation and installed execution on both platforms. Roadmap includes migration and acceptance without broadening runtime, native or workspace scope. | Aligned |

| Release scope to execution plan | Result |
| --- | --- |
| Preparatory artifacts, mandatory automatic transition, exact hook/CI contract and no false-green test exit map to the public cases, inventory and runner in [Task 1](#task-1--validate-the-preparatory-checkout-through-the-public-command) and [Task 2](#task-2--require-discovered-successful-adopter-tests). | Aligned |
| Independently pinned dev extra, unchanged configure and existing-adopter migration map to base/extra installation, preservation controls and refreshed guidance in [Task 3](#task-3--deliver-and-prove-the-installed-adopter-contract). | Aligned |
| Candidate-specific macOS and Windows behavior, private checkout and known failure controls map to executable commands and captured evidence in [Task 4](#task-4--run-the-actual-macos-and-windows-acceptance). | Aligned |
| Published baseline, target and generated mirrors map to Global constraints and Task 3 closeout. Hosted fixture execution remains subject to an authorized fixture and available runners. | Aligned |

**PASS for plan alignment.** No missing or drifted requirements found. The
remaining platform access and exact candidate evidence are execution dependencies.
