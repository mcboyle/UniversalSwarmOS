#!/bin/bash
# SessionStart: print the CACHED law-drift verdict and its AGE. Never sweeps -- see bd-lawsum.sh.
F=/home/mboyle/bd-persist/LAWSUM.status
if [ ! -f "$F" ]; then echo "bd-lawsum: COULD NOT LOOK -- no cached verdict at $F. LAW DRIFT IS UNMEASURED." >&2; exit 2; fi
A=$(( ( $(date +%s) - $(stat -c %Y "$F") ) / 60 ))
head -1 "$F" | sed "s/^# /bd-lawsum (cached ${A}m ago): /" >&2
grep -c ' DRIFT ' "$F" 2>/dev/null | grep -qv '^0$' && sed -n '2,6p' "$F" >&2
exit 0
