# Post-release dependency maintenance — November 21, 2026

Mode: **update**, requested through `gzs-update-dependencies`, from clean
`main` at `dcce721c9621be36814ad922bec67b56f5131f53` (rollback reference).
Official queries ran November 22 UTC / November 21 America/Chicago. The
[structured receipt](2026-11-21-post-release-dependencies.json) records every
selected package, current stable target, source, input hash and audit result.

## Scope and version decision

The published baseline remains **0.12.0**, immutable source
`7303deff043231d8bcbb789e52efdbdde6b7e2f0`; its
[publication record](2026-11-21-0.12.0-release.md) and live GitHub release agree.
This pass restores the installed plugin to the repository's already-selected
version and verifies both existing Python resolutions. No repository dependency
pin, public behavior, configuration or policy changes. Retain 0.12.0 and its
version mirrors; select no new release target for this evidence-only closeout.
No commit, push, tag or release is performed by this maintenance request.

Inventory covers both independent pyprojects/locks and all dependency groups,
the verification extra, exact Python pins, uv compatibility floor and CI
reference, root/example build backends, four hooks, both Actions, workflow uv
archives/digests, bundled components and Codex/Claude/OpenCode bindings.
The example remains local development-only; helper/example runtime dependencies
remain empty. This is the canonical publisher, with no adopted template to
migrate. Keep cohesion adopter-owned and the cognitive engine deferred.

## Live selections and completed migration

All **77** registry projects match the latest stable, non-yanked release with
published artifacts. This includes uv/uv_build **0.13.9**, Ruff **0.17.6**,
ty **0.0.107** and pre-commit **4.7.0**. Both `uv lock --upgrade` runs in each
baseline preserve the exact published lock bytes. Both outdated checks return
`[]`. No package, source, group, edge, backend or constraint needs changing.

[Python's official release list](https://www.python.org/downloads/) confirms
**3.14.10** and **3.12.16** within the approved families; latest stable upstream
is **3.15.2**. The FTP index also contains a 3.16.0 directory, which is not
stable-release evidence. Retain the deliberate N-1 family and embedded-host
reference; no runtime pin changes. Actual checks use managed CPython 3.14.10
and 3.12.16 with uv 0.13.9 on macOS ARM64. Preserve uv **>=0.13.5** without an
upper bound.

Official GitHub release metadata and resolved commits retain checkout **7.0.1**,
setup-uv **10.4.0**, SP **7.0.2**, gz-skills **0.14.0** and disabled Backplane
**0.3.0** at their exact recorded SHAs. The macOS/Windows workflow archive
digests match the official uv release assets. Both catalogs and all development
source and activation bindings already select this current combination.

The installed Codex gz-skills initially remained **0.13.0**, including fresh
root/nested discovery. The maintainer clarified that gz-skills is a dependency
and explicitly directed its update. Treat installation scope as a constraint on
the update method, rather than a reason to omit this dependency.

`codex plugin marketplace upgrade skills-first-starter --json` refreshed only
the named native marketplace to the configured catalog
`55f1a6e419f4bbcdc7bb525275dcf735f4039292`, with no errors. A fresh native
runtime then materialized **gz-skills 0.14.0**. Installed inventory and actual
Git HEAD agree at `0cbd2359c64b473d6c109e1296118f2475057fbc`; its tracked skill
source is clean. No plugin-add command or manual cache edit was used.

Fresh Codex CLI **0.170.0** app-server `skills/list` calls with `forceReload`
find **21 gz-skills skills** and **15 SP skills**, with zero errors, at both
root and `src/`. All gz-skills entries resolve under 0.14.0. An outside-project
control finds no enabled starter plugins. User configuration hashes remain
identical before/after; activation and disabled Backplane are preserved.
The changed `gzs-agent-context-diet` is version **0.2.0**. Reuse the bounded
[exact-source component qualification](2026-11-21-0.11.5-release.md#component-requalification)
and its upstream rehearsal; no new model-equivalence claim is made here.

Review of the [Python 3.14 opportunity guide](../engineering/python314-opportunities.md)
and [versioned release notes](https://docs.python.org/3.14/whatsnew/3.14.html)
identifies no new annotation-introspection, executor, compression or template
processing need in this maintenance. Keep existing source semantics and
exclusive-write preservation; defer new machinery. Those 3.14 APIs remain
unavailable to the standalone 3.12 reference.

## Verification and limits

- Both baselines: repeated upgrade resolution, exact all-group sync,
  `uv lock --check` and empty outdated queries pass. The root sync includes
  `--extra verification`; neither lock changes.
- Separate fully hashed locked exports audited with each environment's pinned
  `pip-audit`: **75 packages each, zero known vulnerabilities, zero skips**.
  `--require-hashes --no-deps --disable-pip` preserves the lock's resolution.
  The auditor emits generic redundant-flag/hashing advice; structured results
  account for every exported registry package.
- `uv run --locked pre-commit run --all-files --verbose`: all four routine
  hooks pass; **128 unittest tests**, one Windows junction case skipped on
  macOS. No rules, assertions, thresholds or hook selections change.
- `uv run --locked gz-starter validate`, packaged-resource parity and actual
  CLI version pass. All version mirrors remain 0.12.0.
- Standalone X-Plane Ruff, ty and unittest controls pass on managed 3.12.16.
  No analyzer changes occur; the same-session 43 checker tests passed before
  this pass on identical owning inputs.
- `uv build --no-sources` and
  `uv run --locked python tools/verify_distribution.py` pass with the
  maintenance receipts included: source-independent sdist-to-wheel build,
  archive/resources and isolated installed CLI/example checks.

No new changed-tool compatibility probe is needed for unchanged package/tool
selections. Native update acceptance above exercises actual source resolution,
discovery and activation boundaries. The CLI's sandbox PATH-alias and remote
marketplace-enumeration warnings do not prevent local installed inventory or
fresh project discovery; no remote-catalog completeness claim is made.

Retain cognitive **DEFERRED / measurement UNKNOWN**, ceiling 15, adopter-owned
cohesion and actual embedded-XPPython3 UNKNOWN. Existing desktop conversation
refresh and other-host behavior remain unverified. This pass does not repeat
release qualification or publish a release. The current conversation's loaded
skill catalog may retain its original snapshot; fresh native sessions verify
the updated source.

## Git save point

The maintainer subsequently invoked `gzs-git-sync`, authorizing ordinary commit
and push of these two receipts and the current handoff on `main`. Fresh fetch
found local and remote aligned at the rollback reference above. Preserve normal
hooks and immutable releases. Run the integration gate and review the staged
three-file scope; report final local/remote SHA equality and exact-commit CI in
the sync response without a CI-receipt-only follow-up commit. Published 0.12.0
and its version mirrors remain unchanged. No release is requested.
