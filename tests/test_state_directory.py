"""Exercise state relocation through the public adoption commands."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gzlite import cli
from tools.verify_distribution import release_fixture

MARKERS = ("bundle.lock.json", "architectural-decisions.md", "settings.toml")


class StateDirectoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory(prefix="gz-state-origin-")
        cls.addClassCleanup(temp.cleanup)
        cls.pin, _, cls.release_env = release_fixture(Path(temp.name), cli.template_version())

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gz-state-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def command(self, action, *options):
        args = [action, "--project", str(self.root)]
        if action in ("configure", "localize"):
            args.extend(("--host", "codex", "--starter-ref", self.pin))
        return subprocess.run(
            [sys.executable, "-m", "gzlite", *args, *options],
            env=self.release_env,
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
        # Unrelated files in a legacy folder do not count as recognized state.
        preview = self.command("configure", *options)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn(".gzlite/bundle.lock.json", json.loads(preview.stdout)["writes"])
        self.assertFalse((self.root / ".gzlite").exists())
        applied = self.command("configure", *options, "--apply")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        current = self.root / ".gzlite"
        record = json.loads((current / MARKERS[0]).read_bytes())
        self.assertEqual(record["adr_policy"]["local_path"], f".gzlite/{MARKERS[1]}")
        self.assertTrue((current / MARKERS[1]).is_file())
        self.assertEqual(list(legacy.iterdir()), [unrelated])
        self.assertEqual(unrelated.read_bytes(), b"project-owned notes")
        status = self.command("status")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["status"], "configured")
        repeated = self.command("configure", *options, "--apply")
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(json.loads(repeated.stdout)["writes"], [])

    def test_legacy_state_requires_migrate_for_every_command(self):
        current = self.root / ".gzlite"
        for directory in (".gz-starter", ".skills-first"):
            legacy = self.root / directory
            legacy.mkdir()
            for name in MARKERS:
                with self.subTest(directory=directory, name=name):
                    marker = legacy / name
                    marker.write_bytes(b"invalid but recognizable")
                    for action in ("configure", "status", "localize", "verify"):
                        options = () if action in ("status", "verify") else ("--apply",)
                        result = self.command(action, *options)
                        self.assertNotEqual(result.returncode, 0, result.stdout)
                        self.assertIn(f"{directory}/{name}", result.stderr)
                        self.assertIn("run gzlite migrate", result.stderr)
                    self.assertFalse(current.exists())
                    self.assertEqual(marker.read_bytes(), b"invalid but recognizable")
                    marker.unlink()
            legacy.rmdir()

    def test_legacy_state_beside_current_state_is_refused_unchanged(self):
        current = self.root / ".gzlite"
        current.mkdir()
        (current / MARKERS[0]).write_bytes(b"current bytes")
        legacy = self.root / ".gz-starter"
        legacy.mkdir()
        (legacy / MARKERS[0]).write_bytes(b"legacy bytes")
        result = self.command("configure", "--apply")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("run gzlite migrate", result.stderr)
        self.assertEqual((current / MARKERS[0]).read_bytes(), b"current bytes")
        self.assertEqual((legacy / MARKERS[0]).read_bytes(), b"legacy bytes")

    def test_staged_originals_block_every_command(self):
        """Originals left in .gzlite/staging/ mean a migration rollback is incomplete."""
        staged = self.root / ".gzlite/staging/.gz-starter"
        staged.mkdir(parents=True)
        (staged / MARKERS[0]).write_bytes(b"original lock")
        for action in ("configure", "status", "localize", "verify"):
            with self.subTest(action=action):
                result = self.command(action)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("rollback is incomplete", result.stderr)
                self.assertIn(".gzlite/staging/", result.stderr)
                self.assertIn(".gzlite/migrated/", result.stderr)
        self.assertEqual((staged / MARKERS[0]).read_bytes(), b"original lock")

    def test_empty_staging_folder_is_not_refused(self):
        from gzlite.paths import validate_state_directory

        (self.root / ".gzlite/staging").mkdir(parents=True)
        validate_state_directory(self.root)

    def test_current_state_directory_passes_validation(self):
        from gzlite.paths import LEGACY_DIRECTORIES, MIGRATED_DIRECTORY, validate_state_directory

        self.assertEqual(LEGACY_DIRECTORIES, (".gz-starter", ".skills-first"))
        self.assertEqual(MIGRATED_DIRECTORY, ".gzlite/migrated")
        (self.root / ".gzlite").mkdir()
        (self.root / ".gzlite" / MARKERS[0]).write_bytes(b"{}")
        validate_state_directory(self.root)

    @unittest.skipIf(os.name == "nt", "symlink creation needs Windows privileges")
    def test_linked_state_roots_and_artifacts_are_refused(self):
        for directory in (".skills-first", ".gz-starter", ".gzlite"):
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
        state = self.root / ".gzlite"
        state.mkdir()
        settings = state / "settings.toml"
        settings.write_bytes(b"enabled = true\n")
        settings.chmod(0o004)
        self.addCleanup(settings.chmod, 0o600)
        if os.access(settings, os.R_OK):
            self.skipTest("current user can read files despite their permission bits")
        result = self.command("configure", "--apply")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("unreadable starter state: .gzlite/settings.toml", result.stderr)
        self.assertFalse((state / "bundle.lock.json").exists())
