---
id: ADR-0009
title: Add a Go tier package, gzglite
revision: 1
state: Proposed
decision_date:
revision_date: 2026-11-27
approved_by:
approved_revision:
approval_ref:
---

# ADR-0009 edition 1 — Add a Go tier package, gzglite

## Scope and context

The 2026-11-14 design handoff recorded that implementation is "100% Python for now",
with Go distant future scope and no parallel Go implementation. The starter's
instructions say "Only Python is supported in lite and heavy" (in `AGENTS.md` and in
the adopter template `AGENTS.skills-first.md`). Several of the maintainer's projects are
Go.

On 2026-11-27 the maintainer decided the lighter framework is a permanent tier with one
package per language, so a Go package is needed.

The decision follows the approved design
`2026-11-27-gzlite-rename-and-tool-split-design.md` (sections 3 and 9) and depends on
ADR-0007 (tier names) and ADR-0008 (tools live in tier packages).

## Alternatives

1. **Stay Python only.** Go projects stay without the tier. Rejected.
2. **Make gzlite serve Go projects too.** Mixes two ecosystems into one package and
   invites Go policy derived from Python policy. Rejected.
3. **A separate Go tier package (chosen).**

## Decision and rationale

A Go tier package, **gzglite**, exists and follows gzlite. It mirrors the gzlite 0.14.1
command set (`migrate`, `freshen`, `project-settings`, `portability`, `vendor` and the
rest as they apply to Go), using `.gzglite/`, `gzgl-` skills and its own per-release
marketplace name. gzglite 0.1.0 follows gzlite 0.14.1 in the release train.

This supersedes:

- "100% Python for now; no parallel Go implementation" (2026-11-14 handoff);
- "Only Python is supported in lite and heavy" (starter `AGENTS.md` and adopter
  template).

**Go policy is not derived from Python policy.** Where behavior
must match (for example the shared release history for `migrate`), gzglite tracks the
gzlite artifact explicitly. Go repositories migrate to gzglite, never through gzlite.

## Consequences

- gzlite 0.14.0 stays Python only. `gzlite migrate` refuses in a Go project and names
  gzglite.
- gz-skills gains `references/go.md` where its skills need it.
- Updating the "Python only" statements in `AGENTS.md` and the adopter template is
  follow-on work; timing is not decided here.
- The gzglite design (`2026-11-27-gzg-starter-design.md`, to be renamed) specifies the
  Go module layout, which this ADR does not decide.

## Confirmation

gzglite 0.1.0 passes its own gate, its parity manifest tracks the shared files, and a
Go adopter with a gz-starter lock migrates to it with `gzglite migrate`.

## Approval evidence

(Empty. The maintainer approves this edition separately.)

## Amendment history

- Edition 1, 2026-11-27: drafted from the approved gzlite design (sections 3 and 9)
  and the maintainer decisions log.
