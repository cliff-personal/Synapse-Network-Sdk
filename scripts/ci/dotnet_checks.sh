#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

LOCAL_DOTNET_DIR="${SYNAPSE_E2E_DOTNET_DIR:-$HOME/.synapse-network-sdk-e2e/dotnet}"
if ! command -v dotnet >/dev/null 2>&1 && [[ -x "$LOCAL_DOTNET_DIR/dotnet" ]]; then
  export DOTNET_ROOT="$LOCAL_DOTNET_DIR"
  export PATH="$DOTNET_ROOT:$PATH"
fi

if ! command -v dotnet >/dev/null 2>&1; then
  echo "[ci:dotnet] .NET SDK not found; skipping local .NET checks"
  exit 0
fi

echo "[ci:dotnet] running .NET SDK tests"
dotnet test dotnet/tests/SynapseNetwork.Sdk.Tests/SynapseNetwork.Sdk.Tests.csproj --configuration Release

echo "[ci:dotnet] .NET SDK checks passed"
