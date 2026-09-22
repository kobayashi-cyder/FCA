from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
import json
import os
import subprocess
import sys
import tempfile
import time
from typing import Callable, Iterable

from .repository_generation import RepositoryEditCandidate


@dataclass(frozen=True)
class SandboxCommand:
    name: str
    phase: str
    argv: tuple[str, ...]
    timeout_sec: int = 60
    required: bool = True


@dataclass(frozen=True)
class SandboxCommandResult:
    name: str
    phase: str
    argv: tuple[str, ...]
    returncode: int | None
    duration_ms: int
    passed: bool
    timed_out: bool
    output_limited: bool
    output: str
    error: str = ""


@dataclass(frozen=True)
class SandboxAttempt:
    round_index: int
    state: str
    edits: tuple[RepositoryEditCandidate, ...]
    commands: tuple[SandboxCommandResult, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class SandboxRepairResult:
    version: str
    state: str
    plan_id: str
    base_commit: str
    repairs_used: int
    attempts: tuple[SandboxAttempt, ...]
    final_edits: tuple[RepositoryEditCandidate, ...]
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.state == "verified_candidate" and not self.errors

    def to_dict(self, *, include_content: bool = False) -> dict:
        return {
            "version": self.version,
            "state": self.state,
            "plan_id": self.plan_id,
            "base_commit": self.base_commit,
            "repairs_used": self.repairs_used,
            "attempts": [
                {
                    "round_index": attempt.round_index,
                    "state": attempt.state,
                    "edits": [
                        edit.to_dict(include_content=include_content)
                        for edit in attempt.edits
                    ],
                    "commands": [asdict(item) for item in attempt.commands],
                    "errors": list(attempt.errors),
                }
                for attempt in self.attempts
            ],
            "final_edits": [
                edit.to_dict(include_content=include_content)
                for edit in self.final_edits
            ],
            "errors": list(self.errors),
        }


RepairProvider = Callable[
    [tuple[RepositoryEditCandidate, ...], SandboxAttempt],
    Iterable[RepositoryEditCandidate] | None,
]


class FCASandboxRepairRunner:
    """Verify repository edits in detached Git worktrees with bounded repair.

    Every attempt starts from the same source HEAD in a fresh detached worktree.
    Candidate edits are SHA-256 preconditioned, Python is statically compiled,
    and explicit allow-listed commands are run without a shell. A repair
    provider may replace candidate contents only for the same pre-approved path
    set and operation set. No branch, commit, push, PR, merge, or source-tree
    mutation is performed.
    """

    VERSION = "fca.sandbox_repair.v1"

    def __init__(
        self,
        root: str | Path,
        *,
        max_repairs: int = 2,
        max_edits: int = 8,
        max_edit_bytes: int = 1_000_000,
        max_total_edit_bytes: int = 2_000_000,
        max_commands: int = 8,
        max_timeout_sec: int = 120,
        max_output_bytes: int = 200_000,
        allowed_executables: Iterable[str] | None = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError("repository root is not a directory")
        if not 0 <= int(max_repairs) <= 4:
            raise ValueError("max_repairs must be in [0, 4]")
        if not 1 <= int(max_edits) <= 32:
            raise ValueError("max_edits must be in [1, 32]")
        if int(max_edit_bytes) <= 0 or int(max_total_edit_bytes) <= 0:
            raise ValueError("edit byte limits must be positive")
        if not 1 <= int(max_commands) <= 32:
            raise ValueError("max_commands must be in [1, 32]")
        if not 1 <= int(max_timeout_sec) <= 600:
            raise ValueError("max_timeout_sec must be in [1, 600]")
        if not 1_000 <= int(max_output_bytes) <= 5_000_000:
            raise ValueError("max_output_bytes must be in [1000, 5000000]")

        defaults = {
            Path(sys.executable).name.casefold(),
            "python",
            "python3",
            "python.exe",
            "py",
            "py.exe",
            "pytest",
            "pytest.exe",
        }
        values = defaults if allowed_executables is None else set(allowed_executables)
        self.allowed_executables = frozenset(
            Path(str(item)).name.casefold()
            for item in values
            if str(item).strip()
        )
        if not self.allowed_executables:
            raise ValueError("allowed_executables must not be empty")

        self.max_repairs = int(max_repairs)
        self.max_edits = int(max_edits)
        self.max_edit_bytes = int(max_edit_bytes)
        self.max_total_edit_bytes = int(max_total_edit_bytes)
        self.max_commands = int(max_commands)
        self.max_timeout_sec = int(max_timeout_sec)
        self.max_output_bytes = int(max_output_bytes)
        self._assert_git_repository()

    def run(
        self,
        initial_edits: Iterable[RepositoryEditCandidate],
        commands: Iterable[SandboxCommand],
        *,
        repairer: RepairProvider | None = None,
    ) -> SandboxRepairResult:
        edits = tuple(initial_edits)
        command_list = tuple(commands)
        self._validate_edits(edits)
        self._validate_commands(command_list)

        base_commit = self._git(
            self.root, "rev-parse", "--verify", "HEAD"
        ).stdout.strip()
        if not base_commit:
            raise RuntimeError("could not resolve repository HEAD")
        source_status = self._git(
            self.root,
            "status",
            "--porcelain",
            "--untracked-files=all",
            check=False,
        ).stdout
        scope = tuple(
            (edit.path, edit.operation, edit.before_sha256)
            for edit in edits
        )
        plan_id = self._plan_id(base_commit, edits, command_list)

        attempts: list[SandboxAttempt] = []
        current = edits
        for round_index in range(self.max_repairs + 1):
            attempt = self._attempt(
                round_index,
                base_commit,
                source_status,
                current,
                command_list,
            )
            attempts.append(attempt)

            if attempt.state == "verified_candidate":
                return SandboxRepairResult(
                    version=self.VERSION,
                    state="verified_candidate",
                    plan_id=plan_id,
                    base_commit=base_commit,
                    repairs_used=round_index,
                    attempts=tuple(attempts),
                    final_edits=current,
                    errors=(),
                )

            if round_index >= self.max_repairs or repairer is None:
                break

            try:
                proposal = repairer(current, attempt)
            except Exception as exc:
                return SandboxRepairResult(
                    version=self.VERSION,
                    state="rejected",
                    plan_id=plan_id,
                    base_commit=base_commit,
                    repairs_used=round_index,
                    attempts=tuple(attempts),
                    final_edits=current,
                    errors=(f"repair_provider_failed:{type(exc).__name__}",),
                )
            if proposal is None:
                break
            next_edits = tuple(proposal)
            if not next_edits:
                break
            self._validate_edits(next_edits)
            next_scope = tuple(
                (edit.path, edit.operation, edit.before_sha256)
                for edit in next_edits
            )
            if next_scope != scope:
                return SandboxRepairResult(
                    version=self.VERSION,
                    state="rejected",
                    plan_id=plan_id,
                    base_commit=base_commit,
                    repairs_used=round_index,
                    attempts=tuple(attempts),
                    final_edits=current,
                    errors=("repair_scope_changed",),
                )
            current = next_edits

        final_errors = attempts[-1].errors if attempts else ("no_attempts",)
        return SandboxRepairResult(
            version=self.VERSION,
            state="rejected",
            plan_id=plan_id,
            base_commit=base_commit,
            repairs_used=max(0, len(attempts) - 1),
            attempts=tuple(attempts),
            final_edits=current,
            errors=tuple(final_errors),
        )

    def _attempt(
        self,
        round_index: int,
        base_commit: str,
        source_status_before: str,
        edits: tuple[RepositoryEditCandidate, ...],
        commands: tuple[SandboxCommand, ...],
    ) -> SandboxAttempt:
        temp_parent = Path(tempfile.mkdtemp(prefix="fca-sandbox-")).resolve()
        worktree = temp_parent / "worktree"
        command_results: list[SandboxCommandResult] = []
        errors: list[str] = []
        try:
            self._git(
                self.root,
                "worktree",
                "add",
                "--detach",
                str(worktree),
                base_commit,
            )
            self._apply_edits(worktree, edits)

            static = self._static_compile(worktree, edits)
            command_results.append(static)
            if not static.passed:
                errors.append("static_compile_failed")
            else:
                for command in commands:
                    result = self._run_command(worktree, command)
                    command_results.append(result)
                    if command.required and not result.passed:
                        errors.append(f"{command.phase}_command_failed:{command.name}")
                        break

            if not errors:
                contamination = self._unexpected_changes(worktree, edits)
                if contamination:
                    errors.extend(contamination)

            source_head_after = self._git(
                self.root, "rev-parse", "--verify", "HEAD"
            ).stdout.strip()
            source_status_after = self._git(
                self.root,
                "status",
                "--porcelain",
                "--untracked-files=all",
                check=False,
            ).stdout
            if source_head_after != base_commit:
                errors.append("source_head_changed")
            if source_status_after != source_status_before:
                errors.append("source_working_tree_changed")

            return SandboxAttempt(
                round_index=round_index,
                state="verified_candidate" if not errors else "rejected",
                edits=edits,
                commands=tuple(command_results),
                errors=tuple(errors),
            )
        except Exception as exc:
            return SandboxAttempt(
                round_index=round_index,
                state="rejected",
                edits=edits,
                commands=tuple(command_results),
                errors=(f"sandbox_attempt_failed:{type(exc).__name__}",),
            )
        finally:
            if worktree.exists():
                self._git(
                    self.root,
                    "worktree",
                    "remove",
                    "--force",
                    str(worktree),
                    check=False,
                )
            try:
                import shutil

                shutil.rmtree(temp_parent, ignore_errors=True)
            except Exception:
                pass

    def _validate_edits(
        self,
        edits: tuple[RepositoryEditCandidate, ...],
    ) -> None:
        if not edits:
            raise ValueError("at least one edit is required")
        if len(edits) > self.max_edits:
            raise ValueError("edit set exceeds max_edits")
        seen: set[str] = set()
        total = 0
        for edit in edits:
            if not isinstance(edit, RepositoryEditCandidate):
                raise TypeError("edits must be RepositoryEditCandidate values")
            path = self._safe_relative_path(edit.path)
            if path in seen:
                raise ValueError("duplicate edit path")
            seen.add(path)
            if edit.operation not in {"create", "modify"}:
                raise ValueError("sandbox repair v1 supports create/modify only")
            if edit.operation == "create" and edit.before_sha256:
                raise ValueError("create edit must have empty before_sha256")
            if edit.operation == "modify" and len(edit.before_sha256) != 64:
                raise ValueError("modify edit requires SHA-256 precondition")
            raw = edit.content.encode("utf-8")
            if len(raw) > self.max_edit_bytes:
                raise ValueError("edit exceeds per-file byte limit")
            total += len(raw)
            if sha256(raw).hexdigest() != edit.after_sha256:
                raise ValueError("edit after_sha256 does not match content")
        if total > self.max_total_edit_bytes:
            raise ValueError("edit set exceeds total byte limit")

    def _validate_commands(
        self,
        commands: tuple[SandboxCommand, ...],
    ) -> None:
        if len(commands) > self.max_commands:
            raise ValueError("command set exceeds max_commands")
        names: set[str] = set()
        for command in commands:
            if not isinstance(command, SandboxCommand):
                raise TypeError("commands must be SandboxCommand values")
            if not command.name or command.name in names:
                raise ValueError("command names must be unique and non-empty")
            names.add(command.name)
            if command.phase not in {"focused", "regression"}:
                raise ValueError("command phase must be focused or regression")
            if not command.argv or any(
                not isinstance(item, str) or not item or "\x00" in item
                for item in command.argv
            ):
                raise ValueError("command argv must contain safe non-empty strings")
            executable = Path(command.argv[0]).name.casefold()
            if executable not in self.allowed_executables:
                raise ValueError("command executable is not allowed")
            if not 1 <= int(command.timeout_sec) <= self.max_timeout_sec:
                raise ValueError("command timeout exceeds policy")

    def _apply_edits(
        self,
        worktree: Path,
        edits: tuple[RepositoryEditCandidate, ...],
    ) -> None:
        for edit in edits:
            rel = self._safe_relative_path(edit.path)
            target = worktree / rel
            self._reject_symlink_chain(worktree, rel)
            if edit.operation == "create":
                if target.exists() or target.is_symlink():
                    raise ValueError("create target already exists")
                target.parent.mkdir(parents=True, exist_ok=True)
            else:
                if not target.is_file() or target.is_symlink():
                    raise ValueError("modify target unavailable")
                actual = sha256(target.read_bytes()).hexdigest()
                if actual != edit.before_sha256:
                    raise ValueError("STALE_CANDIDATE: before hash mismatch")
            target.write_text(edit.content, encoding="utf-8", newline="")
            actual_after = sha256(target.read_bytes()).hexdigest()
            if actual_after != edit.after_sha256:
                raise ValueError("written candidate hash mismatch")

    def _static_compile(
        self,
        worktree: Path,
        edits: tuple[RepositoryEditCandidate, ...],
    ) -> SandboxCommandResult:
        started = time.monotonic()
        checked: list[str] = []
        failures: list[str] = []
        for edit in edits:
            if not edit.path.endswith(".py"):
                continue
            checked.append(edit.path)
            try:
                source = (worktree / edit.path).read_text(encoding="utf-8")
                compile(source, edit.path, "exec")
            except Exception as exc:
                failures.append(f"{edit.path}:{type(exc).__name__}")
        return SandboxCommandResult(
            name="python_static_compile",
            phase="static",
            argv=("<internal compile()>", *checked),
            returncode=0 if not failures else 1,
            duration_ms=int((time.monotonic() - started) * 1000),
            passed=not failures,
            timed_out=False,
            output_limited=False,
            output="\n".join(failures),
            error="" if not failures else "syntax_or_decode_error",
        )

    def _run_command(
        self,
        worktree: Path,
        command: SandboxCommand,
    ) -> SandboxCommandResult:
        started = time.monotonic()
        timed_out = False
        output_limited = False
        returncode: int | None = None
        error = ""
        output = ""
        env = self._minimal_env()
        try:
            with tempfile.TemporaryFile() as sink:
                proc = subprocess.Popen(
                    list(command.argv),
                    cwd=worktree,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=sink,
                    stderr=subprocess.STDOUT,
                    shell=False,
                )
                deadline = started + command.timeout_sec
                while proc.poll() is None:
                    if time.monotonic() >= deadline:
                        timed_out = True
                        proc.kill()
                        break
                    if os.fstat(sink.fileno()).st_size > self.max_output_bytes:
                        output_limited = True
                        proc.kill()
                        break
                    time.sleep(0.02)
                proc.wait(timeout=5)
                returncode = proc.returncode
                sink.seek(0)
                raw = sink.read(self.max_output_bytes + 1)
                if len(raw) > self.max_output_bytes:
                    output_limited = True
                    raw = raw[: self.max_output_bytes]
                output = raw.decode("utf-8", errors="replace")
        except Exception as exc:
            error = type(exc).__name__

        passed = (
            not error
            and not timed_out
            and not output_limited
            and returncode == 0
        )
        return SandboxCommandResult(
            name=command.name,
            phase=command.phase,
            argv=command.argv,
            returncode=returncode,
            duration_ms=int((time.monotonic() - started) * 1000),
            passed=passed,
            timed_out=timed_out,
            output_limited=output_limited,
            output=output,
            error=error,
        )

    def _unexpected_changes(
        self,
        worktree: Path,
        edits: tuple[RepositoryEditCandidate, ...],
    ) -> tuple[str, ...]:
        expected = {edit.path for edit in edits}
        proc = self._git(
            worktree,
            "status",
            "--porcelain",
            "--untracked-files=all",
            check=False,
        )
        unexpected: list[str] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            raw_path = line[3:].strip()
            if " -> " in raw_path:
                raw_path = raw_path.split(" -> ", 1)[1]
            path = raw_path.replace("\\", "/")
            if path not in expected:
                unexpected.append(path)
        if not unexpected:
            return ()
        return ("unexpected_sandbox_changes:" + ",".join(sorted(set(unexpected))),)

    @staticmethod
    def _minimal_env() -> dict[str, str]:
        keep = ("PATH", "SYSTEMROOT", "WINDIR", "TMPDIR", "TEMP", "TMP")
        env = {key: os.environ[key] for key in keep if key in os.environ}
        env.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONNOUSERSITE": "1",
                "PYTHONUNBUFFERED": "1",
            }
        )
        return env

    @staticmethod
    def _safe_relative_path(raw: str) -> str:
        text = str(raw or "").strip().replace("\\", "/")
        path = PurePosixPath(text)
        if (
            not text
            or path.is_absolute()
            or any(part in {"", ".", "..", ".git"} for part in path.parts)
        ):
            raise ValueError("unsafe repository path")
        return path.as_posix()

    @staticmethod
    def _reject_symlink_chain(root: Path, rel: str) -> None:
        current = root
        for part in PurePosixPath(rel).parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("symlink path component rejected")
            if not current.exists():
                break
        resolved_parent = (root / rel).parent.resolve()
        try:
            resolved_parent.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError("path escapes sandbox") from exc

    @staticmethod
    def _plan_id(
        base_commit: str,
        edits: tuple[RepositoryEditCandidate, ...],
        commands: tuple[SandboxCommand, ...],
    ) -> str:
        payload = {
            "version": FCASandboxRepairRunner.VERSION,
            "base_commit": base_commit,
            "scope": [
                {
                    "path": edit.path,
                    "operation": edit.operation,
                    "before_sha256": edit.before_sha256,
                }
                for edit in edits
            ],
            "commands": [
                {
                    "name": command.name,
                    "phase": command.phase,
                    "argv": list(command.argv),
                    "timeout_sec": command.timeout_sec,
                    "required": command.required,
                }
                for command in commands
            ],
        }
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _assert_git_repository(self) -> None:
        proc = self._git(
            self.root,
            "rev-parse",
            "--is-inside-work-tree",
            check=False,
        )
        if proc.returncode != 0 or proc.stdout.strip() != "true":
            raise ValueError("not a Git working tree")

    @staticmethod
    def _git(
        cwd: Path,
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
            check=False,
            shell=False,
        )
        if check and proc.returncode != 0:
            raise RuntimeError(
                f"git command failed:{args[0] if args else 'unknown'}:{proc.returncode}"
            )
        return proc
