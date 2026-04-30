#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v mvn >/dev/null 2>&1; then
  echo "[ci:java] Maven not found; skipping local Java checks"
  exit 0
fi

echo "[ci:java] running Java SDK tests and package build"
mvn -q -f java/pom.xml test package
mvn -q -f java/examples/pom.xml compile

echo "[ci:java] Java SDK checks passed"
