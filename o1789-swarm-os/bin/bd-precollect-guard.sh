#!/bin/bash
# READ-ONLY pre-collect check. Refuses LOUDLY where the collectors fail QUIETLY.
#
# WHY. Two silent-loss modes were measured on 2026-09-07 and neither produces an
# error from any existing tool:
#
#   1. bd-collect-gate.sh:102 is `[ "$V1" = "VERDICT: PATCH" ] || skip`. A LITERAL
#      string equality. row721's DONE.md line 1 reads
#        VERDICT: PATCH  (round 2 -- the three escapes ... are fixed)
#      which is not equal, so the cut is SKIPPED and nothing says so. The same is
#      true of every VERDICT: NO-CHANGE and VERDICT: BLOCKED line on the fleet.
#
#   2. No collector looks ABOVE the declared base. cx-scene .54 parks its work in a
#      WIP commit so bd-mutate gets a clean tree, then resets afterwards. Caught
#      mid-battery its index is EMPTY and `git diff BASE HEAD` is 8 paths, so a
#      collect returns an empty patch AND REPORTS SUCCESS.
#
#   3. A cut can be perfectly collectable AND BE THE WRONG GENERATION. cx-challenge
#      .149 passed checks 1-3 on 2026-09-07 while its 13 declared paths were
#      SET-IDENTICAL to cx-challenge-arm3.patch, round one of arm three, which a
#      newer round two (cx-challenge-arm3-r2.patch, +tests/test_v3_43_73_scrapling.py)
#      had already superseded. Collecting it would have re-landed the older round.
#
# WHAT THIS TOOL JUDGES, AND WHAT IT DOES NOT.
#   IT JUDGES: would a collect right now take what DONE.md declares (checks 1-3),
#   and is the declared PATH SET an older generation of a cut already carried
#   with a different path set (check 4).
#   IT DOES NOT JUDGE: whether the CONTENT is correct, whether the tests pass,
#   whether a lens boarded it, whether the row is the right row, or whether two
#   generations with the SAME path set differ in their diffs -- check 4 compares
#   PATH SETS ONLY and cannot see a content-only revision. An OK from this tool is
#   the absence of four specific silent-loss modes, NEVER a verdict that the cut is
#   right. It is also not a review.
#
# This tool changes nothing and touches no worktree. It answers one question --
# would a collect right now take what DONE.md declares? -- in four outcomes, never
# two: OK / NONPATCH / REFUSE / UNKNOWN. UNKNOWN is not permission.
#
#   usage: bd-precollect-guard.sh <ip|local> <worktree-path>
#   exit:  0 OK | 1 REFUSE | 2 usage | 4 UNKNOWN (could not measure) | 13 NONPATCH (non-patch disposition)
#   env:   BD_CARRY  carried-patch directory for the currency check (default
#                    /home/mboyle/bd-carry). Unreadable -> UNKNOWN, never OK.
#          BD_REVIEW_LOG prep-state log; unavailable evidence returns UNKNOWN (4).
#          BD_GENERIC_PATHS  space-separated paths that are additive shared lists and
#                    must not by themselves make two cuts the same family (default
#                    .github/workflows/ci.yml
#                    tests/test_v3_66_939_ci_gate_shards_cover_every_gate.py)
#          BD_GUARD_MAX_DONE_BYTES  max size for DONE.md before WARN (default 4096, rule 33c)
#          BD_GUARD_BASE  H719 pre-DONE run: with neither DONE.md nor DONE.md.draft in the cut, the tree
#                    checks run on this base (7-40 ASCII hex, else usage rc 2); the declaration checks refuse.
#   H719: with nothing at <cut>/DONE.md the guard judges <cut>/DONE.md.draft as the declaration (NOTE PRE-DONE),
#   so a worker runs it BEFORE the first DONE.md write (prep fires on that write; SYN-70 then refuses DONE edits).
#   A declaration that exists always wins; BD_GUARD_BASE never fills a missing BASE line; a STAGED draft refuses.
set -uo pipefail

if [ "${1:-}" = "--selftest" ]; then
  echo "=== Running bd-precollect-guard.sh built-in selftest (SYN-46) ==="
  python3 - <<'PY_GUARD_SELFTEST'
import os, re, sys

def run_linter(content: str, diff_text: str = "", filename: str = "test.sh"):
    lines = content.splitlines()
    added_lines = set()
    current_line = None
    for dline in diff_text.splitlines():
        if dline.startswith('@@ '):
            m = re.search(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', dline)
            if m:
                current_line = int(m.group(1))
        elif current_line is not None:
            if dline.startswith('+') and not dline.startswith('+++'):
                added_lines.add(current_line)
                current_line += 1
            elif dline.startswith('-') and not dline.startswith('---'):
                pass
            elif dline.startswith(' '):
                current_line += 1

    if not added_lines and not diff_text:
        added_lines = set(range(1, len(lines) + 1))

    re_subst_or_true = re.compile(
        r'(\$\([^)]*\|\|\s*true[^)]*\)'
        r'|\$\([^)]*\)\s*\|\|\s*true\b'
        r'|\(\([^)]*\|\|\s*true[^)]*\)\)'
        r'|\(\([^)]*\)\)\s*\|\|\s*true\b'
        r'|`[^`]*\|\|\s*true[^`]*`'
        r'|`[^`]*`\s*\|\|\s*true\b'
        r'|\|\|\s*true\b)'
    )
    re_rc_capture = re.compile(
        r'(?:'
        r'\b(?:local|declare|export|readonly)?\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*["\']?\$\?["\']?'
        r'|\[\s*["\']?\$\?["\']?'
        r'|\[\[\s*["\']?\$\?["\']?'
        r'|\btest\s+["\']?\$\?["\']?'
        r'|\bexit\s+["\']?\$\?["\']?'
        r'|\(\(\s*["\']?\$\?["\']?'
        r'|echo\s+[^#\n]*rc=\$\?'
        r')'
    )

    issues = []
    for i, raw_line in enumerate(lines):
        if re.search(r'#.*(?:rc-capture-ok|allow-rc-capture)', raw_line, re.I):
            continue
        parts = [p.strip() for p in re.split(r';|&&', raw_line) if p.strip()]
        same_line = False
        for idx in range(len(parts) - 1):
            p1 = parts[idx]
            p2 = parts[idx + 1]
            if re_subst_or_true.search(p1) and re_rc_capture.search(p2):
                if not added_lines or (i + 1) in added_lines:
                    issues.append((i + 1, "HB-shell-rc-capture-lint", f"flags '$(...) || true' followed by '$?' capture on same line: '{p1}; {p2}'"))
                same_line = True
                break
        if same_line:
            continue
        if re_subst_or_true.search(raw_line):
            for j in range(i + 1, min(i + 10, len(lines))):
                next_line = lines[j].strip()
                if not next_line or next_line.startswith('#'):
                    continue
                if re.search(r'#.*(?:rc-capture-ok|allow-rc-capture)', lines[j], re.I):
                    break
                if re_rc_capture.search(next_line):
                    if not added_lines or (j + 1) in added_lines or (i + 1) in added_lines:
                        issues.append((j + 1, "HB-shell-rc-capture-lint", f"flags '$(...) || true' at line {i+1} followed by '$?' capture at line {j+1}: '{next_line}'"))
                break

    func_depth = 0
    if_depth = 0
    case_depth = 0
    loop_depth = 0
    re_func_start = re.compile(r'^\s*(?:function\s+)?([a-zA-Z_0-9:-]+)\s*\(\s*\)\s*(\{)?')
    re_func_keyword = re.compile(r'^\s*function\s+([a-zA-Z_0-9:-]+)\s*(\{)?')
    re_exit_0 = re.compile(r'(?:^|[;&|\s(])exit\s+0(?:\b|[;)\s#]|$)')

    top_level_exits = []
    for i, raw_line in enumerate(lines):
        line_no = i + 1
        code = re.sub(r'#.*$', '', raw_line).strip()
        if not code:
            continue
        m_func = re_func_start.match(code) or re_func_keyword.match(code)
        if m_func and func_depth == 0:
            if m_func.group(2) or '{' in code:
                func_depth += code.count('{') - code.count('}')
            else:
                func_depth = 1
            continue
        if func_depth > 0:
            func_depth += code.count('{') - code.count('}')
            if func_depth <= 0:
                func_depth = 0
            continue
        if re.search(r'\bif\b', code) and not re.search(r'\bfi\b', code):
            if_depth += 1
        if re.search(r'\bcase\b', code) and not re.search(r'\besac\b', code):
            case_depth += 1
        if re.search(r'\b(for|while|until)\b', code) and not re.search(r'\bdone\b', code):
            loop_depth += 1
        if re_exit_0.search(code):
            is_cond = bool(
                if_depth > 0 or case_depth > 0 or loop_depth > 0 or
                re.search(r'(\|\||&&)', code) or
                re.search(r'\b(if|then|elif|else|case)\b', code) or
                re.search(r'[\(\)]', code) or
                re.search(r'\{.*exit\s+0.*\}', code)
            )
            top_level_exits.append((line_no, not is_cond, code))
        if re.search(r'\bfi\b', code) and not re.search(r'\bif\b', code):
            if_depth = max(0, if_depth - 1)
        if re.search(r'\besac\b', code) and not re.search(r'\bcase\b', code):
            case_depth = max(0, case_depth - 1)
        if re.search(r'\bdone\b', code) and not re.search(r'\b(for|while|until)\b', code):
            loop_depth = max(0, loop_depth - 1)

    re_trivial = re.compile(r'^\s*(?:#.*|fi|done|esac|;;|\}|\{|\s*)$')
    re_func_def = re.compile(r'^\s*(?:function\s+)?([a-zA-Z_0-9:-]+)\s*\(\s*\)\s*\{?')

    func_depth = 0
    for i, raw_line in enumerate(lines):
        line_no = i + 1
        code = re.sub(r'#.*$', '', raw_line).strip()
        m_func = re_func_start.match(code) or re_func_keyword.match(code)
        if m_func and func_depth == 0:
            if m_func.group(2) or '{' in code:
                func_depth += code.count('{') - code.count('}')
            else:
                func_depth = 1
            continue
        if func_depth > 0:
            func_depth += code.count('{') - code.count('}')
            if func_depth <= 0:
                func_depth = 0
            continue
        if line_no not in added_lines:
            continue
        stripped = raw_line.strip()
        if re_trivial.match(stripped) or re_func_def.match(stripped) or re_exit_0.search(stripped):
            continue
        if re.search(r'#.*(?:early-exit-ok|allow-after-exit|post-exit-ok)', raw_line, re.I):
            continue
        if os.environ.get("BD_EARLY_EXIT_OK") == "1":
            continue

        prior_uncond = [e for e in top_level_exits if e[0] < line_no and e[1]]
        prior_cond = [e for e in top_level_exits if e[0] < line_no and not e[1]]
        if prior_uncond:
            first_uncond = prior_uncond[0]
            issues.append((line_no, "HB-early-exit-ordering-lint", f"dead code placed after unconditional exit at line {first_uncond[0]} ('{first_uncond[2]}'): '{stripped}'"))
        elif prior_cond:
            first_cond = prior_cond[0]
            n_guards = len(prior_cond)
            issues.append((line_no, "HB-early-exit-ordering-lint", f"new logic placed after {n_guards} 'exit 0' guard(s) (first at line {first_cond[0]}: '{first_cond[2]}'): '{stripped}'"))

    return issues

passed = 0
failed = 0
def check(name, condition, details=""):
    global passed, failed
    if condition:
        print(f"  OK: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name} ({details})")
        failed += 1

# Controls
s1 = "out=$(pytest 2>&1 || true)\nrc=$?"
i1 = run_linter(s1)
check("positive control rc-capture (multi-line)", any(r == "HB-shell-rc-capture-lint" for _, r, _ in i1), f"got: {i1}")

s2 = "cmd_out=$((pytest tests/ 2>&1) || true); rc=$?"
i2 = run_linter(s2)
check("positive control rc-capture (same-line)", any(r == "HB-shell-rc-capture-lint" for _, r, _ in i2), f"got: {i2}")

s4 = "out=$(pytest 2>&1)\nrc=$?"
i4 = run_linter(s4)
check("negative control: honest exit capture passes", len(i4) == 0, f"got: {i4}")

s7 = "#!/bin/bash\n[ -s \"$Q\" ] || exit 0\nbash bd-load-gate.sh || { echo \"LOAD-HOLD\"; exit 0; }\nreconcile_done"
diff7 = "@@ -3,0 +4,1 @@\n+reconcile_done\n"
i7 = run_linter(s7, diff7)
check("positive control early-exit ordering (A10-A defect)", any(r == "HB-early-exit-ordering-lint" for _, r, _ in i7), f"got: {i7}")

s8 = "#!/bin/bash\nreconcile_done\n[ -s \"$Q\" ] || exit 0\nbash bd-load-gate.sh || { echo \"LOAD-HOLD\"; exit 0; }"
diff8 = "@@ -1,0 +2,1 @@\n+reconcile_done\n"
i8 = run_linter(s8, diff8)
check("negative control early-exit ordering (unconditional logic placed first)", len(i8) == 0, f"got: {i8}")

s9 = "#!/bin/bash\n[ -s \"$Q\" ] || exit 0\ndispatch_seat \"$seat\" # early-exit-ok"
diff9 = "@@ -2,0 +3,1 @@\n+dispatch_seat \"$seat\" # early-exit-ok\n"
i9 = run_linter(s9, diff9)
check("annotation bypass: # early-exit-ok passes", len(i9) == 0, f"got: {i9}")

s10 = "#!/bin/bash\necho \"done\"\nexit 0\ncleanup_residue"
diff10 = "@@ -3,0 +4,1 @@\n+cleanup_residue\n"
i10 = run_linter(s10, diff10)
check("positive control dead code after unconditional exit", any("dead code" in m for _, _, m in i10), f"got: {i10}")

print(f"Selftest results: {passed} passed, {failed} failed")
if failed > 0:
    sys.exit(1)
print("SELFTEST PASS (rc-capture + early-exit ordering lints verified with positive controls)")
sys.exit(0)
PY_GUARD_SELFTEST
  exit $?
fi

IP=${1:?usage: bd-precollect-guard.sh <ip|local> <worktree-path>}
WT=${2:?usage: bd-precollect-guard.sh <ip|local> <worktree-path>}
GB=${BD_GUARD_BASE:-}   # H719: it crosses into the ssh command line below, so only a sha is accepted
# The class is spelled out: under en_US.UTF-8, [0-9a-f] also collates in letters like á and fullwidth digits.
if [ -n "$GB" ] && ! [[ $GB =~ ^[0123456789abcdef]{7,40}$ ]]; then echo "usage: BD_GUARD_BASE must be a 7-40 hex sha, got [$GB]" >&2; exit 2; fi

# One remote probe, one round trip. `ssh -n` or it eats the caller's loop stdin.
probe() {
  local script='
    set -uo pipefail
    wt="$1"; gb="${2:-}"
    [ -e "$wt/.git" ] || { echo "NOGIT"; exit 0; }
    df="$wt/DONE.md"   # anything at DONE.md (a directory, a dangling link) is the declaration, unreadable -> NODONE
    if [ -e "$df" ] || [ -L "$df" ]; then [ -f "$df" ] || { echo "NODONE"; exit 0; }
    else df="$wt/DONE.md.draft"; if [ ! -f "$df" ]; then [ -n "$gb" ] || { echo "NODONE"; exit 0; }; df=/dev/null; fi; fi
    printf "DONEFILE\t%s\n" "$df"
    printf "L1\t%s\n" "$(head -1 "$df")"
    printf "DONESZ\t%s\n" "$(wc -c < "$df" 2>/dev/null | tr -d "[:space:]")"
    sed "s/^/DONELINE\t/" "$df"
    b=$(grep -iE "^[[:space:]]*BASE[]:[:space:]]" "$df" | grep -oE "\\b[0-9a-f]{7,40}\\b" | head -1)
    [ "$df" = /dev/null ] && b="$gb"
    printf "BASE\t%s\n" "$b"
    printf "HEAD\t%s\n" "$(git -C "$wt" rev-parse HEAD 2>/dev/null)"
    printf "IDX\t%s\n"  "$(git -C "$wt" diff --cached --name-only 2>/dev/null | wc -l)"
    ref_arg=""
    if [ -n "$b" ] && git -C "$wt" rev-parse --verify -q "$b^{commit}" >/dev/null 2>&1; then
      printf "PATHSREF\tbase\n"
      git -C "$wt" diff --cached --name-only "$b" 2>/dev/null | sed "s/^/PATH\t/"
      git -C "$wt" diff --cached --name-only --diff-filter=A "$b" -- "tests/test_*.py" 2>/dev/null | sed "s/^/NEWTEST\t/"
      ref_arg="$b"
    else
      printf "PATHSREF\tHEAD\n"
      git -C "$wt" diff --cached --name-only 2>/dev/null | sed "s/^/PATH\t/"
      git -C "$wt" diff --cached --name-only --diff-filter=A -- "tests/test_*.py" 2>/dev/null | sed "s/^/NEWTEST\t/"
    fi
    # SYN-34: Enumerate newly added production modules and audit callers
    for np in $(git -C "$wt" diff --cached --name-only --diff-filter=A $ref_arg -- "bulk_downloader/*.py" "bulk_downloader/**/*.py" 2>/dev/null); do
      [ "$(basename "$np")" = "__init__.py" ] && continue
      printf "NEWPROD\t%s\n" "$np"
      stem=$(basename "$np" .py)
      callers=$(git -C "$wt" grep -n -E "\b$stem\b" -- "bulk_downloader/" ":(exclude)$np" 2>/dev/null | wc -l)
      printf "PRODCALLERS\t%s\t%s\n" "$np" "$callers"
    done
    # SYN-34: Probe live import graph gate delta
    if [ -f "$wt/tools/decomp/import_graph_gate.py" ]; then
      py="$wt/venv/bin/python"
      [ -x "$py" ] || py="/home/mboyle/BulkDownloader/venv/bin/python"
      if [ -x "$py" ]; then
        "$py" "$wt/tools/decomp/import_graph_gate.py" --check 2>&1 | sed "s/^/IGOUT\t/"
      fi
    fi
    # Preserve Git path bytes for the namespace check; quoted display paths are not identities.
    nsref=HEAD
    if [ -n "$b" ] && git -C "$wt" rev-parse --verify -q "$b^{commit}" >/dev/null 2>&1; then nsref="$b"; fi
    if topdirs0=$(git -C "$wt" ls-tree -d -z --name-only "$nsref" 2>/dev/null | base64 -w0) &&
       staged0=$(git -C "$wt" diff --cached --name-only -z "$nsref" 2>/dev/null | base64 -w0); then
      printf "NAMESPACE\tOK\nTOPDIR0\t%s\nSTAGED0\t%s\n" "$topdirs0" "$staged0"
    else
      printf "NAMESPACE\tUNKNOWN\n"
    fi
    printf "DIRTY\t%s\n" "$(git -C "$wt" status --porcelain 2>/dev/null | grep -cE "^(AM|MM|RM|AD|MD| M| D)")"
    printf "ENV_INDEX_LEAK\t%s\n" "${GIT_INDEX_FILE:-}"
    # H96: a harness marker COMMITTED into the branch is in the index but in no diff against its own base.
    tm=$(git -C "$wt" ls-files --cached -- DONE.md DONE.md.draft .task-id .launch.sh .codex-launch.sh .onboard.md ".gate-retry-*.DONE.md" RESUME_STATE.md NOTE.md RULING.md 2>/dev/null)
    printf "TRACKEDPROBE\t%s\n" "$?"
    printf "%s\n" "$tm" | grep . | sed "s/^/TRACKEDMARK\t/"
    # R3: Probe completed-cut side-file sprawl (RESUME_STATE.md, stray NOTE.md, RULING.md)
    sf=""
    for f in RESUME_STATE.md NOTE.md RULING.md; do
      if [ -e "$wt/$f" ]; then
        sf="${sf:+$sf
}$f"
      fi
    done
    gt_sf=$(git -C "$wt" ls-files --cached --others -- "RESUME_STATE.md" "NOTE.md" "RULING.md" "**/RESUME_STATE.md" "**/NOTE.md" "**/RULING.md" 2>/dev/null || true)
    if [ -n "$gt_sf" ]; then
      sf="${sf:+$sf
}$gt_sf"
    fi
    if [ -n "$sf" ]; then
      printf "%s\n" "$sf" | sort -u | grep . | sed "s/^/SIDEFILE\t/"
    fi
    # O730: the POST-BOARD form is a valid line too; it must reach its branch below, not read as MISSING (row753 07:2xZ).
    printf "SELFMUT\t%s\n" "$(grep -m1 -E "^SELFMUT: (POST-BOARD \\(O730\\)$|[0-9]+( of [0-9]+)? seams mutated, [0-9]+ escaped, spec=)" "$df")"
  '
  if [ "$IP" = local ]; then bash -c "$script" _ "$WT" "$GB" 2>/dev/null
  else ssh -o ConnectTimeout=8 -o BatchMode=yes "$IP" "bash -s -- '$WT' '$GB'" <<<"$script" 2>/dev/null
  fi
}
OUT=$(probe) || true
[ -n "$OUT" ] || { echo "UNKNOWN $IP $WT -- probe returned nothing; COULD NOT LOOK, not clean"; exit 4; }
case "$OUT" in
  NOGIT*)  echo "UNKNOWN $IP $WT -- not a git worktree"; exit 4;;
  NODONE*) echo "UNKNOWN $IP $WT -- no DONE.md; nothing has been declared"; exit 4;;
