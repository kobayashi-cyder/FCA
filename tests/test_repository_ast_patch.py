from __future__ import annotations

import unittest

from fca.repository_ast_patch import ASTFunctionPatchGenerator, ASTPatchError


class ASTFunctionPatchGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.generator = ASTFunctionPatchGenerator()

    def test_replaces_only_function_body_and_executes_program_ir(self):
        source = (
            "PREFIX = 7\n\n"
            "def transform(text: str) -> float:\n"
            "    # old implementation\n"
            "    return -1.0\n\n"
            "SUFFIX = 9\n"
        )
        result = self.generator.patch(
            "Pythonコードで transform 関数を修正して、数字だけ抽出して合計する",
            source,
            target_symbol="transform",
            path="module.py",
        )

        self.assertTrue(result.ok, result.errors)
        self.assertIn("PREFIX = 7", result.source)
        self.assertIn("SUFFIX = 9", result.source)
        self.assertIn("def transform(text: str) -> float:", result.source)
        self.assertNotIn("return -1.0", result.source)
        self.assertIn("outside_region_byte_stable", result.checks)

        namespace = {}
        exec(compile(result.source, "module.py", "exec"), namespace)
        self.assertEqual(namespace["transform"]("a 2 b 5.5"), 7.5)

    def test_method_uses_first_non_self_parameter(self):
        source = (
            "class Worker:\n"
            "    def transform(self, text):\n"
            "        return 'old'\n"
        )
        result = self.generator.patch(
            "Pythonコードで transform を修正して文字数を数える",
            source,
            target_symbol="Worker.transform",
            path="worker.py",
        )
        self.assertTrue(result.ok, result.errors)

        namespace = {}
        exec(compile(result.source, "worker.py", "exec"), namespace)
        worker = namespace["Worker"]()
        self.assertEqual(worker.transform("abcd"), 4)

    def test_docstring_and_decorator_are_preserved(self):
        source = (
            "def marker(fn):\n"
            "    return fn\n\n"
            "@marker\n"
            "def transform(text):\n"
            "    \"\"\"keep me\"\"\"\n"
            "    return text\n"
        )
        result = self.generator.patch(
            "Pythonコードで transform を修正して大文字にする",
            source,
            target_symbol="transform",
            path="module.py",
        )
        self.assertTrue(result.ok, result.errors)
        self.assertIn('"""keep me"""', result.source)
        self.assertIn("@marker", result.source)
        self.assertIn("decorators_ast_equal", result.checks)

        namespace = {}
        exec(compile(result.source, "module.py", "exec"), namespace)
        self.assertEqual(namespace["transform"]("abc"), "ABC")

    def test_runtime_parameters_must_exist_in_signature(self):
        source = (
            "def transform(text):\n"
            "    return text\n"
        )
        result = self.generator.patch(
            "Pythonコードで transform を修正して文字列を置換する",
            source,
            target_symbol="transform",
            path="module.py",
        )
        self.assertFalse(result.ok)
        self.assertIn("missing_runtime_parameter:new", result.errors)
        self.assertIn("missing_runtime_parameter:old", result.errors)

    def test_runtime_parameters_are_bound_when_present(self):
        source = (
            "def transform(text, old, new):\n"
            "    return text\n"
        )
        result = self.generator.patch(
            "Pythonコードで transform を修正して文字列を置換する",
            source,
            target_symbol="transform",
            path="module.py",
        )
        self.assertTrue(result.ok, result.errors)

        namespace = {}
        exec(compile(result.source, "module.py", "exec"), namespace)
        self.assertEqual(namespace["transform"]("aba", "a", "x"), "xbx")

    def test_missing_symbol_and_bad_source_fail_closed(self):
        missing = self.generator.patch(
            "Pythonコードで unknown を修正して文字数を数える",
            "def transform(text):\n    return text\n",
            target_symbol="unknown",
            path="module.py",
        )
        self.assertFalse(missing.ok)
        self.assertEqual(missing.errors, ("target_symbol_not_found",))

        broken = self.generator.patch(
            "Pythonコードで transform を修正して文字数を数える",
            "def transform(:\n    pass\n",
            target_symbol="transform",
            path="module.py",
        )
        self.assertFalse(broken.ok)
        self.assertTrue(broken.errors[0].startswith("source_syntax:"))

    def test_to_edit_candidate_requires_verified_patch(self):
        good = self.generator.patch(
            "Pythonコードで transform を修正して文字数を数える",
            "def transform(text):\n    return 0\n",
            target_symbol="transform",
            path="module.py",
        )
        edit = good.to_edit_candidate()
        self.assertEqual(edit.operation, "modify")
        self.assertEqual(edit.path, "module.py")
        self.assertEqual(edit.after_sha256, good.after_sha256)

        bad = self.generator.patch(
            "Pythonコードで transform を修正して文字列を置換する",
            "def transform(text):\n    return text\n",
            target_symbol="transform",
            path="module.py",
        )
        with self.assertRaises(ASTPatchError):
            bad.to_edit_candidate()

    def test_unsafe_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "safe relative"):
            self.generator.patch(
                "Pythonコードで transform を修正して文字数を数える",
                "def transform(text):\n    return 0\n",
                target_symbol="transform",
                path="../module.py",
            )


if __name__ == "__main__":
    unittest.main()
