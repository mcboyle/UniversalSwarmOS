#!/usr/bin/env bash
# bd-argon-singleturn.sh: Spawns an Argon 4 worker with strict 1-turn limit and zero-waste configuration
set -euo pipefail

ID="${1:-}"
MODEL_TIER="${2:-gemini-4-argon-low}"
TASK_ARG="${3:-}"

if [[ -z "$ID" || -z "$TASK_ARG" ]]; then
  echo "Usage: $0 <CUT_ID> <MODEL_TIER> <TASK_FILE_OR_STRING>" >&2
  exit 1
fi

WORK_DIR="/home/mboyle/bd-local-wt/cut-${ID}"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

if [[ -f "$TASK_ARG" ]]; then
  PROMPT="$(cat "$TASK_ARG")"
else
  PROMPT="$TASK_ARG"
fi

# Append hard 1-turn stop constraint
FULL_PROMPT="${PROMPT}

CRITICAL EXECUTION DIRECTIVE:
You are operating under Rule 60 single-turn compound execution.
Execute the required inspection, surgical patch, static analysis (ruff/mypy), and verification tests in this SINGLE TURN.
Write DONE.md with VERDICT: PATCH when green.
Output '<STATUS> <path>' per Rule 74 and exit immediately. Do not ask questions or engage in multi-turn conversation."

echo "=== Spawning Argon 4 ($MODEL_TIER) for $ID in $WORK_DIR ==="
exec /home/mboyle/.local/bin/agy \
  --agent lean_worker \
  --model "$MODEL_TIER" \
  --disable-slash-commands \
  --dangerously-skip-permissions \
  -p "$FULL_PROMPT"
