"""Check the embedded starter release history without running git on this checkout.

The history file is generated from the starter's commits by
``tools/build_release_history.py`` outside the gate. These tests read only the
committed file, except the revision-map tests, which build a throwaway
repository in a temporary directory. Blob ids and SHAs below were read once from
this repository's history; the tests compare against them without running git.
"""

import dataclasses
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from gzlite.gitenv import clean_git_env
from gzlite.history import (
    History,
    HistoryError,
    ManagedPath,
    Release,
    load_history,
    parse_history,
)

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools/build_release_history.py"

# Tag -> commit, read from this repository's immutable tags.
TAGS = {
    "v0.1.0": "b3dd0e47095499bd07f33448b38166221c2c1eec",
    "v0.2.0": "f64caeb0702ab0cba823a81512f22b3f15f76d48",
    "v0.3.0": "a7550a6e29b88349041e70e3dbba4778be4b8235",
    "v0.4.0": "b6f76dd75b4e6e779d6364cce0ff65bd73fda93a",
    "v0.4.1": "0a93e18fda328f84fda955d6bc182f34e5d4febf",
    "v0.5.0": "822d86f2f271015cd913d9a79231cf11e614898a",
    "v0.6.0": "c0a6945b2170e1cf5bee3e80738916f5b62d13a5",
    "v0.7.0": "a02635dad451f8f89c7801c2cbc02e2ec453d369",
    "v0.7.1": "27594dbaec853e6bde037b0aaf3f0427a3f053f9",
    "v0.8.0": "e0b752fcc13b87ec7868fe0b0f85badefdb6bf52",
    "v0.9.0": "3f76acf0038b030bf5abd85ce4a419e890d3e420",
    "v0.10.0": "6b236d87f301f689edae6934dabee9495df726d4",
    "v0.11.0": "ccac3b5e1ac03f2cf5642d7766aed6e68001997c",
    "v0.11.1": "041c1989406c1b9c4978042661c2dd38ff1db160",
    "v0.11.2": "1175433c950d47d5330e4a9a36a986f1a0c6ae26",
    "v0.11.3": "309c1a204174d802c69fc7e3c4d65ec236abe121",
    "v0.11.4": "75f0d83d1b7f4b073d31b06c85cdb20c6ef0cd63",
    "v0.11.5": "0d3be366bc3048ed123d36dd6af93ad4d8850b80",
    "v0.11.6": "6a44715f5fc40048c9767497a313a279dfc3a12a",
    "v0.12.0": "7303deff043231d8bcbb789e52efdbdde6b7e2f0",
    "v0.12.1": "a1c3550eac441b0a7beaddc66fb00c58ce0f1e6a",
    "v0.13.0": "98acc5aeec3f3b6ad61171a647dbc0ab7a44b7c6",
}
# windows-health's lock records 0.3.2 at this revision; 0.3.2 was never tagged.
WINDOWS_HEALTH = "88928b2c6c663e37f739c80376dae42b5d8e5b4e"
# Git blob ids of templates/AGENTS.skills-first.md at that revision and at v0.3.0.
WINDOWS_HEALTH_FRAGMENT_BLOB = "47d3412f8855b435fb3094800f9373d1ecdc3758"
V0_3_0_FRAGMENT_BLOB = "b8eb7cfd98087cc3ad370f174dc449fcda75dd91"
# Untagged commits after v0.9.0 that already declare 0.10.0, before and after the
# ADR policy placeholders entered the fragment.
EARLY_0_10_0 = "1dd24b2a52249e22170a102bb0c363daae3e243b"
EARLY_0_10_0_WITH_ADR = "e373f89cfed10dabd9311d16b3e1daea16930967"
ORIGIN_BASE = "https://github.com/tvproductions/"


def version_key(tag: str) -> tuple[int, ...]:
    return tuple(int(part) for part in tag.removeprefix("v").split("."))


