"""Exercise the producer release guard against small Git repositories."""

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from gzlite import cli
from gzlite.gitenv import clean_git_env
from gzlite.native_identity import marketplace_name


class ReleaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.git("init", "--quiet", "--initial-branch=main")
        self.versions("0.13.0")
        self.changelog("0.13.0")
        self.baseline = self.commit()
        self.git("tag", "-a", "v0.13.0", "-m", "baseline")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args],
            cwd=self.root,
            env=clean_git_env(),
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()

    def put(self, name: str, content: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def versions(self, version: str) -> None:
        self.put("bundle.json", json.dumps({"template_version": version}))
        self.put("pyproject.toml", f'[project]\nversion = "{version}"\n')
        for path in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
            self.put(path, json.dumps({"name": marketplace_name(version)}))

    def changelog(self, *versions: str) -> None:
        self.put(
            "CHANGELOG.md",
            "# Changelog\n\n## Unreleased\n"
            + "".join(f"\n## {version} — 2026-11-28\n" for version in versions),
        )

    def commit(self) -> str:
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "fixture")
        return self.git("rev-parse", "HEAD")

    def candidate(self, *, tagged: bool = True, lightweight: bool = False) -> str:
        self.versions("0.14.0")
        self.changelog("0.14.0", "0.13.0")
        revision = self.commit()
        if tagged:
            self.git("tag", "v0.14.0") if lightweight else self.git(
                "tag", "-a", "v0.14.0", "-m", "release"
            )
        return revision

    def check(
        self, *, published: bool = False, releases: dict[str, str] | None = None
    ) -> list[dict]:
        from gzlite.release_check import check_release_integrity

        tags = {
            tag: self.git("rev-parse", f"{tag}^{{commit}}") for tag in self.git("tag").splitlines()
        }
        return check_release_integrity(self.root, published=published, tags=tags, releases=releases)

    def test_cli_returns_findings_for_untagged_dated_release(self):
        self.candidate(tagged=False)
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = cli.main(["release", "check", "--project", str(self.root)])
            except SystemExit as error:
                code = error.code
        self.assertEqual(code, 1, stderr.getvalue())
        self.assertIn("v0.14.0", stdout.getvalue())

    def test_clean_release(self):
        target = self.candidate()
        self.assertEqual(self.check(), [])
        self.assertEqual(
            self.check(published=True, releases={"v0.13.0": self.baseline, "v0.14.0": target}), []
        )

    def test_tag_on_wrong_bundle(self):
        self.candidate(tagged=False)
        self.git("tag", "-a", "v0.14.0", self.baseline, "-m", "wrong target")
        self.assertIn("tag-version", {item["check"] for item in self.check()})

    def test_lightweight_tag_is_refused(self):
        self.candidate(lightweight=True)
        self.assertIn("annotated-tag", {item["check"] for item in self.check()})

    def test_mirror_disagreement(self):
        self.candidate()
        self.put("pyproject.toml", '[project]\nversion = "0.13.0"\n')
        self.put(".claude-plugin/marketplace.json", '{"name": "other"}')
        self.assertEqual(
            {item["artifact"] for item in self.check() if item["check"] == "version-mirror"},
            {"pyproject.toml", ".claude-plugin/marketplace.json"},
        )

    def test_wrong_published_target(self):
        self.candidate()
        findings = self.check(
            published=True, releases={"v0.13.0": self.baseline, "v0.14.0": self.baseline}
        )
        self.assertEqual([item["artifact"] for item in findings], ["v0.14.0"])

    def test_premature_metadata_bump(self):
        self.versions("0.14.0")
        self.commit()
        self.assertIn("version-ahead", {item["check"] for item in self.check()})
        self.changelog("0.14.0", "0.13.0")
        self.commit()
        self.git("tag", "-a", "v0.14.0", "-m", "late release")
        self.assertIn("release-commit", {item["check"] for item in self.check()})
