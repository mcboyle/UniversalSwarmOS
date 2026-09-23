#!/usr/bin/env python3
"""PreToolUse(Bash) hook: REFUSE the command shapes that have cost this fleet a round before.
Deterministic, no model. Exit 2 + stderr = refused (Claude sees the reason, nothing runs).
Exit 0 = allowed. A guard that cannot parse its event allows and says nothing.

Escape hatch: prefix the command with  BD_TRIPWIRE_OK='<why>'  -- the reason is logged, not judged.
Every refusal and every override is appended to /home/mboyle/bd-persist/logs/tripwire.log.

RULES (each names the authority that earned it):
 T1 git add -A / --all / .                     CLAUDE.md A4: stage only inspected paths
 T2 git reset --hard | checkout -- | clean -fd  A4: destructive recovery needs proven target (scripts/deploy.sh exempt)
    H461: judged as an INVOCATION (command word git, subcommand, flags), not as a substring -- a comment or an
    echo argument naming the step is prose; bash/sh -c '<string>' is walked; unparseable quoting fails closed.
 T3 git push --force (not --force-with-lease)  A4
 T4 pytest on tests/ (the full suite) without the canonical tokens (-n 24, --dist loadfile,
    --max-worker-restart=0, --timeout-method=signal, env -u BD_INSTALL_DIR)   A5: a different experiment cannot authorize merge
 T5 any pytest while BD_INSTALL_DIR is exported and the command does not strip it   A5
 T6 sed -i on toolchain/ or scripts/                A7: never sed -i as an applied check
 T7 nohup from a tool call                          memory: nohup-from-tool-call-is-not-detached (use a detached tmux window)
 T8 rm -rf / git worktree remove on a worktree path (bd-cuts, .worktrees, bd-codex-wt, bd-claude-wt, bd-persist)   FLEET_RULE 22
 T9 crontab -r                                      the whole fleet schedule
 T10 pkill/killall -f with an unanchored bare pattern   memory: kill-pattern-matches-brief-text
 T16 pytest in a local cut with more than one (or no) test file  O381: suites run remotely
 T17 cp of *.sh without -p                     bd-pm-F51-A: cp without -p drops exec bits on deployed twins (use cp -p)
 T18 bd-say without rc capture                 bd-pm-F51-A: every bd-say call must check rc (e.g. bd-say ...; rc=$?)
"""
import json, os, re, sys, datetime
LOG = os.environ.get("BD_TRIPWIRE_LOG", "/home/mboyle/bd-persist/logs/tripwire.log")
WT = r"(bd-cuts|\.worktrees|bd-codex-wt|bd-claude-wt|bd-codex-lens-wt|bd-floor-private|bd-persist)"
RULES = [
 ("T1 git add -A/.", re.compile(r"\bgit\s+add\s+(-A\b|--all\b|\.(\s|$|;|&))")),
 ("T3 bare force push", re.compile(r"\bgit\s+push\b(?!.*--force-with-lease).*(\s--force\b|\s-f\b)")),
 ("T6 sed -i on a tool", re.compile(r"\bsed\s+-i\b[^|;&]*\b(toolchain/|scripts/)")),
 ("T7 nohup from a tool call", re.compile(r"(^|[;&|]\s*)nohup\s")),
 ("T8 worktree deletion", re.compile(r"\b(rm\s+-[a-zA-Z]*r[a-zA-Z]*f?[a-zA-Z]*\s+[^;&|]*" + WT + r"|git\s+worktree\s+remove)")),
 ("T9 crontab -r", re.compile(r"\bcrontab\s+-r\b")),
 ("T10 unanchored pkill -f", re.compile(r"\b(pkill|killall)\s+(-[a-zA-Z]*\s+)*-f\s+(?![\"']?\^)[\"']?[A-Za-z][A-Za-z0-9_.-]*[\"']?(\s|$)")),
 # O908 (2026-09-19) -- shapes that each cost a round TODAY:
 ("T11 pipe into crontab -", re.compile(r"\|\s*crontab\s+-(\s|$)")),
 ("T12 sed -i on a LIVE harness script", re.compile(r"\bsed\s+-i\b[^|;&]*\b(bd-band-remote\.sh|bd-worker-precut\.sh|bd-say\.sh|bd-dispatch\.sh|bd-offer-sweep\.sh|bd-review-prep\.sh)")),
 ("T13 process kill of pytest not scoped to a worktree path", re.compile(r"\b(pkill|killall)\s+[^|;&]*\bpytest\b(?![^|;&]*(bd-cuts|bd-seats|bd-local-wt|bd-review-wt))")),
 ("T14 crontab -e", re.compile(r"\bcrontab\s+-e\b")),
]
T2_RX = re.compile(r"\bgit\s+(reset\s+--hard|checkout\s+--\s|clean\s+-[a-zA-Z]*f[a-zA-Z]*d)")   # fallback only (H461)
FULL = re.compile(r"\bpytest\b[^|;&]*\stests/?(\s|$|;|&|\|)")
CANON = ["-n 24", "--dist loadfile", "--max-worker-restart=0", "--timeout-method=signal"]
LOCAL_PYTEST_ROOTS = ("/var/tmp/bd-seats/", "/home/mboyle/bd-cuts/")

