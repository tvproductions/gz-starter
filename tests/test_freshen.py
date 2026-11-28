"""``gzlite freshen``: bring a gzlite adopter to the running release."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from fixtures_adopters import FIXTURE_COMPONENTS, render_adopter

from gzlite import cli
from gzlite.history import load_history
from gzlite.native_json import document

REF = "a" * 40  # the running release's revision
OLD = "b" * 40  # an older gzlite revision the adopter recorded
SAVED = ".gzlite/migrated/freshen-"
ADR_0003 = "docs/decisions/ADR-0003-001-own-bootstrap-verification-in-the-starter.md"
WORKFLOW = ".github/workflows/verify-python.yml"
CHECKOUT = Path(__file__).resolve().parents[1]
HISTORY = load_history()


def tagged(version: str):
    return next(release for release in HISTORY.releases if release.version == version)


class FreshenCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()
        inherited = mock.patch.object(cli, "_inherited_plugins", return_value={})
        inherited.start()
        self.addCleanup(inherited.stop)

    def configure(
        self,
        host: str = "codex",
        ref: str = OLD,
        parts: tuple[dict, ...] = FIXTURE_COMPONENTS,
        adr_policy: str | None = None,
    ) -> None:
        """Adopt as an older gzlite revision did: its own ref and component pins."""
        real = cli.bundle()
        older = {**real, "components": [dict(part) for part in parts]}
        with (
            mock.patch.object(cli, "bundle", return_value=older),
            mock.patch.object(cli, "validate_bundle"),
        ):
            cli.configure(self.root, ref, host=host, apply=True, adr_policy=adr_policy)

    def current(self, host: str = "codex", adr_policy: str | None = None) -> None:
        """Adopt exactly as the running release does."""
        cli.configure(self.root, REF, host=host, apply=True, adr_policy=adr_policy)

    def tree(self, root: Path | None = None) -> dict[str, bytes]:
        root = root or self.root
        return {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }

    def run_cli(self, *args: str, root: Path | None = None) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        argv = ["freshen", "--project", str(root or self.root), "--starter-ref", REF, *args]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def preview(self) -> dict:
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def apply(self) -> dict:
        planned = self.preview()
        self.assertEqual(planned["status"], "preview")
        code, out, err = self.run_cli("--apply", "--fingerprint", planned["fingerprint"])
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

    def assert_current(self) -> dict:
        """Preview and ``--apply`` both report current and write nothing."""
        before = self.tree()
        planned = self.preview()
        self.assertEqual(planned["status"], "current", planned)
        self.assertEqual(planned["writes"], [])
        self.assertEqual(planned["replaced"], [])
        self.assertIsNone(planned["fingerprint"])
        code, out, err = self.run_cli("--apply", "--fingerprint", "0" * 64)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["status"], "current")
        self.assertEqual(self.tree(), before)
        return planned

    def lock(self) -> dict:
        return json.loads((self.root / ".gzlite/bundle.lock.json").read_bytes())

    @staticmethod
    def written(planned: dict) -> list[str]:
        return [item["path"] for item in planned["writes"]]

    @staticmethod
    def texts(planned: dict) -> list[str]:
        return [item["finding"] for item in planned["findings"]]

    def expected(self, name: str, host: str = "codex", adr_policy: str | None = None) -> bytes:
        """What the running release writes at ``REF`` for ``name``, in an empty project."""
        other = self.base / "expected"
        if not other.exists():
            other.mkdir()
            cli.configure(other, REF, host=host, apply=True, adr_policy=adr_policy)
        return (other / name).read_bytes()


class FreshenTests(FreshenCase):
    def test_older_revision_freshens_managed_files_and_pins(self):
        self.configure("codex")
        old_lock = (self.root / ".gzlite/bundle.lock.json").read_bytes()
        planned = self.preview()
        self.assertEqual(planned["status"], "preview")
        written = self.written(planned)
        for name in (".codex/config.toml", ".gzlite/bundle.lock.json", "AGENTS.skills-first.md"):
            self.assertIn(name, written)
        # The update skill has no ref in it: unchanged, so not written.
        self.assertNotIn(".agents/skills/gzl-update/SKILL.md", written)
        self.assertTrue(all(item["reason"] for item in planned["writes"]))
        # The fragment is what this release wrote at the recorded ref: not saved.
        # The lock is generated state: kept as a record, never judged as edited.
        self.assertEqual(
            planned["replaced"],
            [
                {
                    "path": ".gzlite/bundle.lock.json",
                    "saved_to": f"{SAVED}{OLD[:12]}/.gzlite/bundle.lock.json",
                    "why": "record",
                }
            ],
        )
        pins = [f for f in self.texts(planned) if "component pins move" in f]
        self.assertEqual(len(pins), 1)
        self.assertIn("1" * 40, pins[0])
        self.assertTrue(all(item["source"] for item in planned["findings"]))
        self.assertFalse([n for n in planned["next"] if n.startswith("Review each file saved")])

        result = self.apply()
        self.assertEqual(result["status"], "freshened")
        self.assertEqual(result["post_apply_status"]["status"], "configured")
        self.assertEqual(result["post_apply_status"]["pending_files"], [])
        lock = self.lock()
        self.assertEqual(
            lock["starter"], {"repository": cli.ORIGIN, "version": "0.14.0", "revision": REF}
        )
        self.assertEqual(lock["components"], cli.bundle()["components"])
        config = tomllib.loads((self.root / ".codex/config.toml").read_text())
        self.assertEqual(set(config["marketplaces"]), {cli.marketplace()})
        self.assertEqual(config["marketplaces"][cli.marketplace()]["ref"], REF)
        for name in ("AGENTS.skills-first.md", ".gzlite/bundle.lock.json"):
            self.assertEqual((self.root / name).read_bytes(), self.expected(name), name)
        # Retiring and re-adding the tables may leave a blank line; the content matches.
        self.assertEqual(config, tomllib.loads(self.expected(".codex/config.toml").decode()))
        saved = self.root / f"{SAVED}{OLD[:12]}/.gzlite/bundle.lock.json"
        self.assertEqual(saved.read_bytes(), old_lock)
        self.assertFalse((self.root / cli.STAGING_DIRECTORY).exists())

    def test_freshen_twice_after_apply_is_current_and_writes_nothing(self):
        self.configure("claude")
        self.apply()
        self.assert_current()
        self.assertEqual(cli.status(self.root)["pending_files"], [])

    def test_current_adopter_on_every_host_is_current(self):
        for host in ("codex", "claude", "opencode"):
            for mode in ("link", "local"):
                with self.subTest(host=host, mode=mode):
                    shutil.rmtree(self.root)
                    self.root.mkdir()
                    self.current(host, mode)
                    self.assert_current()

    def test_crlf_only_differences_count_as_current(self):
        self.current("codex")
        for name in self.tree():
            path = self.root / name
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        self.assert_current()

    def test_crlf_fragment_at_an_older_revision_is_not_an_edit(self):
        self.configure("codex")
        fragment = self.root / "AGENTS.skills-first.md"
        fragment.write_bytes(fragment.read_bytes().replace(b"\n", b"\r\n"))
        planned = self.preview()
        self.assertIn("AGENTS.skills-first.md", self.written(planned))
        self.assertEqual([i for i in planned["replaced"] if i["why"] == "edited"], [])

    def test_older_release_retires_its_catalog(self):
        # A 0.14.0 adopter, freshened by a later release that names its own catalog.
        self.configure("claude", parts=tuple(cli.bundle()["components"]))
        with (
            mock.patch.object(cli, "template_version", return_value="0.14.1"),
            mock.patch.object(cli, "validate_bundle"),
        ):
            result = self.apply()
            self.assertEqual(result["post_apply_status"]["pending_files"], [])
            self.assert_current()
        data = json.loads((self.root / ".claude/settings.json").read_bytes())
        self.assertEqual(set(data["extraKnownMarketplaces"]), {"gzlite-0-14-1"})
        self.assertFalse([k for k in data["enabledPlugins"] if k.endswith("@gzlite-0-14-0")])
        self.assertEqual(self.lock()["starter"]["version"], "0.14.1")

    def test_pins_ahead_of_the_bundle_are_set_to_the_bundle(self):
        ahead = tuple(
            dict(part, revision="c" * 40) if part["name"] == "superpowers" else dict(part)
            for part in cli.bundle()["components"]
        )
        self.configure("opencode", ref=REF, parts=ahead)
        planned = self.preview()
        self.assertIn("opencode.json", self.written(planned))
        self.assertTrue([f for f in self.texts(planned) if "c" * 40 in f])
        self.apply()
        self.assertEqual(self.lock()["components"], cli.bundle()["components"])
        data, _ = document((self.root / "opencode.json").read_text())
        self.assertFalse([p for p in data["plugins"] if "c" * 40 in p])
        self.assert_current()

    def test_claude_and_codex_with_lock_host_codex_are_both_freshened(self):
        self.configure("codex")
        # Claude was configured too, earlier; the lock records only the last host.
        claude = self.base / "claude"
        claude.mkdir()
        with mock.patch.object(self, "root", claude):
            self.configure("claude")
        shutil.copytree(claude / ".claude", self.root / ".claude")
        self.assertNotIn("host", self.lock())
        planned = self.preview()
        written = self.written(planned)
        self.assertIn(".codex/config.toml", written)
        self.assertIn(".claude/settings.json", written)
        self.apply()
        report = cli.status(self.root)
        self.assertEqual(report["hosts"], ["codex", "claude"])
        self.assertEqual(report["pending_files"], [])
        claude = json.loads((self.root / ".claude/settings.json").read_bytes())
        source = claude["extraKnownMarketplaces"][cli.marketplace()]["source"]
        self.assertEqual(source["ref"], REF)
        for name in (".agents/skills/gzl-update/SKILL.md", ".claude/skills/gzl-update/SKILL.md"):
            self.assertTrue((self.root / name).is_file(), name)
        self.assert_current()

    def test_opencode_jsonc_is_edited_in_place(self):
        jsonc = self.root / "opencode.jsonc"
        jsonc.write_text("// Project OpenCode settings.\n{}\n")
        self.configure("opencode")
        planned = self.preview()
        self.assertIn("opencode.jsonc", self.written(planned))
        self.assertNotIn("opencode.json", self.written(planned))
        self.apply()
        self.assertFalse((self.root / "opencode.json").exists())
        text = jsonc.read_text()
        self.assertTrue(text.startswith("// Project OpenCode settings.\n"))
        data, _ = document(text)
        for part in cli.bundle()["components"]:
            if part["enabled_by_default"]:
                self.assertIn(f"git+{part['repository']}.git#{part['revision']}", data["plugins"])
        self.assert_current()

    def test_local_adr_policy_adopter_freshens(self):
        self.configure("codex", adr_policy="local")
        planned = self.preview()
        self.assertNotIn(".gzlite/architectural-decisions.md", self.written(planned))
        self.apply()
        self.assertEqual(self.lock()["adr_policy"]["mode"], "local")
        self.assert_current()


class DriftTests(FreshenCase):
    def test_edited_fragment_is_replaced_and_saved(self):
        self.current("codex")
        fragment = self.root / "AGENTS.skills-first.md"
        edited = fragment.read_bytes() + b"\nLocal rule added by hand.\n"
        fragment.write_bytes(edited)
        planned = self.preview()
        saved = f"{SAVED}{REF[:12]}/AGENTS.skills-first.md"
        self.assertEqual(
            planned["replaced"],
            [{"path": "AGENTS.skills-first.md", "saved_to": saved, "why": "edited"}],
        )
        self.assertTrue([n for n in planned["next"] if n.startswith("Review each file saved")])
        self.apply()
        self.assertEqual((self.root / saved).read_bytes(), edited)
        self.assertEqual(fragment.read_bytes(), self.expected("AGENTS.skills-first.md"))
        self.assert_current()

    def test_edited_fragment_at_an_older_revision_is_saved_under_that_revision(self):
        self.configure("codex")
        fragment = self.root / "AGENTS.skills-first.md"
        fragment.write_bytes(fragment.read_bytes() + b"Local rule.\n")
        planned = self.preview()
        self.assertIn(
            {
                "path": "AGENTS.skills-first.md",
                "saved_to": f"{SAVED}{OLD[:12]}/AGENTS.skills-first.md",
                "why": "edited",
            },
            planned["replaced"],
        )

    def test_edited_update_skill_is_saved(self):
        self.current("claude")
        skill = self.root / ".claude/skills/gzl-update/SKILL.md"
        skill.write_text(skill.read_text() + "Local step.\n")
        planned = self.preview()
        saved = f"{SAVED}{REF[:12]}/.claude/skills/gzl-update/SKILL.md"
        self.assertIn(
            {"path": ".claude/skills/gzl-update/SKILL.md", "saved_to": saved, "why": "edited"},
            planned["replaced"],
        )
        self.apply()
        self.assertTrue((self.root / saved).read_text().endswith("Local step.\n"))
        self.assertFalse(skill.read_text().endswith("Local step.\n"))

    def test_different_existing_saved_copy_is_refused(self):
        self.current("codex")
        fragment = self.root / "AGENTS.skills-first.md"
        fragment.write_bytes(fragment.read_bytes() + b"Local rule.\n")
        saved = self.root / f"{SAVED}{REF[:12]}/AGENTS.skills-first.md"
        saved.parent.mkdir(parents=True)
        saved.write_text("an earlier copy\n")
        self.assertIn("already holds a different saved copy", self.refused())

    def test_snapshot_from_history_proves_an_untouched_fragment(self):
        # A 0.13.0 adopter whose state folder was moved to .gzlite/ by hand: the
        # recorded revision is in the history, so its own fragment is untouched.
        release = tagged("0.13.0")
        render_adopter(self.root, release, "codex")
        shutil.move(self.root / ".gz-starter", self.root / ".gzlite")
        planned = self.preview()
        self.assertIn("AGENTS.skills-first.md", self.written(planned))
        self.assertEqual([i for i in planned["replaced"] if i["why"] == "edited"], [])
        self.apply()
        self.assertEqual(
            (self.root / "AGENTS.skills-first.md").read_bytes(),
            self.expected("AGENTS.skills-first.md"),
        )


class DoctrineTests(FreshenCase):
    def test_python_project_without_verification_workflow_gets_a_finding(self):
        self.current("codex")
        (self.root / "pyproject.toml").write_text('[project]\nname = "fixture"\n')
        planned = self.assert_current()
        doctrine = [f for f in planned["findings"] if f["source"] == ADR_0003]
        self.assertEqual(len(doctrine), 1)
        self.assertIn(WORKFLOW, doctrine[0]["finding"])
        self.assertTrue((CHECKOUT / ADR_0003).is_file())

    def test_workflow_present_or_no_python_means_no_finding(self):
        self.current("codex")
        self.assertFalse([f for f in self.preview()["findings"] if f["source"] == ADR_0003])
        (self.root / "pyproject.toml").write_text('[project]\nname = "fixture"\n')
        workflow = self.root / WORKFLOW
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: verify\n")
        self.assertFalse([f for f in self.preview()["findings"] if f["source"] == ADR_0003])

    def test_findings_never_cause_writes(self):
        self.configure("codex")
        (self.root / "pyproject.toml").write_text('[project]\nname = "fixture"\n')
        planned = self.preview()
        self.assertTrue([f for f in planned["findings"] if f["source"] == ADR_0003])
        self.assertNotIn(WORKFLOW, self.written(planned))
        self.apply()
        self.assertFalse((self.root / WORKFLOW).exists())

    def test_findings_are_fingerprinted(self):
        self.configure("codex")
        (self.root / "pyproject.toml").write_text('[project]\nname = "fixture"\n')
        planned = self.preview()
        workflow = self.root / WORKFLOW
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: verify\n")
        self.assertNotEqual(self.preview()["fingerprint"], planned["fingerprint"])
        self.assertIn(
            "fingerprint", self.refused("--apply", "--fingerprint", planned["fingerprint"])
        )


class FingerprintTests(FreshenCase):
    def setUp(self):
        super().setUp()
        self.configure("claude")

    def test_preview_twice_is_byte_identical_and_writes_nothing(self):
        before = self.tree()
        first, second = self.run_cli(), self.run_cli()
        self.assertEqual(first[0], 0, first[2])
        self.assertEqual(first, second)
        self.assertEqual(self.tree(), before)
        self.assertRegex(json.loads(first[1])["fingerprint"], r"\A[0-9a-f]{64}\Z")

    def test_wrong_fingerprint_exits_2_and_writes_nothing(self):
        self.assertIn("fingerprint", self.refused("--apply", "--fingerprint", "0" * 64))

    def test_apply_requires_a_fingerprint(self):
        self.refused("--apply")
        self.refused("--apply", "--fingerprint", "not-hex")

    def test_changed_input_invalidates_the_fingerprint(self):
        planned = self.preview()
        fragment = self.root / "AGENTS.skills-first.md"
        fragment.write_bytes(fragment.read_bytes().replace(b"\n", b"\r\n"))
        self.refused("--apply", "--fingerprint", planned["fingerprint"])


class RefusalTests(FreshenCase):
    def test_legacy_state_names_migrate(self):
        render_adopter(self.root, tagged("0.13.0"), "codex")
        self.assertIn("gzlite migrate", self.refused())

    def test_project_without_gzlite_adoption(self):
        self.assertIn("gzlite configure", self.refused())

    def test_non_empty_staging_is_refused(self):
        self.current("codex")
        staging = self.root / cli.STAGING_DIRECTORY
        staging.mkdir()
        (staging / "left.txt").write_text("left\n")
        self.assertIn("staging", self.refused())

    def test_unparseable_lock(self):
        self.current("codex")
        (self.root / ".gzlite/bundle.lock.json").write_text("{not json\n")
        self.refused()

    def test_moving_starter_ref(self):
        self.current("codex")
        before = self.tree()
        code, _, err = self.run_cli()
        self.assertEqual(code, 0, err)
        out, err_stream = io.StringIO(), io.StringIO()
        argv = ["freshen", "--project", str(self.root), "--starter-ref", "main"]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err_stream):
            self.assertEqual(cli.main(argv), 2)
        self.assertIn("full", err_stream.getvalue())
        self.assertEqual(self.tree(), before)

    def test_gzkit_project(self):
        self.current("codex")
        (self.root / ".gzkit").mkdir()
        self.refused()

    def test_path_with_a_space(self):
        spaced = self.base / "with space"
        spaced.mkdir()
        self.refused(root=spaced)


if __name__ == "__main__":
    unittest.main()
