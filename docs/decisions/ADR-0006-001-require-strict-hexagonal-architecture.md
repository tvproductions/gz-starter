---
id: ADR-0006
title: Require strict hexagonal architecture in every adopter
revision: 1
state: Current
decision_date: 2026-11-26
revision_date: 2026-11-26
approved_by: "project maintainer in this conversation"
approved_revision: 1
approval_ref: "#approval-evidence"
---

# ADR-0006 edition 1 — Require strict hexagonal architecture in every adopter

## Scope and context

This decision covers the architecture that the starter imposes on adopter
projects. The starter exists partly to give every project the same design
discipline, and almost every adopter is the maintainer's own project.

The approved application-foundations design (edition 3, 2026-11-16) adapted
GZKit's hexagonal specification to the starter as "right-sized". Adopters kept
the principles but could use fewer components, and `docs/engineering/python.md`
said "favor hexagonal architecture". GZKit's specification, by contrast, is
strict for the whole system at every size. It assumed lighter projects would use
the starter instead.

On 2026-11-26 the maintainer ruled that arriving later is no excuse for less
discipline. The starter must impose the same strict hexagonal rules as GZKit, in
a spirit of strictness: exceptions are allowed, but each one is named and
justified.

## Alternatives

1. **Keep "right-sized".** Lower cost for small projects, but adopters drift
   apart and the starter stops producing project-to-project consistency.
   Rejected by the maintainer.
2. **Require the principles only.** Pure domain and owned ports, but no fixed
   parts, configurator or import test. Leaves structure to each project, which
   is the same drift in a smaller form.
3. **Require GZKit's structure (chosen).** The six parts, one configurator,
   owned `Protocol` ports, fakes in hexagon tests and an import-rule test.

## Decision and rationale

Every adopter applies strict hexagonal architecture, whatever its size:

- six parts: driving adapters, input ports, handlers, domain, output ports and
  driven adapters, wired by one configurator;
- ports are `typing.Protocol` types named in business terms and owned by the
  application; adapters satisfy them by shape;
- the domain is pure: no files, network, subprocesses, environment, clock or
  randomness; what it needs is passed in as values;
- driving adapters call input ports, and only handlers call output ports;
  handlers coordinate a use case and hold no business decisions;
- hexagon tests use hand-written fakes, never mocks, so each driven port has a
  second adapter from its first test;
- an import-rule test enforces which region may import which. A package map
  names every region; the test covers all of them, runs in routine CI and fails
  the build on any violation, never only warning. Existing violations sit in a
  baseline that may only shrink;
- an exception exists only as a named departure in one exceptions register.
  Each entry records the exact rule and code it covers, the reason, and a
  review date, and needs the maintainer's explicit approval. An agent never
  grants one.

The structure and rules follow GZKit's `docs/governance/hexagonal-architecture.md`.
The starter does not import GZKit. This edition does not mandate GZKit's kernel
choices (frozen Pydantic base classes, command and query buses); whether they
belong to "strict" is an open question for a later edition.

## Consequences

- `docs/engineering/python.md` changes "favor" to "require" and states the
  rules above. `docs/engineering/application-foundations.md` replaces its
  right-sized section and defers to this ADR for hexagonal exceptions.
- This supersedes the application-foundations row "Mandatory hexagon structure
  at every size: Adapt" and its related crosswalk dispositions.
- Existing adopters (gzfactory, gzyoke, gz-cartridge, gzcontractor) report their
  gaps and close them through their own reviewed work. This edition does not
  authorise a broad refactor.
- The starter does not yet ship an import-rule checker or scaffold. Providing
  one is follow-up work; until then each adopter writes its own import test.

## Confirmation

An adopter conforms when its package map names each region, its import-rule test
passes in CI with a baseline no larger than before, its hexagon tests contain no
mocks, and every exception is an approved, unexpired entry in its register.

## Approval evidence

Source is the gzfactory project conversation on November 26, 2026. This is an
agent transcription. The agent walked the maintainer through the seven rules
one at a time; the maintainer kept each, asked for a strong import-rule test and
careful scrutiny of exceptions, and those changes were applied in commit
81fb73e. The agent then asked: "Do you approve ADR-0006 revision 1?" The
maintainer replied verbatim:

> approve

The [reviewed proposal](approvals/ADR-0006-001-reviewed.txt) preserves the exact
proposal bytes with SHA-256
`a092f14fcbab9bd6936fe5836ac210902c263a9ba4a4f27aba0d684513a3247d`.
The maintainer's response approves the architectural decision.

## Amendment history

- Edition 1, 2026-11-26: drafted from the maintainer's ruling in the gzfactory
  project's book-impact discussion.
