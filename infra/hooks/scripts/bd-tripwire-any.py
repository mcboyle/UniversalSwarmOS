#!/usr/bin/env python3
"""bd-tripwire-any.py -- O908: ONE tripwire for three platforms (rule 54 parity).
Claude:  PreToolUse Bash  -> {"tool_name":"Bash","tool_input":{"command":...}}           exit 2 + stderr = refuse
Codex:   PreToolUse Bash  -> same shape as Claude (hooks.json)                              exit 2 + stderr = refuse
AGY:     PreToolUse run_command -> {"toolCall":{"name":"run_command","args":{"CommandLine":...}}}
         stdout {"decision":"deny","reason":...} = refuse, {"decision":"allow"} otherwise
Also guards WRITES under the main checkout (/home/mboyle/BulkDownloader) for non-integrator seats:
Claude/Codex Edit|Write|MultiEdit|NotebookEdit file_path, AGY write_to_file/replace_file_content/edit args, and any
shell command whose text names a redirect/cp/mv/sed -i into that path (O886 class: 6 restores in one day).

SYN-14 (HB-O1084):
  - Rule ID + pattern explainability on refusal
  - --explain / --dry-run CLI diagnostics
  - --sanctioned published shapes list
  - Tokenized shell/git arguments, word boundaries on mutating verbs (no merge-base or grep false hits)
  - Stream descriptor (2>&1, 2>/dev/null, >&2) false hit prevention
  - Same-file test node ID deduplication in T15/T16
"""
import json, os, re, sys

# Load sibling bd-tripwire-hook.py if present in local directory, else production path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SIBLING_HOOK = os.path.join(CURRENT_DIR, "bd-tripwire-hook.py")
HOOK_PATH = SIBLING_HOOK if os.path.exists(SIBLING_HOOK) else "/home/mboyle/bd-persist/harness/bd-tripwire-hook.py"
sys.path.insert(0, os.path.dirname(HOOK_PATH))
import importlib.util
spec = importlib.util.spec_from_file_location("trip", HOOK_PATH)
trip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trip)

MAIN = "/home/mboyle/BulkDownloader"
INTEGRATOR = re.compile(r"^(bd-integrator|bd-cx-trainer|bd-pm-|bd-cx-integrator)")
MUTATING_GIT = r"(checkout|reset|apply|am|merge|rebase|pull|commit|stash)(?![\w-])"
MUTATING_GIT_VERBS = {"checkout", "reset", "apply", "am", "merge", "rebase", "pull", "commit", "stash"}
GIT_GLOBAL_VAL = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
EXEMPT_DIRS = ("/dev/null", "/tmp", "/var/tmp", "/home/mboyle/bd-persist", "/home/mboyle/bd-cuts")
STREAM_REDIRECT = re.compile(r"^(?:[0-9]?>(?:&[0-9]|-)|>&[0-9])$")
DEVNULL_REDIRECT = re.compile(r"^(?:[0-9]?&?>+)/dev/null$")
REDIRECT_OPS = {">", ">>", "1>", "2>", "1>>", "2>>", "&>", "&>>"}

SANCTIONED_SHAPES = [
    ("git merge-base", "Read-only ancestry queries ('git merge-base', 'git -C .../BulkDownloader merge-base')"),
    ("same-file node IDs", "Running multiple test cases within the same test file ('pytest tests/<file>.py::<node1> tests/<file>.py::<node2>')"),
    ("stream redirects", "Descriptor/stream redirection ('2>&1', '1>&2', '>&2', '2>/dev/null', '>/dev/null') on read operations"),
    ("main checkout reads", "Read-only git queries under main checkout ('git status', 'git log', 'git diff', 'git show', 'git rev-parse', 'git describe', 'git cat-file')"),
    ("single-file pytest", "Local-cut pytest naming exactly one test file ('pytest tests/<file>.py')"),
    ("worktree harness tools", "Fleet harness tools managing worktrees ('bd-worker-precut.sh', 'bd-prep-one.sh', 'bd-wt-lane.sh')"),
    ("sanctioned override", "Prefixing authorized commands with BD_TRIPWIRE_OK='<reason>' (logged to tripwire.log)"),
]

