#!/usr/bin/env python3
"""bd_satellite_distill.py: Reflex Distillation Helper for Inter-Agent Messages (Milestone 4 / Pillar 10).

Distills inter-agent prose into dense Caveman JSON (< 25 tokens) via satellite LLMs
(ai-ollama01:11434 or LiteLLM gateway) with strict grammar-clamped logit sampling,
a 3.0-second circuit breaker, and an immediate emergency regex bypass.

Schema:
    {"from": "<sender>", "status": "<PASS|FAIL|IN_PROGRESS|BLOCKED>", "summary": "<summary>", "path": "<path>", "action": "<action>"}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_OLLAMA_URL = os.environ.get(
    "BD_DISTILL_ENDPOINT", "http://10.0.70.228:11434/api/chat"
)
DEFAULT_LITELLM_URL = os.environ.get(
    "LITELLM_GATEWAY_URL", "http://127.0.0.1:4000/v1/chat/completions"
)
DEFAULT_LITELLM_KEY = os.environ.get(
    "LITELLM_MASTER_KEY", os.environ.get("LITELLM_API_KEY", "sk-fleet-local")
)
DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_TIMEOUT_SECONDS = 3.0

EMERGENCY_PATTERN = re.compile(
    r"^(STOP|LIMIT|OPERATOR|WAKE|EMERGENCY|FABLE|HIGH|BLOCKED|REFUSED)",
    re.IGNORECASE,
)

CAVEMAN_DISTILL_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "from": {
            "type": "string",
            "description": "Sender seat identifier or role",
        },
        "status": {
            "type": "string",
            "enum": ["PASS", "FAIL", "IN_PROGRESS", "BLOCKED"],
            "description": "Discrete status enum",
        },
        "summary": {
            "type": "string",
            "description": "Concise summary under 8 words",
        },
        "path": {
            "type": "string",
            "description": "Target file or artifact path or empty string",
        },
        "action": {
            "type": "string",
            "description": "Next actionable directive under 5 words",
        },
    },
    "required": ["from", "status", "summary", "path", "action"],
    "additionalProperties": False,
}

LITELLM_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "caveman_distill_response",
        "strict": True,
        "schema": CAVEMAN_DISTILL_JSON_SCHEMA,
    },
}

SYSTEM_PROMPT = (
    "You are a reflex message distillation engine for UniversalSwarmOS.\n"
    "Compress the given inter-agent message into a single JSON object strictly matching this schema:\n"
    '{"from":"<sender_id>","status":"PASS|FAIL|IN_PROGRESS|BLOCKED","summary":"<summary under 6 words>","path":"<file path or empty>","action":"<next action under 4 words>"}\n'
    "Rules:\n"
    "- Total output must be under 20 tokens.\n"
    "- Output ONLY the raw JSON object. No markdown, no code fences, no explanations.\n"
    "- If sender is known, put it in 'from'; otherwise 'unknown'.\n"
    "- If a file path is mentioned in the text, extract it into 'path'; otherwise empty string \"\".\n"
)

REQUIRED_KEYS = ("from", "status", "summary", "path", "action")


def is_emergency_message(text: str) -> bool:
    """Detect if message requires immediate uncompressed delivery."""
    stripped = text.strip()
    return bool(EMERGENCY_PATTERN.match(stripped))


def is_already_caveman_json(text: str) -> str | None:
    """Check if the text is already a valid Caveman JSON string."""
    clean = text.strip()
    if clean.startswith("{") and clean.endswith("}"):
        try:
            data = json.loads(clean)
            if isinstance(data, dict) and all(k in data for k in REQUIRED_KEYS):
                return json.dumps(data, separators=(",", ":"))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            pass
    return None


def extract_json_payload(
    raw_content: str, default_from: str = "unknown"
) -> dict[str, Any] | None:
    """Extract and validate the JSON object from LLM response text with zero-retry single pass."""
    clean = raw_content.strip()

    # Strip any think tags if present
    if "<think>" in clean and "</think>" in clean:
        clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()

    # Strip markdown code blocks if present
    if clean.startswith("```"):
        lines = clean.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            clean = "\n".join(lines[1:])
        if clean.endswith("```"):
            clean = clean[:-3].strip()

    # Instant single-pass JSON validation
    obj: Any = None
    try:
        candidate = json.loads(clean)
        if isinstance(candidate, dict):
            obj = candidate
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        pass

    # Boundary search fallback if preamble or trailing characters exist
    if obj is None:
        start = clean.find("{")
        end = clean.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        json_str = clean[start : end + 1]
        try:
            candidate = json.loads(json_str)
            if isinstance(candidate, dict):
                obj = candidate
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return None

    if not isinstance(obj, dict):
        return None

    # Validate and normalize schema fields
    sender = str(obj.get("from") or default_from or "unknown").strip()
    status = str(obj.get("status") or "IN_PROGRESS").strip().upper()
    if status not in ("PASS", "FAIL", "IN_PROGRESS", "BLOCKED"):
        # Map common synonyms
        if status in ("OK", "DONE", "SUCCESS", "COMPLETED", "LANDED"):
            status = "PASS"
        elif status in ("ERROR", "ERR", "FAILED", "BROKEN"):
            status = "FAIL"
        elif status in ("HOLD", "HALT", "REJECTED"):
            status = "BLOCKED"
        else:
            status = "IN_PROGRESS"

    summary = str(obj.get("summary") or "").strip()
    # Truncate summary if excessively long (> 8 words)
    summary_words = summary.split()
    if len(summary_words) > 8:
        summary = " ".join(summary_words[:8])

    path = str(obj.get("path") or "").strip()
    action = str(obj.get("action") or "").strip()
    # Truncate action if excessively long (> 5 words)
    action_words = action.split()
    if len(action_words) > 5:
        action = " ".join(action_words[:5])

    return {
        "from": sender,
        "status": status,
        "summary": summary,
        "path": path,
        "action": action,
    }


def call_ollama(
    endpoint: str,
    model: str,
    sender: str,
    text: str,
    timeout: float,
) -> dict[str, Any] | None:
    """Invoke native Ollama /api/chat with strict grammar schema binding."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Sender: {sender}\nMessage: {text}"},
        ],
        "stream": False,
        "format": CAVEMAN_DISTILL_JSON_SCHEMA,
        "options": {
            "temperature": 0.0,
            "num_predict": 45,
        },
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "bd-satellite-distill/1.0",
    }
    req = urllib.request.Request(endpoint, data=body_bytes, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        content = data.get("message", {}).get("content", "")
        return extract_json_payload(content, default_from=sender)


def call_litellm(
    endpoint: str,
    model: str,
    api_key: str,
    sender: str,
    text: str,
    timeout: float,
) -> dict[str, Any] | None:
    """Invoke LiteLLM gateway /v1/chat/completions with strict response_format grammar clamping."""
    payload = {
        "model": model.replace(":", "-"),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Sender: {sender}\nMessage: {text}"},
        ],
        "response_format": LITELLM_RESPONSE_FORMAT,
        "max_tokens": 45,
        "temperature": 0.0,
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "bd-satellite-distill/1.0",
    }
    req = urllib.request.Request(endpoint, data=body_bytes, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            return extract_json_payload(content, default_from=sender)
    return None


def distill_message(
    sender: str,
    text: str,
    endpoint: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_MODEL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    gateway_url: str = DEFAULT_LITELLM_URL,
    api_key: str = DEFAULT_LITELLM_KEY,
) -> tuple[str, bool]:
    """Distill inter-agent text into dense Caveman JSON with 3.0s circuit breaker.

    Returns:
        (result_text, was_distilled)
    """
    clean_text = text.strip()
    if not clean_text:
        return text, False

    # 1. Emergency regex bypass: immediately return raw text
    if is_emergency_message(clean_text):
        return text, False

    # 2. Check if already valid Caveman JSON
    already_json = is_already_caveman_json(clean_text)
    if already_json is not None:
        return already_json, True

    # 3. Circuit breaker timeout allocation
    # Use max socket timeout of (timeout - 0.2s) to prevent hanging
    t0 = time.perf_counter()
    socket_timeout = max(0.5, timeout - 0.2)

    extracted: dict[str, Any] | None = None
    # Attempt primary Ollama endpoint
    try:
        extracted = call_ollama(
            endpoint=endpoint,
            model=model,
            sender=sender,
            text=clean_text,
            timeout=socket_timeout,
        )
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ):
        extracted = None

    if extracted:
        compact_json = json.dumps(extracted, separators=(",", ":"))
        return compact_json, True

    # Fallback to LiteLLM if sufficient circuit breaker budget remains
    elapsed = time.perf_counter() - t0
    remaining = timeout - elapsed
    if remaining > 0.8:
        try:
            extracted = call_litellm(
                endpoint=gateway_url,
                model=model,
                api_key=api_key,
                sender=sender,
                text=clean_text,
                timeout=remaining - 0.1,
            )
            if extracted:
                compact_json = json.dumps(extracted, separators=(",", ":"))
                return compact_json, True
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError,
            json.JSONDecodeError,
        ):
            return text, False

    # Circuit breaker engaged or parse failed: fallback to raw original message
    return text, False


