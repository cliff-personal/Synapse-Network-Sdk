#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

LANGUAGES="python,typescript,go,java,dotnet"
TARGET_ENV="staging"
RUN_RUNTIME=true
RUN_FULL=false
INSTALL_MISSING=true

usage() {
  cat <<'EOF'
Usage: bash scripts/e2e/sdk_parity_e2e.sh [options]

Options:
  --languages python,typescript,go,java,dotnet
                               Comma-separated SDKs to verify. Default: all SDKs
  --env staging|local          Target Gateway. "local" requires SYNAPSE_GATEWAY_URL
  --owner-only                 Run owner/provider parity smoke only
  --full                       Enable side-effecting checks guarded by extra env vars
  --skip-install               Do not install missing local toolchains
  -h, --help                   Show this help

Required:
  SYNAPSE_OWNER_PRIVATE_KEY    Owner wallet private key for auth challenge signing

Runtime invoke requirements:
  SYNAPSE_AGENT_KEY            Optional. If missing, the script issues a short-lived
                               staging/local credential from SYNAPSE_OWNER_PRIVATE_KEY.

Environment rules:
  --env staging                Uses SDK staging preset unless SYNAPSE_GATEWAY_URL overrides it
  --env local                  Requires explicit SYNAPSE_GATEWAY_URL; no SDK exposes local as
                               a public environment preset

Optional runtime service overrides:
  SYNAPSE_E2E_FIXED_SERVICE_ID
  SYNAPSE_E2E_FIXED_COST_USDC
  SYNAPSE_E2E_FIXED_PAYLOAD_JSON
  SYNAPSE_E2E_LLM_SERVICE_ID
  SYNAPSE_E2E_LLM_MAX_COST_USDC
  SYNAPSE_E2E_LLM_PAYLOAD_JSON

Optional full side-effecting checks:
  RUN_SDK_PARITY_FULL_E2E=1
  SYNAPSE_E2E_DEPOSIT_TX_HASH
  SYNAPSE_E2E_DEPOSIT_AMOUNT_USDC
  SYNAPSE_PROVIDER_ENDPOINT_URL
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --languages)
      LANGUAGES="${2:-}"
      shift 2
      ;;
    --env)
      TARGET_ENV="${2:-}"
      shift 2
      ;;
    --owner-only)
      RUN_RUNTIME=false
      shift
      ;;
    --full)
      RUN_FULL=true
      shift
      ;;
    --skip-install)
      INSTALL_MISSING=false
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[e2e:sdk-parity] unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$TARGET_ENV" in
  staging)
    export SYNAPSE_ENV=staging
    ;;
  local)
    if [[ -z "${SYNAPSE_GATEWAY_URL:-}" ]]; then
      echo "[e2e:sdk-parity] --env local requires SYNAPSE_GATEWAY_URL" >&2
      exit 2
    fi
    ;;
  *)
    echo "[e2e:sdk-parity] --env must be staging or local" >&2
    exit 2
    ;;
esac

if [[ -z "${SYNAPSE_OWNER_PRIVATE_KEY:-}" ]]; then
  echo "[e2e:sdk-parity] SYNAPSE_OWNER_PRIVATE_KEY is required" >&2
  exit 2
fi

export RUN_SDK_PARITY_FULL_E2E="${RUN_SDK_PARITY_FULL_E2E:-$RUN_FULL}"

