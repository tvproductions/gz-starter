"""Exercise actual unittest outcomes and pre-commit transitions."""

import hashlib
import os

from test_verification import PROJECT, ROOT, VerificationProject, run

PASSING_TEST = """import unittest

class TotalsTests(unittest.TestCase):
    def test_reached_behavior(self):
        with self.subTest(value=2):
            self.assertEqual(2 + 3, 5)
"""
FAILING_TEST = PASSING_TEST.replace("2 + 3, 5", "2 + 3, 6, 'reached negative assertion'")
TOP = '\n[tool.gz-starter.verify]\ntop_level = "."\n'


class VerificationUnittestTests(VerificationProject):
    def test_passing_sibling_does_not_mask_an_omitted_module(self):
        self.write("tests/test_totals.py", PASSING_TEST)
        self.write("tests/hidden/test_other.py", FAILING_TEST)
        self.assert_blocked("tests/hidden/test_other.py")
        self.write("tests/hidden/__init__.py", "")
        self.assert_blocked("reached negative assertion")

    def test_owned_success_with_subtests_passes(self):
        self.write("tests/test_totals.py", PASSING_TEST)
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("behavior PASS", result.stdout)
        self.assertIn("1 successful adopter test", result.stdout)

    def test_default_discovery_can_import_a_flat_project_module(self):
        self.write("totals.py", "def combine(left, right): return left + right\n")
        self.write(
            "tests/test_totals.py",
            "import totals\n" + PASSING_TEST.replace("2 + 3", "totals.combine(2, 3)"),
        )
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_verifier_runs_current_source_even_with_a_stale_bytecode_timestamp(self):
        target = self.write("tests/test_totals.py", PASSING_TEST)
        original_stat = target.stat()
        self.assertEqual(self.verify().returncode, 0)
        self.write("tests/test_totals.py", PASSING_TEST.replace("2 + 3, 5", "2 + 3, 6"))
        os.utime(target, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        self.assert_blocked("5 != 6")

    def test_only_successful_adopter_cases_count(self):
        for declaration in (
            "    @unittest.skip('fixture skip')\n"
            "    def test_reached_behavior(self): self.fail()\n",
            "    @unittest.expectedFailure\n    def test_reached_behavior(self): self.fail()\n",
            "    def test_reached_behavior(self):\n"
            "        with self.subTest(value=1): self.skipTest('fixture subtest')\n",
        ):
            with self.subTest(declaration=declaration):
                self.write(
                    "tests/test_totals.py",
                    "import unittest\nclass TotalsTests(unittest.TestCase):\n" + declaration,
                )
                self.assert_blocked("no successful adopter test")

    def test_discovery_and_runner_failures_preserve_diagnostics(self):
        for fixture, message in (
            (FAILING_TEST, "reached negative assertion"),
            ("import unavailable_example_dependency\n", "unavailable_example_dependency"),
            ("def broken(:\n", "SyntaxError"),
            (
                "def load_tests(loader, suite, pattern):\n    raise ValueError('loader fault')\n",
                "loader fault",
            ),
            (
                PASSING_TEST.replace(
                    "    def test_", "    @unittest.expectedFailure\n    def test_"
                ),
                "unexpected success",
            ),
        ):
            with self.subTest(message=message):
                self.write("tests/test_totals.py", fixture)
                self.assert_blocked(message)

    def test_module_without_collected_cases_never_passes(self):
        self.write("tests/test_totals.py", PASSING_TEST)
        for fixture in (
            "# No test cases.\n",
            "def load_tests(loader, suite, pattern): return []\n",
        ):
            with self.subTest(fixture=fixture):
                self.write("tests/test_other.py", fixture)
                self.assert_blocked("tests/test_other.py")

    def test_support_class_and_a_nonglobbed_loader_have_distinct_roles(self):
        self.write("tests/test_totals.py", PASSING_TEST)
        self.write("tests/fakes.py", "class FakeSender:\n    def test_only(self): pass\n")
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write(
            "tests/check_optional.py",
            "def collect(loader, suite, pattern): return []\nload_tests = collect\n",
        )
        self.assert_blocked("tests/check_optional.py")

    def test_package_aggregator_accounts_for_owned_children(self):
        self.write("pyproject.toml", PROJECT + TOP)
        self.write(
            "tests/__init__.py",
            "from . import test_totals\n"
            "def load_tests(loader, suite, pattern):\n"
            "    return loader.loadTestsFromModule(test_totals)\n",
        )
        self.write("tests/test_totals.py", PASSING_TEST)
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write("tests/test_other.py", FAILING_TEST)
        self.assert_blocked("tests/test_other.py")

    def test_discovery_bounds_and_pattern_do_not_hide_test_assets(self):
        self.write("tests/test_totals.py", PASSING_TEST)
        self.write("checks/test_outside.py", FAILING_TEST)
        self.assert_blocked("checks/test_outside.py")
        (self.root / "checks/test_outside.py").unlink()
        self.write("pyproject.toml", PROJECT + '\n[tool.gz-starter.verify]\npattern = "no*.py"\n')
        self.assert_blocked("tests/test_totals.py")
        self.write("pyproject.toml", PROJECT + '\n[tool.gz-starter.verify]\nstart = "../outside"\n')
        self.assert_blocked("start")

    def test_cases_from_outside_checkout_do_not_count(self):
        self.write(
            "tests/test_totals.py",
            "import unittest\n"
            "def load_tests(loader, suite, pattern):\n"
            "    return unittest.TestSuite([unittest.TestCase()])\n",
        )
        self.assert_blocked("outside the checkout")

    def test_dynamic_suite_cannot_replace_the_collected_cases(self):
        self.write(
            "tests/test_totals.py",
            FAILING_TEST + "\nclass ReplacingSuite(unittest.TestSuite):\n"
            "    def run(self, result, debug=False):\n"
            "        unittest.FunctionTestCase(lambda: None)(result)\n"
            "        return result\n"
            "def load_tests(loader, suite, pattern): return ReplacingSuite(suite)\n",
        )
        self.assert_blocked("unittest suite")

    def test_unchanged_hook_moves_from_bootstrap_to_owned_suite(self):
        project = (
            PROJECT + TOP + "\n[dependency-groups]\n"
            'dev = ["gz-starter[verification]", "pre-commit==4.7.0"]\n'
            f'\n[tool.uv.sources]\ngz-starter = {{ path = "{ROOT.as_posix()}", editable = true }}\n'
        )
        self.write("pyproject.toml", project)
        self.write(".gitignore", ".venv/\n__pycache__/\n")
        hook = self.root / ".pre-commit-config.yaml"
        digest = hashlib.sha256(hook.read_bytes()).digest()
        for command in (("git", "init"), ("git", "add", "."), ("uv", "lock", "--offline")):
            setup = run(self.root, *command)
            self.assertEqual(setup.returncode, 0, setup.stderr)

        def gate():
            return run(self.root, "uv", "run", "--locked", "pre-commit", "run", "--all-files", "-v")

        result = gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("not applicable: pre-implementation", result.stdout)
        self.write("totals.py", "def combine(left, right): return left + right\n")
        result = gate()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("totals.py", result.stdout)
        self.write("tests/__init__.py", "")
        self.write(
            "tests/test_totals.py",
            "import totals\n" + FAILING_TEST.replace("2 + 3", "totals.combine(2, 3)"),
        )
        result = gate()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("reached negative assertion", result.stdout)
        self.write(
            "tests/test_totals.py",
            "import totals\n" + PASSING_TEST.replace("2 + 3", "totals.combine(2, 3)"),
        )
        result = gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("behavior PASS", result.stdout)
        self.assertEqual(hashlib.sha256(hook.read_bytes()).digest(), digest)

    def test_passing_verifier_leaves_the_existing_coverage_failure_red(self):
        self.write(
            "pyproject.toml", PROJECT + TOP + '\n[dependency-groups]\ndev = ["coverage==7.17.4"]\n'
        )
        self.write(
            "totals.py",
            "def combine(value):\n    if value > 0:\n        return value\n    return 0\n",
        )
        self.write("tests/__init__.py", "")
        self.write(
            "tests/test_totals.py",
            "import totals\n" + PASSING_TEST.replace("2 + 3", "totals.combine(5)"),
        )
        lock = run(self.root, "uv", "lock", "--offline")
        self.assertEqual(lock.returncode, 0, lock.stderr)
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        coverage = run(
            self.root,
            "uv",
            "run",
            "--locked",
            "coverage",
            "run",
            "--source=totals",
            "--branch",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-t",
            ".",
        )
        self.assertEqual(coverage.returncode, 0, coverage.stderr)
        result = run(self.root, "uv", "run", "--locked", "coverage", "report", "--fail-under=100")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Coverage failure", result.stdout)
