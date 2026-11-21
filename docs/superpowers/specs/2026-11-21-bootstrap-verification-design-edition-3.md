# Bootstrap verification correction — design edition 3

Date: November 21, 2026. Status **Draft, awaiting design approval**.
Governing request: correct the pre-implementation verification deadlock reported
by the maintainer from GZYoke's v0.9.0 adoption. This design concerns starter
verification/adoption, not permission to implement that consumer's runtime.

## Problem and observed cause

The adoption runbook explicitly permits configuring the stack before product
initialization. Its worked hook instead runs unconditional unittest discovery.
The consumer reports documentation, metadata, locks and CI, with no runtime
package, authored Python tooling or Python test assets. The November 17 report
identifies eight unsaved paths and conflicting current instructions/handoffs.
Its native-loading and runtime-design gates remain independent.

An invented temporary checkout with only README and pyproject reproduces the
mechanism on this starter's managed Python 3.14.10:
`python -m unittest discover -v` reports `Ran 0 tests` / `NO TESTS RAN` and exits
**5**. Nothing demonstrates a failed behavioral assertion. Treating that exit
as success globally would also hide genuinely broken implementation discovery.
Portable git-sync guidance now diagnoses applicability but does not supply a
command, adopted hook or migrated instruction contract.

Private consumer reports were inspected read-only. Public fixtures MUST use
invented names/content; do not copy its private handoff or operational material.

## Intended result and boundaries

An ordinary Python implementation project MUST be able to save preparatory
work before its runtime-design approval, after real bootstrap validation.
Report product behavioral testing as **not applicable: pre-implementation**
with the observed artifact inventory and reason. Do not call it a passing
product suite, completed adoption, runtime approval or release acceptance.

Once runtime code, authored executable tooling or test assets exist, meaningful
unittest verification is mandatory. Fail on missing tests, zero discovery,
import/syntax/load failures, assertion failures and wholly skipped suites.
Preserve each project's existing coverage commands, source scope, numeric
thresholds and cadence. Nonempty discovery alone does not establish relevance
or coverage; those remain reviewed evidence and existing owning gates.

No placeholder tests, manual phase flag, allow-empty option, skipped hook,
shell exit suppression, research-only reclassification, Node tooling, product
runtime implementation, native installation or unrelated dependency migration.
Do not introduce a generic lifecycle, acceptance ledger or conformance framework.

## Approaches and proposed choice

1. **Starter-owned installed development verifier — recommended.** Extend the
   existing packaged helper with one command and test it in the starter. Adopters
   pin the verification extra as a development dependency through uv. This keeps
   verifier implementation/tests out of the adopter source tree: its own tests
   cannot accidentally stand in for the adopter's missing runtime tests.
2. **Copy a verifier and its tests into each adopter.** It runs with locked
   Python, but adds separately maintained executable copies, requires migrating
   them together, and needs special treatment to stop verifier tests masking
   missing product tests. Reject this additional ownership/distribution surface.
3. **Document a conditional shell discovery command.** It is easy to copy but
   splits platform semantics and artifact classification across hook/CI/prose;
   it leaves the already-observed drift and Windows behavior insufficiently
   tested. Reject as the supported shared implementation.

During review the maintainer answered “yes, an implementer is not accounting
for the starter's own testing.” to the proposed installed development-verifier
approach. Record that delivery direction and the producer-testing clarification;
The complete design and the separately identified ADR still need approval.
[ADR-0003 edition 1](../../decisions/ADR-0003-001-own-bootstrap-verification-in-the-starter.md)
identifies the consequential ownership/dependency choice separately.

## Starter testing and adopter testing

The starter already contains runtime implementation and a meaningful unittest
suite. Its own behavioral verification is **always applicable**. The new command
MUST NOT classify this publishing repository as pre-implementation or grant it
an empty-suite path. Its existing hooks, owning behavior tests, packaging and
installed-artifact checks remain mandatory. Add meaningful verifier regressions
before shipping the new helper, including reached-fault/discovery controls and
the starter's own implementation-present case.

Keep three obligations explicit:

1. **Producer qualification:** the starter tests the shared verifier and its
   installed distribution, with exact-source Windows/macOS evidence. An
   implementation plan MUST account for that existing suite and the new owning
   tests immediately; it cannot defer helper tests until an adopter has runtime.
