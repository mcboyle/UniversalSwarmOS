#!/usr/bin/env bash
# Fleet Rule 21 Airgap Interceptor
# Strictly forbids automated or interactive tooling from targeting test2 / 10.0.70.95 / bd-capture-test2
set -euo pipefail

FORBIDDEN_REGEX='10\.0\.70\.95|test2|wrk-test02|bd-capture-test2'

# 1. Inspect positional command-line arguments
for arg in "$@"; do
    if echo "$arg" | grep -E -i -q "$FORBIDDEN_REGEX"; then
        echo "REFUSED: Access to '$arg' refused by Fleet Rule 21 (10.0.70.95 / test2 is operator-only)." >&2
        exit 1
    fi
done

# 2. Inspect standard input if provided (piped or redirected tool invocation payload)
if [ ! -t 0 ]; then
    stdin_payload=$(cat)
    if [ -n "$stdin_payload" ]; then
        if echo "$stdin_payload" | grep -E -i -q "$FORBIDDEN_REGEX"; then
            echo "REFUSED: Tool payload targeting Rule 21 protected host (10.0.70.95 / test2 is operator-only)." >&2
            exit 1
        fi
    fi
fi

exit 0
