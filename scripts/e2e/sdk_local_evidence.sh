#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRODUCT_ROOT="${PRODUCT_ROOT:-/Users/cliff/workspace/agent/Synapse-Network}"
E2E_RUN_ID="${E2E_RUN_ID:-sdk-local-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/output/e2e/sdk-local/$E2E_RUN_ID}"
LOG_FILE="$OUT_DIR/sdk-parity.log"
REPORT_CMD="bash scripts/e2e/sdk_parity_e2e.sh --env local --languages python,typescript,go,java,dotnet --skip-install"

mkdir -p "$OUT_DIR"

PYTHON_VENV_DIR="${PYTHON_VENV_DIR:-$ROOT_DIR/python/.venv}"
PYTHON_BIN="${PYTHON_BIN:-$PYTHON_VENV_DIR/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[sdk-local-evidence] creating Python venv at $PYTHON_VENV_DIR"
  python3 -m venv "$PYTHON_VENV_DIR"
fi
echo "[sdk-local-evidence] ensuring Python SDK dependencies"
"$PYTHON_BIN" -m pip install -q -e "$ROOT_DIR/python[dev]"
export VIRTUAL_ENV="$PYTHON_VENV_DIR"
export PATH="$PYTHON_VENV_DIR/bin:$PATH"

PRIVATE_KEY="$(
  PRODUCT_ROOT="$PRODUCT_ROOT" "$PYTHON_BIN" - <<'PY'
import os
from pathlib import Path

env_path = Path(os.environ["PRODUCT_ROOT"]) / "services/gateway/.env.local"
if not env_path.exists():
    raise SystemExit(f"missing {env_path}")
for line in env_path.read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        continue
    key, value = stripped.split("=", 1)
    if key.strip() == "PRIVATE_KEY":
        print(value.strip().strip('"').strip("'"))
        break
else:
    raise SystemExit(f"PRIVATE_KEY missing from {env_path}")
PY
)"

export SDK_ROOT="$ROOT_DIR"
export PRODUCT_ROOT
export E2E_RUN_ID
export E2E_OUT_DIR="$OUT_DIR"
export SYNAPSE_GATEWAY_URL="${SYNAPSE_GATEWAY_URL:-http://127.0.0.1:8000}"
export SYNAPSE_OWNER_PRIVATE_KEY="${SYNAPSE_OWNER_PRIVATE_KEY:-$PRIVATE_KEY}"
export SYNAPSE_E2E_FIXED_SERVICE_ID="${SYNAPSE_E2E_FIXED_SERVICE_ID:-svc_oss_security_healthcheck}"
export SYNAPSE_E2E_FIXED_COST_USDC="${SYNAPSE_E2E_FIXED_COST_USDC:-0.000000}"
export SYNAPSE_E2E_LLM_SERVICE_ID="${SYNAPSE_E2E_LLM_SERVICE_ID:-svc_deepseek_chat}"
export SYNAPSE_E2E_LLM_MAX_COST_USDC="${SYNAPSE_E2E_LLM_MAX_COST_USDC:-0.010000}"
if [[ -z "${POSTGRES_READONLY_DSN:-}" ]]; then
  POSTGRES_READONLY_DSN="$(
    PRODUCT_ROOT="$PRODUCT_ROOT" "$PYTHON_BIN" - <<'PY'
import os
from pathlib import Path

env_path = Path(os.environ["PRODUCT_ROOT"]) / "services/gateway/.env.local"
for line in env_path.read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        continue
    key, value = stripped.split("=", 1)
    if key.strip() in {"POSTGRES_READONLY_DSN", "POSTGRES_DSN"}:
        print(value.strip().strip('"').strip("'"))
        break
PY
  )"
fi
if [[ -z "$POSTGRES_READONLY_DSN" ]]; then
  echo "[sdk-local-evidence] POSTGRES_READONLY_DSN is required for DB reconciliation" >&2
  exit 2
fi
export POSTGRES_READONLY_DSN

if [[ -z "${SYNAPSE_E2E_FIXED_PAYLOAD_JSON:-}" ]]; then
  export SYNAPSE_E2E_FIXED_PAYLOAD_JSON='{"packageList":["requests==2.31.0"]}'