def log(kind, cmd, why):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write(f"{datetime.datetime.now(datetime.UTC).strftime('%FT%TZ')} {kind} {why} :: {cmd[:300]!r}\n")
    except OSError:
        pass

def strip_heredocs(cmd):
    """Drop heredoc BODIES (prose written to files is not a command). Keeps the << line itself."""
    out, lines, term = [], cmd.split("\n"), None
    for ln in lines:
        if term is not None:
            if ln.strip() == term:
                term = None
            continue
        m = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", ln)
        if m:
            term = m.group(2)
        out.append(ln)
    return "\n".join(out)

def check_detailed(cmd, env):
    cmd = strip_heredocs(cmd)
    hits = []
    details = []

    # H461 (B2-B 15:50Z, FR34 class "a text scanner fires on non-executable text", 2nd after H414): T2 judges
    # INVOCATIONS like T4/T5 -- the segment's command word must be git and its subcommand reset/checkout/clean.
    if git_destructive(cmd) and "scripts/deploy.sh" not in cmd:
        hits.append("T2 destructive git recovery")
        details.append({
            "rule_id": "T2",
            "name": "T2 destructive git recovery",
            "pattern": r"git (reset --hard | checkout -- | clean -f..d)",
            "match": cmd.strip()[:100],
        })

    for name, rx in RULES:
        m = rx.search(cmd)
        if m:
            rule_id = name.split()[0]
            hits.append(name)
            details.append({
                "rule_id": rule_id,
                "name": name,
                "pattern": rx.pattern,
                "match": m.group(0).strip(),
            })

    # H374 (int-B 08:24Z, O418): T4/T5 judge INVOCATIONS, not mentions. A runner name inside a quoted argument
    # (a role-state stamp, a bd-say message quoting a refusal, a seat named pytest-banners) starts nothing.
    # The invocation walk recurses into bash/sh -c '<string>', so quoting a REAL run does not hide it.
    invs = pytest_invocations(cmd)
    if invs is None:                       # unparseable quoting: fall back to the old string match (fail closed)
        full = bool(FULL.search(cmd)); anyrun = bool(re.search(r"\bpytest\b", cmd))
    else:
        full = any(i[1] for i in invs); anyrun = bool(invs)
    if full:
        missing = [t for t in CANON if t not in cmd]
        if "env -u BD_INSTALL_DIR" not in cmd:
            missing.append("env -u BD_INSTALL_DIR")
        if missing:
            msg = "T4 full-suite pytest missing " + ", ".join(missing)
            hits.append(msg)
            details.append({
                "rule_id": "T4",
                "name": msg,
                "pattern": "canonical tokens: " + ", ".join(CANON) + ", env -u BD_INSTALL_DIR",
                "match": "missing: " + ", ".join(missing),
            })
    if anyrun and env.get("BD_INSTALL_DIR") and "env -u BD_INSTALL_DIR" not in cmd \
            and "BD_INSTALL_DIR=" not in cmd:
        hits.append("T5 pytest with BD_INSTALL_DIR inherited")
        details.append({
            "rule_id": "T5",
            "name": "T5 pytest with BD_INSTALL_DIR inherited",
            "pattern": "BD_INSTALL_DIR exported in environment without stripping",
            "match": f"BD_INSTALL_DIR={env.get('BD_INSTALL_DIR')}",
        })
    # O908/O381: a builder seat runs the suite REMOTELY (bd-worker-precut.sh). Locally: ONE test file, or --collect-only.
    # SYN-14: multiple node IDs targeting the SAME test file are sanctioned (same-file node list).
    seat = env.get("BD_SEAT", "")
    if anyrun and re.match(r"bd-(worker|cx-worker|agy-worker)", seat) and "--collect-only" not in cmd and "bd-worker-precut" not in cmd:
        raw_files = re.findall(r"\btests/[A-Za-z0-9_./-]*\.py", cmd)
        files = list(dict.fromkeys(f.split("::", 1)[0] for f in raw_files))
        if len(files) != 1 or re.search(r"\bpytest\b[^|;&]*\s(tests|\.)(/)?(\s|$|;|&)", cmd):
            hits.append("T15 local pytest beyond ONE file from a builder seat (O381: the suite runs remotely via bd-worker-precut.sh)")
            details.append({
                "rule_id": "T15",
                "name": "T15 local pytest beyond ONE file from a builder seat (O381)",
                "pattern": "single test file required in local builder seat runs",
                "match": f"found {len(files)} distinct file(s): {files}",
            })
    # O898/R3: apply the same boundary to every shell running in a fleet cut, not just worker seats.
    # SYN-14: multiple node IDs targeting the same .py test file count as ONE file.
    if invs is not None:
        for args, _ in invs:
            files = list(dict.fromkeys(a.split("::", 1)[0] for a in args if a.split("::", 1)[0].endswith(".py")))
            if local_pytest_context(cmd, args, env) and len(files) != 1:
                hits.append("T16 local-cut pytest must name exactly ONE test file (O381: suites run remotely)")
                details.append({
                    "rule_id": "T16",
                    "name": "T16 local-cut pytest must name exactly ONE test file (O381)",
                    "pattern": "local-cut pytest must name exactly ONE test file",
                    "match": f"found {len(files)} distinct file(s): {files}",
                })
                break
    # SYN-35: cp of *.sh without -p drops exec bits on deployed twins (bd-pm-F51-A)
    if cp_without_preserve(cmd):
        hits.append("T17 cp of *.sh without -p (drops exec bits on deployed twins; use cp -p)")
    # SYN-35: bd-say without rc capture silences wake failures (bd-pm-F51-A)
    if bdsay_without_rc_capture(cmd):
        hits.append("T18 bd-say without rc capture (every bd-say call must check rc; e.g. bd-say ...; rc=$? or || ...)")
    return hits, details

