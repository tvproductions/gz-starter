"""Exercise the vendor command against local fixture repositories only."""

import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from gzlite import vendor
from gzlite.cli import main
from gzlite.gitenv import clean_git_env

SKILL = (
    "---\nname: {name}\ndescription: {name} text.\nmetadata:\n"
    '  govzero-version: "{version}"\n---\n\n{body}\n'
)


def git(cwd: Path, *args: str) -> str:
    """Run git inside a temporary directory with the isolated environment."""
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        env=clean_git_env(),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.strip()


def write_skill(repo: Path, name: str, version: str, body: str = "Body.") -> None:
    folder = repo / "skills" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        SKILL.format(name=name, version=version, body=body), encoding="utf-8", newline="\n"
    )


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "--no-verify", "--no-gpg-sign", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


class Fixture(unittest.TestCase):
    """A temporary upstream repository with two skills and a project to install into."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.repo = self.root / "upstream"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        write_skill(self.repo, "gzs-alpha", "0.1.0")
        write_skill(self.repo, "gzs-beta", "0.1.0")
        self.revision = commit(self.repo, "first")
        self.project = self.root / "project"
        self.target = self.project / ".agents" / "skills"
        self.lock = self.project / "gz-skills.lock.json"
        # Fail closed: a call that forgets --source or a cache override reaches
        # only the local fixture and a temporary cache, never GitHub.
        self.cache = self.root / "env-cache"
        patcher = mock.patch.dict(
            os.environ,
            {
                vendor.REPOSITORY_ENV: self.repo.as_uri(),
                vendor.CACHE_ENV: str(self.cache),
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def install_alpha(self):
        return vendor.install(self.repo, ["gzs-alpha"], self.target, lock=self.lock, force=False)

    def publish_new_version(self):
        write_skill(self.repo, "gzs-alpha", "0.2.0", "Second.")
        commit(self.repo, "second")


class VendorTests(Fixture):
    def test_list_skills_reports_name_version_description_and_hash(self):
        skills = vendor.list_skills(self.repo)
        self.assertEqual([s["name"] for s in skills], ["gzs-alpha", "gzs-beta"])
        self.assertEqual(skills[0]["version"], "0.1.0")
        self.assertEqual(len(skills[0]["sha256"]), 64)

    def test_install_copies_tree_and_writes_lock_entry(self):
        result = self.install_alpha()
        self.assertEqual([i["name"] for i in result["installed"]], ["gzs-alpha"])
        self.assertTrue((self.target / "gzs-alpha" / "SKILL.md").is_file())
        entry = json.loads(self.lock.read_text(encoding="utf-8"))["skills"][0]
        self.assertEqual(entry["name"], "gzs-alpha")
        self.assertEqual(entry["version"], "0.1.0")
        self.assertEqual(entry["source"]["revision"], self.revision)
        self.assertEqual(entry["source"]["path"], "skills/gzs-alpha")
        self.assertEqual(entry["source"]["repository"], vendor.SOURCE_REPOSITORY)
        self.assertEqual(entry["installed_path"], ".agents/skills/gzs-alpha")
        self.assertEqual(entry["sha256"], vendor.tree_sha256(self.target / "gzs-alpha"))

    def test_install_refuses_unknown_skill_and_unlocked_existing_target(self):
        with self.assertRaisesRegex(vendor.VendorError, "unknown skill"):
            vendor.install(self.repo, ["nope"], self.target, lock=self.lock, force=False)
        (self.target / "gzs-alpha").mkdir(parents=True)
        with self.assertRaisesRegex(vendor.VendorError, "without a matching lock"):
            self.install_alpha()
        vendor.install(self.repo, ["gzs-alpha"], self.target, lock=self.lock, force=True)

    def test_status_reports_current_then_changed_then_missing(self):
        self.install_alpha()
        self.assertEqual(vendor.status(self.lock)["skills"][0]["state"], "current")
        skill_file = self.target / "gzs-alpha" / "SKILL.md"
        skill_file.write_text(skill_file.read_text(encoding="utf-8") + "edit\n", encoding="utf-8")
        report = vendor.status(self.lock)
        self.assertEqual(report["skills"][0]["state"], "changed")
        self.assertFalse(report["current"])
        shutil.rmtree(self.target / "gzs-alpha")
        self.assertEqual(vendor.status(self.lock)["skills"][0]["state"], "missing")

    def test_update_without_apply_changes_nothing(self):
        self.install_alpha()
        before = self.lock.read_bytes()
        self.publish_new_version()
        report = vendor.update(self.lock, apply=False, source=self.repo)
        self.assertEqual(report["skills"][0]["state"], "update-available")
        self.assertEqual(self.lock.read_bytes(), before)
        text = (self.target / "gzs-alpha" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Body.", text)

    def test_update_apply_replaces_only_a_tree_matching_the_lock(self):
        self.install_alpha()
        self.publish_new_version()
        report = vendor.update(self.lock, apply=True, source=self.repo)
        self.assertEqual(report["skills"][0]["state"], "current")
        self.assertEqual(report["skills"][0]["installed_version"], "0.2.0")
        text = (self.target / "gzs-alpha" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Second.", text)

    def test_update_apply_refuses_a_modified_tree(self):
        self.install_alpha()
        self.publish_new_version()
        skill_file = self.target / "gzs-alpha" / "SKILL.md"
        skill_file.write_text("local\n", encoding="utf-8")
        with self.assertRaisesRegex(vendor.VendorError, "blocked.*gzs-alpha:changed"):
            vendor.update(self.lock, apply=True, source=self.repo)
        self.assertEqual(skill_file.read_text(encoding="utf-8"), "local\n")

    def test_multi_install_preflights_before_replacing_any(self):
        both = ["gzs-alpha", "gzs-beta"]
        vendor.install(self.repo, both, self.target, lock=self.lock, force=False)
        alpha = self.target / "gzs-alpha" / "SKILL.md"
        before = alpha.read_bytes()
        (self.target / "gzs-beta" / "SKILL.md").write_text("local\n", encoding="utf-8")
        with self.assertRaisesRegex(vendor.VendorError, "locally modified"):
            vendor.install(self.repo, both, self.target, lock=self.lock, force=False)
        self.assertEqual(alpha.read_bytes(), before)

    def test_propagate_finds_every_lock_below_root_and_skips_ignored(self):
        collection = self.root / "collection"
        for name in ("one", "two"):
            base = collection / name
            vendor.install(
                self.repo,
                ["gzs-alpha"],
                base / ".agents" / "skills",
                lock=base / "gz-skills.lock.json",
                force=False,
            )
        ignored = collection / "node_modules" / "x"
        ignored.mkdir(parents=True)
        (ignored / "gz-skills.lock.json").write_text("{}", encoding="utf-8")
        self.publish_new_version()
        preview = vendor.propagate(collection, apply=False, source=self.repo)
        self.assertEqual(len(preview["locks"]), 2)
        self.assertFalse(preview["blocked"])
        applied = vendor.propagate(collection, apply=True, source=self.repo)
        self.assertEqual({r["skills"][0]["state"] for r in applied["locks"]}, {"current"})

    def test_propagate_records_a_blocked_lock_and_continues(self):
        base = self.root / "collection" / "one"
        vendor.install(
            self.repo,
            ["gzs-alpha"],
            base / "skills",
            lock=base / "gz-skills.lock.json",
            force=False,
        )
        (base / "skills" / "gzs-alpha" / "SKILL.md").write_text("x\n", encoding="utf-8")
        report = vendor.propagate(self.root / "collection", apply=True, source=self.repo)
        self.assertTrue(report["blocked"])
        self.assertIn("error", report["locks"][0])

    def test_resolve_source_returns_an_explicit_source(self):
        self.assertEqual(vendor.resolve_source("ignored", source=self.repo), self.repo)

    def test_resolve_source_clones_into_cache_and_reuses_it(self):
        cache = self.root / "cache"
        url = self.repo.as_uri()
        first = vendor.resolve_source(self.revision, source=None, repository=url, cache_root=cache)
        self.assertEqual(first, cache / self.revision)
        self.assertTrue((first / "skills" / "gzs-alpha" / "SKILL.md").is_file())
        self.publish_new_version()
        again = vendor.resolve_source(self.revision, source=None, repository=url, cache_root=cache)
        self.assertEqual(again, first)
        text = (again / "skills" / "gzs-alpha" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Body.", text)

    def test_resolve_source_refreshes_a_mutable_revision(self):
        cache = self.root / "cache"
        url = self.repo.as_uri()
        branch = git(self.repo, "rev-parse", "--abbrev-ref", "HEAD")
        vendor.resolve_source(branch, source=None, repository=url, cache_root=cache)
        self.publish_new_version()
        path = vendor.resolve_source(branch, source=None, repository=url, cache_root=cache)
        text = (path / "skills" / "gzs-alpha" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Second.", text)

    def test_resolve_source_rejects_unsafe_revisions(self):
        for bad in ("-x", "a/b", ".."):
            with self.assertRaises(vendor.VendorError):
                vendor.resolve_source(bad, source=None, cache_root=self.root / "c")

    def test_cache_root_follows_environment_override_and_platform(self):
        with mock.patch.dict(os.environ, {"GZLITE_VENDOR_CACHE": str(self.root / "o")}):
            self.assertEqual(vendor.cache_root(), self.root / "o")
        env = {k: v for k, v in os.environ.items() if k != "GZLITE_VENDOR_CACHE"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(vendor.cache_root().parts[-2:], ("gzlite", "vendor"))


class VendorCliTests(Fixture):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["vendor", *args])
        return code, out.getvalue(), err.getvalue()

    def test_cli_list_install_status_update_propagate(self):
        code, out, _ = self.run_cli("list", "--source", str(self.repo))
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)), 2)
        code, out, _ = self.run_cli(
            "install", "--all", "--source", str(self.repo), "--project", str(self.project)
        )
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)["installed"]), 2)
        self.assertEqual(self.run_cli("status", "--lock", str(self.lock))[0], 0)
        self.publish_new_version()
        code, _, _ = self.run_cli(
            "update", "--lock", str(self.lock), "--source", str(self.repo), "--apply"
        )
        self.assertEqual(code, 0)
        code, out, _ = self.run_cli("propagate", str(self.project), "--source", str(self.repo))
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)["locks"]), 1)

    def test_default_revision_is_the_bundle_pin_and_fetches_offline(self):
        with mock.patch("gzlite.cli._gz_skills_pin", return_value=self.revision):
            code, out, _ = self.run_cli("list")
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)), 2)
        self.assertTrue((self.cache / self.revision).is_dir())

    def test_pin_comes_from_bundle_json(self):
        from gzlite import cli

        expected = next(p for p in cli.bundle()["components"] if p["name"] == "gz-skills")
        self.assertEqual(cli._gz_skills_pin(), expected["revision"])
        self.assertRegex(cli._gz_skills_pin(), r"[0-9a-f]{40}\Z")

    def test_invalid_arguments_refuse_before_any_fetch(self):
        code, _, _ = self.run_cli("install", "--project", str(self.project))
        self.assertEqual(code, 2)
        empty = self.root / "empty"
        empty.mkdir()
        code, out, _ = self.run_cli("propagate", str(empty))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["locks"], [])
        self.assertFalse(self.cache.exists())

    def test_status_exits_1_when_anything_is_not_current(self):
        self.install_alpha()
        (self.target / "gzs-alpha" / "SKILL.md").write_text("x\n", encoding="utf-8")
        code, out, _ = self.run_cli("status", "--lock", str(self.lock))
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["skills"][0]["state"], "changed")

    def test_refusal_is_adoption_blocked_exit_2(self):
        code, _, err = self.run_cli(
            "install", "nope", "--source", str(self.repo), "--project", str(self.project)
        )
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("adoption blocked: "))
        self.assertFalse(self.project.exists())

    def test_install_requires_names_or_all(self):
        code, _, err = self.run_cli(
            "install", "--source", str(self.repo), "--project", str(self.project)
        )
        self.assertEqual(code, 2)
        self.assertIn("adoption blocked", err)


if __name__ == "__main__":
    unittest.main()