esac
get() { awk -F'\t' -v k="$1" '$1==k{print $2}' <<<"$OUT"; }
L1=$(get L1); BASE=$(get BASE); HEAD=$(get HEAD); IDX=$(get IDX); DIRTY=$(get DIRTY)
DONESZ=$(get DONESZ)
ENV_INDEX_LEAK=$(get ENV_INDEX_LEAK)
PATHSREF=$(get PATHSREF)
PATHS=$(awk -F'\t' '$1=="PATH"{print $2}' <<<"$OUT" | sort -u)
IS_LANDED_BY_PROP=$(awk -F'\t' '$1=="DONELINE" && $0 ~ /LANDED-BY-PROPERTY:|SUPERSEDED-ON-MAIN:/{print 1; exit}' <<<"$OUT")
# H719: the declaration judged below is DONE.md, else DONE.md.draft (pre-DONE), else none (BD_GUARD_BASE run).
DONEFILE=$(get DONEFILE); DONE_PATH=${DONEFILE:-$WT/DONE.md}
case "$DONEFILE" in
  */DONE.md.draft) echo "NOTE   $IP $WT -- PRE-DONE (H719): no DONE.md yet; judged DONE.md.draft as the declaration. The result holds for DONE.md only if the draft becomes DONE.md unchanged apart from this output.";;
  /dev/null) echo "NOTE   $IP $WT -- PRE-DONE (H719): no DONE.md or DONE.md.draft; tree checks run on BD_GUARD_BASE=$BASE. Declaration checks (line 1, RED, SELFMUT) refuse until one exists.";;
esac
if [ -n "$GB" ] && [ "$DONEFILE" != /dev/null ] && [ "${GB:0:7}" != "${BASE:0:7}" ]; then
  echo "WARN   $IP $WT -- BD_GUARD_BASE=$GB ignored: $(basename "$DONE_PATH") exists and names BASE ${BASE:-<none>}; a collect takes the declaration, and a missing BASE line is never filled from the environment."
fi
rc=0
BASE_CLAUSE="declared base is current main"   # E3: overridden below if a STALE BASE NOTE fires (O734.3 clean-merge)

# H719: a STAGED DONE.md.draft rides `git diff --cached <base>` (the PATCH-SHA256 object) into the collected patch;
# a declaration is never part of the object it declares.
if printf '%s\n' "$PATHS" | grep -qxF DONE.md.draft; then
  echo "REFUSE $IP $WT -- DONE.md.draft is STAGED (H719): the declaration would ride the collected object."
  echo "FIX COMMAND: git -C \"$WT\" rm --cached DONE.md.draft"
  rc=1
fi

# RC66 Check: GIT_INDEX_FILE leak (H555)
if [ -n "${ENV_INDEX_LEAK:-}" ] || [ -n "${GIT_INDEX_FILE:-}" ]; then
  echo "REFUSE $IP $WT -- GIT_INDEX_FILE is exported in environment: ${ENV_INDEX_LEAK:-$GIT_INDEX_FILE} (H555 index leak / rc 66)."
  echo "FIX COMMAND: unset GIT_INDEX_FILE"
  rc=1
fi

