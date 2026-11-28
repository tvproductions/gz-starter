# gzlite rename and gz-skills tool split: decisions log

Running log of maintainer decisions from the 2026-11-27 conversation, kept until the
design spec is written. [M] = maintainer decided.

- [M] The lighter framework is a permanent tier, not a stage: Superpowers + SP-BP +
  gz-skills + one per-language tier package. gzkit stays the heavy Python framework.
- [M] gz-starter is renamed gzlite (Python); the Go counterpart is gzglite.
- [M] "Light skills, heavy tools" is a gzlite/gzglite principle. gz-skills are
  complements/supplements to Superpowers (judgment skills, prose, GovZero opinions) and
  carry no executable code; their operational tools move into gzlite (Python) and gzglite
  (Go) with matching subcommand names. Language-specific skill knowledge moves to
  per-language reference files.
- [M] Strict hexagonal architecture (gz-starter ADR-0006) applies to Go adopters too; the
  tier packages need a takeover path for existing projects (current violations recorded
  as a shrink-only exceptions baseline).
- [M] Do the rename properly even though many projects rely on gz-starter.
- [M] Migration combination: a deterministic `gzlite migrate` command (reads the
  adopter's lock, plans the chain from its version, preview then fingerprinted `--apply`,
  refuses what it cannot place safely); a thin copy-paste bridge prompt in gzlite's
  migration doc for the one-time first hop (old adopters' update skills do not know
  gzlite); after migrating, the installed update skill handles later upgrades by calling
  the same command. No separate migration skill.

- [M] Projects that use gz-skills without gzlite or gzglite get prose-only fallback
  through each skill's `Discovery and fallback` section; the deterministic version comes
  only with a tier package. (Supersedes gz-skills' "do not require the starter for
  unrelated standalone skill consumers" for deterministic helpers; the skills themselves
  stay usable standalone.)

- [M] The gz-skills vendoring CLI (`govzero-skills`, `gz-skills install|status|update|
  propagate`, `gz-skills.lock.json`) is retired from gz-skills, and the capability moves
  into gzlite and gzglite (working name `vendor`). Native plugins remain the primary
  install path.

- [M] gz-skills is code-free for the whole repository. Its catalog checks (inventory,
  discovery-floor ratchet, version and pin agreement, catalog contract tests) move into
  gzlite as a catalog check command (working name `gzlite catalog check`) usable on any
  skills catalog; gz-skills' gate runs it. `check_package.py`, the Python package and
  `pyproject.toml` go away. Each side pins a past release of the other.

- [M] The `.gz-skills/settings.json` profile values stay `lite` and `heavy`. They are
  intentional modes for using SP-BP or not: the progression by which work, design and
  feature tasks are handled. They are unrelated to the gzlite tier name. Renaming would
  add update load across roughly a dozen adopters. Path and schema stay as they are;
  gzlite/gzglite `project-settings` becomes the single writer and validator. [C] for the
  single-validator detail.

- [M] The renamed package continues gz-starter's version line as gzlite 0.14.0 (a 0.x
  minor). 1.0.0 and its PRD come later, once gzglite exists and migrations have run on
  real adopters.

- [M] Release order: (1) gzlite 0.14.0 ships the rename and all new commands (`migrate`,
  `project-settings`, `portability`, `vendor`, `catalog check`) while still pinning
  gz-skills v0.14.0; (2) gz-skills v0.15.0 removes all code, points skills at the tier
  package's commands, makes the pythonic skills language-neutral with
  `references/python.md`, and gates on `gzlite catalog check`; (3) gzlite 0.14.1 bumps the
  gz-skills pin to v0.15.0; (4) gzglite 0.1.0 mirrors gzlite 0.14.1, adding
  `references/go.md` to gz-skills where needed. Adopters migrate to 0.14.1 or later.

- [M] The approved starter-skill prefix change (`update-gz-template` →
  `gzt-update-template`) folds into gzlite 0.14.0. ADR-0005 lite records move from
  provisional 0.14.0 to 0.15.0, so 0.14.0 is purely rename and tool move.

- [M] Tier-package skill prefixes are `gzl-` (gzlite) and `gzgl-` (gzglite), superseding
  the approved `gzt-` design. Example: `update-gz-template` → `gzl-update`. `gzs-` stays
  for gz-skills.

- [M] Strict hexagonal is wanted. Its checker and takeover path (per-language import-rule
  checker, maintainer-approved exceptions register, shrink-only CI test) get their own
  release after 0.15.0 (provisionally 0.16.0), not 0.14.0.

- [M] Drift rule for migration: carry forward what the tool understands (extra lock keys,
  extra catalogs, every configured host); replace gzlite-owned files (fragment, update
  skill) while saving each locally edited copy under `.gzlite/migrated/` and listing it in
  the preview; refuse only what cannot be read safely (dual state, links, unparseable
  lock, revision not in the starter's history).
- [M] gzlite doctrine is authoritative ("my way or the highway"): when gzlite updates its
  doctrine, adopters conform. gzlite needs a skill plus tools that help adopters "freshen
  up".

- [M] One `gzlite freshen` command plus the thin `gzl-update` skill; `gzlite migrate`
  may also exist (the one-time legacy hop). Highly opinionated, "my way or the highway"
  is the rule in gzlite land. Freshen sets component pins to the release bundle.
- [M] gz-skills keeps its OpenCode adapter as a manifest. Supported harnesses: Codex,
  Claude Code and OpenCode, OpenCode 2.x only.

Observed adopters on this machine (2026-11-27, read-only): xplane-webapi (0.12.1, has both
`.gz-starter/` and `.skills-first/`), gz-mcp-lsp (0.9.0), xplane-fdau (0.8.0),
xplane-health (v0.6.0), windows-health (0.3.2), Ortho4XP (0.1.0). More exist elsewhere.
