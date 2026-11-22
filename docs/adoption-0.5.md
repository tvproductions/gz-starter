# Adopt or migrate to the Python baseline

This runbook covers new projects, existing Python projects and earlier starter
adopters. Start with the [adoption workflow](adoption-workflow.md) for path
selection and the command reference. The helper's `configured` result describes
managed files. The project records acceptance after product and native checks.

For recurring updates, see [the canonical update method](updating.md). The
0.6 release extends the managed set with
`.agents/skills/update-gz-template/SKILL.md`. Include that candidate in three-way
upgrade review and rollback when adopting a released version that supplies it.
Published 0.5.0 itself is unchanged and has no native update skill.

| Starting point | Path | What must survive |
| --- | --- | --- |
| Empty/new Python product | Greenfield below | Product identity, selected lane and intended public contract |
| Working Python product without this starter | Brownfield first adoption | Behavior, data, dependencies, source intent, instructions and history |
| Product already recording an older starter | Brownfield upgrade | All of the above plus prior provenance, reviewed local additions and rollback |
| Generated GitHub-template repository | Greenfield or brownfield according to actual product state | Product identity; use a separate starter checkout, not the copied helper's app HEAD |

## Shared requirements in both lanes

Both lanes follow the mandatory
[architectural-decision policy](engineering/architectural-decisions.md).
Follow the [policy-access guide](adoption.md#architectural-decision-policy-access)
for explicit link/local selection, provenance and three-way preservation. Include
the selected policy copy (if any), lock metadata and generated pointers in
upgrade review/rollback. Preserve existing ADR conventions/history and actual
approvals; do not infer approval from delivery or bulk-migrate collections.
Configuration-only work reports missing procedure/discovery/behavioral evidence.
Adopter propagation remains gated on the released qualified combination and
actual internal use in all three publishers, not this pending implementation.

The baseline policy requires latest stable tooling across
families and a fresh official-source review at adoption and before release.
Older ranges are not freshness exemptions. Keep exact pins after verification;
required stale/unknown evidence blocks acceptance. Explicit Python/host family
policy and evidenced conditional exceptions remain visible. The current
complexipy qualification defect cannot be treated as a passing cognitive check.
Apply the [starter-wide cognitive qualification deferral](engineering/cognitive-integration.md#starter-wide-qualification-deferral):
record DEFERRED / measurement UNKNOWN, retain ceiling 15 and eventual
qualification, and permit progression despite missing shared-engine delivery
alone. No separate adopter waiver is needed. Report conditional acceptance,
never strict cognitive or full strict conformance; other requirements remain.
For the starter and every adopter, [dependency maintenance](baseline-policy.md#dependency-maintenance-means-completed-migration)
requires completing the most current stable migration across newer tool/dependency
families and verification. Bare `gzs-update-dependencies` uses update mode here,
overriding its portable review-only default. Only explicit check, freshness,
assessment or no-changes requests remain read-only; a review or offer to apply
does not complete maintenance. Preserve product contracts and Python N-1/host
policy; retained older versions require demonstrated, owned and dated exceptions.

Explicitly choose `lite` or `heavy` with the pinned `gzs-project-setup` workflow.
Keep its two-field `.gz-skills/settings.json` schema; do not add starter policy
fields there. Missing settings or `profile: null` means lane selection is pending.
The starter helper preserves a valid explicit choice and does not make it for you.

Both lanes require the same applicable Python/Astral foundation and analysis.
Reconcile a project-owned release-scope record under the
[release-planning rule](versioning.md#plan-releases-from-their-governing-work):
PRDs guide majors, selected work/requirements drive minors, and fixes drive
patches. Record the published baseline, proposed version, governing work,
completed/remaining/deferred scope, compatibility impact and acceptance gates
in the existing planning authority. Require this at adoption and release
preparation; a version string or copied starter policy is insufficient.
Execute the [required decision procedure](versioning.md#required-version-decision-procedure)
at requirements intake, planning and closeout. Verify the concrete release target,
governing work and aligned version mirrors; unresolved required evidence blocks
those completion claims. Do not defer version decisions to publication.
Both version their own public contract using SemVer and require a newly written
PRD for every major, including 1.0.0. Refer to
[Backplane's mode definitions](https://github.com/tvproductions/superpowers-backplane/blob/main/docs/superpowers-backplane/modes.md)
for the lite/heavy workflow distinction; the template owns policy, not those
lifecycles. Do not silently promote a lite adopter. The starter currently
enables SP and gz-skills in either lane; installed components do not select a mode.

Heavy's intended stack remains SP + Backplane + gz-skills. Backplane is under
development, pinned and disabled. Preserve existing project planning/release
authorities until it is ready and explicitly activated. A heavy selection is
valid intent, but whole-stack readiness remains pending while Backplane is
deferred. Python acceptance can be measured independently of that readiness.

All applicable [Astral acceptance](engineering/astral-acceptance.md) rows need
observed evidence. N/A needs a reason based on an absent triggering feature.
Required FAIL, UNKNOWN or stale evidence blocks strict acceptance. Record
accepted compatibility exceptions as conditional/nonconforming, never 100%
conformance. Do not use existing structure as an exception by itself.

## Obtain and verify the released starter

Check the canonical published releases and select a reviewed tag. Use a separate
checkout. The example below uses v0.12.0, the first release with the adopter
verifier. Run these commands from the parent of the new checkout:

```bash
gh release view --repo tvproductions/gz-starter
git clone --branch v0.12.0 https://github.com/tvproductions/gz-starter.git reviewed-starter
cd reviewed-starter
git rev-parse HEAD
git rev-parse 'v0.12.0^{commit}'
git status --short
gh release view v0.12.0 --repo tvproductions/gz-starter
uv --version
uv run --locked gz-starter version
uv run --locked gz-starter validate
```

The two SHAs must match and the checkout must be clean. Review the GitHub release,
changelog, and [versioning contract](versioning.md). Confirm that `version`
reports the selected tag's version and save the full SHA. Check the selected
release's minimum uv requirement in `pyproject.toml`. A failed release lookup
leaves latest-release status unknown.

This starter's Python/tool pins are its tested execution environment, not an
evergreen freshness certificate for a new adopter. Verify latest stable patches
within the [approved families](baseline-policy.md) before selecting the target
product's exact pins. Do not change families or refresh unrelated dependencies
merely to configure the stack. Use the scoped upstream maintenance workflow.

## Greenfield: start a new Python product

1. Establish the product root, purpose, application/library/workspace kind,
   supported environments and public API/CLI/data/configuration contract. Choose
   lite or heavy explicitly; keep its selection separate from installed readiness.
2. If no `pyproject.toml` exists, initialize with the verified uv/Python selection:
   use `uv init --app --package --build-backend uv` or
   `uv init --lib --build-backend uv`. Inspect generated `src/`, backend, entry
   points and typing data. If a reviewed template already supplied pyproject,
   reconcile that metadata and product identity directly; do not delete it just
   to run init. Inspect parent workspace discovery before initialization.
   Workspace/native/namespace variants follow their actual documented triggers.
3. Reconcile the [Python engineering policy](engineering/python.md): exact Python
   pin, supported family, uv_build for pure Python, centralized configuration,
   dependency groups and uv-generated lock, strict Ruff/ty, unittest and the four
   routine pre-commit checks matching CI. Commit product-owned metadata and lock.
   The helper does not generate this engineering baseline for you.
4. Follow [project configuration](adoption-workflow.md#apply-project-configuration).
   The target directory must exist. New locks record the published starter
   version and SHA. Add the reviewed fragment pointer to any existing `AGENTS.md`.
5. Follow [native installation](adoption.md) for the active host. Load and invoke
   the pinned setup workflow to record the chosen lane if not yet recorded.
   Verify exact loaded SP/gz-skills sources in a fresh session. Do not copy
   upstream skill trees or activate Backplane to make readiness appear complete.
6. [Wire the adopter verifier](adoption-workflow.md#configure-the-adopter-verifier)
   for single-project CPython 3.14, or exercise the project-owned workspace or
   XPPython3 gates. Complete the acceptance/release record below. Use the
   [worked migrations](engineering/astral-migrations.md) for executable application,
   typed-library and workspace proofs. Even a new project needs effective tool
   configuration, exact environments, source-independent artifacts and clean
   installed behavior; generated files alone do not establish acceptance.

## Brownfield: first adoption into a working product

| Existing state | Initialization decision |
| --- | --- |
| Code/requirements files, no pyproject | Init can create metadata/scaffolding after inventory; migrate existing code/dependencies explicitly afterward |
| Existing pyproject, including tool-only configuration | Skip init; preserve and reconcile metadata, layout and dependencies directly |
| Existing uv-managed project | Skip init; assess/reconcile the actual baseline and acceptance evidence |

uv init is an initializer, not a code/dependency migration command. It refuses an
existing pyproject; do not remove that authority to make initialization succeed.
The same required target baseline and acceptance apply to all three cases.

1. Inspect the target's instructions, Git revision/dirty state, public behavior,
   data boundaries, existing runtime/tooling/CI, dependencies and source overrides,
   native plugins, profile and project-owned operational skills. A `.gzkit/`
   project stays in that ecosystem. Preserve unrelated work; establish a Git
   branch/rollback point without discarding dirty files.
2. From the separate released starter, run the bounded read-only assessment:

   ```bash
   uv run --locked gz-starter backport --project /absolute/path/to/product
   ```

   This lists top-level responsibilities, not an exhaustive source audit. Read
   the actual code and make a migration mapping in the existing project backlog:
   requirement, current state, intended change, owner, behavior check and rollback.
3. Choose a lane and assess all A01–A18 rows. Retain original dependency intent,
   extras/groups/markers, source precedence, commands and persisted formats.
   Map flat imports to installed `src/` packaging where needed. Preserve public
   behavior through meaningful unittest checks before and after each slice.
4. [Preview, apply, and check project configuration](adoption-workflow.md#apply-project-configuration).
   Resolve specific conflicts and link the fragment from existing AGENTS.
   Follow the [selected host procedure](adoption.md#repository-owned-installation-and-brownfield-repair).
   Use `localize` when inherited activation needs repair. Record the explicit
   lane through `gzs-project-setup` if still pending.
5. Migrate in verified slices: packaging/imports; metadata/dependencies/lock;
   effective uv/Ruff/ty configuration; local/hooks/CI; artifacts; applicable
   workspace/host/deployment boundaries. Record migration pending until required
   proof is complete. For single-project CPython 3.14,
   [wire and run the adopter verifier](adoption-workflow.md#configure-the-adopter-verifier).
   Keep workspace and XPPython3 verification with the owning project commands.
6. Complete the acceptance/release record and fresh-session verification.
   Existing released history stays intact. A preexisting 1.x product needs a
   new PRD for its next major, not an invented retrospective PRD for its past 1.0.

## Brownfield: upgrade an earlier starter adoption

When updating to 0.12.1 or later, follow the
[state relocation procedure](updating.md#relocate-legacy-starter-state) for
known files under `.skills-first/` before treating the project as unconfigured.

Do not run `configure --apply` expecting an in-place upgrade. The helper refuses
different managed records and fragments; even `status` can report that conflict
when invoked from a newer starter. This is a preservation boundary, not migration.

1. Save the current adoption lock, the selected host's project configuration,
   `AGENTS.skills-first.md`, AGENTS pointer and `.gz-skills/settings.json`, together
   with app metadata/lock and the original Git rollback reference. Read the old
   starter version/SHA; unknown/legacy provenance stays unknown until investigated.
   Retain local additions and review their original rationale.
2. Compare the old and target published starters through [the template update procedure](updating.md#canonical-sequence).
   Review intervening changelogs for policy, pin, and managed-file changes.
   Pre-0.3 skill copies follow [their dedicated migration](migration-0.3.md).
3. Generate target candidates in an empty disposable directory, from the clean
   target release checkout. Set `starter_host` and `starter_ref` as in
   [project configuration](adoption-workflow.md#apply-project-configuration),
   and use the reviewed `--adr-policy` mode (shown with `link`):

   ```bash
   candidate_dir=$(mktemp -d)
   uv run --locked gz-starter configure --project "$candidate_dir" --host "$starter_host" --starter-ref "$starter_ref" --adr-policy link --apply
   ```

   Retain the printed directory for review. Use its lock, fragment, and managed
   host configuration as target candidates. Keep the product's existing AGENTS.
4. Perform a three-way review: original starter-managed content, current product
   content, and target candidates. Merge only the starter marketplace/source and
   activation settings for the selected host and preserve unrelated settings and comments.
   Reconcile target provenance and component records in the lock, and merge the
   new fragment with reviewed local guidance. Keep profile selection intact;
   pending selection must be completed through upstream setup. Inspect the
   complete product diff before saving it as a reviewed migration commit.
5. Keep the old provenance in the rollback history. The new lock records the
   actual target version and full SHA after
   its managed content is reconciled. If intentional fragment edits remain,
   document them: the helper will continue reporting a managed-content conflict,
   rather than certifying the edited fragment. Do not erase edits merely to get
   a clean helper result.
6. Run preview/status again. A clean exact-baseline reconciliation should be a
   no-op. Review unresolved conflicts, verify the host's selected sources and
   fresh-session discovery, and run the adopter gates. When introducing the
   verifier, follow [the existing-adopter migration](adoption-workflow.md#migrate-existing-adopters-from-090-or-later)
   if applicable. Complete the evidence and migration tasks below.

## Acceptance and release record: required, not inferred

Keep the record in the product's existing review/release authority. Include:

```text
Project/revision and preserved dirty work:
Lane (lite/heavy), selection evidence and intended component stack:
Old starter version/SHA -> target published version/SHA:
Python/tool versions, verification date and supported environments:
Configuration result:
Python A01-A18 results and per-requirement evidence:
Required analysis results, scope, findings and applicability:
Native discovery result; deferred Backplane readiness:
Migration tasks remaining, owner and rollback:
Accepted exceptions (explicit conditional/nonconforming status):
Product public contract, SemVer classification and selected change bundle:
New PRD for this major (required for every major including 1.0.0):
Release eligibility and remaining gaps:
```

At adoption and release acceptance, execute applicable C901, complexipy, Lizard,
cohesion, Interrogate, Vulture, Bandit, branch/statement coverage through unittest,
Cosmic Ray, deptry, pip-audit and Import Linter under the
[Python analysis policy](engineering/python.md). Record exact scope/results and
review findings. A missing/unverified tool is UNKNOWN, not a passing inventory;
N/A needs evidence of absent applicability. Keep these explicit acceptance runs
outside the four ordinary hooks and routine CI. Existing legacy complexity
failures remain failures; preserve measurements rather than raising ceilings.

Build with `uv build --no-sources`; inspect sdist/wheel metadata/resources and
test the actual installed product outside its checkout with intended runtime
dependencies only. Workspaces need independent built-member proof. A locked
development run cannot replace runtime-distribution proof.

Before a product release, select its own version/classification, coherent bundle,
required new major PRD, change/migration notes, current affected-input evidence,
and exact candidate checks. Changed inputs invalidate affected proof. Follow
[release preparation](versioning.md#preparing-and-publishing-a-release); invoke
the installed upstream release workflow when available, within its actual scope.
Publishing still requires authorization. A release distributing guidance with
disclosed gaps is not an unqualified claim of strict baseline acceptance.

The adopter's recorded evidence and review establish acceptance. The CLI's
configuration and Python verifier results supply evidence for individual checks.
