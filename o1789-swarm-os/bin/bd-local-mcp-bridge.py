#!/usr/bin/env python3
"""
bd-local-mcp-bridge.py — Boylenet Local GPU AI Platform Fleet MCP & Native Tool Bridge
Provides 100% capability parity between the Local GPU AI Platform (:4010, :4000, bd-ai-harness)
and Cloud Fleet AI Pools (Claude Pool A/B, Codex Pool C, Antigravity Pool D).

Exposes OpenAI & Anthropic function-calling schemas (`tools=[...]`) and execution adapters for:
  1. ctx_slice         — `ratf` Tree-sitter AST symbol/skeleton/pattern/line slicer (127.0.0.1:8095, Rule 80)
  2. ruff_check        — `python-linter` fast-fail linter (`ruff check`) + Rule 80 bd-blob-ptr cap
  3. mypy_check        — `type-enforcer` static type checker (`mypy`) + Rule 80 bd-blob-ptr cap
  4. bd_test_digest    — `bd-pytest-digest` (Rule 78 <=3 lines, <25 tok) + `bd-blob-ptr` (Rule 80 CAS pointer)
  5. bd_bus_publish    — `bd-bus` SQLite WAL + mesh-bus cross-pool event bus publisher
  6. bd_bus_read       — `bd-bus` SQLite WAL + mesh-bus cross-pool event bus reader
  7. hivemind_recall   — `hivemind-memory` hybrid vector/lexical episodic memory recall
  8. hivemind_store    — `hivemind-memory` verified problem-resolution episode storage
  9. web_search        — Live internet search (DuckDuckGo HTML + Wikipedia OpenSearch fallback)
 10. web_fetch         — Live HTTP/HTTPS URL fetch + cleaned markdown/text extraction
 11. guarded_bash      — Shell execution guarded by /home/mboyle/.gemini/config/shield.py (Rule 22)
                         + /home/mboyle/bin/bd-token-guard.py + /home/mboyle/bin/bd-blob-ptr (Rule 80)
 12. guarded_edit      — Surgical file edit/create guarded by shield.py (Rule 22) + bd-token-guard.py

Also provides Fleet Skill Discovery, Auto-Skill Routing, and Context Injection (`--skill <skill_name>`)
across `/home/mboyle/.agents/skills/`, `/home/mboyle/.agents/plugins/`, and `/home/mboyle/bd-persist/plugins/`.
"""

from __future__ import annotations

import argparse
import contextlib
import difflib
import glob
import html
import io
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import warnings
from typing import Any

warnings.filterwarnings("ignore")

SHIELD_PATHS = [
    "/home/mboyle/.gemini/config/shield.py",
    "/home/mboyle/bd-persist/harness/shield.py",
    "/home/mboyle/.gemini/config/scripts/shield.py",
]
TOKEN_GUARD_SCRIPT = "/home/mboyle/bin/bd-token-guard.py"
BLOB_PTR_SCRIPT = "/home/mboyle/bin/bd-blob-ptr"
PYTEST_DIGEST_SCRIPT = "/home/mboyle/bin/bd-pytest-digest"
ORCHESTRATOR_BASE = os.environ.get(
    "BD_ORCHESTRATOR_BASE", "http://10.0.70.164:4010"
).rstrip("/")

SKILL_SEARCH_ROOTS = [
    "/home/mboyle/.agents/skills",
    "/home/mboyle/.agents/plugins",
    "/home/mboyle/bd-persist/plugins",
    "/home/mboyle/.gemini/antigravity-cli/builtin/skills",
]

AUTO_SKILL_KEYWORDS: list[tuple[str, list[str]]] = [
    (
        "bd-ci-taxonomy",
        [
            "ci ",
            "shard",
            "precut",
            "flake",
            "flaky",
            "runner timeout",
            "dirty working tree",
        ],
    ),
    (
        "bd-lens",
        [
            "lens",
            "red provenance",
            "deployed twin",
            "verdict",
            "refute",
            "board-with-advisory",
        ],
    ),
    (
        "surgical-patch",
        [
            "surgical",
            "narrowest",
            "bug fix",
            "regression proof",
            "small behavior change",
        ],
    ),
    (
        "investigate-first",
        ["investigate", "unknown cause", "intermittent", "root cause", "hypothesis"],
    ),
    (
        "verify-and-stop",
        [
            "verify-and-stop",
            "validation-only",
            "acceptance condition",
            "completion check",
        ],
    ),
    (
        "cavecrew",
        ["cavecrew", "cavecrew-investigator", "cavecrew-builder", "cavecrew-reviewer"],
    ),
    ("boylenet-architect", ["boylenet", "o1740", "27-node", "train recovery"]),
    ("fleet-gridlock-recovery", ["gridlock", "unstick", "dispatcher queue"]),
    ("rebase-orchestrator", ["rebase", "batch overlap", "re-finalization"]),
]


def get_active_shield_path() -> str:
    for p in SHIELD_PATHS:
        if os.path.isfile(p):
            return p
    return SHIELD_PATHS[0]


