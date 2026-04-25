#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[ci:typescript] installing TypeScript SDK dependencies"
npm ci --prefix typescript

echo "[ci:typescript] running TypeScript type checks"
npm run lint --prefix typescript

echo "[ci:typescript] building TypeScript package"
npm run build --prefix typescript

echo "[ci:typescript] running TypeScript unit tests"
npm run test:unit --prefix typescript

echo "[ci:typescript] running TypeScript unit coverage gate"
npm run test:unit:coverage --prefix typescript

echo "[ci:typescript] TypeScript SDK checks passed"