def seat():
    return os.environ.get("BD_SEAT", "")

def is_target_in_main(target, in_main):
    if not target:
        return False
    target = os.path.expanduser(target)
    if any(target == ex or target.startswith(ex + "/") for ex in EXEMPT_DIRS):
        return False
    if target == MAIN or target.startswith(MAIN + "/"):
        return True
    if in_main and not target.startswith("/"):
        return True
    return False

def parse_git_subcommand(tokens):
    """Parses git tokens: returns (target_main: bool, subcommand: str | None)."""
    target_main = False
    subcommand = None
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            i += 1
            if i < len(tokens) and not subcommand:
                subcommand = tokens[i]
            break
        if tok == "-C" and i + 1 < len(tokens):
            val = os.path.expanduser(tokens[i+1])
            if val == MAIN or val.startswith(MAIN + "/"):
                target_main = True
            i += 2
            continue
        if tok.startswith("-C"):
            val = os.path.expanduser(tok[2:])
            if val == MAIN or val.startswith(MAIN + "/"):
                target_main = True
            i += 1
            continue
        if (tok == "--work-tree" or tok == "--git-dir") and i + 1 < len(tokens):
            val = os.path.expanduser(tokens[i+1])
            if val == MAIN or val.startswith(MAIN + "/"):
                target_main = True
            i += 2
            continue
        if tok.startswith("--work-tree=") or tok.startswith("--git-dir="):
            val = os.path.expanduser(tok.split("=", 1)[1])
            if val == MAIN or val.startswith(MAIN + "/"):
                target_main = True
            i += 1
            continue
        if tok in GIT_GLOBAL_VAL:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        subcommand = tok
        break
    return target_main, subcommand

def _tokenized_main_write_shell(cmd):
    segs = trip.command_segments(cmd)
    if segs is None:
        return None
    pwd = os.environ.get("PWD", "")
    in_main = bool(pwd == MAIN or pwd.startswith(MAIN + "/"))
    for seg in segs:
        if not seg:
            continue
        c = os.path.basename(seg[0])
        if c == "cd":
            target = seg[1] if len(seg) > 1 else ""
            if target == "--" and len(seg) > 2:
                target = seg[2]
            target = os.path.expanduser(target)
            if target == MAIN or target.startswith(MAIN + "/"):
                in_main = True
            elif target.startswith("/") or target.startswith("~"):
                in_main = False

        # Check for redirection targeting MAIN checkout
        i = 0
        while i < len(seg):
            tok = seg[i]
            if STREAM_REDIRECT.match(tok) or DEVNULL_REDIRECT.match(tok):
                i += 1
                continue
            if tok in REDIRECT_OPS:
                if i + 1 < len(seg):
                    dest = seg[i+1]
                    if is_target_in_main(dest, in_main):
                        return True, {
                            "rule_id": "T16",
                            "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
                            "pattern": f"file redirect ({tok}) targeting MAIN checkout",
                            "match": f"{tok} {dest}"
                        }
                    i += 2
                    continue
            for op in (">>", ">", "1>>", "1>", "2>>", "2>", "&>>", "&>"):
                if tok.startswith(op):
                    dest = tok[len(op):]
                    if dest and is_target_in_main(dest, in_main):
                        return True, {
                            "rule_id": "T16",
                            "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
                            "pattern": f"file redirect ({op}) targeting MAIN checkout",
                            "match": tok
                        }
                    break
            i += 1

        if c == "git":
            tgt_main, sub = parse_git_subcommand(seg)
            if (tgt_main or in_main) and sub in MUTATING_GIT_VERBS:
                return True, {
                    "rule_id": "T16",
                    "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
                    "pattern": f"git mutating subcommand '{sub}' targeting MAIN checkout",
                    "match": " ".join(seg[:5])
                }
        elif c == "sed":
            if any(a == "-i" or a.startswith("-i") for a in seg):
                if in_main or any(is_target_in_main(a, in_main) for a in seg[1:]):
                    return True, {
                        "rule_id": "T16",
                        "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
                        "pattern": "sed -i modifying files in MAIN checkout",
                        "match": " ".join(seg[:5])
                    }
        elif c == "tee":
            targets = [a for a in seg[1:] if not a.startswith("-") and not DEVNULL_REDIRECT.match(a) and a != "/dev/null"]
            if (in_main and targets) or any(is_target_in_main(a, in_main) for a in targets):
                return True, {
                    "rule_id": "T16",
                    "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
                    "pattern": "tee writing files in MAIN checkout",
                    "match": " ".join(seg[:5])
                }
        elif c in ("cp", "mv", "rsync"):
            args_no_opt = [a for a in seg[1:] if not a.startswith("-")]
            if args_no_opt and is_target_in_main(args_no_opt[-1], in_main):
                return True, {
                    "rule_id": "T16",
                    "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
                    "pattern": f"{c} target in MAIN checkout",
                    "match": " ".join(seg[:5])
                }
        elif c == "patch":
            if in_main or any(seg[j] == "-d" and is_target_in_main(seg[j+1], in_main) for j in range(len(seg)-1)):
                return True, {
                    "rule_id": "T16",
                    "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
                    "pattern": "patch modifying files in MAIN checkout",
                    "match": " ".join(seg[:5])
                }

    return False, None