# CHECK 1 -- line 1 verdict classification and zero-staged-path disposition (SYN-33)
norm_v1() {  # <line> -> normalised verdict line (CR, BOM, surrounding whitespace stripped, as in bd-collect-gate.sh:143)
  local v=${1//$'\r'/}
  v=${v#$'\xef\xbb\xbf'}
  v=${v#"${v%%[![:space:]]*}"}
  printf '%s' "${v%"${v##*[![:space:]]}"}"
}
L1_NORM=$(norm_v1 "$L1")
L1_NORM_UPPER=$(printf '%s' "$L1_NORM" | tr '[:lower:]' '[:upper:]')

is_nonpatch=0
nonpatch_outcome=""
case "$L1_NORM_UPPER" in
  "VERDICT: REFUTED"*|"VERDICT: REFUTE"*|"REFUTED"*|"REFUTE:"*|"REFUTE"*)
    is_nonpatch=1; nonpatch_outcome="REFUTED" ;;
  "VERDICT: BLOCKED"*|"BLOCKED"*)
    is_nonpatch=1; nonpatch_outcome="BLOCKED" ;;
  "VERDICT: NO-CHANGE"*|"NO-CHANGE"*)
    is_nonpatch=1; nonpatch_outcome="NO-CHANGE" ;;
esac

if [ "$is_nonpatch" -eq 1 ]; then
  # Non-patch verdicts with 0 staged paths need explicit disposition (NONPATCH, exit 13), not REFUSE (SYN-33).
  if [ "${IDX:-0}" -gt 0 ] || [ -n "$PATHS" ]; then
    echo "REFUSE $IP $WT -- non-patch verdict [$L1_NORM] with $IDX staged path(s); non-patch cut must have 0 staged paths."
    exit 1
  fi
  if [ "${DIRTY:-0}" -gt 0 ]; then
    echo "REFUSE $IP $WT -- $DIRTY path(s) differ between the index and the worktree (AM/MM/RM/ D)."
    echo "        every collector takes the WORKTREE, so what arrives is not what DONE.md declares."
    exit 1
  fi
  if [ -n "$BASE" ] && [ -n "$HEAD" ] && [ "$HEAD" != "$BASE" ]; then
    echo "REFUSE $IP $WT -- HEAD is not the declared base. Non-patch cut has commits above base."
    exit 1
  fi
  echo "NONPATCH $IP $WT -- non-patch verdict [$L1_NORM] with 0 staged paths ($nonpatch_outcome); valid non-patch disposition"
  exit 13
fi

if [ "$L1" != "VERDICT: PATCH" ]; then
  echo "REFUSE $IP $WT -- line 1 is not the exact token bd-collect-gate:102 compares against."
  echo "        got:  [$L1]"
  echo "        want: [VERDICT: PATCH]   (literal equality; a trailing note is a mismatch)"
  echo "        a collector would SKIP this cut and say nothing."
  rc=1
elif [ -n "$IS_LANDED_BY_PROP" ] && { [ "${IDX:-0}" -gt 0 ] || [ -n "$PATHS" ]; }; then
  echo "REFUSE $IP $WT -- LANDED-BY-PROPERTY declared with $IDX staged path(s); LANDED-BY-PROPERTY cut must have 0 staged paths (O987)."
  rc=1
elif [ "${IDX:-0}" -eq 0 ] && [ -z "$IS_LANDED_BY_PROP" ]; then
  # Already-landed cuts with 0 staged paths need explicit disposition, not REFUSE and never auto-LANDED (SYN-33).
  echo "REFUSE $IP $WT -- 0 staged paths with VERDICT: PATCH lacks LANDED-BY-PROPERTY marker (O987); cuts with 0 staged paths need explicit disposition, never auto-LANDED."
  echo "FIX COMMAND: git -C \"$WT\" add <files>   (stage inspected changes before DONE; 0-path / rc 66)"
  echo "        OR if changes are already landed on base / property proven without edits:"
  echo "        declare 'VERDICT: LANDED' on line 1 with marker 'LANDED-BY-PROPERTY (O987)',"
  echo "        or place harness candidate at harness-work/FIX/<slug>/ per O1066."
  rc=1
fi

# Row812: a PATCH DONE.md must carry a replayable RED command: a `RED[ COMMAND]:` field, or a RED heading/section
# whose next 15 lines hold a runner+target command (wrapped commands allowed). Outcome prose/counts/log paths are not one.
RED_LINES=$(awk -F'\t' '$1=="DONELINE"{sub(/^[^\t]*\t/, ""); print}' <<<"$OUT")
RED_COMMAND=$(python3 - "$RED_LINES" <<'PY_RED'
import re, shlex, sys
SECTION_WINDOW = 15
def _command(value, explicit):
    value = value.strip()
    if value.startswith("`") and "`" in value[1:]:
        value = value[1:value.index("`", 1)]
    value = re.sub(r"^\$\s+", "", value)
    try:
        args = shlex.split(value.rstrip("\\"))
    except ValueError:
        return False
    if args and args[0] == "cd" and "&&" in args:
        args = args[args.index("&&") + 1:]
    while args and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", args[0]):
        args.pop(0)
    if args and args[0] == "env":
        args.pop(0)
        while args and args[0].startswith("-"):
            option = args.pop(0)
            if option in ("-u", "--unset") and args:
                args.pop(0)
    while args and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", args[0]):
        args.pop(0)
    if not args or not re.match(r"^[A-Za-z_./]", args[0]):
        return False
    name = args[0].rsplit("/", 1)[-1]
    legacy_command = re.fullmatch(r"python[0-9.]*|pytest|bash|sh|node|npm|npx|bd-[\w.-]+", name)
    legacy_target = any(arg.startswith("-") or "/" in arg or "::" in arg
                        or re.search(r"\.(?:py|[cm]?js|[jt]sx?|sh)$", arg) for arg in args[1:])
    legacy_short = (name == "pytest" and len(args) == 1
                    or name == "npm" and args[1:] in (["test"], ["run", "test"]))
    return bool(explicit or legacy_short or (legacy_command and legacy_target))
def _field_or_section(lines):
    for i, line in enumerate(lines):
        m = re.match(r"^\s*RED([\s_-]+COMMAND)?\s*:\s*(.+)$", line, re.I)
        if m and _command(m[2], bool(m[1])):
            return line
        # A RED section: `## RED ...` / `RED -- ...` / `RED (` heading, command within the window.
        if re.match(r"^\s*(#+\s*)?RED\b(?!\s*:)", line):
            for cand in lines[i + 1:i + 1 + SECTION_WINDOW]:
                if re.match(r"^\s*#", cand) and not re.match(r"^\s*#!", cand):
                    break
                body = re.sub(r"^\s*(COMMAND\s*:\s*)?", "", cand)
                body = body.strip("` ")
                if _command(body, False):
                    return cand
    return None

WINDOW = 15
RUNNER = re.compile(r"(?:^|[\s`'\"(=])(?:\S*/)?(?:venv/bin/python|python3?|pytest|bash|sh|npm|npx|node|bd-worker-precut\.sh|bd-band(?:-\w+)?|bd-precut|bd-mutate|bd-selfmut-floor\.sh|bd-[\w.-]+\.sh)(?=[\s`'\"]|$)")
TARGET = re.compile(r"tests?/[\w./-]+|\.py\b|::|-m pytest|(?:^|\s)-q\b|-k ")
def _runner_and_target(win):
    """A runner token and a target token within two consecutive lines (wrapped commands)."""
    for j, line in enumerate(win):
        pair = line + " " + (win[j + 1] if j + 1 < len(win) else "")
        if RUNNER.search(line) and TARGET.search(pair):
            return line
    return None
def find(lines):
    hit = _field_or_section(lines)
    if hit:
        return hit
    for i, line in enumerate(lines):
        if re.match(r"^\s*(#+\s*)?RED\b", line) or re.match(r"^\s*RED([\s_-]+COMMAND)?\s*:", line, re.I):
            win = [line]
            for cand in lines[i + 1:i + 1 + WINDOW]:
                if re.match(r"^\s*#", cand) and not re.match(r"^\s*#!", cand):
                    break
                win.append(cand)
            hit = _runner_and_target(win)
            if hit:
                return hit
    return None
hit = find(sys.argv[1].splitlines())
if hit:
    print(hit)
PY_RED
)
if [ "$L1" = "VERDICT: PATCH" ] && [ -z "$RED_COMMAND" ] && [ -z "$IS_LANDED_BY_PROP" ]; then
  echo "REFUSE $IP $WT -- RED COMMAND MISSING. DONE.md must name the failing command on a RED COMMAND: line (legacy RED: test commands are accepted)."
  echo "        counts, log paths and outcome prose do not declare a replayable command."
  rc=1
fi

# Rule 33c: DONE.md must not exceed 4KB (4096 bytes). Warn so the writer trims before a lens reads it.
DONE_MAX_BYTES=${BD_GUARD_MAX_DONE_BYTES:-4096}
DONE_MAX_BYTES=$(tr -dc '0-9' <<<"$DONE_MAX_BYTES")
DONE_MAX_BYTES=${DONE_MAX_BYTES:-4096}
if [ -z "$DONESZ" ] && [ "$IP" = local ] && [ -f "$DONE_PATH" ]; then
  DONESZ=$(wc -c < "$DONE_PATH" 2>/dev/null | tr -d '[:space:]')
fi
DONESZ=$(tr -dc '0-9' <<<"${DONESZ:-0}")
DONESZ=${DONESZ:-0}
if [ "$DONESZ" -gt "$DONE_MAX_BYTES" ]; then
  echo "WARN   $IP $WT -- OVERSIZED DONE.md: ${DONESZ} bytes exceeds rule-33c 4KB limit (${DONE_MAX_BYTES} bytes); trim before a lens reads it."
fi

# CHECK 2 -- work parked above the declared base is invisible to every collector.
if [ -z "$BASE" ]; then
  echo "UNKNOWN $IP $WT -- DONE.md declares no parseable BASE: <sha>; the base cannot be checked."
  echo "        a path count with no named base is not a measurement. Treating as COULD NOT LOOK."
  [ $rc -eq 0 ] && rc=4
elif [ -z "$HEAD" ]; then
  echo "UNKNOWN $IP $WT -- git rev-parse HEAD did not answer"; [ $rc -eq 0 ] && rc=4
else
  case "$HEAD" in
    "$BASE"*) : ;;
    *) # Direction matters and the two directions are OPPOSITE problems.
       # HEAD AHEAD of base  -> work may be parked in commits; the index can be empty.
       # HEAD BEHIND base    -> the index is the truth and vs-HEAD readings render PHANTOMS.
       #                        That is the shape that cost us a whole cut on cx-logincap.
       dir=UNKNOWN
       if [ "$IP" = local ]; then
         git -C "$WT" merge-base --is-ancestor "$HEAD" "$BASE" 2>/dev/null && dir=BEHIND
         [ "$dir" = UNKNOWN ] && { git -C "$WT" merge-base --is-ancestor "$BASE" "$HEAD" 2>/dev/null && dir=AHEAD; }
       else
         ssh -n -o ConnectTimeout=8 "$IP" "git -C '$WT' merge-base --is-ancestor '$HEAD' '$BASE'" 2>/dev/null && dir=BEHIND
         [ "$dir" = UNKNOWN ] && { ssh -n -o ConnectTimeout=8 "$IP" "git -C '$WT' merge-base --is-ancestor '$BASE' '$HEAD'" 2>/dev/null && dir=AHEAD; }
       fi
       echo "REFUSE $IP $WT -- HEAD is not the declared base. Direction: HEAD is $dir the base."
       echo "        declared BASE $BASE"
       echo "        actual   HEAD $HEAD"
       echo "        index holds $IDX staged path(s)."
       case "$dir" in
         AHEAD)   # H82: NAME the above-base path count (acceptance: "refuses with the above-base path count named").
                  # FIXED-BY-LENS (bd-briefauthor-A, H82): a failed git/ssh must read UNKNOWN, never 0 (FLEET_RULE 6).
                  if [ "$IP" = local ]; then above_out=$(git -C "$WT" diff --name-only "$BASE" "$HEAD" 2>/dev/null) && above=$(printf '%s\n' "$above_out" | grep -c . || true) || above=UNKNOWN
                  else above_out=$(ssh -n -o ConnectTimeout=8 "$IP" "git -C '$WT' diff --name-only '$BASE' '$HEAD'" 2>/dev/null) && above=$(printf '%s\n' "$above_out" | grep -c . || true) || above=UNKNOWN; fi
                  echo "        above-base path(s): ${above:-UNKNOWN} (git diff --name-only $BASE $HEAD) vs $IDX staged -- parked in commits, invisible to a collect"
                  echo "        HEAD AHEAD: work may be parked in commits above the base. If the staged"
                  echo "        count is 0 a collect takes NOTHING and reports success. Bring HEAD back"
                  echo "        to the base with the work STAGED before collecting."
                  echo "FIX COMMAND: git -C \"$WT\" reset --soft $BASE   (brings HEAD to base with work staged; clears rc 66)";;
         BEHIND)  echo "        HEAD BEHIND: this can be CORRECT. The index is the truth here; measure with"
                  echo "        git diff --cached $BASE and NEVER bare, because a vs-HEAD reading renders"
                  echo "        commits that landed in between as PHANTOM additions. Collect only after a"
                  echo "        human has read the declared path count against that base."
                  echo "FIX COMMAND: git -C \"$WT\" reset --soft $BASE   (aligns HEAD to declared base)";;
         *)       echo "        Direction COULD NOT BE MEASURED -- ancestry unresolved, which is UNKNOWN,"
                  echo "        not permission. Deepen history or resolve the objects before collecting."
                  echo "FIX COMMAND: git -C \"$WT\" fetch origin && git -C \"$WT\" rebase $BASE";;
       esac
       rc=1;;
  esac
fi

# CHECK 3 -- the collector takes the WORKTREE. Staged-and-modified is not what was declared.
if [ "${DIRTY:-0}" -gt 0 ]; then
  echo "REFUSE $IP $WT -- $DIRTY path(s) differ between the index and the worktree (AM/MM/RM/ D)."
  echo "        every collector takes the WORKTREE, so what arrives is not what DONE.md declares."
  echo "FIX COMMAND: git -C \"$WT\" add -u   (stage unstaged tracked modifications; clears rc 66 dirty worktree)"
  rc=1
fi

# CHECK 4 -- CURRENCY. Collectable is not the same question as current.
# A carried patch in BD_CARRY is a generation that has already been taken. If this
# worktree's declared path set is EXACTLY an OLDER carried generation, and a NEWER
# carried patch of the SAME FAMILY declares a DIFFERENT set, this tree is a
# superseded round and collecting it re-lands the older work.
# FAMILY IS MEASURED, NOT LISTED. It was "shares at least one non-generic path",
# with generic being a hand-maintained pair of names -- and on 2026-09-07 03:2xZ that
# shape produced a FALSE REFUSE on a live train: cut/redaction shared exactly one
# unlisted path with cx-logincap, bulk_downloader/app.py, which most cuts in this repo
# touch. One hub path silently joined two unrelated cuts and the tree was called a
# superseded generation while it was on its way to the bar. A hand-maintained list of
# the paths that do not count is the fail-open A7 forbids: the list cannot know about
# the next hub, and nothing errors when it is stale.
# SO HUB-NESS IS DERIVED FROM THE CARRIED CORPUS ITSELF, every run:
#   HUB   a path carried by >= BD_HUB_PCT percent of the carried patches (default 50).
#         Measured here: ci.yml and the shard test appear in 23 of 27 (85%) and are
#         hubs without anyone naming them; app.py appears in 6 of 27 (22%) and is not.
#   FAMILY  at least BD_FAMILY_MIN (default 2) SHARED NON-HUB paths. Two cuts that
#         share exactly one ordinary file are not the same work, and app.py is exactly
#         that case. The true positives share twelve.
# BD_GENERIC_PATHS is still honoured and is now a FLOOR added to the measured hubs,
# not the whole definition, so an operator can still force a known-additive path.
CARRY=${BD_CARRY:-/home/mboyle/bd-carry}
GENERIC=${BD_GENERIC_PATHS:-".github/workflows/ci.yml tests/test_v3_66_939_ci_gate_shards_cover_every_gate.py"}
HUB_PCT=${BD_HUB_PCT:-50}
FAMILY_MIN=${BD_FAMILY_MIN:-2}
if [ -z "$PATHS" ]; then
  if [ -n "$IS_LANDED_BY_PROP" ]; then
    echo "NOTE   $IP $WT -- LANDED-BY-PROPERTY (O987: 0 staged paths, accepted without a lens)"
  else
    echo "UNKNOWN $IP $WT -- the declared path set could not be read; currency UNMEASURED."
    [ $rc -eq 0 ] && rc=4
  fi
