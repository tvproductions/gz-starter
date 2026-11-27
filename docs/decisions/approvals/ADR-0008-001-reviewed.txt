---
id: ADR-0008
title: Keep gz-skills free of executable code and move its tools to the tier packages
revision: 1
state: Proposed
decision_date:
revision_date: 2026-11-27
approved_by:
approved_revision:
approval_ref:
---

# ADR-0008 edition 1 — Keep gz-skills free of executable code and move its tools to the tier packages

## Scope and context

gz-skills today ships judgment skills and also executable code: two skill-local helpers
(`gzs-project-setup/scripts/project_settings.py`,
`gzs-cross-platform-python/scripts/audit_portability.py`), a vendoring CLI
(`govzero-skills`, `gz-skills install|status|update|propagate`, `gz-skills.lock.json`),
catalog checks (`inventory_skills.py`, `check_package.py`, repository contract tests) and
a Python package with `pyproject.toml`.

On 2026-11-27 the maintainer ruled that gz-skills are complements and supplements to
Superpowers: prose judgment skills carrying GovZero's opinions. The tier packages
(gzlite for Python, gzglite for Go) follow "light skills, heavy tools".

The decision follows the approved design
`2026-11-27-gzlite-rename-and-tool-split-design.md` (sections 5, 6 and 9) and the
decisions log. It depends on ADR-0007 for the tier names.

## Alternatives

1. **Leave the helpers in the skills.** Python-only, travels with each skill directory,
   and gives a Go project nothing equivalent. Rejected.
2. **Move only the helpers.** Leaves a Python package, `pyproject.toml` and the `uvx`
   snapshot contract in a repository meant to be prose. Rejected.
3. **Make gz-skills code-free (chosen).** Helpers, the vendoring CLI and catalog checks
   move to the tier packages; skills keep the judgment and point at the commands.

## Decision and rationale

gz-skills carries no executable code. Its operational tools move:

- the two helpers become `<tier> project-settings` and `<tier> portability`;
- the vendoring CLI and `gz-skills.lock.json` schema become `<tier> vendor`;
- the catalog checks (inventory, discovery-floor ratchet, version and pin agreement,
  router and explicit-only contract checks) become `gzlite catalog check`, usable on any
  skills catalog; gz-skills' own gate runs it. Each side pins a past release of the
  other (decisions log, catalog-check entry).

`<tier>` is `gzlite` (Python) or `gzglite` (Go). Native plugins remain the primary
install path. gz-skills keeps `package.json` and its OpenCode adapter as a distribution
manifest, not tooling.

**Prose-only fallback.** A project that uses gz-skills without a tier package gets the
skill's prose through its `Discovery and fallback` section (for example, writing the
two-field settings file by hand). The deterministic version comes only with a tier
package. The skills stay usable standalone.

**Supersedes** these earlier recorded directions:

- gz-skills' "skill-local helpers travel with their directories";
- gz-skills' "do not require the starter for unrelated standalone skill consumers"
  (now: prose fallback for the skill, tier package for the deterministic helper);
- the `uvx` snapshot contract in gz-skills' AGENTS.md.

## Consequences

- Release order: gzlite 0.14.0 ships the commands while still pinning gz-skills v0.14.0;
  gz-skills v0.15.0 removes all code; gzlite 0.14.1 bumps the pin. No skill ever points
  at a command that no released tier package has.
- gz-skills v0.15.0 removes `src/gz_skills/`, `pyproject.toml`, `uv.lock`,
  `.python-version`, `scripts/check_package.py`, `scripts/inventory_skills.py`, the
  Python tests and the skill scripts. Its CHANGELOG records removals and renames with
  migration notes; no compatibility aliases.
- Skills with Python-specific content gain `references/python.md`; Go adds
  `references/go.md`.
- The moved commands gain tests where they had none (`portability`).
- Standalone consumers lose the deterministic helpers until they adopt a tier package.

## Confirmation

gz-skills v0.15.0 contains no executable code other than the OpenCode adapter manifest
and its test, and its gate passes `gzlite catalog check`. Each moved command passes its
ported tests in gzlite.

## Approval evidence

(Empty. The maintainer approves this edition separately.)

## Amendment history

- Edition 1, 2026-11-27: drafted from the approved gzlite design (sections 5, 6 and 9)
  and the maintainer decisions log.
