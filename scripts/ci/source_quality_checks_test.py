#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

import source_quality_checks as gate


class SourceQualityChecksTest(unittest.TestCase):
    def test_python_public_dict_returns_fail_and_payload_arguments_pass(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "python" / "synapse_client"
            source.mkdir(parents=True)
            target = source / "client.py"
            target.write_text(
                "from typing import Any, Dict, Mapping\n\n"
                "def bad_dict() -> dict[str, Any]:\n"
                "    return {}\n\n"
                "def bad_typing_dict() -> Dict[str, Any]:\n"
                "    return {}\n\n"
                "def bad_mapping() -> Mapping[str, Any]:\n"
                "    return {}\n\n"
                "def ok_payload(payload: dict[str, Any]) -> GoodResult:\n"
                "    return GoodResult()\n\n"
                "def _private_helper() -> dict[str, Any]:\n"
                "    return {}\n",
                encoding="utf-8",
            )

            original_root = gate.ROOT
            original_files = gate.PYTHON_TYPED_RETURN_FILES
            try:
                gate.ROOT = root
                gate.PYTHON_TYPED_RETURN_FILES = {target}
                failures = gate.check_python_public_return_models()
            finally:
                gate.ROOT = original_root
                gate.PYTHON_TYPED_RETURN_FILES = original_files

        self.assertEqual(len(failures), 3)
        self.assertIn("bad_dict returns raw dict[str, Any]", "\n".join(failures))
        self.assertIn("bad_typing_dict returns raw Dict[str, Any]", "\n".join(failures))
        self.assertIn("bad_mapping returns raw Mapping[str, Any]", "\n".join(failures))

    def test_typescript_public_record_returns_fail_and_payload_arguments_pass(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "typescript" / "src"
            source.mkdir(parents=True)
            target = source / "client.ts"
            target.write_text(
                "export async function badPromise(): Promise<Record<string, unknown>> { return {}; }\n"
                "export function badRecord(): Record<string, unknown> { return {}; }\n"
                "export function okPayload(payload: Record<string, unknown>): Promise<GoodResult> { return fetchIt(payload); }\n"
                "function _privateHelper(): Record<string, unknown> { return {}; }\n",
                encoding="utf-8",
            )

            original_root = gate.ROOT
            original_files = gate.TYPESCRIPT_TYPED_RETURN_FILES
            try:
                gate.ROOT = root
                gate.TYPESCRIPT_TYPED_RETURN_FILES = {target}
                failures = gate.check_typescript_public_return_models()
            finally:
                gate.ROOT = original_root
                gate.TYPESCRIPT_TYPED_RETURN_FILES = original_files

        self.assertEqual(len(failures), 2)
        self.assertIn("badPromise returns raw Record", "\n".join(failures))
        self.assertIn("badRecord returns raw Record", "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
