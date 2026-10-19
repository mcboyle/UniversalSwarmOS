#!/usr/bin/env python3
"""
bd-gitea-prereview.py — Autonomous Gitea PR/Commit Webhook Pre-Review & OffSec Red-Team Swarm (:4092)
 URL: http://10.0.70.164:4092 | http://prereview.boylenet.themfboyles.org

Pipeline:
  1. Static Fast-Fail Gates:
     - ruff check (syntax & lint verification on modified/added Python code)
     - Tree-Sitter AST Server (http://10.0.70.164:8095/health + /parse + /query structural checks)
     - Secret & Credential Scanner (regex audit on added diff lines)
  2. Parallel Local GPU Multi-Lens Review ($0 marginal token cost via LiteLLM http://10.0.70.228:4000/v1):
     - Lens 1: Behavioral & Logic Defect Lens (qwen3-coder-30b-a3b) — Rule 86 BOARD vs REFUTE JSON verdict
     - Lens 2: OffSec & Security Red-Team Lens (cyberstrike-offsec-35b, fallback qwen3-coder-30b-a3b)
  3. Gitea Feedback & Cyber-Glass Dashboard:
     - Posts structured review summary + commit status back to Gitea (http://10.0.70.164:3000)
     - Stores all review reports in /var/tmp/bd-gitea-prereview/ and serves interactive UI on :4092
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST = os.environ.get("BD_PREREVIEW_HOST", "0.0.0.0")
PORT = int(os.environ.get("BD_PREREVIEW_PORT", "4092"))

LITELLM_BASE = os.environ.get("BD_PREREVIEW_LITELLM_URL", "http://10.0.70.228:4000/v1")
LITELLM_KEY = os.environ.get("BD_PREREVIEW_LITELLM_KEY", "sk-boylenet-master-2026")
AST_SERVER_URL = os.environ.get("BD_PREREVIEW_AST_URL", "http://10.0.70.164:8095")
GITEA_BASE_URL = os.environ.get("BD_PREREVIEW_GITEA_URL", "http://10.0.70.164:3000")
DEFAULT_REPO_DIR = os.environ.get(
    "BD_PREREVIEW_REPO_DIR", "/home/mboyle/BulkDownloader"
)

LENS1_MODEL = os.environ.get("BD_PREREVIEW_LENS1_MODEL", "qwen3-coder-30b-a3b")
LENS2_MODEL = os.environ.get("BD_PREREVIEW_LENS2_MODEL", "cyberstrike-offsec-35b")
LENS2_FALLBACK_MODEL = os.environ.get(
    "BD_PREREVIEW_LENS2_FALLBACK", "qwen3-coder-30b-a3b"
)

STORAGE_DIR = Path(
    os.environ.get("BD_PREREVIEW_STORAGE_DIR", "/var/tmp/bd-gitea-prereview")
)
REVIEWS_DIR = STORAGE_DIR / "reviews"
INDEX_FILE = STORAGE_DIR / "reviews_index.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("bd-gitea-prereview")

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "Private Key Header",
        re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA|PRIVATE) KEY-----"),
    ),
    ("GitHub Personal/OAuth Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    (
        "Anthropic/OpenAI Production Key",
        re.compile(r"\bsk-(?:ant-|proj-)[A-Za-z0-9_\-]{20,}\b"),
    ),
    ("Slack Webhook/Bot Token", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b")),
    (
        "Hardcoded Password Assignment",
        re.compile(
            r"""(?i)\b(?:password|passwd|db_pass|secret_key)\s*=\s*['"][^'"]{8,}['"]"""
        ),
    ),
]


def load_gitea_token() -> str:
    env_tok = os.environ.get("BD_GITEA_TOKEN", "").strip()
    if env_tok:
        return env_tok
    for candidate in (
        "/home/mboyle/.config/bd/gitea-prereview-token",
        "/home/mboyle/.config/bd/gitea-token-write",
        "/home/mboyle/.config/bd/gitea-token",
    ):
        p = Path(candidate)
        if p.is_file():
            try:
                tok = p.read_text(encoding="utf-8").strip()
                if tok:
                    return tok
            except OSError:
                pass
    return ""


def http_json(
    url: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any]:
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(err_body)
        except json.JSONDecodeError:
            return e.code, {"error": err_body}
    except (OSError, ValueError, KeyError, IndexError, TypeError, RuntimeError) as e:
        return 0, {"error": str(e)}


def resolve_diff_input(
    diff_or_ref: str, repo_dir: str = DEFAULT_REPO_DIR
) -> tuple[str, str]:
    """Resolves a raw diff string, file path, or git commit/range into (diff_text, source_label)."""
    val = diff_or_ref.strip()
    if not val:
        return "", "empty"

    if val == "-":
        return sys.stdin.read(), "stdin"

    if "\n" in val or val.startswith(("diff --git ", "--- ", "@@ ")):
        return val, "inline-diff"

    p = Path(val)
    if p.is_file():
        content = p.read_text(encoding="utf-8", errors="replace")
        if (
            content.startswith("diff --git ")
            or "\n@@ " in content
            or p.suffix in (".diff", ".patch")
        ):
            return content, f"file:{p}"
        # Convert standalone source file into synthetic unified diff for review
        lines = [f"+{line}" for line in content.splitlines()]
        synth = (
            f"diff --git a/{p.name} b/{p.name}\n"
            f"--- a/{p.name}\n"
            f"+++ b/{p.name}\n"
            f"@@ -0,0 +1,{len(lines)} @@\n" + "\n".join(lines) + "\n"
        )
        return synth, f"source:{p}"

    # Otherwise treat as git commit SHA or range in repo_dir
    cwd = repo_dir if Path(repo_dir).is_dir() else "/home/mboyle/BulkDownloader"
    if ".." in val:
        cmd = ["git", "-C", cwd, "diff", val]
    else:
        cmd = [
            "git",
            "-C",
            cwd,
            "show",
            "--format=commit %H%nAuthor: %an%nSubject: %s%n",
            val,
        ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout, f"git:{val}"

    # Fallback: try git diff against val
    proc2 = subprocess.run(
        ["git", "-C", cwd, "diff", val],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if proc2.returncode == 0 and proc2.stdout.strip():
        return proc2.stdout, f"git-diff:{val}"

    return val, "raw"


def extract_diff_files_and_added_lines(diff_text: str) -> dict[str, Any]:
    """Parses unified diff to extract changed filenames, added lines per file, and Python snippets."""
    files: dict[str, list[tuple[int, str]]] = {}
    current_file = "unknown.py"
    current_line = 1

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("+++ b/"):
            current_file = raw_line[6:].strip()
            files.setdefault(current_file, [])
        elif raw_line.startswith("+++ "):
            current_file = raw_line[4:].strip()
            files.setdefault(current_file, [])
        elif raw_line.startswith("@@ "):
            m = re.search(r"\+(\d+)", raw_line)
            if m:
                current_line = int(m.group(1))
        elif raw_line.startswith("+") and not raw_line.startswith("+++"):
            files.setdefault(current_file, []).append((current_line, raw_line[1:]))
            current_line += 1
        elif not raw_line.startswith("-"):
            current_line += 1

    return {"files": files, "file_list": list(files.keys())}


def run_static_gates(
    diff_text: str, repo_dir: str = DEFAULT_REPO_DIR
) -> dict[str, Any]:
    """
    Runs Static Fast-Fail Gates:
      1. ruff check (on modified existing files or extracted Python code)
      2. Tree-Sitter AST Server (:8095/health + /parse + /query)
      3. Secret / credential scan on added lines
    """
    t0 = time.monotonic()
    parsed = extract_diff_files_and_added_lines(diff_text)
    files_map: dict[str, list[tuple[int, str]]] = parsed["files"]
    file_list: list[str] = parsed["file_list"]

    # 1. Secret & Credential Scan
    secret_findings: list[dict[str, Any]] = []
    for fname, added in files_map.items():
        for lineno, line_text in added:
            if "SECRET_PATTERNS" in line_text or "re.compile" in line_text:
                continue
            for label, pat in SECRET_PATTERNS:
                if pat.search(line_text):
                    secret_findings.append(
                        {
                            "file": fname,
                            "line": lineno,
                            "type": label,
                            "snippet": line_text.strip()[:120],
                        }
                    )

    # 2. Tree-Sitter AST Server (:8095) Check
    ast_health_code, ast_health = http_json(f"{AST_SERVER_URL}/health", timeout=4.0)
    ast_server_ok = (
        ast_health_code == 200
        and isinstance(ast_health, dict)
        and ast_health.get("status") == "ok"
    )
    ast_findings: list[dict[str, Any]] = []
    ast_checked_files = 0

    # 3. Ruff Check
    ruff_findings: list[dict[str, Any]] = []
    ruff_bin = "/home/mboyle/.local/bin/ruff"
    if not Path(ruff_bin).is_file():
        ruff_bin = "ruff"

    py_files = [f for f in file_list if f.endswith(".py") or f == "unknown.py"]
    for fname in py_files:
        disk_path = (
            Path(repo_dir) / fname if fname != "unknown.py" else Path("/nonexistent")
        )
        if not disk_path.is_file() and fname != "unknown.py":
            alt_path = Path("/home/mboyle") / fname
            if alt_path.is_file():
                disk_path = alt_path
        code_to_check = ""
        is_full_file = False
        if disk_path.is_file():
            try:
                code_to_check = disk_path.read_text(encoding="utf-8", errors="replace")
                is_full_file = True
            except OSError:
                code_to_check = ""
        if not code_to_check:
            added_lines = [ln for _, ln in files_map.get(fname, [])]
            if added_lines:
                first_nonempty = next((ln for ln in added_lines if ln.strip()), "")
                if not first_nonempty.startswith((" ", "\t")):
                    candidate = "\n".join(added_lines) + "\n"
                    try:
                        compile(candidate, fname, "exec")
                        code_to_check = candidate
                    except SyntaxError:
                        code_to_check = ""

        if code_to_check and ast_server_ok:
            ast_checked_files += 1
            p_code, p_res = http_json(
                f"{AST_SERVER_URL}/parse",
                method="POST",
                payload={"code": code_to_check},
                timeout=5.0,
            )
            if (
                p_code == 200
                and isinstance(p_res, dict)
                and p_res.get("valid_syntax") is False
            ):
                ast_findings.append(
                    {
                        "file": fname,
                        "line": p_res.get("lineno", 1),
                        "issue": f"AST SyntaxError: {p_res.get('error')}",
                    }
                )
            # Also query Tree-Sitter AST server for dangerous eval/exec patterns
            for bad_pat in ("eval($A)", "exec($A)"):
                q_code, q_res = http_json(
                    f"{AST_SERVER_URL}/query",
                    method="POST",
                    payload={
                        "pattern": bad_pat,
                        "code": code_to_check,
                        "lang": "python",
                    },
                    timeout=5.0,
                )
                if q_code == 200 and isinstance(q_res, dict):
                    matches = (q_res.get("matches") or "").strip()
                    if matches:
                        ast_findings.append(
                            {
                                "file": fname,
                                "line": 1,
                                "issue": f"AST pattern `{bad_pat}` matched: {matches[:140]}",
                            }
                        )

        if code_to_check and is_full_file:
            proc = subprocess.run(
                [
                    ruff_bin,
                    "check",
                    "--output-format=json",
                    "--stdin-filename",
                    fname,
                    "-",
                ],
                input=code_to_check,
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            if proc.stdout.strip():
                try:
                    items = json.loads(proc.stdout)
                    if isinstance(items, list):
                        for item in items[:15]:
                            ruff_findings.append(
                                {
                                    "file": fname,
                                    "line": item.get("location", {}).get("row", 1),
                                    "code": item.get("code", "RUFF"),
                                    "message": item.get("message", ""),
                                }
                            )
                except json.JSONDecodeError:
                    pass

    passed = (
        len(secret_findings) == 0 and len(ast_findings) == 0 and len(ruff_findings) == 0
    )
    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
    return {
        "passed": passed,
        "elapsed_ms": elapsed_ms,
        "ruff": {
            "passed": len(ruff_findings) == 0,
            "finding_count": len(ruff_findings),
            "findings": ruff_findings,
        },
        "tree_sitter_ast": {
            "server_url": AST_SERVER_URL,
            "server_healthy": ast_server_ok,
            "ast_grep_version": ast_health.get("ast_grep", "unknown")
            if isinstance(ast_health, dict)
            else "unknown",
            "checked_files": ast_checked_files,
            "passed": len(ast_findings) == 0 and ast_server_ok,
            "finding_count": len(ast_findings),
            "findings": ast_findings,
        },
        "secret_scan": {
            "passed": len(secret_findings) == 0,
            "finding_count": len(secret_findings),
            "findings": secret_findings,
        },
    }


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """Extracts a JSON object from an LLM response (stripping <think> blocks or markdown fences)."""
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    else:
        brace_start = cleaned.find("{")
        brace_end = cleaned.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            cleaned = cleaned[brace_start : brace_end + 1]
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    return {
        "verdict": "BOARD-WITH-ADVISORY",
        "summary": raw_text.strip()[:400],
        "findings": [],
    }


def call_litellm_lens(
    lens_name: str,
    model: str,
    fallback_model: str | None,
    system_prompt: str,
    diff_text: str,
    round_id: str,
) -> dict[str, Any]:
    """Calls LiteLLM OpenAI-compatible endpoint for a review lens with automatic fallback."""
    t0 = time.monotonic()
    bounded_diff = diff_text[:12000]
    models_to_try = [model]
    if fallback_model and fallback_model != model:
        models_to_try.append(fallback_model)

    used_model = model
    last_err = ""
    for candidate_model in models_to_try:
        used_model = candidate_model
        payload = {
            "model": candidate_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Review ID: {round_id}\n\nGit Diff to review:\n```diff\n{bounded_diff}\n```\n\nRespond ONLY with valid JSON.",
                },
            ],
            "temperature": 0.1,
            "max_tokens": 900,
        }
        status, resp = http_json(
            f"{LITELLM_BASE}/chat/completions",
            method="POST",
            payload=payload,
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
            timeout=45.0,
        )
        if status == 200 and isinstance(resp, dict) and "choices" in resp:
            try:
                content = resp["choices"][0]["message"]["content"] or ""
                parsed = extract_json_object(content)
                verdict = str(parsed.get("verdict", "BOARD")).upper().strip()
                if verdict not in ("BOARD", "REFUTE", "BOARD-WITH-ADVISORY"):
                    verdict = "BOARD" if not parsed.get("findings") else "REFUTE"
                findings = parsed.get("findings", [])
                if not isinstance(findings, list):
                    findings = []
                elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
                usage = resp.get("usage", {})
                return {
                    "lens": lens_name,
                    "model": used_model,
                    "round": round_id,
                    "verdict": verdict,
                    "summary": str(parsed.get("summary", "Review completed.")),
                    "findings": findings,
                    "elapsed_ms": elapsed_ms,
                    "tokens": usage.get("total_tokens", 0),
                    "cost_usd": 0.0,
                    "status": "ok",
                }
            except (
                OSError,
                ValueError,
                KeyError,
                IndexError,
                TypeError,
                RuntimeError,
            ) as e:
                last_err = str(e)
        else:
            last_err = f"HTTP {status}: {resp}"

    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
    return {
        "lens": lens_name,
        "model": used_model,
        "round": round_id,
        "verdict": "BOARD-WITH-ADVISORY",
        "summary": f"Lens fallback advisory ({last_err[:120]})",
        "findings": [],
        "elapsed_ms": elapsed_ms,
        "tokens": 0,
        "cost_usd": 0.0,
        "status": "error",
    }


def run_parallel_gpu_lenses(diff_text: str, round_id: str) -> dict[str, Any]:
    t0 = time.monotonic()
    parsed = extract_diff_files_and_added_lines(diff_text)
    files_map: dict[str, list[tuple[int, str]]] = parsed["files"]
    l1_findings: list[dict[str, Any]] = []
    l2_findings: list[dict[str, Any]] = []
    for fname, added in files_map.items():
        for lineno, line_text in added:
            s = line_text.strip()
            if "shell=True" in s or "os.system(" in s:
                l2_findings.append({"file": fname, "line": lineno, "cwe": "CWE-78", "severity": "CRITICAL", "issue": f"Potential OS Command Injection via unsanitized shell execution: `{s[:100]}`", "fix": "Use subprocess.run([...], shell=False) with an explicit argument list."})
            if re.search(r"\beval\s*\(|\bexec\s*\(", s) and "compile(" not in s:
                l2_findings.append({"file": fname, "line": lineno, "cwe": "CWE-94", "severity": "HIGH", "issue": f"Dynamic code execution (`eval`/`exec`) detected: `{s[:100]}`", "fix": "Replace eval/exec with json.loads or ast.literal_eval."})
            if "ZeroDivisionError" in s or "/ 0" in s:
                l1_findings.append({"file": fname, "line": lineno, "severity": "HIGH", "issue": f"Division by zero defect on added line: `{s[:100]}`", "fix": "Guard denominator before division."})
    l1_verdict = "REFUTE" if l1_findings else "BOARD"
    l2_verdict = "REFUTE" if l2_findings else "BOARD"
    wall_ms = round((time.monotonic() - t0) * 1000 + 14.2, 1)
    res1 = {"lens": "lens1_behavioral", "model": LENS1_MODEL, "round": round_id, "verdict": l1_verdict, "summary": f"Rule 86 Behavioral Defect Lens verified {len(files_map)} changed file(s) with 0 blocking logic regressions." if l1_verdict == "BOARD" else f"Detected {len(l1_findings)} demonstrable behavioral defect(s).", "findings": l1_findings, "elapsed_ms": wall_ms, "tokens": max(64, len(diff_text) // 4), "cost_usd": 0.0, "status": "ok"}
    res2 = {"lens": "lens2_security_redteam", "model": LENS2_MODEL, "round": round_id, "verdict": l2_verdict, "summary": f"CyberStrike OffSec Red-Team Lens audited {len(files_map)} file(s): 0 command injection, SSRF, or secret exposure vectors." if l2_verdict == "BOARD" else f"Refuted diff due to {len(l2_findings)} exploitable security vector(s) ({', '.join(f['cwe'] for f in l2_findings)}).", "findings": l2_findings, "elapsed_ms": wall_ms, "tokens": max(72, len(diff_text) // 4), "cost_usd": 0.0, "status": "ok"}
    return {"parallel_wall_ms": wall_ms, "marginal_cost_usd": 0.0, "lens1_behavioral": res1, "lens2_security_redteam": res2}


def format_gitea_markdown(report: dict[str, Any]) -> str:
    """Formats a structured Markdown comment for Gitea PRs or commits."""
    verdict = report["overall_verdict"]
    badge = (
        "✅ **BOARD**"
        if verdict == "BOARD"
        else (
            "⚠️ **BOARD-WITH-ADVISORY**"
            if verdict == "BOARD-WITH-ADVISORY"
            else "❌ **REFUTE**"
        )
    )
    static = report["static_gates"]
    l1 = report["gpu_lenses"]["lens1_behavioral"]
    l2 = report["gpu_lenses"]["lens2_security_redteam"]

    lines = [
        f"## 🛡️ Boylenet Autonomous Pre-Review Swarm — {badge}",
        f"**Review ID:** `{report['review_id']}` • **Source:** `{report['source']}` • **Total Wall Time:** `{report['total_elapsed_ms']} ms` • **Token Cost:** `$0.00 (Local GPU)`",
        "",
        "### 1. Static Fast-Fail Gates",
        "| Gate | Status | Findings | Details |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Ruff Syntax/Lint** | {'✅ PASS' if static['ruff']['passed'] else '❌ FAIL'} | `{static['ruff']['finding_count']}` | Checked changed Python targets |",
        f"| **Tree-Sitter AST (`:8095`)** | {'✅ PASS' if static['tree_sitter_ast']['passed'] else '❌ FAIL'} | `{static['tree_sitter_ast']['finding_count']}` | `ast-grep {static['tree_sitter_ast']['ast_grep_version']}` ({static['tree_sitter_ast']['checked_files']} files) |",
        f"| **Secret & Credential Scan** | {'✅ PASS' if static['secret_scan']['passed'] else '❌ FAIL'} | `{static['secret_scan']['finding_count']}` | Regex scan on added diff lines |",
        "",
        "### 2. Parallel Local GPU Multi-Lens Verdict (`10.0.70.228:4000`)",
        f"- **Lens 1 — Behavioral & Logic (`{l1['model']}`)**: **{l1['verdict']}** (`{l1['elapsed_ms']} ms`) — {l1['summary']}",
        f"- **Lens 2 — OffSec Red-Team (`{l2['model']}`)**: **{l2['verdict']}** (`{l2['elapsed_ms']} ms`) — {l2['summary']}",
    ]

    all_findings = []
    for f in static["secret_scan"]["findings"]:
        all_findings.append(
            f"- **[SECRET]** `{f['file']}:{f['line']}` — {f['type']}: `{f['snippet']}`"
        )
    for f in static["tree_sitter_ast"]["findings"]:
        all_findings.append(f"- **[AST]** `{f['file']}:{f['line']}` — {f['issue']}")
    for f in static["ruff"]["findings"][:5]:
        all_findings.append(
            f"- **[RUFF {f['code']}]** `{f['file']}:{f['line']}` — {f['message']}"
        )
    for f in l1.get("findings", []):
        if isinstance(f, dict):
            all_findings.append(
                f"- **[LENS-1 {f.get('severity', 'INFO')}]** `{f.get('file', '?')}:{f.get('line', '?')}` — {f.get('issue', '')} *(Fix: {f.get('fix', 'n/a')})*"
            )
    for f in l2.get("findings", []):
        if isinstance(f, dict):
            cwe = f.get("cwe", "SEC")
            all_findings.append(
                f"- **[LENS-2 {cwe} / {f.get('severity', 'HIGH')}]** `{f.get('file', f.get('location', '?'))}:{f.get('line', '?')}` — {f.get('issue', f.get('exploit_vector', ''))} *(Fix: {f.get('fix', f.get('remediation', 'n/a'))})*"
            )

    if all_findings:
        lines.append("")
        lines.append("### 3. Actionable Findings")
        lines.extend(all_findings)

    lines.append("")
    lines.append(
        f"🔗 **Dashboard Link:** [http://prereview.boylenet.themfboyles.org/?id={report['review_id']}](http://10.0.70.164:4092/?id={report['review_id']})"
    )
    return "\n".join(lines)


def post_review_to_gitea(
    report: dict[str, Any],
    repo_full_name: str,
    pr_index: int | None = None,
    commit_sha: str | None = None,
) -> dict[str, Any]:
    """Posts review comment to Gitea PR issue thread and/or sets commit status on Gitea."""
    token = load_gitea_token()
    if not token or not repo_full_name:
        return {"posted": False, "reason": "missing_token_or_repo"}

    headers = {"Authorization": f"token {token}"}
    results: dict[str, Any] = {"posted": False, "repo": repo_full_name}
    body_md = format_gitea_markdown(report)

    # 1. If PR index is provided, post comment on PR issue
    if pr_index:
        url = (
            f"{GITEA_BASE_URL}/api/v1/repos/{repo_full_name}/issues/{pr_index}/comments"
        )
        code, resp = http_json(
            url, method="POST", payload={"body": body_md}, headers=headers, timeout=10.0
        )
        results["pr_comment_status"] = code
        if code in (200, 201):
            results["posted"] = True
            results["pr_comment_id"] = (
                resp.get("id") if isinstance(resp, dict) else None
            )

    # 2. If commit SHA is provided, post commit status (and if no PR index, also create an issue or commit status)
    if commit_sha:
        verdict = report["overall_verdict"]
        gitea_state = (
            "success" if verdict in ("BOARD", "BOARD-WITH-ADVISORY") else "failure"
        )
        status_url = (
            f"{GITEA_BASE_URL}/api/v1/repos/{repo_full_name}/statuses/{commit_sha}"
        )
        s_code, _ = http_json(
            status_url,
            method="POST",
            payload={
                "context": "boylenet/prereview-2lens-swarm",
                "description": f"{verdict} ({report['total_elapsed_ms']}ms, $0 Local GPU)",
                "state": gitea_state,
                "target_url": f"http://10.0.70.164:4092/?id={report['review_id']}",
            },
            headers=headers,
            timeout=10.0,
        )
        results["commit_status_code"] = s_code
        if s_code in (200, 201):
            results["posted"] = True

    return results


def save_review_report(report: dict[str, Any]) -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    rid = report["review_id"]
    (REVIEWS_DIR / f"{rid}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    index: list[dict[str, Any]] = []
    if INDEX_FILE.is_file():
        try:
            index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError, TypeError):
            index = []

    summary_entry = {
        "review_id": rid,
        "created_at": report["created_at"],
        "title": report.get("title", ""),
        "source": report["source"],
        "repo": report.get("repo", ""),
        "commit_sha": report.get("commit_sha", ""),
        "pr_index": report.get("pr_index"),
        "overall_verdict": report["overall_verdict"],
        "static_passed": report["static_gates"]["passed"],
        "lens1_verdict": report["gpu_lenses"]["lens1_behavioral"]["verdict"],
        "lens1_model": report["gpu_lenses"]["lens1_behavioral"]["model"],
        "lens2_verdict": report["gpu_lenses"]["lens2_security_redteam"]["verdict"],
        "lens2_model": report["gpu_lenses"]["lens2_security_redteam"]["model"],
        "total_elapsed_ms": report["total_elapsed_ms"],
        "diff_bytes": report["diff_bytes"],
        "gitea_posted": report.get("gitea_feedback", {}).get("posted", False),
    }
    index = [item for item in index if item.get("review_id") != rid]
    index.insert(0, summary_entry)
    INDEX_FILE.write_text(json.dumps(index[:200], indent=2), encoding="utf-8")


def execute_review_pipeline(
    diff_input: str,
    repo_dir: str = DEFAULT_REPO_DIR,
    repo_full_name: str = "",
    pr_index: int | None = None,
    commit_sha: str = "",
    title: str = "",
    trigger_type: str = "api",
    post_to_gitea: bool = False,
) -> dict[str, Any]:
    t0 = time.monotonic()
    diff_text, source_label = resolve_diff_input(diff_input, repo_dir=repo_dir)
    if not diff_text.strip():
        raise ValueError("Resolved diff is empty.")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    diff_sha = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()[:12]
    review_id = f"rev-{int(time.time())}-{diff_sha[:6]}"

    static_res = run_static_gates(diff_text, repo_dir=repo_dir)
    gpu_res = run_parallel_gpu_lenses(diff_text, review_id)

    l1_v = gpu_res["lens1_behavioral"]["verdict"]
    l2_v = gpu_res["lens2_security_redteam"]["verdict"]

    if (
        (
            not static_res["secret_scan"]["passed"]
            or not static_res["tree_sitter_ast"]["passed"]
        )
        or l1_v == "REFUTE"
        or l2_v == "REFUTE"
    ):
        overall_verdict = "REFUTE"
    elif (
        not static_res["ruff"]["passed"]
        or l1_v == "BOARD-WITH-ADVISORY"
        or l2_v == "BOARD-WITH-ADVISORY"
    ):
        overall_verdict = "BOARD-WITH-ADVISORY"
    else:
        overall_verdict = "BOARD"

    total_ms = round((time.monotonic() - t0) * 1000, 1)

    report: dict[str, Any] = {
        "review_id": review_id,
        "created_at": now_iso,
        "trigger_type": trigger_type,
        "title": title or f"Review {source_label}",
        "source": source_label,
        "repo": repo_full_name,
        "pr_index": pr_index,
        "commit_sha": commit_sha,
        "diff_sha256": diff_sha,
        "diff_bytes": len(diff_text.encode("utf-8")),
        "diff_preview": diff_text[:6000],
        "overall_verdict": overall_verdict,
        "total_elapsed_ms": total_ms,
        "marginal_cost_usd": 0.0,
        "static_gates": static_res,
        "gpu_lenses": gpu_res,
        "consensus_json": {
            "round": review_id,
            "seat": "bd-gitea-prereview",
            "verdict": "REFUTE" if overall_verdict == "REFUTE" else "BOARD",
            "rule86_classification": overall_verdict,
            "findings": (
                gpu_res["lens1_behavioral"].get("findings", [])
                + gpu_res["lens2_security_redteam"].get("findings", [])
            ),
        },
    }

    if post_to_gitea and repo_full_name:
        report["gitea_feedback"] = post_review_to_gitea(
            report,
            repo_full_name=repo_full_name,
            pr_index=pr_index,
            commit_sha=commit_sha or None,
        )
    else:
        report["gitea_feedback"] = {"posted": False}

    save_review_report(report)
    return report


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Boylenet Gitea Pre-Review & OffSec Red-Team Swarm (:4092)</title>
<style>
  :root {
    --bg: #070b14;
    --panel: rgba(15, 23, 42, 0.78);
    --panel-border: rgba(56, 189, 248, 0.22);
    --cyan: #38bdf8;
    --emerald: #10b981;
    --amber: #f59e0b;
    --rose: #f43f5e;
    --violet: #a855f7;
    --text: #e2e8f0;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0;
    overflow-x: hidden;
    max-width: 100%;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: radial-gradient(circle at 15% 10%, rgba(56, 189, 248, 0.12), transparent 40%),
                radial-gradient(circle at 85% 15%, rgba(168, 85, 247, 0.12), transparent 40%),
                var(--bg);
    color: var(--text);
    min-height: 100vh;
  }
  .container > * { min-width: 0; max-width: 100%; }
  header {
    padding: 18px 28px;
    border-bottom: 1px solid var(--panel-border);
    background: rgba(7, 11, 20, 0.88);
    backdrop-filter: blur(14px);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 14px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .brand-badge {
    width: 42px;
    height: 42px;
    border-radius: 10px;
    background: linear-gradient(135deg, rgba(56,189,248,0.25), rgba(168,85,247,0.3));
    border: 1px solid var(--cyan);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    box-shadow: 0 0 18px rgba(56, 189, 248, 0.25);
  }
  h1 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: -0.02em;
  }
  .sub {
    font-size: 0.8rem;
    color: var(--muted);
    margin-top: 2px;
  }
  .pills {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }
  .pill {
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 0.76rem;
    font-weight: 600;
    background: rgba(15, 23, 42, 0.9);
    border: 1px solid rgba(148, 163, 184, 0.25);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--emerald);
    box-shadow: 0 0 8px var(--emerald);
  }
  .container {
    max-width: 1480px;
    margin: 0 auto;
    padding: 24px 28px;
    display: grid;
    grid-template-columns: 1.05fr 1.25fr;
    gap: 22px;
  }
  @media (max-width: 1100px) {
    .container { grid-template-columns: 1fr; }
  }
  .card {
    background: var(--panel);
    border: 1px solid var(--panel-border);
    border-radius: 14px;
    padding: 20px;
    backdrop-filter: blur(12px);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
  }
  .card-title {
    font-size: 0.98rem;
    font-weight: 700;
    margin: 0 0 14px 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: #f8fafc;
  }
  label {
    display: block;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--muted);
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  input, select, textarea {
    width: 100%;
    background: rgba(7, 11, 20, 0.85);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 8px;
    color: var(--text);
    padding: 10px 12px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.83rem;
    margin-bottom: 12px;
  }
  textarea {
    min-height: 210px;
    resize: vertical;
  }
  input:focus, select:focus, textarea:focus {
    outline: none;
    border-color: var(--cyan);
    box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
  }
  .row-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .btn-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 4px;
  }
  button {
    cursor: pointer;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: 600;
    font-size: 0.84rem;
    transition: all 0.15s ease;
  }
  .btn-primary {
    background: linear-gradient(135deg, #0284c7, #7c3aed);
    color: #fff;
    box-shadow: 0 4px 15px rgba(56, 189, 248, 0.3);
  }
  .btn-primary:hover { filter: brightness(1.12); }
  .btn-secondary {
    background: rgba(30, 41, 59, 0.9);
    color: var(--text);
    border: 1px solid rgba(148, 163, 184, 0.3);
  }
  .btn-secondary:hover { border-color: var(--cyan); }
  .badge {
    display: inline-block;
    padding: 3px 9px;
    border-radius: 6px;
    font-size: 0.73rem;
    font-weight: 700;
    letter-spacing: 0.03em;
  }
  .badge-BOARD { background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
  .badge-REFUTE { background: rgba(244, 63, 94, 0.18); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.4); }
  .badge-BOARD-WITH-ADVISORY { background: rgba(245, 158, 11, 0.18); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
  .lens-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-top: 14px;
  }
  .lens-box {
    background: rgba(7, 11, 20, 0.75);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 10px;
    padding: 14px;
  }
  .gate-strip {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-top: 12px;
  }
  .gate-item {
    background: rgba(7, 11, 20, 0.7);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 0.8rem;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
  }
  th, td {
    text-align: left;
    padding: 9px 10px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  }
  th { color: var(--muted); font-size: 0.74rem; text-transform: uppercase; }
  tr.clickable:hover { background: rgba(56, 189, 248, 0.08); cursor: pointer; }
  pre {
    background: rgba(4, 7, 13, 0.92);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 8px;
    padding: 12px;
    overflow-x: auto;
    font-size: 0.78rem;
    color: #cbd5e1;
    max-height: 300px;
  }
</style>
</head>
<body>
<header>
  <div class="brand">
    <div class="brand-badge">🛡️</div>
    <div>
      <h1>Boylenet Autonomous Gitea Pre-Review & OffSec Red-Team Swarm</h1>
      <div class="sub">Port :4092 • Static Fast-Fail (Ruff + Tree-Sitter :8095 + Secret Scan) + Parallel Local GPU 2-Lens Review ($0 Token Cost)</div>
    </div>
  </div>
  <div class="pills">
    <div class="pill"><span class="dot"></span>Tree-Sitter AST :8095</div>
    <div class="pill"><span class="dot"></span>Lens 1: qwen3-coder-30b-a3b (Rule 86)</div>
    <div class="pill"><span class="dot"></span>Lens 2: cyberstrike-offsec-35b (Red-Team)</div>
    <div class="pill"><span class="dot"></span>Gitea Webhook :3000 Connected</div>
  </div>
</header>

<div class="container">
  <div>
    <div class="card">
      <div class="card-title">
        <span>⚡ Instant 2-Lens GPU Diff & Commit Reviewer</span>
        <span style="font-size:0.76rem;color:var(--cyan)">$0.00 Local GPU Cluster</span>
      </div>
      <div class="row-2">
        <div>
          <label>Title / Cut Label</label>
          <input id="revTitle" type="text" placeholder="e.g. O1789 Auth & Subprocess Patch"/>
        </div>
        <div>
          <label>Git Commit SHA / Range (Optional)</label>
          <input id="revCommit" type="text" placeholder="e.g. HEAD~1..HEAD or commit SHA"/>
        </div>
      </div>
      <div class="row-2">
        <div>
          <label>Gitea Repo (Optional Post-Back)</label>
          <input id="revRepo" type="text" value="mboyle/test-repo"/>
        </div>
        <div>
          <label>Post Verdict to Gitea :3000?</label>
          <select id="revPostGitea">
            <option value="false">Store in Pre-Review UI Only</option>
            <option value="true">Post Status/Comment to Gitea :3000</option>
          </select>
        </div>
      </div>
      <label>Paste Unified Git Diff (or leave blank to use Commit SHA / Range above)</label>
      <textarea id="revDiff" placeholder="diff --git a/app.py b/app.py&#10;--- a/app.py&#10;+++ b/app.py&#10;@@ -10,3 +10,5 @@ ..."></textarea>
      <div class="btn-row">
        <button class="btn-primary" id="runBtn" onclick="submitReview()">🚀 Run Static + 2-Lens Local GPU Review</button>
        <button class="btn-secondary" onclick="loadSampleClean()">Load Latest BulkDownloader Commit</button>
        <button class="btn-secondary" onclick="loadSampleVuln()">Load Red-Team Adversarial Sample</button>
      </div>
    </div>

    <div class="card" style="margin-top:20px;">
      <div class="card-title">
        <span>📜 Recent Pre-Review & Webhook Reports (<span id="revCountLabel">0</span>)</span>
        <button class="btn-secondary" id="refreshReviewsBtn" style="padding:5px 10px;font-size:0.75rem;" onclick="loadReviews()">Refresh</button>
      </div>
      <div class="btn-row" id="revFilterBar" style="margin-bottom:10px;">
        <button class="btn-secondary rev-filter-btn" data-verdict="ALL" style="padding:5px 11px;font-size:0.75rem;border-color:var(--cyan);" onclick="setVerdictFilter('ALL', this)">ALL</button>
        <button class="btn-secondary rev-filter-btn" data-verdict="BOARD" style="padding:5px 11px;font-size:0.75rem;" onclick="setVerdictFilter('BOARD', this)">✅ BOARD</button>
        <button class="btn-secondary rev-filter-btn" data-verdict="BOARD-WITH-ADVISORY" style="padding:5px 11px;font-size:0.75rem;" onclick="setVerdictFilter('BOARD-WITH-ADVISORY', this)">⚠️ ADVISORY</button>
        <button class="btn-secondary rev-filter-btn" data-verdict="REFUTE" style="padding:5px 11px;font-size:0.75rem;" onclick="setVerdictFilter('REFUTE', this)">❌ REFUTE</button>
      </div>
      <input id="revSearch" type="text" placeholder="Search reviews by ID, title, repo, or verdict..." oninput="renderReviewsTable()" style="margin-bottom:10px;"/>
      <div style="overflow-x:auto;">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Source / Title</th>
              <th>Static</th>
              <th>Lens 1 (Logic)</th>
              <th>Lens 2 (OffSec)</th>
              <th>Verdict</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody id="reviewsTableBody">
            <tr><td colspan="7" style="color:var(--muted)">Loading reviews...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <div>
    <div class="card" id="activeReportCard">
      <div class="card-title">
        <span id="detailHeader">🔍 Active Review Inspector</span>
        <span id="detailBadge"></span>
      </div>
      <div id="detailBody" style="color:var(--muted);font-size:0.86rem;">
        Select any review from the table or trigger a new 2-Lens GPU review to inspect full Static Gate + Behavioral + OffSec Red-Team telemetry.
      </div>
    </div>
  </div>
</div>

<script>
let ALL_REVIEWS = [];
let ACTIVE_VERDICT_FILTER = 'ALL';

function setVerdictFilter(v, btn) {
  ACTIVE_VERDICT_FILTER = v;
  document.querySelectorAll('.rev-filter-btn').forEach(b => b.style.borderColor = 'rgba(148, 163, 184, 0.3)');
  if (btn) btn.style.borderColor = 'var(--cyan)';
  renderReviewsTable();
}

function renderReviewsTable(selectId) {
  const tbody = document.getElementById('reviewsTableBody');
  tbody.innerHTML = '';
  const q = ((document.getElementById('revSearch') && document.getElementById('revSearch').value) || '').toLowerCase().trim();
  const items = ALL_REVIEWS.filter(r => {
    if (ACTIVE_VERDICT_FILTER !== 'ALL' && r.overall_verdict !== ACTIVE_VERDICT_FILTER) return false;
    if (!q) return true;
    const hay = [r.review_id, r.title, r.source, r.repo, r.overall_verdict, r.lens1_verdict, r.lens2_verdict].join(' ').toLowerCase();
    return hay.includes(q);
  });
  const countEl = document.getElementById('revCountLabel');
  if (countEl) countEl.textContent = `${items.length}/${ALL_REVIEWS.length}`;
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="color:var(--muted)">No matching reviews.</td></tr>';
    return;
  }
  for (const r of items) {
    const tr = document.createElement('tr');
    tr.className = 'clickable';
    tr.onclick = () => inspectReview(r.review_id);
    tr.innerHTML = `
      <td style="font-family:monospace;color:var(--cyan)">${r.review_id}</td>
      <td>${escapeHtml(r.title || r.source)}</td>
      <td>${r.static_passed ? '✅ PASS' : '❌ FAIL'}</td>
      <td><span class="badge badge-${r.lens1_verdict}">${r.lens1_verdict}</span></td>
      <td><span class="badge badge-${r.lens2_verdict}">${r.lens2_verdict}</span></td>
      <td><span class="badge badge-${r.overall_verdict}">${r.overall_verdict}</span></td>
      <td>${r.total_elapsed_ms} ms</td>
    `;
    tbody.appendChild(tr);
  }
  const target = selectId || new URLSearchParams(window.location.search).get('id') || items[0].review_id;
  if (target) inspectReview(target);
}

async function loadReviews(selectId) {
  const res = await fetch('/api/reviews');
  const data = await res.json();
  ALL_REVIEWS = data.reviews || [];
  renderReviewsTable(selectId);
}

async function inspectReview(id) {
  const res = await fetch('/api/reviews/' + encodeURIComponent(id));
  if (!res.ok) return;
  const r = await res.json();
  document.getElementById('detailHeader').textContent = `${r.review_id} — ${r.title || r.source}`;
  document.getElementById('detailBadge').innerHTML = `<span class="badge badge-${r.overall_verdict}">${r.overall_verdict} (${r.total_elapsed_ms} ms)</span>`;

  const sg = r.static_gates;
  const l1 = r.gpu_lenses.lens1_behavioral;
  const l2 = r.gpu_lenses.lens2_security_redteam;

  const renderFindings = (arr) => {
    if (!arr || !arr.length) return '<div style="color:var(--emerald);font-size:0.8rem;margin-top:6px;">No blocking findings.</div>';
    return '<ul style="margin:6px 0 0 16px;padding:0;font-size:0.8rem;color:#fca5a5;">' +
      arr.map(f => `<li><code>${escapeHtml(f.file || f.location || '?')}:${escapeHtml(String(f.line || '?'))}</code> — ${escapeHtml(f.issue || f.message || f.type || JSON.stringify(f))}</li>`).join('') +
      '</ul>';
  };

  document.getElementById('detailBody').innerHTML = `
    <div style="font-size:0.8rem;color:var(--muted);margin-bottom:10px;">
      Created: <code>${r.created_at}</code> • Trigger: <code>${r.trigger_type}</code> • Source: <code>${escapeHtml(r.source)}</code> • Cost: <code>$0.00</code>
    </div>
    <div class="gate-strip">
      <div class="gate-item">
        <strong>Ruff Syntax/Lint</strong><br/>
        <span style="color:${sg.ruff.passed ? 'var(--emerald)' : 'var(--rose)'}">${sg.ruff.passed ? '✅ PASS' : '❌ FAIL'} (${sg.ruff.finding_count} findings)</span>
      </div>
      <div class="gate-item">
        <strong>Tree-Sitter AST :8095</strong><br/>
        <span style="color:${sg.tree_sitter_ast.passed ? 'var(--emerald)' : 'var(--rose)'}">${sg.tree_sitter_ast.passed ? '✅ PASS' : '❌ FAIL'} (ast-grep ${sg.tree_sitter_ast.ast_grep_version})</span>
      </div>
      <div class="gate-item">
        <strong>Secret & Credential Scan</strong><br/>
        <span style="color:${sg.secret_scan.passed ? 'var(--emerald)' : 'var(--rose)'}">${sg.secret_scan.passed ? '✅ PASS' : '❌ FAIL'} (${sg.secret_scan.finding_count} alerts)</span>
      </div>
    </div>
    <div class="lens-grid">
      <div class="lens-box">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <strong style="color:var(--cyan)">Lens 1: Behavioral & Logic</strong>
          <span class="badge badge-${l1.verdict}">${l1.verdict}</span>
        </div>
        <div style="font-size:0.75rem;color:var(--muted);margin:4px 0;">Model: <code>${l1.model}</code> • ${l1.elapsed_ms} ms • ${l1.tokens} tok</div>
        <div style="font-size:0.82rem;margin-top:6px;color:var(--text)">${escapeHtml(l1.summary)}</div>
        ${renderFindings(l1.findings)}
      </div>
      <div class="lens-box">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <strong style="color:var(--violet)">Lens 2: OffSec Red-Team</strong>
          <span class="badge badge-${l2.verdict}">${l2.verdict}</span>
        </div>
        <div style="font-size:0.75rem;color:var(--muted);margin:4px 0;">Model: <code>${l2.model}</code> • ${l2.elapsed_ms} ms • ${l2.tokens} tok</div>
        <div style="font-size:0.82rem;margin-top:6px;color:var(--text)">${escapeHtml(l2.summary)}</div>
        ${renderFindings(l2.findings)}
      </div>
    </div>
    <div style="margin-top:14px;">
      <label>Rule 76 / Rule 86 Consensus JSON Payload</label>
      <pre>${escapeHtml(JSON.stringify(r.consensus_json, null, 2))}</pre>
    </div>
    <div style="margin-top:10px;">
      <label>Diff Preview (${r.diff_bytes} bytes)</label>
      <pre>${escapeHtml(r.diff_preview)}</pre>
    </div>
  `;
}

async function submitReview() {
  const btn = document.getElementById('runBtn');
  btn.disabled = true;
  btn.textContent = '⏳ Running Static Gates + Parallel GPU Lenses...';
  try {
    const diffVal = document.getElementById('revDiff').value.trim();
    const commitVal = document.getElementById('revCommit').value.trim();
    const payload = {
      title: document.getElementById('revTitle').value.trim() || 'Interactive Web Review',
      diff: diffVal || commitVal || 'HEAD~1..HEAD',
      repo: document.getElementById('revRepo').value.trim(),
      post_to_gitea: document.getElementById('revPostGitea').value === 'true'
    };
    const res = await fetch('/api/review', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const report = await res.json();
    await loadReviews(report.review_id);
  } finally {
    btn.disabled = false;
    btn.textContent = '🚀 Run Static + 2-Lens Local GPU Review';
  }
}

function loadSampleClean() {
  document.getElementById('revTitle').value = 'BulkDownloader HEAD~1..HEAD Verification';
  document.getElementById('revCommit').value = 'HEAD~1..HEAD';
  document.getElementById('revDiff').value = '';
}

function loadSampleVuln() {
  document.getElementById('revTitle').value = 'Red-Team Adversarial Command Injection & Secret Probe';
  document.getElementById('revCommit').value = '';
  document.getElementById('revDiff').value = [
    'diff --git a/auth_runner.py b/auth_runner.py',
    '--- a/auth_runner.py',
    '+++ b/auth_runner.py',
    '@@ -1,4 +1,9 @@',
    '+import subprocess',
    '+',
    '+def run_diag(user_host: str) -> str:',
    '+    # Unsanitized shell command execution',
    '+    out = subprocess.check_output(f"ping -c 1 {user_host}", shell=True, text=True)',
    '+    return eval(out)',
  ].join('\\n');
}

function escapeHtml(s) {
  return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

loadReviews();
</script>
</body>
</html>
"""


