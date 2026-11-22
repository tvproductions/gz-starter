"""Exercise state relocation through the public adoption commands."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REF = "a" * 40
MARKERS = ("bundle.lock.json", "architectural-decisions.md", "settings.toml")


class StateDirectoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gz-state-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def command(self, action, *options):
        args = [action, "--project", str(self.root)]
        if action in ("configure", "localize"):
            args.extend(("--host", "codex", "--starter-ref", REF))
        return subprocess.run(
            [sys.executable, "-m", "skills_first_starter", *args, *options],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_configure_uses_canonical_state_and_preserves_unrelated_legacy_data(self):
        legacy = self.root / ".skills-first"
        legacy.mkdir()
        unrelated = legacy / "notes.md"
        unrelated.write_bytes(b"project-owned notes")
        options = ("--adr-policy", "local")
        preview = self.command("configure", *options)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn(".gz-starter/bundle.lock.json", json.loads(preview.stdout)["writes"])
        self.assertFalse((self.root / ".gz-starter").exists())
        applied = self.command("configure", *options, "--apply")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        current = self.root / ".gz-starter"
        record = json.loads((current / MARKERS[0]).read_bytes())
        self.assertEqual(record["adr_policy"]["local_path"], f".gz-starter/{MARKERS[1]}")
        self.assertTrue((current / MARKERS[1]).is_file())
        self.assertEqual(list(legacy.iterdir()), [unrelated])
        self.assertEqual(unrelated.read_bytes(), b"project-owned notes")
        status = self.command("status")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["status"], "configured")
        repeated = self.command("configure", *options, "--apply")
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(json.loads(repeated.stdout)["writes"], [])

    def test_recognized_legacy_names_block_commands_and_preserve_dual_state(self):
        legacy = self.root / ".skills-first"
        legacy.mkdir()
        current = self.root / ".gz-starter"
        for name in MARKERS:
            with self.subTest(name=name):
                marker = legacy / name
                marker.write_bytes(b"invalid but recognizable")
                for action in ("configure", "status", "localize"):
                    options = () if action == "status" else ("--apply",)
                    result = self.command(action, *options)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(f".skills-first/{name}", result.stderr)
                    self.assertIn("migration", result.stderr)
                self.assertFalse(current.exists())
                self.assertEqual(marker.read_bytes(), b"invalid but recognizable")
                marker.unlink()
        current.mkdir()
        (current / MARKERS[0]).write_bytes(b"current bytes")
        (legacy / MARKERS[0]).mkdir()
        result = self.command("configure", "--apply")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("migration", result.stderr)
        self.assertEqual((current / MARKERS[0]).read_bytes(), b"current bytes")
        self.assertTrue((legacy / MARKERS[0]).is_dir())

    @unittest.skipIf(os.name == "nt", "symlink creation needs Windows privileges")
    def test_linked_state_roots_and_artifacts_are_refused(self):
        for directory in (".skills-first", ".gz-starter"):
            with self.subTest(directory=directory):
                state = self.root / directory
                target = self.root / "absent"
                state.symlink_to(target, target_is_directory=True)
                result = self.command("configure", "--apply")
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(directory, result.stderr)
                self.assertTrue(state.is_symlink())
                state.unlink()
                state.mkdir()
                marker = state / MARKERS[2]
                marker.symlink_to(target)
                result = self.command("status")
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(MARKERS[2], result.stderr)
                self.assertTrue(marker.is_symlink())
                marker.unlink()
                state.rmdir()
                self.assertFalse(target.exists())

    @unittest.skipIf(os.name == "nt", "requires POSIX permission classes")
    def test_state_file_unreadable_to_owner_blocks_configure(self):
        state = self.root / ".gz-starter"
        state.mkdir()
        settings = state / "settings.toml"
        settings.write_bytes(b"enabled = true\n")
        settings.chmod(0o004)
        self.addCleanup(settings.chmod, 0o600)
        if os.access(settings, os.R_OK):
            self.skipTest("current user can read files despite their permission bits")
        result = self.command("configure", "--apply")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("unreadable starter state: .gz-starter/settings.toml", result.stderr)
        self.assertFalse((state / "bundle.lock.json").exists())
