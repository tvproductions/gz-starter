"""``gzlite migrate``: legacy gz-starter / skills-first state into gzlite state."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from fixtures_adopters import (
    FIXTURE_COMPONENTS,
    host_config,
    lock,
    managed_files,
    render_adopter,
)

from gzlite import cli
from gzlite.fingerprint import fingerprint
from gzlite.history import load_history
from gzlite.native import update_skill_path
from gzlite.native_json import document

REF = "a" * 40
WINDOWS_HEALTH = "88928b2c6c663e37f739c80376dae42b5d8e5b4e"
HISTORY = load_history()
TAGGED = {release.revision for release in HISTORY.releases}
LEGACY = (".gz-starter", ".skills-first")


def tagged(version: str):
    return next(release for release in HISTORY.releases if release.version == version)


class MigrateCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()
        inherited = mock.patch.object(cli, "_inherited_plugins", return_value={})
        inherited.start()
        self.addCleanup(inherited.stop)

    def tree(self, root: Path | None = None) -> dict[str, bytes]:
        root = root or self.root
        return {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }

    def run_cli(self, *args: str, root: Path | None = None) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        argv = ["migrate", "--project", str(root or self.root), "--starter-ref", REF, *args]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def preview(self, root: Path | None = None) -> dict:
        code, out, err = self.run_cli(root=root)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def apply(self, root: Path | None = None) -> dict:
        planned = self.preview(root)
        code, out, err = self.run_cli("--apply", "--fingerprint", planned["fingerprint"], root=root)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def refused(self, *args: str, root: Path | None = None) -> str:
        root = root or self.root
        before = self.tree(root)
        code, out, err = self.run_cli(*args, root=root)
        self.assertEqual(code, 2, out)
        self.assertTrue(err.startswith("adoption blocked: "), err)
        self.assertEqual(self.tree(root), before)
        return err

    @staticmethod
    def edits(planned: dict) -> list[dict]:
        """Saved copies other than legacy state, which is always saved as a record."""
        return [i for i in planned["replaced"] if i["path"].split("/")[0] not in LEGACY]

    def saved_copies(self, root: Path | None = None) -> dict[str, bytes]:
        root = root or self.root
        folder = root / ".gzlite/migrated"
        return self.tree(folder) if folder.exists() else {}

    def new_lock(self, root: Path | None = None) -> dict:
        return json.loads(((root or self.root) / ".gzlite/bundle.lock.json").read_bytes())

    def edit_lock(self, release, change) -> None:
        path = self.root / release.state_directory / "bundle.lock.json"
        data = json.loads(path.read_bytes())
        change(data)
        path.write_text(json.dumps(data, indent=2) + "\n")


class FingerprintTests(unittest.TestCase):
    def test_stable_and_sensitive(self):
        value = fingerprint({"b": b"2", "a": b"1"}, {"plan": [1, 2]})
        self.assertRegex(value, r"\A[0-9a-f]{64}\Z")
        self.assertEqual(value, fingerprint({"a": b"1", "b": b"2"}, {"plan": [1, 2]}))
        self.assertNotEqual(value, fingerprint({"a": b"1", "b": b"3"}, {"plan": [1, 2]}))
        self.assertNotEqual(value, fingerprint({"a": b"1", "b": b"2"}, {"plan": [2, 1]}))


class EveryReleaseTests(MigrateCase):
    """Each tagged release, each host it supported, as its configure wrote it."""

    def check_migrated(self, root: Path, release, host: str) -> None:
        legacy_files = {
            name: data
            for name, data in self.tree(root).items()
            if name.startswith(release.state_directory + "/")
        }
        planned = self.preview(root)
        self.assertEqual(planned["status"], "preview")
        self.assertEqual(planned["from_version"], release.version)
        self.assertEqual(planned["from_revision"], release.revision)
        self.assertEqual(planned["to_version"], "0.14.0")
        self.assertEqual(self.edits(planned), [])
        self.assertTrue([f for f in planned["findings"] if "component pins move" in f])
        self.assertFalse([f for f in planned["findings"] if "never a tagged release" in f])
        written = [item["path"] for item in planned["writes"]]
        self.assertIn(".gzlite/bundle.lock.json", written)
        self.assertIn(update_skill_path(host), written)
        self.assertTrue(all(item["reason"] for item in planned["writes"]))

        result = self.apply(root)
        self.assertEqual(result["status"], "migrated")
        self.assertEqual(result["post_apply_status"]["status"], "configured")
        self.assertEqual(result["post_apply_status"]["pending_files"], [])
        new_lock = self.new_lock(root)
        self.assertEqual(
            new_lock["starter"],
            {"repository": cli.ORIGIN, "version": "0.14.0", "revision": REF},
        )
        self.assertEqual(new_lock["components"], cli.bundle()["components"])
        self.assertEqual(new_lock.get("host", "codex"), host)
        for legacy in LEGACY:
            self.assertFalse((root / legacy).exists(), legacy)
        # Only the legacy state is saved, byte for byte, and nothing is left staged.
        self.assertEqual(self.saved_copies(root), legacy_files)
        self.assertFalse((root / cli.STAGING_DIRECTORY).exists())
        self.assertFalse((root / ".gz-skills").exists())
        skill = root / update_skill_path(host)
        self.assertEqual(
            skill.read_bytes(),
            (cli.HERE / cli.UPDATE_SKILL_SOURCE).read_text(encoding="utf-8").encode(),
        )
        for old in (release.update_skill, release.front_door_skill):
            for surface in (".agents", ".claude"):
                if old:
                    self.assertFalse((root / surface / "skills" / old).exists(), old)
        self.check_host_config(root, release, host)
        self.assertEqual(cli.status(root)["status"], "configured")
        self.assertEqual(cli.status(root)["pending_files"], [])
        before = self.tree(root)
        again = self.preview(root)
        self.assertEqual(again["status"], "nothing to migrate")
        self.assertEqual(again["writes"], [])
        self.assertEqual(self.tree(root), before)

    def check_host_config(self, root: Path, release, host: str) -> None:
        current = cli.marketplace()
        if host == "codex":
            data = tomllib.loads((root / ".codex/config.toml").read_text())
            self.assertEqual(set(data["marketplaces"]), {current})
            self.assertEqual(data["marketplaces"][current]["ref"], REF)
            self.assertFalse([k for k in data["plugins"] if k.endswith("@" + release.marketplace)])
        elif host == "claude":
            data = json.loads((root / ".claude/settings.json").read_bytes())
            self.assertEqual(set(data["extraKnownMarketplaces"]), {current})
            self.assertFalse(
                [k for k in data["enabledPlugins"] if k.endswith("@" + release.marketplace)]
            )
        else:
            data, _ = document((root / "opencode.json").read_text())
            pins = [p for p in data["plugins"] if p.startswith("git+")]
            expected = [
                f"git+{p['repository']}.git#{p['revision']}"
                for p in cli.bundle()["components"]
                if p["enabled_by_default"]
            ]
            self.assertEqual(pins, expected)

    def test_every_tagged_release_and_host_migrates(self):
        self.assertEqual(len(HISTORY.releases), 22)
        combinations = 0
        for release in HISTORY.releases:
            modes = ("link", "local") if "adr_policy" in release.lock_keys else ("link",)
            for host in release.hosts:
                for mode in modes:
                    with self.subTest(release=release.version, host=host, mode=mode):
                        root = self.base / f"{release.version}-{host}-{mode}"
                        root.mkdir()
                        render_adopter(root, release, host, mode=mode)
                        self.check_migrated(root, release, host)
                        if mode == "local":
                            policy = self.new_lock(root)["adr_policy"]
                            self.assertEqual(
                                policy["local_path"], ".gzlite/architectural-decisions.md"
                            )
                            self.assertTrue((root / ".gzlite/architectural-decisions.md").is_file())
                        combinations += 1
        # 0.1.0-0.7.1: codex only. 0.8.0, 0.9.0: three hosts, no ADR policy yet.
        # 0.10.0-0.13.0 (11 tags): three hosts, link and local ADR policy.
        self.assertEqual(combinations, 9 + 2 * 3 + 11 * 3 * 2)

    def test_untagged_revision_migrates_from_its_own_snapshot_with_finding(self):
        release = HISTORY.release_for(WINDOWS_HEALTH)
        self.assertNotIn(WINDOWS_HEALTH, TAGGED)
        self.assertEqual(release.version, "0.3.2")
        render_adopter(self.root, release, "codex", WINDOWS_HEALTH)
        planned = self.preview()
        self.assertEqual(planned["from_version"], "0.3.2")
        self.assertEqual(planned["from_revision"], WINDOWS_HEALTH)
        self.assertEqual(self.edits(planned), [])
        notes = [f for f in planned["findings"] if "never a tagged release" in f]
        self.assertEqual(len(notes), 1)
        self.assertIn("0.3.2", notes[0])
        self.assertIn(WINDOWS_HEALTH, notes[0])
        self.assertEqual(self.apply()["status"], "migrated")
        self.assertEqual(cli.status(self.root)["pending_files"], [])

    def test_uppercase_revision_is_read(self):
        release = tagged("0.9.0")
        render_adopter(self.root, release, "codex")
        self.edit_lock(release, lambda d: d["starter"].update(revision=release.revision.upper()))
        self.assertEqual(self.preview()["from_revision"], release.revision)


class DriftTests(MigrateCase):
    def test_extra_lock_keys_are_carried(self):
        release = tagged("0.6.0")
        render_adopter(self.root, release, "codex")
        catalog = {"name": "fixture-skills-first", "source": "project-local", "reason": "fixture"}
        self.edit_lock(release, lambda d: d.update(catalog=catalog))
        planned = self.preview()
        self.assertTrue([c for c in planned["carried"] if "catalog" in c])
        self.apply()
        self.assertEqual(self.new_lock()["catalog"], catalog)
        self.assertEqual(cli.status(self.root)["status"], "configured")

    def test_extra_catalog_in_host_config_is_carried(self):
        release = tagged("0.13.0")
        render_adopter(self.root, release, "codex")
        config = self.root / ".codex/config.toml"
        extra = (
            '\n[marketplaces.fixture-catalog]\nsource_type = "git"\n'
            'source = "https://example.invalid/fixture.git"\nref = "v1"\n\n'
            '[plugins."fixture-tool@fixture-catalog"]\nenabled = true\n'
        )
        config.write_text(config.read_text() + extra)
        planned = self.preview()
        self.assertTrue([c for c in planned["carried"] if "fixture-catalog" in c])
        self.assertEqual(self.edits(planned), [])
        self.apply()
        data = tomllib.loads(config.read_text())
        self.assertIn("fixture-catalog", data["marketplaces"])
        self.assertTrue(data["plugins"]["fixture-tool@fixture-catalog"]["enabled"])

    def test_extra_claude_catalog_is_carried(self):
        release = tagged("0.11.0")
        render_adopter(self.root, release, "claude")
        path = self.root / ".claude/settings.json"
        data = json.loads(path.read_bytes())
        data["extraKnownMarketplaces"]["fixture-catalog"] = {"source": {"source": "directory"}}
        path.write_text(json.dumps(data, indent=2) + "\n")
        self.apply()
        data = json.loads(path.read_bytes())
        self.assertIn("fixture-catalog", data["extraKnownMarketplaces"])

    def test_edited_fragment_is_replaced_and_saved(self):
        release = tagged("0.12.1")
        render_adopter(self.root, release, "codex")
        fragment = self.root / "AGENTS.skills-first.md"
        edited = fragment.read_bytes() + b"\nLocal rule added by hand.\n"
        fragment.write_bytes(edited)
        planned = self.preview()
        self.assertEqual(
            self.edits(planned),
            [
                {
                    "path": "AGENTS.skills-first.md",
                    "saved_to": ".gzlite/migrated/AGENTS.skills-first.md",
                }
            ],
        )
        self.apply()
        self.assertEqual(
            (self.root / ".gzlite/migrated/AGENTS.skills-first.md").read_bytes(), edited
        )
        self.assertNotIn(b"Local rule added by hand.", fragment.read_bytes())
        self.assertEqual(cli.status(self.root)["pending_files"], [])

    def test_crlf_only_differences_are_not_edits(self):
        release = tagged("0.13.0")
        files = render_adopter(self.root, release, "codex")
        for name in files:
            if not name.endswith(".json"):
                path = self.root / name
                path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        planned = self.preview()
        self.assertEqual(self.edits(planned), [])
        self.apply()
        self.assertEqual(set(self.saved_copies()), {".gz-starter/bundle.lock.json"})
        self.assertEqual(cli.status(self.root)["pending_files"], [])

    def test_edited_update_skill_is_saved(self):
        release = tagged("0.7.1")
        render_adopter(self.root, release, "codex")
        skill = self.root / ".agents/skills/update-gz-template/SKILL.md"
        skill.write_text(skill.read_text() + "Local step.\n")
        planned = self.preview()
        saved = ".gzlite/migrated/.agents/skills/update-gz-template/SKILL.md"
        self.assertIn(
            {"path": ".agents/skills/update-gz-template/SKILL.md", "saved_to": saved},
            planned["replaced"],
        )
        self.apply()
        self.assertTrue((self.root / saved).read_text().endswith("Local step.\n"))
        self.assertFalse((self.root / ".agents/skills/update-gz-template").exists())

    def test_unknown_file_in_legacy_folder_is_saved(self):
        release = tagged("0.12.1")
        render_adopter(self.root, release, "codex")
        (self.root / ".gz-starter/notes.md").write_text("project notes\n")
        planned = self.preview()
        self.assertIn(
            {"path": ".gz-starter/notes.md", "saved_to": ".gzlite/migrated/.gz-starter/notes.md"},
            planned["replaced"],
        )
        self.apply()
        self.assertEqual(
            (self.root / ".gzlite/migrated/.gz-starter/notes.md").read_text(), "project notes\n"
        )
        self.assertFalse((self.root / ".gz-starter").exists())

    def test_edited_starter_marketplace_is_retired_and_config_saved(self):
        release = tagged("0.9.0")
        render_adopter(self.root, release, "codex")
        config = self.root / ".codex/config.toml"
        original = config.read_text().replace(
            f'source = "{release.origin}"\nref = "{release.revision}"',
            'source = "https://github.com/tvproductions/fixture-project.git"\nref = "main"',
        )
        config.write_text(original)
        planned = self.preview()
        self.assertIn(
            {"path": ".codex/config.toml", "saved_to": ".gzlite/migrated/.codex/config.toml"},
            planned["replaced"],
        )
        self.assertTrue([f for f in planned["findings"] if ".codex/config.toml" in f])
        guidance = [f for f in planned["findings"] if "To keep that catalog, re-add it" in f]
        self.assertEqual(len(guidance), 1)
        self.assertIn("catalog skills-first-starter pointed at", guidance[0])
        self.assertIn("fixture-project.git", guidance[0])
        self.assertIn("under a new name that no starter release uses", guidance[0])
        self.apply()
        self.assertEqual((self.root / ".gzlite/migrated/.codex/config.toml").read_text(), original)
        data = tomllib.loads(config.read_text())
        self.assertEqual(set(data["marketplaces"]), {cli.marketplace()})
        self.assertEqual(cli.status(self.root)["pending_files"], [])

    def test_both_claude_and_codex_configured_while_lock_records_codex(self):
        release = tagged("0.13.0")
        render_adopter(self.root, release, "codex")
        # Claude was configured by an earlier configure run, with its own update skill.
        for name, text in managed_files(release, "claude").items():
            if name.startswith(".claude/"):
                (self.root / name).parent.mkdir(parents=True, exist_ok=True)
                (self.root / name).write_text(text)
        old_claude_skill = self.root / ".claude/skills/update-gz-template/SKILL.md"
        self.assertTrue(old_claude_skill.is_file())
        claude = self.root / ".claude/settings.json"
        planned = self.preview()
        written = [item["path"] for item in planned["writes"]]
        self.assertIn(".codex/config.toml", written)
        self.assertIn(".claude/settings.json", written)
        self.assertIn(".claude/skills/gzl-update/SKILL.md", written)
        self.assertIn(".agents/skills/gzl-update/SKILL.md", written)
        self.assertEqual(self.edits(planned), [])
        self.assertTrue([c for c in planned["carried"] if "claude" in c])
        self.apply()
        self.assertEqual(
            sorted(p.name for p in (self.root / ".claude/skills").iterdir()), ["gzl-update"]
        )
        self.assertEqual(
            sorted(p.name for p in (self.root / ".agents/skills").iterdir()), ["gzl-update"]
        )
        report = cli.status(self.root)
        self.assertEqual(report["hosts"], ["codex", "claude"])
        self.assertEqual(report["pending_files"], [])
        current = cli.marketplace()
        self.assertEqual(
            set(tomllib.loads((self.root / ".codex/config.toml").read_text())["marketplaces"]),
            {current},
        )
        data = json.loads(claude.read_bytes())
        self.assertEqual(set(data["extraKnownMarketplaces"]), {current})
        self.assertEqual(
            data["enabledPlugins"],
            {
                p["name"] + "@" + current: p["enabled_by_default"]
                for p in cli.bundle()["components"]
            },
        )
        self.assertNotIn("host", self.new_lock())
        self.assertEqual(cli.status(self.root)["pending_files"], [])
        # status checks the second host too, not only the recorded one.
        (self.root / ".claude/skills/gzl-update/SKILL.md").write_text("drifted\n")
        self.assertEqual(
            cli.status(self.root)["pending_files"], [".claude/skills/gzl-update/SKILL.md"]
        )

    def test_claude_and_opencode_share_one_copy_when_claude_is_recorded(self):
        release = tagged("0.13.0")
        render_adopter(self.root, release, "claude")
        (self.root / "opencode.json").write_text(host_config(release, "opencode", REF))
        planned = self.preview()
        written = [item["path"] for item in planned["writes"]]
        self.assertIn(".claude/skills/gzl-update/SKILL.md", written)
        self.assertNotIn(".agents/skills/gzl-update/SKILL.md", written)
        self.assertTrue(
            [f for f in planned["findings"] if f.startswith("opencode is expected to discover")]
        )
        self.apply()
        self.assertEqual(cli.status(self.root)["hosts"], ["claude", "opencode"])
        self.assertEqual(cli.status(self.root)["pending_files"], [])

    def test_unavoidable_duplicate_leaves_one_host_without_and_says_so(self):
        release = tagged("0.13.0")
        render_adopter(self.root, release, "opencode")
        claude = self.root / ".claude/settings.json"
        claude.parent.mkdir()
        claude.write_text(host_config(release, "claude", release.revision))
        planned = self.preview()
        written = [item["path"] for item in planned["writes"]]
        self.assertIn(".agents/skills/gzl-update/SKILL.md", written)
        self.assertNotIn(".claude/skills/gzl-update/SKILL.md", written)
        self.assertTrue([f for f in planned["findings"] if f.startswith("claude is configured")])
        self.apply()
        self.assertEqual(cli.status(self.root)["pending_files"], [])

    def test_second_opencode_config_with_other_pins_is_migrated(self):
        release = tagged("0.13.0")
        render_adopter(self.root, release, "codex")
        ahead = tuple(dict(part, revision="c" * 40) for part in FIXTURE_COMPONENTS)
        opencode = self.root / "opencode.json"
        original = host_config(release, "opencode", REF, ahead)
        opencode.write_text(original)
        planned = self.preview()
        self.assertIn(
            {"path": "opencode.json", "saved_to": ".gzlite/migrated/opencode.json"},
            self.edits(planned),
        )
        self.apply()
        data, _ = document(opencode.read_text())
        self.assertFalse([p for p in data["plugins"] if "c" * 40 in p])
        self.assertEqual((self.root / ".gzlite/migrated/opencode.json").read_text(), original)
        self.assertEqual(cli.status(self.root)["hosts"], ["codex", "opencode"])
        self.assertEqual(cli.status(self.root)["pending_files"], [])

    def test_inline_comment_on_a_retired_table_is_saved(self):
        release = tagged("0.13.0")
        render_adopter(self.root, release, "codex")
        config = self.root / ".codex/config.toml"
        original = config.read_text().replace(
            "enabled = true", "enabled = true # chosen for this project", 1
        )
        config.write_text(original)
        planned = self.preview()
        self.assertIn(
            {"path": ".codex/config.toml", "saved_to": ".gzlite/migrated/.codex/config.toml"},
            self.edits(planned),
        )
        self.apply()
        self.assertEqual((self.root / ".gzlite/migrated/.codex/config.toml").read_text(), original)

    def test_opencode_jsonc_is_edited_in_place(self):
        release = tagged("0.10.0")
        render_adopter(self.root, release, "opencode")
        (self.root / "opencode.json").rename(self.root / "opencode.jsonc")
        jsonc = self.root / "opencode.jsonc"
        jsonc.write_text("// Project OpenCode settings.\n" + jsonc.read_text())
        planned = self.preview()
        self.assertIn("opencode.jsonc", [item["path"] for item in planned["writes"]])
        self.assertEqual(self.edits(planned), [])
        self.apply()
        self.assertFalse((self.root / "opencode.json").exists())
        text = jsonc.read_text()
        self.assertTrue(text.startswith("// Project OpenCode settings.\n"))
        data, _ = document(text)
        for part in cli.bundle()["components"]:
            if part["enabled_by_default"]:
                self.assertIn(f"git+{part['repository']}.git#{part['revision']}", data["plugins"])
        self.assertEqual(cli.status(self.root)["pending_files"], [])

    def test_hand_written_release_key_is_read_as_version(self):
        release = tagged("0.6.0")
        render_adopter(self.root, release, "codex")

        def hand_written(data):
            starter = data["starter"]
            data["starter"] = {
                "repository": starter["repository"],
                "release": "v0.6.0",
                "revision": starter["revision"],
            }

        self.edit_lock(release, hand_written)
        planned = self.preview()
        self.assertEqual(planned["from_version"], "0.6.0")
        self.assertEqual(self.apply()["status"], "migrated")
        self.assertEqual(self.new_lock()["starter"]["version"], "0.14.0")

    def test_component_pins_move_to_the_bundle_even_when_ahead(self):
        release = tagged("0.11.6")
        ahead = tuple(
            dict(part, revision="c" * 40) if part["name"] == "superpowers" else dict(part)
            for part in FIXTURE_COMPONENTS
        )
        render_adopter(self.root, release, "opencode", components=ahead)
        self.apply()
        self.assertEqual(self.new_lock()["components"], cli.bundle()["components"])
        data, _ = document((self.root / "opencode.json").read_text())
        self.assertFalse([p for p in data["plugins"] if "c" * 40 in p])

    def test_verification_dependency_is_renamed(self):
        release = tagged("0.12.0")
        render_adopter(self.root, release, "codex")
        old = (
            "gz-starter[verification] @ git+https://github.com/tvproductions/gz-starter.git@"
            + "d" * 40
        )
        project = (
            '[project]\nname = "fixture-app"\nversion = "0.1.0"\n\n'
            f'[dependency-groups]\ndev = [\n    "fixture-tool==1.0",\n    "{old}",\n]\n'
        )
        (self.root / "pyproject.toml").write_text(project)
        planned = self.preview()
        self.assertIn("pyproject.toml", [item["path"] for item in planned["writes"]])
        self.assertTrue([n for n in planned["next"] if "run uv lock" in n])
        self.apply()
        new = f"gzlite[verification] @ git+https://github.com/tvproductions/gzlite.git@{REF}"
        self.assertEqual((self.root / "pyproject.toml").read_text(), project.replace(old, new))

    def test_profile_settings_are_never_touched(self):
        release = tagged("0.12.1")
        render_adopter(self.root, release, "codex")
        settings = self.root / ".gz-skills/settings.json"
        settings.parent.mkdir()
        settings.write_bytes(b'{"schema_version": 1, "profile": "lite"}\n')
        self.apply()
        self.assertEqual(settings.read_bytes(), b'{"schema_version": 1, "profile": "lite"}\n')

    def test_bundle_activation_from_a_project_catalog_is_disabled(self):
        release = tagged("0.1.0")
        render_adopter(self.root, release, "codex")
        config = self.root / ".codex/config.toml"
        original = config.read_text() + '\n[plugins."superpowers@fixture-local"]\nenabled = true\n'
        config.write_text(original)
        planned = self.preview()
        self.assertIn(
            {"path": ".codex/config.toml", "saved_to": ".gzlite/migrated/.codex/config.toml"},
            planned["replaced"],
        )
        self.assertTrue([f for f in planned["findings"] if "superpowers@fixture-local" in f])
        self.assertIn(
            ".codex/config.toml: superpowers@fixture-local was active and is now disabled, so "
            "the gzlite-0-14-0 bundle is the only source of superpowers. To re-enable it, set "
            'enabled = true in [plugins."superpowers@fixture-local"] in .codex/config.toml; '
            "while gzlite's bundle provides superpowers, configure and status then refuse it "
            "as duplicate discovery",
            planned["findings"],
        )
        self.apply()
        data = tomllib.loads(config.read_text())
        self.assertIs(data["plugins"]["superpowers@fixture-local"]["enabled"], False)
        self.assertEqual(cli.status(self.root)["pending_files"], [])

    def test_edited_local_adr_policy_copy_is_saved(self):
        release = tagged("0.13.0")
        render_adopter(self.root, release, "codex", mode="local")
        copy = self.root / ".gz-starter/architectural-decisions.md"
        copy.write_text(copy.read_text() + "Local amendment.\n")
        planned = self.preview()
        saved = ".gzlite/migrated/.gz-starter/architectural-decisions.md"
        self.assertIn(
            {"path": ".gz-starter/architectural-decisions.md", "saved_to": saved},
            planned["replaced"],
        )
        self.apply()
        self.assertTrue((self.root / saved).read_text().endswith("Local amendment.\n"))
        self.assertEqual(
            (self.root / ".gzlite/architectural-decisions.md").read_bytes(),
            (cli.HERE / cli.ADR_POLICY_SOURCE).read_bytes(),
        )

    def test_claude_local_activation_of_the_old_catalog_is_refused(self):
        release = tagged("0.13.0")
        render_adopter(self.root, release, "claude")
        local = self.root / ".claude/settings.local.json"
        local.write_text(
            json.dumps({"enabledPlugins": {f"superpowers@{release.marketplace}": True}}) + "\n"
        )
        before = self.tree()
        code, _, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn("superpowers@gz-starter-0-13-0", err)
        self.assertEqual(self.tree(), before)


class FingerprintAndRerunTests(MigrateCase):
    def setUp(self):
        super().setUp()
        self.release = tagged("0.13.0")
        render_adopter(self.root, self.release, "claude")

    def test_preview_twice_is_byte_identical_and_writes_nothing(self):
        before = self.tree()
        first = self.run_cli()
        second = self.run_cli()
        self.assertEqual(first[0], 0, first[2])
        self.assertEqual(first, second)
        self.assertEqual(self.tree(), before)
        self.assertRegex(json.loads(first[1])["fingerprint"], r"\A[0-9a-f]{64}\Z")

    def test_wrong_fingerprint_writes_nothing(self):
        err = self.refused("--apply", "--fingerprint", "0" * 64)
        self.assertIn("fingerprint", err)

    def test_apply_requires_a_fingerprint(self):
        self.refused("--apply")
        self.refused("--apply", "--fingerprint", "not-hex")

    def test_changed_input_invalidates_the_fingerprint(self):
        planned = self.preview()
        # A line-ending-only change leaves the plan alone but is a different input.
        fragment = self.root / "AGENTS.skills-first.md"
        fragment.write_bytes(fragment.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(self.edits(self.preview()), [])
        self.refused("--apply", "--fingerprint", planned["fingerprint"])

    def test_rerun_after_apply_is_nothing_to_migrate(self):
        self.apply()
        before = self.tree()
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["status"], "nothing to migrate")
        self.assertEqual(result["writes"], [])
        self.assertIsNone(result["fingerprint"])
        self.assertEqual(self.tree(), before)

    def test_failure_during_apply_rolls_everything_back(self):
        planned = self.preview()
        before = self.tree()
        real_rmdir = os.rmdir

        def fail_on_legacy(path, *args, **kwargs):
            # The legacy folder is removed last, after every write and delete.
            if Path(path).resolve() == (self.root / ".gz-starter").resolve():
                raise OSError("fixture failure")
            return real_rmdir(path, *args, **kwargs)

        with mock.patch.object(cli.os, "rmdir", side_effect=fail_on_legacy):
            code, _, err = self.run_cli("--apply", "--fingerprint", planned["fingerprint"])
        self.assertEqual(code, 2, err)
        self.assertIn("rolled back", err)
        # Everything is as before, except that the saved copies are kept.
        after = self.tree()
        kept = {name: after.pop(name) for name in list(after) if name.startswith(".gzlite/")}
        self.assertEqual(after, before)
        self.assertEqual(
            kept[".gzlite/migrated/.gz-starter/bundle.lock.json"],
            before[".gz-starter/bundle.lock.json"],
        )
        self.assertTrue(all(name.startswith(".gzlite/migrated/") for name in kept))
        self.assertFalse((self.root / cli.STAGING_DIRECTORY).exists())
        # A retry plans again around the kept copies and succeeds.
        self.assertEqual(self.apply()["status"], "migrated")

    def test_failed_restore_keeps_every_copy_and_names_it(self):
        planned = self.preview()
        lock_bytes = (self.root / ".gz-starter/bundle.lock.json").read_bytes()
        real_rmdir, real_replace = os.rmdir, os.replace
        staging = (self.root / cli.STAGING_DIRECTORY).resolve()

        def fail_on_legacy(path, *args, **kwargs):
            if Path(path).resolve() == (self.root / ".gz-starter").resolve():
                raise OSError("fixture failure")
            return real_rmdir(path, *args, **kwargs)

        def fail_restore(source, target, *args, **kwargs):
            # Moving a staged original back is what fails (a delete-pending file).
            if staging in Path(source).resolve().parents:
                raise OSError("fixture restore failure")
            return real_replace(source, target, *args, **kwargs)

        with (
            mock.patch.object(cli.os, "rmdir", side_effect=fail_on_legacy),
            mock.patch.object(cli.os, "replace", side_effect=fail_restore),
        ):
            code, _, err = self.run_cli("--apply", "--fingerprint", planned["fingerprint"])
        self.assertEqual(code, 2, err)
        self.assertIn("rollback is incomplete", err)
        self.assertIn(".gz-starter/bundle.lock.json was not restored", err)
        self.assertIn(".gzlite/staging/.gz-starter/bundle.lock.json", err)
        self.assertIn("saved copy at .gzlite/migrated/.gz-starter/bundle.lock.json", err)
        self.assertEqual(
            (self.root / ".gzlite/migrated/.gz-starter/bundle.lock.json").read_bytes(), lock_bytes
        )
        self.assertEqual(
            (self.root / ".gzlite/staging/.gz-starter/bundle.lock.json").read_bytes(), lock_bytes
        )
        self.assertTrue((self.root / ".gzlite/bundle.lock.json").is_file())
        # Nothing is retried blindly: the staging leftovers block a new migrate.
        self.refused()

    def test_failing_status_after_apply_is_a_finding(self):
        planned = self.preview()
        with mock.patch.object(cli, "status", side_effect=cli.AdoptionError("fixture")):
            code, out, err = self.run_cli("--apply", "--fingerprint", planned["fingerprint"])
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["status"], "migrated")
        self.assertEqual(result["post_apply_status"]["status"], "unavailable")
        self.assertIn("post-apply status could not run: fixture", result["findings"])
        self.assertFalse((self.root / ".gz-starter").exists())


class RefusalTests(MigrateCase):
    def setUp(self):
        super().setUp()
        self.release = tagged("0.12.1")
        render_adopter(self.root, self.release, "codex")

    def test_dual_state(self):
        (self.root / ".skills-first").mkdir()
        self.assertIn("both", self.refused())

    def test_legacy_and_gzlite_state(self):
        (self.root / ".gzlite").mkdir()
        (self.root / ".gzlite/bundle.lock.json").write_text("{}\n")
        self.refused()

    def test_symlinked_state_folder(self):
        target = self.base / "elsewhere"
        shutil.move(self.root / ".gz-starter", target)
        try:
            os.symlink(target, self.root / ".gz-starter", target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            import _winapi

            _winapi.CreateJunction(str(target), str(self.root / ".gz-starter"))
        self.refused()

    def test_path_with_a_space(self):
        spaced = self.base / "with space"
        spaced.mkdir()
        render_adopter(spaced, self.release, "codex")
        self.refused(root=spaced)

    def test_unparseable_lock(self):
        (self.root / ".gz-starter/bundle.lock.json").write_text("{not json\n")
        self.refused()

    def test_lock_without_a_starter_revision(self):
        self.edit_lock(self.release, lambda d: d["starter"].pop("revision"))
        self.refused()

    def test_revision_not_in_history(self):
        self.edit_lock(self.release, lambda d: d["starter"].update(revision="b" * 40))
        self.assertIn("history", self.refused())

    def test_gzkit_project(self):
        (self.root / ".gzkit").mkdir()
        self.refused()

    def test_go_project_names_gzglite(self):
        (self.root / "go.mod").write_text("module example.invalid/fixture\n")
        self.assertIn("gzglite", self.refused())

    def test_go_module_with_pyproject_is_python(self):
        (self.root / "go.mod").write_text("module example.invalid/fixture\n")
        (self.root / "pyproject.toml").write_text('[project]\nname = "fixture"\n')
        self.assertEqual(self.preview()["status"], "preview")


class NothingToMigrateTests(MigrateCase):
    def test_project_without_legacy_state(self):
        result = self.preview()
        self.assertEqual(result["status"], "nothing to migrate")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_lock_fixture_is_what_configure_wrote(self):
        release = tagged("0.13.0")
        text = lock(release, "claude", release.revision)
        self.assertEqual(list(json.loads(text)), list(release.lock_keys))


if __name__ == "__main__":
    unittest.main()
