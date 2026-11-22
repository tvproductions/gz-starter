---
id: ADR-0005
title: Own lite management records in the starter
revision: 1
state:
decision_date:
revision_date: 2026-11-22
approved_by:
approved_revision:
approval_ref:
---

# Own lite management records in the starter — proposal, edition 1

## Scope and context

GZ Starter needs to deliver the six named records selected in the
[November 14 design discussion](../../handoffs/2026-11-14-opinionated-cli-design-discussion.md#six-separate-management-artifacts).
The current release requires a release-scope record in the adopter's existing
authority. New lite adopters do not receive the selected files. Existing
adopters may already have Markdown documents, issues and approval evidence
that need a reviewed mapping.

The maintainer chose structured JSON sidecars, narrative and generated
Markdown, and a hand-written changelog. This edition proposes the executable
ownership and persistence boundary for that choice. Apply
[ADR-0001](../../decisions/ADR-0001-001-qualify-exact-component-combinations.md)
to any claimed companion compatibility. Backplane owns its native lifecycle
and semantic contract. The starter owns its local file representation and
installed development tooling. The first release needs usable lite records
with Backplane disabled.

## Alternatives

1. Give each of the five structured artifacts one JSON sidecar. Group the
   sidecars under the starter's existing adopter state directory. Each
   record type has a clear owning file and an independently reviewable diff.
   Cross-references still require validation against the whole candidate.
2. Use one JSON document with five collections. This reduces the number of
   coordinated sidecar writes but concentrates unrelated edits in one
   document and weakens the correspondence between owners and files.
3. Require the current Backplane native issue workflow as the authority for
   the six local views. This requires Backplane and a native issue target to
   use the lite records, which would prevent independent lite adoption.

## Proposed decision and rationale

Choose one versioned JSON sidecar per structured artifact under
`.gz-starter/records/`. Keep the following Markdown files at the project
root, with separate ownership for each category.

| File | Authority represented |
| --- | --- |
| `REQUIREMENTS.md` | Governing requirements and acceptance criteria |
| `BACKLOG.md` | Work identity, criteria, relationships, priority and lifecycle |
| `ROADMAP.md` | Capability progression, milestones and deferrals |
| `WORK.md` | Selected execution, blockers, evidence and continuation |
| `RELEASES.md` | Published baseline, selected scope, classification, acceptance and publication |
| `CHANGELOG.md` | Hand-written change history |

The sidecars own structured facts and stable references. Each of the first
five Markdown files owns human narrative and reserves a delimited generated
section for the corresponding view. `CHANGELOG.md` has no sidecar or
generated section. A change to structured facts goes through the sidecar
owner. An edited generated section requires explicit reconciliation before
replacement. Original narrative and unrelated bytes survive regeneration.

Use installed `gz-starter` development tooling for initial creation,
validation and regeneration. Use the project's existing explicit lane
selection. An absent or pending selection may be previewed but cannot
authorize record creation. Preserve the selected profile schema. Existing
records require a reviewed mapping and an explicit apply operation. Import
only the approved facts and references, and preserve existing authorities
until the reviewed transfer is verified.

Before a coordinated write, validate candidate schemas and references,
capture expected starting and candidate bytes under owned local transaction
state, and check for competing writes before replacement. On interruption,
verify that every affected path still has its starting or candidate identity
before completing or restoring the recorded write. Stop on unexplained
changes and report the affected paths. This permits recovery using ordinary
files and Git history. The transaction record is temporary recovery state.

## Consequences

- Starter-specific file names, schemas and commands apply to adopters under
  this contract. Consumers of standalone Backplane retain their own records.
- The feature design must specify versioned schemas, view boundaries,
  references, conflicts, recovery and the installed CLI entry points.
  This edition selects the ownership model and on-disk boundaries.
- The typed commit contract and lite-to-heavy transfer remain
  [tracked obligations](../../../ROADMAP.md#lite-management-records-and-follow-through)
  with distinct acceptance gates. This edition does not activate commit
  enforcement or change remote issue state.

## Confirmation

Verify a fresh lite adopter gets the six artifacts and five sidecars through
the installed entry point. Verify a brownfield adopter can preview and apply a
reviewed mapping and rerun without churn. Test malformed records, unresolved
references, independently edited views, write interruption and competing
edits. Confirm the changelog and narrative are preserved and that lite
operations leave Backplane and remote issue state undisturbed.

## Approval evidence

Pending separate explicit approval of ADR-0005 edition 1. Preserve the exact
reviewed proposal and the maintainer's response before recording it as Current.

## Amendment history

Edition 1, November 22, 2026. Initial proposal for the local lite records
ownership and persistence boundary.
