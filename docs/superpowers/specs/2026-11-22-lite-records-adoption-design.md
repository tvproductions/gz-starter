# Lite records adoption — feature design for review

November 22, 2026. Draft work under the
[lite records roadmap scope](../../../ROADMAP.md#lite-management-records-and-follow-through).
[ADR-0005 edition 2](../../decisions/ADR-0005-002-own-lite-management-records-in-the-starter.md)
is the approved ownership and persistence decision. The feature design
still requires its own review before implementation.

## Outcome

Every completed lite adoption has the six named Git-tracked Markdown files
and five versioned JSON sidecars from ADR-0005. The same contract applies
to every supported host. It uses the existing explicit gz-skills profile.
Existing PRDs, ADRs, approvals, tags and evidence keep their authority and
are referenced from the applicable record.

The first delivery provides creation, reviewed brownfield reconciliation,
validation and regeneration through installed development tooling. Release
classification and acceptance remain under the starter's existing policy.
The typed commit contract and lite-to-heavy transfer keep their roadmap gates.

## Entry points

| Proposed route | Behavior |
| --- | --- |
| `gz-starter records init` | Preview the required files for an explicitly selected lite project. An explicit apply creates missing files using a reviewed reconciled result. A repeated apply to a consistent project reports no writes. |
| `gz-starter records check` | Check the paths, format, record identities, references and generated views without writes. Report missing, conflicting, invalid or valid local records. Adoption acceptance also needs reviewed authority and actual Git-tracking evidence. |
| `gz-starter records render` | Preview changes derived from valid sidecars. Explicit apply refreshes generated content if the existing section can be recognized as a prior generated view. |

These are proposed command names. All address a named project root. Reuse
the starter's path and profile checks, and extend them for the nested managed
paths where necessary. Keep host configuration and record management as
explicit operations. The adoption runbook must require the records step for
lite before reporting completed adoption. Missing or null profile selection
reports pending. A selected heavy profile continues under its own workflow.

## Greenfield acceptance

1. Select lite through the existing profile procedure. Preview creation of the
   eleven canonical paths and inspect the result before apply.
2. Apply the preview. All five sidecars start with valid empty collections
   unless the project supplies reviewed initial records. The generated views
   disclose empty collections. An already existing hand-written changelog is
   preserved byte-for-byte.
3. Track the eleven files and verify them from a separate clean checkout.
   Validate the records and run the existing applicable adopter gates. Repeat
   the apply and confirm no writes. A bootstrap record does not imply a
   selected release, coverage evidence or a published version.

## Brownfield acceptance

1. Inventory existing planning authorities, relevant open work, selected
   release scope, and local Markdown. At the reviewed source revisions, map
   each governed fact to its destination record. Resolve ambiguous ownership
   and record source identities, dependencies, requirement and evidence links,
   remaining work and deferrals. Preserve existing source documents.
2. Review the intended transfer and local file changes before apply. For each
   existing Markdown file, retain narrative and existing history and add a
   generated section at the reviewed location. Keep the changelog human-owned.
   Apply the reviewed local changes only when the proposed inputs still match.
3. Verify the resulting sidecars and generated views. Follow the project's
   authorized process to mark the old authority's disposition and point to the
   new owner. The local tooling makes no GitHub updates. If the former
   authority still controls a transferred fact, acceptance remains pending.
   Any remote edit to mark the old disposition requires the project's
   existing authorization.
4. Track the records, verify from a clean checkout and record the reconciliation
   evidence in the existing adoption record. The tool can verify local facts
   and references. A reviewer verifies the authority transfer and any
   external approvals. A locally valid layout alone leaves those judgments open.

### Example

An existing issue tracks a new export format, blocks another issue and links
to an approved product requirement. The reviewed local backlog record carries
the issue's stable identity, source revision, dependency and requirement
reference. Its local status and priority live in `backlog.json`. The existing
issue and discussion remain available, with a pointer to the new owner after
authorized reconciliation. An independently approved PRD remains the authority
for the requirement, and `requirements.json` identifies the exact source.

## Consistency and recovery

Use the versioned envelope and reference proposals in the
[minimum contract draft](2026-11-14-lite-record-and-commit-contract-draft.md#common-sidecar-envelope)
as the basis for the five schema definitions. Resolve IDs across the whole
candidate. Reject duplicate keys, unsupported formats, unknown fields and
invalid references. Distinguish an unreadable evidence source from a
successful verification. Required missing evidence blocks the claim that
depends on it.

Generated sections have one delimited region per view. Store sufficient
generation identity to distinguish an edited region from a valid but stale
view. Render deterministically and preserve all bytes outside the region.
Unknown boundaries or edited generated content stop automatic replacement.

Take a single writer guard before a coordinated write. Record expected
starting and candidate bytes, including absent files. Keep recovery material
in a project-local untracked location. Validate the full candidate, constrain
all writes to canonical regular-file destinations and verify the resulting
set. A valid complete candidate can finalize. A verified mixture can restore
the recorded start. Unknown bytes or an unsafe path stop automatic recovery.
The exact manifest, generation identity and interruption protocol still need
design review and reached-fault tests.

## Release evidence

| Case | Required observation |
| --- | --- |
| Fresh installed adoption | Exact layout, tracked and present in a clean checkout, deterministic no-op on repeat |
| Brownfield transfer | Preserved content, original issue identities and references, exact local ownership, verified disposition of old authority |
| Unresolved competing authority | Adoption pending even if local files validate |
| Invalid sidecar or edited view | Precise diagnostic and no writes outside an explicitly reviewed reconciliation |
| Concurrent or interrupted write | No second starter writer, verified restoration or completion, independent changes preserved |
| Existing consumer behavior | Host configuration, profile schema, existing adopter verification, the hand-written changelog and external issue state preserved by the local tool |

Use invented repository fixtures for public tests. Verify the installed entry
point on macOS and Windows for the persistence and recovery paths. Exercise
both the normal adoption and release checks against the actual candidate and
record the result. Only released behavior and recorded acceptance close the
roadmap deliverable.
