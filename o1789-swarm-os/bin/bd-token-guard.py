#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import os
import re
import shlex
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
MAX_ALLOWED_LINES = 100
AST_SERVER_URL = "http://127.0.0.1:8095"
BLOBS_DIR = Path("/var/tmp/bd-blobs")
USAGE_DB = Path("/home/mboyle/bd-persist/accounting/usage.sqlite")
SOURCE_EXTENSIONS = (".py", ".ts", ".js", ".jsx", ".tsx", ".json", ".yaml", ".yml", ".md", ".sh", ".bash", ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".sql", ".toml", ".ini", ".cfg", ".tsv", ".csv")
PYTEST_INFO_FLAGS = {"--help", "-h", "--version", "-V"}

def count_file_lines(file_path: str) -> Optional[int]:
    try:
        p = Path(file_path).resolve()
        if not p.is_file():
            return None
        with open(p, "rb") as f:
            lines = 0
            buf_size = 1024 * 1024
            read_bytes = f.raw.read if hasattr(f, "raw") else f.read
            buf = read_bytes(buf_size)
            while buf:
                lines += buf.count(b"\n")
                buf = read_bytes(buf_size)
            return lines
    except Exception:
        return None

def is_naked_pytest(command: str) -> Tuple[bool, str]:
    cmd = command.strip()
    if not cmd:
        return (False, "")
    if re.search(r"(?:^|[\s;&|])(?:bd-test|/home/mboyle/bin/bd-test)\b", cmd):
        return (False, "")
    if re.search(r"\|\s*(?:bd-pytest-digest|/home/mboyle/bin/bd-pytest-digest)\b", cmd):
        return (False, "")
    pytest_match = re.search(r"(?:^|[\s;&|])(?:python[0-9.]*\s+-m\s+pytest|py\.test|[^\s;&|]*/pytest|pytest)\b(?P<args>[^;&|]*)", cmd)
    if not pytest_match:
        return (False, "")
    args_str = pytest_match.group("args")
    try:
        tokens = shlex.split(args_str)
    except Exception:
        tokens = args_str.split()
    for tok in tokens:
        if tok in PYTEST_INFO_FLAGS:
            return (False, "")
    return (True, "NAKED PYTEST PROHIBITED (Rule 62/78 Token Guard): Naked pytest execution dumps massive raw "
        "tracebacks (avg ~1,940 tokens, up to 30,000 tokens) into context. "
        "Use 'bd-test [args]' or pipe output to 'bd-pytest-digest --pipe'.")

def is_full_file_read_command(command: str, cwd: str="") -> Tuple[bool, str]:
    cmd = command.strip()
    if not cmd:
        return (False, "")
    cat_match = re.search(r"(?:^|[\s;&|])(?P<prog>cat|bat|more|less)\s+(?P<args>[^|;&<>]+)", cmd)
    if cat_match:
        args_str = cat_match.group("args").strip()
        try:
            tokens = shlex.split(args_str)
        except Exception:
            tokens = args_str.split()
        for tok in tokens:
            if tok.startswith("-"):
                continue
            path_str = tok
            if cwd and (not os.path.isabs(path_str)):
                path_str = os.path.join(cwd, path_str)
            line_count = count_file_lines(path_str)
            if line_count is not None and line_count > MAX_ALLOWED_LINES:
                pipe_head = re.search(r"\|\s*head\s+(?:-n\s*(\d+)|-(\d+))", cmd)
                if pipe_head:
                    n_lines = int(pipe_head.group(1) or pipe_head.group(2) or 10)
                    if n_lines <= MAX_ALLOWED_LINES:
                        continue
                return (True, f"FULL-FILE READ PROHIBITED (Rule 58/80 Token Guard): Command dumps entire file "
                    f"'{tok}' ({line_count:,} lines > {MAX_ALLOWED_LINES} line ceiling). "
                    f"Full-file reads cause prompt bloat. Use 'ratf' MCP (ctx_slice) for AST slicing "
                    f"or pipe through 'head -n 50'.")
    head_match = re.search(r"(?:^|[\s;&|])head\s+(?:-n\s*(\d+)|-(\d+))\s+([^\s;&|<>]+)", cmd)
    if head_match:
        n_lines = int(head_match.group(1) or head_match.group(2) or 10)
        target = head_match.group(3)
        if n_lines > MAX_ALLOWED_LINES:
            return (True, f"OVERSIZED READ PROHIBITED (Rule 58/80 Token Guard): 'head -n {n_lines}' on '{target}' "
                f"exceeds the {MAX_ALLOWED_LINES} line threshold. Use bounded slicing or ratf ctx_slice.")
    return (False, "")

