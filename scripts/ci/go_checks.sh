#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v go >/dev/null 2>&1; then
  echo "[ci:go] Go toolchain not found; skipping local Go checks"
  exit 0
fi

echo "[ci:go] running Go SDK tests"
go -C go test ./...

echo "[ci:go] Go SDK checks passed"
