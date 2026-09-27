#!/usr/bin/env bash
# tests/adversarial/run_adversarial_tsv_test.sh
# Adversarial verification test for Milestone 1 AC4:
# "Interactive queue re-ordering successfully modifies the underlying ledger file
#  without corrupting active dispatcher reads."
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=========================================================================="
echo " ADVERSARIAL VERIFICATION HARNESS: DISPATCH-LEDGER CONCURRENCY & AWK INTEGRITY"
echo "=========================================================================="
echo "Target: $PROJECT_ROOT"
echo "Date:   $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

cd "$PROJECT_ROOT"

# Step 1: Run TypeScript Adversarial Harness
echo "[*] Step 1: Executing adversarial TSV mutation harness..."
node tests/adversarial/adversarial_tsv_harness.ts || {
  echo ""
  echo "[!] HARNESS FAILED AS PREDICTED: Defects detected under empirical adversarial stress."
  echo "    See above metrics for exact counts of column count mismatches (NF != 5) and accumulated blank lines."
  exit 1
}

echo "[+] Harness passed unexpectedly (no defects found)."
exit 0
