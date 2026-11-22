# Starter Skill Prefix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans as selected by the maintainer. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one discoverable `gzt-update-template` skill and a preservation-first upgrade for earlier adopters.

**Architecture:** Keep the authored skill and generated wheel resource as the source and distribution pair. Reuse the CLI discovery preflight and the adopter's three-way upgrade procedure. Keep verifier link compatibility independent from native installation.

**Tech Stack:** Managed CPython 3.14, uv, unittest, pre-commit, and Codex, Claude Code, and OpenCode project discovery.

**Spec:** [Approved starter-owned skill prefix](../specs/2026-11-22-starter-skill-prefix-design.md).

## Global Constraints

- The release target is 0.13.0 after the separately scoped 0.12.1 patch. Recheck the published baseline and actual post-patch code before executing.
- The `gzt-` convention applies to starter-owned skills. Preserve upstream identifiers, CLI and package names, state format, activation scope and verification coverage.
- Work on `main` and preserve unrelated work. Use locked uv and unittest. Published tags and historical evidence remain intact.
- Verify the native discovery link edit is permitted. The current workspace exposes `.agents/` as read-only. Use the applicable workspace permission procedure if that restriction remains at execution.

## Review Focus

- Preview and apply on all three host selections write exactly one new skill and preserve existing AGENTS content.
- Old-only and dual-name discovery fail before configuration writes, including an edited legacy copy.
- A standalone verifier can read the exact old checkout link. Wrong-name, wrong-target, and dangling links still fail.
- An installed wheel emits the canonical skill. The source distribution and generated resources exclude the retired skill path.
- An authorized upgrade preserves local edits, and rollback restores the old skill and its references together.

## Task 1: Ship the canonical skill and preserve discovery boundaries

**Files:** `src/skills_first_starter/{native.py,cli.py,verification_inventory.py}`, `templates/skills/`, `.agents/skills/`, `tools/package_resources.py`, `templates/AGENTS.skills-first.md`, generated resources, `tests/{test_starter.py,test_native_hosts.py,test_verification.py}`, and `tools/verify_distribution.py`.

**Interfaces:** Keep `update_skill_path(host: str) -> str`. It returns `.claude/skills/gzt-update-template/SKILL.md` for Claude and `.agents/skills/gzt-update-template/SKILL.md` for Codex and OpenCode. All other CLI signatures remain unchanged.

- [ ] Extend the existing adoption tests to assert the exact path and `name: gzt-update-template` for every host. Add old-only and dual-name cases with edited legacy bytes and assert `configure --apply` refuses, identifies the legacy path, and leaves the fixture unchanged.
- [ ] Extend the verifier's existing alias tests with exact new and legacy link or Windows materialized-link cases. Assert failure for a cross-name target, dangling target, and arbitrary linked input. Run the affected unittest modules and capture reached assertion failures for behavior missing from the previous implementation.
- [ ] Rename the authored directory and update frontmatter, checkout discovery link, CLI output/source paths, instructions, and wheel resource manifest. Reuse a canonical skill ID constant for the runtime paths. In the existing discovery preflight, reject the legacy ID on each scanned surface with recovery guidance to `docs/updating.md`, and retain the canonical alternate-surface check. Leave activation-only `localize` behavior intact.
- [ ] Match both verifier alias names only to their corresponding exact targets. Preserve inventory behavior for ordinary skill directories and existing unsupported-link diagnostics. Regenerate using `uv run --locked python tools/package_resources.py`, remove the retired generated directory as part of the rename, and update the installed-distribution assertions for one canonical copy.
- [ ] Run `uv run --locked python -m unittest discover -s tests -p 'test_starter.py' -v`. Run the same command with `test_native_hosts.py` and `test_verification.py`. Confirm zero failures and report platform-only skips.

## Task 2: Document, rehearse, and verify the migration

**Files:** `README.md`, `docs/{updating,structure,architecture,adoption,adoption-workflow,adoption-0.5,rename-gz-starter}.md`, `docs/engineering/naming-and-layout.md`, `CHANGELOG.md`, `ROADMAP.md`, `bundle.json`, `pyproject.toml`, `uv.lock`, and generated bundle resource.

- [ ] Update current instructions while retaining the old ID where it identifies historical releases or an upgrade input. In `docs/updating.md`, specify the original/current/candidate comparison, merge and reference update, removal of the legacy path from discovery, exact rollback set, and fresh-session checks. Keep the legacy skill and documentation entry usable from older pinned releases during the transition.
- [ ] Rehearse the procedure in an invented adopter with an edited legacy skill. Confirm the preflight refuses before reconciliation. Apply the reviewed migration in the fixture and verify local edits, provenance, profile, and host settings. Exercise rollback from its saved revision and verify restored legacy behavior. Report managed-content conflicts for an intentionally customized copy.
- [ ] Reconcile 0.13.0 in the bundle, package, uv-owned lock, generated bundle and unreleased changelog once the minor becomes active. Match `gz-starter version` to the mirrors and verify the actual published baseline against Git and GitHub.
- [ ] Run `uv run --locked pre-commit run --all-files --verbose`, `uv run --locked gz-starter validate`, `uv run --locked python tools/package_resources.py --check`, `uv build --no-sources`, and `uv run --locked python tools/verify_distribution.py`. Check changed documentation links and `git diff --check`.
- [ ] Use fresh native sessions on each supported host to prove the exact candidate exposes the new skill once and the old skill is absent from project discovery. Check the adopted and outside-project controls where available. Requalify affected verifier inputs on the required hosted macOS and Windows runners. Record actual source/fixture SHAs and observed results. Report unavailable checks as pending and keep acceptance and publication distinct.