cleanup_paths=()
cleanup() {
  ((${#cleanup_paths[@]})) || return 0
  for path in "${cleanup_paths[@]}"; do
    rm -rf "$path"
  done
}
trap cleanup EXIT

fail_missing_tool() {
  local name="$1"
  echo "[e2e:sdk-parity] missing $name and --skip-install was set" >&2
  exit 2
}

require_brew() {
  if ! command -v brew >/dev/null 2>&1; then
    echo "[e2e:sdk-parity] Homebrew is required to auto-install $*" >&2
    exit 2
  fi
}

brew_install() {
  if [[ "$INSTALL_MISSING" != "true" ]]; then
    fail_missing_tool "$*"
  fi
  require_brew "$@"
  echo "[e2e:sdk-parity] installing $*"
  brew install "$@"
}

ensure_python3() {
  command -v python3 >/dev/null 2>&1 || brew_install python
}

ensure_node() {
  command -v npm >/dev/null 2>&1 || brew_install node
  if [[ ! -d "$ROOT_DIR/typescript/node_modules" ]]; then
    npm_config_registry="${NPM_CONFIG_REGISTRY:-https://registry.npmjs.org}" npm ci --prefix "$ROOT_DIR/typescript"
  fi
}

ensure_go() {
  command -v go >/dev/null 2>&1 || brew_install go
}

java_major_version() {
  if ! command -v java >/dev/null 2>&1; then
    return 1
  fi
  java -XshowSettings:properties -version 2>&1 | awk -F= '/java.specification.version/ {gsub(/[[:space:]]/, "", $2); sub(/^1\./, "", $2); print $2; exit}'
}

ensure_java() {
  command -v mvn >/dev/null 2>&1 || brew_install maven
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
  echo "[e2e:sdk-parity] installing .NET SDK 8.0 into $dotnet_dir"
  curl -fsSL https://dot.net/v1/dotnet-install.sh -o "$dotnet_dir/dotnet-install.sh"
  bash "$dotnet_dir/dotnet-install.sh" --channel 8.0 --install-dir "$dotnet_dir" --no-path
  export DOTNET_ROOT="$dotnet_dir"
  export PATH="$DOTNET_ROOT:$PATH"
}

ensure_agent_key() {
  if [[ -n "${SYNAPSE_AGENT_KEY:-}" || "$RUN_RUNTIME" != "true" ]]; then
    return
  fi
  ensure_python3
  echo "[e2e:sdk-parity] SYNAPSE_AGENT_KEY missing; issuing a temporary credential"
  SYNAPSE_AGENT_KEY="$(
    PYTHONPATH="$ROOT_DIR/python" python3 - <<'PY'
import os

from synapse_client import SynapseAuth
from synapse_client.exceptions import AuthenticationError

auth = SynapseAuth.from_private_key(
    os.environ["SYNAPSE_OWNER_PRIVATE_KEY"],
    environment=os.environ.get("SYNAPSE_ENV", "staging"),
    gateway_url=os.environ.get("SYNAPSE_GATEWAY_URL") or None,
)
try:
    result = auth.issue_credential(
        name=f"{os.environ.get('E2E_RUN_ID', 'sdk-parity')}-agent",
        max_calls=20,
        rpm=60,
        expires_in_sec=3600,
    )
    print(result.token)
except AuthenticationError:
    credentials = auth.list_active_credentials()
    if not credentials:
        raise
    print(auth._usable_token_for_credential(credentials[0]))
PY
  )"
  export SYNAPSE_AGENT_KEY
}

emit_owner_event_python() {
  ensure_python3
  PYTHONPATH="$ROOT_DIR/python" python3 - <<'PY'
import json
import os

from synapse_client import SynapseAuth
auth = SynapseAuth.from_private_key(
    os.environ["SYNAPSE_OWNER_PRIVATE_KEY"],
    environment=os.environ.get("SYNAPSE_ENV", "staging"),
    gateway_url=os.environ.get("SYNAPSE_GATEWAY_URL") or None,
)
token = auth.get_token()
balance = auth.get_balance()
usage = auth.get_usage_logs(limit=1)
guide = auth.get_registration_guide()
print(json.dumps({
    "language": "python",
    "scenario": "owner-provider-parity",
    "token": bool(token),
    "credential": bool(os.environ.get("SYNAPSE_AGENT_KEY")),
    "balanceType": type(balance).__name__,
    "usageLogs": len(usage.logs),
    "guideType": type(guide).__name__,
}))
PY
}

emit_owner_event_typescript() {
  ensure_node
  local smoke_file="$ROOT_DIR/typescript/.tmp-sdk-parity-owner.ts"
  cleanup_paths+=("$smoke_file")
  cat > "$smoke_file" <<'TS'
import { Wallet } from "ethers";
import { SynapseAuth } from "./src";

async function main() {
  const auth = SynapseAuth.fromWallet(new Wallet(process.env.SYNAPSE_OWNER_PRIVATE_KEY!), {
    environment: process.env.SYNAPSE_ENV ?? "staging",
    gatewayUrl: process.env.SYNAPSE_GATEWAY_URL || undefined,
  });
  const token = await auth.getToken();
  const balance = await auth.getBalance();
  const usage = await auth.getUsageLogs({ limit: 1 });
  const guide = await auth.getRegistrationGuide();
  console.log(JSON.stringify({
    language: "typescript",
    scenario: "owner-provider-parity",
    token: Boolean(token),
    credential: Boolean(process.env.SYNAPSE_AGENT_KEY),
    balanceType: typeof balance,
    usageLogs: usage.logs?.length ?? 0,
    guideType: typeof guide,
  }));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
TS
  (cd "$ROOT_DIR/typescript" && npm exec -- tsx .tmp-sdk-parity-owner.ts)
}

emit_owner_event_go() {
  ensure_go
  local smoke_dir="$ROOT_DIR/go/.tmp_sdk_parity_owner"
  cleanup_paths+=("$smoke_dir")
  mkdir -p "$smoke_dir"
  cat > "$smoke_dir/main.go" <<'GO'
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"

	synapse "github.com/cliff-personal/Synapse-Network-Sdk/go/synapse"
)

func main() {
	auth, err := synapse.NewAuthFromPrivateKey(os.Getenv("SYNAPSE_OWNER_PRIVATE_KEY"), synapse.AuthOptions{
		Environment: os.Getenv("SYNAPSE_ENV"),
		GatewayURL:  os.Getenv("SYNAPSE_GATEWAY_URL"),
	})
	if err != nil {
		panic(err)
	}
	ctx := context.Background()
	token, err := auth.GetToken(ctx)
	if err != nil {
		panic(err)
	}
	balance, err := auth.GetBalance(ctx)
	if err != nil {
		panic(err)
	}
	usage, err := auth.GetUsageLogs(ctx, 1)
	if err != nil {
		panic(err)
	}
	guide, err := auth.GetRegistrationGuide(ctx)
	if err != nil {
		panic(err)
	}
	event := map[string]any{
		"language": "go", "scenario": "owner-provider-parity", "token": token != "",
		"credential": os.Getenv("SYNAPSE_AGENT_KEY") != "", "balanceType": fmt.Sprintf("%T", balance),
		"usageLogs": len(usage.Logs), "guideSteps": len(guide.Steps),
	}
	payload, _ := json.Marshal(event)
	fmt.Println(string(payload))
}
GO
  go -C "$ROOT_DIR/go" run ./.tmp_sdk_parity_owner
}

emit_owner_event_java() {
  ensure_java
  local smoke_file="$ROOT_DIR/java/examples/src/main/java/ai/synapsenetwork/sdk/examples/ParityOwnerSmoke.java"
  cleanup_paths+=("$smoke_file")
  mkdir -p "$(dirname "$smoke_file")"
  cat > "$smoke_file" <<'JAVA'
package ai.synapsenetwork.sdk.examples;

import ai.synapsenetwork.sdk.SynapseAuth;

public final class ParityOwnerSmoke {
  public static void main(String[] args) {
    try {
      run();
    } catch (Throwable ex) {
      ex.printStackTrace();
      System.exit(1);
    }
  }

  private static void run() {
    SynapseAuth.Options options = new SynapseAuth.Options();
    options.environment = System.getenv().getOrDefault("SYNAPSE_ENV", "staging");
    options.gatewayUrl = System.getenv("SYNAPSE_GATEWAY_URL");
    SynapseAuth auth = SynapseAuth.fromPrivateKey(System.getenv("SYNAPSE_OWNER_PRIVATE_KEY"), options);
    String token = auth.getToken();
    var balance = auth.getBalance();
    var usage = auth.getUsageLogs(1);
    var guide = auth.getRegistrationGuide();
    System.out.println("{\"language\":\"java\",\"scenario\":\"owner-provider-parity\",\"token\":" + (!token.isBlank()) +
        ",\"credential\":" + (System.getenv("SYNAPSE_AGENT_KEY") != null && !System.getenv("SYNAPSE_AGENT_KEY").isBlank()) +
        ",\"balanceType\":\"" + balance.getClass().getSimpleName() +
        "\",\"usageLogs\":" + (usage.logs() == null ? 0 : usage.logs().size()) +
        ",\"guideSteps\":" + (guide.steps() == null ? 0 : guide.steps().size()) + "}");
  }
}
JAVA
  mvn -q -f java/examples/pom.xml compile org.codehaus.mojo:exec-maven-plugin:3.5.0:java \
    -Dexec.mainClass=ai.synapsenetwork.sdk.examples.ParityOwnerSmoke
}

emit_owner_event_dotnet() {
  ensure_dotnet
  local smoke_dir="$ROOT_DIR/dotnet/examples/owner-smoke"
  cleanup_paths+=("$smoke_dir")
  mkdir -p "$smoke_dir"
  cat > "$smoke_dir/owner-smoke.csproj" <<'XML'
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <ProjectReference Include="../../src/SynapseNetwork.Sdk/SynapseNetwork.Sdk.csproj" />
  </ItemGroup>
</Project>
XML
  cat > "$smoke_dir/Program.cs" <<'CS'
using System.Text.Json;
using SynapseNetwork.Sdk;

var auth = SynapseAuth.FromPrivateKey(
    Environment.GetEnvironmentVariable("SYNAPSE_OWNER_PRIVATE_KEY")!,
    new SynapseAuthOptions
    {
        Environment = Environment.GetEnvironmentVariable("SYNAPSE_ENV") ?? "staging",
        GatewayUrl = Environment.GetEnvironmentVariable("SYNAPSE_GATEWAY_URL"),
    });
var token = await auth.GetTokenAsync();
var balance = await auth.GetBalanceAsync();
var usage = await auth.GetUsageLogsAsync(1);
var guide = await auth.GetRegistrationGuideAsync();
Console.WriteLine(JsonSerializer.Serialize(new
{
    language = "dotnet",
    scenario = "owner-provider-parity",
    token = !string.IsNullOrWhiteSpace(token),
    credential = !string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("SYNAPSE_AGENT_KEY")),
    balanceType = balance.GetType().Name,
    usageLogs = usage.Logs?.Count ?? 0,
    guideSteps = guide.Steps?.Count ?? 0,
}));
CS
  dotnet run --project "$smoke_dir/owner-smoke.csproj" --configuration Release
}

run_owner_language() {
  local language="$1"
  echo "[e2e:sdk-parity] running $language owner/provider parity smoke"
  case "$language" in
    python)
      emit_owner_event_python
      ;;
    typescript|ts)
      emit_owner_event_typescript
      ;;
    go)
      emit_owner_event_go
      ;;
    java)
      emit_owner_event_java
      ;;
    dotnet)
      emit_owner_event_dotnet
      ;;
    *)
      echo "[e2e:sdk-parity] unsupported language: $language" >&2
      exit 2
      ;;
  esac
}

ensure_agent_key

IFS=',' read -r -a SELECTED_LANGUAGES <<< "$LANGUAGES"
for language in "${SELECTED_LANGUAGES[@]}"; do
  language="$(echo "$language" | tr -d '[:space:]')"
  if [[ -n "$language" ]]; then
    run_owner_language "$language"
  fi
done

if [[ "$RUN_RUNTIME" == "true" ]]; then
  runtime_args=(--languages "$LANGUAGES")
  if [[ "$INSTALL_MISSING" != "true" ]]; then
    runtime_args+=(--skip-install)
  fi
  bash scripts/e2e/sdk_wave1_local.sh "${runtime_args[@]}"
fi

echo "[e2e:sdk-parity] selected SDKs passed owner/provider parity smoke"