def blob_id(text: str) -> str:
    """Compute the git blob id of ``text`` without running git."""
    data = text.encode("utf-8")
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = load_history()
        cls.by_tag = {release.tag: release for release in cls.history.releases}

    def releases_between(self, first: str, last: str) -> list[Release]:
        low, high = version_key(first), version_key(last)
        return [r for r in self.history.releases if low <= version_key(r.tag) <= high]

    def test_lists_every_starter_tag_with_its_commit(self):
        self.assertIsInstance(self.history, History)
        self.assertEqual({r.tag: r.revision for r in self.history.releases}, TAGS)
        self.assertEqual([r.tag for r in self.history.releases], list(TAGS))
        for release in self.history.releases:
            self.assertEqual(release.version, release.tag.removeprefix("v"))

    def test_untagged_adopter_revision_uses_its_own_snapshot(self):
        release = self.history.release_for(WINDOWS_HEALTH)
        self.assertEqual(release.version, "0.3.2")
        self.assertEqual(release.tag, "v0.3.0")
        self.assertEqual(release.revision, WINDOWS_HEALTH)
        self.assertEqual(blob_id(release.fragment_template), WINDOWS_HEALTH_FRAGMENT_BLOB)
        self.assertEqual(blob_id(self.by_tag["v0.3.0"].fragment_template), V0_3_0_FRAGMENT_BLOB)
        self.assertNotEqual(release.snapshot, self.by_tag["v0.3.0"].snapshot)

    def test_commit_declaring_a_version_before_its_tag(self):
        early = self.history.release_for(EARLY_0_10_0)
        self.assertEqual((early.version, early.tag), ("0.10.0", "v0.9.0"))
        self.assertFalse(early.adr_placeholders)
        release = self.history.release_for(EARLY_0_10_0_WITH_ADR)
        self.assertEqual((release.version, release.tag), ("0.10.0", "v0.9.0"))
        self.assertTrue(release.adr_placeholders)
        self.assertIn("{{ADR_POLICY_CANONICAL_URL}}", release.fragment_template)
        self.assertIn("{{ADR_POLICY_WORKING_SOURCE}}", release.fragment_template)
        self.assertIsNotNone(release.adr_policy_template)

    def test_tag_commits_resolve_to_their_own_release(self):
        for tag, revision in TAGS.items():
            with self.subTest(tag=tag):
                self.assertEqual(self.history.release_for(revision).tag, tag)

    def test_revision_outside_history_raises(self):
        with self.assertRaises(HistoryError):
            self.history.release_for("b" * 40)

    def test_every_mapped_revision_names_a_listed_release(self):
        self.assertTrue({entry.tag for entry in self.history.revisions.values()} <= set(TAGS))
        self.assertTrue(set(TAGS.values()) <= set(self.history.revisions))
        for release in self.history.releases:
            self.assertEqual(self.history.revisions[release.revision].snapshot, release.snapshot)

    def test_identical_snapshots_are_stored_once(self):
        used = {entry.snapshot for entry in self.history.revisions.values()}
        self.assertEqual(used, set(self.history.snapshots))
        self.assertLess(len(self.history.snapshots), len(self.history.revisions))

    def test_state_directory_moves_at_0_12_1(self):
        for release in self.releases_between("v0.1.0", "v0.12.0"):
            with self.subTest(tag=release.tag):
                self.assertEqual(release.state_directory, ".skills-first")
        for release in self.releases_between("v0.12.1", "v0.13.0"):
            with self.subTest(tag=release.tag):
                self.assertEqual(release.state_directory, ".gz-starter")

    def test_marketplace_is_versioned_from_0_13_0(self):
        for release in self.releases_between("v0.1.0", "v0.12.1"):
            with self.subTest(tag=release.tag):
                self.assertEqual(release.marketplace, "skills-first-starter")
        self.assertEqual(self.by_tag["v0.13.0"].marketplace, "gz-starter-0-13-0")

    def test_origin_follows_repository_renames(self):
        ranges = (
            ("v0.1.0", "v0.3.0", "skills-first-starter.git"),
            ("v0.4.0", "v0.9.0", "gz-skills-first-starter.git"),
            ("v0.10.0", "v0.13.0", "gz-starter.git"),
        )
        for first, last, name in ranges:
            for release in self.releases_between(first, last):
                with self.subTest(tag=release.tag):
                    self.assertEqual(release.origin, ORIGIN_BASE + name)

    def test_hosts_grow_at_0_8_0(self):
        for release in self.releases_between("v0.1.0", "v0.7.1"):
            with self.subTest(tag=release.tag):
                self.assertEqual(release.hosts, ("codex",))
        for release in self.releases_between("v0.8.0", "v0.13.0"):
            with self.subTest(tag=release.tag):
                self.assertEqual(release.hosts, ("claude", "codex", "opencode"))
        for release in self.history.releases:
            self.assertEqual(tuple(sorted(release.managed_paths)), release.hosts)

    def test_managed_skills_follow_the_release(self):
        for release in self.history.releases:
            with self.subTest(tag=release.tag):
                if version_key(release.tag) < (0, 6, 0):
                    self.assertIsNone(release.update_skill)
                    self.assertIsNone(release.update_skill_template)
                else:
                    self.assertEqual(release.update_skill, "update-gz-template")
                    template = release.update_skill_template or ""
                    self.assertTrue(template.startswith("---\nname: update-gz-template\n"))
                if release.tag in ("v0.1.0", "v0.2.0"):
                    self.assertEqual(release.front_door_skill, "skills-first-start")
                    template = release.front_door_skill_template or ""
                    self.assertTrue(template.startswith("---\nname: skills-first-start\n"))
                else:
                    self.assertIsNone(release.front_door_skill)
                    self.assertIsNone(release.front_door_skill_template)

    def test_adr_policy_placeholders_start_at_0_10_0(self):
        for release in self.history.releases:
            with self.subTest(tag=release.tag):
                expected = version_key(release.tag) >= (0, 10, 0)
                self.assertIs(release.adr_placeholders, expected)
                self.assertIs("{{ADR_POLICY_CANONICAL_URL}}" in release.fragment_template, expected)
                self.assertIs(release.adr_policy_template is not None, expected)
                self.assertIs(release.adr_policy_url is not None, expected)
        url = self.by_tag["v0.13.0"].adr_policy_url
        self.assertEqual(
            url,
            "https://github.com/tvproductions/gz-starter/blob/{ref}/"
            "docs/engineering/architectural-decisions.md",
        )

    def test_managed_paths_match_each_release_configure(self):
        self.assertEqual(
            list(self.by_tag["v0.1.0"].managed_paths["codex"]),
            [
                "merged:.codex/config.toml",
                ".skills-first/bundle.lock.json",
                "AGENTS.skills-first.md",
                ".agents/skills/skills-first-start/SKILL.md",
                "if-absent:AGENTS.md",
            ],
        )
        self.assertEqual(
            list(self.by_tag["v0.3.0"].managed_paths["codex"]),
            [
                "merged:.codex/config.toml",
                ".skills-first/bundle.lock.json",
                "AGENTS.skills-first.md",
                "if-absent:AGENTS.md",
            ],
        )
        self.assertEqual(
            list(self.by_tag["v0.13.0"].managed_paths["claude"]),
            [
                "merged:.claude/settings.json",
                ".gz-starter/bundle.lock.json",
                "AGENTS.skills-first.md",
                ".claude/skills/update-gz-template/SKILL.md",
                "if-absent:AGENTS.md",
                "adr-local:.gz-starter/architectural-decisions.md",
            ],
        )
        self.assertEqual(
            list(self.by_tag["v0.10.0"].managed_paths["opencode"]),
            [
                "merged:opencode.json",
                "merged-if-exists:opencode.jsonc",
                ".skills-first/bundle.lock.json",
                "AGENTS.skills-first.md",
                ".agents/skills/update-gz-template/SKILL.md",
                "if-absent:AGENTS.md",
                "adr-local:.skills-first/architectural-decisions.md",
            ],
        )

    def test_managed_entries_parse_markers(self):
        entries = self.by_tag["v0.13.0"].managed_entries("codex")
        self.assertIn(ManagedPath(".codex/config.toml", "merged"), entries)
        self.assertIn(ManagedPath(".gz-starter/bundle.lock.json", "always"), entries)
        self.assertIn(ManagedPath("AGENTS.md", "if-absent"), entries)
        self.assertIn(ManagedPath(".gz-starter/architectural-decisions.md", "adr-local"), entries)
        with self.assertRaises(HistoryError):
            self.by_tag["v0.7.1"].managed_entries("claude")

    def test_lock_keys_record_what_each_release_wrote(self):
        self.assertEqual(
            list(self.by_tag["v0.1.0"].lock_keys), ["schema_version", "starter", "components"]
        )
        self.assertEqual(
            list(self.by_tag["v0.8.0"].lock_keys),
            ["schema_version", "starter", "components", "host"],
        )
        self.assertEqual(
            list(self.by_tag["v0.13.0"].lock_keys),
            ["schema_version", "starter", "components", "adr_policy", "host"],
        )

    def test_default_agents_file_is_recorded(self):
        for release in self.history.releases:
            with self.subTest(tag=release.tag):
                self.assertIn("AGENTS.skills-first.md", release.agents_md_template)

    def test_committed_file_is_canonical(self):
        raw = files("gzlite").joinpath("resources/release_history.json").read_bytes()
        self.assertNotIn(b"\r", raw)
        canonical = json.dumps(json.loads(raw), indent=2, sort_keys=True) + "\n"
        self.assertEqual(raw, canonical.encode("utf-8"))

    def test_schema_documents_every_release_field(self):
        schema = json.loads(
            files("gzlite")
            .joinpath("resources/schemas/release-history.schema.json")
            .read_text(encoding="utf-8")
        )
        identity = {"tag", "revision", "snapshot"}
        fields = {field.name for field in dataclasses.fields(Release)} - identity
        snapshot = schema["$defs"]["snapshot"]
        self.assertEqual(set(snapshot["required"]), fields)
        self.assertEqual(set(snapshot["properties"]), fields)
        self.assertEqual(set(schema["$defs"]["release"]["required"]), identity)

    def test_release_fields_are_immutable(self):
        release = self.by_tag["v0.13.0"]
        self.assertIsInstance(release.managed_paths["codex"], tuple)
        self.assertIsInstance(release.lock_keys, tuple)
        with self.assertRaises(TypeError):
            cast(Any, release.managed_paths)["codex"] = ()

    def test_loader_rejects_managed_paths_that_do_not_match_hosts(self):
        raw = files("gzlite").joinpath("resources/release_history.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        snapshot = data["snapshots"][self.by_tag["v0.13.0"].snapshot]
        del snapshot["managed_paths"]["claude"]
        with self.assertRaises(HistoryError):
            parse_history(json.dumps(data))


def git(cwd: Path, *args: str) -> str:
    """Run git in a temporary repository, isolated from inherited and global settings."""
    settings = (
        "user.name=t",
        "user.email=t@example.invalid",
        "commit.gpgsign=false",
        "tag.gpgsign=false",
        # A directory that never exists: no global hook can run in the fixture.
        f"core.hooksPath={cwd.parent / 'no-hooks'}",
    )
    options = [item for setting in settings for item in ("-c", setting)]
    return subprocess.run(
        ["git", "-C", str(cwd), *options, *args],
        cwd=cwd,
        env=clean_git_env(),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.strip()


class RevisionMapTests(unittest.TestCase):
    """Exercise the builder's nearest-tag rule against a throwaway repository."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve() / "starter"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        spec = importlib.util.spec_from_file_location("build_release_history", BUILDER)
        assert spec is not None and spec.loader is not None
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)

    def commit(self, name: str) -> str:
        (self.repo / f"{name}.txt").write_text(name, encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", name)
        return git(self.repo, "rev-parse", "HEAD")

    def test_each_commit_maps_to_its_latest_ancestor_tag(self):
        before = self.commit("before")
        first = self.commit("first")
        git(self.repo, "tag", "v0.1.0")
        git(self.repo, "checkout", "-q", "-b", "side")
        side = self.commit("side")
        git(self.repo, "checkout", "-q", "main")
        between = self.commit("between")
        second = self.commit("second")
        git(self.repo, "tag", "v0.2.0")
        git(self.repo, "merge", "--no-ff", "--no-edit", "-q", "side")
        merge = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "tag", "v0.3.0")
        after = self.commit("after")

        mapping = self.builder.revision_map(self.repo, ["v0.1.0", "v0.2.0"], "v0.3.0")

        self.assertEqual(
            mapping,
            {
                first: "v0.1.0",
                side: "v0.1.0",
                between: "v0.1.0",
                second: "v0.2.0",
                merge: "v0.2.0",
            },
        )
        self.assertNotIn(before, mapping)
        self.assertNotIn(after, mapping)

    def test_tags_out_of_ancestry_order_stop_the_build(self):
        self.commit("base")
        git(self.repo, "checkout", "-q", "-b", "side")
        self.commit("side")
        git(self.repo, "tag", "v0.2.0")
        git(self.repo, "checkout", "-q", "main")
        self.commit("main")
        git(self.repo, "tag", "v0.1.0")
        git(self.repo, "merge", "--no-ff", "--no-edit", "-q", "side")
        git(self.repo, "tag", "v0.3.0")

        with self.assertRaises(self.builder.BuildError):
            self.builder.revision_map(self.repo, ["v0.1.0", "v0.2.0"], "v0.3.0")


if __name__ == "__main__":
    unittest.main()
