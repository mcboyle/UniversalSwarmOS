#!/usr/bin/env bash
# bd-verdict-write-hook.sh -- FLEET_RULE.md section 14, the write-time half.
# PostToolUse on Write|Edit. WARNS on a verdict written with an unroutable line 1 or filename.
#
# THE RULE: report the EXISTING population, change nothing; STOP THE POPULATION GROWING.
# Existing corpus, measured 2026-09-08: 24 of 47 live review verdicts carry `VERDICT: REFUTED`,
# a token no router parses, in files named VERDICT.md that the routers' glob (VERDICT-*.md, DASH
# REQUIRED) can never open. Invisible twice. This hook makes a NEW one visible at the moment it is
# written -- which is the only moment anyone is still looking.
#
# IT DOES NOT BLOCK. A hook that refuses a write can destroy an agent's work mid-task; the operator
# ruled report-and-gate, not refuse-and-lose. Exit 0 always; the signal is the message.
set -uo pipefail
IN=$(cat 2>/dev/null) || exit 0
F=$(printf '%s' "$IN" | python3 -c 'import json,sys
try: d=json.load(sys.stdin)
except Exception: print(""); raise SystemExit
ti=d.get("tool_input") or {}
print(ti.get("file_path") or ti.get("path") or "")' 2>/dev/null)
[ -n "$F" ] || exit 0

# ---- O1056 / FLEET_RULE 17+20: A LENS WRITES ONLY <cut>/.review/. ADDED 2026-09-20. ----------------
# A lens seat (role review-lite / review-shape / review-correctness; every such seat carries "review"
# in BD_SEAT) that writes ANY path inside a cut worktree outside that cut's .review/ has its verdict
# VOIDED and takes an O966 strike (O1056). A cut is the nearest ancestor holding a .git (dir or
# worktree file); bd-persist is not a repo, so handoff/compact/inbox writes never trip this.
# WARN ONLY, never refuse (rule 31b): the message is the signal; the refusal is the collect gate's.
# Runs BEFORE the verdict-file filter below because the offending write is by definition not a
# verdict file. Tag LENS-OUTSIDE-REVIEW is distinct so the log can be grepped for this class alone.
case "${BD_SEAT:-}" in
  *review*)
    D=$(dirname "$F"); ROOT=""
    while [ "$D" != "/" ] && [ -n "$D" ]; do
      if [ -e "$D/.git" ]; then ROOT="$D"; break; fi
      D=$(dirname "$D")
    done
    if [ -n "$ROOT" ]; then
      case "$F" in
        "$ROOT"/.review/*) ;;
        *)
          LMSG="LENS-OUTSIDE-REVIEW (O1056): seat '$BD_SEAT' wrote '$F' outside '$ROOT/.review/' -- a lens never edits a cut it judges (FLEET_RULE 17/20); this verdict is VOIDED at the gate and the fix routes to the fixer lane. Warn only (31b), the write stands."
          echo "VERDICTLINT-WARN $(date -u +%FT%TZ) $F :: $LMSG" >> "${BD_VERDICT_LINT_LOG:-/home/mboyle/bd-persist/verdictlint-warn.log}" 2>/dev/null
          echo "verdict-write WARN: $F"
          echo "  $LMSG" ;;
      esac
    fi ;;
  *worker*)
    # HB-worker-review-dir-warn (SYN-56): symmetric warning when a worker seat writes <cut>/.review/ (FLEET_RULE 20).
    AF=$(realpath -m -- "$F" 2>/dev/null || echo "$F")
    D=$(dirname "$AF"); ROOT=""
    while [ "$D" != "/" ] && [ "$D" != "." ] && [ -n "$D" ]; do
      if [ -e "$D/.git" ]; then ROOT="$D"; break; fi
      D=$(dirname "$D")
    done
    if [ -z "$ROOT" ] && [ -e "$D/.git" ]; then ROOT="$D"; fi
    if [ -n "$ROOT" ]; then
      case "$AF" in
        "$ROOT"/.review|"$ROOT"/.review/*|"$ROOT"/.review/|.review|.review/*|.review/)
          WMSG="WORKER-INSIDE-REVIEW (HB-worker-review-dir-warn): seat '$BD_SEAT' wrote '$F' under '$ROOT/.review/' -- a worker seat never writes review artifacts or verdicts (FLEET_RULE 20); review is owned by lens seats. Warn only (31b), the write stands."
          echo "VERDICTLINT-WARN $(date -u +%FT%TZ) $F :: $WMSG" >> "${BD_VERDICT_LINT_LOG:-/home/mboyle/bd-persist/verdictlint-warn.log}" 2>/dev/null
          echo "verdict-write WARN: $F"
          echo "  $WMSG" ;;
      esac
    fi ;;
esac

# ---- RULE 22: NO WORKTREE ADD/REMOVE IN TESTS (SYN-28 / O1084 / codex survey). ------
# Tests touching fleet git state by adding/removing canonical worktrees cause worktree explosion
# (2113 registered worktrees). Tests must use clone --shared or isolated scratch repositories.
case "$F" in
  */tests/test_*.py|tests/test_*.py|*/test_*.py|test_*.py|*/tests/test_*.sh|tests/test_*.sh|*/test_*.sh|test_*.sh)
    if [ -r "$F" ] && grep -qE 'worktree (add|remove)' "$F" 2>/dev/null; then
      WT_MSG="RULE-22-TEST-WORKTREE: test '$F' contains 'worktree add/remove' -- tests must use clone --shared or isolated scratch (Rule 22: no canonical worktree mutations in tests)"
      echo "VERDICTLINT-WARN $(date -u +%FT%TZ) $F :: $WT_MSG" >> "${BD_VERDICT_LINT_LOG:-/home/mboyle/bd-persist/verdictlint-warn.log}" 2>/dev/null
      echo "verdict-write WARN: $F"
      echo "  $WT_MSG"
    fi
    ;;
