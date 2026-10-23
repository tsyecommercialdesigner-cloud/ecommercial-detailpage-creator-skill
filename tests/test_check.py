import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check


class PackageChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="detailpage-check-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "中文 space" / "demo-skill"
        self.root.mkdir(parents=True)
        self.entry = self.root / "SKILL.md"
        self.entry.write_text('---\nname: "demo-skill"\ndescription: "测试详情页"\n---\n# 正文\n', encoding="utf-8")

    def test_valid_unicode_and_space_path(self):
        self.assertEqual(check.read_metadata(self.entry)["name"], "demo-skill")

    def test_yaml_plain_and_multiline_strings(self):
        self.entry.write_text("---\nname: demo-skill\ndescription: >-\n  根据产品图\n  设计详情页\n---\n# 正文\n", encoding="utf-8")
        self.assertEqual(check.read_metadata(self.entry)["description"], "根据产品图 设计详情页")

    def test_yaml_rejects_unsafe_tags_and_non_mapping(self):
        for payload in ["!!python/object/apply:os.system ['echo unsafe']", "[name, description]"]:
            with self.subTest(payload=payload):
                self.entry.write_text(f"---\n{payload}\n---\n# 正文\n", encoding="utf-8")
                with self.assertRaises(ValueError): check.read_metadata(self.entry)

    def test_invalid_metadata(self):
        initial = self.entry.read_text(encoding="utf-8")
        for invalid in [initial.replace('"demo-skill"', '"wrong-name"'),
                        initial.replace('"demo-skill"', '"Bad--name"'),
                        initial.replace('"测试详情页"', '""'),
                        initial.replace('"测试详情页"', '12'),
                        initial.replace('"测试详情页"', json.dumps("长" * 1025)),
                        initial.replace('# 正文', ''),
                        initial.replace('---\n# 正文', '# 正文'),
                        initial.replace('description:', 'name:')]:
            with self.subTest(invalid=invalid):
                self.entry.write_text(invalid, encoding="utf-8")
                with self.assertRaises(ValueError):
                    check.read_metadata(self.entry)

    def test_valid_relative_link_and_anchor(self):
        (self.root / "资料.md").write_text("# 中文标题\n", encoding="utf-8")
        self.entry.write_text("[资料](%E8%B5%84%E6%96%99.md#中文标题)", encoding="utf-8")
        self.assertEqual(check.check_links(self.entry, self.root), [])

    def test_same_file_anchor(self):
        self.entry.write_text("# 当前章节\n[跳转](#当前章节)\n", encoding="utf-8")
        self.assertEqual(check.check_links(self.entry, self.root), [])

    def test_broken_target_and_anchor(self):
        for link in ["missing.md", "SKILL.md#不存在"]:
            with self.subTest(link=link):
                self.entry.write_text(f"[资料]({link})", encoding="utf-8")
                self.assertTrue(check.check_links(self.entry, self.root))

    def test_escape_even_when_target_exists(self):
        (self.root.parent / "outside.md").write_text("# Outside", encoding="utf-8")
        self.entry.write_text("[outside](../outside.md)", encoding="utf-8")
        self.assertIn("escapes boundary", check.check_links(self.entry, self.root)[0])

    def test_windows_case_mismatch(self):
        (self.root / "Reference.md").write_text("# Header", encoding="utf-8")
        self.entry.write_text("[ref](reference.md)", encoding="utf-8")
        self.assertTrue(check.check_links(self.entry, self.root))

    def test_external_url_is_not_fetched(self):
        self.entry.write_text("[external](https://example.invalid/test)", encoding="utf-8")
        self.assertEqual(check.check_links(self.entry, self.root), [])

    def test_symlink_escape_if_available(self):
        outside = self.root.parent / "outside.md"
        outside.write_text("# Outside", encoding="utf-8")
        try:
            (self.root / "link.md").symlink_to(outside)
        except OSError:
            self.skipTest("symlink creation unavailable")
        self.entry.write_text("[outside](link.md)", encoding="utf-8")
        self.assertIn("escapes boundary", check.check_links(self.entry, self.root)[0])

    def test_case_data_failures(self):
        data = json.loads((check.REPO / "evals/cases.json").read_text(encoding="utf-8"))
        path = self.root / "cases.json"
        variants = []
        for kind in ["empty", "duplicate", "routing", "rubric", "expected"]:
            invalid = copy.deepcopy(data)
            if kind == "empty":
                invalid["cases"] = []
            elif kind == "duplicate":
                invalid["cases"].append(copy.deepcopy(invalid["cases"][0]))
            elif kind == "routing":
                invalid["cases"][0]["expected_selection"] = "maybe"
            elif kind == "rubric":
                invalid["rubric_version"] = "2"
            else:
                invalid["cases"][0]["expected"] = []
            variants.append(invalid)
        for invalid in variants:
            with self.subTest(invalid=invalid):
                path.write_text(json.dumps(invalid), encoding="utf-8")
                with self.assertRaises(ValueError):
                    check.check_cases(path)

    def test_entrypoint_from_another_working_directory(self):
        result = subprocess.run([sys.executable, str(check.REPO / "scripts/check.py")],
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_entrypoint_returns_failure(self):
        entrypoint = self.root / "scripts/check.py"
        entrypoint.parent.mkdir()
        entrypoint.write_text((check.REPO / "scripts/check.py").read_text(encoding="utf-8"), encoding="utf-8")
        result = subprocess.run([sys.executable, str(entrypoint)], cwd=self.root,
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL:", result.stderr)


if __name__ == "__main__":
    unittest.main()