def check(cmd, env):
    return check_detailed(cmd, env)[0]

def local_pytest_context(cmd, args, env):
    """Whether this pytest invocation executes in, or explicitly targets, a fleet cut."""
    pwd = env.get("PWD") or os.getcwd()
    if any(pwd == root[:-1] or pwd.startswith(root) for root in LOCAL_PYTEST_ROOTS):
        return True
    if any(any(a.startswith(root) for root in LOCAL_PYTEST_ROOTS) for a in args):
        return True
    root_rx = "|".join(re.escape(root) for root in LOCAL_PYTEST_ROOTS)
    return bool(re.search(r"(?:^|[;&]\s*)cd\s+(?:--\s+)?['\"]?(?:" + root_rx + r")\S*['\"]?\s*(?:&&|;)", cmd))

WRAP = {"env", "exec", "nice", "nohup", "time", "timeout", "flock", "sudo", "stdbuf", "command", "ionice", "xvfb-run"}
OPS = {"&&", "||", "|", ";", "&", "(", ")", "{", "}", "\n"}
def _split_shell_ops(cmd):
    """SYN-14 fx1: insert spaces around UNQUOTED shell operators so shlex sees them as their own tokens:
    ';' '&&' '||' '|' and file redirects ('x>f' -> 'x > f'). Descriptor forms ('2>&1', '>&2', '&>f', 'N>f') keep
    their fd/&-prefix attached to the operator. Quote/backslash aware; text inside quotes is never touched.

    fx2 (bd-review-correctness-B2x-hb-B, re-lens escapes):
      * SUBSHELL PARENS. bash takes '(' and ')' as operators with no surrounding space, so '(cd MAIN && git
        merge origin/main)' is a subshell -- but fx1 left them glued to the words, making the command word
        '(cd' (basename '(cd' != 'cd'), so the cd never set in_main and the git merge was ALLOWED while the
        unpatched guard refused it. Split bare parens. A '(' that opens a substitution ('$(', '<(', '>(') is
        NOT an operator, so it and its matching ')' are emitted untouched.
      * NEWLINE. A newline is a command separator in every shell, and '\n' is already in OPS, but posix shlex
        treats it as plain whitespace and drops it, so 'cd MAIN<newline>git merge origin/main' collapsed into
        ONE segment whose command word was 'cd' and the git merge was invisible. Emit an unquoted newline as
        ';' -- the separator OPS already recognises. (A backslash-newline is a line continuation and is
        consumed by the backslash branch above, so it is never reached here.)"""
    out, i, n, q, sub = [], 0, len(cmd), None, 0
    while i < n:
        ch = cmd[i]
        if q:
            out.append(ch)
            if ch == "\\" and q == '"' and i + 1 < n:
                out.append(cmd[i + 1]); i += 2; continue
            if ch == q:
                q = None
            i += 1; continue
        if ch == "\\" and i + 1 < n:
            out.append(ch); out.append(cmd[i + 1]); i += 2; continue
        if ch in "'\"":
            q = ch; out.append(ch); i += 1; continue
        if ch == ";":
            out.append(" ; "); i += 1; continue
        if ch == "\n":
            out.append(" ; "); i += 1; continue
        if ch == "(" and (cmd[i - 1] if i else "") in ("$", "<", ">"):
            sub += 1; out.append(ch); i += 1; continue
        if sub and ch == ")":
            sub -= 1; out.append(ch); i += 1; continue
        if ch in "()" and not sub:
            out.append(" " + ch + " "); i += 1; continue
        if cmd.startswith("&&", i) or cmd.startswith("||", i):
            out.append(" " + cmd[i:i + 2] + " "); i += 2; continue
        if ch == "|":
            out.append(" | "); i += 1; continue
        if ch == ">":
            # fd or '&' prefix already emitted as part of the previous word: pull it back off when it is a bare
            # descriptor ('2', '&') at a word start, so it stays attached to the operator.
            j = len(out)
            pre = ""
            if j and out[-1] in ("&",) or (j and out[-1].isdigit()):
                k = j
                while k and (out[k - 1].isdigit() or out[k - 1] == "&"):
                    k -= 1
                if k == 0 or out[k - 1] in (" ", "\t", "\n"):
                    pre = "".join(out[k:]); del out[k:]
            op = ">>" if cmd.startswith(">>", i) else ">"
            i += len(op)
            if i < n and cmd[i] == "&" and i + 1 < n and (cmd[i + 1].isdigit() or cmd[i + 1] == "-"):
                op += cmd[i:i + 2]; i += 2
                out.append(" " + pre + op + " ")
            elif i < n and cmd[i] == "|":
                op += "|"; i += 1; out.append(" " + pre + op + " ")
            else:
                out.append(" " + pre + op + " ")
            continue
        out.append(ch); i += 1
    return "".join(out)