esac

case "$F" in *DONE.md|*/VERDICT*.md|*VERDICT-*.md) ;; *) exit 0 ;; esac
[ -r "$F" ] || exit 0

L1=$(head -1 "$F" 2>/dev/null)
B=$(basename "$F")
MSG=""

# ROUTABLE TOKENS, from CLAUDE.md's router table plus LANDED (section 13 of FLEET_RULE, this seat's
# terminal marker). Anything else is read by NOTHING and dead-ends the cut, however true its file is.
case "$L1" in
  'VERDICT: PATCH'|'VERDICT: BOARD'|'VERDICT: REFUTE'|'VERDICT: BOUNCE'|'VERDICT: LANDED') ;;
  'VERDICT: '*) MSG="line 1 is '$L1' -- NOT a routed token. Routed: PATCH BOARD REFUTE BOUNCE LANDED. REFUTED/PENDING-WRITE/PARTIAL/PASS are read by NOTHING." ;;
  *)            MSG="line 1 is not a verdict line at all: '$(printf '%s' "$L1" | cat -A | head -c 80)'" ;;
esac

# ---- RULE 16: THE TREE YOU JUDGED. ADDED 2026-09-09 ON OPERATOR RULING. --------------------------
# MEASURED 2026-09-08 across the open cut set: of 18 unrouted verdicts on 8 cuts, ** 17 RECORD NO
# TREE AT ALL and exactly 0 still match the cut. ** Rule 16 has been written for weeks and nothing
# enforced it, so the population grew until staleness became UNCHECKABLE for the whole set -- a
# BOARD nobody can prove is about the current object is not evidence, it is a guess with a token.
# WARN ONLY, never refuse: rule 31b -- a hook that blocks a write can destroy an agent's work
# mid-task, and the ruling was report-and-gate. The refusal belongs at the collect gate.
# Accepts either form the corpus already uses: a `git write-tree` index hash, or a PATCH-SHA256.
case "$L1" in
  'VERDICT: BOARD'|'VERDICT: REFUTE'|'VERDICT: BOUNCE')
    # H703 (O1266i): a TREE-only verdict dies on every rebase; PATCH-SHA256 (sha256 of `git diff --cached
    # --full-index <declared base>`) is the key that survives an identical patch on a new base. WARN only.
    if ! grep -qE 'PATCH-SHA256:[[:space:]]*[0-9a-f]{64}' "$F" 2>/dev/null; then
      MSG="$MSG${MSG:+ | }NO PATCH-SHA256 -- record 'PATCH-SHA256: <sha256 of git diff --cached --full-index <declared base>>' beside TREE (H703): a TREE-only verdict goes stale on every rebase of an identical patch"
    fi
    if ! grep -qiE '(write-tree|index tree|TREE HASH JUDGED|PATCH-SHA256)' "$F" 2>/dev/null; then
      MSG="$MSG${MSG:+ | }NO TREE RECORDED -- rule 16 wants the index tree you judged (git -C <wt> write-tree) or a PATCH-SHA256. Without one this verdict can NEVER be checked for staleness; 17 of 18 existing unrouted verdicts have this defect and not one of them still matches its cut."
    fi ;;
