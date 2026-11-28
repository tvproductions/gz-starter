# Adopt the skills stack

Choose the procedure that matches the project:

| Starting point | Procedure |
| --- | --- |
| New Python product | [Greenfield](adoption-0.5.md#greenfield-start-a-new-python-product) |
| Working product with no starter adoption record | [Brownfield first adoption](adoption-0.5.md#brownfield-first-adoption-into-a-working-product) |
| Existing adopter moving to a different starter revision | [Template update](updating.md#canonical-sequence) and [brownfield upgrade](adoption-0.5.md#brownfield-upgrade-an-earlier-starter-adoption) |
| Existing setup with inherited plugin activation to repair | [Preview, apply, and verify `localize`](adoption.md#repository-owned-installation-and-brownfield-repair) |
| Existing project evaluating structure only | [Read-only backport assessment](backport.md) |

## Skills and executable tools

Skills route requests, apply project policy, and review evidence. The
`gz-starter` CLI handles repeatable inspection, configuration, and verification.
Use `uv run --locked gz-starter <command> --help` in the reviewed starter
checkout. Run `verify` from the adopter's locked environment.

| Tool | What it establishes |
| --- | --- |
| `backport --project <root>` | Top-level inventory for a migration review. |
| `configure --project <root> --host <host> --starter-ref <sha>` | Managed-file preview. `--apply` writes the reviewed configuration. |
| `status --project <root>` | Managed-file state against the matching starter release. |
| `localize --project <root> --host <host> --starter-ref <sha>` | Project activation repair preview. `--apply` writes local overrides. |
| `run-opencode --project <root> -- <args>` | A scoped OpenCode session or native discovery command. |
| `verify --project .` | Artifact and required unittest results for a supported adopter checkout. |
| `version` and `validate` | The checkout's declared template version and bundle/catalog consistency. Git and GitHub establish release identity. |

The starter owns one skill, `update-gz-template`. It guides release selection,
three-way reconciliation, and rollback while using Git, `gh`, and the helper
for executable steps. Upstream `gzs-project-setup` uses its settings helper to
record the chosen profile. `gzs-quality-gate` runs project-defined checks, and
`gzs-update-dependencies` uses the owning package and plugin tools. The adopter
owns its migration mapping, exact ADR approvals, release scope, and acceptance decision.
Record managed configuration, fresh native discovery, product checks, and
acceptance evidence in the project's existing records.

## Shared requirements

Both lanes MUST identify deployment/configuration ownership and follow the
[configuration contract](project-configuration.md) and
[application foundations](engineering/application-foundations.md). Inventory
existing formats, environment names, paths, data and automation before a reviewed
migration; preserve working settings and project authorities. Require actual
consumer and installed-preservation evidence, recording unavailable host checks.

For recurring template updates and pre-skill adopter bootstrap, use
[canonical template updates](updating.md). Version 0.6 adds one native
update skill; 0.5 and earlier adopters can bootstrap it from the published release.

The [adoption runbook](adoption-0.5.md) defines explicit lane selection and
applicable adoption/release analysis for both lanes.

Adopt the [outer/inner-loop composition](architecture.md#outer-loop-inner-loop-and-supplemental-disciplines):
starter supplies the outer loop, SP the inner development loop, and gz-skills
supplemental engineering disciplines. Preserve project authority and carry this
model into the project's linked instructions. This document guides adoption;
upstream workflows retain their owners.
For the mandatory ADR practice introduced in 0.10.0, read the
[architectural-decision policy](engineering/architectural-decisions.md) and
[policy access/reconciliation guide](adoption.md#architectural-decision-policy-access).
Bind both lanes to recognition, reuse, exact-edition approval and alignment.
Keep suitable existing decision collections and actual approval history. Select
an immutable source link, a repository-local policy copy, or both; preserve that
choice and its provenance. Helper configuration does not establish portable ADR
workflow discovery, behavioral qualification or adoption completion. Propagation
awaits reviewed released companion contributions and three-publisher evidence.

Read [the adoption guide](adoption.md) for native host loading,
compatibility checks, updates, and rollback.

For structural adoption in an existing project, read
[backport guidance](backport.md). Run the read-only assessment, map
existing sources to proposed targets, and implement only useful, authorized
changes with project verification. Configuration adoption does not move code.

Full Python baseline adoption requires the
[Astral alignment contract](engineering/astral-alignment.md). Inventory layout,
packaging, configuration and enforcement gaps, then implement necessary
refactoring within the authorized project scope. Preserve public behavior and
project authorities. Existing layout is not automatically exempt; compatibility
exceptions require evidence, an owner and revisit condition. Configuration-only
work reports the remaining migration explicitly.

Use the [Astral acceptance contract](engineering/astral-acceptance.md) to record
each requirement, actual evidence, applicability and owned exceptions in the
project's existing authority. Follow the [worked migrations](engineering/astral-migrations.md)
for application, typed-library and workspace paths. Reconcile effective uv/Ruff/ty
configuration, exact selected environments, executable provenance and clean
installed behavior before claiming full Python acceptance. File configuration
and fresh-session native discovery remain separate results.

Before choosing versions, use the adoption guide's “Getting current SP and
gz-skills” procedure. Check latest published releases, distinguish development
main from a release, and record reviewed full SHAs. The starter pins are a
baseline, not an instruction to keep SP behind because Backplane is deferred.
Allow `0.0.0` only as an unpublished bare-scaffold placeholder. As soon as any
original implementation, tests, documentation or configuration is added, set
the initial project version to **0.1.0**. Do not release project-owned work as
`0.0.0`. Correct unpublished `0.0.0` projects containing original work and align
runtime version output and release records. Verify this before accepting
adoption. Preserve existing published
versions and tags; follow the mandatory [versioning policy](versioning.md).
Also use its “Maintaining the adopted stack” procedure for the starter template,
SP, SP-BP and gz-skills at adoption and scoped maintenance. Compare recorded
provenance with upstream releases/commits, preserve app additions and overrides,
and record independent adopt/defer decisions. Track SP-BP updates without
enabling it while readiness and explicit adoption remain pending.
Generic maintenance routes to gz-skills `gzs-update-dependencies` for authorized
updates and `gzs-dependency-risk-audit` for risk assessments. Keep the starter's
role to policy and adoption bindings; do not add a competing local maintenance
skill. The pinned gz-skills maintenance skill also supports freshness-only
reviews and starter/plugin inventory without changing pins or environments.
For the starter and every adopter, apply the mandatory
[completed-migration binding](baseline-policy.md#dependency-maintenance-means-completed-migration):
a maintenance/update/upgrade/freshen request or bare `gzs-update-dependencies`
invocation completes migration to the most current stable versions, including
new families, and verification. Override older portable review-only defaults;
only explicit check/freshness/assessment/no-changes requests are read-only. Do not
stop at recommendations or an offer to apply. Preserve product requirements and
retain older versions only for demonstrated incompatibility with an owned, dated
exception. Preserve approved starter Python policy over upstream profile defaults;
choosing a profile remains explicit and separate from helper configuration, but is
required before adoption can be called complete.

Establish the exact target project and a reviewed published starter revision.
Read the starter's [versioning contract](versioning.md). Record its
declared template version and exact SHA independently of the app version;
confirm published release/tag identity separately. Legacy unversioned locks
require reviewed reconciliation, never an inferred label or silent rewrite.
Read the [project configuration contract](project-configuration.md);
inventory app dependencies, locks and settings, preserve additions and reviewed
overrides, and report freshness/adoption gaps. The helper leaves these files
untouched and does not resolve packages or load application settings.
Inspect project instructions, existing plugins and skill discovery, and gzkit
ownership. Keep app rules and existing user changes. Do not make a copy of an
upstream skill tree or install the same skill through two discovery contracts.

## Apply project configuration

Inspect both state directories before configuring an existing project. Follow
the [legacy state procedure](updating.md#relocate-legacy-starter-state) when
recognized artifacts are present under `.skills-first/`. The helper writes
current state under `.gz-starter/` starting with 0.12.1.

From the separate, reviewed starter checkout, substitute the absolute project
path and the full release commit SHA you verified. Use `codex`, `claude`, or
`opencode` for the project's host.

```sh
project_root=/absolute/path/to/product
starter_ref=FULL_STARTER_SHA
starter_host=codex
uv run --locked gz-starter configure --project "$project_root" --host "$starter_host" --starter-ref "$starter_ref"
```

Review the preview and the [ADR policy access options](adoption.md#architectural-decision-policy-access).
Supply the same `--adr-policy link` or `--adr-policy local` option on preview
and apply when selecting an explicit mode. After the preview is reviewed:

```sh
uv run --locked gz-starter configure --project "$project_root" --host "$starter_host" --starter-ref "$starter_ref" --apply
uv run --locked gz-starter status --project "$project_root"
```

A conflict requires reconciliation of the specific source or file; do not remove
other installations or use a force overwrite to make it pass. Existing AGENTS
stays untouched: review the generated fragment and add a pointer within scope.
Profile choice is separate; do not infer lite/heavy from the components selected.

Native installation is a separate, explicit operation. Require repository/project
scope for installation, marketplace registration and enablement. Do not install
globally/at user scope or use unscoped commands that alter user defaults. Shared
native download caches do not imply user-wide activation. If the host cannot
preserve repository scope, record the limitation instead of falling back to a
global/user install. Follow only the guide for the active host and preserve
existing upstream versions. For a
configuration-only request, stop after configuration and identify installation
as pending. OpenCode v2 supports the active SP/gz-skills pair through its upstream
adapters; Backplane's OpenCode lifecycle remains deferred.
Keep installation, version updates and enablement separate. An update request
does not authorize widening activation. Codex CLI 0.166.0 `plugin add` enables
the plugin user-wide even from a project-local marketplace; do not use it as
a project update or reinstall command. Record and verify revisions, project
enablement and unchanged user defaults independently.

SP-BP is an expected addition to the target stack and is disabled by default. Preserve existing backlog/handoff practice; do not
install or activate Backplane as part of ordinary adoption. Its future activation
requires an explicit readiness review and configuration change.

Verify actual SP and gz-skills discovery in a fresh session. If Backplane is later
explicitly adopted, also verify its compatibility contract. Record exact sources and PASS/FAIL/UNKNOWN; status/configuration is not
proof of loading. GitHub authentication, a real issue preflight, and any mutation
scenario require the corresponding authorized environment. Do not operate on
production issues just to test installation. Backplane's manifest version does
not prove a published release or cross-harness readiness.

## Configure the adopter verifier

Apply this procedure in both lanes for a single-project CPython 3.14 checkout
using gzlite 0.14.0 or later. Earlier GZ Starter releases from 0.12.0 deliver
the verifier through the separate `gz-starter` distribution.
Keep workspaces and XPPython3 on their existing project-owned verification
paths. Treat native discovery, runtime-design approval, configuration and
product acceptance as separate results.

For a greenfield checkout, require project metadata, the managed exact Python
pin, a valid lock, a README when declared, and the
[supported unittest hook](engineering/verification-policy.md#bootstrap-and-implementation-verification-for-adopters).
Use a uv non-package project during preparatory work. If build metadata is
already present, set `[tool.uv] package = false` until the package is buildable.
The first source, tooling or test asset activates behavioral verification
regardless of this setting. Reconcile package metadata and its lock as soon as
the product is ready for installation and perform the installed-product checks.

From the adopter root, record the current unittest, coverage, and CI commands.
Resolve the reviewed verifier release tag to its full commit SHA with Git. Add
the extra as a dev dependency using that exact SHA:

```sh
uv add --dev "gzlite[verification] @ git+https://github.com/tvproductions/gzlite.git@FULL_RELEASE_SHA"
uv sync --locked
```

Set up the [supported unittest hook](engineering/verification-policy.md#bootstrap-and-implementation-verification-for-adopters)
before running either gate. Reuse the existing unittest hook category and
configure discovery through `[tool.gz-starter.verify]` if the project uses a
supported non-default layout. Preserve the other three routine checks and
existing coverage. Then run:

```sh
uv run --locked gzlite verify --project .
uv run --locked pre-commit run --all-files
```

Use the lock generated by uv. Record the verifier tool's immutable pin and
the adopted template's version and source separately. When CI is in scope, adapt the
[shell-only example](../src/gzlite/resources/templates/verification/verify-python.yml)
at `.github/workflows/verify-python.yml`. Authenticate before fetching private
source and prove the exact event SHA, supported runner and actual job results.
Convert simple inline wrappers to the supported direct commands. Retain other
required jobs and their existing coverage cadence.

### Migrate existing adopters from 0.9.0 or later

1. Record current starter, verifier and app versions and exact sources, lane,
   pending paths, and existing hook, CI and coverage commands. Review current
   vs. target changes and identify the rollback commit and tracked configuration
   to restore. Preview `configure` against the reviewed starter separately.
2. Apply the reviewed dev-pin and uv lock change. Replace only the old
   unconditional unittest hook with the supported entry. Retain other hooks,
   product dependencies, coverage scope/thresholds, managed Python pin and
   native settings. Verify any existing discovery layout before switching.
3. Reconcile CI, `AGENTS.md`, the generated fragment, requirements and handoffs
   together. Supersede old bootstrap instructions. Preserve earlier failed
   receipts, runtime-design approval requirements, prior skip history and
   every outstanding acceptance gap.
4. Run the direct verifier and full pre-commit gate. Review the diff, exact
   command results and the installed outcome. Use ordinary sync separately
   when authorized. If rollback is needed, restore the reviewed old hook, CI,
   instructions, tool pin and corresponding lock together and rerun its owning
   checks. Preserve existing product changes and current adoption records.

Ordinary `configure` previews or applies managed adoption configuration. Edit
the adopter's existing hook, CI, pyproject or handoff only in the reviewed
migration. A bootstrap result records verified preparatory artifacts and product
test N/A. Complete the remaining adopter checks before claiming acceptance.
