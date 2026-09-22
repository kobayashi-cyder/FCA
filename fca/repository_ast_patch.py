from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import ast
import json
import re
from typing import Any

from .code_generation import CodeGenerationError, FCACodeGenerator, ProgramIR
from .repository_generation import RepositoryEditCandidate


class ASTPatchError(RuntimeError):
    """Raised when a bounded AST patch cannot be formed safely."""


@dataclass(frozen=True)
class ASTFunctionPatchResult:
    ok: bool
    path: str
    target_symbol: str
    source: str
    before_sha256: str
    after_sha256: str
    changed_lines: tuple[int, int] | None
    ir: ProgramIR | None
    checks: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self, *, include_source: bool = False) -> dict[str, Any]:
        data = asdict(self)
        data["ir"] = self.ir.to_dict() if self.ir is not None else None
        if not include_source:
            data.pop("source", None)
        return data

    def to_edit_candidate(self) -> RepositoryEditCandidate:
        if not self.ok:
            raise ASTPatchError("cannot convert a rejected AST patch")
        return RepositoryEditCandidate(
            path=self.path,
            operation="modify",
            before_sha256=self.before_sha256,
            after_sha256=self.after_sha256,
            content=self.source,
            checks=self.checks,
        )


class ASTFunctionPatchGenerator:
    """Replace only one existing Python function body using FCA ProgramIR.

    The original signature, decorators, surrounding module text, classes,
    comments outside the function body, and all unrelated symbols remain byte
    identical. The generated body is deterministic and uses only bounded local
    operations. No filesystem, subprocess, git, or import execution occurs here.
    """

    VERSION = "fca.ast_function_patch.v1"
    _SAFE_PATH = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.py")
    _RESERVED_PREFIX = "__fca_patch_"

    def __init__(self, *, code_generator: FCACodeGenerator | None = None) -> None:
        self.code_generator = code_generator or FCACodeGenerator()

    def patch(
        self,
        goal: str,
        source: str,
        *,
        target_symbol: str,
        path: str = "module.py",
    ) -> ASTFunctionPatchResult:
        goal = str(goal or "").strip()
        target_symbol = str(target_symbol or "").strip()
        path = str(path or "").replace("\\", "/").strip()
        if not goal:
            raise ValueError("goal is required")
        if not target_symbol:
            raise ValueError("target_symbol is required")
        if not self._SAFE_PATH.fullmatch(path) or ".." in path.split("/"):
            raise ValueError("path must be a safe relative .py path")
        if not isinstance(source, str):
            raise TypeError("source must be text")

        before_sha = sha256(source.encode("utf-8")).hexdigest()
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            return self._reject(
                path,
                target_symbol,
                source,
                before_sha,
                None,
                (f"source_syntax:{exc.lineno}",),
            )

        try:
            ir = self.code_generator.infer_ir(goal)
        except CodeGenerationError as exc:
            return self._reject(
                path,
                target_symbol,
                source,
                before_sha,
                None,
                ("program_ir_failed", type(exc).__name__),
            )

        node = self._find_function(tree, target_symbol)
        if node is None:
            return self._reject(
                path,
                target_symbol,
                source,
                before_sha,
                ir,
                ("target_symbol_not_found",),
            )
        if not node.body:
            return self._reject(
                path,
                target_symbol,
                source,
                before_sha,
                ir,
                ("target_function_has_no_body",),
            )

        params = self._parameter_names(node)
        if not params:
            return self._reject(
                path,
                target_symbol,
                source,
                before_sha,
                ir,
                ("target_function_requires_input_parameter",),
            )
        runtime_missing = self._missing_runtime_parameters(ir, params)
        if runtime_missing:
            return self._reject(
                path,
                target_symbol,
                source,
                before_sha,
                ir,
                tuple(f"missing_runtime_parameter:{name}" for name in runtime_missing),
            )

        keep_docstring = (
            isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )
        replace_index = 1 if keep_docstring else 0
        if replace_index >= len(node.body):
            return self._reject(
                path,
                target_symbol,
                source,
                before_sha,
                ir,
                ("docstring_only_function_not_patchable",),
            )

        first = node.body[replace_index]
        last = node.body[-1]
        if first.lineno is None or last.end_lineno is None:
            return self._reject(
                path,
                target_symbol,
                source,
                before_sha,
                ir,
                ("source_location_unavailable",),
            )

        lines = source.splitlines(keepends=True)
        if not (1 <= first.lineno <= len(lines)):
            return self._reject(
                path,
                target_symbol,
                source,
                before_sha,
                ir,
                ("source_location_out_of_bounds",),
            )

        indent_match = re.match(r"[ \t]*", lines[first.lineno - 1])
        indent = indent_match.group(0) if indent_match else (" " * (node.col_offset + 4))
        newline = "\r\n" if "\r\n" in source else "\n"
        suffix = sha256(
            f"{path}:{target_symbol}".encode("utf-8")
        ).hexdigest()[:8]

        try:
            body_lines = self._emit_body(
                ir,
                value_name=params[0],
                parameter_names=frozenset(params),
                suffix=suffix,
            )
        except ASTPatchError as exc:
            return self._reject(
                path,
                target_symbol,
                source,
                before_sha,
                ir,
                (str(exc),),
            )

        replacement = "".join(f"{indent}{line}{newline}" for line in body_lines)
        prefix = "".join(lines[: first.lineno - 1])
        suffix_text = "".join(lines[last.end_lineno :])
        patched = prefix + replacement + suffix_text

        checks: list[str] = [
            "source_ast_parse",
            "target_symbol_resolved",
            "signature_preserved",
            "bounded_function_body_replacement",
        ]
        errors: list[str] = []

        try:
            patched_tree = ast.parse(patched, filename=path)
            compile(patched_tree, path, "exec")
            checks.append("patched_compile")
        except SyntaxError as exc:
            errors.append(f"patched_syntax:{exc.lineno}")

        patched_node = self._find_function(patched_tree, target_symbol) if not errors else None
        if patched_node is None and not errors:
            errors.append("patched_symbol_missing")
        elif patched_node is not None:
            if ast.dump(node.args, include_attributes=False) != ast.dump(
                patched_node.args, include_attributes=False
            ):
                errors.append("signature_changed")
            else:
                checks.append("signature_ast_equal")
            if ast.dump(node.decorator_list, include_attributes=False) != ast.dump(
                patched_node.decorator_list, include_attributes=False
            ):
                errors.append("decorators_changed")
            else:
                checks.append("decorators_ast_equal")

        fragment_errors = self._validate_generated_body(body_lines)
        if fragment_errors:
            errors.extend(fragment_errors)
        else:
            checks.append("generated_body_policy")

        if "".join(lines[: first.lineno - 1]) != prefix or "".join(
            lines[last.end_lineno :]
        ) != suffix_text:
            errors.append("outside_region_changed")
        else:
            checks.append("outside_region_byte_stable")

        return ASTFunctionPatchResult(
            ok=not errors,
            path=path,
            target_symbol=target_symbol,
            source=patched,
            before_sha256=before_sha,
            after_sha256=sha256(patched.encode("utf-8")).hexdigest(),
            changed_lines=(first.lineno, last.end_lineno),
            ir=ir,
            checks=tuple(checks),
            errors=tuple(errors),
        )

    @classmethod
    def _find_function(
        cls,
        tree: ast.AST,
        target_symbol: str,
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        parts = tuple(part for part in target_symbol.split(".") if part)
        if not parts:
            return None
        body = getattr(tree, "body", ())
        current: ast.AST | None = None
        for index, part in enumerate(parts):
            matches = [
                item
                for item in body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and item.name == part
            ]
            if len(matches) != 1:
                return None
            current = matches[0]
            if index < len(parts) - 1:
                if not isinstance(current, ast.ClassDef):
                    return None
                body = current.body
        return current if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)) else None

    @staticmethod
    def _parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
        args = node.args
        ordered = [*args.posonlyargs, *args.args]
        if args.vararg is not None:
            ordered.append(args.vararg)
        ordered.extend(args.kwonlyargs)
        if args.kwarg is not None:
            ordered.append(args.kwarg)
        names = [arg.arg for arg in ordered]
        if names and names[0] in {"self", "cls"} and len(names) > 1:
            names = names[1:]
        return tuple(names)

    @staticmethod
    def _missing_runtime_parameters(
        ir: ProgramIR,
        parameter_names: tuple[str, ...],
    ) -> tuple[str, ...]:
        available = set(parameter_names)
        missing = [
            name
            for name, value in ir.parameters
            if value == "__RUNTIME__" and name not in available
        ]
        return tuple(sorted(missing))

    def _emit_body(
        self,
        ir: ProgramIR,
        *,
        value_name: str,
        parameter_names: frozenset[str],
        suffix: str,
    ) -> tuple[str, ...]:
        data = f"{self._RESERVED_PREFIX}data_{suffix}"
        seen = f"{self._RESERVED_PREFIX}seen_{suffix}"
        out = f"{self._RESERVED_PREFIX}out_{suffix}"
        item = f"{self._RESERVED_PREFIX}item_{suffix}"
        key = f"{self._RESERVED_PREFIX}key_{suffix}"
        numbers = f"{self._RESERVED_PREFIX}numbers_{suffix}"
        params = dict(ir.parameters)
        lines: list[str] = []

        if ir.input_mode == "json_file":
            lines.extend(
                [
                    "import json as __fca_json",
                    "from pathlib import Path as __fca_Path",
                    f"{data} = __fca_json.loads(__fca_Path({value_name}).read_text(encoding='utf-8'))",
                ]
            )
        elif ir.input_mode == "text_file":
            lines.extend(
                [
                    "from pathlib import Path as __fca_Path",
                    f"{data} = __fca_Path({value_name}).read_text(encoding='utf-8')",
                ]
            )
        else:
            lines.append(f"{data} = {value_name}")

        for op in ir.operations:
            if op == "json_numeric_keys":
                lines.extend(
                    [
                        f"if not isinstance({data}, dict):",
                        "    raise TypeError('JSON object required')",
                        f"{data} = sorted(str(k) for k, v in {data}.items() if isinstance(v, (int, float)) and not isinstance(v, bool))",
                    ]
                )
            elif op == "json_keys":
                lines.extend(
                    [
                        f"if not isinstance({data}, dict):",
                        "    raise TypeError('JSON object required')",
                        f"{data} = sorted(map(str, {data}.keys()))",
                    ]
                )
            elif op == "extract_numbers":
                lines.extend(
                    [
                        "import re as __fca_re",
                        f"if isinstance({data}, (list, tuple)):",
                        f"    {data} = [float(x) for x in {data}]",
                        "else:",
                        f"    {data} = [float(x) for x in __fca_re.findall(r'[-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)', str({data}))]",
                    ]
                )
            elif op == "split_lines":
                lines.append(f"{data} = str({data}).splitlines()")
            elif op == "filter_nonempty":
                lines.append(
                    f"{data} = [str(x).strip() for x in {data} if str(x).strip()]"
                )
            elif op == "unique":
                lines.extend(
                    [
                        "import json as __fca_json",
                        f"{seen} = set()",
                        f"{out} = []",
                        f"for {item} in list({data} if isinstance({data}, list) else str({data})):",
                        f"    {key} = __fca_json.dumps({item}, ensure_ascii=False, sort_keys=True) if isinstance({item}, (dict, list)) else repr({item})",
                        f"    if {key} not in {seen}:",
                        f"        {seen}.add({key})",
                        f"        {out}.append({item})",
                        f"{data} = {out}",
                    ]
                )
            elif op == "sort":
                lines.append(f"{data} = sorted({data})")
            elif op == "sort_desc":
                lines.append(f"{data} = sorted({data}, reverse=True)")
            elif op in {"head", "tail"}:
                count = self._runtime_or_literal("count", params, parameter_names)
                if op == "head":
                    lines.append(f"{data} = list({data})[:int({count})]")
                else:
                    lines.append(
                        f"{data} = list({data})[-int({count}):] if int({count}) else []"
                    )
            elif op == "count_occurrences":
                needle = self._runtime_or_literal("needle", params, parameter_names)
                lines.append(f"{data} = str({data}).count(str({needle}))")
            elif op == "regex_extract":
                pattern = self._runtime_or_literal("pattern", params, parameter_names)
                lines.extend(
                    [
                        "import re as __fca_re",
                        f"{data} = __fca_re.findall(str({pattern}), str({data}))",
                    ]
                )
            elif op == "replace":
                old = self._runtime_or_literal("old", params, parameter_names)
                new = self._runtime_or_literal("new", params, parameter_names)
                lines.append(f"{data} = str({data}).replace(str({old}), str({new}))")
            elif op == "reverse":
                lines.append(f"{data} = str({data})[::-1]")
            elif op == "upper":
                lines.append(f"{data} = str({data}).upper()")
            elif op == "lower":
                lines.append(f"{data} = str({data}).lower()")
            elif op in {"sum", "mean", "median", "min", "max"}:
                lines.extend(
                    [
                        "import re as __fca_re",
                        f"if isinstance({data}, (list, tuple)):",
                        f"    {numbers} = [float(x) for x in {data}]",
                        "else:",
                        f"    {numbers} = [float(x) for x in __fca_re.findall(r'[-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)', str({data}))]",
                    ]
                )
                if op == "sum":
                    lines.append(f"{data} = sum({numbers})")
                elif op in {"mean", "median"}:
                    lines.append("import statistics as __fca_statistics")
                    fn = "fmean" if op == "mean" else "median"
                    lines.append(f"{data} = __fca_statistics.{fn}({numbers})")
                else:
                    lines.append(f"{data} = {op}({numbers})")
            elif op == "word_count":
                lines.append(f"{data} = len(str({data}).split())")
            elif op == "char_count":
                lines.append(f"{data} = len(str({data}))")
            elif op == "line_count":
                lines.append(f"{data} = len(str({data}).splitlines())")
            else:
                raise ASTPatchError(f"unsupported_ir_operation:{op}")

        lines.append(f"return {data}")
        return tuple(lines)

    @staticmethod
    def _runtime_or_literal(
        name: str,
        params: dict[str, str],
        parameter_names: frozenset[str],
    ) -> str:
        value = params.get(name, "__RUNTIME__")
        if value == "__RUNTIME__":
            if name not in parameter_names:
                raise ASTPatchError(f"missing_runtime_parameter:{name}")
            return name
        if name == "count":
            try:
                return str(int(value))
            except ValueError as exc:
                raise ASTPatchError("invalid_count_parameter") from exc
        return repr(value)

    @staticmethod
    def _validate_generated_body(lines: tuple[str, ...]) -> tuple[str, ...]:
        wrapper = "def __fca_probe(value, needle='', pattern='', old='', new='', count=0):\n"
        wrapper += "".join(f"    {line}\n" for line in lines)
        try:
            tree = ast.parse(wrapper, filename="<fca-ast-patch>")
            compile(tree, "<fca-ast-patch>", "exec")
        except SyntaxError as exc:
            return (f"generated_body_syntax:{exc.lineno}",)

        allowed_imports = {"json", "pathlib", "re", "statistics"}
        forbidden_calls = {"eval", "exec", "compile", "__import__", "open"}
        errors: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] not in allowed_imports:
                        errors.append(f"generated_body_forbidden_import:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                root = str(node.module or "").split(".", 1)[0]
                if root not in allowed_imports:
                    errors.append(f"generated_body_forbidden_import:{root}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in forbidden_calls
            ):
                errors.append(f"generated_body_forbidden_call:{node.func.id}")
        return tuple(errors)

    @staticmethod
    def _reject(
        path: str,
        target_symbol: str,
        source: str,
        before_sha: str,
        ir: ProgramIR | None,
        errors: tuple[str, ...],
    ) -> ASTFunctionPatchResult:
        return ASTFunctionPatchResult(
            ok=False,
            path=path,
            target_symbol=target_symbol,
            source=source,
            before_sha256=before_sha,
            after_sha256=before_sha,
            changed_lines=None,
            ir=ir,
            checks=(),
            errors=errors,
        )
