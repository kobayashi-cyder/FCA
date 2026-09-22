from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import ast
import json
import re
from typing import Any


class CodeGenerationError(RuntimeError):
    """Raised when a request cannot be converted into a verified code candidate."""


@dataclass(frozen=True)
class ProgramIR:
    language: str
    input_mode: str
    operations: tuple[str, ...]
    parameters: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "input_mode": self.input_mode,
            "operations": list(self.operations),
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True)
class CodeGenerationResult:
    ok: bool
    request: str
    filename: str
    source: str
    ir: ProgramIR | None
    checks: tuple[str, ...]
    errors: tuple[str, ...]
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ir"] = self.ir.to_dict() if self.ir is not None else None
        return data


class FCACodeGenerator:
    """Bounded local code generator derived from FAP's verified code path.

    The generator intentionally keeps generation pure: it returns source text and
    verification evidence but never writes files, invokes a shell, changes a
    repository, or promotes a candidate. Repository mutation remains the job of
    FCA's existing repository-coding host boundary.

    V1 supports deterministic Python programs expressed as a compact ProgramIR.
    This is narrower than an LLM coder but materially more general than a set of
    per-task source templates.
    """

    VERSION = "fca.code_generation.v1"
    CREATE_WORD = re.compile(
        r"(作って|作成|生成|書いて|実装|構築|build|create|make|generate)",
        re.I,
    )
    CODE_WORD = re.compile(
        r"(python|\.py\b|スクリプト|コード|program|programming)",
        re.I,
    )
    MAX_SOURCE_BYTES = 300_000

    _ALLOWED_IMPORTS = {
        "argparse",
        "json",
        "re",
        "statistics",
        "pathlib",
    }
    _FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__", "open"}

    @classmethod
    def claims(cls, text: str) -> bool:
        src = str(text or "")
        return bool(cls.CREATE_WORD.search(src) and cls.CODE_WORD.search(src))

    @staticmethod
    def _has(src: str, pattern: str) -> bool:
        return bool(re.search(pattern, src, re.I))

    def infer_ir(self, request: str) -> ProgramIR:
        src = str(request or "").strip()
        if not src:
            raise CodeGenerationError("request is required")
        if not self._has(src, r"python|\.py\b|スクリプト|コード|program"):
            raise CodeGenerationError("v1 currently supports Python generation")

        is_json = self._has(src, r"json.{0,16}(読|ファイル)|jsonファイル")
        is_file = self._has(
            src,
            r"(テキスト|txt|文章).{0,10}ファイル|ファイル.{0,10}(読|入力)",
        )
        input_mode = "json_file" if is_json else ("text_file" if is_file else "text")

        ops: list[str] = []
        params: dict[str, str] = {}

        if is_json and self._has(
            src,
            r"(数値|数字).{0,12}(キー|項目)|値が.{0,8}(数値|数字).{0,8}(キー|項目)",
        ):
            ops.append("json_numeric_keys")
        elif is_json and self._has(src, r"(キー一覧|キーを表示|keys?)"):
            ops.append("json_keys")

        if self._has(
            src,
            r"(数字|数値).{0,8}(だけ)?.{0,8}(抽出|取り出|抜き出)|extract.{0,8}numbers?",
        ):
            ops.append("extract_numbers")

        line_semantics = self._has(src, r"(行|line)")
        if line_semantics and any(
            self._has(src, p)
            for p in (
                r"空行",
                r"重複.{0,4}(消|除)",
                r"昇順",
                r"降順",
                r"先頭",
                r"末尾",
            )
        ):
            if "split_lines" not in ops:
                ops.append("split_lines")

        if self._has(src, r"空行.{0,8}(除|消)|空白行.{0,8}(除|消)|non.?empty"):
            if "split_lines" not in ops:
                ops.append("split_lines")
            ops.append("filter_nonempty")

        if self._has(src, r"重複.{0,6}(消|除)|ユニーク|unique|dedup"):
            ops.append("unique")

        if self._has(src, r"降順|descending"):
            ops.append("sort_desc")
        elif self._has(src, r"昇順|並べ替|ソート|sort"):
            ops.append("sort")

        head = re.search(r"(?:先頭|最初)[^0-9]{0,5}(\d+)\s*(?:件|行|個)?", src)
        tail = re.search(r"(?:末尾|最後)[^0-9]{0,5}(\d+)\s*(?:件|行|個)?", src)
        if head:
            params["count"] = head.group(1)
            ops.append("head")
        elif tail:
            params["count"] = tail.group(1)
            ops.append("tail")

        if self._has(
            src,
            r"(指定した|指定の).{0,8}(単語|文字列).{0,12}(回数|数える)|出現回数|occurrences?",
        ):
            ops.append("count_occurrences")
            params["needle"] = "__RUNTIME__"

        if self._has(src, r"正規表現.{0,10}(抽出|取り出)|regex.{0,8}(extract|find)"):
            ops.append("regex_extract")
            params["pattern"] = "__RUNTIME__"

        if self._has(src, r"置換|replace"):
            ops.append("replace")
            params["old"] = "__RUNTIME__"
            params["new"] = "__RUNTIME__"

        if self._has(src, r"逆順|反転|reverse"):
            ops.append("reverse")
        if self._has(src, r"大文字|uppercase|upper\b"):
            ops.append("upper")
        if self._has(src, r"小文字|lowercase|lower\b"):
            ops.append("lower")

        if self._has(src, r"合計|総和|sum"):
            ops.append("sum")
        if self._has(src, r"平均|mean|average"):
            ops.append("mean")
        if self._has(src, r"中央値|median"):
            ops.append("median")
        if self._has(src, r"最小|min(?:imum)?\b"):
            ops.append("min")
        if self._has(src, r"最大|max(?:imum)?\b"):
            ops.append("max")

        if self._has(src, r"単語数|word\s*count"):
            ops.append("word_count")
        if self._has(src, r"文字数|char(?:acter)?\s*count|length"):
            ops.append("char_count")
        if self._has(src, r"行数|line\s*count"):
            ops.append("line_count")

        ordered: list[str] = []
        for op in ops:
            if op not in ordered:
                ordered.append(op)

        if not ordered:
            raise CodeGenerationError(
                "request does not map to the verified ProgramIR vocabulary"
            )
        return ProgramIR(
            language="python",
            input_mode=input_mode,
            operations=tuple(ordered),
            parameters=tuple(sorted(params.items())),
        )

    def generate(self, request: str, *, filename: str = "fca_generated.py") -> CodeGenerationResult:
        request = str(request or "").strip()
        ir = self.infer_ir(request)
        self._validate_filename(filename)
        source = self._emit_python(ir)
        checks, errors = self.validate_source(source)
        raw = source.encode("utf-8")
        return CodeGenerationResult(
            ok=not errors,
            request=request,
            filename=filename,
            source=source,
            ir=ir,
            checks=checks,
            errors=errors,
            sha256=sha256(raw).hexdigest(),
        )

    @classmethod
    def validate_source(cls, source: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        raw = source.encode("utf-8")
        checks: list[str] = []
        errors: list[str] = []

        if len(raw) <= cls.MAX_SOURCE_BYTES:
            checks.append("size_limit")
        else:
            errors.append("artifact exceeds size limit")

        try:
            tree = ast.parse(source, filename="<fca-generated>")
            compile(tree, "<fca-generated>", "exec")
            checks.append("compile")
        except SyntaxError as exc:
            return tuple(checks), (f"python syntax: {exc.msg} line={exc.lineno}",)

        policy_errors = cls._python_policy(tree)
        if policy_errors:
            errors.extend(policy_errors)
        else:
            checks.append("ast_policy")

        if "PROGRAM_IR =" in source and "def apply_program(" in source:
            checks.append("ir_contract")
        else:
            errors.append("missing ProgramIR contract")

        return tuple(checks), tuple(errors)

    @classmethod
    def _python_policy(cls, tree: ast.AST) -> list[str]:
        errors: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root not in cls._ALLOWED_IMPORTS:
                        errors.append(f"forbidden import: {root}")
            elif isinstance(node, ast.ImportFrom):
                root = str(node.module or "").split(".", 1)[0]
                if root not in cls._ALLOWED_IMPORTS:
                    errors.append(f"forbidden import: {root}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in cls._FORBIDDEN_CALLS
            ):
                errors.append(f"forbidden call: {node.func.id}")
        return errors

    @staticmethod
    def _validate_filename(filename: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}\.py", filename):
            raise ValueError("filename must be a simple .py filename")

    @staticmethod
    def _emit_python(ir: ProgramIR) -> str:
        params = dict(ir.parameters)
        return f'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import statistics

INPUT_MODE = {ir.input_mode!r}
PROGRAM_IR = {list(ir.operations)!r}
IR_PARAMS = {params!r}


def _as_numbers(value):
    if isinstance(value, (list, tuple)):
        return [float(x) for x in value]
    return [
        float(x)
        for x in re.findall(r"[-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)", str(value))
    ]


def _unique(value):
    seen = set()
    out = []
    for item in list(value):
        key = (
            json.dumps(item, ensure_ascii=False, sort_keys=True)
            if isinstance(item, (dict, list))
            else repr(item)
        )
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def apply_program(value, *, needle="", pattern="", old="", new="", count=0):
    data = value
    for op in PROGRAM_IR:
        if op == "json_numeric_keys":
            if not isinstance(data, dict):
                raise TypeError("JSON object required")
            data = sorted(
                str(k)
                for k, v in data.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            )
        elif op == "json_keys":
            if not isinstance(data, dict):
                raise TypeError("JSON object required")
            data = sorted(map(str, data.keys()))
        elif op == "extract_numbers":
            data = _as_numbers(data)
        elif op == "split_lines":
            data = str(data).splitlines()
        elif op == "filter_nonempty":
            data = [str(x).strip() for x in data if str(x).strip()]
        elif op == "unique":
            data = _unique(data if isinstance(data, list) else str(data))
        elif op == "sort":
            data = sorted(data)
        elif op == "sort_desc":
            data = sorted(data, reverse=True)
        elif op == "head":
            data = list(data)[:count]
        elif op == "tail":
            data = list(data)[-count:] if count else []
        elif op == "count_occurrences":
            data = str(data).count(needle)
        elif op == "regex_extract":
            data = re.findall(pattern, str(data))
        elif op == "replace":
            data = str(data).replace(old, new)
        elif op == "reverse":
            data = str(data)[::-1]
        elif op == "upper":
            data = str(data).upper()
        elif op == "lower":
            data = str(data).lower()
        elif op == "sum":
            data = sum(_as_numbers(data))
        elif op == "mean":
            data = statistics.fmean(_as_numbers(data))
        elif op == "median":
            data = statistics.median(_as_numbers(data))
        elif op == "min":
            data = min(_as_numbers(data))
        elif op == "max":
            data = max(_as_numbers(data))
        elif op == "word_count":
            data = len(str(data).split())
        elif op == "char_count":
            data = len(str(data))
        elif op == "line_count":
            data = len(str(data).splitlines())
        else:
            raise ValueError(f"unsupported IR op: {{op}}")
    return data


def load_input(raw):
    if INPUT_MODE == "json_file":
        return json.loads(Path(raw).read_text(encoding="utf-8"))
    if INPUT_MODE == "text_file":
        return Path(raw).read_text(encoding="utf-8")
    return raw


def main():
    parser = argparse.ArgumentParser(
        description="Generated by FCA bounded ProgramIR code generator"
    )
    parser.add_argument("input", nargs="?", default="")
    parser.add_argument("--needle", default="")
    parser.add_argument("--pattern", default="")
    parser.add_argument("--old", default="")
    parser.add_argument("--new", default="")
    parser.add_argument(
        "--count",
        type=int,
        default=int(IR_PARAMS.get("count", "0") if IR_PARAMS.get("count") not in {{None, "__RUNTIME__"}} else 0),
    )
    args = parser.parse_args()

    value = load_input(args.input)
    result = apply_program(
        value,
        needle=args.needle,
        pattern=args.pattern,
        old=args.old,
        new=args.new,
        count=args.count,
    )
    if isinstance(result, (dict, list)):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
'''
