"""Exercise the catalog check against fixture catalogs built in temporary directories."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from gzlite import catalog
from gzlite.cli import main

SKILL = "---\nname: {name}\ndescription: {name} text.\n---\n\n# {name}\n{floor}"
FLOOR = "\n## Discovery and fallback\n\nRun the project's own check.\n"
NAMES = ("gzs-alpha", "gzs-beta", "gzs-router")
EXPLICIT = ("gzs-beta",)
ADAPTER = 'const explicitOnly = new Set(["gzs-beta"]);\n'


def marketplace(ref: str) -> dict:
    return {"plugins": [{"name": "cat", "source": {"source": "url", "ref": ref}}]}


class CatalogTestCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gz-catalog-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for name in NAMES:
            body = SKILL.format(name=name, floor=FLOOR)
            if name == "gzs-router":
                rows = "".join(f"| Do {n} | `{n}` | note |\n" for n in NAMES if n != name)
                body += f"\n## Catalog\n\n| Need | Skill | Note |\n|---|---|---|\n{rows}"
            self.write(f"skills/{name}/SKILL.md", body)
            allow = "false" if name in EXPLICIT else "true"
            self.write(
                f"skills/{name}/agents/openai.yaml",
                f'interface:\n  display_name: "{name}"\npolicy:\n  allow_implicit_invocation: {allow}\n',
            )
        for relative in catalog.VERSION_FILES:
            self.write_json(relative, {"version": "1.2.3"})
        for relative in catalog.MARKETPLACES:
            self.write_json(relative, marketplace("v1.2.3"))
        self.write("adapters/opencode/cat.js", ADAPTER)

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def write_json(self, relative, data):
        self.write(relative, json.dumps(data))

    def checks(self):
        return [(f["check"], f["artifact"]) for f in catalog.check(self.root)]


class CheckTests(CatalogTestCase):
    def test_clean_catalog_has_no_findings(self):
        self.assertEqual(catalog.check(self.root), [])

    def test_inventory_lists_each_skill(self):
        records = catalog.inventory(self.root)
        self.assertEqual([r["name"] for r in records], list(NAMES))
        self.assertEqual(records[0]["path"], "skills/gzs-alpha/SKILL.md")
        self.assertTrue(all(r["declares_floor"] and len(r["tree_sha256"]) == 64 for r in records))

    def test_missing_skills_directory_is_an_error(self):
        with (
            tempfile.TemporaryDirectory(prefix="gz-empty-") as empty,
            self.assertRaises(ValueError),
        ):
            catalog.check(Path(empty))

    def test_floor_missing_is_a_finding_and_listed_is_exempt(self):
        self.write("skills/gzs-alpha/SKILL.md", SKILL.format(name="gzs-alpha", floor=""))
        self.assertEqual(self.checks(), [("floor", "skills/gzs-alpha/SKILL.md")])
        self.write_json(catalog.DATA_FILE, {"schema_version": 1, "floor_pending": ["gzs-alpha"]})
        self.assertEqual(self.checks(), [])

    def test_empty_floor_section_does_not_count(self):
        self.write(
            "skills/gzs-alpha/SKILL.md",
            SKILL.format(name="gzs-alpha", floor="\n## Discovery and fallback\n\n## Next\n"),
        )
        self.assertEqual(self.checks(), [("floor", "skills/gzs-alpha/SKILL.md")])

    def test_floor_ratchet_flags_a_repaired_skill_still_listed(self):
        self.write_json(catalog.DATA_FILE, {"schema_version": 1, "floor_pending": ["gzs-alpha"]})
        found = catalog.check(self.root)
        self.assertEqual([f["check"] for f in found], ["floor"])
        self.assertIn("remove it from floor_pending", found[0]["message"])

    def test_floor_pending_naming_no_skill_is_a_finding(self):
        self.write_json(catalog.DATA_FILE, {"schema_version": 1, "floor_pending": ["gone"]})
        self.assertEqual(self.checks(), [("floor", catalog.DATA_FILE)])

    def test_malformed_data_file_is_a_finding(self):
        self.write_json(catalog.DATA_FILE, {"schema_version": 2})
        self.assertEqual(self.checks(), [("catalog-data", catalog.DATA_FILE)])
        self.write(catalog.DATA_FILE, "{")
        self.assertEqual(self.checks(), [("catalog-data", catalog.DATA_FILE)])

    def test_versions_must_agree(self):
        self.write_json(".codex-plugin/plugin.json", {"version": "1.2.4"})
        found = catalog.check(self.root)
        self.assertEqual([f["check"] for f in found], ["versions"])
        self.assertIn("1.2.4", found[0]["message"])

    def test_versions_compare_only_manifests_present(self):
        (self.root / ".codex-plugin" / "plugin.json").unlink()
        self.assertEqual(catalog.check(self.root), [])

    def test_unparseable_manifest_is_a_finding(self):
        self.write("package.json", "not json")
        self.assertEqual(self.checks(), [("versions", "package.json")])

    def test_pins_must_agree(self):
        self.write_json(".agents/plugins/marketplace.json", marketplace("v1.2.4"))
        self.assertEqual(self.checks(), [("pins", ".claude-plugin/marketplace.json")])

    def test_pin_may_use_sha_in_one_marketplace(self):
        sha = "a" * 40
        self.write_json(
            ".claude-plugin/marketplace.json",
            {"plugins": [{"name": "cat", "source": {"sha": sha}}]},
        )
        self.write_json(".agents/plugins/marketplace.json", marketplace(sha))
        self.assertEqual(catalog.check(self.root), [])

    def test_router_must_list_every_skill_in_its_table(self):
        self.write(
            "skills/gzs-router/SKILL.md",
            SKILL.format(name="gzs-router", floor=FLOOR) + "\nMentions `gzs-alpha` in prose.\n",
        )
        found = catalog.check(self.root)
        self.assertEqual([f["check"] for f in found], ["router", "router"])
        self.assertEqual({f["artifact"] for f in found}, {"skills/gzs-router/SKILL.md"})

    def test_explicit_only_sets_must_agree(self):
        self.write("adapters/opencode/cat.js", 'const explicitOnly = new Set(["gzs-alpha"]);\n')
        self.assertEqual(self.checks(), [("explicit-only", "adapters/opencode/cat.js")])

    def test_adapter_literal_accepts_single_quotes_and_multiple_lines(self):
        self.write(
            "adapters/opencode/cat.js", "const explicitOnly = new Set([\n  'gzs-beta',\n]);\n"
        )
        self.assertEqual(catalog.check(self.root), [])

    def test_unrecognised_adapter_shape_is_a_finding(self):
        for text in ("const explicitOnly = loadNames();\n", "explicitOnly = new Set([name]);\n"):
            self.write("adapters/opencode/cat.js", text)
            self.assertEqual(self.checks(), [("explicit-only", "adapters/opencode/cat.js")])

    def test_unrecognised_policy_value_is_a_finding(self):
        self.write(
            "skills/gzs-alpha/agents/openai.yaml",
            "policy:\n  allow_implicit_invocation: maybe\n",
        )
        self.assertEqual(self.checks(), [("explicit-only", "skills/gzs-alpha/agents/openai.yaml")])

    def test_policy_key_outside_policy_block_is_a_finding(self):
        self.write(
            "skills/gzs-alpha/agents/openai.yaml",
            "interface:\n  allow_implicit_invocation: false\n",
        )
        self.assertEqual(self.checks(), [("explicit-only", "skills/gzs-alpha/agents/openai.yaml")])

    def test_skill_name_must_match_directory(self):
        self.write(
            "skills/gzs-alpha/SKILL.md",
            SKILL.format(name="gzs-other", floor=FLOOR),
        )
        self.assertEqual(self.checks(), [("skill-name", "skills/gzs-alpha/SKILL.md")])


class CommandTests(CatalogTestCase):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_exit_zero_when_clean(self):
        code, out, _ = self.run_main("catalog", "check", "--root", str(self.root))
        self.assertEqual((code, json.loads(out)), (0, []))

    def test_exit_one_with_indented_findings(self):
        self.write_json("package.json", {"version": "9.9.9"})
        code, out, _ = self.run_main("catalog", "check", "--root", str(self.root))
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)[0]["check"], "versions")
        self.assertIn('\n  {\n    "check"', out)

    def test_exit_two_without_skills_directory(self):
        with tempfile.TemporaryDirectory(prefix="gz-empty-") as empty:
            code, out, err = self.run_main("catalog", "check", "--root", empty)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("error:", err)

    def test_exit_two_for_unknown_subcommand(self):
        with self.assertRaises(SystemExit) as raised, redirect_stderr(io.StringIO()):
            main(["catalog", "bogus"])
        self.assertEqual(raised.exception.code, 2)

    def test_inventory_prints_records(self):
        code, out, _ = self.run_main("catalog", "inventory", "--root", str(self.root))
        self.assertEqual(code, 0)
        self.assertEqual([r["name"] for r in json.loads(out)], list(NAMES))


if __name__ == "__main__":
    unittest.main()
