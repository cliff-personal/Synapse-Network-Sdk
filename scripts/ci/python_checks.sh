#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

export SYNAPSE_ENV=staging
unset SYNAPSE_GATEWAY

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
"$PYTHON_BIN" -m pip install -e "./python[dev]"

echo "[ci:python] running Python format check"
"$PYTHON_BIN" -m ruff format --check python/synapse_client

echo "[ci:python] running Python lint"
"$PYTHON_BIN" -m ruff check python/synapse_client

echo "[ci:python] running Python type checks"
"$PYTHON_BIN" -m mypy --config-file python/pyproject.toml python/synapse_client

echo "[ci:python] running Python unit tests with 80% coverage gate"
"$PYTHON_BIN" -m pytest -q \
  python/synapse_client/test/test_auth_unit.py \
  python/synapse_client/test/test_client_unit.py \
  python/synapse_client/test/test_provider_facade_unit.py \
  --cov=synapse_client \
  --cov-report=term-missing \
  --cov-report=xml:python/coverage.xml \
  --cov-fail-under=80

echo "[ci:python] running Python complexity gate"
"$PYTHON_BIN" scripts/ci/source_quality_checks.py
radon_output="$("$PYTHON_BIN" -m radon cc python/synapse_client -n C -s --exclude "*/test/*")"
if [[ -n "$radon_output" ]]; then
  echo "$radon_output"
  echo "[ci:python] cyclomatic complexity C or worse detected; keep functions at radon grade A or B" >&2
  exit 1
fi

echo "[ci:python] building Python package"
"$PYTHON_BIN" -m build python

echo "[ci:python] Python SDK checks passed"