def _regex_fallback_main_write_shell(cmd):
    # Strip descriptor redirects and /dev/null
    clean = re.sub(r"(?:[0-9]?>(?:&[0-9]|/dev/null\b)|>&[0-9]|&>/dev/null)", " ", cmd)
    m1 = re.search(r"(>\s*|>>\s*|\bcp\b[^|;&]*\s|\bmv\b[^|;&]*\s|\bsed\s+-i\b[^|;&]*\s|\btee\s+(-a\s+)?|\brsync\b[^|;&]*\s|\bpatch\b[^|;&]*-d\s*)" + re.escape(MAIN), clean)
    if m1:
        return True, {
            "rule_id": "T16",
            "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
            "pattern": "direct write/copy/edit targeting MAIN checkout",
            "match": m1.group(0).strip()
        }
    m2 = re.search(r"\bgit\b[^|;&]*\s+-C\s+['\"]?" + re.escape(MAIN) + r"['\"]?\s+[^|;&]*\b" + MUTATING_GIT, clean)
    if m2:
        return True, {
            "rule_id": "T16",
            "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
            "pattern": f"git -C MAIN mutating command ({MUTATING_GIT})",
            "match": m2.group(0).strip()
        }
    if re.search(r"\bcd\s+['\"]?" + re.escape(MAIN) + r"(?:/\S*)?['\"]?\s*(?:&&|;)", clean):
        m3_git = re.search(r"\bgit\s+[^|;&]*\b" + MUTATING_GIT, clean)
        if m3_git:
            return True, {
                "rule_id": "T16",
                "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
                "pattern": f"cd MAIN && git mutating command ({MUTATING_GIT})",
                "match": m3_git.group(0).strip()
            }
        m3_sed = re.search(r"\bsed\s+-i\b", clean)
        if m3_sed:
            return True, {
                "rule_id": "T16",
                "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
                "pattern": "cd MAIN && sed -i",
                "match": m3_sed.group(0).strip()
            }
        m3_tee = re.search(r"\btee\s+(?!/dev/null\b)", clean)
        if m3_tee:
            return True, {
                "rule_id": "T16",
                "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
                "pattern": "cd MAIN && tee",
                "match": m3_tee.group(0).strip()
            }
        m3_red = re.search(r">\s*(?!/(?:dev/null|tmp|var/tmp|home/mboyle/bd-persist|home/mboyle/bd-cuts)\b)\S+", clean)
        if m3_red:
            return True, {
                "rule_id": "T16",
                "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
                "pattern": "cd MAIN && file redirect",
                "match": m3_red.group(0).strip()
            }
    return False, None