2. **Adopter bootstrap validation:** run the qualified verifier against the
   adopter's actual artifacts. A no-runtime adopter may report product tests
   inapplicable while still requiring real bootstrap checks. The producer's
   passing suite is evidence about the tool, not the adopter's product or files.
3. **Adopter implementation verification:** actual product/tool/test assets
   require its own meaningful tests and preserve coverage enforcement. Installed
   starter tests do not satisfy those obligations.

Adopters may reuse producer qualification for the exact installed source/version
and supported environment; do not rerun the starter's entire suite on every
adopter commit. They MUST run checks against their own current checkout. Tool
updates, changed relevant inputs or unsupported environments require affected
requalification and honest UNKNOWNs. Neither reused producer evidence nor a
bootstrap PASS establishes runtime-design approval or complete adoption.

## Supported executable contract

Add `gz-starter verify --project <root>`. Run it in the adopter's exact managed,
locked Python environment. Its common hook entry is:

```yaml
- id: unittest
  name: unittest and bootstrap verification
  entry: uv run --locked gz-starter verify --project .
  language: system
  pass_filenames: false
  always_run: true
  stages: [pre-commit]
```

Keep the other three hook categories Ruff check, Ruff format and ty. The hook
must run on a docs-only commit and on the first commit containing source, using
the same entry in both cases. The [supported workflow](#supported-github-actions-workflow)
installs the exact managed Python, runs `uv sync --locked`, invokes the
verifier directly, and runs `uv run --locked pre-commit run --all-files`.
Pre-commit can succeed without invoking a disabled hook. The direct CI call
validates the hook even in that case. Both calls run the verifier in CI when
the hook is eligible. Preserve existing required checks
and their cadence. An existing coverage gate must still produce a failing
result on an uncovered reached behavior even when the verifier passes.

Use `uv lock --check` for the lock-consistency check. An absent or stale lock
fails without rewriting it. Return exit `0` for a valid bootstrap with product
test N/A or a successful required suite. Return `1` for invalid inputs, unsupported
inventory or test selection, or a failed required suite. Keep unittest's failure
output and discovery detail. CLI argument errors retain the existing CLI convention.

Distribute the verifier through an optional `verification` extra. Declare its
YAML parser explicitly there; use safe parsing, not regex YAML interpretation
or an undeclared transitive import. Retain the base helper's standard-library
runtime. The consumer adds an immutable reviewed released Git source for
`gz-starter[verification]` to its dev group with `uv add --dev`, then commits its
own generated lock. Do not advertise a PyPI release that has not been published,
use a moving branch, install globally, or fabricate adoption provenance. Existing
recorded template adoption and this independently pinned verification tool are
distinct until a full reviewed template migration reconciles them.

For a project that has metadata but no buildable package, use a non-package uv
project for the preparatory checkout. If packaging metadata is already present,
set `[tool.uv] package = false` expressly to defer project installation while
still installing locked development tools. Adding source under this setting
still activates behavioral tests. Reconcile the setting, packaging and lock
when the first buildable product is ready, then exercise the installed product
under its existing acceptance rules.

Initial support is the ordinary pinned CPython 3.14 project on Windows/macOS,
in either lane. This does not establish support for running the starter's 3.14
distribution inside an embedded 3.12 host. Preserve the separate host exception
and its current verification path; do not broaden compatibility metadata without
actual evidence. Workspaces retain their explicit per-owner discovery and
coverage obligations; unsupported selection/aggregation fails with a diagnostic
rather than silently using one root suite. A `[tool.uv.workspace]` declaration is
outside this command's initial single-project support. Existing workspaces keep
their owning commands and coverage/aggregation gates; migration guidance must
identify this boundary before replacing any hook.

## Supported GitHub Actions workflow

This worked adopter workflow uses ARM64 `macos-15` and x64 `windows-2025`,
with explicit shells and no `uses` steps. `GITHUB_SHA` is the expected commit
for every supported event. For `pull_request` it is GitHub's merge commit for
that event. If the exact SHA cannot be fetched, stop. Give the jobs only
`contents: read` and pass `GH_TOKEN` only to steps that call GitHub. The
credential helper applies to the fetch command and leaves the remote URL and
Git configuration free of credentials. See [GitHub event semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request)
and the [uv release assets](https://github.com/astral-sh/uv/releases/tag/0.13.9).

```yaml
name: Verify Python project
on:
  push:
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
env:
  GIT_TERMINAL_PROMPT: '0'
  SKIP: ''
  UV_VERSION: '0.13.9'
  PYTHON_VERSION: '3.14.10'
jobs:
  macos:
    runs-on: macos-15
    defaults:
      run:
        shell: bash
    steps:
      - name: Checkout event commit
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          git init .
          git remote add origin "$GITHUB_SERVER_URL/$GITHUB_REPOSITORY.git"
          git -c credential.helper= -c 'credential.helper=!gh auth git-credential' fetch --no-tags --depth=1 origin "$GITHUB_SHA"
          git checkout --detach FETCH_HEAD
          test "$(git rev-parse HEAD)" = "$GITHUB_SHA"
      - name: Provision uv
        env:
          GH_TOKEN: ${{ github.token }}
          UV_SHA256: '5aeca67f2283f75235de40d0bd9c0a5bbc5fce23b6d48b3bf9fa1b2db08382ca'
        run: |
          uv_dir=$(mktemp -d "$RUNNER_TEMP/gz-uv.XXXXXX")
          uv_archive="$uv_dir/uv-aarch64-apple-darwin.tar.gz"
          gh release download "$UV_VERSION" --repo astral-sh/uv --pattern uv-aarch64-apple-darwin.tar.gz --output "$uv_archive"
          printf '%s  %s\n' "$UV_SHA256" "$uv_archive" | shasum -a 256 -c -
          tar -xzf "$uv_archive" -C "$uv_dir"
          test -x "$uv_dir/uv-aarch64-apple-darwin/uv"
          printf '%s\n' "$uv_dir/uv-aarch64-apple-darwin" >> "$GITHUB_PATH"
      - name: Run project gate
        run: |
          uv --version
          uv python install --no-bin --no-registry "$PYTHON_VERSION"
          uv sync --locked
          uv run --locked gz-starter verify --project .
          uv run --locked pre-commit run --all-files
  windows:
    runs-on: windows-2025
    defaults:
      run:
        shell: pwsh
    steps:
      - name: Checkout event commit
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          $PSNativeCommandUseErrorActionPreference = $true
          git init .
          git remote add origin "$env:GITHUB_SERVER_URL/$env:GITHUB_REPOSITORY.git"
          git -c credential.helper= -c 'credential.helper=!gh auth git-credential' fetch --no-tags --depth=1 origin "$env:GITHUB_SHA"
          git checkout --detach FETCH_HEAD
          if ((git rev-parse HEAD) -cne $env:GITHUB_SHA) { throw 'Unexpected checkout SHA' }
      - name: Provision uv
        env:
          GH_TOKEN: ${{ github.token }}
          UV_SHA256: 'edd61f7f5728a56cc62455386661860bdfc7bab65872f39b0c25bdcc1d8e1beb'
        run: |
          $PSNativeCommandUseErrorActionPreference = $true
          $uvDir = Join-Path $env:RUNNER_TEMP ([Guid]::NewGuid().ToString())
          New-Item -ItemType Directory -Path $uvDir | Out-Null
          $uvArchive = Join-Path $uvDir 'uv-x86_64-pc-windows-msvc.zip'
          gh release download "$env:UV_VERSION" --repo astral-sh/uv --pattern uv-x86_64-pc-windows-msvc.zip --output "$uvArchive"
          if ((Get-FileHash -Algorithm SHA256 -LiteralPath $uvArchive).Hash -ine $env:UV_SHA256) { throw 'Unexpected uv archive SHA-256' }
          Expand-Archive -LiteralPath $uvArchive -DestinationPath $uvDir
          if (!(Test-Path -PathType Leaf -LiteralPath (Join-Path $uvDir 'uv.exe'))) { throw 'Missing uv.exe' }
          Add-Content -LiteralPath $env:GITHUB_PATH -Value $uvDir -Encoding utf8
      - name: Run project gate
        run: |
          $PSNativeCommandUseErrorActionPreference = $true
          uv --version
          uv python install --no-bin --no-registry "$env:PYTHON_VERSION"
          uv sync --locked
          uv run --locked gz-starter verify --project .
          uv run --locked pre-commit run --all-files
```

Validate present `.github/workflows/*.yml` and `*.yaml` as GitHub-style YAML.
Use a safe constructor with YAML 1.2 boolean semantics so the `on` key is a
string and `true`/`false` remain booleans. Reject duplicate mapping keys,
multiple documents, merge keys, aliases and custom tags in the supported
workflow and hook. A successful parse alone gives no workflow acceptance.

Use `.github/workflows/verify-python.yml` for this workflow. Validate its two
 job bodies and their checkout, provisioning and gate steps in order. Match
parsed fields and complete `run` bodies. Allow
presentation changes to `name`, YAML style, line endings and final newline.
Allow reviewed version and digest updates in the env fields. Compare
`PYTHON_VERSION` to `.python-version`; require a stable uv version meeting the
configured minimum and a 64-character hexadecimal digest per platform. Release
and maintenance evidence records where the digests came from. The runner
checks their bytes. Require one local hook with ID `unittest` and the exact
specified entry, system language, `always_run`, `pass_filenames` and stage.
Reject a missing or duplicate hook, filters on that hook or incompatible global
file filters. CI sets `SKIP` empty. Reject gate-suppressing fields such as workflow path
filters, job or step `if`, `continue-on-error`, or an alternate shell. A changed
required workflow fails with a diagnostic identifying what is unsupported.

A docs/config checkout may omit CI if none has been configured. A checkout
using this supported CI contract must include both jobs. If the project has
other workflows, they can carry additional required checks. Treat `run`,
`uses`, and job-level reusable workflow calls outside the canonical file as
tooling triggers. Edition 3 defines only the recipe above. Other workflows need
their own hosted evidence. Preserve existing required checks and verify hosted
required-check settings and the result for the exact event SHA separately.

## Artifact validation and classification

Before deciding test applicability, inspect the actual checkout, including
ignored and untracked source/test files. Use filesystem inventory independent
of the index and `.gitignore`. Exclude root Git metadata and the project's
managed root `.venv`, identified by its `pyvenv.cfg`. Skip the contents of the
standard root `.ruff_cache` and `.ty_cache` and normal `__pycache__` directories
only when their contents match their generated layout. Inspect ordinary
`build/` and `dist/` trees for authored files. Regular distribution archives
are data artifacts. Use available Git mode information as a classification
signal for discovered files on Windows. Inspect each entry's kind before pruning;
an unreadable item, unknown link, or reparse point/junction in a verification
input fails with the path. Honor the existing path policy. Recognize the
starter's `.agents/skills/update-gz-template` and `.claude/skills/update-gz-template`
as two exact documented aliases of the same in-tree skill if their recorded
relative target resolves to `templates/skills/update-gz-template`. Inspect that
target once. A portable Git materialization of either alias as a plain file
must contain exactly the same relative target. It supplies no native-discovery
evidence. Source, test and other unrecognized symlinks fail closed.

Require project metadata, the lock, the exact Python pin and the supported
hook. Validate present centralized tool configuration, native/profile/
bundle JSON/TOML and workflow YAML, the declared readme, and local Markdown
references. Run owning lock consistency validation; do not infer consistency
from TOML parse alone. Report checked paths/counts and applicable limitations,
without dumping settings contents or reading operational data/credential stores.
Absent native setup is an adoption gap, not invented proof of native readiness.

Product modules, standalone scripts, tool modules and test assets activate
behavioral requirements automatically. Recognize Python files (`.py`, `.pyw`,
`.pyi`) anywhere in scope, authored script files (`.sh`, `.bash`, `.ps1`, `.cmd`,
`.bat`), runnable shebangs, executable file mode where recorded by Git or the
filesystem, and paths named by local script/entry-point declarations. Include
an extensionless script on Windows by inspecting its shebang or declared entry,
regardless of POSIX file-mode support. A declared executable whose target is
absent or whose kind cannot be determined is a validation failure. Treat Python
subprocess wrappers, local actions and custom inline program logic outside the
supported workflow as authored tooling. Convert simple wrapper orchestration
to the supported direct-command workflow during migration. `package = false`,
an ignore rule and a stale handoff cannot override an observed trigger.

The command has two observable outcomes, neither derived from a manually chosen
stage:

- **Bootstrap PASS:** artifact checks pass and no implementation/tool/test
  trigger exists. Print the inventory and explicit product-test N/A reason.
- **Behavior required:** discover/run with the project interpreter and checked
  selection below. Report triggering paths, discovery failures, missing or
  unselected test modules and test outcomes. A passing result requires at least
  one adopter-owned success and zero runner/discovery failures.

Use `[tool.gz-starter.verify]` in the root pyproject for one optional `start`,
`pattern` and `top_level` selection. Default to `tests`, `test*.py` and unittest's
normal discovery top level. Paths must resolve inside the checkout. Inventory
candidate modules across the checkout using the conventional `test*.py`,
`*_test.py`, and the project pattern. Also include modules in the test directory
declaring local unittest cases or a `load_tests` hook. A conventional candidate
outside the selected directory or excluded by the selection still requires
accounting. Fixtures and support modules with no tests may remain under the
test directory; they still trigger behavior applicability as authored Python.

Record discovered test identities and associate them with resolved, local test
module paths. Every inventoried test module needs an adopter-owned collected
case. Allow a package initializer acting solely as a `load_tests` aggregator
when discovery invokes it and it returns a nonempty suite of cases accounted
for in that package's local modules. A package initializer defining its own
cases must also account for those cases at module level. Fail an omitted nested
module, even when a sibling passes, and fail an empty `load_tests` result.
Unsupported dynamic ownership or discovery that cannot be reconciled to
inventoried modules fails with a diagnostic. Reject a suite supplied solely by
an installed package or outside the checkout. This is module-level evidence.
Review existing assertions and preserve coverage enforcement to evaluate test
relevance.

Run standard unittest with a result that records successful owning cases and
preserves original runner diagnostics. Use the actual success event of an
adopter-owned test, including parent case semantics for subtests. A nonzero
count and `wasSuccessful()` alone can pass a suite consisting only of skips,
skipped subtests or expected failures. An unexpected success, assertion failure,
syntax/import failure or `load_tests` failure remains a gate failure.

Static inventory cannot prove test relevance. State that limit; keep coverage
requirements and review of owning assertions explicit. The installed verifier's
tests/dependencies are outside adopter inventory and cannot satisfy its suite.

## Adoption and migration deliverables

Update authoritative verification/Python policy, the generated instructions,
greenfield and brownfield runbooks, worked hook/CI examples and canonical update
guidance together. Explain conditional bootstrap acceptance, pending product
build/installed/coverage checks, and automatic transition to full requirements.
Do not alter upstream portable skills or the user's runtime-design gate.

Give existing v0.9.0 and later adopters executable instructions to:

1. Record the old template/tool sources, current diff, pending paths and rollback.
2. Add the exact reviewed verification development source and regenerate/sync
   the project lock with uv; retain all app dependencies and selected lane.
3. Replace the unconditional unittest hook with the supported entry; preserve
   the other categories and richer existing tests/coverage commands.
4. Reconcile CI with direct commands and the same entry, including private-repo
   authentication before raw git fetch. Preserve exact event-SHA checkout.
5. Reconcile stale AGENTS, generated fragment, requirements and handoffs in one
   reviewed change: supersede the deadlock, preserve historical failed receipts
   and unauthorized-skip history, explicitly retain runtime-design approval and
   other outstanding acceptance gaps. Do not infer an exception from git sync.
6. Run the real hook gate, review the result and diff, then use the separately
   authorized ordinary sync procedure. A local bootstrap PASS is not hosted CI
   success or release/adoption acceptance.

Provide preview/preservation/idempotence and installed-artifact acceptance through
the existing helper's public CLI seam. Do not silently rewrite existing adopter
hooks, CI, pyproject or handoffs during ordinary configure. An explicit migration
uses the documented reviewed changes; do not create a force-adoption path.

## Required acceptance cases

Test the new helper immediately through its public command, using invented
temporary projects and substantive negative controls. No placeholder suite.

| Case | Required observation |
| --- | --- |
| Docs/config/lock/CI only | Real artifact checks PASS; explicit behavioral N/A; no product test claimed. |
| Malformed TOML, JSON or YAML; stale lock; broken local link | Fail before applicability can produce PASS. |
| Runtime package or standalone tooling; no tests | Fail with the triggering path and missing-test reason. |
| Ignored/untracked or unconventional-location source; extensionless script on Windows | Behavioral requirements still activate. |
| New verification helper | Its own starter tests exercise validation/classification/discovery failures before shipping. |
| Starter publishing repository | Inventory identifies the implementation path including its recognized skill aliases. Run the starter's existing owning gates. The adopter verifier may reject the starter's multi-owner selection. |
| Good code with reached-behavior assertions | Actual owning suite runs and succeeds. |
| Failed assertion, syntax/import error, load_tests exception | Nonzero result and original failure diagnostics. |
| Test file with no tests, empty load_tests, wrong discovery selection | Fail, including a passing sibling masking an omitted or empty nested module. |
| Every test skipped, skipped subtest only, or expected failure only | Fail to establish a successful behavioral suite. |
| Bootstrap followed by adding implementation | Same unchanged hook automatically rejects absent tests. |
| Existing runtime coverage failure | Existing coverage gate continues to fail; no scope/threshold/cadence weakening. |
| Unittest hook removed, duplicated, stage-gated, or file-filtered | The direct CI invocation fails even when pre-commit alone would pass. |
| Valid `on`, duplicate YAML key, altered CI shell or suppression field | Accept the canonical trigger key; reject duplicate keys and gate-changing workflow mutations. |
| Package initializer `load_tests` aggregates local child tests | Account for the aggregator and child modules; fail an empty aggregate or an omitted test module. |
| Documented starter skill aliases and unexpected source symlink/junction | Accept the exact in-tree alias forms and keep behavior mandatory; reject unexpected linked inputs. |
| Unreadable/symlinked input or unsupported workspace | Fail closed; do not hide source/discovery errors. |
| Installed verifier in an adopter | Its own installed tests cannot satisfy missing adopter tests. |
| Existing local configuration/provenance | Preserve additions, lane, native settings, prior evidence and runtime approval gate. |

Before publication, pin the invented qualification adopter's development extra
to the full unpublished candidate Git SHA and commit or archive its fixture
lock. Qualify the same candidate's source-independent installed artifact.
Released adopter instructions instead identify the immutable published source.
Run the installed development extra and exact supported hook on actual macOS
ARM64 and Windows x64 with managed Python and the shell-only workflow above.
On each OS, capture a positive bootstrap and the same installed hook after
adding a source with no tests, then a reached failing assertion and a passing
suite. Run the omitted-module and skipped-only controls and preserve a failing
existing coverage gate alongside a passing verifier. Execute a private event
checkout on each hosted runner and record expected and observed SHAs; a missing
or wrong SHA must fail before tests. Capture command, version, runner OS and
architecture, source SHA, output and status, with credentials redacted. Retain
actual `gh` run links. Keep unavailable runs UNKNOWN until execution supplies
evidence. Locally, CPython 3.14.10 has reproduced empty discovery (exit 5), a
passing sibling with an omitted failing module (exit 0), and skipped-subtest-only
and expected-failure-only suites (exit 0). These probes exercise unittest.

Run the repository's full applicable gate, build from sdist without development
sources, and exercise the installed verifier including its YAML dependency.
Refresh packaged authorities and exact-candidate freshness evidence after
implementation. Retain cognitive DEFERRED / measurement UNKNOWN and all unrelated
native/embedded/platform limits.

## Release scope and approvals

Proposed published baseline **0.11.6 → 0.12.0 / minor** for the new supported
command, verification dependency and adoption interface. Published maintenance
and eval patches retain their own receipts and scope. Keep current development
metadata at 0.11.6 until planning reconciles the proposed version, lock, packaged
bundle and changelog against the accepted scope. See the
[roadmap release record](../../../ROADMAP.md#selected-correction--pre-implementation-verification-november-17-2026).

Included work is this executable bootstrap contract, tests, adopted examples,
migration and actual Windows/macOS proof.
Exclude GZYoke runtime/adopter edits, unrelated roadmap work, native activation,
companion changes and release publication. Publication and Git sync require their
own authority; no design or ADR approval authorizes them.

Before dependent implementation, obtain approval of this design edition 3 and
separate explicit approval of ADR-0003 edition 1. Then write the implementation
plan and implement with reached-fault tests. Preserve actual approval evidence;
do not label this proposal accepted based on the request to correct the defect.

[Edition 1](2026-11-17-bootstrap-verification-design-edition-1.md) preserves
the initial draft. [Edition 2](2026-11-17-bootstrap-verification-design.md)
records the maintainer's delivery direction and separates the producer,
bootstrap and adopter behavior obligations. Edition 3 specifies the workflow,
transition and suite evidence. ADR-0003 edition 1 continues to identify the
ownership and distribution decision separately.
