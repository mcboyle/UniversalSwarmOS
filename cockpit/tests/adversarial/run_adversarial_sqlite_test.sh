#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

TEST_PORT="${TEST_PORT:-3457}"
export TEST_PORT

echo "=== Running Adversarial SQLite Concurrency Test Suite ==="

SERVER_LAUNCHED=0
if ! curl -s "http://localhost:${TEST_PORT}/api/nodes" >/dev/null 2>&1; then
  echo "[*] Launching background Next.js test server on port ${TEST_PORT}..."
  npx next start -p "$TEST_PORT" > /tmp/next_sqlite_test_server.log 2>&1 &
  SERVER_PID=$!
  SERVER_LAUNCHED=1

  cleanup() {
    if [ "$SERVER_LAUNCHED" -eq 1 ]; then
      echo "[*] Stopping Next.js test server (PID ${SERVER_PID})..."
      kill "$SERVER_PID" 2>/dev/null || true
      wait "$SERVER_PID" 2>/dev/null || true
    fi
  }
  trap cleanup EXIT INT TERM

  for i in {1..30}; do
    if curl -s "http://localhost:${TEST_PORT}/api/nodes" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
else
  echo "[*] Using existing Next.js server on port ${TEST_PORT}"
fi

node --experimental-strip-types tests/adversarial/adversarial_sqlite_concurrency.ts
