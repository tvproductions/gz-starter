# gzlite 0.14.0 and gz-skills v0.15.0 design

Date: 2026-11-27. Status: approved by the maintainer 2026-11-27. The ADRs in section 9
still need their own approval.

Covers two repositories and one release train: `tvproductions/gz-starter` becomes
**gzlite** (release 0.14.0, then 0.14.1), and `tvproductions/gz-skills` becomes code-free
(release v0.15.0). The Go counterpart **gzglite** has its own design
(`2026-11-27-gzg-starter-design.md`, to be renamed) and mirrors gzlite 0.14.1.

When approved, this document is split into one spec per repository under each
repository's `docs/superpowers/specs/`, and the decisions that overturn earlier recorded
direction are recorded as ADRs (section 9).

Marking: **[M]** maintainer decided (see `2026-11-27-gzlite-decisions-log.md`). **[C]** a
design call made while writing. Facts come from read-only surveys of origin/main on
2026-11-27: gz-starter `98acc5a` (0.13.0), gz-skills `57a7f19` (v0.14.0). The local
gz-starter checkout (`U:\repos\agents\gz-skills-first-starter`) is stale at v0.10.0 and
in the pre-rename folder; it is brought current, with the maintainer's go-ahead, before
any implementation.

## 1. Intent

The lighter GovZero framework is a permanent tier, not a starting stage: Superpowers +
Superpowers Backplane + gz-skills + one tier package per language. gzkit remains the
heavier Python framework. **[M]**

- **gz-skills** are complements and supplements to Superpowers: judgment skills written
  as prose, carrying GovZero's opinions. They carry no executable code. **[M]**
- **Tier packages** (gzlite for Python, gzglite for Go) follow "light skills, heavy
  tools": their own skills are thin, and deterministic work lives in their CLIs. **[M]**
- The starter name implied graduation to gzkit, which a Go project can never do, so the
  Python package is renamed gzlite. **[M]** The rename is done properly even though
  roughly a dozen projects rely on gz-starter. **[M]**

## 2. Goals, non-goals, anti-goals

Goals:

1. Rename gz-starter to gzlite across repository, distribution, CLI, marketplace, state
   folder and skill prefix. **[M]**
2. Move all executable code out of gz-skills into gzlite (and later gzglite). **[M]**
3. Let every adopter, from any earlier gz-starter version, migrate in one reviewed,
   deterministic step. **[M]**

Non-goals:

- ADR-0005 lite records (moved to 0.15.0). **[M]**
- The strict-hexagonal checker and takeover path (own release after 0.15.0,
  provisionally 0.16.0). **[M]**
- Renaming the `.gz-skills/settings.json` profile values. **[M]**
- Changing Superpowers or Superpowers Backplane.

Anti-goals:

- Any window in which a skill points at a command no released tier package has.
- A migration that silently overwrites an adopter's hand-edited managed file.
- Confusing the `lite`/`heavy` profile modes with the gzlite/gzkit tiers.

## 3. Release train **[M]**

1. **gzlite 0.14.0**: the rename and every new command (section 5); bundle still pins
   gz-skills v0.14.0 (with its helpers), so nothing breaks in between.
2. **gz-skills v0.15.0**: removes all code (section 6); skills point at the tier package's
   commands; gate runs `gzlite catalog check` from gzlite 0.14.0. A 0.x minor.
3. **gzlite 0.14.1**: bumps only the gz-skills pin to v0.15.0.
4. **gzglite 0.1.0**: mirrors gzlite 0.14.1; adds `references/go.md` to gz-skills skills
   where needed (a gz-skills patch or minor).

Adopters migrate with `gzlite migrate` to 0.14.1 or later. Version line continues:
gz-starter 0.13.0 → gzlite 0.14.0; 1.0.0 and its PRD come later. **[M]**

## 4. The rename

| Surface | gz-starter 0.13.0 | gzlite 0.14.0 |
|---|---|---|
| GitHub repository | `tvproductions/gz-starter` | `tvproductions/gzlite` via `gh repo rename` (keeps tags, releases, redirects); needs the maintainer's explicit go-ahead at execution **[C]** |
| Local checkout folder | `gz-starter` (this machine: stale `gz-skills-first-starter`) | `gzlite` **[C]** |
| Distribution | `gz-starter` | `gzlite` **[C]** |
| CLI | `gz-starter` (alias `skills-first-starter`) | `gzlite`; `gz-starter` and `skills-first-starter` stay as aliases, as a bridge so unmigrated CI keeps working **[M]** |
| Python import package | `skills_first_starter` | `gzlite` **[C]** (no external importers are known; the verification extra is invoked as a CLI) |
| Verification extra | `gz-starter[verification]` | `gzlite[verification]` **[C]** |
| Native marketplace | per release, `gz-starter-0-13-0` | per release, `gzlite-0-14-0` **[C]** (same scheme) |
| Marketplace recognizer | `skills-first-starter`, `gz-starter-N-N-N` | adds `gzlite-N-N-N`; keeps both legacy forms for retirement **[C]** |
| State folder | `.gz-starter/` (legacy `.skills-first/`) | `.gzlite/` **[C]** |
| Update skill | `update-gz-template` (approved, unshipped: `gzt-update-template`) | `gzl-update` **[M]** prefix; **[C]** name |
| Display name | GZ Starter | GZ Lite **[C]** |

