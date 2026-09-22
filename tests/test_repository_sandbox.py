from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fca.repository_ast_patch import ASTFunctionPatchGenerator
from fca.repository_generation import RepositoryEditCandidate
from fca.repository_sandbox import FCASandboxRepairRunner, SandboxCommand


class FCASandboxRepairRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self._git("init")
        self._git("config", "user.email", "fca-test@example.invalid")
        self._git("config", "user.name", "FCA Test")
        self._write(
            "calc.py",
            "def transform(text):\n"
            "    return 'old'\n",
        )
        self._write(
            "test_calc.py",
            "import unittest\n"
            "from calc import transform\n\n"
            "class CalcTests(unittest.TestCase):\n"
            "    def test_transform(self):\n"
            "        self.assertEqual(transform('abc'), 'ABC')\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
        )
        self._git("add", ".")
        self._git("commit", "-m", "base")
        self.base_head = self._git("rev-parse", "HEAD").stdout.strip()
        self.base_status = self._git(
            "status", "--porcelain", "--untracked-files=all"
        ).stdout
        self.ast = ASTFunctionPatchGenerator()
        self.command = SandboxCommand(
            name="focused_unittest",
            phase="focused",
            argv=(
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                ".",
                "-p",
                "test_*.py",
                "-q",
            ),
            timeout_sec=30,
        )

    def tearDown(self):
        self.temp.cleanup()

    def _git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )

    def _write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def _patch(self, goal):
        source = (self.root / "calc.py").read_text(encoding="utf-8")
        result = self.ast.patch(
            goal,
            source,
            target_symbol="transform",
            path="calc.py",
        )
        self.assertTrue(result.ok, result.errors)
        return result.to_edit_candidate()

    def test_verified_candidate_runs_in_detached_worktree(self):
        edit = self._patch(
            "Pythonコードで transform を修正して大文字にする"
        )
        runner = FCASandboxRepairRunner(self.root)
        result = runner.run((edit,), (self.command,))

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.repairs_used, 0)
        self.assertEqual(len(result.attempts), 1)
        self.assertEqual(result.attempts[0].state, "verified_candidate")
        self.assertTrue(result.attempts[0].commands[0].passed)
        self.assertTrue(result.attempts[0].commands[1].passed)
        self.assertEqual(self._git("rev-parse", "HEAD").stdout.strip(), self.base_head)
        self.assertEqual(
            self._git("status", "--porcelain", "--untracked-files=all").stdout,
            self.base_status,
        )
        self.assertEqual(
            (self.root / "calc.py").read_text(encoding="utf-8"),
            "def transform(text):\n    return 'old'\n",
        )

    def test_failed_candidate_is_repaired_and_retested_automatically(self):
        bad = self._patch(
            "Pythonコードで transform を修正して小文字にする"
        )
        good = self._patch(
            "Pythonコードで transform を修正して大文字にする"
        )
        repair_calls = []

        def repairer(current, attempt):
            repair_calls.append((current, attempt))
            self.assertEqual(attempt.state, "rejected")
            self.assertTrue(
                any("focused_command_failed" in item for item in attempt.errors)
            )
            return (good,)

        runner = FCASandboxRepairRunner(self.root, max_repairs=2)
        result = runner.run(
            (bad,),
            (self.command,),
            repairer=repairer,
        )

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.repairs_used, 1)
        self.assertEqual(len(result.attempts), 2)
        self.assertEqual(result.attempts[0].state, "rejected")
        self.assertEqual(result.attempts[1].state, "verified_candidate")
        self.assertEqual(len(repair_calls), 1)
        self.assertEqual(result.final_edits[0].after_sha256, good.after_sha256)
        self.assertEqual(self._git("rev-parse", "HEAD").stdout.strip(), self.base_head)

    def test_repair_scope_cannot_expand(self):
        bad = self._patch(
            "Pythonコードで transform を修正して小文字にする"
        )
        other_content = "VALUE = 1\n"
        other = RepositoryEditCandidate(
            path="other.py",
            operation="create",
            before_sha256="",
            after_sha256=sha256(other_content.encode("utf-8")).hexdigest(),
            content=other_content,
            checks=("test",),
        )

        runner = FCASandboxRepairRunner(self.root, max_repairs=2)
        result = runner.run(
            (bad,),
            (self.command,),
            repairer=lambda current, attempt: (other,),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.errors, ("repair_scope_changed",))
        self.assertFalse((self.root / "other.py").exists())

    def test_repair_attempts_are_bounded(self):
        bad = self._patch(
            "Pythonコードで transform を修正して小文字にする"
        )
        calls = []

        def repairer(current, attempt):
            calls.append(attempt.round_index)
            return current

        runner = FCASandboxRepairRunner(self.root, max_repairs=1)
        result = runner.run(
            (bad,),
            (self.command,),
            repairer=repairer,
        )

        self.assertFalse(result.ok)
        self.assertEqual(len(result.attempts), 2)
        self.assertEqual(result.repairs_used, 1)
        self.assertEqual(calls, [0])

    def test_stale_before_hash_is_rejected_without_source_mutation(self):
        good = self._patch(
            "Pythonコードで transform を修正して大文字にする"
        )
        stale = RepositoryEditCandidate(
            path=good.path,
            operation=good.operation,
            before_sha256="0" * 64,
            after_sha256=good.after_sha256,
            content=good.content,
            checks=good.checks,
        )

        runner = FCASandboxRepairRunner(self.root)
        result = runner.run((stale,), (self.command,))

        self.assertFalse(result.ok)
        self.assertTrue(
            any("sandbox_attempt_failed" in item for item in result.errors)
        )
        self.assertEqual(self._git("rev-parse", "HEAD").stdout.strip(), self.base_head)
        self.assertEqual(
            (self.root / "calc.py").read_text(encoding="utf-8"),
            "def transform(text):\n    return 'old'\n",
        )

    def test_disallowed_executable_is_rejected_before_execution(self):
        good = self._patch(
            "Pythonコードで transform を修正して大文字にする"
        )
        runner = FCASandboxRepairRunner(self.root)
        command = SandboxCommand(
            name="bad",
            phase="focused",
            argv=("sh", "-c", "echo nope"),
        )
        with self.assertRaisesRegex(ValueError, "not allowed"):
            runner.run((good,), (command,))


if __name__ == "__main__":
    unittest.main()