def command_segments(cmd):
    """[rest] for every segment: rest[0] is the COMMAND WORD after VAR=.. and wrapper stripping, descending into
    bash|sh -c strings. None when shlex cannot tokenize (unbalanced quotes) -- callers fail closed."""
    import shlex
    try:
        # fx2: _split_shell_ops already renders an unquoted newline as ';'. The old ' \n ' padding was dead
        # code -- posix shlex discards a bare newline as whitespace, which is exactly how the separator was lost.
        toks = shlex.split(_split_shell_ops(cmd), posix=True)
    except ValueError:
        return None
    segs, cur = [], []
    for t in toks:
        if t in OPS:
            segs.append(cur); cur = []; continue
        cur.append(t)
    segs.append(cur)
    out = []
    for seg in segs:
        i = 0
        while i < len(seg):
            t = seg[i]
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t): i += 1; continue
            if t in WRAP:
                i += 1
                while i < len(seg) and (seg[i].startswith("-") or (t == "timeout" and re.match(r"^\d+[smhd]?$", seg[i])) or (t == "flock" and seg[i].startswith("/"))):
                    i += 2 if seg[i] in (("-u", "-C", "-S") if t == "env" else ("-n", "-c", "-o", "-e", "-i", "-u", "-w", "-E", "-k", "-s")) else 1   # short options that take a value (nice -n 5, ionice -c 3, stdbuf -o L, timeout -k 5)
                continue
            break
        rest = seg[i:]
        if not rest: continue
        c = rest[0]
        if re.search(r"(^|/)(ba|z|da)?sh$", c) and len(rest) >= 3 and rest[1] in ("-c", "-lc", "-ec", "-xc"):
            sub = command_segments(rest[2])
            if sub is None: return None
            out.extend(sub); continue
        out.append(rest)
    return out

