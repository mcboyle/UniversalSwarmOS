#!/bin/bash
# PostToolUse(Write|Edit) -> keep bd-persist/INDEX.tsv current. Never blocks: the index is a
# convenience and a failure to update it must not fail somebody's write. Silent on no-op.
python3 "$(dirname "${BASH_SOURCE[0]}")/bd-persist-index.py" 2>&1 >/dev/null | head -3 >&2
exit 0
