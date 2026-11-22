# Starter state directory correction — short design

Status: approved by the maintainer in this conversation on November 22, 2026,
with the response **“design approved”**. This is an agent transcription; no
durable conversation URL is available. No implementation has begun.
This revision addresses the three design-review gaps: migration outcomes,
legacy-state detection and affected hosted qualification.

## Intent and authority

The maintainer directed that starter-owned files stop using `.skills-first/`
and selected **`.gz-starter/`** as the replacement. The maintainer explicitly
classified this as a starter patch: published **0.12.0 → pending 0.12.1**.
The existing adoption preservation/conflict contract remains authoritative.

## Approach

Use `.gz-starter/` as the sole current state directory, and reuse the existing
reviewed template-update workflow for relocating legacy records. A name-only
replacement would miss existing adopters; automatic directory migration would
bypass review of local modifications. Add no new migration command or storage
format. This is a bounded path correction within the existing preservation-first
architecture, with no new ownership, schema, runtime service or activation choice.
No new ADR is proposed for the directory spelling and existing-workflow reuse.

## Behavior and adopter directive

1. New configure preview/apply uses `.gz-starter/bundle.lock.json` and, for
   local ADR-policy mode, `.gz-starter/architectural-decisions.md`. Record
   `adr_policy.local_path` and generated working-policy links accordingly.
2. Configure, status and localize detect the old `.skills-first/` state before
   treating a project as unconfigured or changing files. Require reviewed
   migration; preserve both locations on a conflict and never merge, overwrite,
   silently initialize a second adoption or traverse linked legacy state.
   Apply the legacy-state matrix below rather than rejecting every directory
   with the old name.
3. Direct existing adopters in both lanes to inventory and back up the old
   state, preview the move through their template update, relocate reviewed
   starter-owned content into `.gz-starter/`, reconcile local policy paths and
   instruction links, and verify the result. Preserve actual starter/component
   revisions, source hashes, local edits, profile choices and rollback. A path
   move alone does not upgrade the recorded starter version or source SHA or
   establish successful configure/status reconciliation. Follow the distinct
   relocation and upgrade outcomes below.
4. Update the verifier's recognized JSON/TOML paths and diagnose legacy state
   as requiring migration. Do not allow a legacy adoption to pass as a fresh
   bootstrap. Keep normal discovery, unittest and coverage requirements intact.
5. Carry the mandatory directory/migration directive in authored adopter
   instructions, the owned update skill and current adoption/update guidance.
   Supersede the earlier active promise that `.skills-first/` stays stable,
   while retaining historical receipts, approval bytes and published sources.
6. Keep native host configuration/skill paths, marketplace IDs, Python imports,
   compatibility command aliases and the root instruction-fragment filename
   outside this directory correction. Do not change real adopter repositories.

## Legacy-state detection and end condition

Check the two state locations at the project root. Recognized legacy artifacts
are `.skills-first/bundle.lock.json`, `.skills-first/architectural-decisions.md`
and the verifier-recognized `.skills-first/settings.toml`. A recognized name
counts even when its contents are malformed or it has an unexpected file type;
do not require successful parsing to detect legacy state.
The new TOML recognition path is `.gz-starter/settings.toml`; this does not
introduce a settings schema or make configure create that file.

Inspect entry metadata before content access. Reject symlinked state roots,
linked managed artifacts, dangling links and unsupported reparse points without
traversing their targets. Apply existing destination safety checks at the new
location too. A non-directory entry occupying either state-directory name is
an explicit conflict, never something to replace or reinterpret automatically.

| Observed state | Required helper/verifier behavior |
| --- | --- |
| No recognized legacy artifacts; no current adoption | Continue the command's ordinary checks. Configure may preview/apply fresh adoption. Verifier bootstrap still does not require an adoption lock. |
| Ordinary empty `.skills-first/` directory | Preserve it; it does not block adoption or verification. Create starter state only under `.gz-starter/`. |
| Ordinary `.skills-first/` directory containing only unrelated files | Preserve those files; absence of recognized legacy artifacts is not a migration failure. Normal verifier inventory, executable triggers and link checks still apply to them. |
| Any recognized legacy artifact, with no current managed state | Configure, status, localize and verify fail with an actionable migration diagnostic before any writes. Do not return `not configured` or verified bootstrap. |
| Recognized legacy artifacts and current managed state both present | Refuse without choosing, merging or rewriting either source, even if both lock files appear identical. Require explicit reconciliation. |
| Linked, dangling, unreadable or unsupported state entries | Fail closed with the affected path; preserve both locations and external targets. |
| Current state only, optionally with an empty or unrelated old directory | Apply existing command-specific validation and preservation rules at `.gz-starter/`; do not require removing unrelated data to obtain acceptance. |

