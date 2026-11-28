"""Exercise the portability audit through the module and the public command."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gzlite.gitenv import clean_git_env
from gzlite.portability import audit

CAPTURE = "import subprocess\nsubprocess.run(['x'], {flags})\n"


class PortabilityTestCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gz-port-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def write(self, name, text, newline=None):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline=newline) as handle:
            handle.write(text)

    def git(self, *args):
        # A hook's inherited GIT_* variables would redirect to the outer repository.
        subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            check=True,
            env=clean_git_env(),
            errors="replace",
            text=True,
        )


class LineEndingTests(PortabilityTestCase):
    def test_missing_gitattributes(self):
        found = audit(self.root, ["line-endings"], [])
        self.assertEqual([f["artifact"] for f in found], [".gitattributes"])
        self.assertEqual(found[0]["check"], "line-endings")
        self.assertIn("Missing", found[0]["message"])

    def test_gitattributes_without_directive(self):
        self.write(".gitattributes", "*.png binary\n")
        found = audit(self.root, ["line-endings"], [])
        self.assertEqual(len(found), 1)
        self.assertIn("lacks", found[0]["message"])

    def test_directive_present_is_clean(self):
        self.write(".gitattributes", "* text=auto eol=lf\n")
        self.assertEqual(audit(self.root, ["line-endings"], []), [])

    def test_crlf_in_index_names_the_file(self):
        self.write(".gitattributes", "* text=auto eol=lf\n")
        self.write("docs/notes.md", "one\r\ntwo\r\n", newline="")
        self.git("init", "-q")
        self.git("config", "core.autocrlf", "false")
        # Bypass the attribute so the CRLF blob lands in the index unchanged.
        self.write(".gitattributes", "* -text\n")
        self.git("add", "docs/notes.md")
        self.write(".gitattributes", "* text=auto eol=lf\n")
        found = audit(self.root, ["line-endings"], [])
        self.assertEqual([f["artifact"] for f in found], ["docs/notes.md"])

    def test_non_git_directory_skips_index_scan(self):
        self.write(".gitattributes", "* text=auto eol=lf\n")
        self.write("a.md", "x\r\n", newline="")
        self.assertEqual(audit(self.root, ["line-endings"], []), [])


class SubprocessErrorsTests(PortabilityTestCase):
    def findings(self, flags, paths=()):
        self.write("tool.py", CAPTURE.format(flags=flags))
        return audit(self.root, ["subprocess-errors"], list(paths))

    def test_text_capture_without_errors_is_flagged(self):
        found = self.findings("capture_output=True, text=True")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["check"], "subprocess-errors")
        self.assertEqual(found[0]["artifact"], "tool.py:2")

    def test_errors_argument_is_clean(self):
        self.assertEqual(self.findings("capture_output=True, text=True, errors='replace'"), [])

    def test_binary_capture_is_clean(self):
        self.assertEqual(self.findings("capture_output=True"), [])

    def test_encoding_and_pipe_forms_are_flagged(self):
        self.assertEqual(len(self.findings("stdout=subprocess.PIPE, encoding='utf-8'")), 1)

    def test_pruned_directories_and_paths(self):
        self.write("node_modules/dep/x.py", CAPTURE.format(flags="text=True, capture_output=True"))
        self.write("src/y.py", CAPTURE.format(flags="text=True, capture_output=True"))
        self.write("other/z.py", CAPTURE.format(flags="text=True, capture_output=True"))
        found = audit(self.root, ["subprocess-errors"], ["src"])
        self.assertEqual([f["artifact"] for f in found], ["src/y.py:2"])
        everywhere = audit(self.root, ["subprocess-errors"], [])
        self.assertEqual([f["artifact"] for f in everywhere], ["other/z.py:2", "src/y.py:2"])


class CommandTests(PortabilityTestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "gzlite", "portability", *args],
            capture_output=True,
            check=False,
            cwd=self.root,
            env=clean_git_env(),
            errors="replace",
            text=True,
        )

    def test_clean_exits_zero_with_empty_list(self):
        self.write("ok.py", "print('hi')\n")
        done = self.run_cli("--root", str(self.root), "--check", "subprocess-errors")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), [])

    def test_findings_exit_one(self):
        done = self.run_cli("--root", str(self.root))
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertEqual(json.loads(done.stdout)[0]["artifact"], ".gitattributes")

    def test_unknown_check_exits_two(self):
        done = self.run_cli("--root", str(self.root), "--check", "nope")
        self.assertEqual(done.returncode, 2)

    def test_bad_root_and_bad_path_exit_two(self):
        self.assertEqual(self.run_cli("--root", str(self.root / "missing")).returncode, 2)
        done = self.run_cli("--root", str(self.root), "--path", "missing")
        self.assertEqual(done.returncode, 2)

    def test_command_writes_nothing(self):
        self.run_cli("--root", str(self.root))
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
