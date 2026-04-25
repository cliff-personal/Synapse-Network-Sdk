#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python}"
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  VENV_DIR="${PYTHON_VENV_DIR:-$ROOT_DIR/python/.venv}"
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "[ci:python] creating virtual environment at $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
  PYTHON_BIN="$VENV_DIR/bin/python"
fi

echo "[ci:python] installing Python SDK dev dependencies"
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -e "./python[dev]" pytest-cov

echo "[ci:python] running Python unit tests with coverage"
"$PYTHON_BIN" -m pytest -q \
  python/synapse_client/test/test_auth_unit.py \
  python/synapse_client/test/test_client_unit.py \
  --cov=synapse_client \
  --cov-report=term-missing \
  --cov-report=xml:python/coverage.xml \
  --cov-fail-under=75

echo "[ci:python] building Python package"
"$PYTHON_BIN" -m build python

echo "[ci:python] Python SDK checks passed"
