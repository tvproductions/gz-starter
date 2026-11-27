import json
import os
import tempfile
import tomllib
import unittest
from pathlib import Path

from gzlite import cli as starter
from gzlite.native_identity import (
    LEGACY_MARKETPLACE,
    STARTER_SOURCES,
    is_starter_marketplace,
    marketplace_name,
)

REF = "a" * 40
OLD_REF = "b" * 40
SOURCE = "https://github.com/tvproductions/gz-starter.git"


class MarketplaceNameTests(unittest.TestCase):
    def test_releases_through_0_12_1_keep_the_shared_name(self):
        for version in ("0.9.0", "0.12.0", "0.12.1"):
            with self.subTest(version=version):
                self.assertEqual(marketplace_name(version), LEGACY_MARKETPLACE)

    def test_later_releases_name_their_own_catalog(self):
        self.assertEqual(marketplace_name("0.12.2"), "gz-starter-0-12-2")
        self.assertEqual(marketplace_name("0.13.0"), "gz-starter-0-13-0")
        self.assertEqual(marketplace_name("0.14.0"), "gzlite-0-14-0")
        self.assertEqual(marketplace_name("0.14.1"), "gzlite-0-14-1")
        self.assertEqual(marketplace_name("1.0.0"), "gzlite-1-0-0")

    def test_only_published_starter_names_are_recognized(self):
        self.assertTrue(is_starter_marketplace("skills-first-starter"))
        self.assertTrue(is_starter_marketplace("gz-starter-0-12-2"))
        self.assertTrue(is_starter_marketplace("gz-starter-0-13-0"))
        self.assertTrue(is_starter_marketplace("gzlite-0-14-0"))
        self.assertFalse(is_starter_marketplace("gzglite-0-1-0"))
        self.assertFalse(is_starter_marketplace("gzlite-0-14"))
        self.assertFalse(is_starter_marketplace("gz-starter"))
        self.assertFalse(is_starter_marketplace("gz-skills"))

    def test_sources_include_gzlite_and_every_earlier_form(self):
        for source in (
            "https://github.com/tvproductions/gzlite.git",
            "https://github.com/tvproductions/gzlite",
            "git@github.com:tvproductions/gzlite.git",
            "https://github.com/tvproductions/gz-starter.git",
            "git@github.com:tvproductions/skills-first-starter",
        ):
            with self.subTest(source=source):
                self.assertIn(source, STARTER_SOURCES)

    def test_both_catalogs_carry_this_release_name(self):
        current = marketplace_name(starter.template_version())
        root = Path(__file__).parents[1]
        for path in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
            with self.subTest(path=path):
                self.assertEqual(json.loads((root / path).read_bytes())["name"], current)


