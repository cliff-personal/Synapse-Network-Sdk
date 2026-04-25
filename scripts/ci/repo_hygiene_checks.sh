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

echo "[ci:hygiene] checking deprecated product brand wording"
OLD_AGENT_PAY="Agent""Pay"
OLD_SYNAPSE_AGENT_PAY="Synapse Agent""Pay"
OLD_BUSINESS_TO_AGENT="Business-to-""Agent"
OLD_B_TWO_A="B""2A"
if grep -RInE --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=dist --exclude-dir=build --exclude-dir=coverage --exclude-dir=.pytest_cache \
  "($OLD_SYNAPSE_AGENT_PAY|$OLD_AGENT_PAY|$OLD_BUSINESS_TO_AGENT|$OLD_B_TWO_A)" .; then
  echo "[ci:hygiene] deprecated product brand wording detected; use SynapseNetwork" >&2
  exit 1
fi

echo "[ci:hygiene] checking multilingual README split"
test -f README.zh-CN.md
test -f docs/sdk/README.zh-CN.md
grep -q '<strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a>' README.md
grep -q '<a href="./README.md">English</a> · <strong>简体中文</strong>' README.zh-CN.md
grep -q '<strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a>' docs/sdk/README.md
grep -q '<a href="./README.md">English</a> · <strong>简体中文</strong>' docs/sdk/README.zh-CN.md
python3 - <<'PY'
from pathlib import Path
import re

def assert_no_han(path: str) -> None:
    text = Path(path).read_text()
    normalized = text.replace("简体中文", "")
    if re.search(r"[\u4e00-\u9fff]", normalized):
        raise SystemExit(f"{path} should keep Chinese content in the zh-CN README")

assert_no_han("README.md")
assert_no_han("docs/sdk/README.md")
PY

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
