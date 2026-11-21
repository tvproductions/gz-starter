---
id: ADR-0003
title: Own bootstrap verification in the starter's installed development tooling
revision: 1
state: Current
decision_date: 2026-11-21
revision_date: 2026-11-17
approved_by: "project maintainer in this conversation"
approved_revision: 1
approval_ref: "#approval-evidence"
---

# ADR-0003 — Bootstrap verification ownership and distribution

**Current edition 1. Explicit architectural approval recorded November 21, 2026.**
The exact reviewed proposal and the maintainer's approval are preserved below.

## Context and scope

The starter permits preparatory adoption before runtime implementation, but
requires routine unittest verification without an executable applicability path.
The consumer's empty unittest discovery exits 5; bypassing that result globally
would hide broken implementation discovery. A supported implementation needs
clear ownership, distribution, inputs and test obligations.

The starter already owns deterministic adoption tooling and opinionated Python
policy. gz-skills owns portable engineering workflows, SP owns feature delivery,
and Backplane owns its independent lifecycle. No generic orchestrator, ledger,
plugin manager or consumer runtime belongs in this correction. Reuse ADR-0001's
exact-source/independent-component constraints and ADR-0002's separation of
project metadata from product runtime configuration.

## Alternatives

1. Extend the starter's installed helper with a development verification command
   and optional dependency extra. One upstream implementation and owning tests
   serve both lanes; adopters must pin and lock an additional development tool.
2. Deliver copied verifier source/tests into each adopter. This avoids an
   installed helper dependency, but adds copy/provenance migration and requires
   special handling so verifier tests do not mask missing product tests.
3. Supply conditional shell snippets only, or move applicability into a portable
   skill. This minimizes starter code, but leaves duplicated executable/platform
   semantics or confuses generic workflow ownership with starter-specific
   adoption/configuration validation. Guidance alone has already proved
   insufficient to complete migration.

## Proposed decision

Choose alternative 1: own `gz-starter verify --project <root>` in the starter's
installed development tooling and test it through the public CLI. Adopters add
an immutable released source for `gz-starter[verification]` to their uv dev group;
no product runtime dependency or copied workflow skill is introduced.

Put explicitly declared safe YAML parsing in the verification extra, preserving
the base adoption helper's standard-library dependency contract. Keep all
project settings in the owning root pyproject. No manual stage/allow-empty switch
is permitted. Observe artifact presence, validate bootstrap inputs and require
real discovery/testing when implementation/tool/test assets appear. The verifier
does not establish arbitrary test relevance, replace coverage gates, certify
native skill loading or approve a consumer's runtime design.

Provide one reviewed hook/CI command contract and migration instructions.
Ordinary configure continues preserving existing product metadata, hook/CI and
handoff files; it does not silently rewrite them. Generic sync/maintenance
workflows remain upstream-owned. Keep the installed verifier's own tests outside
adopter suite inventory so they cannot stand in for consumer behavior tests.

## Consequences and limits

- The new optional interface and migration need versioned delivery and an
  explicit supported Python/platform scope. The current starter distribution
  targets Python 3.14; it is not installed in a 3.12 embedded host by inference.
- There is one tested implementation to update. Adopters own the exact Git
  source/dev lock and review template/tool version changes independently.
- Artifact parsing, product behavior, coverage and hosted CI are separate
  observations. Parsing CI does not qualify executable workflow logic.
- Preserve discovery failures, failed/empty suites and existing coverage scope,
  cadence and thresholds. Inventory uncertainty fails closed.
- No runtime implementation, native activation, companion/adopter write,
  Git sync or release publication follows from this decision's approval.

## Confirmation

Use the acceptance matrix in
[design edition 2](../superpowers/specs/2026-11-17-bootstrap-verification-design.md).
Demonstrate a valid pre-implementation save point, automatic rejection after
implementation/tooling appears without tests, actual test/discovery failures,
coverage preservation, installed distribution behavior, and concrete migration
of stale instruction/handoff requirements. Execute the supported path on actual
macOS and Windows without Node; configuration alone is not platform proof.

## Approval and edition history

Edition 1, November 17, 2026: initial proposal, prepared by the agent in response
to the maintainer's bounded defect request. Approval fields were open at that
checkpoint.

Review direction, November 17: the maintainer endorsed the installed-development
approach and emphasized accounting for the starter's own testing. Design edition
2 makes producer and adopter obligations explicit. The ADR remained open at
that checkpoint.

## Approval evidence

Source is the project maintainer conversation on November 21, 2026. The
agent's prompt identified two approvals in separate items and asked for
approval of bootstrap verifier design edition 3 and, separately, ADR-0003
edition 1. The maintainer replied verbatim:

> approve both

This is an agent transcription. The conversation has no durable review URL.
The explicit reply approves both identified editions. The
[reviewed ADR proposal](approvals/ADR-0003-001-reviewed.txt) has SHA-256
`b859b87b0a3d5e50bc3919d6a86b12a323894825f9ee7c9f05d56333734e7c69`.
The [reviewed design edition 3](../superpowers/specs/2026-11-21-bootstrap-verification-design-edition-3.md)
has SHA-256 `7f0d36db98488dd7d999080d150c094f8de16a4f8c9c3eb6b0128bd68b8c6c07`.
Its draft wording is preserved in the exact reviewed file. The hashes identify
the text; the maintainer's reply records approval.

## Administrative capture

On November 21 the working ADR moved to Current, its approval fields were
filled, and this evidence was added. Edition 1 retains its reviewed choice,
scope and constraints. The reviewed proposal remains available independently
of these administrative edits.
