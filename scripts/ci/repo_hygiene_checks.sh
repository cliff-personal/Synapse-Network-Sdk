#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[ci:hygiene] checking stale gateway domains"
STALE_GATEWAY_DOMAIN="gateway.synapse"".network"
if grep -RInF --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=dist --exclude-dir=build --exclude-dir=coverage --exclude-dir=.pytest_cache \
  "$STALE_GATEWAY_DOMAIN" .; then
  echo "[ci:hygiene] stale gateway domain detected: $STALE_GATEWAY_DOMAIN" >&2
  exit 1
fi

echo "[ci:hygiene] checking public preview staging defaults"
grep -RIn --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv \
  "https://api-staging.synapse-network.ai" README.md docs python/synapse_client typescript/src typescript/tests >/dev/null

echo "[ci:hygiene] checking tracked sensitive filenames"
sensitive_files="$(
  git ls-files \
    | grep -Ei '(^|/)\.env($|\.|/)|private|secret|key|pem|wallet|mnemonic|credential' \
    | grep -Ev '(^|/)\.env\.example$' \
    || true
)"
if [[ -n "$sensitive_files" ]]; then
  echo "[ci:hygiene] potentially sensitive tracked filenames detected:" >&2
  echo "$sensitive_files" >&2
  exit 1
fi

echo "[ci:hygiene] repo hygiene checks passed"