def main() -> int:
    parser = argparse.ArgumentParser(description="Satellite Reflex Distillation Helper")
    parser.add_argument(
        "--from",
        dest="sender",
        type=str,
        default="unknown",
        help="Sender seat identifier",
    )
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Message text to distill (or '-' for stdin)",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=DEFAULT_OLLAMA_URL,
        help=f"Ollama endpoint (default: {DEFAULT_OLLAMA_URL})",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Circuit breaker timeout (default: {DEFAULT_TIMEOUT_SECONDS}s)",
    )
    parser.add_argument(
        "positional_args", nargs="*", help="Optional positional [from] [text]"
    )

    args = parser.parse_args()

    sender = args.sender
    text = args.text

    # Handle positional arguments if provided
    if not text and args.positional_args:
        if len(args.positional_args) == 1:
            text = args.positional_args[0]
        elif len(args.positional_args) >= 2:
            sender = args.positional_args[0]
            text = " ".join(args.positional_args[1:])

    # Read from stdin if text is '-' or omitted
    if text is None or text == "-":
        if not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            text = ""

    if not text:
        sys.stdout.write("\n")
        return 0

    result, _ = distill_message(
        sender=sender,
        text=text,
        endpoint=args.endpoint,
        model=args.model,
        timeout=args.timeout,
    )

    sys.stdout.write(result + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
