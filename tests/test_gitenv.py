"""Exercise git environment isolation."""

import os
import unittest
from unittest import mock

from gzlite.gitenv import clean_git_env


class CleanGitEnvTests(unittest.TestCase):
    def test_strips_every_git_variable_and_keeps_the_rest(self):
        patched = {
            "GIT_DIR": "x",
            "GIT_COMMON_DIR": "y",
            "GIT_INDEX_FILE": "z",
            "GIT_NAMESPACE": "n",
            "PATH": "keep-path",
            "GITHUB_TOKEN_LOOKALIKE": "kept-no-underscore-after-git",
        }
        with mock.patch.dict(os.environ, patched):
            cleaned = clean_git_env()
        self.assertFalse([key for key in cleaned if key.startswith("GIT_")])
        self.assertEqual(cleaned["PATH"], "keep-path")
        self.assertIn("GITHUB_TOKEN_LOOKALIKE", cleaned)

    def test_returns_a_copy(self):
        clean_git_env()["ADDED_BY_TEST"] = "1"
        self.assertNotIn("ADDED_BY_TEST", os.environ)


if __name__ == "__main__":
    unittest.main()