Relocation is complete when recognized starter artifacts have moved to the
canonical directory, current references use those paths, and no recognized
legacy artifact remains at its old path. An empty or unrelated old directory
may remain. Do not delete it to manufacture completion. Capture rollback outside
both active state directories before moving anything. Inventory unknown content
and relocate it only with established ownership/authorization; do not move a
whole directory blindly or merge an existing target.

## Relocation versus a template upgrade

**Directory-only relocation:** preserve `starter.repository`, `starter.version`,
`starter.revision`, component records, selected host, ADR-policy mode and original
source path/hash. Change only the selected local policy path and affected active
instruction references needed for the move; preserve local policy/configuration
content and project adaptations. Do not stamp 0.12.1 or its SHA onto an adoption
that has not actually consumed that target. These steps are a reviewed filesystem
operation under the existing update workflow, not a new helper migration mode.

After a directory-only move, configure/status may still report a managed-content
conflict when run from the newer starter: they compare the old lock, fragment and
policy with the executing checkout's generated candidates. Report that outcome
as **relocated; template reconciliation pending**, not `configured` or completed
template adoption. This is a reporting distinction, not a new CLI status/API.
Do not suppress the conflict or replace local edits to obtain a green result.
Localize may use the canonical lock's actual component selections under its
existing activation-only contract; it must not upgrade adoption provenance.
Verifier success establishes only its artifact/test checks, not template-upgrade
acceptance.

**Actual template upgrade:** verify the released 0.12.1 tag/full SHA in a separate
checkout, generate target candidates in a disposable directory with the explicit
host and ADR-policy selection, and perform the existing original/current/target
comparison. Reconcile the relocated record, managed instructions, local policy
references, update skill and native source settings as one reviewed change.
Only then record the actual target version/SHA and any deliberately updated
component/source-policy metadata; retain the previous records in rollback.
Component installation and activation remain separate operations. Before
publication, invented fixtures may use clearly identified candidate SHAs without
claiming a released target or migrating real adopters.

An unmodified reconciled fixture must have successful status, empty repeated
configure writes and unchanged repeated-run bytes. When legitimate project
adaptations still differ from generated content, retain them and report the
existing conflict and pending reconciliation explicitly; do not claim complete
helper acceptance. Prove both the relocation-only outcome and a completed
template-upgrade outcome with legacy-version fixtures, including local policy
edits and unchanged recorded component pins.

## Completion and verification

Reconcile 0.12.1 in the bundle, package, owning-tool lock metadata, packaged
bundle and unreleased changelog after approval. Regenerate all affected wheel
resources through `tools/package_resources.py`.

Add meaningful public-seam regressions for fresh adoption on all three hosts,
preview/no-op behavior, local ADR policy, legacy-only and dual-directory refusal,
preserved bytes and no partial writes, linked destinations, status/localize and
verifier recognition. Extend installed-artifact checks to prove the new paths
and legacy preservation. Run the full applicable integration gate on managed
Python 3.14.10 with supported uv. No analyzer or dependency selection changes
are planned. Preserve cognitive DEFERRED / measurement UNKNOWN and host limits.

Because verifier inputs change, repeat the existing single manual hosted
qualification workflow as required by the
[current handoff](../../handoffs/2026-11-18-discipline-evaluation-handoff.md#0120-published-and-verified).
Pin the installed verifier to the full candidate source SHA. On actual macOS
ARM64 and Windows x64 with the exact managed Python 3.14.10 selection and reviewed
uv, replay the existing eight expected-outcome assertions and exercise canonical
state, relocation-only and upgraded fixtures, legacy-only and dual-state
rejection, empty/unrelated legacy-directory preservation, and linked state
(including Windows junctions). Exercise both the direct verifier and unchanged
adopter hook where applicable. Assert the raw expected exits/diagnostics and
preserved bytes inside the qualification jobs; expected rejections must not
become independently failed workflow runs. Record source SHA, fixture SHA,
platform/runtime, command results and the actual run identity.

Producer CI, a mocked platform or a configured workflow does not replace these
hosted results. If fixture access or execution is unavailable, record affected
qualification as UNKNOWN / pending and leave patch acceptance incomplete while
continuing independent local work. Preserve the standing cognitive deferral;
do not use generic host limits to waive this affected qualification requirement.

No commit/push, native installation, tag or release publication is implied by
this patch request. Existing published 0.12.0 remains immutable.