def main_write_shell(cmd):
    """Detects writes into the MAIN checkout (/home/mboyle/BulkDownloader) from non-integrator seats.
    Returns (is_refused: bool, detail_dict: dict | None).
    Sanctioned read operations (merge-base, git log --grep=..., 2>&1 redirects, git status/diff) do NOT match."""
    pwd = os.environ.get("PWD", "")
    if MAIN not in cmd:  # SYN-14 fx1: any mention, incl. 'MAIN;' / 'MAIN>' / 'MAIN&&', goes to the tokenized check
        if not (pwd == MAIN or pwd.startswith(MAIN + "/")):
            return False, None
    if INTEGRATOR.match(seat()):
        return False, None

    res = _tokenized_main_write_shell(cmd)
    if res is not None:
        return res
    return _regex_fallback_main_write_shell(cmd)

def main_write_path(path):
    return bool(path) and (path == MAIN or path.startswith(MAIN + "/")) and not INTEGRATOR.match(seat())

def refuse_text(hits, details=None):
    lines = ["bd-tripwire: REFUSED -- " + "; ".join(hits) + "."]
    if details:
        lines.append("  [MATCHED PATTERN(S)]:")
        for d in details:
            if isinstance(d, dict):
                lines.append(f"    - [{d.get('rule_id', 'T?')}] pattern: {d.get('pattern')} | match: {d.get('match')}")
            else:
                lines.append(f"    - {d}")
    lines.append("These shapes have each cost a round before; fix the command "
                 "(BD_TRIPWIRE_OK='<why>' prefix overrides a shell shape; main-checkout writes are the integrator's lane, use your worktree).")
    return "\n".join(lines)

def detect_sanctioned_shapes(cmd):
    matches = []
    if "merge-base" in cmd:
        matches.append("git merge-base read-only ancestry query")
    if re.search(r"2>&1|2>/dev/null|>&2|1>&2", cmd):
        matches.append("stderr stream descriptor redirection (2>&1 / 2>/dev/null / >&2)")
    if "::" in cmd and "pytest" in cmd:
        matches.append("pytest test node ID selector")
    if re.search(r"\bgit\s+(?:-C\s+\S+\s+)?(status|log|diff|show|rev-parse|describe|cat-file)\b", cmd):
        matches.append("read-only git inspection")
    return matches

def explain_command(cmd):
    m_override = re.match(r"\s*BD_TRIPWIRE_OK=(['\"]?)(.+?)\1\s", cmd)
    hits, details = trip.check_detailed(cmd, os.environ) if hasattr(trip, "check_detailed") else (trip.check(cmd, os.environ) if cmd else [], [])
    refused_shell, shell_detail = main_write_shell(cmd)
    if refused_shell:
        hits.append("T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)")
        if shell_detail:
            details.append(shell_detail)

    print(f"TRIPWIRE EXPLAIN: {cmd!r}")
    if hits:
        print("DECISION: REFUSED" + (" (BYPASSABLE via override)" if m_override else ""))
        print("[MATCHED RULES & PATTERNS]:")
        for d in details:
            if isinstance(d, dict):
                print(f"  - [{d.get('rule_id', 'T?')}] {d.get('name')}")
                print(f"    Pattern: {d.get('pattern')}")
                print(f"    Matched: {d.get('match')}")
            else:
                print(f"  - Pattern Detail: {d}")
        if m_override:
            print(f"[ACTIVE OVERRIDE]: reason={m_override.group(2)!r}")
        print("[REMEDY]: Fix the command or prefix with BD_TRIPWIRE_OK='<why>' if authorized.")
        return 2
    else:
        print("DECISION: ALLOWED")
        sanctioned = detect_sanctioned_shapes(cmd)
        if sanctioned:
            print("[SANCTIONED SHAPES DETECTED]:")
            for s in sanctioned:
                print(f"  - {s}")
        print("No tripwire rules matched.")
        return 0

