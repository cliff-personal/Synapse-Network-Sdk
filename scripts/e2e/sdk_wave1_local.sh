#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

LANGUAGES="python,typescript,go,java,dotnet"
FREE_ONLY=false
INSTALL_MISSING=true
SKIP_AUTH_NEGATIVE=false

usage() {
  cat <<'EOF'
Usage: bash scripts/e2e/sdk_wave1_local.sh [options]

Options:
  --languages python,typescript,go,java,dotnet
                               Comma-separated SDKs to verify. Default: all SDKs
  --free-only                  Skip token-metered LLM invoke
  --skip-install               Do not install missing local toolchains
  --skip-auth-negative         Skip invalid credential negative checks
  -h, --help                   Show this help

Required:
  SYNAPSE_AGENT_KEY            Staging Agent Key, e.g. agt_xxx

Optional:
  SYNAPSE_GATEWAY_URL          Explicit Gateway URL; defaults to SDK staging
  SYNAPSE_E2E_FIXED_SERVICE_ID Fixed-price API service override
  SYNAPSE_E2E_FIXED_COST_USDC  Required with SYNAPSE_E2E_FIXED_SERVICE_ID
  SYNAPSE_E2E_FIXED_PAYLOAD_JSON
  SYNAPSE_E2E_LLM_SERVICE_ID   Default: svc_deepseek_chat
  SYNAPSE_E2E_LLM_MAX_COST_USDC Default: 0.010000
  SYNAPSE_E2E_LLM_PAYLOAD_JSON
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --languages)
      LANGUAGES="${2:-}"
      shift 2
      ;;
    --free-only)
      FREE_ONLY=true
      shift
      ;;
    --skip-install)
      INSTALL_MISSING=false
      shift
      ;;
    --skip-auth-negative)
      SKIP_AUTH_NEGATIVE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[e2e:sdk-wave1] unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${SYNAPSE_AGENT_KEY:-}" ]]; then
  echo "[e2e:sdk-wave1] SYNAPSE_AGENT_KEY is required for real staging E2E" >&2
  exit 2
fi

export SYNAPSE_E2E_FREE_ONLY="$FREE_ONLY"
export SYNAPSE_E2E_SKIP_AUTH_NEGATIVE="$SKIP_AUTH_NEGATIVE"

if [[ -n "${SYNAPSE_GATEWAY_URL:-}" ]]; then
  echo "[e2e:sdk-wave1] using explicit SYNAPSE_GATEWAY_URL=$SYNAPSE_GATEWAY_URL"
else
  echo "[e2e:sdk-wave1] using SDK default staging Gateway"
fi

fail_missing_tool() {
  local name="$1"
  echo "[e2e:sdk-wave1] missing $name and --skip-install was set" >&2
  exit 2
}

require_brew() {
  if ! command -v brew >/dev/null 2>&1; then
    echo "[e2e:sdk-wave1] Homebrew is required to auto-install $*" >&2
    exit 2
  fi
}

brew_install() {
  if [[ "$INSTALL_MISSING" != "true" ]]; then
    fail_missing_tool "$*"
  fi
  require_brew "$@"
  echo "[e2e:sdk-wave1] installing $*"
  brew install "$@"
}

ensure_go() {
  if command -v go >/dev/null 2>&1; then
    return
  fi
  brew_install go
}

java_major_version() {
  if ! command -v java >/dev/null 2>&1; then
    return 1
  fi
  local spec
  spec="$(java -XshowSettings:properties -version 2>&1 | awk -F= '/java.specification.version/ {gsub(/[[:space:]]/, "", $2); print $2; exit}')"
  if [[ "$spec" == 1.* ]]; then
    echo "${spec#1.}"
  else
    echo "$spec"
  fi
}

ensure_java() {
  if ! command -v mvn >/dev/null 2>&1; then
    brew_install maven
  fi

  local major
  major="$(java_major_version || true)"
  if [[ -z "$major" || "$major" -lt 17 ]]; then
    brew_install openjdk@17
    if /usr/libexec/java_home -v 17 >/dev/null 2>&1; then
      export JAVA_HOME
      JAVA_HOME="$(/usr/libexec/java_home -v 17)"
    elif [[ -d "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home" ]]; then
      export JAVA_HOME="/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
      export PATH="$JAVA_HOME/bin:$PATH"
    fi
  fi
}

