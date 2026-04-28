#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_SOURCE = ROOT / "python" / "synapse_client"
TYPESCRIPT_SOURCE = ROOT / "typescript" / "src"

MAX_SOURCE_LINES = 500
MAX_TEST_LINES = 700
MAX_PYTHON_FUNCTION_LINES = 40
IGNORED_DIRS = {"__pycache__", ".pytest_cache", ".venv", "dist", "build", "coverage", "node_modules"}


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
        limit = MAX_TEST_LINES if "/test/" in f"/{relative(path)}" or "/tests/" in f"/{relative(path)}" else MAX_SOURCE_LINES
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
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and hasattr(node, "end_lineno"):
                lines = effective_lines_for_node(path, node)
                if lines > MAX_PYTHON_FUNCTION_LINES:
                    failures.append(
                        f"{relative(path)}:{node.lineno} {node.name} has {lines} effective lines; "
                        f"limit is {MAX_PYTHON_FUNCTION_LINES}"
                    )
    return failures


def effective_lines_for_node(path: Path, node: ast.AST) -> int:
    source = path.read_text(encoding="utf-8").splitlines()
    body = getattr(node, "body", [])
    start = getattr(body[0], "lineno", getattr(node, "lineno", 1)) if body else getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    return sum(1 for line in source[start - 1 : end] if line.strip() and not line.strip().startswith("#"))


def main() -> int:
    failures = check_file_lengths() + check_python_function_lengths()
    if failures:
        print("[ci:quality] source quality gate failed")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("[ci:quality] source line and function size gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