elif [ ! -d "$CARRY" ] || [ ! -r "$CARRY" ]; then
  echo "UNKNOWN $IP $WT -- carried-patch directory $CARRY is missing or unreadable."
  echo "        currency COULD NOT BE MEASURED, which is not permission to collect."
  [ $rc -eq 0 ] && rc=4
else
  MINE=$(printf '%s\n' "$PATHS")
  KEY=$(printf '%s\n' "$MINE" | md5sum | cut -d' ' -f1)
  # MEASURE THE HUBS from the carried corpus before comparing anything to anything.
  NPATCH=$(ls "$CARRY"/*.patch 2>/dev/null | wc -l)
  HUBS=""
  if [ "$NPATCH" -gt 0 ]; then
    HUBS=$(for pf in "$CARRY"/*.patch; do
             [ -f "$pf" ] || continue
             grep '^diff --git ' "$pf" | sed 's|.* b/||' | sort -u
           done | sort | uniq -c | awk -v n="$NPATCH" -v pct="$HUB_PCT" \
             '$1 * 100 >= n * pct { $1=""; sub(/^ +/,""); print }')
  fi
  # the operator floor is ADDED to what was measured, never a substitute for it
  HUBS=$(printf '%s\n%s\n' "$HUBS" "$(printf '%s\n' $GENERIC)" | grep -v '^$' | sort -u)
  NONGEN=$(printf '%s\n' "$MINE" | grep -vxF -f <(printf '%s\n' "$HUBS") || true)
  exact_older=""; newer_diff=""; scanned=0
  for pf in "$CARRY"/*.patch; do
    [ -f "$pf" ] || continue
    scanned=$((scanned+1))
    pset=$(grep '^diff --git ' "$pf" | sed 's|.* b/||' | sort -u)
    [ -n "$pset" ] || continue
    shared=$(printf '%s\n' "$pset" | grep -xF -f <(printf '%s\n' "$NONGEN") 2>/dev/null | wc -l)
    # FAMILY needs more than one ordinary file in common. One shared hub-ish path is
    # a coincidence of a busy repo, not evidence that two cuts are the same work.
    [ "$shared" -ge "$FAMILY_MIN" ] || continue   # different family, says nothing about us
    pkey=$(printf '%s\n' "$pset" | md5sum | cut -d' ' -f1)
    if [ "$pkey" = "$KEY" ]; then exact_older="$exact_older $pf"
    else newer_diff="$newer_diff $pf"
    fi
  done
  if [ "$scanned" -eq 0 ]; then
    echo "UNKNOWN $IP $WT -- $CARRY holds no *.patch to compare against; currency UNMEASURED."
    [ $rc -eq 0 ] && rc=4
  elif [ -n "$exact_older" ] && [ -n "$newer_diff" ]; then
    # is any different-set family member NEWER than the identical one?
    newest_same=0
    for pf in $exact_older; do t=$(stat -c %Y "$pf"); [ "$t" -gt "$newest_same" ] && newest_same=$t; done
    sup=""
    for pf in $newer_diff; do t=$(stat -c %Y "$pf"); [ "$t" -gt "$newest_same" ] && sup="$sup $pf"; done
    if [ -n "$sup" ]; then
      echo "REFUSE $IP $WT -- SUPERSEDED GENERATION. Collectable, but not the current round."
      echo "        this tree declares $(printf '%s\n' "$MINE" | wc -l) path(s), measured against $PATHSREF."
      echo "        that path set is IDENTICAL to already-carried:"
      for pf in $exact_older; do echo "          $pf   ($(date -d @$(stat -c %Y "$pf") -u +%H:%MZ))"; done
      echo "        family = $FAMILY_MIN+ shared non-hub path(s); $(printf '%s\n' "$HUBS" | grep -c . ) hub path(s) measured across $NPATCH carried patch(es) at >= ${HUB_PCT}%."
      echo "        and a LATER carried patch of the same family declares a DIFFERENT set:"
      for pf in $sup; do
        echo "          $pf   ($(date -d @$(stat -c %Y "$pf") -u +%H:%MZ))"
        d=$(comm -13 <(printf '%s\n' "$MINE") <(grep '^diff --git ' "$pf" | sed 's|.* b/||' | sort -u) | tr '\n' ' ')
        [ -n "$d" ] && echo "            it adds: $d"
      done
      echo "        collecting this tree would re-land the earlier round. Take the later one,"
      echo "        or have the owner say in DONE.md which generation is current."
      rc=1
    fi
  fi
fi

# CHECK 5 -- IS THE DECLARED BASE STILL THE TIP? 2026-09-14T06:2xZ bd-integrator-B, under O387.
# WHY THIS WAS MISSING AND WHY IT MATTERS. CHECK 4 is headed "CURRENCY", but the currency it
# measures is against carried PATH SETS in $CARRY -- a superseded GENERATION of the same cut.
# The only ancestry test in this file before today was CHECK 2's, and that compares HEAD to the
# cut's OWN declared base, inside the worktree. NOTHING asked whether that base is still main.
# So a cut whose base was the tip yesterday passed this guard forever.
# MEASURED, 2026-09-14T06:0xZ: row784b (/home/mboyle/bd-local-wt/row784-A6-20260913) declared
# BASE 900c08fc (v3.66.1538) and got a clean OK, while main was 66178294 (v3.66.1539). Diffed
# against its declared base it is 3 paths; diffed against CURRENT main it is TEN, because its
# index still carries 1538's release trio, register and generated artifacts. Collected and
# merged as a tree it would have REVERTED v3.66.1539. That is a silent regression the collector
# cannot see, which is exactly the class of thing a pre-collect guard exists to catch.
# THE REFERENCE IS THE CANONICAL REPO ON THIS HOST, not the worktree's own remote-tracking ref,
# which on a detached build worktree can be arbitrarily stale and would make the check lie.
# COULD NOT LOOK IS NOT PERMISSION (FLEET_RULE 6): if the reference or the base cannot be
# resolved, this is UNKNOWN (rc 4), never a pass.
CANON=${BD_GUARD_CANON:-/home/mboyle/BulkDownloader}
if [ $rc -eq 0 ]; then
  if [ ! -e "$CANON/.git" ]; then
    echo "UNKNOWN $IP $WT -- canonical repo $CANON is not a git repo; base currency UNMEASURED."
    rc=4
  else
    MAIN=$(git -C "$CANON" rev-parse --verify -q main^{commit} 2>/dev/null)
    # ROW precollect-guard-base-check: CANON's OWN main can itself be behind a remote-tracking
    # ref it has already fetched -- something can land on the real remote (origin/gitea) without
    # this host's checkout catching up. Before trusting local main as "the tip", walk every
    # refs/remotes/*/main it has the objects for. E1 (review, 2026-09-20T19:18Z): the first cut
    # of this fix downgraded a MEASURABLE case to UNKNOWN (rc=4) and skipped the BASE comparison
    # entirely -- "COULD NOT LOOK" only when you truly could not, and here the remote tip is
    # right there in CANON's own object store. FLIP: when local main is strictly behind a fetched
    # remote-tracking main, walk the CHAIN to the furthest ahead one reachable this way and use
    # THAT as MAIN for the comparison below (a NOTE, not a refusal by itself); fall through to the
    # existing BASE-vs-MAIN NOTE/REFUSE logic measuring against the truer tip. Diverging remotes
    # (neither an ancestor of the other) cannot be resolved to one tip -- that stays rc=4.
    if [ -n "$MAIN" ]; then
      _lag_ref=""; _diverged=0
      for _ref in $(git -C "$CANON" for-each-ref --format='%(refname)' 'refs/remotes/*/main' 2>/dev/null); do
        _rsha=$(git -C "$CANON" rev-parse --verify -q "${_ref}^{commit}" 2>/dev/null) || continue
        [ "$_rsha" = "$MAIN" ] && continue
        if git -C "$CANON" merge-base --is-ancestor "$MAIN" "$_rsha" 2>/dev/null; then
          if [ -z "$_lag_ref" ]; then
            _lag_ref=$_ref; _lag_sha=$_rsha
          elif git -C "$CANON" merge-base --is-ancestor "$_lag_sha" "$_rsha" 2>/dev/null; then
            _lag_ref=$_ref; _lag_sha=$_rsha   # a further-ahead ref supersedes a closer one
          elif ! git -C "$CANON" merge-base --is-ancestor "$_rsha" "$_lag_sha" 2>/dev/null; then
            _diverged=1   # neither is an ancestor of the other: ambiguous, cannot pick one tip
          fi
        fi
      done
      if [ "$_diverged" = 1 ]; then
        echo "UNKNOWN $IP $WT -- CANON $CANON local main $MAIN is behind more than one fetched remote-tracking main and they DIVERGE from each other; base currency UNMEASURED (this host's checkout is stale and ambiguous)."
        rc=4
      elif [ -n "$_lag_ref" ]; then
        echo "NOTE   $IP $WT -- CANON $CANON local main $MAIN is BEHIND its own fetched $_lag_ref $_lag_sha by $(git -C "$CANON" rev-list --count "${MAIN}..${_lag_sha}") commit(s); this host's checkout is stale, measuring base currency against $_lag_ref instead."
        MAIN=$_lag_sha
      fi
    fi
    if [ "$rc" != 0 ]; then :
    elif [ -z "$MAIN" ]; then
      echo "UNKNOWN $IP $WT -- cannot resolve main in $CANON; base currency UNMEASURED."
      rc=4
    elif ! git -C "$CANON" rev-parse --verify -q "${BASE}^{commit}" >/dev/null 2>&1; then
      echo "UNKNOWN $IP $WT -- declared base $BASE is not a commit in $CANON; base currency UNMEASURED."
      rc=4
    elif [ "$(git -C "$CANON" rev-parse "${BASE}^{commit}")" != "$MAIN" ] \
         && git -C "$CANON" merge-base --is-ancestor "$BASE" "$MAIN" 2>/dev/null; then
      # O734.3 arm: a stale base whose INDEX merges CLEAN onto main is carried by the train (not re-prepped): NOTE, not REFUSE.
      # Probe: dangling commit of the index tree on $BASE, merge-tree'd against $MAIN (git >= 2.38); rc 0 clean, 1 conflicts, else could not probe.
      _o734_t=$(git -C "$WT" write-tree 2>/dev/null); _o734_rc=99
      if [ "$IP" = local ] && [ -n "$_o734_t" ]; then
        _o734_c=$(git -C "$WT" commit-tree "$_o734_t" -p "$BASE" -m "o734-probe" 2>/dev/null) \
          && { git -C "$WT" merge-tree --write-tree "$MAIN" "$_o734_c" >/dev/null 2>&1; _o734_rc=$?; }
      fi
      if [ "$_o734_rc" = 0 ]; then
        echo "NOTE   $IP $WT -- STALE BASE $BASE is BEHIND main $MAIN by $(git -C "$CANON" rev-list --count "${BASE}..${MAIN}") commit(s) but the index merges CLEAN onto main (merge-tree rc=0): the train carries the rebase (O734.3). Not a refusal."
        # E3 (review 2026-09-20T19:37Z): the final OK line's fixed phrase "declared base is
        # current main" was printed even right after THIS line said BASE is behind main -- a
        # record that contradicts the line above it. Make the OK line's base clause honest.
        BASE_CLAUSE="declared base is BEHIND the tip by $(git -C "$CANON" rev-list --count "${BASE}..${MAIN}") commit(s) (clean merge, O734.3)"
      else
      echo "REFUSE $IP $WT -- STALE BASE. Declared base $BASE is BEHIND main $MAIN by $(git -C "$CANON" rev-list --count "${BASE}..${MAIN}") commit(s). (O734.3 probe: merge-tree rc=$_o734_rc, not clean or could not probe)"
      # COUNT OR SAY YOU COULD NOT COUNT. `git diff | wc -l` reports 0 both when the diff is
      # empty and when git ERRORED (e.g. $MAIN is not an object in THIS worktree's store --
      # which happens whenever the canonical reference is a different repo). A silent 0 here
      # would understate the damage in the very message that exists to show it. Same trap class
      # as the 0-byte `gh ... --log` that reads as "the log does not say so" (H345).
      _pg_cnt() {
        _c=$(git -C "$WT" diff --cached --name-only "$1" 2>/dev/null) || { echo UNMEASURED; return; }
        git -C "$WT" rev-parse --verify -q "$1^{commit}" >/dev/null 2>&1 || { echo UNMEASURED; return; }
        printf '%s' "$_c" | grep -c . 
      }
      echo "        against its own base this tree touches $(_pg_cnt "$BASE") path(s);"
      echo "        against CURRENT main it touches $(_pg_cnt "$MAIN") path(s)."
      echo "        (UNMEASURED means that commit is not in this worktree's object store -- fetch it to see the count.)"
      echo "        the extra paths are whatever main changed since, so collecting this tree would"
      echo "        re-land the older versions of them. REBASE onto $MAIN, re-run the precut, and"
      echo "        re-record INDEX TREE / PATCH-SHA256 (rule 16) -- all three change on the rebase."
      echo "FIX COMMAND: git -C \"$WT\" fetch origin main && git -C \"$WT\" rebase $MAIN   (O912 pre-done rebase; then re-record BASE and write-tree in DONE.md)"
      rc=1
      fi
    elif [ "$(git -C "$CANON" rev-parse "${BASE}^{commit}")" != "$MAIN" ]; then
      echo "REFUSE $IP $WT -- BASE NOT ON MAIN. Declared base $BASE is not an ancestor of main $MAIN."
      rc=1
    fi
  fi
fi

# CHECK 6 -- SELF-MUTATION BEFORE DONE (H489, operator 2026-09-14 20:1xZ). 7 of 11 REFUTEs that day (775c 4/6, 775d 3/6,
# 806 3/12, 665, 741, ...) were lens-written mutants escaping the worker's own tests: the floor ran for the first time
# AFTER the offer. DONE.md must carry the line harness/bd-selfmut-floor.sh prints --
#   SELFMUT: <n> seams mutated, <k> escaped, spec=<path>
# -- with k=0, and the spec must be THE CENSUS OF THIS INDEX (bd-brief-seams -> bd-seamcensus over the staged diff,
# numstat-derived), not a hand-picked list: this check re-derives that census here and requires the mutant label
# sets to be EQUAL, and every mutant to sit in a staged path (H480: a seam is (staged path, function)).
# A remote worktree cannot be censused from here: UNKNOWN (rc 4), never OK. Nothing is mutated by this check.
SMN="not censused (O930 gate off)"   # read by the OK line under set -u; the gate below overrides it when on
if [ "${BD_SELFMUT_GATE:-off}" = on ]; then   # O930 (operator 2026-09-19): pre-mutation gate RETIRED (68 lines, 0 escapes, 46 refusals)
SMLINE=$(get SELFMUT)
SMH=/home/mboyle/bd-persist/harness
# O730: a T1/T2 cut may carry `SELFMUT: POST-BOARD (O730)` -- the battery runs after the board. Tier from the row's newest brief.
o730_tier(){ local row b; row=$(basename "$WT" | sed -E 's/^rows?-?//' | grep -oE '^[0-9]+') || return 1
  b=$(ls -t "${BD_BRIEF_DIR:-/home/mboyle/bd-codex-briefs}"/ROW"$row"-*.md 2>/dev/null | head -1); [ -n "$b" ] || return 1
  grep -oE 'TIER:[[:space:]]*T[0-3]' "$b" | tail -1 | grep -m1 -oE 'T[0-3]'; }   # O736: TIER: anywhere on a line; the LAST one wins (an addendum re-tiers a brief whose header still says the old tier: row753 07:2xZ)
if [ "$SMLINE" = "SELFMUT: POST-BOARD (O730)" ]; then
  O730T=$(o730_tier || echo none)
  SMN="POST-BOARD (O730, tier=$O730T)"   # read by the OK line; no census yet (set -u: "SMN: unbound variable", row753 07:2xZ)
  case "$O730T" in T1|T2) echo "PASS   $IP $WT -- SELFMUT POST-BOARD accepted (O730, tier=$O730T from newest brief); battery runs after the board.";;
    *) echo "REFUSE $IP $WT -- SELFMUT: POST-BOARD (O730) is only valid for T1/T2; newest brief tier=$O730T. Run bd-selfmut-floor.sh."; rc=1;; esac
