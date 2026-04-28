#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python}"
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  VENV_DIR="${PYTHON_VENV_DIR:-$ROOT_DIR/python/.venv}"
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "[ci:security] creating virtual environment at $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
  PYTHON_BIN="$VENV_DIR/bin/python"
fi

echo "[ci:security] installing Python security scanner"
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install bandit

echo "[ci:security] running Python static security scan"
"$PYTHON_BIN" -m bandit -q -r python/synapse_client -x python/synapse_client/test

echo "[ci:security] running production npm audit"
npm_config_registry="${NPM_CONFIG_REGISTRY:-https://registry.npmjs.org}" \
  npm audit --prefix typescript --omit=dev --audit-level=high

echo "[ci:security] security checks passed"
