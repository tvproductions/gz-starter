"""Exercise project settings through the module and the public command."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gzlite.project_settings import (
    SettingsError,
    initialize,
    inspect,
    select,
    validate_settings,
)


class ValidatorTests(unittest.TestCase):
    def test_accepts_exact_schema(self):
        for profile in (None, "lite", "heavy"):
            validate_settings({"schema_version": 1, "profile": profile})

    def test_rejects_other_shapes(self):
        for data in (
            {"schema_version": 1, "profile": None, "note": "x"},
            {"schema_version": "1", "profile": None},
            {"schema_version": True, "profile": None},
            {"schema_version": 2, "profile": None},
            {"schema_version": 1, "profile": "medium"},
            {"schema_version": 1},
            [],
            None,
        ):
            with self.subTest(data=data), self.assertRaises(SettingsError):
                validate_settings(data)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gz-set-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.path = self.root / ".gz-skills" / "settings.json"

    def test_lifecycle_and_bytes(self):
        self.assertEqual(inspect(self.root)["status"], "absent")
        self.assertEqual(initialize(self.root)["status"], "created")
        self.assertEqual(
            self.path.read_bytes(), b'{\n  "schema_version": 1,\n  "profile": null\n}\n'
        )
        self.assertEqual(initialize(self.root)["status"], "present")
        self.assertEqual(select(self.root, "lite")["status"], "updated")
        self.assertEqual(select(self.root, "lite")["status"], "present")
        select(self.root, "heavy")
        self.assertEqual(
            json.loads(self.path.read_text(encoding="utf-8")),
            {"schema_version": 1, "profile": "heavy"},
        )
        with self.assertRaisesRegex(SettingsError, "reversal"):
            select(self.root, "lite")
        self.assertEqual(inspect(self.root)["profile"], "heavy")
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()), ["settings.json"])

    def test_select_before_initialize_refused(self):
        with self.assertRaisesRegex(SettingsError, "initialize"):
            select(self.root, "lite")
        self.assertFalse(self.path.exists())

    def test_gzkit_blocks_without_creating_home(self):
        (self.root / ".gzkit").mkdir()
        with self.assertRaisesRegex(SettingsError, "incompatible"):
            initialize(self.root)
        self.assertFalse((self.root / ".gz-skills").exists())

    def test_symlinked_home_refused(self):
        target = self.root / "elsewhere"
        target.mkdir()
        try:
            (self.root / ".gz-skills").symlink_to(target, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"symlinks unavailable: {error}")
        with self.assertRaisesRegex(SettingsError, "symlink"):
            initialize(self.root)

    def test_malformed_and_unknown_files_are_never_replaced(self):
        self.path.parent.mkdir()
        for original in ("{not json", '{"schema_version": 1, "profile": "lite", "note": "x"}\n'):
            self.path.write_text(original, encoding="utf-8")
            for action in (lambda: initialize(self.root), lambda: select(self.root, "heavy")):
                with self.subTest(original=original), self.assertRaises(SettingsError):
                    action()
                self.assertEqual(self.path.read_text(encoding="utf-8"), original)

    def test_spaced_path_refused(self):
        spaced = self.root / "has space"
        spaced.mkdir()
        with self.assertRaises(ValueError):
            inspect(spaced)


class CommandTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gz-set-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "gzlite", "project-settings", *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_inspect_prints_json(self):
        done = self.run_cli("inspect", "--project", str(self.root))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["status"], "absent")

    def test_initialize_then_select(self):
        self.assertEqual(self.run_cli("initialize", "--project", str(self.root)).returncode, 0)
        done = self.run_cli("select", "--project", str(self.root), "--profile", "lite")
        self.assertEqual(json.loads(done.stdout)["status"], "updated")

    def test_refusal_exits_two(self):
        done = self.run_cli("select", "--project", str(self.root), "--profile", "lite")
        self.assertEqual(done.returncode, 2)
        self.assertIn("adoption blocked", done.stderr)


if __name__ == "__main__":
    unittest.main()
