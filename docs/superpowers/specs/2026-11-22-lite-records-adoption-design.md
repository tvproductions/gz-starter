# Lite records adoption — feature design for review

This proposed workflow implements
[ADR-0005 edition 2](../../decisions/ADR-0005-002-own-lite-management-records-in-the-starter.md)
for every lite adopter. The starter supplies the six paths, local validation
and safe regeneration. The adopter edits and commits the records, approves its
own plans and verifies its own authority transfers.

The changelog examples below describe the approved ADR-0005 edition 2
baseline. The maintainer has since requested structured changelog entries.
Review [ADR-0005 edition 3](ADR-0005-003-own-lite-management-records-in-the-starter.md)
before settling the changelog walkthrough, schema and acceptance checks.

The selected architecture uses Git-tracked JSON sidecars, generated Markdown
sections and a hand-written changelog. The ADR considered both allowing a
different structured owner per adopter and storing all structured facts in one
file. The chosen layout gives each fact a predictable owner and keeps edits to
different management areas independently reviewable.

The [roadmap](../../../ROADMAP.md#lite-management-records-and-follow-through)
reserves 0.13.0 for the skill rename over published 0.12.1 at
`a1c3550eac441b0a7beaddc66fb00c58ce0f1e6a`. This compatible feature is a
separate minor, forecast as 0.14.0 if the rename publishes first. Select the
active version and reconcile the mirrors when the release takes up this work.
Typed commit records and lite-to-heavy transfer have separate roadmap gates.
This feature design needs its own approval before implementation planning.

## Walkthrough 1 — Start a lite project

Paper Finch is an invented Python tool that exports a reading list. All Paper
Finch names, IDs (including `B-CSV`), issue numbers, approvals and release
values in the walkthroughs are fixture data. Use the same distinction in
tests and examples. GZ Starter's actual feature and release decisions belong
to its existing roadmap and approval records.

The Paper Finch maintainer selects **lite** with `gz-skills:gzs-project-setup`. That skill owns
`.gz-skills/settings.json` and records `{"schema_version":1,"profile":"lite"}`.
Host configuration follows the existing starter runbook. A missing or null
profile reports `PENDING profile selection`. Heavy follows its own workflow.
An invalid profile or a conflicting project authority such as gzkit stops the
records command with the existing setup diagnostic.

The example uses the adopter's locked development environment. The commands
and reports below describe the proposed interface.

```text
$ uv run --locked gz-starter records init --project . --namespace paper-finch --plan ../finch-records.json
CREATE  REQUIREMENTS.md  BACKLOG.md  ROADMAP.md  WORK.md  RELEASES.md  CHANGELOG.md
CREATE  .gz-starter/records/{requirements,backlog,roadmap,work,releases}.json
REVIEW  ../finch-records.json
PLAN    sha256:<full digest printed by the command>
PENDING records apply and Git verification
```

The brace list represents five separate paths. The preview writes only the
requested review file. With no seed input, all five sidecars contain empty
`records` arrays. Each rendered file starts with its title and an empty
generated view. A new changelog starts with `# Changelog` and
`## Unreleased`. The maintainer reviews the proposed local bytes and runs:

```text
$ uv run --locked gz-starter records init --project . --apply ../finch-records.json --expect-sha256 <digest>
APPLIED 11 paths
PENDING Git verification
```

An adopter can use `--seed <directory>` during preview to supply the five
complete sidecars instead. This lets a project review a populated candidate
before creation. The following table shows every nonempty record in the Paper
Finch candidate. The common namespace is `paper-finch`. References shown as
IDs expand to the two-field objects defined below. An omitted list is empty
and an omitted nullable field is null. The plan and approval in this example
are exact references to invented, already approved project files.

| Sidecar and view | What the maintainer enters | Generated Markdown excerpt |
| --- | --- | --- |
| `requirements.json` → `REQUIREMENTS.md` | `R-CSV`, title “Export a reading list as CSV”, statement “Readers can export their reading list as CSV”, authority and approval at pinned sources, constraint “UTF-8”, criterion `C-HEADER` “First row is title,author” | `- R-CSV — Export a reading list as CSV`; shows the statement, UTF-8, criterion and the PRD source |
| `backlog.json` → `BACKLOG.md` | `B-CSV`, title “CSV export”, kind `outcome`, objective “Emit a UTF-8 reading list”, in scope “Header and rows”, out of scope “CSV import”, criterion `C-ROWS` “One row per book”, coverage of `R-CSV/C-HEADER` with contribution “Writes header”, sole contribution, priority `normal`, state `active`, lifecycle evidence pointing to the execution start record | `- B-CSV — CSV export [active, normal]`; shows scope, criterion and coverage |
| `roadmap.json` → `ROADMAP.md` | `M-EXPORT`, title “Portable exports”, capability “Move reading lists between tools”, outcome `B-CSV`, forecast `V-FIRST`, deferral for “CSV import” with reason “First release is export-only” and revisit “After first-release feedback” | `- M-EXPORT — Portable exports`; shows the forecast and deferral |
| `work.json` → `WORK.md` | `W-CSV`, selects `B-CSV`; pinned plan and approval; task `T-ROWS` “Write export rows”, state `in-progress`; continuation “Run export unittest after adding rows” | `- W-CSV — B-CSV`; shows task progress and continuation |
| `releases.json` → `RELEASES.md` | `V-FIRST`, state `selected`, version `0.1.0`, baseline null, impact `minor`, rationale “First usable export”, selected outcome `B-CSV`, gate `G-EXPORT` “Verify header and rows”, verdict `UNKNOWN`, publication null | `- V-FIRST — 0.1.0 (selected)`; shows first-release scope and the outstanding gate |
| None | The maintainer writes “Add CSV export for reading lists” in `CHANGELOG.md` when ready | `- Add CSV export for reading lists` |

For example, this is `.gz-starter/records/work.json`. The two digest
strings stand in for hashes of the example's approved plan and approval.
A real seed uses the observed hashes.

```json
{
  "format": "gz-starter-records/v1",
  "artifact": "work",
  "namespace": "paper-finch",
  "records": [
    {
      "id": "W-CSV",
      "type": "execution",
      "outcome": {"namespace": "paper-finch", "id": "B-CSV"},
      "plan": {
        "locator": "docs/plans/csv.md",
        "revision": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
        "record_id": null,
        "availability": "available"
      },
      "approval": {
        "locator": "docs/plans/csv-approval.md",
        "revision": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
        "record_id": null,
        "availability": "available"
      },
      "tasks": [
        {"id": "T-ROWS", "statement": "Write export rows", "state": "in-progress"}
      ],
      "blockers": [],
      "evidence": [],
      "continuation": "Run export unittest after adding rows"
    }
  ]
}
```

After ordinary edits to the empty sidecars, the maintainer uses the render
workflow below to get the same views. The generated section of `WORK.md`
looks like this, with its SHA-256 field abbreviated:

```markdown
# Work

Pair on the first export fixture.

<!-- gz-starter:records:v1 work sha256=<64 lowercase hex digits> -->
- W-CSV — B-CSV
  - Plan and approval: [pinned source references]
  - T-ROWS — Write export rows [in-progress]
  - Continuation: Run export unittest after adding rows
<!-- /gz-starter:records:v1 work -->
```

The maintainer commits the eleven paths through their normal Git process and
runs `records check --project . --require-tracked` in a separate clean
checkout. The check reports valid records, current views and all eleven paths
tracked. Repeating init preview reports `NO CHANGES`. It creates no plan
when nothing needs writing. The existing adoption record captures these
observations with the applicable adopter gates. The outstanding release gate
remains `UNKNOWN`.

## Walkthrough 2 — Bring existing work into lite

In an alternative Paper Finch checkout, issue #12 owns CSV export scope and
priority. Issue #15 depends on #12 and tracks sharing exported files. The
approved PRD defines the CSV header. The maintainer keeps the existing heading
and discussion in `BACKLOG.md`, and uses the five populated seed sidecars and
a reviewed transfer map as preview inputs.

| Source before apply | Destination after verified transfer | Evidence and retained history |
| --- | --- | --- |
| Issue #12 scope, criteria, lifecycle and priority | `B-CSV` fields in `backlog.json` | Preserve issue ID, URL, body and discussion. The issue disposition identifies the destination and retired fields. |
| #15 and its dependency on #12 | A new `B-SHARE` backlog record whose `depends_on` includes `B-CSV` | Retain both issue identities and their historical relationship. Record dispositions for both issues if both are active authorities. |
| `docs/PRD.md`, approved CSV section | PRD remains the wording authority. `R-CSV` owns the local identity and pinned governing reference. | Keep the PRD and approval in Git. Record the exact pinned content. |
| Existing milestone scope and next-release selection | `M-EXPORT` forecasts progress in `roadmap.json`. `V-FIRST` selects members in `releases.json`. | Preserve the old planning document and milestone discussion. In the old authority identify the transferred fields and link their new owners. |
| Approved export plan and its execution checklist | Plan and approval remain governing sources. `W-CSV` owns execution progress and continuation. | Keep the approved plan and checklist history. Mark the old progress fields historical and link `W-CSV`. |
| Existing changelog | `CHANGELOG.md` remains human-owned | Keep the original bytes. |

```text
$ uv run --locked gz-starter records init --project . --namespace paper-finch --seed ../finch-seed --transfer ../finch-map.json --plan ../finch-transfer.json
MAP     issue #12 lifecycle, priority, scope, criteria -> backlog.json B-CSV
MAP     issue #15 dependency on #12 -> backlog.json B-SHARE depends_on B-CSV
KEEP    CHANGELOG.md (identical bytes)
APPEND  generated views to existing Markdown
PLAN    sha256:<full digest printed by the command>
PENDING old authority disposition and Git verification
```

Preview reports each mapped field and destination and shows current and proposed
bytes or a diff. It reports that the Markdown narrative and changelog are
preserved. The maintainer reviews the map and applies its exact plan with the
same `init --apply … --expect-sha256 …` form. If #12 gains a blocker between
preview and apply, the fresh source observation differs. The command reports
`STALE issue #12; preview again` and writes zero project paths. The maintainer
reconciles the new dependency and reviews a new plan.

A successful apply puts the required lite layout in place for inspection.
The existing authority still governs mapped facts until the reviewer verifies
the cutover. During that interval, make changes to those facts at the old
authority. If an old source changes, refresh its observation, reconcile the
staged sidecars and generated views, and review the revised mapping before
switching. The maintainer
uses the project's authorized procedure to mark transferred issue fields
historical and point to their new owner. For a local plan or milestone, the
governing heading can carry a dated supersession note with the fact names and
destination IDs. Once the reviewer verifies the dispositions and the installed
records, adopters edit the transferred facts in the sidecars.

Projects can keep using GitHub Issues for intake, discussion, and evidence.
Record issue origins and pinned observations in the sidecars and display their
links in the generated Markdown. The required lite layout applies to projects
with and without issues. Each transferred management fact has one active owner.
If issue #12 still decides priority, the adoption record stays `PENDING
competing authority: #12 priority` even when the local `records check` passes.
An unreadable issue or ambiguous source has the same pending outcome. Commit
the resulting layout and verify it in a clean checkout. The reviewer records
the reviewed map digest, exact installed tree, source revisions, observed
dispositions and remaining exceptions in the existing adoption record.
A source that never governed a fact may remain a historical reference.

### Preview and apply contract

- `init` requires `--project` and either preview arguments or the apply pair.
  Preview requires `--plan` and, on first creation, `--namespace`. All five
  seed files must be provided together if seeded. Its seed directory contains
  exactly the five named sidecars. Transfer input is required when an existing
  planning authority governs any fact. The adopter inventories those authorities
  and supplies the mapping. The tool cannot discover every planning practice.
- The transfer file contains `format: gz-starter-records-transfer/v1` and
  `mappings`. Each entry has `source` (SourceRef), `source_fields` (nonempty
  named fact list), `destination` (RecordRef), `destination_fields` (nonempty
  list of JSON Pointers relative to the resolved record), and `disposition`
  (text describing where and how the reviewer will verify retirement). Supply
  separate entries for independently retired groups. Reject duplicate source
  facts or destination fields, unresolved destinations, and conflicting
  assignments. Include all migrated fact groups, including release membership.
- A revision used to freeze a mutable local source is the SHA-256 of its
  exact bytes at a project-relative path. A Git snapshot uses a full commit
  and a path in that tree. A mutable GitHub issue uses a read-only `gh`
  observation by repository and issue number with node ID, number, URL, title,
  body, open/closed state and reason, update time, labels, milestone, project
  membership, parent, children and incoming and outgoing dependencies. Require
  these observations even when empty. Exhaust pagination and distinguish
  explicit null or empty from an error, inaccessible field or missing page.
  Include milestone identity, title, description, state, due date and observed
  membership when a milestone governs scope. A board or embedded workflow
  with governing custom fields needs its own verifiable snapshot and reviewed
  correspondence. An unreadable governing field leaves transfer pending.
  Preserve the full observation and relationship IDs in the plan, using sorted
  JSON object keys and stable identity order for unordered collections before
  hashing. Apply observes the same projection and hashes it again.
  A v1 source can be a project file, a Git snapshot or a GitHub issue observation.
  An external authority outside those inputs stays
  pending until the project can supply a verifiable supported source and
  prove its correspondence to the original.
- `init` preserves an existing changelog and all existing Markdown bytes.
  For a view without any markers it appends LF-separated generated content
  at EOF. Existing valid views follow the render rules. Refuse a partial
  sidecar set, different existing sidecar bytes from the proposed seed, or
  pre-existing edits inside a marked region. Reconcile existing sidecars
  through ordinary review, followed by render.
- Init preview produces a plan at an explicit path outside
  the managed paths and recovery storage. Open it exclusively. The v1 plan
  records format `gz-starter-records-plan/v1`, operation, resolved checkout
  root, profile byte hash, namespace, transfer map and recheckable source
  observations, plus starting and candidate path identities and exact bytes
  for all eleven paths. Use base64 for file bytes and null for absence; the
  SHA-256 identifies the exact UTF-8 plan bytes. Provide a human-readable
  preview of the plan and resulting file diff. Preview has no authority to
  perform the apply. The adopter supplies the reviewed digest on apply.
- Init apply checks plan format, digest, operation, checkout and profile, then
  validates all embedded destinations and regenerates expected candidate
  views from the reviewed bytes. It checks unchanged inputs and source
  observations under the writer guard before preparing a transaction.
  A fully installed candidate can return `NO CHANGES` if the sources still
  match. Other mismatches are stale input errors. If old authorities were
  deliberately retired after successful apply, use a new init preview or
  check, since the earlier migration plan identifies their former revisions.
  A remote authority can change after the last observation. The reviewer
  checks current dispositions again before claiming adoption acceptance.
- `check` reports local structure, consistency and generated view state.
  With `--require-tracked`, also require the eleven entries to be ordinary
  tracked files with identical stage-zero index and HEAD blob identities.
  Compare worktree content to these blobs with Git's configured path-aware
  clean conversion, and run byte-sensitive records checks on the actual
  worktree. This accepts a clean CRLF checkout.
  Apply and check keep human authority transfer separate. Check never
  establishes acceptance of a referenced release, approval or evaluation by
  finding a locator or digest alone. Arbitrary project evaluation and approval
  formats require human review. The local report distinguishes valid records
  and verified source identity from pending semantic acceptance.

## Walkthrough 3 — Work with the records

In Paper Finch, the maintainer edits `work.json` once the export rows are
written. They set `T-ROWS` to `done` and change continuation to “Verify
CSV output on a clean checkout.” `records check` reports
`STALE VIEW WORK.md`. They run:

```text
$ uv run --locked gz-starter records render --project .
UPDATE  WORK.md generated region
$ uv run --locked gz-starter records render --project . --apply
APPLIED 1 path
```

Preview is optional and writes no managed files. Apply acquires the writer
guard, reads the current files, and validates and renders the complete
candidate before any replacements. It requires no saved preview or pasted
digest. If the files changed since an optional preview, apply uses the current
inputs under the same checks. A current view reports `NO CHANGES`.

The generated task now shows `[done]` and the new continuation. “Pair on the
first export fixture” stays byte-for-byte. The backlog still says `active`
and the release verdict is still `UNKNOWN`. The maintainer records those
distinct decisions when the applicable evidence exists.

If someone types “[done]” inside the generated region by hand, render reports
`EDITED GENERATED REGION WORK.md` and changes no files. The
maintainer preserves any intended change in the sidecar or narrative, restores
the previous intact region from Git by hand and previews again.

For a recovery exercise, the maintainer edits both the priority in
`backlog.json` and the continuation in `work.json`. A single render apply
is interrupted after replacing `BACKLOG.md` but before replacing `WORK.md`.
Absent other edits, `records recover --project .` previews a rollback.
With `--apply --expect-sha256 <reported-digest>`, it restores the prior
`BACKLOG.md` bytes. Both deliberate sidecar edits stay on disk, and a fresh
render can apply the pair. If the maintainer independently edits narrative
in `WORK.md` before recovery, recovery reports
`RECOVERY CONFLICT WORK.md differs from start and candidate` and makes no
managed writes. The maintainer can save the independent narrative in a
separate file, restore the exact known starting `WORK.md`, run rollback, then
reapply their narrative and preview again. Starter never discards the edit.

## v1 sidecar schemas

The five sidecars live beneath `.gz-starter/records/` as specified by the
ADR. Each sidecar holds the current collection of structured records for its
corresponding Markdown document. For example, `backlog.json` holds the project's
backlog records, and `BACKLOG.md` renders a view of that collection alongside
the adopter's narrative. Git history preserves earlier committed states.
`CHANGELOG.md` remains hand-written.

Use strict UTF-8 JSON. In each, the exact envelope is `format` (literal
`gz-starter-records/v1`), `artifact` (the filename stem), `namespace` (a
project-owned lowercase slug matching `[a-z][a-z0-9-]{0,63}`), and `records`
(an array of the artifact's one record type). Unknown keys, duplicate JSON
keys, malformed UTF-8, wrong types and unknown versions fail validation.
Fields in the tables are required, including empty arrays and explicit nulls.
Strings described as text are nonblank and contain no control characters.
IDs match `[A-Z][A-Z0-9-]{0,63}`. Record IDs are unique across all five files.
Criterion, task and gate IDs are unique within their parent and may be reused
in another parent. Choose stable IDs independently of status, release or
parent. Keep existing IDs on edits and transferred records. Use terminal
states or deferrals to retain referenced history.

`RecordRef` has exactly `namespace` and `id` and resolves within the same
namespace. `SourceRef` has exactly `locator` (text), `revision` (null or
`git-commit:<full oid>`, `git-blob:<full oid>` or `sha256:<64 lowercase hex>`),
`record_id` (text or null) and `availability` (`available`, `unavailable`
or `redacted`). Git OIDs are lowercase 40 or 64 hex characters according to
the source repository. Use project-relative paths or absolute HTTPS
locators, with `record_id` for a section, issue node or named result as needed.
An available reference requires a revision. Validate source identity and
readable contents where an authority or acceptance claim depends on it.
Unavailable or redacted sources can document gaps. Report an unresolved
claim as pending and identify the source. Evidence that cannot be evaluated
never supports a pass. Imported and cited evidence retains its owning locator.

| File and literal `type` | Exact record fields beyond `id` and `type` |
| --- | --- |
| `requirements.json` / `requirement` | `title` and `statement` text, `authority` SourceRef, `approvals` SourceRef array, `constraints` text array, `criteria` nonempty array of `{id, statement}` |
| `backlog.json` / `work-item` | `title` and `objective` text, `kind` one of `capability`, `outcome`, `gate`, `external-boundary`, `in_scope` nonempty text array, `out_of_scope` text array, `criteria` nonempty array of `{id, statement}`, `coverage` array described below, `parent` backlog ref or null, `depends_on` backlog ref array, `priority` one of `low`, `normal`, `high`, `urgent`, `state` enum below, `lifecycle_evidence` SourceRef array, `block` null or `{reason, resume_state}`, `closure_reason` text or null, `origins` SourceRef array |
| `roadmap.json` / `milestone` | `title` and `capability` text, `outcomes` outcome ref array, `forecast` release ref or null, `deferrals` array of `{scope, reason, revisit}` with all three text |
| `work.json` / `execution` | `outcome` outcome ref, `plan` and `approval` SourceRefs, `tasks` nonempty array of `{id, statement, state}` with state `pending`, `in-progress`, `blocked` or `done`, `blockers` array of `{task_id, reason, resume}` with task ID and two text fields, `evidence` SourceRef array, `continuation` text or null |
| `releases.json` / `release` | `version` stable SemVer core, `baseline` earlier published release ref or null for verified first-release scope, `state` one of `selected`, `published`, `withdrawn`, `impact` one of `patch`, `minor`, `major`, `rationale` text, `members` nonempty outcome ref array, `gates` nonempty array described below, `publication` null or `{approval, tag, channels}` where approval and tag are SourceRefs and channels is a nonempty SourceRef array |

Statements, reasons, resume conditions and scopes in nested objects are text.
Arrays of references and scope strings reject duplicate entries. Preserve
ordered checklist and scope prose. The remaining value rules are:

- A coverage row is exactly `{requirement, criterion_id, contribution,
  integration_owner}`. The reference and criterion ID resolve together,
  contribution is text, and integration owner is an outcome ref or null for
  a sole contribution. For several contributors to the same requirement
  criterion, all rows must name the same integration owner. One row per
  criterion per work item. Coverage records scope and never asserts
  satisfaction.
- Backlog lifecycle states are `backlog`, `designing`, `ready`, `active`,
  `blocked`, `review`, `completed` and `not-planned`. Require a concrete
  block only in `blocked`, with a resume state among the other open states.
  Require a closure reason only in terminal states. Require lifecycle evidence
  for ready, active, review and terminal states. Review prior and next
  snapshots for the eligibility and transition evidence described by the
  [paired design inputs](../../handoffs/2026-11-14-opinionated-cli-design-discussion.md#simultaneous-design-checkpoint).
  A local snapshot checker does not reconstruct transition history. Reject
  parent cycles, dependency cycles, self-links and wrong reference types.
- One execution record per outcome. Blocked tasks each have at least one
  entry in `blockers`. Other tasks have none. Plans and approvals are pinned.
  Execution blockers describe the selected task, while backlog blockers
  describe the outcome. A task update confers no outcome transition.
- Each release gate is exactly `{id, statement, verdict, inputs, evaluation}`.
  Verdict is `SATISFIED`, `UNSATISFIED` or `UNKNOWN`. Inputs are a SourceRef
  array. A resolved verdict requires nonempty exact inputs and an available
  evaluation SourceRef. The evaluation retains the immutable results and
  definitions used. `UNKNOWN` has a null evaluation and may list known inputs.
  Changed applicable inputs require a fresh evaluation before acceptance.
  The reviewer compares the asserted verdict to its actual evaluation and
  records the disposition through the project's acceptance procedure. The
  CLI validates readable source identity and references. A missing, changed
  or unreadable source leaves the dependent claim pending.
- Release versions are unique and at most one is selected. Publishing
  requires observed publication, approval and tag references, plus all
  gates satisfied against the delivered inputs. Other states use null
  publication. One outcome may appear in only one selected or published
  scope. Keep published versions, membership and observed tag immutable.
  The project reviewer verifies the baseline, SemVer derivation, release
  decisions, publication evidence and history through existing policy.
  Roadmap forecasts may point to a selected or historical published
  release and carry no membership authority.

### Issue Artifacts as issue-level views

A GitHub issue relates to specific records through their observed issue
identity and explicit references. In the Paper Finch fixture, issue #12
relates to backlog record `B-CSV`. That record links to the relevant
requirement criterion, and the work and release sidecars refer to it where
applicable. The issue has no need for a copy of the entire backlog.

For adopters who use GitHub Issues, the preferred presentation to qualify is
a named [GitHub Issue Artifact](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/using-artifacts-with-issues)
for the issue's related records. It can show a short human-readable view,
record IDs and commit-pinned links to the source sidecars. The sidecars remain
the editable source for their structured facts. The artifact's version
records what was shown at a given source revision. A downloadable JSON
attachment is useful when a consumer specifically needs a portable snapshot
of an individual record.

Qualify the proposed Artifact workflow with an invented issue and committed
fixture records. Verify the artifact can be created, updated and retrieved
at an earlier version, and that both versions point to the correct source
records. Record the GitHub feature and CLI or API revision used. GitHub
currently supplies Issue Artifacts in public preview. Feature review still
needs to decide whether this GitHub presentation is a first-release gate.

### SP-BP alignment

The lite configuration guarantees a common local record layout and requires
the data needed to preserve SP-BP semantics. Qualify that alignment for the
selected SP-BP revision under
[ADR-0001](../../decisions/ADR-0001-001-qualify-exact-component-combinations.md).
Record the exact contract source and the disposition of each correspondence:

| Lite record | SP-BP meaning to preserve |
| --- | --- |
| Requirement | Stable statement and criterion keys, governing source revision and approvals |
| Backlog | Native issue identity when observed, kind, bounded scope, lifecycle, hierarchy, dependencies, priority and coverage |
| Roadmap | Capability and outcome grouping, forecasts and explicit deferrals |
| Work | Selected outcome, pinned plan and approval, progress, blockers, evidence and continuation |
| Release | Published baseline, selected membership, exact-input acceptance and publication evidence |

Verify the correspondence against Paper Finch's populated records and its
GitHub issue transfer case. A field may map to a native issue field or to a
linked governing document, according to the selected SP-BP contract. Record
any missing or ambiguous mapping and keep alignment pending until resolved.
Backplane owns its mode and native issue contract. The first release tests
the required local shape and verifies the correspondence. The actual
lite-to-heavy transfer and native workflow qualification keep their separate
roadmap gates. Future schema revisions require explicit migration and fixture
verification. v1 refuses newer formats.

## Generated view and recovery details

A view uses the two full-line v1 markers shown in the walkthrough. A marker
with the reserved opening or closing prefix and malformed syntax, an unknown
version, a wrong artifact, extra markers or a mismatched pair is a conflict.
The opening marker stores SHA-256 of the body bytes between the marker lines.
Verify it before comparing to the newly generated body. A matching old hash
and different deterministic output means stale. A mismatched hash means an
edited region. The digest detects accidental edits, with Git and reviewer
inspection as the provenance for a disputed prior view.

Generate UTF-8 with LF inside the replacement region, fixed field order as
listed above, and record ordering by ID. In each section render the ID, title
or outcome, and each nonempty structured field in schema order. Render
RecordRefs with their IDs, and sources as escaped locators with revisions and
availability. Sort set-like reference arrays by identity, preserve checklist
order, and escape Markdown and raw HTML in user strings. Empty arrays render
as `No records yet.` when the entire artifact is empty. Own the opening line
through the closing line's terminator and preserve all bytes outside that
span, including surrounding CRLF and a trailing narrative without a newline.
Accept LF or CRLF in a previously intact region. If Git converted body line
endings, compare the stored digest to its LF-normalized body and compare
content in LF. A current CRLF view needs no rewrite. The entire Markdown
file must be UTF-8. Preserve an existing changelog as opaque bytes.

Use a single nonblocking OS-backed advisory lock across init apply, render
apply and recovery apply. Locate the stable lock file and transaction under
the checkout's private Git admin directory using Git's worktree-specific
path resolution. Keep the lock inode in place and hold its descriptor until
work completes. A process exit releases the OS lock. A concurrent writer
reports busy. Use the same guard for reading a consistent preview or check
and report a pending transaction before trusting its managed paths. Refuse
linked or unexpected paths, reparse points, multiply linked files and
nonregular destinations, including unsafe ancestors. Compare paths under the
real checkout and validate the canonical allowlist on each write. Treat the
Git admin directory resolved by Git as the private root for scratch state.

During apply, validate all eleven candidate inputs and treat only changed
paths as write participants. The durable manifest contains format
`gz-starter-records-transaction/v1`, operation, checkout identity, the reviewed
plan digest for init or the validated candidate digest for render, fixed
canonical path order, starting and candidate identities
(length and SHA-256 or absent), exact snapshots, and directories the
transaction may need to create. Record unchanged managed inputs and profile
identity as read preconditions. Record the exact reserved scratch path for
each replacement, chosen absent before manifest activation. Include a
manifest digest and validate the snapshot hashes before use. Make the
complete manifest and snapshots durable
in a temporary private directory, then atomically activate that directory
before making managed changes. An incomplete preparation cannot have made
managed writes. Preserve existing permission bits where supported and create
new files with ordinary checkout permissions.

Immediately before replacing each destination, recheck its expected bytes and
safe path. Stage replacement bytes on the destination filesystem, flush them
and replace with the platform's atomic single-file operation. Flush directory
updates where the platform provides it. Verify the complete result before
finalizing. Finalization atomically renames the active transaction out of
the recovery slot before deleting its private snapshots. Clean up incomplete
preparations and finalized private directories under the guard. Preserve an
unexpected filesystem entry for inspection. Same-directory scratch files use
exclusive creation at the reserved paths, stay untracked, and can be visible
after interruption. Do not change Git ignore configuration. On recovery,
clean expected regular scratch files whose bytes are an exact prefix of the
staged starting or candidate snapshot for that destination. Stop on
unexpected bytes or path types. Directory creation is idempotent.
Rollback removes an introduced directory
only if it is verified empty, otherwise it preserves its contents.

Recovery preview classifies every participant and binds its report to the
manifest digest and observed state digest. Recovery apply rechecks both under
the guard. Validate unchanged managed inputs and the profile as well as the
write participants before classifying the outcome. If an unchanged input has
drifted, report it as a conflict and retain the transaction for inspection.
For all-candidate finalization verify the complete local candidate against
the manifest. Old external authorities remain subject to review before
adoption acceptance. All participants must match a recorded state before
any managed write. Recheck the path's identity immediately before changing it.

| Observed participant bytes | Recovery action |
| --- | --- |
| All starting | Finalize the abandoned transaction. Restore absence by removing empty transaction-created directories when safe. |
| All candidate | Verify the candidate and finalize. |
| Mixed, all recognized | Roll back in reverse write order to the starting bytes, removing a file only when it was originally absent and still has candidate bytes. Verify all starting states, then finalize. |
| Any independent edit, unsafe entry or corrupt manifest | Report the path or corrupt state and stop with the manifest and snapshots available. |

An interruption during rollback leaves a mixture with the same two identities,
so recovery can run again. If an independent edit arrives during rollback,
the affected path fails its next comparison and the transaction stays active.
Verify recognized bytes after each replacement and across the whole set before
finalization. The guard coordinates starter writers in one checkout. Editors,
Git and remote services do not participate in that lock. Run with the records
closed to other writers during apply and recovery. Qualify process
interruption on both supported operating systems. Power-loss durability
depends on filesystem and platform flush semantics and has no v1 acceptance
claim. A noncooperating overwrite in the interval
between a comparison and atomic replacement cannot be prevented by a portable
filesystem compare-and-swap. Git supplies the coherent committed snapshot.

Successful preview, check or apply returns zero. Validation conflicts, stale
plans, unsafe paths and pending recovery return nonzero and name the failed
precondition. A valid preview can report pending future actions. Report
existing recognized pending states, such as missing selection or an incomplete
layout, with a nonzero check result. A plan file is review material and may
contain private project text. Keep it local and remove it after acceptance.

## Acceptance of the first delivery

Exercise the installed commands from a fresh lite project and a brownfield
fixture on macOS and Windows. Verify a clean checkout has the eleven tracked
paths. Include both empty and populated initialization, reproducible
rendering, direct render apply without a saved preview, unchanged-content
repeats, invalid schemas and references,
source invalidation, unresolved competing authority, edited generated sections,
narrative preservation and independent adopters using their existing gates.
Verify the SP-BP correspondence against the recorded contract revision,
including both local-only facts and facts with GitHub issue origins.

Reach faults before manifest activation, between file replacements, during
rollback and after the final replacement. Exercise all four recovery outcomes,
a second writer and unsafe paths. Assert file bytes and transaction state.
Keep the existing four routine hooks and check the actual installed command.
Keep the existing adopter verifier and host setup working through their
normal entry points. The release candidate needs input-matched integration
and hosted qualification, observed old-authority disposition in the
brownfield fixture, and released-source evidence to close the roadmap item.
