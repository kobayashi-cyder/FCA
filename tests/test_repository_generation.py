import unittest

from fca.repository_generation import (
    FCARepositoryGenerator,
    RepositoryGenerationError,
)


class FCARepositoryGenerationTests(unittest.TestCase):
    def setUp(self):
        self.generator = FCARepositoryGenerator()

    def test_creates_module_and_focused_test_without_touching_snapshot(self):
        snapshot = {
            "README.md": "# demo\n",
            "fca/existing.py": "VALUE = 1\n",
        }
        before = dict(snapshot)
        result = self.generator.generate(
            "Pythonコードを作って。テキストから数字だけ抽出して合計する。"
        , snapshot)

        self.assertTrue(result.ok)
        self.assertEqual(snapshot, before)
        self.assertEqual(result.state, "generated_candidate")
        self.assertEqual(len(result.edits), 2)
        self.assertTrue(result.target_path.startswith("generated/fca_program_"))
        self.assertEqual(result.edits[0].operation, "create")
        self.assertEqual(result.edits[0].before_sha256, "")
        self.assertTrue(result.edits[1].path.startswith("tests/test_"))
        self.assertIn("focused_test_generated", result.checks)
        self.assertEqual(len(result.plan_id), 64)
        self.assertEqual(len(result.repository_digest), 64)

    def test_explicit_target_path_is_respected(self):
        result = self.generator.generate(
            "tools/stats.py にPythonコードを作って、数字を抽出して平均を出す",
            {},
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.target_path, "tools/stats.py")
        self.assertEqual(result.edits[0].path, "tools/stats.py")

    def test_existing_arbitrary_file_is_never_overwritten(self):
        snapshot = {
            "tools/stats.py": "print('human authored')\n",
        }
        result = self.generator.generate(
            "tools/stats.py をPythonコードで更新して、数字を抽出して合計する",
            snapshot,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.edits, ())
        self.assertIn("existing_target_not_fca_generated", result.errors)

    def test_existing_fca_generated_file_can_be_regenerated(self):
        first = self.generator.generate(
            "tools/stats.py にPythonコードを作って、数字を抽出して合計する",
            {},
        )
        self.assertTrue(first.ok)
        snapshot = {
            first.edits[0].path: first.edits[0].content,
            first.edits[1].path: first.edits[1].content,
        }
        second = self.generator.generate(
            "tools/stats.py をPythonコードで更新して、数字を抽出して平均を出す",
            snapshot,
        )
        self.assertTrue(second.ok)
        self.assertEqual(second.edits[0].operation, "modify")
        self.assertEqual(second.edits[1].operation, "modify")
        self.assertTrue(second.edits[0].before_sha256)

    def test_generated_focused_test_contains_computed_expected_value(self):
        result = self.generator.generate(
            "calc.py にPythonコードを作って、数字を抽出して合計する",
            {},
        )
        self.assertTrue(result.ok)
        test_source = result.edits[1].content
        self.assertIn("module.apply_program", test_source)
        self.assertIn("27.0", test_source)
        self.assertIn("['extract_numbers', 'sum']", test_source)

    def test_unknown_program_request_becomes_rejected_result(self):
        result = self.generator.generate(
            "bad.py にPythonコードを作って、未知の専用アルゴリズムを実装して",
            {},
        )
        self.assertFalse(result.ok)
        self.assertIn("program_generation_failed", result.errors)
        self.assertIn("CodeGenerationError", result.errors)
        self.assertEqual(result.edits, ())

    def test_include_tests_false_produces_single_bounded_edit(self):
        result = self.generator.generate(
            "one.py にPythonコードを作って文字数を数える",
            {},
            include_tests=False,
        )
        self.assertTrue(result.ok)
        self.assertEqual(len(result.edits), 1)
        self.assertNotIn("focused_test_generated", result.checks)

    def test_snapshot_digest_is_stable_under_mapping_order(self):
        a = self.generator.generate(
            "one.py にPythonコードを作って文字数を数える",
            {"b.txt": "2", "a.txt": "1"},
            include_tests=False,
        )
        b = self.generator.generate(
            "one.py にPythonコードを作って文字数を数える",
            {"a.txt": "1", "b.txt": "2"},
            include_tests=False,
        )
        self.assertEqual(a.repository_digest, b.repository_digest)
        self.assertEqual(a.plan_id, b.plan_id)

    def test_unsafe_paths_fail_closed_before_candidate_creation(self):
        with self.assertRaisesRegex(ValueError, "unsafe repository path"):
            self.generator.generate(
                "Pythonコードを作って文字数を数える",
                {"../secret.py": "x"},
            )

        with self.assertRaisesRegex(ValueError, "unsafe repository path"):
            self.generator.generate(
                "Pythonコードを作って文字数を数える",
                {},
                target_path="../escape.py",
            )

    def test_non_python_target_rejected(self):
        with self.assertRaisesRegex(RepositoryGenerationError, ".py target"):
            self.generator.generate(
                "Pythonコードを作って文字数を数える",
                {},
                target_path="generated/result.js",
            )

    def test_to_dict_omits_source_by_default(self):
        result = self.generator.generate(
            "calc.py にPythonコードを作って数字を抽出して合計する",
            {},
        )
        public = result.to_dict()
        self.assertNotIn("content", public["edits"][0])
        full = result.to_dict(include_content=True)
        self.assertIn("content", full["edits"][0])


if __name__ == "__main__":
    unittest.main()
