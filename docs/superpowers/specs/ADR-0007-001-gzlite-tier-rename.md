---
id: ADR-0007
title: Rename gz-starter to gzlite and position it as a permanent tier
revision: 1
state: Proposed
decision_date:
revision_date: 2026-11-27
approved_by:
approved_revision:
approval_ref:
---

# ADR-0007 edition 1 — Rename gz-starter to gzlite and position it as a permanent tier

## Scope and context

This decision covers the identity of the Python package now called gz-starter: its
name, its place among the GovZero frameworks, and the names of every surface that
carries it. It also records two scope moves in the same release train.

The name "starter" implied graduation to gzkit. A Go project can never graduate to a
Python framework, and the maintainer ruled on 2026-11-27 that the lighter framework is
a permanent tier, not a stage. `docs/rename-gz-starter.md` records the current identity
(`gz-starter`, `skills-first-starter`), and the approved starter-skill prefix design
(`gzt-`, `2026-11-22-starter-skill-prefix-design.md`) is unshipped.

The decision follows the approved design
`2026-11-27-gzlite-rename-and-tool-split-design.md` (sections 4 and 9) and the
maintainer decisions in `2026-11-27-gzlite-decisions-log.md`.

## Alternatives

1. **Keep gz-starter.** No migration load for roughly a dozen adopters, but the name
   keeps implying a stage and cannot describe a Go counterpart. Rejected by the
   maintainer.
2. **Rename and keep the `gzt-` skill prefix.** Smaller change from the approved
   prefix design, but `gzt-` names no tier and has no Go counterpart. Rejected.
3. **Rename to gzlite with `gzl-`/`gzgl-` prefixes (chosen).** One tier package per
   language: gzlite for Python, gzglite for Go.

## Decision and rationale

**Positioning.** The lighter GovZero framework is a permanent tier, not a stage:
Superpowers + Superpowers Backplane + gz-skills + one tier package per language.
gzkit remains the heavier Python framework. gz-starter is renamed gzlite (Python); the
Go counterpart is gzglite.

**Names.**

| Surface | gz-starter 0.13.0 | gzlite 0.14.0 |
|---|---|---|
| GitHub repository | `tvproductions/gz-starter` | `tvproductions/gzlite` via `gh repo rename`; needs the maintainer's explicit go-ahead at execution |
| Local checkout folder | `gz-starter` | `gzlite` |
| Distribution | `gz-starter` | `gzlite` |
| CLI | `gz-starter` (alias `skills-first-starter`) | `gzlite`; `gz-starter` and `skills-first-starter` stay as aliases, a bridge so unmigrated CI keeps working |
| Python import package | `skills_first_starter` | `gzlite` |
| Verification extra | `gz-starter[verification]` | `gzlite[verification]` |
| Native marketplace | per release, `gz-starter-0-13-0` | per release, `gzlite-0-14-0` |
| Marketplace recognizer | `skills-first-starter`, `gz-starter-N-N-N` | adds `gzlite-N-N-N`; keeps both legacy forms for retirement |
| State folder | `.gz-starter/` (legacy `.skills-first/`) | `.gzlite/` |
| Update skill | `update-gz-template` (approved, unshipped: `gzt-update-template`) | `gzl-update` |
| Display name | GZ Starter | GZ Lite |

The Go tier uses `gzglite`, `.gzglite/`, `gzglite-0-1-0`, `gzgl-` and `gzgl-update`.

**Skill prefixes.** Tier-package skills use `gzl-` (gzlite) and `gzgl-` (gzglite).
This supersedes the approved `gzt-` design; the `update-gz-template` to
`gzt-update-template` change folds into gzlite 0.14.0 as `gzl-update`. `gzs-` stays for
gz-skills.

**Unchanged.** The `.gz-skills/settings.json` profile values stay `lite` and `heavy`.
They are modes for whether Superpowers Backplane drives the progression of work, and
are unrelated to the tier name.

**Scope moves.** ADR-0005 lite records move from provisional 0.14.0 to 0.15.0, so
0.14.0 is purely rename and tool move. The strict-hexagonal checker and takeover path
(follow-up to ADR-0006) get their own release after 0.15.0, provisionally 0.16.0.

**Version line.** gz-starter 0.13.0 continues as gzlite 0.14.0, then 0.14.1. 1.0.0 and
its PRD come later.

This ADR supersedes `docs/rename-gz-starter.md` as the current identity. That document
and other historical text (CHANGELOG, evidence, past ADRs, handoffs) are not rewritten.

## Consequences

- Every adopter migrates once, with `gzlite migrate` and `gzlite freshen` (release
  0.14.1 or later). The legacy aliases and recognizers keep unmigrated CI working
  meanwhile.
- The GitHub rename keeps tags, releases and redirects, but is executed only with the
  maintainer's explicit go-ahead.
- ROADMAP.md moves the lite records to 0.15.0 and records the checker release.
- Historical references to gz-starter remain and are intentional.
- A Go project is no longer implied to be a candidate for a Python framework.

## Confirmation

The gzlite 0.14.0 gate passes with the new names on every surface in the table. A
migration test covers a fixture adopter per historical release, and no shipped skill
uses the `gzt-` prefix.

## Approval evidence

(Empty. The maintainer approves this edition separately.)

## Amendment history

- Edition 1, 2026-11-27: drafted from the approved gzlite design (sections 4 and 9)
  and the maintainer decisions log.
