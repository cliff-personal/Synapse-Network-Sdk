#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[ci:pr] running SDK pull request quality gates"

bash scripts/ci/repo_hygiene_checks.sh
bash scripts/ci/python_checks.sh
bash scripts/ci/typescript_checks.sh
bash scripts/ci/security_checks.sh

echo "[ci:pr] all SDK quality gates passed"
