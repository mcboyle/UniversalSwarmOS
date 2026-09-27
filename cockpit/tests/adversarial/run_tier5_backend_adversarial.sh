#!/usr/bin/env bash
# ==============================================================================
# tests/adversarial/run_tier5_backend_adversarial.sh
# Runner for Tier 5 Backend Adversarial Test Suite
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=============================================================================="
echo " RUNNING TIER 5 BACKEND ADVERSARIAL TEST SUITE"
echo "=============================================================================="
echo "Timestamp: $(date -u +%FT%TZ)"
echo "Runner:    node --test --experimental-strip-types tests/adversarial/tier5_backend_adversarial.test.ts"
echo ""

node --test --experimental-strip-types tests/adversarial/tier5_backend_adversarial.test.ts

echo ""
echo ">>> TIER 5 BACKEND ADVERSARIAL SUITE PASSED SUCCESSFULLY <<<"
exit 0