def pytest_invocations(cmd):
    """[(args_after_runner, is_full_suite)] for every segment whose COMMAND WORD is pytest / python -m pytest.
    None when shlex cannot tokenize."""
    segs = command_segments(cmd)
    if segs is None: return None
    out = []
    for rest in segs:
        c = rest[0]
        args = None
        if re.search(r"(^|/)python[0-9.]*$", c) and len(rest) >= 3 and rest[1] == "-m" and rest[2] == "pytest": args = rest[3:]
        elif re.search(r"(^|/)pytest$", c): args = rest[1:]
        if args is None: continue
        full = any(re.match(r"^tests/?$", a) for a in args if not a.startswith("-"))
        out.append((args, full))
    return out

GIT_GLOBAL_VAL = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
def git_destructive(cmd):
    """True when some segment's COMMAND WORD is git and its subcommand is reset --hard, checkout -- <path>, or
    clean -f..d (H461). Falls back to the substring regex when the command cannot be tokenized (fail closed)."""
    segs = command_segments(cmd)
    if segs is None:
        return bool(T2_RX.search(cmd))
    for rest in segs:
        if not re.search(r"(^|/)git$", rest[0]): continue
        i = 1
        while i < len(rest) and rest[i].startswith("-"):
            i += 2 if rest[i] in GIT_GLOBAL_VAL else 1
        if i >= len(rest): continue
        sub, args = rest[i], rest[i+1:]
        if sub == "reset" and "--hard" in args: return True
        if sub == "checkout" and args[:1] == ["--"]: return True
        if sub == "clean" and any(re.match(r"^-[a-zA-Z]*f[a-zA-Z]*d", a) for a in args): return True
    return False

def cp_without_preserve(cmd):
    """True when some segment invokes cp with a *.sh argument but lacks -p / -a / --preserve.
    Falls back to regex when quotes are unparseable (fail closed). (SYN-35, bd-pm-F51-A)"""
    segs = command_segments(cmd)
    if segs is None:
        if re.search(r"(?:^|[;&|]\s*|\b(?:exec|sudo|env|nohup)\s+)(?:[a-zA-Z0-9_./]+/)?cp\b[^|;&]*\b\S+\.sh\b", cmd):
            if not re.search(r"\bcp\b[^|;&]*(\s-[a-zA-Z]*[pa][a-zA-Z]*|\s--(?:preserve(?:=\S*(?:mode|all)\S*)?|archive)(?=\s|$))", cmd):
                return True
        return False
    for rest in segs:
        if not rest:
            continue
        if not re.search(r"(^|/)cp$", rest[0]):
            continue
        args = rest[1:]
        has_preserve = False
        has_sh = False
        for a in args:
            if a.startswith("-"):
                if re.match(r"^-[a-zA-Z]*[pa][a-zA-Z]*$", a):
                    has_preserve = True
                elif a in ("--preserve", "--archive"):
                    has_preserve = True
                elif a.startswith("--preserve="):
                    # only mode-bearing lists keep exec bits; --preserve=timestamps does not
                    if {"mode", "all"} & set(a.split("=", 1)[1].split(",")):
                        has_preserve = True
            else:
                if a.endswith(".sh") or re.search(r"\.sh$", a):
                    has_sh = True
        if has_sh and not has_preserve:
            return True
    return False

