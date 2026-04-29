#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE = ROOT / "python" / "synapse_client"
TYPESCRIPT_SOURCE = ROOT / "typescript" / "src"

MAX_SOURCE_LINES = 500
MAX_TEST_LINES = 700
MAX_PYTHON_FUNCTION_LINES = 40
IGNORED_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "dist",
    "build",
    "coverage",
    "node_modules",
}
PYTHON_TYPED_RETURN_FILES = {
    PYTHON_SOURCE / "auth.py",
    PYTHON_SOURCE / "_auth_credentials.py",
    PYTHON_SOURCE / "_auth_finance.py",
    PYTHON_SOURCE / "_auth_provider_control.py",
    PYTHON_SOURCE / "client.py",
    PYTHON_SOURCE / "provider.py",
}
TYPESCRIPT_TYPED_RETURN_FILES = {
    TYPESCRIPT_SOURCE / "auth.ts",
    TYPESCRIPT_SOURCE / "auth_provider_control.ts",
    TYPESCRIPT_SOURCE / "client.ts",
    TYPESCRIPT_SOURCE / "provider.ts",
}
RAW_RETURN_NAMES = {"dict", "Dict", "Mapping", "MutableMapping"}
ALLOWED_RETURN_NAME_PREFIXES = ("_", "parse_", "serialize_", "build_", "request_", "response_", "model_")
ALLOWED_RETURN_NAME_SUFFIXES = ("_body", "_payload", "_patch", "_schema", "_schemas", "_manifest", "_headers")


def iter_files(root: Path, suffix: str) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob(f"*{suffix}"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def effective_lines(path: Path) -> int:
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("//"):
            count += 1
    return count


def check_file_lengths() -> list[str]:
    failures: list[str] = []
    for path in iter_files(PYTHON_SOURCE, ".py") + iter_files(TYPESCRIPT_SOURCE, ".ts"):
        limit = (
            MAX_TEST_LINES
            if "/test/" in f"/{relative(path)}" or "/tests/" in f"/{relative(path)}"
            else MAX_SOURCE_LINES
        )
        total = len(path.read_text(encoding="utf-8").splitlines())
        if total > limit:
            failures.append(f"{relative(path)} has {total} lines; limit is {limit}")
    return failures


def check_python_function_lengths() -> list[str]:
    failures: list[str] = []
    for path in iter_files(PYTHON_SOURCE, ".py"):
        if "/test/" in f"/{relative(path)}":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and hasattr(
                node, "end_lineno"
            ):
                lines = effective_lines_for_node(path, node)
                if lines > MAX_PYTHON_FUNCTION_LINES:
                    failures.append(
                        f"{relative(path)}:{node.lineno} {node.name} has {lines} effective lines; "
                        f"limit is {MAX_PYTHON_FUNCTION_LINES}"
                    )
    return failures


def check_public_sdk_return_models() -> list[str]:
    failures = check_python_public_return_models()
    failures.extend(check_typescript_public_return_models())
    return failures


def check_python_public_return_models() -> list[str]:
    failures: list[str] = []
    for path in sorted(PYTHON_TYPED_RETURN_FILES):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if is_allowed_raw_return_name(node.name) or node.returns is None:
                continue
            annotation = ast.unparse(node.returns)
            if annotation_contains_raw_map(node.returns):
                failures.append(
                    f"{relative(path)}:{node.lineno} {node.name} returns raw {annotation}; use a SDK model"
                )
    return failures


def is_allowed_raw_return_name(name: str) -> bool:
    return name.startswith(ALLOWED_RETURN_NAME_PREFIXES) or name.endswith(ALLOWED_RETURN_NAME_SUFFIXES)


def annotation_contains_raw_map(node: ast.AST | None) -> bool:
    if node is None:
        return False
    if isinstance(node, ast.Name):
        return node.id in RAW_RETURN_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in RAW_RETURN_NAMES
    if isinstance(node, ast.Subscript):
        return annotation_contains_raw_map(node.value) or annotation_contains_raw_map(node.slice)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return annotation_contains_raw_map(node.left) or annotation_contains_raw_map(node.right)
    if isinstance(node, ast.Tuple):
        return any(annotation_contains_raw_map(element) for element in node.elts)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        text = node.value.replace(" ", "")
        return any(text == name or text.startswith(f"{name}[") for name in RAW_RETURN_NAMES)
    return False


def check_typescript_public_return_models() -> list[str]:
    failures: list[str] = []
    patterns = [
        re.compile(
            r"^\s*export\s+(?:async\s+)?function\s+([A-Za-z]\w*)\s*\([^{};]*?\)\s*:"
            r"\s*(?:Promise<\s*)?Record<string, unknown>",
            re.MULTILINE | re.DOTALL,
        ),
        re.compile(
            r"^\s*(?:async\s+)?([A-Za-z]\w*)\s*\([^{};]*?\)\s*:\s*(?:Promise<\s*)?Record<string, unknown>",
            re.MULTILINE | re.DOTALL,
        ),
    ]
    for path in sorted(TYPESCRIPT_TYPED_RETURN_FILES):
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            for match in pattern.finditer(text):
                lineno = text.count("\n", 0, match.start()) + 1
                name = match.group(1)
                if name in {"constructor"} or name.startswith("_"):
                    continue
                failures.append(
                    f"{relative(path)}:{lineno} {name} returns raw Record; use a named SDK result type"
                )
    return sorted(set(failures))


def effective_lines_for_node(path: Path, node: ast.AST) -> int:
    source = path.read_text(encoding="utf-8").splitlines()
    body = getattr(node, "body", [])
    start = (
        getattr(body[0], "lineno", getattr(node, "lineno", 1))
        if body
        else getattr(node, "lineno", 1)
    )
    end = getattr(node, "end_lineno", start)
    return sum(
        1
        for line in source[start - 1 : end]
        if line.strip() and not line.strip().startswith("#")
    )


def main() -> int:
    failures = (
        check_file_lengths()
        + check_python_function_lengths()
        + check_public_sdk_return_models()
    )
    if failures:
        print("[ci:quality] source quality gate failed")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("[ci:quality] source line and function size gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