class UpgradeTests(unittest.TestCase):
    """An adopter of an earlier release moves to this release's catalog name."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve() / "project"
        self.root.mkdir()
        home = Path(temp.name).resolve() / "home"
        home.mkdir()
        saved = {k: os.environ.get(k) for k in ("CODEX_HOME", "CLAUDE_CONFIG_DIR")}
        os.environ["CODEX_HOME"] = str(home)
        os.environ["CLAUDE_CONFIG_DIR"] = str(home)
        self.addCleanup(self._restore, saved)
        self.current = starter.marketplace()

    @staticmethod
    def _restore(saved):
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def write_codex(self, text):
        path = self.root / ".codex/config.toml"
        path.parent.mkdir()
        path.write_text(text)
        return path

    def legacy_codex(self, backplane="false"):
        return (
            'model = "fixture"\n\n'
            "[marketplaces.skills-first-starter]\n"
            f'source_type = "git"\nsource = "{SOURCE}"\nref = "{OLD_REF}"\n\n'
            '[plugins."superpowers@skills-first-starter"]\nenabled = true\n\n'
            '[plugins."gz-skills@skills-first-starter"]\nenabled = true\n\n'
            f'[plugins."superpowers-backplane@skills-first-starter"]\nenabled = {backplane}\n\n'
            "[fixture]\nkeep = true\n"
        )

    def test_codex_upgrade_retires_the_0_13_0_name_as_0_13_0_wrote_it(self):
        old = "gz-starter-0-13-0"
        path = self.write_codex(
            'model = "fixture"\n\n'
            f"[marketplaces.{old}]\n"
            f'source_type = "git"\nsource = "{SOURCE}"\nref = "{OLD_REF}"\n\n'
            f'[plugins."superpowers@{old}"]\nenabled = true\n\n'
            f'[plugins."gz-skills@{old}"]\nenabled = true\n\n'
            f'[plugins."superpowers-backplane@{old}"]\nenabled = false\n'
        )
        starter.configure(self.root, REF, apply=True)
        data = tomllib.loads(path.read_text())
        self.assertEqual(set(data["marketplaces"]), {self.current})
        self.assertEqual(self.current, "gzlite-0-14-0")
        self.assertFalse([k for k in data["plugins"] if k.endswith("@" + old)])

    def test_codex_upgrade_retires_the_earlier_name_and_keeps_project_tables(self):
        path = self.write_codex(self.legacy_codex())
        starter.configure(self.root, REF, apply=True)
        data = tomllib.loads(path.read_text())
        self.assertEqual(set(data["marketplaces"]), {self.current})
        self.assertEqual(data["marketplaces"][self.current]["ref"], REF)
        self.assertTrue(all(key.endswith("@" + self.current) for key in data["plugins"]))
        self.assertIs(data["plugins"]["gz-skills@" + self.current]["enabled"], True)
        self.assertEqual(data["model"], "fixture")
        self.assertTrue(data["fixture"]["keep"])
        self.assertEqual(starter.configure(self.root, REF)["writes"], [])

    def test_codex_upgrade_preserves_an_explicit_project_choice(self):
        original = self.legacy_codex(backplane="true")
        path = self.write_codex(original)
        with self.assertRaises(starter.AdoptionError):
            starter.configure(self.root, REF, apply=True)
        self.assertEqual(path.read_text(), original)

    def test_claude_upgrade_retires_the_earlier_name(self):
        path = self.root / ".claude/settings.json"
        path.parent.mkdir()
        legacy = {
            "fixture": True,
            "extraKnownMarketplaces": {
                "skills-first-starter": {
                    "source": {"source": "git", "url": SOURCE, "ref": OLD_REF},
                    "autoUpdate": False,
                }
            },
            "enabledPlugins": {
                "superpowers@skills-first-starter": True,
                "gz-skills@skills-first-starter": True,
                "superpowers-backplane@skills-first-starter": False,
            },
        }
        path.write_text(json.dumps(legacy))
        starter.configure(self.root, REF, host="claude", apply=True)
        data = json.loads(path.read_bytes())
        self.assertEqual(set(data["extraKnownMarketplaces"]), {self.current})
        self.assertTrue(all(key.endswith("@" + self.current) for key in data["enabledPlugins"]))
        self.assertIs(data["fixture"], True)
        self.assertEqual(starter.configure(self.root, REF, host="claude")["writes"], [])

    def assert_codex_refused(self, original):
        path = self.write_codex(original)
        with self.assertRaises(starter.AdoptionError):
            starter.configure(self.root, REF, apply=True)
        self.assertEqual(path.read_text(), original)
        self.assertFalse((self.root / ".gz-starter").exists())

    def test_codex_upgrade_refuses_an_explicit_legacy_disable(self):
        original = self.legacy_codex().replace(
            '[plugins."gz-skills@skills-first-starter"]\nenabled = true',
            '[plugins."gz-skills@skills-first-starter"]\nenabled = false',
        )
        self.assertNotEqual(original, self.legacy_codex())
        self.assert_codex_refused(original)

    def test_codex_upgrade_refuses_a_legacy_name_on_a_fork(self):
        original = self.legacy_codex().replace(SOURCE, "https://example.invalid/fork.git")
        self.assert_codex_refused(original)

    def test_codex_keeps_a_duplicate_suppression_without_a_legacy_source(self):
        path = self.write_codex('[plugins."gz-skills@skills-first-starter"]\nenabled = false\n')
        starter.configure(self.root, REF, apply=True)
        data = tomllib.loads(path.read_text())
        self.assertIs(data["plugins"]["gz-skills@skills-first-starter"]["enabled"], False)
        self.assertIs(data["plugins"]["gz-skills@" + self.current]["enabled"], True)

    def legacy_claude(self):
        return {
            "extraKnownMarketplaces": {
                "skills-first-starter": {
                    "source": {"source": "git", "url": SOURCE, "ref": OLD_REF},
                    "autoUpdate": False,
                }
            },
            "enabledPlugins": {"gz-skills@skills-first-starter": True},
        }

    def assert_claude_refused(self, settings, name="settings.json"):
        path = self.root / ".claude" / name
        path.parent.mkdir(exist_ok=True)
        original = json.dumps(settings).encode()
        path.write_bytes(original)
        with self.assertRaises(ValueError):
            starter.configure(self.root, REF, host="claude", apply=True)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse((self.root / ".gz-starter").exists())

    def test_claude_upgrade_refuses_an_explicit_auto_update(self):
        settings = self.legacy_claude()
        settings["extraKnownMarketplaces"]["skills-first-starter"]["autoUpdate"] = True
        self.assert_claude_refused(settings)

    def test_claude_upgrade_refuses_an_explicit_legacy_disable(self):
        settings = self.legacy_claude()
        settings["enabledPlugins"]["gz-skills@skills-first-starter"] = False
        self.assert_claude_refused(settings)

    def test_claude_upgrade_refuses_active_legacy_local_settings(self):
        self.assert_claude_refused(self.legacy_claude(), name="settings.local.json")

    def test_localize_refuses_a_lock_without_a_recorded_release(self):
        lock = self.root / ".gz-starter/bundle.lock.json"
        lock.parent.mkdir()
        lock.write_text(
            json.dumps({"schema_version": 1, "components": starter.bundle()["components"]})
        )
        path = self.write_codex('model = "fixture"\n')
        with self.assertRaises(starter.AdoptionError):
            starter.localize(self.root, OLD_REF, host="codex", apply=True)
        self.assertEqual(path.read_text(), 'model = "fixture"\n')

    def test_localize_keeps_the_name_published_by_the_recorded_release(self):
        lock = self.root / ".gz-starter/bundle.lock.json"
        lock.parent.mkdir()
        lock.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "starter": {"repository": SOURCE, "version": "0.12.1", "revision": OLD_REF},
                    "components": starter.bundle()["components"],
                }
            )
        )
        path = self.write_codex('model = "fixture"\n')
        starter.localize(self.root, OLD_REF, host="codex", apply=True)
        data = tomllib.loads(path.read_text())
        self.assertEqual(set(data["marketplaces"]), {LEGACY_MARKETPLACE})
        self.assertIs(data["plugins"]["gz-skills@" + LEGACY_MARKETPLACE]["enabled"], True)


if __name__ == "__main__":
    unittest.main()