elif [ -z "$SMLINE" ] && [ "$IP" = local ] && SMUNK=$(grep -m1 -E '^SELFMUT: UNKNOWN \((budget|census)' "$DONE_PATH" 2>/dev/null) && [ -n "$SMUNK" ]; then
  # O733.3: over-max / empty census is UNMEASURED, not a refusal, locally as it already is remotely; the lens does the census.
  # H558: carry the language denominator. A ts/js surface the python-only census cannot see is named in the reason.
  TSJS_N=$(git -C "$WT" diff --cached --name-only 2>/dev/null | grep -cE '\.(ts|tsx|js|jsx|mjs|cjs)$')
  [ "${TSJS_N:-0}" -gt 0 ] && LANGNOTE="; ts,js: $TSJS_N changed file(s) COULD NOT LOOK (census is python/shell-only, H558)" || LANGNOTE=""
  echo "UNKNOWN $IP $WT -- [$SMUNK] accepted as UNMEASURED (O733.3: seams over BD_REVIEW_SELFMUT_MAXSEAMS or empty census); the review lens censuses$LANGNOTE."
  [ $rc -eq 0 ] && rc=4
elif [ -z "$SMLINE" ]; then
  if [ -n "$IS_LANDED_BY_PROP" ]; then
    SMN="LANDED-BY-PROPERTY (0 staged, accepted without a lens)"
    echo "NOTE   $IP $WT -- SELFMUT: 0 staged paths (LANDED-BY-PROPERTY O987, accepted without a lens)"
  else
    echo "REFUSE $IP $WT -- SELFMUT LINE MISSING (H489). DONE.md has no \`SELFMUT: <n> seams mutated, <k> escaped, spec=<path>\` line."
    echo "        run: bash $SMH/bd-selfmut-floor.sh $WT   and paste its last line into DONE.md (k must be 0)."
    rc=1
  fi
elif [ "$IP" != local ]; then
  echo "UNKNOWN $IP $WT -- SELFMUT line present [$SMLINE] but the spec cannot be censused on a remote host; coverage UNMEASURED."
  [ $rc -eq 0 ] && rc=4