def mask_quotes(s):
    def repl(m):
        return m.group(1) + (" " * (len(m.group(2)))) + m.group(1)
    return re.sub(r"(\"|\x27)(.*?)\1", repl, s)

def bdsay_without_rc_capture(cmd):
    """True when cmd invokes bd-say / bd-say.sh without capturing or checking its exit code
    ($?, ||, if, etc.). Authority: bd-pm-F51-A (every bd-say call checks rc). (SYN-35)"""
    if "bd-say" not in cmd:
        return False

    # Check for bash/sh -c subcommands recursively
    try:
        import shlex
        toks = shlex.split(cmd.replace("\n", " \n "), posix=True)
    except ValueError:
        toks = None

    if toks:
        i = 0
        while i < len(toks):
            t = toks[i]
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t): i += 1; continue
            if t in WRAP: i += 1; continue
            if re.search(r"(^|/)(ba|z|da)?sh$", t) and i + 2 < len(toks) and toks[i+1] in ("-c", "-lc", "-ec", "-xc"):
                if bdsay_without_rc_capture(toks[i+2]):
                    return True
            i += 1

    lines = [re.sub(r"^\s*#.*$", "", ln) for ln in cmd.split("\n")]
    clean_cmd = "\n".join(lines)
    masked = mask_quotes(clean_cmd)
    masked = re.sub(r"(?:^|\s)#.*$", "", masked)

    inv_pat = re.compile(r"(?:^|[;&|\n]\s*|\$\(\s*|\b(?:exec|sudo|env|nohup|bash|sh)\s+)(?P<call>(?:[a-zA-Z0-9_./~-]+/)?bd-say(?:\.sh)?\b)")
    matches = list(inv_pat.finditer(masked))
    if not matches:
        return False

    def has_unchecked_status(invocation):
        if re.search(r"\b(?:if|elif|while|until)\s+[^;|\n]*\bbd-say(?:\.sh)?\b", invocation):
            return False
    
        if re.search(r"\bbd-say(?:\.sh)?\b[^|;&\n]*\|\|", invocation):
            return False
    
        if re.search(r"\bbd-say(?:\.sh)?\b[^|;&\n]*[;&\n]\s*[^|;&\n]*\$(\?|\{\?\})", invocation):
            return False
        if re.search(r"\$\([^)]*\bbd-say(?:\.sh)?\b[^)]*\)[^|;&\n]*[;&\n]\s*[^|;&\n]*\$(\?|\{\?\})", invocation):
            return False
    
        return True

    for i, match in enumerate(matches):
        end = matches[i + 1].start("call") if i + 1 < len(matches) else len(masked)
        if has_unchecked_status(masked[match.start():end]):
            return True
    return False

