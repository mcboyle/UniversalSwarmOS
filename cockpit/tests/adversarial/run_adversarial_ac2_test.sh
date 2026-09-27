#!/usr/bin/env bash
# ==============================================================================
# tests/adversarial/run_adversarial_ac2_test.sh
# Master Adversarial Verification Harness for Acceptance Criterion 2:
# "UI renders a dedicated API Quota panel that distinguishes between
#  5-hour limits and weekly limits for Claude vs Gemini."
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

COLOR_RESET="\033[0m"
COLOR_GREEN="\033[1;32m"
COLOR_RED="\033[1;31m"
COLOR_CYAN="\033[1;36m"
COLOR_YELLOW="\033[1;33m"
COLOR_BOLD="\033[1m"

echo -e "${COLOR_CYAN}==============================================================================${COLOR_RESET}"
echo -e "${COLOR_BOLD}   AC2 ADVERSARIAL VERIFICATION HARNESS: API QUOTA PANEL & TELEMETRY${COLOR_RESET}"
echo -e "${COLOR_CYAN}==============================================================================${COLOR_RESET}"
echo -e "Project Root: ${PROJECT_ROOT}"
echo -e "Timestamp:    $(date -u +%FT%TZ)"
echo ""

TEST_PORT=3456
export TEST_PORT

# Check if Next.js server is already running on TEST_PORT
SERVER_LAUNCHED=0
if ! curl -s "http://localhost:${TEST_PORT}/api/nodes" >/dev/null 2>&1; then
  echo -e "${COLOR_YELLOW}[*] Starting background Next.js test server on port ${TEST_PORT}...${COLOR_RESET}"
  npx next start -p $TEST_PORT > /tmp/next_ac2_test_server.log 2>&1 &
  SERVER_PID=$!
  SERVER_LAUNCHED=1

  cleanup() {
    if [ "$SERVER_LAUNCHED" -eq 1 ]; then
      echo -e "\n${COLOR_YELLOW}[*] Stopping Next.js test server (PID ${SERVER_PID})...${COLOR_RESET}"
      kill "$SERVER_PID" 2>/dev/null || true
      wait "$SERVER_PID" 2>/dev/null || true
    fi
  }
  trap cleanup EXIT INT TERM

  for i in {1..30}; do
    if curl -s "http://localhost:${TEST_PORT}/api/quotas" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
else
  echo -e "${COLOR_GREEN}✓ Using existing Next.js server on port ${TEST_PORT}${COLOR_RESET}"
fi

echo -e "${COLOR_YELLOW}[RUNNING]${COLOR_RESET} Executing adversarial AC2 test suite..."
node --test --experimental-strip-types tests/adversarial/adversarial_ac2_quota.test.ts

echo -e "\n${COLOR_GREEN}==============================================================================${COLOR_RESET}"
echo -e "${COLOR_GREEN}${COLOR_BOLD}>>> AC2 ADVERSARIAL VERIFICATION PASSED (100% SUCCESSFUL) <<<${COLOR_RESET}"
echo -e "${COLOR_GREEN}==============================================================================${COLOR_RESET}"
