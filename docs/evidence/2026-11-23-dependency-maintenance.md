# Dependency maintenance — November 23, 2026

The maintainer invoked `gzs-update-dependencies` in update mode. The rollback
reference is clean `main` at `93a5eeca112e1480dc8bb5fd09c3f69adb71282b`.
[Published 0.12.1](https://github.com/tvproductions/gz-starter/releases/tag/v0.12.1)
at `a1c3550eac441b0a7beaddc66fb00c58ce0f1e6a` advances to **0.12.2 / patch**
under the [selected maintenance scope](../../ROADMAP.md#selected-0122-patch-scope--dependency-maintenance-november-23-2026).
The five compatible upgrades restore the existing latest-stable tooling
commitment. The 0.13.0 skill rename has its own scope and qualification.

## Official inventory and migration

The [structured inventory](2026-11-23-dependency-inventory.json) records all 77
PyPI projects, candidate lock selections, source URLs and input digests. Both
baselines move to the latest stable versions with non-yanked artifacts.

| Package | Previous | Selected | Release evidence |
| --- | --- | --- | --- |
| ty | 0.0.107 | 0.0.108 | [Astral release and rule changes](https://github.com/astral-sh/ty/releases/tag/0.0.108) |
| coverage | 7.17.4 | 7.17.5 | [Coverage.py on PyPI](https://pypi.org/project/coverage/7.17.5/) |
| charset-normalizer | 3.5.2 | 3.5.3 | [charset-normalizer on PyPI](https://pypi.org/project/charset-normalizer/3.5.3/) |
| filelock | 4.3.0 | 4.3.1 | [filelock on PyPI](https://pypi.org/project/filelock/4.3.1/) |
| python-discovery | 1.9.6 | 1.9.7 | [python-discovery on PyPI](https://pypi.org/project/python-discovery/1.9.7/) |

Both manifests pin ty and coverage. uv resolves the other three transitively.
The ty release replaces `mismatched-type-name` and renames `uv-metadata`.
The checkout has no configuration or suppressions for either identifier. The
existing rules and thresholds apply to the updated executable. Neither package
gains a runtime dependency. The local example retains version 0.1.0.

[Python releases](https://www.python.org/downloads/) select 3.14.10 for
the supported `>=3.14,<3.15` range under N-1 and 3.12.16 for the standalone
`>=3.12,<3.13` reference. Latest upstream stable is 3.15.2.
[XPPython3 4.8.0 installation guidance](https://xppython3.readthedocs.io/en/latest/usage/installation_plugin.html)
documents the integrated 3.12 runtime. Its installed patch and load behavior
remain unverified. The maintainer retains this host boundary and should recheck
the embedded runtime at the next host-dependent qualification.

uv and both uv_build declarations retain **0.13.9**. The uv compatibility
floor stays **>=0.13.5**. The workflow assets match their upstream release
digests. Exact official tags match the CI and catalog selections for checkout
**7.0.1**, setup-uv **10.4.0**, Superpowers **7.0.2**, gz-skills **0.14.0** and
disabled Backplane **0.3.0**. The publisher has no adopted starter template.
Native harness versions in the adoption notes identify tested hosts. The
repository does not install or pin machine-wide native harness executables.

The [Python 3.14 release notes](https://docs.python.org/3.14/whatsnew/3.14.html)
and [opportunity guide](../engineering/python314-opportunities.md) support
retaining the existing implementation. Path copying would require preservation
and rollback checks. The upgrades add no annotation introspection, large work
queue, compression or template processing consumer. Defer those API changes.
The standalone 3.12 baseline cannot use 3.14-specific APIs.

## Verification

- Both baselines passed repeated `uv lock --upgrade`, `uv lock --check`, and
  locked all-group sync, with the verification extra in the standard baseline.
  Both second resolutions left identical lock bytes and both
  `uv pip list --outdated --format json` checks returned `[]`.
- Both hashed `uv export --locked --all-groups --no-emit-local` requirements
  sets passed locked `pip-audit --require-hashes --no-deps --disable-pip`.
  Each covered 75 packages with zero known vulnerabilities and zero skips.
  The auditor emitted its generic redundant-flag and hashing advice.
- Managed 3.12.16 passed `tools/verify_xplane_baseline.py`, including its
  ty positive and `invalid-assignment` negative controls. On both exact
  interpreters, coverage 7.17.5 with its C extension collected and reported an
  instrumented Unicode decode and filelock exclusion/reacquisition probe.
  Virtualenv accepted each exact interpreter through python-discovery and
  created a working temporary environment. One invocation tightened its
  default cache directory to mode `0700`.
- `gz-starter validate`, bundled-resource parity and `gz-starter version`
  passed. The bundle, wheel resource, project metadata and CLI report 0.12.2.
- `uv run --locked pre-commit run --all-files --verbose` passed all four
  routine hooks on the stable candidate, with 135 unittest cases and one
  Windows-only skip. On the first run the tests passed and pre-commit detected
  a concurrent handoff edit. The rerun verified an identical tracked diff
  and status before and after execution. All 43 checker CLI tests passed.
- `uv build --no-sources` and `uv run --locked python tools/verify_distribution.py`
  passed on managed 3.14.10 with uv 0.13.9. These checks cover the sdist,
  wheel resources and isolated installed CLI, including adopter hook outcomes.

## Native update and limits

Codex CLI 0.171.0 originally had gz-skills **0.13.0** installed. The targeted
`codex plugin marketplace upgrade skills-first-starter --json` refreshed the
configured catalog at `55f1a6e419f4bbcdc7bb525275dcf735f4039292`. Fresh native
resolution loaded **0.14.0** at `0cbd2359c64b473d6c109e1296118f2475057fbc`.
Installed inventory and source revision agree. User configuration digest and
effective starter plugin enablement were verified before and after the update.

Fresh app-server discovery at the root and `src/` found 15 Superpowers skills,
21 gz-skills skills from 0.14.0 and the starter's `update-gz-template` with no
errors. An outside-project session found none of these skills. Backplane was
disabled and absent from discovery. Desktop refresh and other native hosts
remain unverified for this maintenance pass.

Cognitive measurement remains **DEFERRED / UNKNOWN** under the standing
ceiling of 15. Cohesion remains adopter-owned. No analyzer implementation
changed. The [current handoff](../handoffs/2026-11-18-discipline-evaluation-handoff.md#0122-dependency-maintenance-save-point)
records the subsequent Git save-point authorization. Exact-source release
acceptance and publication remain pending.