The Go tier uses `gzglite`, `.gzglite/`, `gzglite-0-1-0`, `gzgl-` and `gzgl-update`.

Historical references (CHANGELOG, evidence, past ADRs, handoffs) are not rewritten.

## 5. gzlite 0.14.0 commands

All new commands follow gz-starter's existing conventions: JSON on stdout
(`indent=2`), refusals as `adoption blocked: …` on stderr with exit 2, preview by default
and `--apply` to write, space-free paths, state-folder validation before and after
writes. **[C]** The base helper stays standard-library Python (ADR-0003); only `verify`
keeps its optional extra.

### 5.0 Doctrine: "my way or the highway" **[M]**

gzlite is highly opinionated and its doctrine is authoritative. When gzlite updates its
doctrine, adopters conform. Two commands and one skill carry that out:

- `gzlite migrate` (5.1): the one-time hop from legacy gz-starter or skills-first state
  into gzlite state. **[M]** that a migrate may exist; **[C]** its scope.
- `gzlite freshen --project <root> [--apply --fingerprint <hash>]`: brings a gzlite
  adopter to the running release in three parts. **[M]**
  1. Managed files (host config, lock, state folder, fragment, update skill) to the
     current release under the drift rule (5.1).
  2. Component pins set to the release's bundle, with no exceptions; pins an adopter set
     on its own are not carried forward. **[M]**
  3. Doctrine conformance that cannot be fixed by writing a managed file (verification
     setup; later strict-hexagonal import rules and lite records) reported as findings,
     each citing its doctrine source (ADR or policy document). Findings are never
     auto-fixed; they are the project's to-do list. **[C]**
  `freshen` refuses legacy state and names `migrate`. **[C]**
- `gzl-update` skill (thin): run `gzlite migrate` if legacy state exists, then
  `gzlite freshen`; show the preview and findings; apply only the fingerprint the
  maintainer names; work the findings with Superpowers. **[M]**

### 5.1 `gzlite migrate --project <root> [--apply --fingerprint <hash>]` **[M]**

- Reads the adopter's lock from `.gz-starter/` or `.skills-first/` (any version from
  0.1.0), and plans the full chain to the running gzlite release: state folder move to
  `.gzlite/`, lock rewrite (`starter.repository`, `version`, `revision`), marketplace
  retirement and new `gzlite-0-14-x` entries in Claude, Codex and OpenCode host config,
  plugin keys, the AGENTS pointer and `AGENTS.skills-first.md` fragment, the update skill
  (`update-gz-template` → `gzl-update`), ADR policy file location, and the verification
  extra's dev-dependency name where present.
- Preview lists every change by file and the reason (which release introduced it), plus
  a fingerprint over inputs and planned changes. `--apply` recomputes and writes only on
  a matching fingerprint. **[C]** for the fingerprint, matching the maintainer's rule for
  xplane-wed-helper.
- Drift rule **[M]**, applied to every difference from what the recorded release wrote:
  - carry forward what the tool understands: extra lock keys, extra catalogs, and every
    configured host (Claude, Codex, OpenCode), not only the host the lock records;
  - replace gzlite-owned files (the fragment and the update skill) with the current
    release's, saving each locally edited copy under `.gzlite/migrated/` and listing it in
    the preview;
  - refuse, changing nothing, only what cannot be read safely: dual state (both
    `.gz-starter/` and `.skills-first/`, as in `xplane-webapi`), links, paths with
    spaces, an unparseable lock, a revision not in the starter's history, or a `.gzkit/`.
- Component pins move to the target release's bundle. **[M]**
- Never invents a lite/heavy profile; leaves `.gz-skills/settings.json` untouched.
- After `--apply` it runs the equivalent of `status` and reports the result.
- The release-by-release history `migrate` needs (what each version wrote) is embedded
  as data, generated from the tagged releases and tested against each one. **[C]**

Settled after the builder check **[C]**:

- **Release history keyed by revision.** The embedded history maps each published
  starter revision to what its `configure` wrote. A lock naming an untagged revision that
  is an ancestor of a tagged release (for example `windows-health`: 0.3.2 at `88928b2`,
  never tagged) uses the nearest earlier tag's file set, and any difference goes through
  the drift rule. A revision that is not in the starter's history is refused. All three
  historical repository names (`skills-first-starter`, `gz-skills-first-starter`,
  `gz-starter`) are accepted.