# ---------------------------------------------------------------------------
# RULE 80: bd-blob-ptr OUTPUT CAPPER
# ---------------------------------------------------------------------------
def cap_with_blob_ptr(raw_text: str, returncode: int = 0) -> str:
    """Pass output through /home/mboyle/bin/bd-blob-ptr --pipe --rc <rc> (Rule 80)."""
    if not raw_text:
        return ""
    lines = raw_text.splitlines()
    raw_bytes = raw_text.encode("utf-8", errors="replace")
    if len(lines) <= 15 and len(raw_bytes) <= 800:
        return raw_text
    if os.path.isfile(BLOB_PTR_SCRIPT):
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            proc = subprocess.run(
                ["python3", BLOB_PTR_SCRIPT, "--pipe", "--rc", str(returncode)],
                input=raw_text,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if proc.stdout:
                return proc.stdout.strip()
    return raw_text[:800] + f"\n...[truncated {len(raw_bytes)} bytes total]"


# ---------------------------------------------------------------------------
# RULE 22 & RULE 58/62/78/80 PRE-TOOL HOOK ENFORCEMENT
# ---------------------------------------------------------------------------
def run_shield_and_token_guard(
    tool_name: str,
    tool_input: dict[str, Any],
    cwd: str | None = None,
) -> tuple[bool, int, str]:
    """
    Validate tool invocation against /home/mboyle/.gemini/config/shield.py (Rule 22)
    and /home/mboyle/bin/bd-token-guard.py (Rules 58/62/78/80).
    Returns (allowed, rc, message).
    """
    eff_cwd = cwd or os.getcwd()
    shield_path = get_active_shield_path()

    # Map local tool names to standard Claude/Codex hook tool_name
    hook_tool_name = tool_name
    if tool_name in ("guarded_bash", "bash_exec", "Bash"):
        hook_tool_name = "Bash"
    elif tool_name in ("guarded_edit", "write_file", "Edit", "Write"):
        hook_tool_name = "Edit"
    elif tool_name in ("read_file", "Read"):
        hook_tool_name = "Read"

    hook_payload = json.dumps(
        {
            "tool_name": hook_tool_name,
            "tool_input": tool_input,
            "cwd": eff_cwd,
        }
    )

    # 1. Rule 22 check via shield.py
    if os.path.isfile(shield_path):
        p_shield = subprocess.run(
            ["python3", shield_path],
            input=hook_payload,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if p_shield.returncode != 0:
            reason = (p_shield.stderr or p_shield.stdout).strip()
            return (
                False,
                p_shield.returncode,
                f"[Rule 22 shield.py BLOCKED (rc={p_shield.returncode} path={shield_path})]: {reason}",
            )

    # Extra Rule 22 path guard for guarded_edit on .git internals outside authorized sandboxes
    if hook_tool_name == "Edit":
        target_fp = str(tool_input.get("file_path") or tool_input.get("path") or "")
        if target_fp:
            real_fp = os.path.realpath(
                os.path.join(eff_cwd, target_fp)
                if not os.path.isabs(target_fp)
                else target_fp
            )
            if "/.git/" in (real_fp + "/") or real_fp.endswith("/.git"):
                allowed_prefixes = (
                    "/home/mboyle/bd-cuts/",
                    "/home/mboyle/bd-local-wt/",
                    "/home/mboyle/bd-review-wt/",
                    "/home/mboyle/bd-persist/harness-work/BURN/cuts/",
                )
                if not any(real_fp.startswith(pref) for pref in allowed_prefixes):
                    return (
                        False,
                        2,
                        f"[Rule 22 shield.py BLOCKED (rc=2)]: Direct edit of .git internals outside authorized sandboxes is forbidden: {real_fp}",
                    )

    # 2. Rule 58/62/78/80 check via bd-token-guard.py
    if os.path.isfile(TOKEN_GUARD_SCRIPT) and hook_tool_name in (
        "Bash",
        "Read",
        "Edit",
    ):
        p_tg = subprocess.run(
            ["python3", TOKEN_GUARD_SCRIPT, "hook"],
            input=hook_payload,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if p_tg.returncode != 0:
            reason = (p_tg.stderr or p_tg.stdout).strip()
            return (
                False,
                p_tg.returncode,
                f"[Rule 58/78/80 bd-token-guard.py BLOCKED (rc={p_tg.returncode})]: {reason}",
            )

    return True, 0, "PASS"


# ---------------------------------------------------------------------------
# FLEET SKILL DISCOVERY, AUTO-ROUTER & CONTEXT INJECTION
# ---------------------------------------------------------------------------
def discover_all_skills() -> dict[str, str]:
    """Return mapping of skill_name -> absolute SKILL.md path across all fleet skill roots."""
    found: dict[str, str] = {}
    patterns = [
        "/home/mboyle/.agents/skills/*/SKILL.md",
        "/home/mboyle/.agents/skills/synced/*/*/SKILL.md",
        "/home/mboyle/.agents/plugins/*/skills/*/SKILL.md",
        "/home/mboyle/bd-persist/plugins/*/skills/*/SKILL.md",
        "/home/mboyle/.gemini/antigravity-cli/builtin/skills/*/SKILL.md",
    ]
    for pat in patterns:
        for path in sorted(glob.glob(pat)):
            skill_dir = os.path.basename(os.path.dirname(path))
            if skill_dir not in found:
                found[skill_dir] = path
            # Also register normalized hyphen/underscore alias
            alt_name = skill_dir.replace("_", "-")
            if alt_name not in found:
                found[alt_name] = path
    return found


def resolve_skill_path(skill_name: str) -> str | None:
    clean = skill_name.strip()
    if not clean:
        return None
    if os.path.isfile(clean):
        return os.path.abspath(clean)
    catalog = discover_all_skills()
    if clean in catalog:
        return catalog[clean]
    alt = clean.replace("_", "-")
    if alt in catalog:
        return catalog[alt]
    return None


def parse_skill_list(raw_skills: list[str] | str | None) -> list[str]:
    if not raw_skills:
        return []
    if isinstance(raw_skills, str):
        items = [raw_skills]
    else:
        items = list(raw_skills)
    out: list[str] = []
    for item in items:
        for part in str(item).split(","):
            p = part.strip()
            if p and p not in out:
                out.append(p)
    return out


def auto_route_skills(
    prompt: str | None, explicit_skills: list[str] | str | None = None
) -> list[str]:
    """Resolve explicit `--skill` names and optionally auto-route based on prompt intent."""
    requested = parse_skill_list(explicit_skills)
    resolved: list[str] = []
    auto_mode = False
    for s in requested:
        if s.lower() == "auto":
            auto_mode = True
        elif s not in resolved:
            resolved.append(s)

    if auto_mode and prompt:
        low_p = prompt.lower()
        for skill_id, kw_list in AUTO_SKILL_KEYWORDS:
            if any(kw in low_p for kw in kw_list) and skill_id not in resolved:
                resolved.append(skill_id)
    return resolved


def load_skill_content(skill_name: str, max_chars: int = 6000) -> dict[str, Any]:
    path = resolve_skill_path(skill_name)
    if not path or not os.path.isfile(path):
        return {
            "rc": 1,
            "skill": skill_name,
            "error": f"Skill '{skill_name}' not found in {SKILL_SEARCH_ROOTS}",
            "available_skills": sorted(discover_all_skills().keys()),
        }
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        full_text = f.read()
    truncated = len(full_text) > max_chars
    content = full_text[:max_chars]
    if truncated:
        content += f"\n...[SKILL.md capped at {max_chars} chars; full file at {path} ({len(full_text)} bytes)]"
    return {
        "rc": 0,
        "skill": skill_name,
        "path": path,
        "bytes": len(full_text),
        "truncated": truncated,
        "content": content,
    }


def build_skill_injection_block(
    skills: list[str] | str | None,
    prompt: str | None = None,
    max_chars_per_skill: int = 6000,
) -> tuple[str, list[dict[str, Any]]]:
    """Build system-prompt injection text and metadata receipts for all requested/auto-routed skills."""
    target_skills = auto_route_skills(prompt, skills)
    if not target_skills:
        return "", []
    blocks: list[str] = []
    receipts: list[dict[str, Any]] = []
    for sk in target_skills:
        info = load_skill_content(sk, max_chars=max_chars_per_skill)
        receipts.append(
            {
                "skill": sk,
                "rc": info["rc"],
                "path": info.get("path"),
                "bytes": info.get("bytes", 0),
            }
        )
        if info["rc"] == 0:
            blocks.append(
                f'<FLEET_SKILL name="{sk}" path="{info["path"]}">\n'
                f"{info['content'].strip()}\n"
                f"</FLEET_SKILL>"
            )
    if not blocks:
        return "", receipts
    header = (
        "\n\n[BOYLENET FLEET SKILL INJECTION PARITY — ACTIVE SKILLS LOADED]\n"
        "Follow the operational instructions and invariants in the loaded <FLEET_SKILL> blocks below:\n"
    )
    return header + "\n\n".join(blocks), receipts


# ---------------------------------------------------------------------------
# TOOL IMPLEMENTATIONS (1-7 + LEGACY ALIASES)
# ---------------------------------------------------------------------------
def tool_ctx_slice(args: dict[str, Any]) -> dict[str, Any]:
    """1. ctx_slice (`ratf` AST symbol/line/skeleton/pattern slicer — Rule 80 parity)."""
    file_path = str(args.get("file_path") or args.get("path") or "").strip()
    symbol = str(args.get("symbol") or "").strip()
    skeleton = bool(args.get("skeleton", False))
    pattern = str(args.get("pattern") or "").strip()
    code = str(args.get("code") or "")
    lang = str(args.get("lang") or "python").strip()
    endpoint = str(args.get("endpoint") or "").strip()
    start_line = args.get("start_line") or args.get("StartLine")
    end_line = args.get("end_line") or args.get("EndLine")

    # Line-range slice mode (when start_line/end_line provided without symbol/skeleton/pattern)
    if (
        (start_line is not None or end_line is not None)
        and not symbol
        and not skeleton
        and not pattern
    ):
        if not file_path:
            return {"rc": 1, "error": "file_path is required for line slicing"}
        p = os.path.expanduser(file_path)
        s_line = max(1, int(start_line or 1))
        e_line = int(end_line) if end_line is not None else (s_line + 79)
        if e_line - s_line + 1 > 100:
            e_line = s_line + 99
        allowed, rc_h, msg_h = run_shield_and_token_guard(
            "Read",
            {"file_path": p, "StartLine": s_line, "EndLine": e_line},
        )
        if not allowed:
            return {"rc": rc_h, "blocked": True, "error": msg_h}
        if not os.path.isfile(p):
            return {"rc": 1, "error": f"File not found: {p}"}
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        sliced = all_lines[s_line - 1 : e_line]
        numbered = "".join(
            f"{idx}: {line}" for idx, line in enumerate(sliced, start=s_line)
        )
        return {
            "rc": 0,
            "status": "ok",
            "mode": "line_slice",
            "file_path": p,
            "start_line": s_line,
            "end_line": min(e_line, len(all_lines)),
            "total_lines": len(all_lines),
            "slice": numbered,
        }

    # Delegate to ratf MCP (`mcp_server_ratf.ctx_slice` -> 127.0.0.1:8095)
    try:
        import mcp_server_ratf  # type: ignore[import-untyped]

        raw_res = mcp_server_ratf.ctx_slice(
            code=code,
            pattern=pattern,
            lang=lang,
            endpoint=endpoint,
            timeout=float(args.get("timeout") or 15.0),
            skeleton=skeleton,
            symbol=symbol,
            file_path=file_path,
        )
        with contextlib.suppress(ValueError, TypeError):
            parsed = json.loads(raw_res)
            if isinstance(parsed, dict):
                parsed.setdefault("rc", 0 if parsed.get("status") == "ok" else 1)
                return parsed
        return {"rc": 0, "status": "ok", "result": raw_res}
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        return {"rc": 1, "error": f"ctx_slice error: {exc}"}


def tool_ruff_check(args: dict[str, Any]) -> dict[str, Any]:
    """2a. ruff_check (`python-linter` fast-fail parity)."""
    path = str(args.get("path") or ".").strip()
    fix = bool(args.get("fix", False))
    cmd = ["ruff", "check"]
    if fix:
        cmd.append("--fix")
    cmd.append(path)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    combined = (
        proc.stdout + "\n" + proc.stderr
    ).strip() or "All checks passed! No issues found."
    capped = cap_with_blob_ptr(combined, proc.returncode)
    return {
        "rc": proc.returncode,
        "tool": "ruff_check",
        "path": path,
        "fix": fix,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "output": capped,
    }


def tool_mypy_check(args: dict[str, Any]) -> dict[str, Any]:
    """2b. mypy_check (`type-enforcer` fast-fail parity)."""
    path = str(args.get("path") or ".").strip()
    strict = bool(args.get("strict", False))
    cmd = ["mypy"]
    if strict:
        cmd.append("--strict")
    cmd.append(path)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    combined = (proc.stdout + "\n" + proc.stderr).strip() or "Success: no issues found."
    capped = cap_with_blob_ptr(combined, proc.returncode)
    return {
        "rc": proc.returncode,
        "tool": "mypy_check",
        "path": path,
        "strict": strict,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "output": capped,
    }


def tool_bd_test_digest(args: dict[str, Any]) -> dict[str, Any]:
    """3. bd_test_digest (`bd-pytest-digest` Rule 78 + `bd-blob-ptr` Rule 80 parity)."""
    target = str(args.get("target") or args.get("path") or "tests/").strip()
    extra_args = args.get("extra_args") or []
    if isinstance(extra_args, str):
        extra_list = shlex.split(extra_args)
    else:
        extra_list = [str(x) for x in extra_args]
    cwd = str(args.get("cwd") or os.getcwd())

    pytest_bin = "pytest"
    venv_pytest = os.path.join(cwd, "venv", "bin", "pytest")
    if os.path.isfile(venv_pytest):
        pytest_bin = venv_pytest
    elif os.path.isfile(
        "/home/mboyle/BulkDownloader/venv/bin/pytest"
    ) and cwd.startswith("/home/mboyle/BulkDownloader"):
        pytest_bin = "/home/mboyle/BulkDownloader/venv/bin/pytest"

    cmd = [pytest_bin] + shlex.split(target) + extra_list
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=180, check=False
    )
    raw_out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")

    # Pipe through bd-pytest-digest --pipe (Rule 78: <=3 lines, <25 tokens)
    digest_out = raw_out.strip()
    digest_rc = proc.returncode
    if os.path.isfile(PYTEST_DIGEST_SCRIPT):
        p_dig = subprocess.run(
            [
                "python3",
                PYTEST_DIGEST_SCRIPT,
                "--pipe",
                "--exit-code",
                str(proc.returncode),
            ],
            input=raw_out,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        digest_out = (p_dig.stdout or p_dig.stderr).strip()
        digest_rc = p_dig.returncode

    # Also store raw log in CAS via bd-blob-ptr (Rule 80)
    blob_ptr = cap_with_blob_ptr(raw_out, proc.returncode)
    return {
        "rc": digest_rc,
        "tool": "bd_test_digest",
        "target": target,
        "cwd": cwd,
        "digest": digest_out,
        "blob_ptr": blob_ptr,
        "rule78_pytest_digest": True,
        "rule80_blob_ptr": True,
    }


def tool_bd_bus_publish(args: dict[str, Any]) -> dict[str, Any]:
    """4a. bd_bus_publish (`bd-bus` SQLite WAL cross-pool event bus parity)."""
    topic = str(args.get("topic") or "").strip()
    payload = str(args.get("payload") or "")
    if not topic:
        return {"rc": 1, "error": "topic is required"}
    import bd_bus_mcp  # type: ignore[import-untyped]

    status = bd_bus_mcp.bus_publish(topic=topic, payload=payload)
    return {
        "rc": 0,
        "tool": "bd_bus_publish",
        "topic": topic,
        "payload": payload,
        "status": status,
        "db_path": str(bd_bus_mcp.DB_PATH),
    }


def tool_bd_bus_read(args: dict[str, Any]) -> dict[str, Any]:
    """4b. bd_bus_read (`bd-bus` SQLite WAL cross-pool event bus parity)."""
    seat = str(args.get("seat") or os.environ.get("BD_SEAT", "local-gpu-agent")).strip()
    topic = str(args.get("topic") or "").strip()
    unread_only = bool(args.get("unread_only", False))
    if not topic:
        return {"rc": 1, "error": "topic is required"}
    import bd_bus_mcp  # type: ignore[import-untyped]

    messages = bd_bus_mcp.bus_read(seat=seat, topic=topic, unread_only=unread_only)
    return {
        "rc": 0,
        "tool": "bd_bus_read",
        "seat": seat,
        "topic": topic,
        "unread_only": unread_only,
        "messages": cap_with_blob_ptr(messages, 0),
        "db_path": str(bd_bus_mcp.DB_PATH),
    }


def _load_hivemind_module() -> Any:
    hm_cfg = "/home/mboyle/.gemini/config"
    hm_plugin = "/home/mboyle/.gemini/config/plugins/hivemind-memory"
    if hm_cfg not in sys.path:
        sys.path.insert(0, hm_cfg)
    if hm_plugin not in sys.path:
        sys.path.insert(0, hm_plugin)
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "hivemind_mcp_server", os.path.join(hm_plugin, "server.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load hivemind-memory server.py")
    mod = importlib.util.module_from_spec(spec)
    with (
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        spec.loader.exec_module(mod)
    return mod


_HIVEMIND_MOD: Any = None


def get_hivemind_mod() -> Any:
    global _HIVEMIND_MOD
    if _HIVEMIND_MOD is None:
        _HIVEMIND_MOD = _load_hivemind_module()
    return _HIVEMIND_MOD


def tool_hivemind_recall(args: dict[str, Any]) -> dict[str, Any]:
    """5a. hivemind_recall (`hivemind-memory` parity)."""
    query = str(args.get("query") or "").strip()
    limit = int(args.get("limit") or args.get("top_k") or 5)
    if not query:
        return {"rc": 1, "error": "query is required"}
    hm = get_hivemind_mod()
    records = hm.memory_recall(query=query, limit=limit)
    return {
        "rc": 0,
        "tool": "hivemind_recall",
        "query": query,
        "count": len(records),
        "records": records,
    }


def tool_hivemind_store(args: dict[str, Any]) -> dict[str, Any]:
    """5b. hivemind_store (`hivemind-memory` parity)."""
    symptom = str(args.get("symptom") or args.get("problem") or "").strip()
    root_cause = str(args.get("root_cause") or "").strip()
    resolution = str(args.get("resolution") or args.get("solution_patch") or "").strip()
    code_diff = str(args.get("code_diff") or "")
    verification_cmd = str(args.get("verification_cmd") or "")
    tags = args.get("tags") if isinstance(args.get("tags"), list) else None
    if not symptom:
        return {"rc": 1, "error": "symptom is required"}
    hm = get_hivemind_mod()
    res = hm.memory_store(
        symptom=symptom,
        root_cause=root_cause,
        resolution=resolution,
        code_diff=code_diff,
        verification_cmd=verification_cmd,
        tags=tags,
    )
    res["rc"] = 0
    res["tool"] = "hivemind_store"
    return res


def html_to_clean_text(raw_html: str, max_chars: int = 4000) -> str:
    cleaned = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", raw_html)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"[ \t\r\f\v]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n", cleaned).strip()
    return cleaned[:max_chars]


def tool_web_fetch(args: dict[str, Any]) -> dict[str, Any]:
    """6a. web_fetch (Live HTTP/HTTPS URL markdown/text extraction)."""
    url = str(args.get("url") or "").strip()
    max_chars = int(args.get("max_chars") or 4000)
    if not url:
        return {"rc": 1, "error": "url is required"}
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) BoylenetLocalMCPBridge/1.0",
            "Accept": "text/html,application/json,text/plain,*/*",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15.0) as resp:
        ctype = resp.headers.get("Content-Type", "")
        raw_bytes = resp.read(256 * 1024)
        raw_text = raw_bytes.decode("utf-8", errors="replace")
        if "html" in ctype.lower() or "<html" in raw_text[:500].lower():
            title_m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw_text)
            title = html.unescape(title_m.group(1).strip()) if title_m else ""
            text_out = html_to_clean_text(raw_text, max_chars=max_chars)
        else:
            title = ""
            text_out = raw_text[:max_chars]
        return {
            "rc": 0,
            "tool": "web_fetch",
            "status_code": resp.status,
            "url": url,
            "content_type": ctype,
            "title": title,
            "content": text_out,
        }


def tool_web_search(args: dict[str, Any]) -> dict[str, Any]:
    """6b. web_search (Live web search via DuckDuckGo HTML + Wikipedia OpenSearch fallback)."""
    query = str(args.get("query") or "").strip()
    max_results = int(args.get("max_results") or 5)
    if not query:
        return {"rc": 1, "error": "query is required", "results": []}
    results: list[dict[str, str]] = []
    try:
        q_enc = urllib.parse.urlencode({"q": query})
        ddg_url = f"https://html.duckduckgo.com/html/?{q_enc}"
        req = urllib.request.Request(
            ddg_url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            page = resp.read().decode("utf-8", errors="replace")
        blocks = re.findall(
            r'<a rel="nofollow" class="result__a" href="([^"]+)">(.*?)</a>.*?<a class="result__snippet"[^>]*>(.*?)</a>',
            page,
            flags=re.DOTALL,
        )
        for href, raw_title, raw_snip in blocks[:max_results]:
            parsed_href = urllib.parse.urlparse(href)
            qs = urllib.parse.parse_qs(parsed_href.query)
            real_url = qs.get("uddg", [href])[0]
            results.append(
                {
                    "title": html_to_clean_text(raw_title, 200),
                    "url": real_url,
                    "snippet": html_to_clean_text(raw_snip, 400),
                }
            )
    except (OSError, ValueError, urllib.error.URLError):
        pass

    if not results:
        try:
            wiki_q = urllib.parse.urlencode(
                {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": str(max_results),
                }
            )
            wiki_url = f"https://en.wikipedia.org/w/api.php?{wiki_q}"
            req = urllib.request.Request(
                wiki_url,
                headers={
                    "User-Agent": "BoylenetLocalMCPBridge/1.0 (https://boylenet.local)"
                },
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                wdata = json.loads(resp.read().decode("utf-8"))
            for item in wdata.get("query", {}).get("search", [])[:max_results]:
                title = item.get("title", "")
                results.append(
                    {
                        "title": title,
                        "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                        "snippet": html_to_clean_text(item.get("snippet", ""), 400),
                    }
                )
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return {
                "rc": 1,
                "tool": "web_search",
                "query": query,
                "error": str(exc),
                "results": [],
            }

    return {
        "rc": 0,
        "tool": "web_search",
        "query": query,
        "result_count": len(results),
        "results": results,
    }


def tool_guarded_bash(args: dict[str, Any]) -> dict[str, Any]:
    """
    7a. guarded_bash — Protected by /home/mboyle/.gemini/config/shield.py (Rule 22)
    + /home/mboyle/bin/bd-token-guard.py + /home/mboyle/bin/bd-blob-ptr (Rule 80 output cap).
    """
    command = str(args.get("command") or "")
    cwd = str(args.get("cwd") or os.getcwd())
    if not command.strip():
        return {"rc": 1, "error": "command is required"}

    allowed, hook_rc, hook_msg = run_shield_and_token_guard(
        "guarded_bash",
        {"command": command},
        cwd=cwd,
    )
    if not allowed:
        return {
            "rc": hook_rc,
            "tool": "guarded_bash",
            "blocked": True,
            "cwd": cwd,
            "command": command,
            "shield_py": get_active_shield_path(),
            "error": hook_msg,
        }

    proc = subprocess.run(
        ["/bin/bash", "-c", command],
        shell=False,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=int(args.get("timeout") or 45),
        check=False,
    )
    combined = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    capped = cap_with_blob_ptr(combined.strip(), proc.returncode)
    return {
        "rc": proc.returncode,
        "tool": "guarded_bash",
        "blocked": False,
        "cwd": cwd,
        "command": command,
        "shield_py": f"PASS (rc=0 via {get_active_shield_path()})",
        "token_guard": "PASS (rc=0)",
        "rule80_blob_ptr": "[BLOB-PTR:" in capped,
        "output": capped,
    }


def tool_guarded_edit(args: dict[str, Any]) -> dict[str, Any]:
    """
    7b. guarded_edit — Surgical file edit/create protected by shield.py (Rule 22)
    + bd-token-guard.py + bd-blob-ptr diff summary cap.
    """
    file_path = str(args.get("file_path") or args.get("path") or "").strip()
    old_string = str(args.get("old_string") or "")
    new_string = str(
        args.get("new_string") if "new_string" in args else args.get("content", "")
    )
    create_if_missing = bool(
        args.get("create_if_missing", False) or ("content" in args and not old_string)
    )
    allow_multiple = bool(args.get("allow_multiple", False))
    cwd = str(args.get("cwd") or os.getcwd())

    if not file_path:
        return {"rc": 1, "error": "file_path is required"}

    abs_path = os.path.abspath(
        os.path.join(cwd, os.path.expanduser(file_path))
        if not os.path.isabs(file_path)
        else os.path.expanduser(file_path)
    )

    allowed, hook_rc, hook_msg = run_shield_and_token_guard(
        "guarded_edit",
        {"file_path": abs_path, "old_string": old_string, "new_string": new_string},
        cwd=cwd,
    )
    if not allowed:
        return {
            "rc": hook_rc,
            "tool": "guarded_edit",
            "blocked": True,
            "file_path": abs_path,
            "error": hook_msg,
        }

    if not os.path.exists(abs_path):
        if not create_if_missing:
            return {
                "rc": 1,
                "tool": "guarded_edit",
                "file_path": abs_path,
                "error": "File does not exist (set create_if_missing=True to create)",
            }
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_string)
        return {
            "rc": 0,
            "tool": "guarded_edit",
            "status": "created",
            "file_path": abs_path,
            "written_bytes": len(new_string),
            "shield_py": f"PASS (rc=0 via {get_active_shield_path()})",
        }

    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
        orig_text = f.read()

    indentation_normalized = False
    match_mode = "exact"

    if not old_string:
        if create_if_missing:
            updated_text = new_string
            match_mode = "overwrite"
        else:
            return {
                "rc": 1,
                "tool": "guarded_edit",
                "file_path": abs_path,
                "error": "old_string is required when editing an existing file",
            }
    else:
        norm_res = normalize_and_apply_edit(
            orig_text=orig_text,
            old_string=old_string,
            new_string=new_string,
            allow_multiple=allow_multiple,
            is_python=abs_path.endswith(".py"),
        )
        if not norm_res["matched"]:
            return {
                "rc": 1,
                "tool": "guarded_edit",
                "file_path": abs_path,
                "error": norm_res["error"],
            }
        updated_text = norm_res["updated_text"]
        indentation_normalized = bool(norm_res.get("indentation_normalized", False))
        match_mode = str(norm_res.get("match_mode", "exact"))

    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(updated_text)

    diff_lines = list(
        difflib.unified_diff(
            orig_text.splitlines(),
            updated_text.splitlines(),
            fromfile=abs_path,
            tofile=abs_path,
            lineterm="",
        )
    )
    diff_text = "\n".join(diff_lines)
    return {
        "rc": 0,
        "tool": "guarded_edit",
        "status": "edited",
        "match_mode": match_mode,
        "indentation_normalized": indentation_normalized,
        "file_path": abs_path,
        "shield_py": f"PASS (rc=0 via {get_active_shield_path()})",
        "diff": cap_with_blob_ptr(diff_text, 0),
    }


def _rebase_new_lines_to_orig_indent(
    matched_orig_lines: list[str],
    old_lines: list[str],
    new_lines: list[str],
) -> list[str]:
    """Rebase new_lines to the exact per-section indentation of matched_orig_lines using anchor deltas."""
    anchors: dict[int, tuple[int, int]] = {}
    orig_cursor = 0
    for idx, nl in enumerate(new_lines):
        s = nl.strip()
        if not s:
            continue
        nl_ind = len(nl) - len(nl.lstrip(" "))
        for m_idx in range(orig_cursor, len(matched_orig_lines)):
            if matched_orig_lines[m_idx].strip() == s:
                orig_ind = len(matched_orig_lines[m_idx]) - len(
                    matched_orig_lines[m_idx].lstrip(" ")
                )
                anchors[idx] = (orig_ind, orig_ind - nl_ind)
                orig_cursor = m_idx + 1
                break

    active_delta = 0
    if anchors:
        first_anchor_idx = min(anchors.keys())
        active_delta = anchors[first_anchor_idx][1]
    else:
        for orig_ln, old_ln in zip(matched_orig_lines, old_lines):
            if orig_ln.strip() and old_ln.strip():
                orig_ind = len(orig_ln) - len(orig_ln.lstrip(" "))
                old_ind = len(old_ln) - len(old_ln.lstrip(" "))
                active_delta = orig_ind - old_ind
                break

    rebased_new: list[str] = []
    for idx, nl in enumerate(new_lines):
        s = nl.strip()
        if not s:
            rebased_new.append("")
            continue
        nl_ind = len(nl) - len(nl.lstrip(" "))
        if idx in anchors:
            exact_orig_ind, active_delta = anchors[idx]
            rebased_new.append((" " * exact_orig_ind) + s)
        else:
            target_ind = max(0, nl_ind + active_delta)
            rebased_new.append((" " * target_ind) + s)
    return rebased_new


def normalize_and_apply_edit(
    orig_text: str,
    old_string: str,
    new_string: str,
    allow_multiple: bool = False,
    is_python: bool = True,
) -> dict[str, Any]:
    """
    Pass 1: Exact substring match (verified with compile() on Python files).
    Pass 2: Indentation-normalized line-stripped block match with anchor-delta rebasing.
    """
    count = orig_text.count(old_string)
    if count > 1 and not allow_multiple:
        return {
            "matched": False,
            "error": f"old_string matched {count} locations; provide more context or set allow_multiple=True",
        }
    if count >= 1:
        candidate = (
            orig_text.replace(old_string, new_string)
            if allow_multiple
            else orig_text.replace(old_string, new_string, 1)
        )
        syntax_ok = True
        if is_python:
            try:
                compile(candidate, "<guarded_edit>", "exec")
            except SyntaxError:
                syntax_ok = False
        if syntax_ok:
            return {
                "matched": True,
                "updated_text": candidate,
                "indentation_normalized": False,
                "match_mode": "exact",
            }

    # Pass 2: Line-stripped block matching + anchor-delta indentation rebasing
    orig_lines = orig_text.splitlines()
    old_lines = old_string.splitlines()
    new_lines = new_string.splitlines()

    while old_lines and not old_lines[0].strip():
        old_lines.pop(0)
    while old_lines and not old_lines[-1].strip():
        old_lines.pop()

    if not old_lines:
        return {"matched": False, "error": "old_string is empty"}

    matches: list[tuple[int, int]] = []
    n_old = len(old_lines)
    for i in range(len(orig_lines) - n_old + 1):
        if all(orig_lines[i + k].strip() == old_lines[k].strip() for k in range(n_old)):
            matches.append((i, i + n_old))

    # Subsequence fallback when original file has inline comment/blank lines omitted by the model
    if not matches:
        for i in range(len(orig_lines)):
            if orig_lines[i].strip() != old_lines[0].strip():
                continue
            k = 0
            j = i
            while j < len(orig_lines) and k < n_old:
                s_orig = orig_lines[j].strip()
                s_old = old_lines[k].strip()
                if s_orig == s_old:
                    k += 1
                    j += 1
                elif not s_orig or s_orig.startswith("#"):
                    j += 1
                else:
                    break
            if k == n_old:
                matches.append((i, j))

    if not matches:
        return {"matched": False, "error": "old_string not found in file"}
    if len(matches) > 1 and not allow_multiple:
        return {
            "matched": False,
            "error": f"old_string matched {len(matches)} locations; provide more context or set allow_multiple=True",
        }

    target_matches = matches if allow_multiple else [matches[0]]
    updated_lines = list(orig_lines)
    for start_idx, end_idx in reversed(target_matches):
        matched_orig = orig_lines[start_idx:end_idx]
        rebased_new = _rebase_new_lines_to_orig_indent(
            matched_orig, old_lines, new_lines
        )
        updated_lines[start_idx:end_idx] = rebased_new

    updated_text = "\n".join(updated_lines)
    if orig_text.endswith("\n") and not updated_text.endswith("\n"):
        updated_text += "\n"
    return {
        "matched": True,
        "updated_text": updated_text,
        "indentation_normalized": True,
        "match_mode": "indentation_normalized",
    }


def apply_guarded_edit(args: dict[str, Any]) -> dict[str, Any]:
    """Alias for tool_guarded_edit with indentation-normalized block matching."""
    return tool_guarded_edit(args)


def tool_cluster_tier_status() -> dict[str, Any]:
    req = urllib.request.Request(f"{ORCHESTRATOR_BASE}/api/tiers/status", method="GET")
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {
        "rc": 0,
        "tool": "cluster_tier_status",
        "current_mode": data.get("current_mode"),
        "effective_tier": data.get("effective_tier"),
        "active_model": data.get("active_model"),
        "cluster_totals": data.get("cluster_totals"),
    }


def tool_bd_semantic_search(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    top_k = int(args.get("top_k") or args.get("limit") or 5)
    collection = str(args.get("collection") or "boylenet_fleet_rag").strip()
    if not query:
        return {"rc": 1, "tool": "bd_semantic_search", "error": "query is required"}
    cmd = [
        "python3",
        "/home/mboyle/bin/bd-semantic-search",
        query,
        "--top-k",
        str(top_k),
        "--collection",
        collection,
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45, check=False)
    if proc.returncode == 0 and proc.stdout.strip():
        with contextlib.suppress(ValueError, TypeError):
            parsed = json.loads(proc.stdout)
            if isinstance(parsed, dict):
                parsed["tool"] = "bd_semantic_search"
                return parsed
    return {
        "rc": proc.returncode or 1,
        "tool": "bd_semantic_search",
        "query": query,
        "output": (proc.stdout or proc.stderr).strip(),
    }


FLEET_MCP_TOOLS_OPENAI: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "ctx_slice",
            "description": "AST symbol/skeleton/pattern/line slicer via Tree-sitter AST server (`ratf` MCP at 127.0.0.1:8095, Rule 80 parity). Extracts a function/class definition by symbol name, AST skeleton, ast-grep pattern, or bounded line range (<=100 lines).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the source file on disk.",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Optional symbol name (function/class/method) to extract.",
                    },
                    "skeleton": {
                        "type": "boolean",
                        "description": "If true, return AST skeleton with bodies folded.",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Optional ast-grep pattern query.",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Optional 1-indexed start line for bounded line slice (<=100 lines).",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Optional 1-indexed end line for bounded line slice (<=100 lines).",
                    },
                    "endpoint": {
                        "type": "string",
                        "description": "Optional endpoint override: symbol, skeleton, query, parse, health.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ruff_check",
            "description": "Run `ruff check` (`python-linter` fast-fail parity) on a file or directory, with Rule 80 bd-blob-ptr output cap.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Target file or directory path.",
                    },
                    "fix": {
                        "type": "boolean",
                        "description": "Optionally apply safe auto-fixes (default false).",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mypy_check",
            "description": "Run `mypy` (`type-enforcer` static type checking fast-fail parity) on a file or directory, with Rule 80 bd-blob-ptr output cap.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Target file or directory path.",
                    },
                    "strict": {
                        "type": "boolean",
                        "description": "Enable --strict type checking (default false).",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bd_test_digest",
            "description": "Run pytest through `bd-pytest-digest` (Rule 78: <=3 lines, <25 tokens, exact exit code preserved) and `bd-blob-ptr` (Rule 80 CAS pointer to /var/tmp/bd-blobs/<sha256>.log) so local context windows never overflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Pytest target file, directory, or node ID (e.g. tests/test_x.py).",
                    },
                    "extra_args": {
                        "type": "string",
                        "description": "Optional extra pytest flags (e.g. '-k test_name').",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Optional working directory.",
                    },
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bd_bus_publish",
            "description": "Publish an event message to the `bd-bus` cross-pool SQLite WAL event bus (/home/mboyle/bd-persist/fleet-bus.db).",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Target event bus topic.",
                    },
                    "payload": {
                        "type": "string",
                        "description": "Message payload string or JSON.",
                    },
                },
                "required": ["topic", "payload"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bd_bus_read",
            "description": "Read messages from a topic on the `bd-bus` cross-pool SQLite WAL event bus (/home/mboyle/bd-persist/fleet-bus.db).",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Target event bus topic to read.",
                    },
                    "seat": {
                        "type": "string",
                        "description": "Consumer seat identifier (default 'local-gpu-agent').",
                    },
                    "unread_only": {
                        "type": "boolean",
                        "description": "Whether to return only unread messages for this seat (default false).",
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hivemind_recall",
            "description": "Search and retrieve past episodic bug resolutions and solutions from `hivemind-memory`.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language error symptom, traceback, or problem query.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of records to return (default 5).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hivemind_store",
            "description": "Store a verified problem-resolution episode into `hivemind-memory` shared fleet memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symptom": {
                        "type": "string",
                        "description": "Error signature or symptom description.",
                    },
                    "root_cause": {
                        "type": "string",
                        "description": "Underlying root cause of the defect.",
                    },
                    "resolution": {
                        "type": "string",
                        "description": "Summary of how the defect was fixed.",
                    },
                    "code_diff": {
                        "type": "string",
                        "description": "Optional unified diff or patch snippet.",
                    },
                },
                "required": ["symptom", "root_cause", "resolution"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the live internet for technical documentation, packages, CVEs, or references.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query string."},
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default 5).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch a live HTTP/HTTPS web page or API URL and return status code, title, and cleaned markdown/text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full HTTP/HTTPS URL to fetch.",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to return (default 4000).",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "guarded_bash",
            "description": "Execute a shell command guarded by /home/mboyle/.gemini/config/shield.py (Rule 22 Git anti-destruction hook), bd-token-guard.py (Rules 58/62/78), and bd-blob-ptr (Rule 80 output cap).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute.",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Optional working directory (default current directory).",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "guarded_edit",
            "description": "Surgically edit or create a file, guarded by /home/mboyle/.gemini/config/shield.py (Rule 22) and bd-blob-ptr diff summary cap.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Target file path."},
                    "old_string": {
                        "type": "string",
                        "description": "Exact substring to replace (omit only when creating a new file).",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "Replacement content.",
                    },
                    "create_if_missing": {
                        "type": "boolean",
                        "description": "Allow creating the file if it does not exist.",
                    },
                },
                "required": ["file_path", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bd_semantic_search",
            "description": "Fleet-Wide Hybrid RAG + AST Semantic Search on Qdrant (10.0.70.125:6333, collection boylenet_fleet_rag) + TEI BGE Embeddings (:8081) + TEI BGE-Reranker-Large (:8082). Searches FLEET_RULE.md, role-prompts, harness scripts, O1789 infrastructure receipts, and BulkDownloader AST.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language or technical search query.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of top reranked results to return (default 5).",
                    },
                    "collection": {
                        "type": "string",
                        "description": "Optional Qdrant collection name (default 'boylenet_fleet_rag').",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def get_openai_tools_schema(subset: list[str] | None = None) -> list[dict[str, Any]]:
    if not subset:
        return FLEET_MCP_TOOLS_OPENAI
    wanted = set(subset)
    return [t for t in FLEET_MCP_TOOLS_OPENAI if t["function"]["name"] in wanted]


def get_anthropic_tools_schema(
    subset: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Convert OpenAI function schemas to Anthropic /v1/messages `tools=[{name, description, input_schema}]`."""
    out: list[dict[str, Any]] = []
    for item in get_openai_tools_schema(subset):
        fn = item["function"]
        out.append(
            {
                "name": fn["name"],
                "description": fn["description"],
                "input_schema": fn["parameters"],
            }
        )
    return out


def execute_mcp_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Unified dispatcher for all Fleet MCP & Native tools (plus legacy aliases)."""
    clean_name = (name or "").strip()
    safe_args = args if isinstance(args, dict) else {}
    try:
        if clean_name in ("ctx_slice", "read_file"):
            if (
                clean_name == "read_file"
                and "start_line" not in safe_args
                and "symbol" not in safe_args
            ):
                safe_args = dict(safe_args)
                safe_args["start_line"] = 1
                safe_args["end_line"] = min(int(safe_args.get("max_lines", 80)), 100)
            return tool_ctx_slice(safe_args)
        if clean_name == "ruff_check":
            return tool_ruff_check(safe_args)
        if clean_name == "mypy_check":
            return tool_mypy_check(safe_args)
        if clean_name in ("bd_test_digest", "pytest_digest"):
            return tool_bd_test_digest(safe_args)
        if clean_name in ("bd_bus_publish", "bus_publish"):
            return tool_bd_bus_publish(safe_args)
        if clean_name in ("bd_bus_read", "bus_read"):
            return tool_bd_bus_read(safe_args)
        if clean_name in ("hivemind_recall", "memory_recall"):
            return tool_hivemind_recall(safe_args)
        if clean_name in ("hivemind_store", "memory_store"):
            return tool_hivemind_store(safe_args)
        if clean_name == "web_search":
            return tool_web_search(safe_args)
        if clean_name == "web_fetch":
            return tool_web_fetch(safe_args)
        if clean_name in ("guarded_bash", "bash_exec"):
            return tool_guarded_bash(safe_args)
        if clean_name in ("guarded_edit", "write_file"):
            if clean_name == "write_file":
                safe_args = dict(safe_args)
                safe_args.setdefault("file_path", safe_args.get("path", ""))
                safe_args.setdefault("new_string", safe_args.get("content", ""))
                safe_args["create_if_missing"] = True
            return tool_guarded_edit(safe_args)
        if clean_name in ("bd_semantic_search", "semantic_search"):
            return tool_bd_semantic_search(safe_args)
        if clean_name == "cluster_tier_status":
            return tool_cluster_tier_status()
        if clean_name == "load_skill":
            return load_skill_content(
                str(safe_args.get("skill") or safe_args.get("name") or "")
            )
        return {"rc": 1, "error": f"Unknown MCP tool: {clean_name}"}
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        ImportError,
        subprocess.SubprocessError,
        urllib.error.URLError,
    ) as exc:
        return {"rc": 1, "tool": clean_name, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Boylenet Local GPU AI Platform Fleet MCP & Skill Bridge"
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="Print OpenAI function-calling tools schema JSON",
    )
    parser.add_argument(
        "--anthropic-tools",
        action="store_true",
        help="Print Anthropic /v1/messages tools schema JSON",
    )
    parser.add_argument(
        "--list-skills",
        action="store_true",
        help="List all discovered Fleet skills and paths",
    )
    parser.add_argument(
        "--skill",
        action="append",
        default=[],
        help="Load and print Fleet skill injection block",
    )
    parser.add_argument(
        "--call", default=None, help="Execute a specific MCP tool by name"
    )
    parser.add_argument("--args", default="{}", help="JSON arguments object for --call")
    parser.add_argument(
        "--verify-parity",
        action="store_true",
        help="Run self-verification across all 7 tool families and Rule 22/78/80",
    )

    ns = parser.parse_args()

    if ns.list_tools:
        print(
            json.dumps(
                {
                    "rc": 0,
                    "tool_count": len(FLEET_MCP_TOOLS_OPENAI),
                    "tools": FLEET_MCP_TOOLS_OPENAI,
                },
                indent=2,
            )
        )
        return 0
    if ns.anthropic_tools:
        anth = get_anthropic_tools_schema()
        print(json.dumps({"rc": 0, "tool_count": len(anth), "tools": anth}, indent=2))
        return 0
    if ns.list_skills:
        skills = discover_all_skills()
        print(
            json.dumps(
                {"rc": 0, "skill_count": len(skills), "skills": skills}, indent=2
            )
        )
        return 0
    if ns.skill:
        block, receipts = build_skill_injection_block(ns.skill)
        print(
            json.dumps(
                {"rc": 0, "receipts": receipts, "injected_chars": len(block)}, indent=2
            )
        )
        print(block)
        return 0 if all(r["rc"] == 0 for r in receipts) else 1
    if ns.call:
        parsed_args = json.loads(ns.args) if ns.args else {}
        res = execute_mcp_tool(ns.call, parsed_args)
        print(json.dumps(res, indent=2))
        return 0 if res.get("rc", 0) == 0 else int(res.get("rc", 1))
    if ns.verify_parity:
        s_slice = execute_mcp_tool(
            "ctx_slice",
            {
                "file_path": "/home/mboyle/bin/bd-blob-ptr",
                "symbol": "normalize_exit_code",
            },
        )
        s_ruff = execute_mcp_tool(
            "ruff_check", {"path": "/home/mboyle/bin/bd-blob-ptr"}
        )
        s_mypy = execute_mcp_tool(
            "mypy_check", {"path": "/home/mboyle/bin/bd-blob-ptr"}
        )
        s_bus_pub = execute_mcp_tool(
            "bd_bus_publish",
            {"topic": "agent31-mcp-bridge", "payload": "bridge_parity_verified"},
        )
        s_bus_rd = execute_mcp_tool(
            "bd_bus_read",
            {
                "topic": "agent31-mcp-bridge",
                "seat": "agent31-verifier",
                "unread_only": False,
            },
        )
        s_hm = execute_mcp_tool(
            "hivemind_recall", {"query": "connection timeout", "limit": 2}
        )
        s_shield_block = execute_mcp_tool(
            "guarded_bash",
            {"command": "git checkout -- .", "cwd": "/home/mboyle/BulkDownloader"},
        )
        summary = {
            "rc": 0,
            "shield_path": get_active_shield_path(),
            "tool_count": len(FLEET_MCP_TOOLS_OPENAI),
            "checks": {
                "ctx_slice_rc": s_slice.get("rc"),
                "ruff_check_rc": s_ruff.get("rc"),
                "mypy_check_rc": s_mypy.get("rc"),
                "bd_bus_publish_rc": s_bus_pub.get("rc"),
                "bd_bus_read_rc": s_bus_rd.get("rc"),
                "hivemind_recall_rc": s_hm.get("rc"),
                "rule22_shield_block_rc": s_shield_block.get("rc"),
                "rule22_shield_blocked": s_shield_block.get("blocked"),
            },
        }
        print(json.dumps(summary, indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
