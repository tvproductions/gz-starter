"""Exercise the adopter verifier at its command-line boundary."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_PIN = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
HOOK = """repos:
  - repo: local
    hooks:
      - id: unittest
        name: unittest and bootstrap verification
        entry: uv run --locked gz-starter verify --project .
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
"""
PROJECT = """[project]
name = "sample-totals"
version = "0.1.0"
readme = "README.md"
requires-python = ">=3.14,<3.15"

[tool.uv]
package = false
required-version = ">=0.13.5"
python-preference = "only-managed"
"""
WORKFLOW_PATH = ".github/workflows/verify-python.yml"
DESIGN = ROOT / "docs/superpowers/specs/2026-11-21-bootstrap-verification-design-edition-3.md"
WORKFLOW = DESIGN.read_text(encoding="utf-8").split("```yaml\n")[2].split("```", 1)[0]


def run(root: Path, *command: str) -> subprocess.CompletedProcess[str]:
    """Run a real fixture command outside the producer checkout."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV", "PYTHONPATH", "SKIP"}
        and not key.startswith("GIT_")
    }
    return subprocess.run(
        command,
        cwd=root,
        env=env,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


class VerificationProject(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="gz-verify-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.write("pyproject.toml", PROJECT)
        self.write("README.md", "# Sample totals\n")
        self.write(".python-version", PYTHON_PIN + "\n")
        self.write(".pre-commit-config.yaml", HOOK)
        lock = run(self.root, "uv", "lock", "--offline")
        self.assertEqual(lock.returncode, 0, lock.stderr)

    def write(self, path: str, content: str) -> Path:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        return target

    def verify(self):
        return run(
            self.root, sys.executable, "-m", "skills_first_starter", "verify", "--project", "."
        )

    def assert_blocked(self, *messages):
        result = self.verify()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("bootstrap PASS", result.stdout)
        for message in messages:
            self.assertIn(message, result.stdout + result.stderr)


class VerificationCliTests(VerificationProject):
    def test_canonical_bootstrap_validates_state_and_legacy_cannot_pass(self):
        self.write(".gz-starter/bundle.lock.json", "{}")
        state = self.write(".gz-starter/settings.toml", "invalid TOML")
        self.assert_blocked(".gz-starter/settings.toml")
        state.write_text("enabled = true\n", encoding="utf-8")
        self.write(".skills-first/other.md", "# Unrelated\n")
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        legacy = self.write(".skills-first/settings.toml", "enabled = true\n")
        self.assert_blocked(".skills-first/settings.toml", "migration")
        self.assertEqual(legacy.read_bytes(), b"enabled = true\n")
        state.unlink()
        (self.root / ".gz-starter/bundle.lock.json").unlink()
        self.assert_blocked(".skills-first/settings.toml", "migration")

    def test_locked_docs_config_and_supported_workflow_pass(self):
        for trigger_key in ("on:", "'on':"):
            with self.subTest(trigger_key=trigger_key):
                self.write(WORKFLOW_PATH, WORKFLOW.replace("on:\n", trigger_key + "\n", 1))
                result = self.verify()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("not applicable: pre-implementation", result.stdout)
                self.assertIn("README.md", result.stdout)
                self.assertIn(WORKFLOW_PATH, result.stdout)

    def test_broken_artifact_fails_before_bootstrap_and_lock_is_preserved(self):
        initial_lock = (self.root / "uv.lock").read_bytes()
        for path, contents in (
            ("pyproject.toml", "[project\n"),
            ("pyproject.toml", PROJECT.replace("0.1.0", "0.2.0")),
            (".codex/config.toml", "unset ="),
            (".gz-skills/settings.json", "{"),
            ("README.md", "[Details](missing.md)"),
            (WORKFLOW_PATH, "jobs: ["),
        ):
            with self.subTest(path=path, contents=contents):
                target = self.root / path
                previous = target.read_bytes() if target.exists() else None
                self.write(path, contents)
                self.assert_blocked("uv.lock" if "0.2.0" in contents else path)
                self.assertEqual((self.root / "uv.lock").read_bytes(), initial_lock)
                if previous is None:
                    target.unlink()
                else:
                    target.write_bytes(previous)
        (self.root / "uv.lock").unlink()
        self.assert_blocked("uv.lock")
        self.assertFalse((self.root / "uv.lock").exists())

    def test_missing_readme_and_broken_local_anchor_fail(self):
        (self.root / "README.md").unlink()
        self.assert_blocked("README.md")
        self.write("README.md", "[Missing](#missing)\n")
        self.assert_blocked("#missing")

    def test_balanced_parentheses_in_a_local_markdown_link_are_supported(self):
        self.write("README.md", "[Notes](docs/note(sample).md#overview)\n")
        self.write("docs/note(sample).md", "# Overview\n")
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_disabled_or_ambiguous_hook_cannot_pass_direct_verification(self):
        for change in (
            "repos: []\n",
            HOOK + HOOK[HOOK.index("      - id:") :],
            HOOK.replace("[pre-commit]", "[manual]"),
            HOOK + "        files: '^src/'\n",
            HOOK.replace("always_run: true", "always_run: 1"),
            HOOK + "exclude: '^docs/'\n",
            HOOK + "repos: []\n",
        ):
            with self.subTest(change=change):
                self.write(".pre-commit-config.yaml", change)
                self.assert_blocked(".pre-commit-config.yaml")
        (self.root / ".pre-commit-config.yaml").unlink()
        self.assert_blocked(".pre-commit-config.yaml")

    def test_routine_hook_with_existing_flags_preserves_bootstrap(self):
        self.write(
            ".pre-commit-config.yaml",
            HOOK + "      - id: ruff-check\n        name: Ruff check\n"
            "        entry: uv run --locked ruff check --quiet\n        language: system\n",
        )
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_changed_workflow_shape_and_unsafe_yaml_fail(self):
        for change in (
            WORKFLOW.replace("shell: pwsh", "shell: cmd"),
            WORKFLOW.replace("uv sync --locked", "uv sync", 1),
            WORKFLOW.replace("push:\n", "push:\n    paths: ['src/**']\n", 1),
            WORKFLOW.replace("shell: pwsh", "shell: pwsh\n        name: invalid", 1),
            WORKFLOW.replace("runs-on: macos-15", "runs-on: macos-15\n    if: false"),
            WORKFLOW.replace("      - name: Run project gate", "      - continue-on-error: true"),
            WORKFLOW + "jobs: {}\n",
            WORKFLOW + "---\njobs: {}\n",
            WORKFLOW + "extra: !special x\n",
            "base: &base {name: value}\ncopy: {<<: *base}\n",
        ):
            with self.subTest(change=change[-30:]):
                self.write(WORKFLOW_PATH, change)
                self.assert_blocked(WORKFLOW_PATH)

    def test_artifacts_require_tests_even_when_ignored_untracked_or_outside_src(self):
        self.write(".gitignore", "scraps/\n")
        for path, contents in (
            ("scraps/totals.py", "total = 42\n"),
            ("bin/reconcile", "#!/bin/sh\nexit 0\n"),
            ("maintenance/tools.ps1", "Write-Output 'example'\n"),
            (".github/workflows/extra.yml", "jobs: {other: {steps: [{run: echo sample}]}}\n"),
            (".github/actions/local/action.yml", "runs: {using: composite, steps: []}\n"),
        ):
            with self.subTest(path=path):
                target = self.write(path, contents)
                self.assert_blocked(path, "test")
                target.unlink()

    def test_extensionless_git_executable_mode_requires_tests(self):
        target = self.write("run-summary", "example command\n")
        for args in (("init",), ("add", "--chmod=+x", target.name)):
            result = run(self.root, "git", *args)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_blocked(target.name, "test")

    def test_workspace_is_rejected_without_rewriting_its_hook(self):
        self.write("pyproject.toml", PROJECT + "\n[tool.uv.workspace]\nmembers = []\n")
        self.assert_blocked("workspace")
        self.assertEqual((self.root / ".pre-commit-config.yaml").read_bytes(), HOOK.encode())

    def test_standalone_tool_config_does_not_hide_the_owning_project_settings(self):
        self.write("legacy/.ruff.toml", "line-length = 90\n")
        self.assert_blocked("legacy/.ruff.toml", "pyproject.toml")

    def test_sensitive_file_is_inventory_only(self):
        self.write(".env", "#!/bin/sh\nDO_NOT_DISPLAY_EXAMPLE_SECRET\n")
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("DO_NOT_DISPLAY_EXAMPLE_SECRET", result.stdout + result.stderr)

    def test_opaque_reference_is_not_a_verification_input_but_authored_paths_are(self):
        self.write("docs/reference material.pdf", "not opened by the verifier")
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("reference material.pdf", result.stdout)
        self.write("tools/invalid name.py", "print('must not execute')\n")
        self.assert_blocked("tools/invalid name.py", "spaces are unsupported")

    def test_regular_file_skill_aliases_are_limited_to_exact_targets(self):
        self.write("templates/skills/update-gz-template/SKILL.md", "# Update\n")
        for alias in (".agents", ".claude"):
            self.write(
                f"{alias}/skills/update-gz-template", "../../templates/skills/update-gz-template"
            )
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write(".agents/skills/update-gz-template", "../../other")
        self.assert_blocked(".agents/skills/update-gz-template")

    def test_installed_update_skill_directory_is_an_ordinary_adopter_asset(self):
        self.write(".agents/skills/update-gz-template/SKILL.md", "# Update\n")
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("update-gz-template/SKILL.md", result.stdout)

    def test_native_opencode_jsonc_preserves_valid_comments_and_trailing_commas(self):
        path = self.write("opencode.jsonc", '{\n  // local settings\n  "plugin": [],\n}\n')
        before = path.read_bytes()
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(path.read_bytes(), before)

    def test_symlinked_source_and_excluded_directory_fail(self):
        try:
            (self.root / "linked.py").symlink_to(self.root / "README.md")
        except OSError as error:
            self.skipTest(f"symlinks unavailable: {error.__class__.__name__}")
        self.assert_blocked("linked.py")
        (self.root / "linked.py").unlink()
        (self.root / ".venv").symlink_to(self.root, target_is_directory=True)
        self.assert_blocked(".venv")

    @unittest.skipIf(os.name == "nt", "requires POSIX file modes")
    def test_unreadable_path_fails(self):
        path = self.write("unreadable.txt", "example")
        path.chmod(0)
        self.addCleanup(path.chmod, 0o600)
        self.assert_blocked("unreadable.txt")

    @unittest.skipUnless(os.name == "nt", "requires Windows junctions")
    def test_windows_junction_is_rejected_before_traversal(self):
        target = self.root / "elsewhere"
        target.mkdir()
        sentinel = target / "sentinel.txt"
        sentinel.write_bytes(b"external content")
        for name in ("linked", ".skills-first", ".gz-starter"):
            with self.subTest(name=name):
                junction = self.root / name
                result = run(
                    self.root, "cmd", "/d", "/c", "mklink", "/J", str(junction), str(target)
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                try:
                    self.assert_blocked(name)
                    self.assertEqual(sentinel.read_bytes(), b"external content")
                finally:
                    junction.rmdir()

    @unittest.skipIf(os.name == "nt", "Windows junction coverage runs separately")
    def test_state_links_are_rejected_before_verification_reads_files(self):
        state = self.root / ".skills-first"
        state.mkdir()
        external = self.write("elsewhere/sentinel.txt", "external content")
        marker = state / "settings.toml"
        marker.symlink_to(external)
        self.assert_blocked("starter state symlink", ".skills-first/settings.toml")
        self.assertEqual(external.read_bytes(), b"external content")


if __name__ == "__main__":
    unittest.main()
