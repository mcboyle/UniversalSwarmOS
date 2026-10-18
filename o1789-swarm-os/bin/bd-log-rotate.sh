#!/usr/bin/env bash
# bd-log-rotate.sh -- O1159: Auto-slice bloated context files
# O1365 (2026-09-24, operator interactive): review-claims.tsv and review.log legs REMOVED -- they are live state, not context
# (stripping RELEASED rows undid every claim release hourly; tailing review.log cut verdict lines bd-boardgate reads). say.log only.
set -euo pipefail
cd /home/mboyle/bd-persist
d=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p archives

[ -f say.log ] && { cp say.log archives/say.log.$d.bak; tail -n 50 say.log > say.tmp && mv say.tmp say.log; }

# Keep only the last 5 days of say.log backups (review-claims/review.log .bak files are kept: they are the O1365 restore source)
find archives/ -type f -name 'say.log.*.bak' -mtime +5 -delete 2>/dev/null || true
