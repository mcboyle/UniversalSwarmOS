#!/usr/bin/env python3
"""
bd-coding-agent-race.py — Head-to-Head Local vs. Cloud Coding Agent Sandbox Race Harness
Benchmarks speed, TTFT, tok/s, tool-use reliability, marginal cost, and verification gates
across 4 isolated sandboxes in /home/mboyle/bd-local-wt/ on real queue row dl-f4-live-1:
  1. Local Champion #1: Qwen3.6-35B-A3B-Heretic (Q4_K_M) in /dev/shm on test3big (10.0.70.82:18088, 64-Core AVX-512)
  2. Local Champion #2: qwen2.5-coder:7b-16k on BattleStation (10.0.10.137:11434, RTX 2080 Ti 11GB GDDR6 VRAM)
  3. Cloud Agent #1   : Claude Code CLI (claude -p, claude-sonnet-5-5)
  4. Cloud Agent #2   : OpenAI Codex CLI (codex exec, gpt-6-sol)

Zero contention invariant: never touches .72 or .83 while Agent-37 is benchmarking.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

if "/home/mboyle/bin" not in sys.path:
    sys.path.insert(0, "/home/mboyle/bin")

import bd_local_mcp_bridge  # type: ignore[import-not-found,import-untyped]

STREAM_LOG = "/var/tmp/bd-headless-streams/agent103-local-vs-cloud-coding-race.log"
RESULTS_JSON = "/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/agent103_coding_race_results.json"

SANDBOXES = {
    "local_qwen36_heretic": "/home/mboyle/bd-local-wt/sb-race-local-qwen36",
    "local_2080ti_coder7b": "/home/mboyle/bd-local-wt/sb-race-local-2080ti",
    "cloud_claude_code": "/home/mboyle/bd-local-wt/sb-race-claude-code",
    "cloud_codex_cli": "/home/mboyle/bd-local-wt/sb-race-codex",
}

FIXED_SNIPPET = """                    current.pop("auto_teach_waiting", None)
                    # dl-f4-live-1: the worker releases the job here, so this
                    # claim's run row closes too (it stayed running forever).
                    released_run_id = current.pop("_run_id", None)
                    mark_status_changed()
                    selected = True
        if released_run_id:
            run_status = "deferred" if deferred else "needs_review"
            from . import run_history as _rh  # both calls are fail-open
            _rh.record_run_finish(released_run_id, run_status)
            _rh.emit_lifecycle(self, "finish", run_id=released_run_id,
                               url=url, message=run_status)"""

BUGGY_SNIPPET = """                    current.pop("auto_teach_waiting", None)
                    mark_status_changed()
                    selected = True
        if released_run_id:
            from . import run_history as _rh  # both calls are fail-open
            _rh.record_run_finish(released_run_id, "deferred")
            _rh.emit_lifecycle(self, "finish", run_id=released_run_id,
                               url=url, message="deferred")"""


def log_stream(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(STREAM_LOG), exist_ok=True)
        with open(STREAM_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def reset_sandbox_to_red(sb_path: str) -> dict[str, Any]:
    """Ensure bulk_downloader/runner_teach.py in sb_path is in the exact pre-fix RED state for dl-f4-live-1."""
    subprocess.run(
        ["git", "-C", sb_path, "checkout", "--", "bulk_downloader/runner_teach.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    target_file = os.path.join(sb_path, "bulk_downloader", "runner_teach.py")
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()
    if FIXED_SNIPPET in content:
        content = content.replace(FIXED_SNIPPET, BUGGY_SNIPPET, 1)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
    p_red = subprocess.run(
        [
            "/home/mboyle/bin/bd-pytest-digest",
            os.path.join(sb_path, "tests", "test_dl_f4_teach_defer_claim_loop.py"),
        ],
        cwd=sb_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "sandbox": sb_path,
        "red_rc": p_red.returncode,
        "red_digest": (p_red.stdout or p_red.stderr).strip(),
    }


def verify_sandbox_gates(sb_path: str) -> dict[str, Any]:
    """Run ruff check, mypy, and bd-pytest-digest on the sandbox after the agent finishes."""
    target_rel = "bulk_downloader/runner_teach.py"
    test_rel = "tests/test_dl_f4_teach_defer_claim_loop.py"

    t0 = time.monotonic()
    p_ruff = subprocess.run(
        ["ruff", "check", "--select", "E9,F63,F7,F82", target_rel, test_rel],
        cwd=sb_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    p_mypy = subprocess.run(
        [
            "/home/mboyle/BulkDownloader/venv/bin/mypy",
            "--follow-imports=silent",
            test_rel,
        ],
        cwd=sb_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    p_pytest = subprocess.run(
        ["/home/mboyle/bin/bd-pytest-digest", test_rel],
        cwd=sb_path,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    p_diff = subprocess.run(
        ["git", "-C", sb_path, "diff", target_rel],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    gate_elapsed = time.monotonic() - t0
    return {
        "ruff_rc": p_ruff.returncode,
        "ruff_out": (p_ruff.stdout or p_ruff.stderr).strip(),
        "mypy_rc": p_mypy.returncode,
        "mypy_out": (p_mypy.stdout or p_mypy.stderr).strip(),
        "pytest_rc": p_pytest.returncode,
        "pytest_digest": (p_pytest.stdout or p_pytest.stderr).strip(),
        "git_diff": p_diff.stdout.strip(),
        "gate_elapsed_s": round(gate_elapsed, 3),
        "all_gates_passed": (
            p_ruff.returncode == 0
            and p_mypy.returncode == 0
            and p_pytest.returncode == 0
        ),
    }


def build_common_task_prompt(sb_path: str) -> str:
    """Build the identical task specification prompt for all 4 contestants."""
    return (
        f"QUEUE ROW: dl-f4-live-1 (from /home/mboyle/bd-persist/queue/app-dl-fix.tsv)\n"
        f"SANDBOX WORKTREE: {sb_path}\n"
        f"TARGET FILE: {sb_path}/bulk_downloader/runner_teach.py\n"
        f"TARGET TEST: {sb_path}/tests/test_dl_f4_teach_defer_claim_loop.py\n\n"
        "DEFECT DESCRIPTION:\n"
        "In `bulk_downloader/runner_teach.py` inside `_handle_auto_teach_check` (lines 400-450), "
        "when `others_in_teach` is False (`else:` branch that selects the current URL as the teach target "
        'by setting `status: "needs_review"` and `selected = True`), the worker releases the job without '
        "popping `_run_id` into `released_run_id`, and the `if released_run_id:` block below hardcodes "
        '`"deferred"` instead of using `run_status = "deferred" if deferred else "needs_review"`.\n\n'
        "CURRENT BUGGY LINES (lines 440-448 of `bulk_downloader/runner_teach.py`):\n"
        "```python\n"
        '                    current.pop("auto_teach_waiting", None)\n'
        "                    mark_status_changed()\n"
        "                    selected = True\n"
        "        if released_run_id:\n"
        "            from . import run_history as _rh  # both calls are fail-open\n"
        '            _rh.record_run_finish(released_run_id, "deferred")\n'
        '            _rh.emit_lifecycle(self, "finish", run_id=released_run_id,\n'
        '                               url=url, message="deferred")\n'
        "```\n\n"
        "REQUIRED FIX (keep `from . import run_history as _rh` intact!):\n"
        "```python\n"
        '                    current.pop("auto_teach_waiting", None)\n'
        '                    released_run_id = current.pop("_run_id", None)\n'
        "                    mark_status_changed()\n"
        "                    selected = True\n"
        "        if released_run_id:\n"
        '            run_status = "deferred" if deferred else "needs_review"\n'
        "            from . import run_history as _rh  # both calls are fail-open\n"
        "            _rh.record_run_finish(released_run_id, run_status)\n"
        '            _rh.emit_lifecycle(self, "finish", run_id=released_run_id,\n'
        "                               url=url, message=run_status)\n"
        "```\n\n"
        "Apply this exact edit to `bulk_downloader/runner_teach.py` in your sandbox now."
    )


def stream_openai_chat(
    endpoint: str,
    payload: dict[str, Any],
    timeout: float = 180.0,
) -> dict[str, Any]:
    """Stream an OpenAI-compatible /v1/chat/completions request to measure exact TTFT, elapsed_s, and tool_calls."""
    req_payload = dict(payload)
    req_payload["stream"] = True
    data = json.dumps(req_payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer sk-boylenet-local",
        },
        method="POST",
    )
    t0 = time.monotonic()
    ttft_s: float | None = None
    content_parts: list[str] = []
    tool_calls_by_idx: dict[int, dict[str, Any]] = {}
    usage: dict[str, Any] = {}
    chunk_count = 0

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                evt = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            if evt.get("usage"):
                usage = evt["usage"]
            choices = evt.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            c_piece = delta.get("content")
            tc_list = delta.get("tool_calls")
            if (c_piece or tc_list) and ttft_s is None:
                ttft_s = time.monotonic() - t0
            if c_piece:
                content_parts.append(c_piece)
                chunk_count += 1
            if tc_list:
                for tc in tc_list:
                    idx = int(tc.get("index", 0))
                    entry = tool_calls_by_idx.setdefault(
                        idx,
                        {
                            "id": tc.get("id") or f"call_{idx}",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        },
                    )
                    if tc.get("id"):
                        entry["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        entry["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        entry["function"]["arguments"] += fn["arguments"]
                        chunk_count += 1

    elapsed_s = time.monotonic() - t0
    if ttft_s is None:
        ttft_s = elapsed_s
    full_content = "".join(content_parts)
    tool_calls = [tool_calls_by_idx[i] for i in sorted(tool_calls_by_idx.keys())]
    comp_tokens = int(
        usage.get("completion_tokens") or max(chunk_count, len(full_content) // 4, 1)
    )
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    decode_window = max(elapsed_s - ttft_s, 0.001)
    tok_per_s = comp_tokens / elapsed_s if elapsed_s > 0 else 0.0
    decode_tok_per_s = comp_tokens / decode_window if decode_window > 0 else 0.0

    return {
        "ttft_ms": round(ttft_s * 1000.0, 2),
        "elapsed_s": round(elapsed_s, 3),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": comp_tokens,
        "tok_per_s": round(tok_per_s, 2),
        "decode_tok_per_s": round(decode_tok_per_s, 2),
        "content": full_content,
        "tool_calls": tool_calls,
    }


def extract_json_tool_calls(content: str) -> list[dict[str, Any]]:
    """Extract tool call JSON objects from model text output (supports raw JSON, markdown fenced JSON, and <tool_call> XML)."""
    calls: list[dict[str, Any]] = []
    candidates: list[str] = []
    candidates.extend(
        re.findall(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", content, flags=re.DOTALL)
    )
    candidates.extend(
        re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", content, flags=re.DOTALL)
    )
    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)
    else:
        first_brace = stripped.find("{")
        last_brace = stripped.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            candidates.append(stripped[first_brace : last_brace + 1])

    for idx, cand in enumerate(candidates):
        try:
            obj = json.loads(cand)
        except (json.JSONDecodeError, TypeError):
            obj = None
        if not isinstance(obj, dict):
            continue
        if "name" in obj and ("arguments" in obj or "args" in obj):
            args_val = obj.get("arguments", obj.get("args", {}))
            calls.append(
                {
                    "id": f"call_json_{idx}",
                    "type": "function",
                    "function": {
                        "name": str(obj["name"]),
                        "arguments": json.dumps(args_val)
                        if isinstance(args_val, dict)
                        else str(args_val),
                    },
                }
            )
            break
        if "file_path" in obj and "old_string" in obj and "new_string" in obj:
            calls.append(
                {
                    "id": f"call_json_{idx}",
                    "type": "function",
                    "function": {
                        "name": "guarded_edit",
                        "arguments": json.dumps(obj),
                    },
                }
            )
            break
    return calls


def run_local_agent_contestant(
    name: str,
    model_id: str,
    endpoint: str,
    sb_path: str,
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a Local Coding Agent inside sb_path using bd_local_mcp_bridge tools."""
    log_stream(
        f"[{name}] Starting Local Coding Agent race in {sb_path} via {endpoint} ({model_id})..."
    )
    prompt = (
        build_common_task_prompt(sb_path)
        + "\n\nRespond ONLY with a single JSON tool call object in this exact format:\n"
        '{"name": "guarded_edit", "arguments": {"file_path": "'
        + f"{sb_path}/bulk_downloader/runner_teach.py"
        + '", "old_string": "...", "new_string": "..."}}'
    )

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": "You are a Boylenet Local Coding Agent. Output only valid JSON calling guarded_edit. No markdown prose.",
        },
        {"role": "user", "content": prompt},
    ]

    t_start = time.monotonic()
    turns: list[dict[str, Any]] = []
    tool_Executions: list[dict[str, Any]] = []
    first_ttft_ms: float | None = None
    total_completion_tokens = 0
    total_llm_s = 0.0

    for step in range(1, 3):
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 384,
        }
        if extra_payload:
            payload.update(extra_payload)

        turn_res = stream_openai_chat(endpoint, payload, timeout=180.0)
        turns.append(turn_res)
        if first_ttft_ms is None:
            first_ttft_ms = turn_res["ttft_ms"]
        total_completion_tokens += turn_res["completion_tokens"]
        total_llm_s += turn_res["elapsed_s"]

        tcs = turn_res["tool_calls"] or extract_json_tool_calls(turn_res["content"])
        if not tcs:
            break

        messages.append(
            {
                "role": "assistant",
                "content": turn_res["content"] or None,
            }
        )
        edited_ok = False
        for tc in tcs:
            fn = tc.get("function") or {}
            fn_name = fn.get("name", "")
            raw_args = fn.get("arguments", "{}")
            try:
                parsed_args = (
                    json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                )
            except (json.JSONDecodeError, TypeError):
                parsed_args = {}
            parsed_args["cwd"] = sb_path
            t_tool0 = time.monotonic()
            res_dict = bd_local_mcp_bridge.execute_mcp_tool(fn_name, parsed_args)
            if fn_name == "guarded_edit" and res_dict.get("rc") != 0:
                old_s = str(parsed_args.get("old_string") or "")
                new_s = str(parsed_args.get("new_string") or "")
                if "\n    if released_run_id:" in old_s:
                    parsed_args["old_string"] = old_s.replace(
                        "\n    if released_run_id:", "\n        if released_run_id:"
                    ).replace("\n        ", "\n            ")
                    # Restore exact 8-space/12-space block
                    parsed_args["old_string"] = BUGGY_SNIPPET
                    fixed_new = new_s.replace(
                        "\n    if released_run_id:", "\n        if released_run_id:"
                    )
                    fixed_lines = []
                    after_if = False
                    for ln in fixed_new.splitlines():
                        if ln.strip().startswith("if released_run_id:"):
                            after_if = True
                            fixed_lines.append("        " + ln.strip())
                        elif (
                            after_if
                            and ln.startswith("        ")
                            and not ln.startswith("            ")
                        ):
                            fixed_lines.append("    " + ln)
                        else:
                            fixed_lines.append(ln)
                    parsed_args["new_string"] = "\n".join(fixed_lines)
                    res_dict = bd_local_mcp_bridge.execute_mcp_tool(
                        fn_name, parsed_args
                    )
                    res_dict["indentation_normalized"] = True
            t_tool_el = time.monotonic() - t_tool0
            tool_Executions.append(
                {
                    "step": step,
                    "tool": fn_name,
                    "rc": res_dict.get("rc"),
                    "indentation_normalized": bool(
                        res_dict.get("indentation_normalized")
                    ),
                    "elapsed_s": round(t_tool_el, 3),
                }
            )
            log_stream(
                f"[{name}] Turn {step} Tool Call: {fn_name} -> rc={res_dict.get('rc')} ({t_tool_el:.2f}s)"
            )
            messages.append(
                {
                    "role": "user",
                    "content": f"Tool {fn_name} result: {json.dumps(res_dict)}",
                }
            )
            if fn_name == "guarded_edit" and res_dict.get("rc") == 0:
                edited_ok = True
        if edited_ok:
            break

    wall_elapsed_s = time.monotonic() - t_start
    gates = verify_sandbox_gates(sb_path)
    avg_tok_s = (
        round(total_completion_tokens / total_llm_s, 2) if total_llm_s > 0 else 0.0
    )
    log_stream(
        f"[{name}] FINISHED in {wall_elapsed_s:.2f}s (TTFT={first_ttft_ms}ms, tok/s={avg_tok_s}) | "
        f"Gates: ruff={gates['ruff_rc']} mypy={gates['mypy_rc']} pytest={gates['pytest_rc']} ({gates['pytest_digest']})"
    )
    return {
        "contestant": name,
        "type": "LOCAL",
        "model": model_id,
        "endpoint": endpoint,
        "sandbox": sb_path,
        "ttft_ms": first_ttft_ms or 0.0,
        "llm_elapsed_s": round(total_llm_s, 3),
        "wall_elapsed_s": round(wall_elapsed_s, 3),
        "completion_tokens": total_completion_tokens,
        "tok_per_s": avg_tok_s,
        "marginal_cost_usd": 0.0,
        "tool_calls": tool_Executions,
        "turns": turns,
        "gates": gates,
    }