def evaluate_view_file(args: Dict[str, Any]) -> Tuple[bool, str]:
    file_path = args.get("AbsolutePath") or args.get("file_path") or args.get("path") or ""
    if not file_path:
        return (True, "")
    start_line = args.get("StartLine") or args.get("start_line") or args.get("offset")
    end_line = args.get("EndLine") or args.get("end_line") or args.get("limit")
    if start_line is not None and end_line is not None:
        try:
            span = int(end_line) - int(start_line) + 1
            if span > MAX_ALLOWED_LINES:
                return (False, f"OVERSIZED SLICE PROHIBITED (Token Guard): Requested range [{start_line}-{end_line}] "
                    f"is {span} lines (> {MAX_ALLOWED_LINES} limit). "
                    f"Reduce slice span to <= {MAX_ALLOWED_LINES} lines or use ratf MCP (ctx_slice) for AST symbols.")
            return (True, "")
        except (ValueError, TypeError):
            pass
    if start_line is not None and end_line is None:
        total_lines = count_file_lines(file_path)
        if total_lines is not None:
            try:
                remaining = total_lines - int(start_line) + 1
                if remaining > MAX_ALLOWED_LINES:
                    return (False, f"UNBOUNDED SLICE PROHIBITED (Token Guard): Reading from line {start_line} to EOF "
                        f"returns {remaining} lines (> {MAX_ALLOWED_LINES} limit). Specify EndLine <= {int(start_line) + MAX_ALLOWED_LINES}.")
            except (ValueError, TypeError):
                pass
    total_lines = count_file_lines(file_path)
    if total_lines is not None and total_lines > MAX_ALLOWED_LINES:
        return (False, f"FULL-FILE READ PROHIBITED (Rule 58/Token Guard): '{file_path}' has {total_lines:,} lines "
            f"(> {MAX_ALLOWED_LINES} line threshold). Reading entire files causes severe context bloating. "
            f"Use 'ratf' MCP (ctx_slice) to extract symbols/skeletons, or specify StartLine/EndLine <= {MAX_ALLOWED_LINES}.")
    return (True, "")

def evaluate_tool_call(name: str, args: Dict[str, Any], cwd: str="") -> Tuple[bool, str]:
    if name in ("view_file", "Read", "read_file", "read_resource"):
        allowed, reason = evaluate_view_file(args)
        if not allowed:
            return (False, reason)
    elif name in ("run_command", "Bash", "bash", "exec_command", "execute_command", "terminal"):
        command = args.get("CommandLine") or args.get("command") or ""
        cmd_cwd = args.get("Cwd") or args.get("cwd") or cwd
        is_bad_pytest, pytest_reason = is_naked_pytest(command)
        if is_bad_pytest:
            return (False, pytest_reason)
        is_bad_read, read_reason = is_full_file_read_command(command, cmd_cwd)
        if is_bad_read:
            return (False, read_reason)
    return (True, "")

def handle_hook_mode():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        payload = json.loads(raw)
    except Exception:
        sys.exit(0)
    name = ""
    args: Dict[str, Any] = {}
    cwd = ""
    if "toolCall" in payload or "tool_call" in payload:
        tc = payload.get("toolCall") or payload.get("tool_call") or {}
        name = tc.get("name", "")
        args = tc.get("args", {})
        cwd = args.get("Cwd", os.getcwd())
    else:
        name = payload.get("tool_name", "")
        args = payload.get("tool_input", {})
        cwd = payload.get("cwd", os.getcwd())
    allowed, reason = evaluate_tool_call(name, args, cwd)
    if not allowed:
        print(json.dumps({"decision": "deny", "reason": reason}))
        sys.stderr.write(f"[bd-token-guard] REFUSED: {reason}\n")
        sys.exit(2)
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)