esac

# ---- SYN-2: VERDICTS SPLIT IN/OUT-SCOPE + NAME FIXTURE IDS (O1084) ----------------
case "$L1" in
  'VERDICT: REFUTE'|'VERDICT: BOUNCE')
    if ! grep -qiE '(in[-_ ]scope|out[-_ ]of[-_ ]scope|inscope|outofscope)' "$F" 2>/dev/null; then
      MSG="$MSG${MSG:+ | }NO SCOPE SPLIT (SYN-2) -- REFUTE/BOUNCE verdicts must split IN-SCOPE vs OUT-OF-SCOPE findings so minor/unpromised issues do not cause bounce churn."
    fi
    if ! grep -qE '\b[EU][0-9]+\b|\b[EU]-[0-9]+\b|\bfixtures?/[A-Za-z0-9_.-]+|\btest[-_][A-Za-z0-9_.-]+\b' "$F" 2>/dev/null; then
      MSG="$MSG${MSG:+ | }NO FIXTURE IDS NAMED (SYN-2) -- REFUTE/BOUNCE verdicts must name fixture IDs (e.g. E1/E2 or test fixture path) for structured in-place fix rounds."
    fi ;;
esac

# FILENAME. bd-autobounce-scan.sh finds '*/.review/VERDICT-*.md' -- THE DASH IS REQUIRED.
case "$B" in
  VERDICT.md) MSG="$MSG${MSG:+ | }filename is VERDICT.md with NO DASH -- bd-autobounce-scan globs VERDICT-*.md and can never open it. 47 such files already exist." ;;
esac

# ---- H615: THE DIRECTORY, NOT JUST THE NAME. ADDED 2026-09-21. ---------------------------------
# FLEET_RULE 35 routes from <cut>/.review/VERDICT-*.md ONLY. A verdict written ONE DIRECTORY UP has
# a perfect name, a routed token and a recorded tree, and is read by nothing.
# MEASURED 2026-09-21T16:45Z on harness-work/HB-F51: five live BOARDs sat at the cut root (H602,
# H604, H611 and two on H607). All four cuts read "PATCH, no verdict anywhere" in the PM census for
# 24-90 minutes and H611 was re-lensed by a second seat on that false reading.
# The O1056 block above could not catch these: it walks up for a `.git` ancestor, and an HB scratch
# cut under bd-persist/ has none, so ROOT was empty and the case never ran. This check identifies a
# cut by its OWN contents instead -- a directory holding DONE.md or a .review/ subdir is a cut.
# WARN ONLY (rule 31b); the refusal belongs at the collect gate.
case "$B" in
  VERDICT-*.md)
    VD=$(dirname "$(realpath -m -- "$F" 2>/dev/null || printf '%s' "$F")")
    if [ "$(basename "$VD")" != ".review" ] && { [ -f "$VD/DONE.md" ] || [ -d "$VD/.review" ]; }; then
      MSG="$MSG${MSG:+ | }VERDICT-AT-CUT-ROOT (H615): written to the cut root '$VD', not '$VD/.review/'. FLEET_RULE 35 globs <cut>/.review/VERDICT-*.md, so routing, bd-board-census and the collect gate will all read this cut as HAVING NO VERDICT. Correct path: $VD/.review/$B"
    fi ;;
