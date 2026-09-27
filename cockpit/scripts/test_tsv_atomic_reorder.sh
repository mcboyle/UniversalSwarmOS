#!/usr/bin/env bash
# scripts/test_tsv_atomic_reorder.sh
# Verifies Acceptance Criterion AC4:
# "Interactive queue re-ordering successfully modifies ledger file without corrupting active dispatcher reads."
set -euo pipefail

TARGET_TSV="${1:-$(mktemp /tmp/test_dispatch_ledger_XXXXXX.tsv)}"
LOCK_FILE="${TARGET_TSV}.lock"
STOP_FILE=$(mktemp -u /tmp/test_stop_XXXXXX)
RESULT_FILE=$(mktemp /tmp/test_result_XXXXXX)

cleanup() {
  touch "$STOP_FILE" 2>/dev/null || true
  rm -f "$STOP_FILE" "$RESULT_FILE" "$LOCK_FILE" "${TARGET_TSV}"* 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Ensure STOP_FILE does not exist initially
rm -f "$STOP_FILE"

# Create initial test fixture with 10 tasks in DISPATCH-LEDGER format
cat << 'EOF' > "$TARGET_TSV"
2026-09-22T20:00:00Z	bd-worker-1	row1	dispatched	/path/1.md
2026-09-22T20:01:00Z	bd-worker-2	row2	dispatched	/path/2.md
2026-09-22T20:02:00Z	bd-worker-3	row3	dispatched	/path/3.md
2026-09-22T20:03:00Z	bd-worker-4	row4	dispatched	/path/4.md
2026-09-22T20:04:00Z	bd-worker-5	row5	dispatched	/path/5.md
2026-09-22T20:05:00Z	bd-worker-6	row6	dispatched	/path/6.md
2026-09-22T20:06:00Z	bd-worker-7	row7	dispatched	/path/7.md
2026-09-22T20:07:00Z	bd-worker-8	row8	dispatched	/path/8.md
2026-09-22T20:08:00Z	bd-worker-9	row9	dispatched	/path/9.md
2026-09-22T20:09:00Z	bd-worker-10	row10	dispatched	/path/10.md
EOF

INITIAL_COUNT=$(wc -l < "$TARGET_TSV")
echo "[*] Target TSV fixture created with $INITIAL_COUNT rows: $TARGET_TSV"
echo "[*] Launching high-frequency dispatcher readers (simulating bd-dispatch.sh awk loops)..."

# Background dispatcher reader loop (simulating live bd-dispatch.sh & bd-assign-idle.sh queries)
dispatcher_loop() {
  local reads=0
  local bad=0
  while [ ! -f "$STOP_FILE" ]; do
    # Simulates awk reading exactly 5 tab-separated fields
    local out
    out=$(awk -F'\t' 'NF!=5 {print NR, NF}' "$TARGET_TSV" 2>/dev/null || true)
    local lines
    lines=$(wc -l < "$TARGET_TSV" 2>/dev/null || echo 0)
    
    # Any row with != 5 columns or total lines != 10 indicates a torn/corrupted read
    if [ -n "$out" ] || [ "$lines" -ne 10 ]; then
      bad=$((bad + 1))
    fi
    reads=$((reads + 1))
  done
  echo "$reads $bad" > "$RESULT_FILE"
}

dispatcher_loop &
READER_PID=$!

# Brief pause to let background loop spin up
sleep 0.05

echo "[*] Performing 30 successive atomic queue re-orderings using TypeScript atomic-tsv..."

node -e "
import { mutateTsvAtomically, reorderDispatchLedgerRows } from './src/lib/atomic-tsv.ts';
const targetTsv = process.argv[1];

async function main() {
  const allRows = ['row1', 'row2', 'row3', 'row4', 'row5', 'row6', 'row7', 'row8', 'row9', 'row10'];
  for (let i = 1; i <= 30; i++) {
    const order = (i % 2 === 0)
      ? [...allRows].reverse()
      : [...allRows].sort(() => Math.random() - 0.5);
    await mutateTsvAtomically(
      targetTsv,
      (lines) => reorderDispatchLedgerRows(lines, order),
      5000
    );
    await new Promise((r) => setTimeout(r, 5));
  }
}
main().catch((err) => {
  console.error('Error during TSV reorder:', err);
  process.exit(1);
});
" "$TARGET_TSV"

touch "$STOP_FILE"
wait "$READER_PID" 2>/dev/null || true

TOTAL_READS=0
TORN_READS=0
if [ -f "$RESULT_FILE" ]; then
  read -r TOTAL_READS TORN_READS < "$RESULT_FILE"
fi

echo "[+] Total dispatcher reads during reorders: $TOTAL_READS"
echo "[+] Corrupted / torn reads detected: $TORN_READS"

FINAL_COUNT=$(wc -l < "$TARGET_TSV")
echo "[+] Final TSV row count: $FINAL_COUNT (expected 10)"

if [ "$TORN_READS" -gt 0 ]; then
  echo "[!] FAILED: Encountered $TORN_READS torn reads!" >&2
  exit 1
fi

if [ "$TOTAL_READS" -lt 50 ]; then
  echo "[!] FAILED: Too few reads executed ($TOTAL_READS)" >&2
  exit 1
fi

if [ "$FINAL_COUNT" -ne 10 ]; then
  echo "[!] FAILED: Ledger corrupted, final line count $FINAL_COUNT != 10" >&2
  exit 1
fi

echo "[+] PASSED: AC4 Verified - Interactive queue re-ordering successfully modified ledger file with zero torn reads across $TOTAL_READS dispatcher queries."
exit 0
