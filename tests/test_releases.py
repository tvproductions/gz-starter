"""Release pins are checked against a real, isolated Git origin."""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fixtures_adopters import render_adopter

from gzlite import cli
from gzlite.gitenv import clean_git_env
from gzlite.history import load_history
from gzlite.paths import BUNDLE_LOCK
from gzlite.releases import ReleaseError, tagged_release


class TaggedReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = tempfile.TemporaryDirectory()
        cls.addClassCleanup(fixture.cleanup)
        parent = Path(fixture.name).resolve()
        cls.publisher = parent / "publisher"
        cls.publisher.mkdir()
        cls.origin = cls.publisher.as_uri()
        cls.xdg_config = parent / "config"
        git_config = cls.xdg_config / "git" / "config"
        git_config.parent.mkdir(parents=True)
        cls.git("config", "--file", str(git_config), f"url.{cls.origin}.insteadOf", cli.ORIGIN)
        cls.git("init", "--quiet", "--initial-branch=main")
        cls.tagged = cls.commit_bundle(cli.template_version())
        cls.git("tag", "--annotate", f"v{cli.template_version()}", "--message=release")
        cls.lightweight = cls.commit_bundle("8.0.0")
        cls.git("tag", "v8.0.0")
        cls.mismatch = cls.commit_bundle("8.0.1")
        cls.git("tag", "--annotate", "v8.0.2", "--message=wrong version")
        cls.other_release = cls.commit_bundle("8.0.3")
        cls.git("tag", "--annotate", "v8.0.3", "--message=other release")
        cls.untagged = cls.commit_bundle(cli.template_version())

    @classmethod
    def git(cls, *args: str) -> str:
        return subprocess.run(
            ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args],
            cwd=cls.publisher,
            env=clean_git_env(),
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()

    @classmethod
    def commit_bundle(cls, version: str) -> str:
        path = cls.publisher / "bundle.json"
        path.write_text(json.dumps({"template_version": version}), encoding="utf-8")
        cls.git("add", "bundle.json")
        cls.git("commit", "--quiet", "--message", version)
        return cls.git("rev-parse", "HEAD")

    def setUp(self):
        target = tempfile.TemporaryDirectory()
        self.addCleanup(target.cleanup)
        self.project = Path(target.name).resolve()
        self.enterContext(patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.xdg_config)}))

    def invoke(self, command: str, *args: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main([command, "--project", str(self.project), *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def snapshot(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in self.project.rglob("*")
            if path.is_file()
        }

    def test_resolves_annotated_release_at_peeled_commit(self):
        with patch.dict(os.environ, {"GIT_DIR": str(self.publisher / "bogus")}):
            release = tagged_release(self.tagged, origin=self.origin)
        version = cli.template_version()
        self.assertEqual(
            (release.tag, release.version, release.revision), (f"v{version}", version, self.tagged)
        )

    def test_refuses_invalid_release_refs(self):
        for ref in (
            self.lightweight,
            self.mismatch,
            self.untagged,
            "main",
            self.tagged[:12],
            self.git("rev-parse", f"v{cli.template_version()}"),
        ):
            with self.subTest(ref=ref), self.assertRaises(ReleaseError):
                tagged_release(ref, origin=self.origin)

    def test_unreachable_origin_is_named(self):
        missing = (self.publisher / "missing-origin").as_uri()
        with self.assertRaises(ReleaseError) as caught:
            tagged_release(self.tagged, origin=missing)
        self.assertIn(missing, str(caught.exception))

    def test_configure_refuses_unpublished_and_other_release_without_writes(self):
        for ref in (self.untagged, self.other_release):
            with self.subTest(ref=ref):
                code, output, error = self.invoke("configure", "--starter-ref", ref, "--apply")
                self.assertEqual(code, 2, output)
                self.assertIn(ref, error)
                self.assertEqual(list(self.project.iterdir()), [])

    def test_valid_release_configures_and_status_verifies_recorded_pin(self):
        code, output, error = self.invoke("configure", "--starter-ref", self.tagged, "--apply")
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(output)["starter"]["revision"], self.tagged)
        code, output, error = self.invoke("status")
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(output)["status"], "configured")

        lock = self.project / BUNDLE_LOCK
        record = json.loads(lock.read_text(encoding="utf-8"))
        record["starter"]["revision"] = self.untagged
        lock.write_text(json.dumps(record), encoding="utf-8")
        before = self.snapshot()
        code, output, error = self.invoke("status")
        self.assertEqual(code, 2, output)
        self.assertIn(self.untagged, error)
        self.assertEqual(self.snapshot(), before)

    def test_localize_and_migrate_reject_unpublished_target_without_writes(self):
        for command, args in (
            ("localize", ("--host", "codex", "--apply")),
            ("migrate", ("--apply", "--fingerprint", "a" * 64)),
        ):
            with self.subTest(command=command):
                code, output, error = self.invoke(command, "--starter-ref", self.untagged, *args)
                self.assertEqual(code, 2, output)
                self.assertIn(self.untagged, error)
                self.assertEqual(list(self.project.iterdir()), [])

    def test_migrate_accepts_a_known_untagged_legacy_source(self):
        legacy_revision = "88928b2c6c663e37f739c80376dae42b5d8e5b4e"
        release = load_history().release_for(legacy_revision)
        render_adopter(self.project, release, "codex")
        ref = ("--starter-ref", self.tagged)

        code, output, error = self.invoke("migrate", *ref)
        self.assertEqual(code, 0, error)
        preview = json.loads(output)
        self.assertIn("never a tagged release", str(preview["findings"]))
        self.assertEqual(preview["from_revision"], legacy_revision)
        code, output, error = self.invoke(
            "migrate", *ref, "--apply", "--fingerprint", preview["fingerprint"]
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(output)["status"], "migrated")
        record = json.loads((self.project / BUNDLE_LOCK).read_bytes())
        self.assertEqual(record["starter"]["revision"], self.tagged)

    def test_freshen_refuses_unpublished_target_without_writes(self):
        code, _, error = self.invoke("configure", "--starter-ref", self.tagged, "--apply")
        self.assertEqual(code, 0, error)
        before = self.snapshot()
        code, output, error = self.invoke("freshen", "--starter-ref", self.tagged)
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(output)["status"], "current")
        code, output, error = self.invoke("freshen", "--starter-ref", self.untagged)
        self.assertEqual(code, 2, output)
        self.assertIn(self.untagged, error)
        self.assertEqual(self.snapshot(), before)