def run_fleet_audit() -> Dict[str, Any]:
    if not USAGE_DB.exists():
        return {"error": "usage.sqlite not found"}
    conn = sqlite3.connect(str(USAGE_DB))
    rows = conn.execute('''
        SELECT provider, count(*), 
               SUM(json_extract(usage, '$.input_tokens')),
               SUM(COALESCE(json_extract(usage, '$.cached_input_tokens'), json_extract(usage, '$.cache_read_input_tokens'), 0)),
               SUM(json_extract(usage, '$.output_tokens'))
        FROM usage_responses
        GROUP BY provider
    ''').fetchall()
    providers = {}
    for r in rows:
        prov, cnt, in_tok, cached_tok, out_tok = r
        in_tok = in_tok or 0
        cached_tok = cached_tok or 0
        out_tok = out_tok or 0
        hit_pct = round(cached_tok / in_tok * 100, 2) if in_tok else 0.0
        providers[prov] = {"turns": cnt, "input_tokens": in_tok, "cached_tokens": cached_tok, "cache_hit_pct": hit_pct, "output_tokens": out_tok}
    out_samples = [r[0] for r in conn.execute("SELECT json_extract(usage, '$.output_tokens') FROM usage_responses "
        "WHERE json_extract(usage, '$.output_tokens') IS NOT NULL ORDER BY timestamp DESC LIMIT 20000").fetchall() if r[0] is not None]
    out_metrics = {}
    if out_samples:
        out_samples.sort()
        n = len(out_samples)
        gt_50 = sum((1 for x in out_samples if x > 50))
        out_metrics = {"sample_size": n, "p50": out_samples[int(n * 0.5)], "p90": out_samples[int(n * 0.9)], "p99": out_samples[int(n * 0.99)], "avg": round(sum(out_samples) / n, 1), "pct_over_50_tokens": round(gt_50 / n * 100, 2)}
    cas_metrics = {"blob_count": 0, "total_bytes": 0, "mb": 0.0, "est_tokens_saved": 0}
    if BLOBS_DIR.exists():
        try:
            files = [os.path.join(BLOBS_DIR, f) for f in os.listdir(BLOBS_DIR) if os.path.isfile(os.path.join(BLOBS_DIR, f))]
            total_bytes = sum((os.path.getsize(f) for f in files))
            cas_metrics = {"blob_count": len(files), "total_bytes": total_bytes, "mb": round(total_bytes / (1024 * 1024), 2), "est_tokens_saved": int(total_bytes / 3.6)}
        except Exception:
            pass
    return {"providers": providers, "output_metrics": out_metrics, "cas_metrics": cas_metrics}

def print_manifesto():
    manifesto = """
================================================================================
                    BOYLENET FLEET TOKEN OPTIMIZATION MANIFESTO
================================================================================

1. CORE FLEET AXIOMS:
   - "Output tokens cost 5x input tokens, and every response becomes next-turn context."
   - "Unbounded file reads and naked test dumps are fatal context pollutants."
   - "KV cache prefix thrashing destroys the 99% hit rate; frozen prefixes are law."

2. THE 5 FATAL TOKEN SINKS (RANKED BY IMPACT):
   Rank 1: Worktree & Prefix Cache Misses (Rule 83)
           • Cost: 40,000 - 150,000 cold tokens per turn penalty ($15.00/M vs $3.75/M).
           • Impact: Recomputing cache keys burns ~58.6M expensive cold tokens per 12h.
           • Remedy: Recycle persistent scratchpads in bd-local-wt; freeze system prefixes.
           • Net Savings: 75.0% cost reduction on cache misses; >99.0% cache retention.

   Rank 2: Full-File Reads vs AST Slicing (Rule 58 / ratf ctx_slice)
           • Cost: 3,000 - 25,000 tokens per module read into persistent history.
           • Impact: Swells context window from 25k to 350k+ tokens across 20 turns.
           • Remedy: Enforce ratf MCP (ctx_slice) symbol/skeleton extracts or <=100 line bounds.
           • Net Savings: 95.0% - 98.8% token reduction per source code inspection.

   Rank 3: Conversational Filler vs Rule 74 (<50 tok)
           • Cost: Unchecked outputs average 686.4 tokens/turn (p90: 1,441 tok).
           • Impact: Burns premium output quota ($75/M on Opus) + pollutes downstream turns.
           • Remedy: Enforce Rule 74 hard cap: <=50 output tokens (<STATUS> <path>).
           • Net Savings: 96.4% output token reduction (saves ~661 tokens/turn).

   Rank 4: Raw Test Dumps vs bd-pytest-digest (Rule 62/78)
           • Cost: Raw pytest failures dump 1,940 - 26,500 tokens of tracebacks into context.
           • Impact: Triggers premature compaction and context eviction.
           • Remedy: Wrap with bd-test or pipe to bd-pytest-digest (<=3 lines, <25 tokens).
           • Net Savings: 98.7% - 99.7% token reduction per test run.

   Rank 5: Unused Tool Schemas (H494)
           • Cost: Eagerly loading unneeded tools injects 13,000 - 36,500 tokens EVERY turn.
           • Impact: Artifact schema alone was 50KB (~13k tok); 99 MCP tools add 23.5k tok.
           • Remedy: Disallow Artifact on workers; prune unneeded MCP tools via lean_worker.
           • Net Savings: 13,000 - 36,500 tokens spared on every single request turn.

3. PROACTIVE ENFORCEMENT GUARDRAILS:
   - Tool calls intercepted pre-execution via bd-token-guard.py.
   - Naked pytest blocked unconditionally.
   - Reads exceeding 100 lines blocked with AST slicing guidance.
================================================================================
"""
    print(manifesto.strip())