def print_sanctioned():
    print("SANCTIONED COMMAND SHAPES (FLEET TRIPWIRE POLICY):")
    for name, desc in SANCTIONED_SHAPES:
        print(f"  - {name}: {desc}")

def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("--explain", "--dry-run"):
            cmd = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
            if not cmd:
                print("Usage: bd-tripwire-any.py --explain <command>", file=sys.stderr)
                sys.exit(1)
            rc = explain_command(cmd)
            sys.exit(rc)
        elif arg == "--sanctioned":
            print_sanctioned()
            sys.exit(0)
        elif arg in ("--help", "-h"):
            print("Usage: bd-tripwire-any.py [--explain <cmd> | --dry-run <cmd> | --sanctioned | --help]")
            sys.exit(0)

    ev = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    hits = []
    details = []

    if "toolCall" in ev:  # AGY
        tc = ev.get("toolCall") or {}
        name = tc.get("name", "")
        args = tc.get("args") or {}
        if name == "run_command":
            cmd = args.get("CommandLine") or ""
            m = re.match(r"\s*BD_TRIPWIRE_OK=(['\"]?)(.+?)\1\s", cmd)
            hits, details = trip.check_detailed(cmd, os.environ) if hasattr(trip, "check_detailed") else (trip.check(cmd, os.environ) if cmd else [], [])
            refused_shell, shell_detail = main_write_shell(cmd)
            if refused_shell:
                hits.append("T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)")
                if shell_detail:
                    details.append(shell_detail)
            if hits and m:
                trip.log("OVERRIDE", cmd, str(hits))
                hits = []
            if hits:
                trip.log("REFUSED", cmd, str(hits) + (f" details={details}" if details else ""))
        else:
            for k in ("AbsolutePath", "TargetFile", "absolute_path", "file_path", "path"):
                target_val = str(args.get(k, ""))
                if main_write_path(target_val) and re.search(r"write|replace|edit|create|delete|move", name, re.I):
                    hits.append("T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)")
                    detail_item = {
                        "rule_id": "T16",
                        "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
                        "pattern": "file write tool targeting MAIN checkout path",
                        "match": f"{name} targeting {target_val}"
                    }
                    details.append(detail_item)
                    trip.log("REFUSED", f"{name} {target_val}", str(hits))
                    break
        print(json.dumps({"decision": "deny", "reason": refuse_text(hits, details)} if hits else {"decision": "allow"}))
        sys.exit(0)

    tool = ev.get("tool_name", "")
    ti = ev.get("tool_input") or {}  # Claude / Codex
    if tool == "Bash":
        cmd = ti.get("command") or ""
        refused_shell, shell_detail = main_write_shell(cmd) if cmd else (False, None)
        if refused_shell:
            trip.log("REFUSED", cmd, f"T16 main-checkout write: {shell_detail}")
            details = [shell_detail] if shell_detail else None
            print(refuse_text(["T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)"], details), file=sys.stderr)
            sys.exit(2)
        sys.exit(0)  # T1-T15 handled by bd-tripwire-hook.py

    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        target_path = str(ti.get("file_path") or ti.get("notebook_path") or "")
        if main_write_path(target_path):
            trip.log("REFUSED", f"{tool} {target_path}", "T16 main-checkout write")
            detail_item = {
                "rule_id": "T16",
                "name": "T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)",
                "pattern": "file edit/write targeting MAIN checkout path",
                "match": f"{tool} targeting {target_path}"
            }
            print(refuse_text(["T16 write into the MAIN CHECKOUT from a non-integrator seat (O886)"], [detail_item]), file=sys.stderr)
            sys.exit(2)
    sys.exit(0)

if __name__ == "__main__":
    main()
