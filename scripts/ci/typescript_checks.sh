#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[ci:typescript] installing TypeScript SDK dependencies"
npm_config_registry="${NPM_CONFIG_REGISTRY:-https://registry.npmjs.org}" npm ci --prefix typescript

echo "[ci:typescript] running TypeScript format, lint, and type checks"
npm run lint --prefix typescript

echo "[ci:typescript] type-checking TypeScript examples"
npm run typecheck:examples --prefix typescript

echo "[ci:typescript] building TypeScript package"
npm run build --prefix typescript

echo "[ci:typescript] running TypeScript unit tests"
npm run test:unit --prefix typescript

echo "[ci:typescript] running TypeScript unit coverage gate"
npm run test:unit:coverage --prefix typescript

echo "[ci:typescript] running duplication gate"
npm run duplication --prefix typescript

echo "[ci:typescript] TypeScript SDK checks passed"