- **Shared history.** gzlite publishes the history as a JSON data file in each release.
  gzglite embeds the same file, tracked as a `verbatim` entry in its parity manifest, so
  Go adopters with gz-starter locks migrate to gzglite with identical history.
  `gzlite migrate` refuses in a Go project (a `go.mod` and no `pyproject.toml`) and names
  gzglite.
- **Verification dependency.** Where `pyproject.toml` has the `gz-starter[verification]`
  dev dependency, `migrate` rewrites it to `gzlite[verification] @ git+…gzlite.git@SHA`
  under the fingerprint, then reports "run `uv lock`" as a required next step outside the
  fingerprint (relocking needs the network and is not byte-deterministic). `status`
  reports the adopter as not verified until `uv lock --check` passes.
- **Renamed gz-skills skills.** gzlite 0.14.1 also updates the managed fragment's skill
  names (a history step), not only the pin. `migrate` reports old gz-skills skill names
  found in project-owned files (`AGENTS.md`, `CLAUDE.md`, docs) as findings and does not
  rewrite them.
- **`vendor` source.** `gzlite vendor` fetches the pinned gz-skills revision with `git`
  into a local cache keyed by revision, or takes `--source <checkout>`. The gate tests it
  against a local fixture repository, with no network. No `gz-skills.lock.json` consumer
  is known, so the command stays minimal.
- **ADRs.** Each ADR in section 9 needs its own explicit approval before the
  implementation that depends on it (gz-starter AGENTS.md: approving a spec or plan does
  not approve an ADR).

### 5.2 Bridge prompt for the first hop **[M]**

`docs/migrating-from-gz-starter.md` carries one short copy-paste prompt the maintainer
gives an agent in each old project. It tells the agent to install gzlite at a named
release SHA, run `gzlite migrate --project .` and then `gzlite freshen --project .`,
showing each preview and applying only the fingerprint the maintainer names, then run
`gzlite status` (and `gzlite verify` where the project uses it). Old projects' update skills do not know gzlite; after migrating, the
installed `gzl-update` handles later upgrades by calling the same command.

### 5.3 `gzlite project-settings inspect|initialize|select` **[M]** move; **[C]** shape

Moves `gzs-project-setup/scripts/project_settings.py` (167 lines) unchanged in behaviour:
`--project <root>`, `select --profile lite|heavy`; schema exactly
`{"schema_version": 1, "profile": null|"lite"|"heavy"}` at `.gz-skills/settings.json`;
exclusive create, atomic replace, refusals (`.gzkit/`, links, malformed file, select
before initialize, heavy→lite). It becomes the single validator: `configure`'s
`profile_check()` and `verify`'s `_profile()` call the same code. **[C]** Output changes
from one JSON line to gzlite's JSON convention, and exit codes to gzlite's (0 / 2). **[C]**

The profile values `lite` and `heavy` are the intentional modes for whether SP-BP drives
the progression of work, design and feature tasks; they are unrelated to the tier name.
**[M]**

### 5.4 `gzlite portability` **[M]** move; **[C]** shape

Moves `gzs-cross-platform-python/scripts/audit_portability.py` (356 lines, read-only):
`--root`, repeatable `--check line-endings|subprocess-errors` and `--path`. JSON findings
`{check, artifact, message}`. It keeps its own exit codes (0 clean, 1 findings, 2 usage)
because it is a check, not an adoption command. **[C]** It gains tests (it has none
today). Go-specific checks belong to gzglite's `portability`.

### 5.5 `gzlite vendor list|install|status|update|propagate` **[M]** move; **[C]** shape

Moves the gz-skills vendoring CLI (`src/gz_skills`, ~680 lines) and the
`gz-skills.lock.json` schema. Behaviour unchanged (tree-hash locks; update replaces a tree
only if its hash still matches; preview by default for `update` and `propagate`), output
moves to JSON. Native plugins remain the primary install path.

### 5.6 `gzlite catalog check --root <catalog>` **[M]** move; **[C]** shape

Moves gz-skills' maintainer checks so the gz-skills repository has no code:
`inventory_skills.py` (inventory, `--check-floor` ratchet requiring a
`## Discovery and fallback` section with a shrink-only `FLOOR_PENDING` list), and the
catalog-contract parts of `tests/test_repository_contract.py`: version agreement across
the bundle mirrors, marketplace pins, router table lists every catalog skill, explicit-only
skill sets agree across hosts. Usable on any skills catalog, including adopters' own.
The floor-pending list moves into the catalog as data (for example
`catalog-check.json`). **[C]**

