---
id: ADR-0005
title: Own lite management records in the starter
revision: 2
state: Current
decision_date: 2026-11-22
revision_date: 2026-11-22
approved_by: "project maintainer in this conversation"
approved_revision: 2
approval_ref: "#approval-evidence"
---

# ADR-0005 edition 2 — Own lite management records in the starter

## Scope and context

Every GZ Starter lite adopter needs the same local management contract. The
[November 14 design](../handoffs/2026-11-14-opinionated-cli-design-discussion.md#six-separate-management-artifacts)
selected six named Markdown files, JSON authority for structured facts, and a
hand-written changelog. Current releases direct adopters to their existing
planning authority. Some already use GitHub Issues or project documents.
Their work, identities and evidence must survive reconciliation.

The starter owns the lite files and their installed tooling. Backplane owns
its mode definitions and native lifecycle. The local contract must work with
Backplane disabled on every supported starter host. Apply
[ADR-0001](ADR-0001-001-qualify-exact-component-combinations.md)
to claims about compatibility with an exact companion combination.

## Alternatives

1. Require canonical local records and make their sidecars authoritative for
   lite management facts. Adopters gain a consistent checkout and workflow.
   Brownfield projects need a reviewed reconciliation before acceptance.
2. Require the six local files while allowing each adopter to choose the
   authority for their structured fields. This reduces initial migration
   effort but means that the same local record can be editable, a cache or a
   pointer depending on the project.
3. Put all five structured categories in one local JSON file. This reduces
   coordinated writes but combines unrelated edits and makes individual
   artifact ownership less visible in diffs.

## Decision and rationale

Choose alternative 1 with one versioned JSON sidecar per structured artifact.
Use this layout for every GZ Starter lite adopter, including new projects and
existing projects. Keep the Markdown at the project root and the sidecars
beneath `.gz-starter/records/`. The files are project-owned and tracked in Git.

| Root Markdown file | Sidecar filename | Owns |
| --- | --- | --- |
| `REQUIREMENTS.md` | `requirements.json` | Requirement identities, governing references, constraints and acceptance criteria |
| `BACKLOG.md` | `backlog.json` | Work identity, scope, criteria, relationships, priority and lifecycle |
| `ROADMAP.md` | `roadmap.json` | Capability progression, milestones and deferrals |
| `WORK.md` | `work.json` | Selected execution, blockers, evidence and continuation |
| `RELEASES.md` | `releases.json` | Published baseline, selected release scope, classification, acceptance and publication |
| `CHANGELOG.md` | — | Hand-written change history |

The sidecar owns each structured management fact. The corresponding Markdown
file owns narrative and presents a delimited view generated from the sidecar.
Regeneration preserves narrative and unrelated bytes. An edited generated
section is a conflict that requires explicit reconciliation. Preserve an
existing changelog as the hand-written artifact.

PRDs, ADRs, actual approvals, published tags and verification evidence retain
their own authority. Sidecars link to their identities and observed revisions.
A reference to a GitHub issue or another document may supply intake, history or
evidence. It does not substitute for the local record or supply a second
editable owner for that record's lifecycle, priority, or release membership.
Existing issue IDs, links, comments and history remain intact.

Use the existing explicit lite selection and installed `gz-starter`
development tooling. The selection authorizes using the lite layout and
does not itself establish adoption acceptance. A new project can preview
the canonical files and explicitly apply their creation. A brownfield
project previews the mapping from existing sources, including open work,
relationships, requirement and evidence references, and release scope.
The adopter reviews the intended authority transfer before apply. After
apply, verify the records and their views and identify the transferred
fields' new owners in the old planning authority. Preserve old records and
their history. An unresolved mapping or competing active owner leaves lite
adoption pending.

Allow one starter-managed record write at a time in the owning checkout.
Before replacement, validate the entire candidate, capture the expected
starting and candidate bytes, and check write preconditions. Use temporary,
untracked recovery state distinct from the tracked management records.
Recover an interrupted transaction only after verifying that every affected
path still has its recorded starting or candidate identity. Stop and report
independent edits, unexpected links or unexplained state. Never overwrite
those paths as part of automatic recovery.

## Consequences

- Every completed lite adoption supplies all six files, five sidecars and
  one local owner per governed fact. The contract applies through the same
  starter entry points on supported hosts.
- The feature design defines exact schemas, generated section markers,
  field references, migration steps, installed commands and the recovery
  protocol. These details must enforce the same layout and ownership.
- The typed commit records and lite-to-heavy transfer remain tracked in the
  [roadmap](../../ROADMAP.md#lite-management-records-and-follow-through).
  Their enforcement and transfer mechanisms need separately reviewed designs.

## Confirmation

Verify a fresh lite adoption creates the exact eleven paths through the
installed entry point and verify a clean Git checkout retains them. Prove
brownfield reconciliation using a project with active GitHub work and
existing narrative. Verify the old issues and history are preserved, the
local owners are explicit, and a competing owner blocks acceptance.
Exercise missing files, malformed records, broken references, edited views,
repeated application, simultaneous writers and interrupted writes with an
independent edit. Confirm the hand-written changelog survives.

## Approval evidence

Source is the project maintainer conversation on November 22, 2026. This is
an agent transcription. The agent asked for explicit approval of ADR-0005
edition 2 and linked that exact proposal. The maintainer replied verbatim:

> approve adr-0005

Edition 2 was the only edition presented for approval. The
[reviewed proposal](approvals/ADR-0005-002-reviewed.txt) preserves the exact
proposal bytes with SHA-256
`e3abf2f2bb5590021729a0074ea0f460cc94305eb447e1ae4743bfa3a61f7d7a`.
The maintainer's response approves the architectural decision.

## Amendment history

- [Edition 1](../superpowers/specs/ADR-0005-001-own-lite-management-records-in-the-starter.md),
  November 22, 2026. Initial proposal, SHA-256
  `2e6191d04659a3e0801f66b070c47711a6561ba75d3a518fb8b919b9a4b4808d`.
- Edition 2, November 22, 2026. Proposed after the maintainer called for
  a uniform starter contract and approved in the response above. During
  administrative capture, the agent recorded Current metadata, relocated
  the working ADR, fixed its links and updated the headings. The reviewed
  decision and constraints are unchanged. The feature design remains under
  review.