def run_self_tests() -> bool:
    print("=== RUNNING BD-TOKEN-GUARD VERIFICATION TESTS ===")
    tests = [("T1: Naked pytest blocked", "run_command", {"CommandLine": "pytest tests/test_foo.py"}, False, "Naked pytest"), ("T2: Python -m pytest blocked", "run_command", {"CommandLine": "python3 -m pytest"}, False, "python3 -m pytest"), ("T3: Wrapped bd-test allowed", "run_command", {"CommandLine": "bd-test tests/test_foo.py"}, True, "bd-test invocation"), ("T4: Piped pytest-digest allowed", "run_command", {"CommandLine": "pytest tests/ | bd-pytest-digest --pipe"}, True, "piped pytest-digest"), ("T5: Pytest help flag allowed", "run_command", {"CommandLine": "pytest --help"}, True, "pytest --help"), ("T6: Cat large file (>100 lines) blocked", "run_command", {"CommandLine": "cat /home/mboyle/bin/bd-pytest-digest"}, False, "cat large file"), ("T7: Cat piped to head <=100 allowed", "run_command", {"CommandLine": "cat /home/mboyle/bin/bd-pytest-digest | head -n 50"}, True, "cat piped to head 50"), ("T8: View_file unbounded large file blocked", "view_file", {"AbsolutePath": "/home/mboyle/bin/bd-pytest-digest"}, False, "view_file large file"), ("T9: View_file bounded slice <=100 allowed", "view_file", {"AbsolutePath": "/home/mboyle/bin/bd-pytest-digest", "StartLine": 1, "EndLine": 50}, True, "bounded slice 50 lines"), ("T10: View_file oversized slice >100 blocked", "view_file", {"AbsolutePath": "/home/mboyle/bin/bd-pytest-digest", "StartLine": 1, "EndLine": 150}, False, "oversized slice 150 lines"), ("T11: View_file small file (<=100 lines) allowed", "view_file", {"AbsolutePath": "/home/mboyle/bin/pytest"}, True, "small file read")]
    passed = 0
    for t_id, t_name, t_args, expected_allow, desc in tests:
        allowed, reason = evaluate_tool_call(t_name, t_args)
        status = allowed == expected_allow
        if status:
            passed += 1
            print(f"  [PASS] {t_id}: {desc} -> allowed={allowed}")
        else:
            print(f"  [FAIL] {t_id}: {desc} -> expected {expected_allow}, got {allowed} (reason: {reason})")
    print(f"\nVerification Results: {passed}/{len(tests)} tests passed.")
    return passed == len(tests)

def main():
    if len(sys.argv) == 1 and (not sys.stdin.isatty()):
        handle_hook_mode()
        return
    parser = argparse.ArgumentParser(description="bd-token-guard -- Pre-execution Token Optimization Linter")
    subparsers = parser.add_subparsers(dest="subcommand")
    subparsers.add_parser("hook", help="Run in PreToolUse hook mode (reads JSON from stdin)")
    cmd_p = subparsers.add_parser("check-command", help="Check a shell command for token waste")
    cmd_p.add_argument("command", help="Shell command to evaluate")
    read_p = subparsers.add_parser("check-read", help="Check a file read request for token waste")
    read_p.add_argument("file_path", help="Path to file")
    read_p.add_argument("--start", type=int, default=None, help="Start line")
    read_p.add_argument("--end", type=int, default=None, help="End line")
    subparsers.add_parser("audit", help="Run empirical token waste audit across fleet data")
    subparsers.add_parser("manifesto", help="Print Fleet Token Optimization Manifesto")
    subparsers.add_parser("test", help="Run internal validation test suite")
    args = parser.parse_args()
    if args.subcommand == "hook":
        handle_hook_mode()
    elif args.subcommand == "check-command":
        allowed, reason = evaluate_tool_call("run_command", {"CommandLine": args.command})
        if allowed:
            print("[ALLOW] Command conforms to token guardrails.")
            sys.exit(0)
        else:
            print(f"[DENY] {reason}")
            sys.exit(2)
    elif args.subcommand == "check-read":
        t_args: Dict[str, Any] = {"AbsolutePath": args.file_path}
        if args.start is not None:
            t_args["StartLine"] = args.start
        if args.end is not None:
            t_args["EndLine"] = args.end
        allowed, reason = evaluate_tool_call("view_file", t_args)
        if allowed:
            print("[ALLOW] File read conforms to token guardrails.")
            sys.exit(0)
        else:
            print(f"[DENY] {reason}")
            sys.exit(2)
    elif args.subcommand == "audit":
        res = run_fleet_audit()
        print(json.dumps(res, indent=2))
    elif args.subcommand == "manifesto":
        print_manifesto()
    elif args.subcommand == "test":
        success = run_self_tests()
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
if __name__ == "__main__":
    main()