### 5.7 Existing commands

`configure`, `localize`, `run-opencode`, `status`, `backport`, `verify`, `validate`,
`version` keep their behaviour under the new names, with the new state folder,
marketplace name and recognizer.

## 6. gz-skills v0.15.0

- Remove `src/gz_skills/`, `pyproject.toml`, `uv.lock`, `.python-version`,
  `scripts/check_package.py`, `scripts/inventory_skills.py`, the Python tests, and the
  two skill scripts. **[M]**
- `package.json` and the OpenCode adapter (`index.js`, `adapters/opencode/gz-skills.js`)
  stay as a distribution manifest for OpenCode, not tooling, with its test. **[M]**
- Supported harnesses are Codex, Claude Code and OpenCode, with OpenCode 2.x only. **[M]**
  Any OpenCode 1.x compatibility code or documentation is removed from gz-skills, gzlite
  and gzglite. **[C]** for the removal.
- Bundle version mirrors drop `pyproject.toml`; `package.json` and both `plugin.json`
  files remain and must agree, checked by `gzlite catalog check`.
- `gzs-project-setup`: operational step becomes "run `gzlite project-settings …`
  (Python) or `gzglite project-settings …` (Go)"; `Discovery and fallback` explains how
  to write the two-field file by hand when no tier package is present. **[M]** prose
  fallback.
- `gzs-cross-platform-python` becomes a language-neutral cross-platform skill (working
  name `gzs-cross-platform`) with `references/python.md`; deterministic step is the tier
  package's `portability`. **[M]**
- `gzs-pythonic-pattern-detect`/`-apply` become language-neutral idiomatic-pattern skills
  (working names `gzs-idiomatic-pattern-detect`/`-apply`) with `references/python.md`.
  **[M]** direction; **[C]** names.
- The "Project Python version and policy" block, repeated in five skills, moves to
  `references/python.md` in each. "Adopted heavy Python profile" in
  `gzs-update-dependencies` and "Heavy Python environment guidance" in
  `gzs-project-setup` become per-language references.
- `gzs-router` catalog updated for renamed skills.
- AGENTS.md: drop the Python tooling section and the `uvx` snapshot contract; state that
  the repository carries no executable code and gates on `gzlite catalog check`.
  `docs/packaging.md` updated. Removals and renames recorded in CHANGELOG with migration
  notes, as AGENTS.md requires. Every touched skill gets a version bump.
- Renamed skills: old names are recorded as removed in CHANGELOG; the router lists the new
  names. No compatibility aliases. **[M]**

## 7. Adopters

Known on this machine: `xplane-webapi` (0.12.1, dual state, refused until resolved by
hand), `gz-mcp-lsp` (0.9.0), `xplane-fdau` (0.8.0), `xplane-health` (v0.6.0),
`windows-health` (0.3.2), `Ortho4XP` (0.1.0); about a dozen in total. Each migrates with
the bridge prompt, `migrate` and `freshen`. The Go repositories (`windows-health`,
`xplane-health`) wait for gzglite 0.1.0 and migrate to it, never through gzlite. **[M]**

## 8. Testing **[C]**

- `migrate` golden tests from a fixture adopter per historical release (0.1.0 through
  0.13.0, each generated by that release's `configure`), per host, plus refusal fixtures
  (hand-edited file, dual state, link, space, `.gzkit/`).
- Determinism: every preview run twice is byte-identical; fingerprints stable.
- Moved commands keep their existing tests (`test_project_setup.py`, installer tests,
  inventory tests) ported into gzlite; `portability` gains tests.
- `gzlite catalog check` run against gz-skills v0.14.0 and v0.15.0 fixtures.
- No network in the gate.

## 9. Decisions that overturn earlier recorded direction

Recorded as ADRs (gzlite repository, and a pointer in gz-skills):

- Starter is renamed gzlite; tier, not stage. Supersedes `docs/rename-gz-starter.md` as
  the current identity.
- gz-skills carries no executable code; helpers, vendoring and catalog checks move to the
  tier packages. Supersedes gz-skills' "skill-local helpers travel with their
  directories", "do not require the starter for unrelated standalone skill consumers"
  (now: prose fallback), and the `uvx` snapshot contract.
- A Go tier package (gzglite) exists. Supersedes "100% Python for now; no parallel Go
  implementation" (2026-11-14 handoff) and the "Python only in lite and heavy" line,
  without deriving Go policy from Python policy.
- Prefix `gzl-`/`gzgl-` supersedes the approved `gzt-` design.
- Lite records move to 0.15.0.

## 10. Left to the builder

Module layout of the renamed package, the embedded release-history data format, exact
JSON shapes for the moved commands' output, wording of the bridge prompt, and the order
of work inside each release.
