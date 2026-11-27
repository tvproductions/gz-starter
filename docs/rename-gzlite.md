# Canonical rename to gzlite

The maintainer selected **gzlite** as the canonical repository, distribution and
command name on November 27, 2026. gzlite is a permanent tier, not a stage: the
lighter GovZero framework is Superpowers + Superpowers Backplane + gz-skills + one
tier package per language, and gzkit remains the heavier Python framework. The name
"starter" implied graduation to gzkit, which a Go project can never do. Display name
is **GZ Lite**. The Go counterpart is **gzglite**. The rename ships in gzlite 0.14.0;
release scheduling is in [ROADMAP.md](../ROADMAP.md).

This record supersedes [Canonical rename to gz-starter](rename-gz-starter.md) as the
current identity. That document and other historical text (CHANGELOG, evidence, past
ADRs, handoffs) are not rewritten.

## Canonical identities and retained compatibility

| Surface | gz-starter 0.13.0 | gzlite 0.14.0 |
|---|---|---|
| GitHub repository | `tvproductions/gz-starter` | `tvproductions/gzlite` via `gh repo rename`; needs the maintainer's explicit go-ahead at execution |
| Local checkout folder | `gz-starter` | `gzlite` |
| Distribution | `gz-starter` | `gzlite` |
| CLI | `gz-starter` (alias `skills-first-starter`) | `gzlite`; `gz-starter` and `skills-first-starter` stay as aliases, a bridge so unmigrated CI keeps working |
| Python import package | `skills_first_starter` | `gzlite` |
| Verification extra | `gz-starter[verification]` | `gzlite[verification]` |
| Native marketplace | per release, `gz-starter-0-13-0` | per release, `gzlite-0-14-0` |
| Marketplace recognizer | `skills-first-starter`, `gz-starter-N-N-N` | adds `gzlite-N-N-N`; keeps `skills-first-starter` and `gz-starter-N-N-N` for retirement |
| State folder | `.gz-starter/` (legacy `.skills-first/`) | `.gzlite/` |
| Update skill | `update-gz-template` (approved, unshipped: `gzt-update-template`) | `gzl-update` |
| Display name | GZ Starter | GZ Lite |

The Go tier uses `gzglite`, `.gzglite/`, `gzglite-0-1-0`, `gzgl-` and `gzgl-update`.

## Skill prefixes

Tier-package skills use `gzl-` (gzlite) and `gzgl-` (gzglite). This supersedes the
approved `gzt-` design (`gzt-update-template`); `update-gz-template` becomes
`gzl-update`. `gzs-` stays for gz-skills.

## Unchanged

The `.gz-skills/settings.json` profile values stay `lite` and `heavy`. They are modes
for whether Superpowers Backplane drives the progression of work, and are unrelated
to the tier name.

## Execution

The GitHub rename keeps tags, releases and redirects, but is executed only with the
maintainer's explicit go-ahead. Do not mechanically rewrite historical references.