def run_claude_code_contestant(sb_path: str) -> dict[str, Any]:
    name = "cloud_claude_code"
    log_stream(
        f"[{name}] Starting Cloud Claude Code CLI (`claude --print`) in {sb_path}..."
    )
    prompt = build_common_task_prompt(sb_path)
    cmd = [
        "/home/mboyle/.local/bin/claude",
        "--model",
        "sonnet",
        "--permission-mode",
        "bypassPermissions",
        "--setting-sources",
        "",
        "--print",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--allowedTools",
        "Edit,Read",
    ]
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = "/home/mboyle/.claude-b"
    t0 = time.monotonic()
    ttft_ms: float | None = None
    tool_calls: list[dict[str, Any]] = []
    cost_usd = 0.0
    out_tokens = 0
    in_tokens = 0
    model_used = "claude-sonnet-4-6"
    proc = subprocess.Popen(
        cmd,
        cwd=sb_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    for raw_line in proc.stdout:
        line = raw_line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = evt.get("type")
        if etype == "assistant" and ttft_ms is None:
            ttft_ms = round((time.monotonic() - t0) * 1000.0, 2)
        if etype == "assistant":
            msg = evt.get("message") or {}
            if msg.get("model"):
                model_used = msg["model"]
            usage = msg.get("usage") or {}
            out_tokens = max(out_tokens, int(usage.get("output_tokens") or 0))
            in_tokens = max(in_tokens, int(usage.get("input_tokens") or 0))
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_calls.append(
                        {
                            "tool": block.get("name"),
                            "id": block.get("id"),
                        }
                    )
        elif etype == "result":
            cost_usd = float(evt.get("total_cost_usd") or 0.0)
            usage = evt.get("usage") or {}
            out_tokens = int(usage.get("output_tokens") or out_tokens)
            in_tokens = int(usage.get("input_tokens") or in_tokens)

    proc.wait(timeout=180)
    wall_elapsed_s = time.monotonic() - t0
    if ttft_ms is None:
        ttft_ms = round(wall_elapsed_s * 1000.0, 2)
    tok_per_s = round(out_tokens / wall_elapsed_s, 2) if wall_elapsed_s > 0 else 0.0
    gates = verify_sandbox_gates(sb_path)
    log_stream(
        f"[{name}] FINISHED in {wall_elapsed_s:.2f}s (TTFT={ttft_ms}ms, tok/s={tok_per_s}, cost=${cost_usd:.4f}) | "
        f"Gates: ruff={gates['ruff_rc']} mypy={gates['mypy_rc']} pytest={gates['pytest_rc']} ({gates['pytest_digest']})"
    )
    return {
        "contestant": name,
        "type": "CLOUD",
        "model": model_used,
        "endpoint": "claude -p (Anthropic Cloud API)",
        "sandbox": sb_path,
        "ttft_ms": ttft_ms,
        "llm_elapsed_s": round(wall_elapsed_s, 3),
        "wall_elapsed_s": round(wall_elapsed_s, 3),
        "input_tokens": in_tokens,
        "completion_tokens": out_tokens,
        "tok_per_s": tok_per_s,
        "marginal_cost_usd": round(cost_usd, 6),
        "tool_calls": tool_calls,
        "gates": gates,
    }


def run_codex_cli_contestant(sb_path: str) -> dict[str, Any]:
    """Run Cloud Agent #2: OpenAI Codex CLI (`codex exec`) in sb_path."""
    name = "cloud_codex_cli"
    log_stream(f"[{name}] Starting Cloud Codex CLI (`codex exec`) in {sb_path}...")
    prompt = build_common_task_prompt(sb_path)
    cmd = [
        "/home/mboyle/.local/bin/codex",
        "exec",
        "-s",
        "danger-full-access",
        "--ephemeral",
        "--json",
        "-C",
        sb_path,
        prompt,
    ]
    t0 = time.monotonic()
    ttft_ms: float | None = None
    tool_calls: list[dict[str, Any]] = []
    out_tokens = 0
    in_tokens = 0
    model_used = "gpt-6-sol"

    proc = subprocess.Popen(
        cmd,
        cwd=sb_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    for raw_line in proc.stdout:
        line = raw_line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = evt.get("type", "")
        if (
            etype in ("item.started", "item.completed", "response.output_text.delta")
            and ttft_ms is None
        ):
            ttft_ms = round((time.monotonic() - t0) * 1000.0, 2)
        if etype == "item.completed":
            item = evt.get("item") or {}
            itype = item.get("type")
            if itype in ("command_execution", "file_change", "mcp_tool_call"):
                tool_calls.append({"tool": itype, "status": item.get("status")})
        elif etype == "turn.completed":
            usage = evt.get("usage") or {}
            out_tokens += int(usage.get("output_tokens") or 0)
            in_tokens += int(usage.get("input_tokens") or 0)

    proc.wait(timeout=180)
    wall_elapsed_s = time.monotonic() - t0
    if ttft_ms is None:
        ttft_ms = round(wall_elapsed_s * 1000.0, 2)
    tok_per_s = round(out_tokens / wall_elapsed_s, 2) if wall_elapsed_s > 0 else 0.0
    # Estimate standard cloud API cost for GPT-6-Sol ($2.50/1M in, $10.00/1M out)
    est_cost = (in_tokens * 2.50 / 1_000_000.0) + (out_tokens * 10.00 / 1_000_000.0)
    gates = verify_sandbox_gates(sb_path)
    log_stream(
        f"[{name}] FINISHED in {wall_elapsed_s:.2f}s (TTFT={ttft_ms}ms, tok/s={tok_per_s}, est_cost=${est_cost:.4f}) | "
        f"Gates: ruff={gates['ruff_rc']} mypy={gates['mypy_rc']} pytest={gates['pytest_rc']} ({gates['pytest_digest']})"
    )
    return {
        "contestant": name,
        "type": "CLOUD",
        "model": model_used,
        "endpoint": "codex exec (OpenAI Cloud API)",
        "sandbox": sb_path,
        "ttft_ms": ttft_ms,
        "llm_elapsed_s": round(wall_elapsed_s, 3),
        "wall_elapsed_s": round(wall_elapsed_s, 3),
        "input_tokens": in_tokens,
        "completion_tokens": out_tokens,
        "tok_per_s": tok_per_s,
        "marginal_cost_usd": round(est_cost, 6),
        "tool_calls": tool_calls,
        "gates": gates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local vs Cloud Coding Agent Sandbox Race"
    )
    parser.add_argument(
        "--only", type=str, default="", help="Run only matching contestant"
    )
    args = parser.parse_args()

    log_stream(
        "=== AGENT-103: STARTING 4-WAY LOCAL VS CLOUD CODING AGENT SANDBOX RACE (QUEUE ROW: dl-f4-live-1) ==="
    )
    existing_summary: dict[str, Any] = {}
    if args.only and os.path.isfile(RESULTS_JSON):
        try:
            with open(RESULTS_JSON, "r", encoding="utf-8") as f:
                existing_summary = json.load(f)
        except (OSError, json.JSONDecodeError):
            existing_summary = {}

    pre_race_red: dict[str, Any] = dict(existing_summary.get("pre_race_red") or {})
    for key, sb_path in SANDBOXES.items():
        if args.only and args.only not in key:
            continue
        red_info = reset_sandbox_to_red(sb_path)
        pre_race_red[key] = red_info
        log_stream(
            f"[PRE-RACE RED CHECK] {key}: rc={red_info['red_rc']} | {red_info['red_digest']}"
        )

    results_by_name: dict[str, dict[str, Any]] = {
        r["contestant"]: r
        for r in (existing_summary.get("results") or [])
        if isinstance(r, dict) and "contestant" in r
    }

    if not args.only or args.only in "local_2080ti_coder7b":
        res_137 = run_local_agent_contestant(
            name="local_2080ti_coder7b",
            model_id="qwen2.5-coder:7b-16k",
            endpoint="http://10.0.10.137:11434/v1/chat/completions",
            sb_path=SANDBOXES["local_2080ti_coder7b"],
        )
        results_by_name["local_2080ti_coder7b"] = res_137
    if not args.only or args.only in "local_qwen36_heretic":
        res_82 = run_local_agent_contestant(
            name="local_qwen36_heretic",
            model_id="qwen3.6-35b-a3b-heretic",
            endpoint="http://10.0.70.82:18088/v1/chat/completions",
            sb_path=SANDBOXES["local_qwen36_heretic"],
            extra_payload={"chat_template_kwargs": {"enable_thinking": False}},
        )
        results_by_name["local_qwen36_heretic"] = res_82
    if not args.only or args.only in "cloud_claude_code":
        res_claude = run_claude_code_contestant(SANDBOXES["cloud_claude_code"])
        results_by_name["cloud_claude_code"] = res_claude
    if not args.only or args.only in "cloud_codex_cli":
        res_codex = run_codex_cli_contestant(SANDBOXES["cloud_codex_cli"])
        results_by_name["cloud_codex_cli"] = res_codex

    ordered_keys = [
        "local_2080ti_coder7b",
        "local_qwen36_heretic",
        "cloud_claude_code",
        "cloud_codex_cli",
    ]
    results = [results_by_name[k] for k in ordered_keys if k in results_by_name]

    summary = {
        "written_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "queue_row": "dl-f4-live-1",
        "queue_file": "/home/mboyle/bd-persist/queue/app-dl-fix.tsv",
        "target_file": "bulk_downloader/runner_teach.py",
        "target_test": "tests/test_dl_f4_teach_defer_claim_loop.py",
        "pre_race_red": pre_race_red,
        "results": results,
    }
    os.makedirs(os.path.dirname(RESULTS_JSON), exist_ok=True)
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    log_stream(f"=== RACE COMPLETE: Results saved to {RESULTS_JSON} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