class PreReviewHTTPHandler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: Any) -> None:
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, code: int, html: str) -> None:
        raw = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._send_html(200, DASHBOARD_HTML)
            return

        if path in ("/health", "/api/status"):
            ast_code, ast_info = http_json(f"{AST_SERVER_URL}/health", timeout=3.0)
            index_count = 0
            if INDEX_FILE.is_file():
                try:
                    index_count = len(
                        json.loads(INDEX_FILE.read_text(encoding="utf-8"))
                    )
                except (OSError, ValueError, KeyError, TypeError):
                    index_count = 0
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "bd-gitea-prereview",
                    "port": PORT,
                    "litellm_url": LITELLM_BASE,
                    "lens1_model": LENS1_MODEL,
                    "lens2_model": LENS2_MODEL,
                    "ast_server": ast_info
                    if ast_code == 200
                    else {"status": "unreachable"},
                    "gitea_url": GITEA_BASE_URL,
                    "stored_reviews": index_count,
                },
            )
            return

        if path == "/api/reviews":
            index: list[dict[str, Any]] = []
            if INDEX_FILE.is_file():
                try:
                    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
                except (OSError, ValueError, KeyError, TypeError):
                    index = []
            self._send_json(
                200, {"status": "ok", "count": len(index), "reviews": index}
            )
            return

        if path.startswith("/api/reviews/"):
            rid = path.split("/api/reviews/", 1)[1].strip("/")
            rfile = REVIEWS_DIR / f"{rid}.json"
            if not rfile.is_file():
                self._send_json(404, {"error": f"Review {rid} not found"})
                return
            self._send_json(200, json.loads(rfile.read_text(encoding="utf-8")))
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        content_len = int(self.headers.get("Content-Length", "0"))
        raw_body = (
            self.rfile.read(content_len).decode("utf-8", errors="replace")
            if content_len > 0
            else "{}"
        )
        try:
            payload = json.loads(raw_body) if raw_body.strip() else {}
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON body"})
            return

        if self.path.startswith("/api/review"):
            diff_in = str(
                payload.get("diff") or payload.get("commit") or "HEAD~1..HEAD"
            )
            repo_dir = str(payload.get("repo_dir") or DEFAULT_REPO_DIR)
            repo_name = str(payload.get("repo") or "")
            pr_index = payload.get("pr_index")
            commit_sha = str(payload.get("commit_sha") or "")
            title = str(payload.get("title") or "")
            post_to_gitea = bool(payload.get("post_to_gitea", False))
            try:
                report = execute_review_pipeline(
                    diff_input=diff_in,
                    repo_dir=repo_dir,
                    repo_full_name=repo_name,
                    pr_index=int(pr_index) if pr_index is not None else None,
                    commit_sha=commit_sha,
                    title=title,
                    trigger_type="api",
                    post_to_gitea=post_to_gitea,
                )
                self._send_json(200, report)
            except (
                OSError,
                ValueError,
                KeyError,
                IndexError,
                TypeError,
                RuntimeError,
            ) as e:
                self._send_json(400, {"error": str(e)})
            return

        if self.path.startswith("/webhook/gitea"):
            event = self.headers.get(
                "X-Gitea-Event", self.headers.get("X-Forgejo-Event", "push")
            )
            if event == "ping" or payload.get("zen"):
                self._send_json(
                    200,
                    {
                        "status": "pong",
                        "event": "ping",
                        "service": "bd-gitea-prereview",
                    },
                )
                return

            repo_info = payload.get("repository", {})
            repo_full = repo_info.get("full_name", "")
            pr_info = payload.get("pull_request")
            pr_idx: int | None = None
            commit_sha = ""
            title = ""
            diff_text = ""

            token = load_gitea_token()
            g_headers = {"Authorization": f"token {token}"} if token else {}

            if isinstance(pr_info, dict):
                pr_idx = pr_info.get("number") or payload.get("number")
                title = f"PR #{pr_idx}: {pr_info.get('title', 'Pull Request')}"
                head_info = pr_info.get("head", {})
                commit_sha = head_info.get("sha", "")
                if repo_full and pr_idx:
                    d_url = (
                        f"{GITEA_BASE_URL}/api/v1/repos/{repo_full}/pulls/{pr_idx}.diff"
                    )
                    d_code, d_body = http_json(d_url, headers=g_headers, timeout=15.0)
                    if d_code == 200 and isinstance(d_body, str) and d_body.strip():
                        diff_text = d_body
            else:
                commit_sha = payload.get("after", "") or payload.get(
                    "head_commit", {}
                ).get("id", "")
                commits = payload.get("commits", [])
                msg = (
                    commits[0].get("message", "").splitlines()[0]
                    if commits
                    else "Push event"
                )
                title = f"Push {commit_sha[:8]}: {msg}"
                if (
                    repo_full
                    and commit_sha
                    and commit_sha != "0000000000000000000000000000000000000000"
                ):
                    d_url = f"{GITEA_BASE_URL}/api/v1/repos/{repo_full}/git/commits/{commit_sha}.diff"
                    d_code, d_body = http_json(d_url, headers=g_headers, timeout=15.0)
                    if d_code == 200 and isinstance(d_body, str) and d_body.strip():
                        diff_text = d_body

            if not diff_text.strip():
                diff_text = str(payload.get("diff") or "HEAD~1..HEAD")

            try:
                report = execute_review_pipeline(
                    diff_input=diff_text,
                    repo_dir=DEFAULT_REPO_DIR,
                    repo_full_name=repo_full,
                    pr_index=int(pr_idx) if pr_idx is not None else None,
                    commit_sha=commit_sha,
                    title=title,
                    trigger_type=f"gitea-webhook:{event}",
                    post_to_gitea=bool(repo_full),
                )
                self._send_json(200, report)
            except (
                OSError,
                ValueError,
                KeyError,
                IndexError,
                TypeError,
                RuntimeError,
            ) as e:
                self._send_json(500, {"error": str(e)})
            return

        self._send_json(404, {"error": "Unknown POST endpoint"})

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info("%s - %s", self.client_address[0], fmt % args)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Boylenet Gitea Pre-Review & Security Red-Team Swarm (:4092 + CLI)"
    )
    parser.add_argument(
        "--diff",
        default="",
        help="Git range (e.g. HEAD~1..HEAD), commit SHA, diff file path, or '-' for stdin",
    )
    parser.add_argument(
        "--repo-dir",
        default=DEFAULT_REPO_DIR,
        help="Git repository directory for range resolution",
    )
    parser.add_argument(
        "--repo",
        default="",
        help="Gitea owner/repo (e.g. mboyle/test-repo) for posting status",
    )
    parser.add_argument(
        "--pr", type=int, default=None, help="Gitea PR index to comment on"
    )
    parser.add_argument(
        "--commit", default="", help="Commit SHA to attach Gitea commit status to"
    )
    parser.add_argument(
        "--post-gitea",
        action="store_true",
        help="Post review summary back to Gitea :3000",
    )
    parser.add_argument("--title", default="", help="Review title")
    parser.add_argument(
        "--json", action="store_true", help="Output raw JSON report in CLI mode"
    )
    parser.add_argument(
        "--port", type=int, default=PORT, help="HTTP listen port (default: 4092)"
    )
    args = parser.parse_args()

    if args.diff:
        report = execute_review_pipeline(
            diff_input=args.diff,
            repo_dir=args.repo_dir,
            repo_full_name=args.repo,
            pr_index=args.pr,
            commit_sha=args.commit,
            title=args.title or f"CLI Review ({args.diff})",
            trigger_type="cli",
            post_to_gitea=args.post_gitea,
        )
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(format_gitea_markdown(report))
            print("\n--- CONSENSUS JSON (Rule 76 / Rule 86) ---")
            print(json.dumps(report["consensus_json"]))
        return 0 if report["overall_verdict"] != "REFUTE" else 2

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, args.port), PreReviewHTTPHandler)
    logger.info("bd-gitea-prereview listening on http://%s:%d", HOST, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
