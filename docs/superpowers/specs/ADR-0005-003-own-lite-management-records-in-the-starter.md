---
id: ADR-0005
title: Own lite management records in the starter
revision: 3
state:
decision_date:
revision_date: 2026-11-22
approved_by:
approved_revision:
approval_ref:
---

# ADR-0005 edition 3 — Own lite management records in the starter

## Scope and context

Every GZ Starter lite adopter needs a common management record contract.
[Edition 2](../../decisions/ADR-0005-002-own-lite-management-records-in-the-starter.md)
establishes six Git-tracked Markdown files, five authoritative JSON sidecars
and a hand-written changelog. The maintainer directed structured changelog
entries and asked to continue the decision in ADR-0005. This proposed edition
brings the changelog into the same contract. Edition 2 remains current until
the maintainer separately approves this edition.

The starter owns lite file layout and tooling. Backplane owns its mode and
native lifecycle. The local workflow must work with Backplane disabled. Use
[ADR-0001](../../decisions/ADR-0001-001-qualify-exact-component-combinations.md)
for claims about the exact companion combination.

## Alternatives

1. Keep five sidecars and enforce changelog structure through a Markdown
   convention. This minimizes migration and leaves structured entry identities
   and references dependent on parsing prose.
2. Use six sidecars and generate the changelog like the other views. One
   typed record format per document gives people and agents the same editing
   and validation contract.
3. Keep change entries on their GitHub issues and assemble the changelog
   from GitHub. This puts the entries next to work discussions and requires
   a second source for projects or changes without an issue.

## Proposed decision

Choose alternative 2. Use six Git-tracked Markdown files at the project
root and six corresponding, versioned JSON sidecars in
`.gz-starter/records/`:

| Markdown | Sidecar | Structured facts |
| --- | --- | --- |
| `REQUIREMENTS.md` | `requirements.json` | Requirement identities, governing references, constraints and criteria |
| `BACKLOG.md` | `backlog.json` | Work identity, scope, criteria, relationships, priority and lifecycle |
| `ROADMAP.md` | `roadmap.json` | Capability progression, milestones and deferrals |
| `WORK.md` | `work.json` | Selected execution, blockers, evidence and continuation |
| `RELEASES.md` | `releases.json` | Baseline, selected scope, classification, acceptance and publication |
| `CHANGELOG.md` | `changelog.json` | Categorized user-facing change entries and their work, evidence and release references |

A sidecar holds the current collection for its document. Its entries are
the editable source for structured facts. The corresponding Markdown owns
narrative and has a delimited generated view. Preserve surrounding bytes
and stop on edited generated content. Git preserves earlier committed
states. PRDs, ADRs, approvals, tags and verification evidence retain their
own authority.

Each changelog entry has a stable identity, a category from a controlled
set, a user-facing summary and typed references to the work or evidence
behind it where applicable. A release reference ties a versioned entry to
the release sidecar. Generate the changelog with reproducible grouping and
ordering. Use the release sidecar's version and publication facts for
grouping. Agents and people follow the same validation and Git review.
The adopter verifies that the summary accurately describes the change
through the project's existing review process.

A GitHub issue can show a single related entry in a named Issue Artifact
with the entry ID and a commit-pinned source reference. An issue can also
relate to several entries. Keep the issue's native identity separate from
the local entry ID. An Artifact is an issue-level view. Qualify the
Artifact workflow before making it an acceptance gate.

## Adoption and recovery

Keep explicit lite selection. New projects preview and apply the required
files. Existing projects review a mapping from their current authorities
against exact source revisions and can inspect the installed files before
cutover. Keep the old authority active until the transfer is verified.
Retain issue identities, links and history, and record where the old
authority was retired for each transferred fact. A competing owner or
unresolved mapping leaves adoption pending.

Keep a byte-exact, retrievable copy of any prior changelog. Preserve the
visible published history. Reconcile existing unreleased entries during
review so each appears once in the active view after cutover. Conversion of
published entries requires a reviewed mapping that retains wording and
release grouping.

Allow one starter writer per checkout. Validate the full candidate and
capture starting and candidate identities and bytes before writes. Keep
recovery material local and untracked. Recover only from recognized
states. If a path is unsafe or contains an independent edit, preserve it
and report the conflict.

## Confirmation

From an installed fresh lite checkout, verify all twelve paths are tracked
and survive a clean checkout. Verify changelog entry identity, category,
references, release grouping, generated output and changed-view detection.
In a brownfield fixture, verify that old changelog history remains visible,
unreleased entries appear once, and authority transfer has one active
owner per fact. Include the changelog in interrupted-write recovery and
repeat-render checks. If the feature scope includes GitHub Artifact
qualification, verify that an invented issue exposes a related entry and
can retrieve the previous artifact version with its original source reference.

## Related feature work

The [lite records feature design](2026-11-22-lite-records-adoption-design.md)
owns exact schemas, command behavior, walkthroughs and the acceptance matrix.
The [roadmap](../../../ROADMAP.md#lite-management-records-and-follow-through)
owns delivery scope. Typed commit records and lite-to-heavy transfer
remain separate deliverables with their own completion evidence.

## Review of the edition decision

On November 22, the maintainer directed keeping this change within the
existing lite ownership ADR and asked for a check against published ADR
practice. Nygard's original format preserves reversed decisions and links
their replacements. Fowler and AWS describe an append-only approach in
which a new ADR supersedes the accepted one when the decision changes.
[Nygard](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
· [Fowler](https://martinfowler.com/bliki/ArchitectureDecisionRecord.html)
· [AWS](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html)

UK Government Digital Service guidance allows a reviewed update to an
accepted ADR when its decision was never implemented. It recommends a new
ADR where implementation has already begun. The maintainer agreed in this
review to keep the cohesive lite ownership decision together and asked to
record the evidence and rationale. This review direction leaves approval of
the exact edition open.
[GDS implementation guidance](https://gds-way.digital.cabinet-office.gov.uk/standards/architecture-decisions.html#implementation)

Evidence checked in the canonical starter checkout at
`a7af3fbebf5998206c8cb3a92fdee2f08235e88f`, the commit that recorded edition
2. There are no commits after that checkpoint in this checkout and no
changes from published `v0.12.1` to source, tests, tools or package and
bundle metadata. Searches for the planned records commands and format in
source, tests and tools found no implementation. The installed
`gz-starter --help` did not list a `records` command. These checks cover
this checkout and its published baseline.

The changelog change answers the same ownership and persistence question
as the other five records. In this case the decision is still in design, so
a new edition gives it one coherent contract while preserving what edition 2
actually approved. This follows the maintainer's direction for ADR-0005.
The general [ADR policy](../../engineering/architectural-decisions.md#preserve-history-and-independent-evolution)
still requires a new identity for material replacements. Edition 2's
[approved text](../../decisions/approvals/ADR-0005-002-reviewed.txt) and
[approval evidence](../../decisions/ADR-0005-002-own-lite-management-records-in-the-starter.md#approval-evidence)
remain intact.

## Amendment history

- [Edition 1](ADR-0005-001-own-lite-management-records-in-the-starter.md)
  was the initial proposal.
- [Edition 2](../../decisions/ADR-0005-002-own-lite-management-records-in-the-starter.md)
  is current. Its exact approved text and approval remain on record.
- Edition 3 is the maintainer-directed review of the same lite ownership
  decision with the changelog brought into the structured layout.