esac

# ---- H611 / RULING O1160: THE FILENAME MUST CARRY THE SEAT. ADDED 2026-09-21. ------------------
# MEASURED: on rowsg8 two correctness lenses both wrote .review/VERDICT-correctness.md. B3-B's
# REFUTE landed first; B2-B's BOARD overwrote it 2.5 minutes later. The REFUTE is not in
# .review/superseded/ -- it was not superseded, it was DESTROYED -- and the cut went on to trainer
# pickup on the survivor. A second lens whose verdict the first can silently delete is not a
# second lens. O1160 names every verdict VERDICT-<kind>-<seat>.md, which two seats cannot collide
# on; bd-review-claim and bd-assign-lens.sh both issue that exact path now, and
# `bd-boardgate.sh --contested` reads the resulting pair as a disagreement instead of a boarding.
# This is the write-time half: it fires at the one moment the author is still looking.
# WARN ONLY, never refuse (rule 31b). The bare name still routes -- every glob is VERDICT-*.md --
# so nothing already written changes meaning; what changes is that the NEXT one is visible.
case "$B" in
  VERDICT-*-*.md) ;;                                   # already seat-tagged
  VERDICT-*.md)
    _VKIND=${B#VERDICT-}; _VKIND=${_VKIND%.md}
    _VSEAT=$(printf '%s' "${BD_SEAT:-<your-seat>}" | tr -c 'A-Za-z0-9._-' '-')
    MSG="$MSG${MSG:+ | }UNTAGGED VERDICT FILENAME (H611/O1160): '$B' carries no seat, so the next $_VKIND lens on this cut OVERWRITES it -- that is exactly how rowsg8's REFUTE was destroyed by a later BOARD. Write 'VERDICT-$_VKIND-$_VSEAT.md' instead (bd-review-claim prints the path as VERDICT-PATH when you claim)." ;;
esac

# ---- H139: PREVENT CITATION OF EPHEMERAL /tmp ARTIFACTS -------------------------
# A verdict that cites /tmp/... will lose its evidence when the session scratchpad expires.
# Warn immediately on write so the author rescues it to bd-persist before returning.
if grep -qE '/tmp/[A-Za-z0-9_./-]+' "$F" 2>/dev/null; then
  TMP_PATH=$(grep -oE '/tmp/[A-Za-z0-9_./-]+' "$F" | head -1)
  MSG="$MSG${MSG:+ | }EPHEMERAL /tmp CITATION (H139): verdict cites '$TMP_PATH'; rescue durable artifacts to bd-persist/ before returning verdict"
fi

if [ -n "$MSG" ]; then
  echo "VERDICTLINT-WARN $(date -u +%FT%TZ) $F :: $MSG" >> "${BD_VERDICT_LINT_LOG:-/home/mboyle/bd-persist/verdictlint-warn.log}" 2>/dev/null
  echo "verdict-write WARN: $F"
  echo "  $MSG"
fi
# ---- SYN-28: POST-VERDICT PRUNE ----------------------------------------------------
# Upon writing a valid terminal verdict (BOARD, REFUTE, BOUNCE) inside a cut's .review/,
# trigger post-verdict prune of ephemeral scratch directories for this cut and clean dead git worktree links.
case "$L1" in
  'VERDICT: BOARD'|'VERDICT: REFUTE'|'VERDICT: BOUNCE')
    case "$F" in
      */.review/VERDICT-*.md|*/.review/VERDICT*.md)
        CUT_DIR=$(dirname "$(dirname "$F")")
        REAPER="${BD_SCRATCH_REAPER_SH:-/home/mboyle/bd-persist/harness/bd-scratch-reaper.sh}"
        if [ -x "$REAPER" ] && [ -d "$CUT_DIR" ] && [ -e "$CUT_DIR/.git" ]; then
          "$REAPER" --prune-cut "$CUT_DIR" >/dev/null 2>&1 || true
        fi
        ;;
    esac
    ;;
esac

exit 0