has_dotnet_8() {
  command -v dotnet >/dev/null 2>&1 && dotnet --list-sdks 2>/dev/null | grep -q '^8\.'
}

ensure_dotnet() {
  if has_dotnet_8; then
    return
  fi
  if [[ "$INSTALL_MISSING" != "true" ]]; then
    fail_missing_tool ".NET SDK 8.0"
  fi

  local dotnet_dir="${SYNAPSE_E2E_DOTNET_DIR:-$HOME/.synapse-network-sdk-e2e/dotnet}"
  mkdir -p "$dotnet_dir"
  echo "[e2e:sdk-wave1] installing .NET SDK 8.0 into $dotnet_dir"
  curl -fsSL https://dot.net/v1/dotnet-install.sh -o "$dotnet_dir/dotnet-install.sh"
  bash "$dotnet_dir/dotnet-install.sh" --channel 8.0 --install-dir "$dotnet_dir" --no-path
  export DOTNET_ROOT="$dotnet_dir"
  export PATH="$DOTNET_ROOT:$PATH"
}

ensure_python3() {
  if command -v python3 >/dev/null 2>&1; then
    return
  fi
  brew_install python
}

ensure_node() {
  if command -v npm >/dev/null 2>&1; then
    return
  fi
  brew_install node
}

validate_events() {
  local output_file="$1"
  local language="$2"
  python3 - "$output_file" "$language" "$FREE_ONLY" "$SKIP_AUTH_NEGATIVE" <<'PY'
import json
import sys

path, language, free_only, skip_auth_negative = sys.argv[1:5]
required = {"health", "local-negative", "fixed-price"}
if free_only != "true":
    required.add("llm")
if skip_auth_negative != "true":
    required.add("auth-negative")

seen = set()
with open(path, "r", encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if not line.startswith("{"):
            continue
        event = json.loads(line)
        if event.get("language") != language:
            raise SystemExit(f"unexpected language event: {event}")
        scenario = event.get("scenario")
        if scenario:
            seen.add(scenario)

missing = sorted(required - seen)
if missing:
    raise SystemExit(f"{language} e2e missing scenarios: {', '.join(missing)}")
PY
}

run_and_validate() {
  local language="$1"
  shift
  local output_file
  output_file="$(mktemp)"
  echo "[e2e:sdk-wave1] running $language real Gateway E2E"
  "$@" | tee "$output_file"
  validate_events "$output_file" "$language"
  rm -f "$output_file"
}

run_language() {
  local language="$1"
  case "$language" in
    python)
      ensure_python3
      bash scripts/ci/python_checks.sh
      run_and_validate python env PYTHONPATH="$ROOT_DIR/python" python3 python/examples/e2e.py
      ;;
    typescript|ts)
      ensure_node
      bash scripts/ci/typescript_checks.sh
      run_and_validate typescript npm run example:e2e --prefix typescript
      ;;
    go)
      ensure_go
      bash scripts/ci/go_checks.sh
      run_and_validate go go -C go run ./examples/e2e
      ;;
    java)
      ensure_java
      bash scripts/ci/java_checks.sh
      run_and_validate java mvn -q -f java/examples/pom.xml \
        org.codehaus.mojo:exec-maven-plugin:3.5.0:java \
        -Dexec.mainClass=ai.synapsenetwork.sdk.examples.E2eSmoke
      ;;
    dotnet)
      ensure_dotnet
      bash scripts/ci/dotnet_checks.sh
      run_and_validate dotnet dotnet run --project dotnet/examples/e2e/e2e.csproj --configuration Release
      ;;
    *)
      echo "[e2e:sdk-wave1] unsupported language: $language" >&2
      exit 2
      ;;
  esac
}

ensure_python3

IFS=',' read -r -a SELECTED_LANGUAGES <<< "$LANGUAGES"
for language in "${SELECTED_LANGUAGES[@]}"; do
  language="$(echo "$language" | tr -d '[:space:]')"
  if [[ -n "$language" ]]; then
    run_language "$language"
  fi
done

echo "[e2e:sdk-wave1] all selected SDKs passed real Gateway E2E"