fi
if [[ -z "${SYNAPSE_E2E_LLM_PAYLOAD_JSON:-}" ]]; then
  export SYNAPSE_E2E_LLM_PAYLOAD_JSON='{"messages":[{"role":"user","content":"hello from sdk local e2e"}]}'
fi

DOTNET_ROOT="${DOTNET_ROOT:-${SYNAPSE_E2E_DOTNET_DIR:-$HOME/.synapse-network-sdk-e2e/dotnet}}"
if [[ -x "$DOTNET_ROOT/dotnet" ]]; then
  export DOTNET_ROOT
  export PATH="$DOTNET_ROOT:$PATH"
fi

if [[ "${SYNAPSE_LOCAL_EVIDENCE_USE_EXISTING_AGENT_KEY:-}" != "1" ]]; then
  unset SYNAPSE_AGENT_KEY
fi

echo "[sdk-local-evidence] run id: $E2E_RUN_ID"
echo "[sdk-local-evidence] output: $OUT_DIR"

curl -fsS "$SYNAPSE_GATEWAY_URL/health" > "$OUT_DIR/gateway-health.json"
curl -fsS "${ADMIN_GATEWAY_URL:-http://127.0.0.1:8300}/health" > "$OUT_DIR/admin-gateway-health.json"
psql "$POSTGRES_READONLY_DSN" -X -v ON_ERROR_STOP=1 -Atc "SELECT 'invocations=' || count(*) FROM synapse_invocations" > "$OUT_DIR/db-preflight.txt"

PYTHONPATH="$ROOT_DIR/python" "$PYTHON_BIN" - <<'PY'
import json
import os
from decimal import Decimal
from pathlib import Path

from synapse_client import SynapseAuth

auth = SynapseAuth.from_private_key(
    os.environ["SYNAPSE_OWNER_PRIVATE_KEY"],
    environment="staging",
    gateway_url=os.environ["SYNAPSE_GATEWAY_URL"],
)
balance = auth.get_balance()
available = Decimal(str(balance.consumer_available_balance))
required = Decimal(str(os.environ["SYNAPSE_E2E_LLM_MAX_COST_USDC"])) * Decimal("5")
payload = {
    "ownerBalance": str(balance.owner_balance),
    "consumerAvailableBalance": str(balance.consumer_available_balance),
    "providerReceivable": str(balance.provider_receivable),
    "platformFeeAccrued": str(balance.platform_fee_accrued),
    "requiredForFiveLlmCalls": str(required),
}
Path(os.environ["E2E_OUT_DIR"], "owner-balance-preflight.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
if available < required:
    raise SystemExit(
        f"local owner balance is insufficient: consumerAvailableBalance={available}, required={required}"
    )
print("[sdk-local-evidence] owner balance preflight passed")
PY

(
  cd "$ROOT_DIR"
  $REPORT_CMD
) 2>&1 | tee "$LOG_FILE"

"$PYTHON_BIN" "$ROOT_DIR/scripts/e2e/sdk_local_evidence_report.py" \
  --log "$LOG_FILE" \
  --out-dir "$OUT_DIR" \
  --run-id "$E2E_RUN_ID" \
  --postgres-dsn "$POSTGRES_READONLY_DSN" \
  --max-cost-usdc "$SYNAPSE_E2E_LLM_MAX_COST_USDC" \
  --command "$REPORT_CMD"

node "$ROOT_DIR/scripts/e2e/sdk_local_screenshots.mjs"

"$PYTHON_BIN" "$ROOT_DIR/scripts/e2e/sdk_local_evidence_report.py" \
  --log "$LOG_FILE" \
  --out-dir "$OUT_DIR" \
  --run-id "$E2E_RUN_ID" \
  --postgres-dsn "$POSTGRES_READONLY_DSN" \
  --max-cost-usdc "$SYNAPSE_E2E_LLM_MAX_COST_USDC" \
  --screenshots-json "$OUT_DIR/screenshots.json" \
  --command "$REPORT_CMD"

echo "[sdk-local-evidence] complete"
echo "[sdk-local-evidence] report: $OUT_DIR/report.md"
echo "[sdk-local-evidence] screenshots: $OUT_DIR/screenshots"