def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if ev.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (ev.get("tool_input") or {}).get("command") or ""
    if not cmd:
        sys.exit(0)
    m = re.match(r"\s*BD_TRIPWIRE_OK=(['\"]?)(.+?)\1\s", cmd)
    hits, details = check_detailed(cmd, os.environ)
    if not hits:
        sys.exit(0)
    if m:
        log("OVERRIDE", cmd, f"{hits} reason={m.group(2)!r}")
        sys.exit(0)
    log("REFUSED", cmd, str(hits) + (f" details={details}" if details else ""))
    detail_lines = [f"  [{d['rule_id']}] pattern: {d['pattern']} (matched: {d['match']!r})" for d in details]
    pat_str = ("\n" + "\n".join(detail_lines)) if detail_lines else ""
    print("bd-tripwire: REFUSED -- " + "; ".join(hits) + pat_str + "\n"
          "These shapes have each cost a round before (authority in the rule name; see the hook header).\n"
          "Fix the command, or if this exact case is sanctioned prefix it with BD_TRIPWIRE_OK='<why>' "
          "(logged to bd-persist/logs/tripwire.log). Nothing was run.", file=sys.stderr)
    sys.exit(2)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        cases = {  # command -> expected refusal (True) / allowed (False)
            "git add -A": True, "git add .": True, "git add CLAUDE.md": False,
            "git reset --hard origin/main": True, "bash scripts/deploy.sh && git reset --hard x": False,
            "git checkout -- foo.py": True, "git checkout main": False, "git clean -fdx": True,
            "git push --force origin x": True, "git push --force-with-lease origin x": False, "git push origin x": False,
            "sed -i 's/a/b/' toolchain/bin/bd-x": True, "sed -i 's/a/b/' /tmp/x": False,
            "nohup ./run.sh &": True, "cd x; nohup y": True, "echo nohup": False,
            "rm -rf /home/mboyle/bd-cuts/cut/x": True, "rm -rf /tmp/scratch": False, "git worktree remove x": True,
            "crontab -r": True, "crontab -l": False,
            "pkill -f codex": True, "pkill -f '^bash /home/x'": False, "pkill -f /home/mboyle/x.sh": False,
            "venv/bin/python -m pytest tests/ -n 8": True,
            "env -u BD_INSTALL_DIR BD_DISABLE_KEEPALIVE=1 PYTHONUNBUFFERED=1 venv/bin/python -m pytest tests/ -n 24 --dist loadfile --timeout=240 --timeout-method=signal --max-worker-restart=0 -p no:randomly": False,
            "env -u BD_INSTALL_DIR bash -c 'venv/bin/python -m pytest tests/test_x.py -q'": False,
            "BD_TRIPWIRE_OK='sanctioned recovery' git reset --hard abc": True,  # check() still flags; main() overrides
            "cat > f <<'EOF'\nnever run git add -A or crontab -r\nEOF\necho done": False,
            "cat <<EOF > f\ngit reset --hard\nEOF\ngit add -A": True,
            # H374 acceptance (int-B 08:24Z): (i)/(ii) invocations still refuse; (iii)/(iv) mentions pass
            "X=1 Y=2 venv/bin/python -m pytest tests/ -n 8": True,
            "cd /home/x && venv/bin/python -m pytest tests/": True,
            "echo go | venv/bin/python -m pytest tests -n 8": True,
            "bash -c 'venv/bin/python -m pytest tests/ -n 8'": True,
            "timeout 600 nice -n 5 pytest tests/": True,
            "./bd-role-state.sh set integrator bd-integrator-B \"pytest-timeout fired on pytest-banners-r10-B1; the gate ran venv/bin/python -m pytest tests/ -n 8 and precut then band\"": False,
            "./bd-say.sh bd-pm-B \"T4 refused: venv/bin/python -m pytest tests/ -n 8 missing tokens\"; rc=$?": False,
            "grep -c 'python -m pytest tests/' /home/mboyle/x.log": False,
            # H461 acceptance (B2-B 15:50Z, rows a-f): invocations refuse, mentions pass, unparseable fails closed
            "git status --porcelain   # git checkout -- <path> is what I did NOT do": False,
            "echo 'never run git checkout -- <path> here'": False,
            "git show 66178294:tests/foo.py > tests/foo.py": False,
            "bash -c 'git checkout -- tests/foo.py'": True,
            "cd /x && git reset --hard origin/main": True,
            "git -C /home/x checkout -- f.py": True,
            "git checkout -b topic": False,
            "git clean -n": False,
            "echo 'unbalanced && git reset --hard x": True,
            # O898/R3: local cuts permit a RED-first single file, never a local battery.
            "pytest tests/a.py tests/b.py": False,
            "pytest tests/a.py": False,
            "pytest": False,
            "pytest tests/": True,
            "cd /home/mboyle/bd-cuts/cut/r3 && pytest tests/a.py tests/b.py": True,
            # SYN-35: cp of *.sh without -p (T17) and bd-say without rc capture (T18)
            "cp script.sh dest.sh": True,
            "cp -p script.sh dest.sh": False,
            "cp -a script.sh dest.sh": False,
            "cp --preserve script.sh dest.sh": False,
            "cp --preserve=timestamps script.sh dest.sh": True,
            "cp --preserve=ownership,timestamps script.sh dest.sh": True,
            "cp --preserve=mode script.sh dest.sh": False,
            "cp --preserve=mode,timestamps script.sh dest.sh": False,
            "cp --preserve=all script.sh dest.sh": False,
            "cp --archive script.sh dest.sh": False,
            "cp file.py other.py": False,
            "./bd-say.sh bd-pm-B \"done\"": True,
            "./bd-say.sh bd-pm-B \"done\"; rc=$?": False,
            "./bd-say.sh bd-pm-B \"done\" || exit 1": False,
            "if ./bd-say.sh bd-pm-B \"done\"; then echo ok; fi": False,
            # SYN-14: same-file node IDs are allowed; multi-file node IDs are refused
            "cd /home/mboyle/bd-cuts/cut/r3 && pytest tests/a.py::test_1 tests/a.py::test_2": False,
            "cd /home/mboyle/bd-cuts/cut/r3 && pytest tests/a.py::test_1 tests/b.py::test_2": True,
        }
        bad = 0
        for c, exp in cases.items():
            got = bool(check(c, {"PWD": "/tmp/bd-tripwire-selftest"}))
            if got != exp:
                bad += 1; print(f"SELFTEST FAIL {c!r}: expected refused={exp} got={got}")
        assert check("venv/bin/python -m pytest tests/test_x.py", {"BD_INSTALL_DIR": "/x"}), "T5 env case"
        assert not check("venv/bin/python -m pytest tests/test_x.py", {"PWD": "/tmp/bd-tripwire-selftest"}), "T5 clean env"
        local_env = {"PWD": "/var/tmp/bd-seats/worker/r3"}
        positive = "pytest tests/a.py tests/b.py"
        negative = "pytest tests/a.py"
        assert check(positive, local_env), "T16 positive control"
        assert not check(negative, local_env), "T16 negative control"
        assert check("cp script.sh dest.sh", {}), "T17 positive control"
        assert not check("cp -p script.sh dest.sh", {}), "T17 negative control"
        assert check("cp --preserve=timestamps script.sh dest.sh", {}), "T17 REFUTE-1 escape: --preserve=timestamps keeps no mode"
        assert check("cp \"unterminated --preserve=timestamps script.sh dest.sh", {}), "T17 REFUTE-1 escape, unparseable-quote fallback"
        assert check("./bd-say.sh bd-pm-B 'done'", {}), "T18 positive control"
        assert not check("./bd-say.sh bd-pm-B 'done'; rc=$?", {}), "T18 negative control"
        worker_env = {"PWD": "/var/tmp/bd-seats/worker/r3", "BD_SEAT": "bd-agy-worker1"}
        assert not check("pytest tests/a.py::test_1 tests/a.py::test_2", worker_env), "T15/T16 same-file node IDs allowed"
        assert check("pytest tests/a.py::test_1 tests/b.py::test_2", worker_env), "T15/T16 multi-file node IDs refused"
        hits_det, det = check_detailed("git add .", {})
        assert "T1 git add -A/." in hits_det and len(det) > 0 and det[0]["rule_id"] == "T1", "check_detailed T1"
        log("SELFTEST", positive, "T16 positive control refused")
        log("SELFTEST", negative, "T16 negative control allowed")
        print("selftest", "FAIL" if bad else f"OK ({len(cases)+5} cases)"); sys.exit(1 if bad else 0)
    main()