else
  # H515: a CAPPED census reports "n of N seams mutated" (n = emitted = len(spec)); the
  # optional " of N" is informational, so \1 (n) stays the count CHECK 6 compares to len(spec).
  SMN=$(sed -E 's/^SELFMUT: ([0-9]+)( of [0-9]+)? seams mutated, ([0-9]+) escaped, spec=(.*)$/\1/' <<<"$SMLINE")
  SMK=$(sed -E 's/^SELFMUT: ([0-9]+)( of [0-9]+)? seams mutated, ([0-9]+) escaped, spec=(.*)$/\3/' <<<"$SMLINE")
  SMS=$(sed -E 's/^SELFMUT: ([0-9]+)( of [0-9]+)? seams mutated, ([0-9]+) escaped, spec=(.*)$/\4/' <<<"$SMLINE" | awk '{print $1}')
  case "$SMS" in /*) ;; *) SMS="$WT/$SMS";; esac
  SMREP="$(dirname "$SMS")/report.json"
  if [ "$SMK" != 0 ]; then
    echo "REFUSE $IP $WT -- SELF-MUTATION: $SMK escaped of $SMN (H489). A mutant the patch's own tests do not catch is a lens REFUTE waiting to happen."
    [ -f "$SMREP" ] && python3 -c 'import json,sys; [print("        ESCAPED " + (r.get("label") or "?")) for r in json.load(open(sys.argv[1])).get("rows", []) if r.get("verdict") == "ESCAPED"]' "$SMREP" 2>/dev/null
    rc=1
  elif [ ! -f "$SMS" ]; then
    echo "REFUSE $IP $WT -- SELFMUT spec $SMS does not exist (H489); the line names a battery that cannot be checked."
    rc=1
  elif [ ! -x "$SMH/bd-brief-seams" ] || [ ! -x "$SMH/bd-seamcensus" ]; then
    echo "UNKNOWN $IP $WT -- SELFMUT coverage UNMEASURED: $SMH/bd-brief-seams or bd-seamcensus is not executable."
    [ $rc -eq 0 ] && rc=4
  else
    SMT=$(mktemp -d /tmp/bd-guard-selfmut.XXXXXX); : > "$SMT/seams.md"
    if BD_SEAMCENSUS="$SMH/bd-seamcensus" BD_BRIEF_SEAMS_CAP="${BD_REVIEW_SELFMUT_SITECAP:-400}" "$SMH/bd-brief-seams" "$WT" "$SMT/seams.md" > "$SMT/seams.log" 2>&1 \
       && "$SMH/bd-seamcensus" --work "$WT" --seams "$SMT/seams.md" --spec-out "$SMT/spec.json" --max-seams "${BD_REVIEW_SELFMUT_MAXSEAMS:-40}" > "$SMT/census.json" 2> "$SMT/census.log"; then
      SMV=$(printf '%s\n' "$PATHS" > "$SMT/paths.txt"; python3 - "$SMT/census.json" "$SMT/spec.json" "$SMS" "$SMN" "$SMT/paths.txt" <<'PY' 2>&1
import json, sys
census = json.load(open(sys.argv[1])); want = {m["label"] for m in json.load(open(sys.argv[2]))}
spec = json.load(open(sys.argv[3])); have = {m.get("label") for m in spec}
staged = {l.strip() for l in open(sys.argv[5]) if l.strip()}
prod = census.get("functions_prod", [])
bad = []
if prod and not have: bad.append("spec is EMPTY but the index changes production function(s): " + " ".join(prod))
if want - have: bad.append("census seams MISSING from the spec (hand-picked?): " + "; ".join(sorted(want - have)))
if have - want: bad.append("spec mutants NOT in this index's census: " + "; ".join(sorted(x or "?" for x in have - want)))
off = sorted({m.get("file") or "?" for m in spec if (m.get("file") or "") not in staged})
if off: bad.append("spec mutates UNSTAGED path(s) (H480): " + " ".join(off))
if int(sys.argv[4]) != len(spec): bad.append("line says %s seams mutated, spec holds %d" % (sys.argv[4], len(spec)))
print("\n".join(bad) if bad else "COVERED %d production function(s), %d seam(s) == census" % (len(prod), len(have)))
sys.exit(1 if bad else 0)
PY
); smv=$?
      if [ $smv -ne 0 ]; then
        echo "REFUSE $IP $WT -- SELFMUT SPEC IS NOT THIS INDEX'S CENSUS (H489):"; printf '%s\n' "$SMV" | sed 's/^/        /'
        echo "        re-run: bash $SMH/bd-selfmut-floor.sh $WT   (after the index is final) and paste its last line."
        rc=1
      else
        echo "SELFMUT $IP $WT -- $SMV; $SMK escaped"
      fi
    else
      echo "UNKNOWN $IP $WT -- SELFMUT coverage UNMEASURED: census failed ($(tail -1 "$SMT/census.log" "$SMT/seams.log" 2>/dev/null | grep -v '^==>' | grep -m1 .))."
      [ $rc -eq 0 ] && rc=4
    fi
    rm -rf "$SMT"
  fi
fi
fi   # O930

# CHECK 7 -- SHARD WIRING (H490). Rows 800 and 800b were REFUTED because a NEW tests/test_*.py was not wired into ci.yml +
# the 939 shard gate. A staged new test file is run through THIS INDEX'S copy of that one gate (the cut may itself edit
# _DECLARED / ci.yml); a red gate refuses, naming the new file(s) the gate names. No new test -> nothing to run.
NEWTESTS=$(awk -F'\t' '$1=="NEWTEST"{print $2}' <<<"$OUT" | sort -u)
SHGATE=tests/test_v3_66_939_ci_gate_shards_cover_every_gate.py
SHPY=/home/mboyle/BulkDownloader/venv/bin/python
if [ -n "$NEWTESTS" ]; then
  SHN=$(printf '%s\n' "$NEWTESTS" | wc -l)
  if [ "$IP" != local ]; then
    echo "UNKNOWN $IP $WT -- $SHN staged NEW test file(s) but the shard gate cannot run on a remote host; wiring UNMEASURED (H490)."
    [ $rc -eq 0 ] && rc=4
  elif [ ! -f "$WT/$SHGATE" ] || [ ! -x "$SHPY" ]; then
    echo "UNKNOWN $IP $WT -- $SHN staged NEW test file(s); shard gate $SHGATE or $SHPY missing; wiring UNMEASURED (H490)."
    [ $rc -eq 0 ] && rc=4
  else
    SHLOG=$(mktemp /tmp/bd-guard-shard.XXXXXX)
    ( cd "$WT" && env -u BD_INSTALL_DIR BD_DISABLE_KEEPALIVE=1 PYTHONDONTWRITEBYTECODE=1 timeout -k 10 "${BD_GUARD_SHARD_BUDGET:-300}" "$SHPY" -m pytest -q -p no:cacheprovider "$SHGATE" ) >"$SHLOG" 2>&1; shrc=$?
    if [ $shrc -eq 0 ]; then
      echo "SHARD $IP $WT -- $SHN staged NEW test file(s) pass $SHGATE on this index: $(printf '%s' "$NEWTESTS" | tr '\n' ' ')"
    elif [ $shrc -eq 124 ] || [ $shrc -eq 137 ]; then
      echo "UNKNOWN $IP $WT -- shard gate timed out (rc=$shrc, budget ${BD_GUARD_SHARD_BUDGET:-300}s); wiring UNMEASURED (H490)."
      [ $rc -eq 0 ] && rc=4
    else
      NAMED=$(printf '%s\n' "$NEWTESTS" | while IFS= read -r t; do grep -qF -- "$t" "$SHLOG" && echo "$t"; done)
      if [ -n "$NAMED" ]; then
        echo "REFUSE $IP $WT -- SHARD WIRING (H490): $SHGATE is RED on this index and names $(printf '%s\n' "$NAMED" | wc -l) staged NEW test file(s):"
        printf '%s\n' "$NAMED" | sed 's/^/        UNWIRED /'
      else
        echo "REFUSE $IP $WT -- SHARD WIRING (H490): $SHGATE is RED on this index (rc=$shrc) with $SHN staged NEW test file(s); it names none of them -- the index breaks the gate elsewhere:"
      fi
      grep -E '^(FAILED|ERROR) ' "$SHLOG" | head -5 | sed 's/^/        /'
      echo "        gate log: $SHLOG   (fix: BD_GATE_SCOPE marker at module scope; repo-wide -> _DECLARED + a ci.yml gate-suites shard, same cut)"
      rc=1
    fi
    [ $shrc -ne 0 ] || rm -f "$SHLOG"
  fi
fi

# CHECK 8 -- IMPORT EDGE DEBT VALIDATION (SYN-34).
# Validates that DONE.md OWED edges == import_graph_gate --check delta.
# Under Trio Rule, new import edges must NOT be re-frozen in a worker cut; they must be declared
# verbatim in DONE.md under '## OWED TO THE INTEGRATOR -- NEW IMPORT EDGES'.
# Any mismatch between live graph delta and DONE.md is a refusal (prevents drift and silent coupling).
IG_DELTA_REPORT=$(python3 - "$OUT" <<'PY_IG'
import re, sys

out_lines = sys.argv[1].splitlines()

# 1. Parse delta edges from IGOUT
gate_edges = set()
ig_lines = [l[6:] for l in out_lines if l.startswith("IGOUT\t")]
for line in ig_lines:
    m = re.search(r"^\s*\+\s*([a-zA-Z0-9_/.-]+\.py)\s*->\s*([a-zA-Z0-9_/.-]+\.py)", line)
    if m:
        gate_edges.add(f"{m.group(1)} -> {m.group(2)}")

# 2. Parse declared edges from DONELINE
done_lines = [l[9:] for l in out_lines if l.startswith("DONELINE\t")]
in_owed = False
declared_edges = set()
for line in done_lines:
    if re.search(r"OWED\b.*(?:IMPORT\s+EDGES|TO\s+THE\s+INTEGRATOR)", line, re.I):
        in_owed = True
        continue
    if in_owed:
        if re.match(r"^\s*##?\s+(?!OWED)", line) or re.match(r"^\s*(REMOTE PRECUT|PATHS|MODEL|PROPOSED):", line, re.I):
            in_owed = False
            continue
        m = re.search(r"(?:^|[+\s*-])([a-zA-Z0-9_/.-]+\.py)\s*->\s*([a-zA-Z0-9_/.-]+\.py)", line)
        if m:
            declared_edges.add(f"{m.group(1)} -> {m.group(2)}")

# Check syntax / unparseable error from IGOUT
unparseable = [l for l in ig_lines if "UnparseableSourceError" in l]
if unparseable:
    print("UNPARSEABLE\t" + unparseable[0])
    sys.exit(0)

missing = sorted(gate_edges - declared_edges)
phantom = sorted(declared_edges - gate_edges)

if missing:
    print("MISSING\t" + "; ".join(missing))
if phantom:
    print("PHANTOM\t" + "; ".join(phantom))
if not missing and not phantom:
    print(f"MATCH\t{len(gate_edges)}")
PY_IG
)

if [ -n "$IG_DELTA_REPORT" ]; then
  case "$IG_DELTA_REPORT" in
    MATCH*)
      n_edges=$(awk -F'\t' '{print $2}' <<< "$IG_DELTA_REPORT")
      if [ "$n_edges" -gt 0 ]; then
        echo "PASS   $IP $WT -- IMPORT EDGE DEBT (SYN-34): $n_edges declared owed import edge(s) == import_graph_gate --check delta."
      fi
      ;;
    MISSING*)
      missing_edges=$(awk -F'\t' '{print $2}' <<< "$IG_DELTA_REPORT")
      echo "REFUSE $IP $WT -- IMPORT EDGE DEBT DRIFT (SYN-34): live graph delta has new import edge(s) missing from DONE.md:"
      while IFS= read -r me; do
        [ -n "$me" ] && echo "        MISSING: $me"
      done < <(tr ';' '\n' <<< "$missing_edges")
      echo "        Declare all new import edges in DONE.md under '## OWED TO THE INTEGRATOR -- NEW IMPORT EDGES'."
      rc=1
      ;;
    PHANTOM*)
      phantom_edges=$(awk -F'\t' '{print $2}' <<< "$IG_DELTA_REPORT")
      echo "REFUSE $IP $WT -- IMPORT EDGE DEBT DRIFT (SYN-34): DONE.md declares owed import edge(s) not present in live graph delta:"
      while IFS= read -r pe; do
        [ -n "$pe" ] && echo "        PHANTOM: $pe"
      done < <(tr ';' '\n' <<< "$phantom_edges")
      echo "        DONE.md owed edges must match live graph delta exactly (re-verify with tools/decomp/import_graph_gate.py --check)."
      rc=1
      ;;
    UNPARSEABLE*)
      err=$(awk -F'\t' '{print $2}' <<< "$IG_DELTA_REPORT")
      echo "REFUSE $IP $WT -- IMPORT EDGE DEBT (SYN-34): import_graph_gate could not parse source files: $err"
      rc=1
      ;;
  esac
fi

# CHECK 9 -- ORPHAN MODULE CALLER AUDIT (SYN-34).
# Verifies that any newly added production module under bulk_downloader/ has at least 1 caller in bulk_downloader/.
# Prevents orphaned modules from landing without production integration.
ORPHAN_COUNT=0
HAS_PRODCALLERS=0
while IFS=$'\t' read -r np callers; do
  [ -n "$np" ] || continue
  HAS_PRODCALLERS=1
  if [ "${callers:-0}" -eq 0 ]; then
    # Check for explicit allow override in environment or DONE.md
    if [ "${BD_ALLOW_ORPHAN_MODULES:-0}" = "1" ] || grep -qiE "ALLOW[ _-]ORPHAN.*$(basename "$np" .py)" "$DONE_PATH" 2>/dev/null; then
      echo "NOTE   $IP $WT -- ORPHAN MODULE (SYN-34): $np has 0 callers in bulk_downloader/ (permitted by override)."
    else
      echo "REFUSE $IP $WT -- ORPHAN MODULE (SYN-34): newly added production module $np has 0 callers in bulk_downloader/."
      echo "        A new library module must integrate real callers in production code, not land as an orphaned unit."
      rc=1
      ORPHAN_COUNT=$((ORPHAN_COUNT + 1))
    fi
  fi
done < <(awk -F'\t' '$1=="PRODCALLERS"{print $2 "\t" $3}' <<< "$OUT")

if [ "$ORPHAN_COUNT" -eq 0 ] && [ "$HAS_PRODCALLERS" -eq 1 ]; then
  echo "PASS   $IP $WT -- ORPHAN MODULE CALLER AUDIT (SYN-34): all newly added production modules have callers in bulk_downloader/."
fi


# CHECK 10 -- STAGED GENERATED ARTIFACT GUARD (SYN-44 / Trio Rule).
# Generated artifacts (FUNCTION_INDEX.md, import_graph_baseline.json, INV_TAGS, etc.)
# are integrator-owned. A worker cut must never stage them.
GEN_ARTIFACTS="FUNCTION_INDEX.md tools/decomp/import_graph_baseline.json INV_TAGS.md INV_TAGS.json PIN_INDEX.json ROUTE_INDEX.json ENDPOINT_CATALOG.md DEPENDENCY_GRAPH.json DEPENDENCY_GRAPH.md tests/source_window_hashes.json project-knowledge/STATIC_KB_MANIFEST.json"
STAGED_GEN=""
for ga in $GEN_ARTIFACTS; do
  if printf '%s\n' "$PATHS" | grep -qxF "$ga"; then
    STAGED_GEN="$STAGED_GEN $ga"
  fi
done
if [ -n "$STAGED_GEN" ]; then
  echo "REFUSE $IP $WT -- STAGED GENERATED ARTIFACT(S) (SYN-44 / Trio Rule):$STAGED_GEN"
  echo "        Generated artifacts are integrator-owned and must NEVER be staged in a cut."
  echo "        Unstage with: git restore --staged$STAGED_GEN"
  echo "        Declare any expected drift in DONE.md under '## OWED TO THE INTEGRATOR'."
  rc=1
fi

# CHECK 11 -- GENERATED-ARTIFACT STALENESS AT STAGE (SYN-44).
# Flags FUNCTION_INDEX and import graph staleness at stage time, not at integrator.
# If code changes introduce drift in FUNCTION_INDEX or new import edges, that debt
# must be declared in DONE.md under OWED TO THE INTEGRATOR, otherwise it crosses
# the worker/integrator boundary silently and causes train/rebase churn.
if [ "$IP" = local ] && [ -d "$WT" ]; then
  py_guard=$(command -v "$WT/venv/bin/python" 2>/dev/null || command -v /home/mboyle/BulkDownloader/venv/bin/python 2>/dev/null || command -v python3)
  # H719: the pre-DONE flow pastes this script's output into the declaration, and a SYN-44 REFUSE block carries the
  # very words both greps below accept. They read the declaration minus this script's own lines: "<TAG> <ip> <wt> --",
  # the 8-space detail lines and FIX COMMAND lines.
  DECL_TEXT=$(grep -vE '^((PASS|REFUSE|OK|NOTE|WARN|UNKNOWN|NONPATCH|SELFMUT|SHARD)[[:space:]]+[^[:space:]]+[[:space:]]+[^[:space:]]+[[:space:]]+--([[:space:]]|$)|        [^[:space:]]|FIX COMMAND:)' "$DONE_PATH" 2>/dev/null)

  # Check FUNCTION_INDEX drift
  if [ -f "$WT/tools/build_function_index.py" ] && [ -f "$WT/FUNCTION_INDEX.md" ]; then
    if ! "$py_guard" "$WT/tools/build_function_index.py" --check >/dev/null 2>&1; then
      if grep -qiE '(OWED.*INTEGRATOR|FUNCTION_INDEX.*drift|FUNCTION_INDEX.*stale|FUNCTION_INDEX.*regen)' <<<"$DECL_TEXT"; then
        echo "PASS   $IP $WT -- FUNCTION_INDEX staleness flagged at stage time and declared under OWED TO THE INTEGRATOR (SYN-44)."
      else
        echo "REFUSE $IP $WT -- FUNCTION_INDEX stale vs staged diff (SYN-44):"
        echo "        Staged code modifies callables but FUNCTION_INDEX drift is not declared in DONE.md."
        echo "        Declare the debt under '## OWED TO THE INTEGRATOR' in DONE.md (Trio Rule: do NOT stage FUNCTION_INDEX.md)."
        rc=1
      fi
    fi
  fi

  # Check import graph new edges
  if [ -f "$WT/tools/decomp/import_graph_gate.py" ] && [ -f "$WT/tools/decomp/import_graph_baseline.json" ]; then
    ig_rc=0
    ig_out=$(timeout 15 "$py_guard" "$WT/tools/decomp/import_graph_gate.py" --check 2>&1) || ig_rc=$?
    if [ "$ig_rc" -ne 0 ] && grep -qE '^\s*\+\s*[a-zA-Z0-9_/.-]+\.py\s*->' <<< "$ig_out"; then
      if grep -qiE '(OWED.*(?:INTEGRATOR|IMPORT)|new import edge|import.*edge)' <<<"$DECL_TEXT"; then
        echo "PASS   $IP $WT -- import graph staleness flagged at stage time and declared under OWED TO THE INTEGRATOR (SYN-44)."
      else
        echo "REFUSE $IP $WT -- import graph staleness flagged vs staged diff (SYN-44):"
        echo "        Live import graph has new edge(s) not in baseline and not declared in DONE.md."
        echo "        Declare all new edges under '## OWED TO THE INTEGRATOR -- NEW IMPORT EDGES' in DONE.md."
        rc=1
      fi
    fi
  fi
fi

# CHECK 8 -- SHELL SCRIPT LINTS (HB-shell-rc-capture-lint + HB-early-exit-ordering-lint, SYN-46).
# Flags $(...) || true + rc=$? anti-pattern (Rule 7) and new logic placed after exit 0 guards.
STAGED_SH=""
if [ -n "$PATHS" ]; then
  STAGED_SH=$(printf '%s\n' "$PATHS" | while IFS= read -r f; do
    [ -n "$f" ] || continue
    case "$f" in
      *.sh|*.bash) echo "$f" ;;
      *) if [ "$IP" = local ] && [ -f "$WT/$f" ] && head -1 "$WT/$f" 2>/dev/null | grep -qE '^#!.*(sh|bash)'; then echo "$f"; fi ;;
    esac
  done)
fi

SHELL_CLAUSE=""
if [ -n "$STAGED_SH" ]; then
  N_STAGED_SH=$(wc -l <<<"$STAGED_SH")
  if [ "$IP" != local ]; then
    echo "UNKNOWN $IP $WT -- $N_STAGED_SH staged shell script(s) but shell lints cannot run on a remote host; lints UNMEASURED."
    [ $rc -eq 0 ] && rc=4
  else
    DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SHLINT=""
    if [ -x "$DIR/bd-shell-lint.sh" ]; then
      SHLINT="$DIR/bd-shell-lint.sh"
    elif [ -x "/home/mboyle/bd-persist/harness/bd-shell-lint.sh" ]; then
      SHLINT="/home/mboyle/bd-persist/harness/bd-shell-lint.sh"
    fi

    if [ -n "$SHLINT" ]; then
      LINT_OUTPUT=$("$SHLINT" --diff "$WT" "${BASE:-}" 2>&1)
      LINT_RC=$?
      if [ $LINT_RC -ne 0 ]; then
        echo "REFUSE $IP $WT -- SHELL SCRIPT LINT REFUSAL (SYN-46):"
        printf '%s\n' "$LINT_OUTPUT" | sed 's/^/        /'
        rc=1
      else
        echo "PASS   $IP $WT -- SHELL LINTS (SYN-46): $N_STAGED_SH staged shell script(s) passed rc-capture and early-exit ordering checks."
        SHELL_CLAUSE=", $N_STAGED_SH shell script(s) lint-clean"
      fi
    else
      LINT_OUT=$(python3 - "$WT" "${BASE:-}" "$STAGED_SH" <<'PY_SHLINT'
import os, re, subprocess, sys
wt = sys.argv[1]
base = sys.argv[2]
staged_sh = [s.strip() for s in sys.argv[3].splitlines() if s.strip()]

re_subst_or_true = re.compile(
    r'(\$\([^)]*\|\|\s*true[^)]*\)'
    r'|\$\([^)]*\)\s*\|\|\s*true\b'
    r'|\(\([^)]*\|\|\s*true[^)]*\)\)'
    r'|\(\([^)]*\)\)\s*\|\|\s*true\b'
    r'|`[^`]*\|\|\s*true[^`]*`'
    r'|`[^`]*`\s*\|\|\s*true\b'
    r'|\|\|\s*true\b)'
)
re_rc_capture = re.compile(
    r'(?:'
    r'\b(?:local|declare|export|readonly)?\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*["\']?\$\?["\']?'
    r'|\[\s*["\']?\$\?["\']?'
    r'|\[\[\s*["\']?\$\?["\']?'
    r'|\btest\s+["\']?\$\?["\']?'
    r'|\bexit\s+["\']?\$\?["\']?'
    r'|\(\(\s*["\']?\$\?["\']?'
    r'|echo\s+[^#\n]*rc=\$\?'
    r')'
)

issues = []
for f in staged_sh:
    try:
        p_show = subprocess.run(["git", "-C", wt, "show", f":{f}"], capture_output=True, text=True, check=True)
        content = p_show.stdout
    except Exception:
        p_path = os.path.join(wt, f)
        if os.path.isfile(p_path):
            with open(p_path, "r", errors="replace") as fp:
                content = fp.read()
        else:
            continue

    cmd = ["git", "-C", wt, "diff", "--cached", "-U0"]
    if base:
        cmd.append(base)
    cmd.extend(["--", f])
    try:
        p_diff = subprocess.run(cmd, capture_output=True, text=True)
        diff_text = p_diff.stdout
    except Exception:
        diff_text = ""

    lines = content.splitlines()
    added_lines = set()
    current_line = None
    for dline in diff_text.splitlines():
        if dline.startswith("@@ "):
            m = re.search(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", dline)
            if m:
                current_line = int(m.group(1))
        elif current_line is not None:
            if dline.startswith("+") and not dline.startswith("+++"):
                added_lines.add(current_line)
                current_line += 1
            elif dline.startswith("-") and not dline.startswith("---"):
                pass
            elif dline.startswith(" "):
                current_line += 1

    if not added_lines and not diff_text:
        added_lines = set(range(1, len(lines) + 1))

    for i, raw_line in enumerate(lines):
        if re.search(r"#.*(?:rc-capture-ok|allow-rc-capture)", raw_line, re.I):
            continue
        parts = [p.strip() for p in re.split(r";|&&", raw_line) if p.strip()]
        same_line = False
        for idx in range(len(parts) - 1):
            p1 = parts[idx]
            p2 = parts[idx + 1]
            if re_subst_or_true.search(p1) and re_rc_capture.search(p2):
                if not added_lines or (i + 1) in added_lines:
                    issues.append((f, i + 1, "HB-shell-rc-capture-lint", f"flags '$(...) || true' followed by '$?' capture on same line: '{p1}; {p2}' -- '|| true' unconditionally zeroes '$?' and blinds detectors to regressions (Rule 7). Fix: capture exit code without '|| true' under 'set -u'."))
                same_line = True
                break
        if same_line:
            continue
        if re_subst_or_true.search(raw_line):
            for j in range(i + 1, min(i + 10, len(lines))):
                next_line = lines[j].strip()
                if not next_line or next_line.startswith("#"):
                    continue
                if re.search(r"#.*(?:rc-capture-ok|allow-rc-capture)", lines[j], re.I):
                    break
                if re_rc_capture.search(next_line):
                    if not added_lines or (j + 1) in added_lines or (i + 1) in added_lines:
                        issues.append((f, j + 1, "HB-shell-rc-capture-lint", f"flags '$(...) || true' at line {i+1} followed by '$?' capture at line {j+1}: '{next_line}' -- '|| true' unconditionally zeroes '$?' and blinds detectors to regressions (Rule 7). Fix: capture exit code without '|| true' under 'set -u'."))
                break

    func_depth = 0
    if_depth = 0
    case_depth = 0
    loop_depth = 0
    re_func_start = re.compile(r"^\s*(?:function\s+)?([a-zA-Z_0-9:-]+)\s*\(\s*\)\s*(\{)?")
    re_func_keyword = re.compile(r"^\s*function\s+([a-zA-Z_0-9:-]+)\s*(\{)?")
    re_exit_0 = re.compile(r"(?:^|[;&|\s(])exit\s+0(?:\b|[;)\s#]|$)")

    top_level_exits = []
    for i, raw_line in enumerate(lines):
        line_no = i + 1
        code = re.sub(r"#.*$", "", raw_line).strip()
        if not code:
            continue
        m_func = re_func_start.match(code) or re_func_keyword.match(code)
        if m_func and func_depth == 0:
            if m_func.group(2) or "{" in code:
                func_depth += code.count("{") - code.count("}")
            else:
                func_depth = 1
            continue
        if func_depth > 0:
            func_depth += code.count("{") - code.count("}")
            if func_depth <= 0:
                func_depth = 0
            continue
        if re.search(r"\bif\b", code) and not re.search(r"\bfi\b", code):
            if_depth += 1
        if re.search(r"\bcase\b", code) and not re.search(r"\besac\b", code):
            case_depth += 1
        if re.search(r"\b(for|while|until)\b", code) and not re.search(r"\bdone\b", code):
            loop_depth += 1
        if re_exit_0.search(code):
            is_cond = bool(
                if_depth > 0 or case_depth > 0 or loop_depth > 0 or
                re.search(r"(\|\||&&)", code) or
                re.search(r"\b(if|then|elif|else|case)\b", code) or
                re.search(r"[\(\)]", code) or
                re.search(r"\{.*exit\s+0.*\}", code)
            )
            top_level_exits.append((line_no, not is_cond, code))
        if re.search(r"\bfi\b", code) and not re.search(r"\bif\b", code):
            if_depth = max(0, if_depth - 1)
        if re.search(r"\besac\b", code) and not re.search(r"\bcase\b", code):
            case_depth = max(0, case_depth - 1)
        if re.search(r"\bdone\b", code) and not re.search(r"\b(for|while|until)\b", code):
            loop_depth = max(0, loop_depth - 1)

    re_trivial = re.compile(r"^\s*(?:#.*|fi|done|esac|;;|\}|\{|\s*)$")
    re_func_def = re.compile(r"^\s*(?:function\s+)?([a-zA-Z_0-9:-]+)\s*\(\s*\)\s*\{?")

    func_depth = 0
    for i, raw_line in enumerate(lines):
        line_no = i + 1
        code = re.sub(r"#.*$", "", raw_line).strip()
        m_func = re_func_start.match(code) or re_func_keyword.match(code)
        if m_func and func_depth == 0:
            if m_func.group(2) or "{" in code:
                func_depth += code.count("{") - code.count("}")
            else:
                func_depth = 1
            continue
        if func_depth > 0:
            func_depth += code.count("{") - code.count("}")
            if func_depth <= 0:
                func_depth = 0
            continue
        if line_no not in added_lines:
            continue
        stripped = raw_line.strip()
        if re_trivial.match(stripped) or re_func_def.match(stripped) or re_exit_0.search(stripped):
            continue
        if re.search(r"#.*(?:early-exit-ok|allow-after-exit|post-exit-ok)", raw_line, re.I):
            continue
        if os.environ.get("BD_EARLY_EXIT_OK") == "1":
            continue

        prior_uncond = [e for e in top_level_exits if e[0] < line_no and e[1]]
        prior_cond = [e for e in top_level_exits if e[0] < line_no and not e[1]]
        if prior_uncond:
            first_uncond = prior_uncond[0]
            issues.append((f, line_no, "HB-early-exit-ordering-lint", f"dead code placed after unconditional exit at line {first_uncond[0]} ('{first_uncond[2]}'): '{stripped}'"))
        elif prior_cond:
            first_cond = prior_cond[0]
            n_guards = len(prior_cond)
            issues.append((f, line_no, "HB-early-exit-ordering-lint", f"new logic placed after {n_guards} 'exit 0' guard(s) (first at line {first_cond[0]}: '{first_cond[2]}'): '{stripped}' -- Logic placed after early 'exit 0' guards is skipped when guards trigger (e.g. queue empty, load gate). Place unconditional logic before guards, or annotate '# early-exit-ok'."))

if issues:
    for sf, lno, rule, msg in issues:
        print(f"REFUSE\t{sf}\t{lno}\t{rule}\t{msg}")
else:
    print("PASS")
PY_SHLINT
)
      if grep -q '^REFUSE' <<<"$LINT_OUT"; then
        echo "REFUSE $IP $WT -- SHELL SCRIPT LINT REFUSAL (SYN-46):"
        while IFS=$'\t' read -r _st sf lno rule msg; do
          [ -n "$sf" ] || continue
          echo "        $sf:$lno: [$rule] $msg"
        done < <(grep '^REFUSE' <<<"$LINT_OUT")
        rc=1
      else
        echo "PASS   $IP $WT -- SHELL LINTS (SYN-46): $N_STAGED_SH staged shell script(s) passed rc-capture and early-exit ordering checks."
        SHELL_CLAUSE=", $N_STAGED_SH shell script(s) lint-clean"
      fi
    fi
  fi
fi

# CHECK 12 -- ENDPOINT REACHABILITY AUTO-DECLARE LINTER (HB-reach-autodeclare / SYN-48)
# fx5 (lens bd-review-correctness-B3x-hb-B): the fx4 rebase renamed this CHECK 8 -> CHECK 10 "since
# live already has CHECK 8/9", but live also has CHECK 10 and CHECK 11 (both SYN-44), so the rename
# only moved the collision. 12 is the first free number.
# Pre-check newly added mutating routes (@bp.route) against reports/endpoint_reachability.json
# to alert workers before precut failure and provide --auto-classify-cut fix command.
REACH_LINTER=${BD_REACH_LINTER:-/home/mboyle/bd-persist/harness/bd-reach-autodeclare.py}
[ -f "$REACH_LINTER" ] || REACH_LINTER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/bd-reach-autodeclare.py"
if [ "$IP" = local ] && [ -d "$WT" ] && [ -f "$REACH_LINTER" ]; then
  rl_out=$(python3 "$REACH_LINTER" --check --worktree "$WT" ${BASE:+--base "$BASE"} --strict 2>&1)
  rl_rc=$?
  if [ $rl_rc -ne 0 ]; then
    echo "REFUSE $IP $WT -- ENDPOINT REACHABILITY (HB-reach-autodeclare): undeclared mutating route addition(s) detected:"
    printf '%s\n' "$rl_out" | grep -E '^  \[UNDECLARED-ROUTE\]' | sed 's/^/        /'
    echo "FIX COMMAND: python3 $REACH_LINTER --auto-classify-cut <ROW> --worktree \"$WT\" ${BASE:+--base "$BASE"} --write"
    rc=1
  fi
fi

# CHECK 13 -- EXPECTED RC=3 GATES PREFLIGHT WARNINGS (O906 / SYN-21; renumbered from 8 on rebase over SYN-34/44/46/48)
# Surfaces known repo gate expectations to warn workers before collector/precut bounce:
#   1. BD_GATE_SCOPE missing in new tests (O906.1)
#   2. SSRF census registration for new network seams (O906.2)
#   3. Import-graph baseline regeneration (O906.3)
#   4. Canonical-row gate DIRECT-4 missing pending note (O906.4)
if [ "$IP" = local ] && [ -d "$WT" ]; then
  # 1. BD_GATE_SCOPE marker
  if [ -n "$NEWTESTS" ]; then
    for nt in $NEWTESTS; do
      if [ -f "$WT/$nt" ] && ! grep -qE '^[[:space:]]*BD_GATE_SCOPE[[:space:]]*=' "$WT/$nt" 2>/dev/null; then
        echo "WARN   $IP $WT -- [rc=3 gate expected] $nt lacks BD_GATE_SCOPE marker (O906.1). Fix: add BD_GATE_SCOPE = 'module' at module top."
      fi
    done
  fi

  # 2. SSRF census
  if git -C "$WT" diff --cached -U0 2>/dev/null | grep -qE '^\+[^+].*\b(urlopen|requests\.(get|post|put|delete|request)|urllib\.request)\b'; then
    if ! git -C "$WT" diff --cached --name-only 2>/dev/null | grep -qE 'ssrf|reports/.*ssrf'; then
      echo "WARN   $IP $WT -- [rc=3 gate expected] SSRF urlopen/requests seam added in staged changes without census update (O906.2)."
    fi
  fi

  # 3. Import-graph baseline
  new_prod=$(git -C "$WT" diff --cached --name-only --diff-filter=A -- "bulk_downloader/*.py" 2>/dev/null || true)
  if [ -n "$new_prod" ] && ! git -C "$WT" diff --cached --name-only 2>/dev/null | grep -qE 'tools/decomp/import_graph_baseline\.json'; then
    echo "WARN   $IP $WT -- [rc=3 gate expected] New production python modules staged without import_graph_baseline.json update (O906.3). Fix: venv/bin/python toolchain/bin/bd-imports --work \"$WT\" --update"
  fi

  # 4. Canonical-row gate (DIRECT-4)
  if [ -f "$DONE_PATH" ] && grep -qiE 'PRECUT.*rc=3' "$DONE_PATH" 2>/dev/null; then
    # H605: an authored blocker note may name several gates. Neither "only"
    # nor the legacy "register row pending" phrase is required. Copied WARN
    # output is evidence of a warning, not an author's canonical-row note.
    if awk '
      { line=tolower($0)
        if (line ~ /^[[:space:]]*(precut|o906[.]4|canonical[- ]row):/ &&
            line ~ /(^|[^[:alnum:]_-])direct-4([^[:alnum:]_-]|$)/) noted=1
      }
      END { exit !noted }
    ' "$DONE_PATH"; then
      echo "PASS   $IP $WT -- O906.4 canonical-row blocker documented; other named gates still apply."
    else
      echo "WARN   $IP $WT -- [rc=3 gate expected] DONE.md records PRECUT rc=3 without canonical-row note (O906.4). If DIRECT-4 blocks, name it and every other blocker, e.g. 'O906.4: DIRECT-4, import graph and inventory remain'."
    fi
  fi

fi

# CHECK 14 -- PREP-INFLIGHT (SYN-70; renumbered from 12 on rebase over SYN-46/48/21). Refuse a DONE.md edit while a cut is PREP-STARTED but not yet PREPPED.
# A DONE.md edit mid-prep triggers FORCE re-prep and drops recorded verdicts.
# Incremental state must be recorded in FIXER/LOG.md instead of touching DONE.md mid-prep.
RLOG="${BD_REVIEW_LOG:-/home/mboyle/bd-persist/review.log}"
if [ -f "$RLOG" ]; then
  BNAME=$(basename "$WT")
  TID=${BNAME#row}
  TID=${TID%-local}
  if ! INFLIGHT=$(awk -v tid="$TID" -v bname="$BNAME" '
    $1 == "PREP-STARTED" {
      k = $2; sub(/^row/, "", k); sub(/-local$/, "", k)
      if (k == tid || $2 == bname || $2 == tid) s = 1
    }
    $1 ~ /^(PREPPED|PREP-REFUSED|SKIP-LANDED-BY-PROPERTY|SKIP-ARCHIVED|SKIP-ALREADY-BRIEFED)$/ {
      k = $2; sub(/^row/, "", k); sub(/-local$/, "", k)
      if (k == tid || $2 == bname || $2 == tid) s = 0
    }
    END { print(s ? 1 : 0) }
  ' "$RLOG" 2>/dev/null); then
    echo "UNKNOWN $IP $WT -- PREP-INFLIGHT: cannot read prep state from $RLOG."
    [ $rc -eq 0 ] && rc=4
  elif [ "$INFLIGHT" != 0 ] && [ "$INFLIGHT" != 1 ]; then
    echo "UNKNOWN $IP $WT -- PREP-INFLIGHT: invalid prep state from $RLOG."
    [ $rc -eq 0 ] && rc=4
  fi
  if [ "$INFLIGHT" = "1" ]; then
    echo "REFUSE $IP $WT -- PREP-INFLIGHT: cut is PREP-STARTED but not yet PREPPED (SYN-70)."
    echo "        Refusing DONE.md edit while prep is in flight (triggers FORCE re-prep and drops recorded verdicts)."
    echo "        Fixer records band rc/tree in FIXER/LOG.md instead of touching DONE.md mid-prep."
    rc=1
  fi
else
  echo "UNKNOWN $IP $WT -- PREP-INFLIGHT: prep log is absent or not a regular file: $RLOG."
  [ $rc -eq 0 ] && rc=4
fi

# CHECK 11 -- STAGED PATHS OUTSIDE KNOWN REPO TOP-LEVEL DIRS (SYN-72 / O1045 / O1066b).
# Ambiguous staging wording produced cuts staging harness-work/ into the product repo.
# Refuse any cut that stages paths outside the repo's known top-level dirs.
if [ "$(get NAMESPACE)" != OK ]; then
  echo "UNKNOWN $IP $WT -- staged namespace probe unavailable (SYN-72)"
  exit 4
fi
NS_CANON=${BD_GUARD_CANON:-/home/mboyle/BulkDownloader}
NS_CANON0=""
if [ -d "$NS_CANON" ] && [ -e "$NS_CANON/.git" ]; then
  NS_CANON0=$(git -C "$NS_CANON" ls-tree -d -z --name-only HEAD 2>/dev/null | base64 -w0) || {
    echo "UNKNOWN $IP $WT -- canonical namespace probe unavailable (SYN-72)"
    exit 4
  }
fi
BAD_PATHS=$(python3 - "$(get TOPDIR0)" "$(get STAGED0)" "$NS_CANON0" "${BD_KNOWN_TOPLEVEL_DIRS:-}" "${IS_LANDED_BY_PROP:-}" <<'PY_NAMESPACE'
import base64
import os
import sys

def paths(encoded):
    raw = base64.b64decode(encoded, validate=True)
    if raw and not raw.endswith(b"\0"):
        raise ValueError("incomplete namespace stream")
    return raw.split(b"\0")[:-1] if raw else []

known = set(paths(sys.argv[1])) | set(paths(sys.argv[3]))
known.update(os.fsencode(p) for p in sys.argv[4].split())
staged = paths(sys.argv[2])
if not staged and not sys.argv[5]:
    raise ValueError("empty staged namespace stream")
for path in staged:
    top = path.split(b"/", 1)[0]
    if top in (b"harness-work", b"bd-persist", b"bd-carry", b"harness") or (b"/" in path and top not in known):
        # One escaped display line per actual path, even with tabs/newlines.
        print(ascii(os.fsdecode(path)))
PY_NAMESPACE
) || {
  echo "UNKNOWN $IP $WT -- staged namespace could not be decoded (SYN-72)"
  exit 4
}

if [ -n "$BAD_PATHS" ]; then
  bad_cnt=$(printf '%s\n' "$BAD_PATHS" | awk 'NF' | wc -l)
  echo "REFUSE $IP $WT -- STAGED PATH OUTSIDE KNOWN TOP-LEVEL DIRS (SYN-72). $bad_cnt staged path(s) sit outside known repo top-level dirs:"
  printf '%s\n' "$BAD_PATHS" | sed 's/^/        /'
  echo "        harness candidates belong under /home/mboyle/bd-persist/harness-work/FIX/<slug>/ (O1045, O1066b), NEVER staged into the product repo."
  echo "        fix: git rm --cached <path> and keep candidates outside the product worktree."
  rc=1
fi

# CHECK 15 -- TRACKED HARNESS MARKERS (H96). A marker committed into the branch sits in the index yet in no
# `git diff --cached <base>` when the base carries it too, so every base-diff probe reads clean while a collector
# that takes commits or the index lands DONE.md/.task-id as repository content. Probe the index itself.
TRACKEDPROBE=$(printf '%s\n' "$OUT" | awk -F'\t' '$1=="TRACKEDPROBE"{print $2; exit}')
TRACKEDMARK=$(printf '%s\n' "$OUT" | awk -F'\t' '$1=="TRACKEDMARK"{print $2}')
if [ "$TRACKEDPROBE" != 0 ]; then
  echo "UNKNOWN $IP $WT -- tracked-marker probe (git ls-files --cached) did not answer (rc=${TRACKEDPROBE:-none}); COULD NOT LOOK (H96)."
  [ $rc -eq 0 ] && rc=4
elif [ -n "$TRACKEDMARK" ]; then
  echo "REFUSE $IP $WT -- TRACKED HARNESS MARKER (H96): $(printf '%s\n' "$TRACKEDMARK" | wc -l) marker path(s) are in the index (git ls-files --cached):"
  printf '%s\n' "$TRACKEDMARK" | sed 's/^/        /'
  echo "        a base-diff probe cannot see a marker the base also tracks; collected, it lands as repository content."
  echo "FIX COMMAND: git -C \"$WT\" rm --cached -- $(printf '%s\n' "$TRACKEDMARK" | tr '\n' ' ')  (untracks only; the files stay on disk)"
  rc=1
fi

# R3: Completed-cut side-file sprawl. Completed cuts (VERDICT: PATCH) must retain only lean DONE.md (<25 lines);
# side files (RESUME_STATE.md, NOTE.md, RULING.md) cause markdown sprawl, token bloat, and index pollution risk.
SIDEFILES=$(printf '%s\n' "$OUT" | awk -F'\t' '$1=="SIDEFILE"{print $2}')
if [ -n "$SIDEFILES" ]; then
  echo "REFUSE $IP $WT -- COMPLETED-CUT SIDE-FILE SPRAWL (R3): $(printf '%s\n' "$SIDEFILES" | awk 'NF' | wc -l) stray side file(s) present (purge on completed cuts):"
  printf '%s\n' "$SIDEFILES" | awk 'NF' | sed 's/^/        /'
  echo "        completed cuts must retain only lean DONE.md (<25 lines); side files (RESUME_STATE.md, NOTE.md, RULING.md) are prohibited."
  echo "FIX COMMAND: (cd \"$WT\" && rm -f $(printf '%s\n' "$SIDEFILES" | awk 'NF' | tr '\n' ' '))"
  rc=1
fi

# CHECK 16 -- PROPORTIONAL VERIFICATION & 303 CROSS-SUITE AUDIT GATE (R5 / Feature 21)
# Under proportional verification, worker unit test scope is strictly narrowed to task-relevant tests
# during intermediate edits. Full regression coverage (the 303-test cross-suite audit: frontier_efficiency,
# frontier_blueprint_integration, fleet_parity_reconciliation, audit_fleet_parity.py) is enforced at
# the Train Integration / Collector Gate (bd-precollect-guard.sh) and CI.
IS_COLLECTOR_STAGE=0
case "${BD_GATE_STAGE:-}" in
  collector|precut|integration|train) IS_COLLECTOR_STAGE=1;;
esac
case "${BD_SEAT:-}" in
  bd-integrator*|bd-collector*|bd-pm*|bd-cx-integrator*) IS_COLLECTOR_STAGE=1;;
esac
if [ "${BD_COLLECTOR_GATE:-0}" = "1" ] || [ "${BD_ENFORCE_303:-0}" = "1" ] || [ "${3:-}" = "--collector-audit" ]; then
  IS_COLLECTOR_STAGE=1
fi

AUDIT_NOTE=""
if [ "$IS_COLLECTOR_STAGE" -eq 1 ]; then
  AUDIT_SUITES="frontier_efficiency frontier_blueprint_integration fleet_parity_reconciliation audit_fleet_parity.py"
  AUDIT_FAIL=0
  if [ "$IP" = local ] && [ -d "$WT" ]; then
    for asuite in $AUDIT_SUITES; do
      suite_path=""
      if [ -f "$WT/tests/$asuite" ]; then suite_path="$WT/tests/$asuite"
      elif [ -f "$WT/tools/$asuite" ]; then suite_path="$WT/tools/$asuite"
      elif [ -f "$WT/$asuite" ]; then suite_path="$WT/$asuite"
      fi
      if [ -n "$suite_path" ]; then
        if [[ "$suite_path" == *.py ]]; then
          python3 "$suite_path" >/dev/null 2>&1 || {
            echo "FAIL ${IP:-local} ${WT:-.} -- 303-test cross-suite audit failed on $asuite" >&2
            rc=1
            AUDIT_FAIL=1
          }
        elif [ -x "$suite_path" ]; then
          "$suite_path" >/dev/null 2>&1 || {
            echo "FAIL ${IP:-local} ${WT:-.} -- 303-test cross-suite audit failed on $asuite" >&2
            rc=1
            AUDIT_FAIL=1
          }
        fi
      fi
    done
  fi
  if [ $AUDIT_FAIL -eq 0 ]; then
    AUDIT_NOTE=", 303-test cross-suite audit verified"
  else
    AUDIT_NOTE=", 303-test cross-suite audit failed"
  fi
else
  AUDIT_NOTE=", proportional verification active (worker scope narrowed)"
fi

[ $rc -eq 0 ] && echo "OK ${IP:-local} ${WT:-.} -- line 1 exact, HEAD == declared base ${BASE:-}, ${IDX:-0} staged$( [ -n "${IS_LANDED_BY_PROP:-}" ] && echo " (LANDED-BY-PROPERTY O987)" ), index == worktree, path set is not a superseded generation in ${CARRY:-none}, ${BASE_CLAUSE:-declared base is current main}, SELFMUT $( case "${SMN:-}" in POST-BOARD*|LANDED-BY-PROPERTY*) echo "${SMN:-}";; *) echo "0 escaped of ${SMN:-0} == census";; esac ), import-edge-debt == delta, orphan audit ok, artifact-staleness checked (SYN-44)${AUDIT_NOTE:-}${SHELL_CLAUSE:-}"
exit $rc
