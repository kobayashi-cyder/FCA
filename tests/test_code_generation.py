import unittest

from fca import CodeGenerationError, FCACodeGenerator


class FCACodeGenerationTests(unittest.TestCase):
    def setUp(self):
        self.generator = FCACodeGenerator()

    def test_claims_requires_creation_and_code_intent(self):
        self.assertTrue(
            self.generator.claims("Pythonコードを作って、数字を抽出して合計して")
        )
        self.assertFalse(self.generator.claims("Pythonについて説明して"))
        self.assertFalse(self.generator.claims("何か作って"))

    def test_infers_compositional_program_ir(self):
        ir = self.generator.infer_ir(
            "Pythonコードを作って。テキストから数字だけ抽出して合計する。"
        )
        self.assertEqual(ir.language, "python")
        self.assertEqual(ir.input_mode, "text")
        self.assertEqual(ir.operations, ("extract_numbers", "sum"))

    def test_file_pipeline_is_not_a_fixed_task_template(self):
        ir = self.generator.infer_ir(
            "Pythonスクリプトを生成。テキストファイルを読み、空行を除去し、"
            "重複行を消して昇順に並べ、先頭3行を返す。"
        )
        self.assertEqual(ir.input_mode, "text_file")
        self.assertEqual(
            ir.operations,
            ("split_lines", "filter_nonempty", "unique", "sort", "head"),
        )
        self.assertEqual(dict(ir.parameters)["count"], "3")

    def test_generation_returns_verified_in_memory_candidate(self):
        result = self.generator.generate(
            "Pythonコードを作成して、文字列を大文字に変換する"
        )
        self.assertTrue(result.ok)
        self.assertIn("compile", result.checks)
        self.assertIn("ast_policy", result.checks)
        self.assertIn("ir_contract", result.checks)
        self.assertIn("def apply_program(", result.source)
        self.assertEqual(len(result.sha256), 64)

    def test_unknown_semantics_fail_closed(self):
        with self.assertRaisesRegex(CodeGenerationError, "ProgramIR vocabulary"):
            self.generator.generate(
                "Pythonコードを作って、未知の専用アルゴリズムを実装して"
            )

    def test_non_python_request_fails_closed(self):
        with self.assertRaisesRegex(CodeGenerationError, "supports Python"):
            self.generator.infer_ir("JavaScriptコードを作って数を合計して")

    def test_filename_cannot_escape_artifact_boundary(self):
        with self.assertRaisesRegex(ValueError, "simple .py filename"):
            self.generator.generate(
                "Pythonコードを作って文字数を数える",
                filename="../escape.py",
            )

    def test_policy_rejects_dangerous_import_and_exec(self):
        checks, errors = self.generator.validate_source(
            "import subprocess\nexec('print(1)')\nPROGRAM_IR = []\ndef apply_program(): pass\n"
        )
        self.assertIn("forbidden import: subprocess", errors)
        self.assertIn("forbidden call: exec", errors)
        self.assertNotIn("ast_policy", checks)


if __name__ == "__main__":
    unittest.main()
