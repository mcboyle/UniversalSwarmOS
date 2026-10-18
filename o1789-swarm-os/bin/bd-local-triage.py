#!/usr/bin/env python3
"""
bd-local-triage.py -- Local LLM Triage & Utility Runner for Boylenet Fleet
Routes high-frequency classification, commit generation, and log distillation to local Turing GPUs via LiteLLM (:4000) or direct Ollama backends at $0.00 marginal cost.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

LITELLM_URL = os.environ.get("LITELLM_URL", "http://127.0.0.1:4000/v1")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-fleet-local")
LOG_PATH = "/home/mboyle/bd-persist/state/LOCAL_LLM_INFERENCE.log"


def call_litellm(
    model: str, messages: list, max_tokens: int = 512, temperature: float = 0.1
) -> dict:
    url = f"{LITELLM_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": {"type": "json_object"}
        if "json" in messages[0]["content"].lower()
        else None,
    }
    # remove None keys
    payload = {k: v for k, v in payload.items() if v is not None}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LITELLM_KEY}",
    }

    t0 = time.perf_counter()
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.perf_counter() - t0
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            log_inference(
                model,
                elapsed,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                "SUCCESS",
            )
            return {"content": content, "elapsed_s": round(elapsed, 3), "usage": usage}
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        KeyError,
        json.JSONDecodeError,
        OSError,
    ) as e:
        elapsed = time.perf_counter() - t0
        log_inference(model, elapsed, 0, 0, f"ERROR: {e}")
        raise RuntimeError(f"LiteLLM call failed ({model}): {e}") from e


def log_inference(model: str, elapsed: float, p_tok: int, c_tok: int, status: str):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry = f"{ts}\t{model}\t{elapsed:.3f}s\tin:{p_tok}\tout:{c_tok}\t{status}\n"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(entry)
    except OSError:
        pass


def classify_text(text: str) -> dict:
    sys_prompt = (
        "You are the Boylenet Local Triage Agent. Analyze the incoming task or message and return a strict JSON object with fields:\n"
        "- domain: one of ['HARNESS', 'CORE_ENGINE', 'UI_COCKPIT', 'TYPES', 'LINT', 'DOCS', 'FLEET_OPS']\n"
        "- priority: one of ['P0_BLOCKER', 'P1_HIGH', 'P2_NORMAL', 'P3_LOW']\n"
        "- suggested_tier: one of ['tier-3-local' (for docs, lint, simple format), 'tier-2-single-turn' (for bounded unit test/fix), 'tier-1-opus' (for multi-file architecture, rebase train, PM)]\n"
        "- target_files: list of mentioned or inferred file paths\n"
        "- summary: 1-line terse summary (<=60 chars)\n"
        "Return ONLY the valid JSON object."
    )
    res = call_litellm(
        "trivial",
        [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": text[:4000]},
        ],
    )
    try:
        return json.loads(res["content"])
    except json.JSONDecodeError:
        return {
            "raw": res["content"],
            "domain": "UNKNOWN",
            "suggested_tier": "tier-2-single-turn",
        }


def distill_ci_log(log_text: str) -> str:
    sys_prompt = (
        "You are the Boylenet CI Log Distiller. Given a test run output or failure trace, extract the core failure into a strict 3-line format:\n"
        "LINE 1: FAILED <test_file>::<test_name>\n"
        "LINE 2: ERROR <ExceptionName>: <brief exception message>\n"
        "LINE 3: LOC <file_path>:<line_number>\n"
        "If there are no failures, output: PASS (all tests green).\n"
        "Output strictly the 3 lines, no other commentary."
    )
    res = call_litellm(
        "ci-summary",
        [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": log_text[-6000:]},
        ],
        max_tokens=150,
    )
    return res["content"].strip()


def commit_message(diff_text: str) -> str:
    sys_prompt = (
        "You are a Conventional Commits craftsman. Given a git diff stat or diff hunk, write a single-line Conventional Commit message.\n"
        "Format: <type>(<scope>): <terse imperative description <= 50 chars>\n"
        "Types: feat, fix, test, docs, refactor, chore, perf.\n"
        "Output strictly the commit subject line only."
    )
    res = call_litellm(
        "trivial",
        [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": diff_text[:3000]},
        ],
        max_tokens=60,
    )
    return res["content"].strip()


def main():
    parser = argparse.ArgumentParser(
        description="Boylenet Local LLM Triage & Utility Runner"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # classify
    p_classify = subparsers.add_parser(
        "classify", help="Classify task or inbox message"
    )
    p_classify.add_argument(
        "text", nargs="?", help="Text to classify (or pipe via stdin)"
    )

    # ci-digest
    p_ci = subparsers.add_parser(
        "ci-digest", help="Distill raw pytest/CI log to 3 lines"
    )
    p_ci.add_argument("file", nargs="?", help="Log file path (or pipe via stdin)")

    # commit-msg
    p_commit = subparsers.add_parser(
        "commit-msg", help="Generate Conventional Commit message from diff"
    )
    p_commit.add_argument("file", nargs="?", help="Diff file path (or pipe via stdin)")

    args = parser.parse_args()

    if args.command == "classify":
        content = args.text or sys.stdin.read()
        if not content.strip():
            print("Error: empty input text", file=sys.stderr)
            sys.exit(1)
        res = classify_text(content)
        print(json.dumps(res, indent=2))

    elif args.command == "ci-digest":
        if args.file and os.path.exists(args.file):
            with open(args.file, "r", errors="replace") as f:
                content = f.read()
        else:
            content = sys.stdin.read()
        if not content.strip():
            print("Error: empty input log", file=sys.stderr)
            sys.exit(1)
        print(distill_ci_log(content))

    elif args.command == "commit-msg":
        if args.file and os.path.exists(args.file):
            with open(args.file, "r", errors="replace") as f:
                content = f.read()
        else:
            content = sys.stdin.read()
        if not content.strip():
            print("Error: empty input diff", file=sys.stderr)
            sys.exit(1)
        print(commit_message(content))


if __name__ == "__main__":
    main()
