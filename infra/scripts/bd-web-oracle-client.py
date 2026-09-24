#!/usr/bin/env python3
"""
bd-web-oracle-client.py -- Unified Autonomous Virtual Browser Oracle Client.
Bridges consumer flat-rate subscriptions (Gemini Ultra, ChatGPT Plus, Claude Account A, Claude Account B)
into Boylenet terminal workflows and agent swarms via Chrome DevTools Protocol (CDP) on Windows VM 10.0.70.181:9222.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
import urllib.request
from typing import Any, Dict, List, Optional
from websocket import create_connection

KNOWN_NODES = {
    "181": "127.0.0.1",
    "137": "10.0.10.137",
    "bittorrent": "127.0.0.1",
    "battlestation": "10.0.10.137",
}


def get_tabs(host: str = "127.0.0.1") -> List[Dict[str, Any]]:
    """Fetch active page targets from CDP bridge on specified host."""
    bridge_url = f"http://{host}:9222/json/list"
    try:
        req = urllib.request.urlopen(bridge_url, timeout=4)
        targets = json.loads(req.read().decode())
        return [t for t in targets if t.get("type") == "page"]
    except Exception as e:
        print(f"[ORACLE] Error reaching CDP bridge at {bridge_url}: {e}", file=sys.stderr)
        return []


def cdp_eval_js(ws, expr: str, req_id: int = 1) -> Any:
    """Evaluate JavaScript expression via CDP Runtime.evaluate."""
    msg = {
        "id": req_id,
        "method": "Runtime.evaluate",
        "params": {"expression": expr, "returnByValue": True},
    }
    ws.send(json.dumps(msg))
    while True:
        raw = ws.recv()
        resp = json.loads(raw)
        if resp.get("id") == req_id:
            return resp.get("result", {}).get("result", {}).get("value")


def cdp_send(ws, method: str, params: Optional[Dict[str, Any]] = None, req_id: int = 1) -> Dict[str, Any]:
    """Execute arbitrary CDP method."""
    msg = {"id": req_id, "method": method, "params": params or {}}
    ws.send(json.dumps(msg))
    while True:
        raw = ws.recv()
        resp = json.loads(raw)
        if resp.get("id") == req_id:
            return resp.get("result", {})

OPERATOR_AUTH_PIN = "628895"


def handle_credential_and_pin_prompts(ws, pin: str = OPERATOR_AUTH_PIN, req_id: int = 90) -> bool:
    """Handle in-browser password manager / Google Password Manager PIN prompts automatically."""
    js_unlock = f"""(() => {{
        // 1. Check for PIN or security dialog inputs
        const pinInputs = Array.from(document.querySelectorAll('input[type="password"], input[type="tel"], input[type="text"], input[inputmode="numeric"]')).filter(el => {{
            const ph = (el.placeholder || '').toLowerCase();
            const al = (el.getAttribute('aria-label') || '').toLowerCase();
            const nm = (el.name || '').toLowerCase();
            const id = (el.id || '').toLowerCase();
            return ph.includes('pin') || al.includes('pin') || nm.includes('pin') || id.includes('pin');
        }});
        if (pinInputs.length > 0) {{
            const pinEl = pinInputs[0];
            pinEl.focus();
            pinEl.value = '{pin}';
            pinEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
            pinEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
            const submitBtn = document.querySelector('button[type="submit"], button[aria-label*="Next" i], button[aria-label*="Submit" i], button[aria-label*="Unlock" i], button[aria-label*="Verify" i]');
            if (submitBtn) {{ submitBtn.click(); }}
            return true;
        }}
        // 2. Check for native autofill trigger or password manager prompt
        const autofillBtns = Array.from(document.querySelectorAll('button, div[role="button"]')).filter(el => {{
            const text = (el.innerText || '').toLowerCase();
            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
            return text.includes('autofill') || aria.includes('autofill') || text.includes('use saved password') || aria.includes('use saved password');
        }});
        if (autofillBtns.length > 0) {{
            autofillBtns[0].click();
            return true;
        }}
        return false;
    }})()"""
    try:
        res = cdp_eval_js(ws, js_unlock, req_id)
        if res:
            time.sleep(1.0)
            return True
    except Exception:
        pass
    return False


def query_gemini(tab: Dict[str, Any], prompt: str, timeout: int = 120) -> str:
    """Query Google Gemini Ultra."""
    ws = create_connection(tab["webSocketDebuggerUrl"], timeout=10, suppress_origin=True)
    try:
        # Check login
        signed_in = cdp_eval_js(
            ws,
            "document.body.innerText.includes('Sign in') && !document.querySelector('.ql-editor, rich-textarea, textarea')",
            10,
        )
        if signed_in:
            if handle_credential_and_pin_prompts(ws):
                time.sleep(2.0)
            else:
                return "[GEMINI ERROR] Requires login on oracle host"

        # Focus editor
        cdp_eval_js(
            ws,
            """(() => {
                const ed = document.querySelector('rich-textarea div.ql-editor, .ql-editor, rich-textarea, textarea, [contenteditable="true"]');
                if (ed) { ed.focus(); return true; }
                return false;
            })()""",
            11,
        )
        time.sleep(0.2)
        cdp_send(ws, "Input.insertText", {"text": prompt}, 12)
        time.sleep(0.3)

        # Dispatch input event so UI recognizes typed text and enables send button
        cdp_eval_js(
            ws,
            """(() => {
                const ed = document.querySelector('rich-textarea div.ql-editor, .ql-editor, [contenteditable="true"]');
                if (ed) { ed.dispatchEvent(new Event('input', { bubbles: true })); }
            })()""",
            13,
        )
        time.sleep(0.3)

        initial_count = cdp_eval_js(ws, "document.querySelectorAll('message-content').length", 14) or 0

        # Click send or press Enter
        clicked = cdp_eval_js(
            ws,
            """(() => {
                const btn = document.querySelector('button[aria-label="Send message"], button[aria-label*="Send"], .send-button, button.send-button');
                if (btn) { btn.click(); return true; }
                return false;
            })()""",
            15,
        )
        if not clicked:
            # Fallback to Enter key
            cdp_send(ws, "Input.dispatchKeyEvent", {"type": "rawKeyDown", "windowsVirtualKeyCode": 13, "unmodifiedText": "\r", "text": "\r"}, 16)
            cdp_send(ws, "Input.dispatchKeyEvent", {"type": "keyUp", "windowsVirtualKeyCode": 13, "unmodifiedText": "\r", "text": "\r"}, 17)

        t0 = time.time()
        time.sleep(1.0)
        while time.time() - t0 < timeout:
            state = cdp_eval_js(
                ws,
                """(() => {
                    const stop = document.querySelector('mat-icon[fonticon="stop"], button[aria-label*="Stop"]');
                    const msgs = document.querySelectorAll('message-content');
                    let text = msgs.length > 0 ? msgs[msgs.length - 1].textContent.trim() : "";
                    return { isTyping: !!stop, count: msgs.length, text: text };
                })()""",
                15,
            )
            if state:
                if state.get("count", 0) > initial_count and not state.get("isTyping") and state.get("text"):
                    return state.get("text")
            time.sleep(0.5)
        return "[GEMINI TIMEOUT] Response timed out"
    finally:
        ws.close()


def query_chatgpt(tab: Dict[str, Any], prompt: str, timeout: int = 120) -> str:
    """Query ChatGPT Plus."""
    ws = create_connection(tab["webSocketDebuggerUrl"], timeout=10, suppress_origin=True)
    try:
        # Check login / credential prompt
        has_login = cdp_eval_js(
            ws,
            "document.querySelector('button[data-testid=\"login-button\"], a[href*=\"/login\"]') !== null",
            19,
        )
        if has_login:
            handle_credential_and_pin_prompts(ws)
            time.sleep(2.0)

        # Focus prompt area
        cdp_eval_js(
            ws,
            """(() => {
                const ed = document.querySelector('#prompt-textarea, [contenteditable="true"]');
                if (ed) { ed.focus(); return true; }
                return false;
            })()""",
            20,
        )
        time.sleep(0.2)
        cdp_send(ws, "Input.insertText", {"text": prompt}, 21)
        time.sleep(0.3)

        initial_count = cdp_eval_js(ws, "document.querySelectorAll('[data-message-author-role=\"assistant\"]').length", 22) or 0

        # Click send
        clicked = cdp_eval_js(
            ws,
            """(() => {
                const btn = document.querySelector('button[data-testid="send-button"], button[aria-label="Send prompt"], #composer-submit-button');
                if (btn && btn.getAttribute('data-testid') !== 'stop-button') { btn.click(); return true; }
                return false;
            })()""",
            23,
        )
        if not clicked:
            return "[CHATGPT ERROR] Could not click send button"

        t0 = time.time()
        time.sleep(1.0)
        last_text = ""
        stable_count = 0
        while time.time() - t0 < timeout:
            state = cdp_eval_js(
                ws,
                """(() => {
                    const stop = document.querySelector('button[data-testid="stop-button"], button[aria-label*="Stop"]');
                    const msgs = document.querySelectorAll('[data-message-author-role="assistant"]');
                    let text = msgs.length > 0 ? msgs[msgs.length - 1].textContent.trim() : "";
                    return { isGenerating: !!stop, count: msgs.length, text: text };
                })()""",
                24,
            )
            if state:
                text = state.get("text", "")
                count = state.get("count", 0)
                is_gen = state.get("isGenerating", False)
                if count > initial_count and text:
                    if not is_gen:
                        return text
                    # Text stabilization fallback
                    if text == last_text and len(text) > 0:
                        stable_count += 1
                        if stable_count >= 3:  # unchanged for ~1.5s
                            return text
                    else:
                        last_text = text
                        stable_count = 0
            time.sleep(0.5)
        return "[CHATGPT TIMEOUT] Response timed out"
    finally:
        ws.close()


def query_claude(tab: Dict[str, Any], prompt: str, timeout: int = 120, label: str = "CLAUDE") -> str:
    """Query Claude (Account A or B)."""
    ws = create_connection(tab["webSocketDebuggerUrl"], timeout=10, suppress_origin=True)
    try:
        # Check login / credential prompt
        has_login = cdp_eval_js(
            ws,
            "document.querySelector('button[data-testid=\"login-button\"], a[href*=\"/login\"], input[type=\"email\"]') !== null",
            29,
        )
        if has_login:
            handle_credential_and_pin_prompts(ws)
            time.sleep(2.0)

        # Focus input
        cdp_eval_js(
            ws,
            """(() => {
                const ed = document.querySelector('div.tiptap.ProseMirror, fieldset div[contenteditable="true"], div[contenteditable="true"]');
                if (ed) { ed.focus(); return true; }
                return false;
            })()""",
            30,
        )
        time.sleep(0.2)
        cdp_send(ws, "Input.insertText", {"text": prompt}, 31)
        time.sleep(0.3)

        initial_count = cdp_eval_js(ws, "document.querySelectorAll('.font-claude-response').length", 32) or 0

        # Click send
        clicked = cdp_eval_js(
            ws,
            """(() => {
                const btn = document.querySelector('button[aria-label="Send message"], button[aria-label="Send Message"]');
                if (btn) { btn.click(); return true; }
                return false;
            })()""",
            33,
        )
        if not clicked:
            return f"[{label} ERROR] Could not click send button"

        t0 = time.time()
        time.sleep(1.0)
        while time.time() - t0 < timeout:
            state = cdp_eval_js(
                ws,
                """(() => {
                    const stop = document.querySelector('button[aria-label*="Stop"]');
                    const msgs = document.querySelectorAll('.font-claude-response');
                    let text = msgs.length > 0 ? msgs[msgs.length - 1].textContent.trim() : "";
                    return { isStreaming: !!stop, count: msgs.length, text: text };
                })()""",
                34,
            )
            if state:
                if state.get("count", 0) > initial_count and not state.get("isStreaming") and state.get("text"):
                    return state.get("text")
            time.sleep(0.5)
        return f"[{label} TIMEOUT] Response timed out"
    finally:
        ws.close()


def resolve_targets(host: str = "127.0.0.1") -> Dict[str, Dict[str, Any]]:
    """Scan tabs and map to canonical oracle targets on specified host."""
    tabs = get_tabs(host)
    targets: Dict[str, Dict[str, Any]] = {}

    claude_tabs = []
    for t in tabs:
        url = t.get("url", "").lower()
        if "gemini.google.com" in url:
            targets["gemini"] = t
        elif "chatgpt.com" in url:
            targets["chatgpt"] = t
        elif "claude.ai" in url:
            claude_tabs.append(t)

    # Differentiate Claude tabs:
    for ct in claude_tabs:
        url = ct.get("url", "")
        # Claude A is attached to code/session or Matthew Boyle Max
        if "code/session" in url or "session_013" in url:
            targets["claude-a"] = ct
        elif "chat/" in url or "/new" in url or "/login" in url:
            if "claude-b" not in targets:
                targets["claude-b"] = ct
            elif "claude-a" not in targets:
                targets["claude-a"] = ct

    # Fallbacks if only 1 Claude tab or unmatched
    if len(claude_tabs) == 1 and "claude-a" not in targets and "claude-b" not in targets:
        targets["claude-a"] = claude_tabs[0]
    elif len(claude_tabs) >= 2:
        if "claude-a" not in targets:
            targets["claude-a"] = claude_tabs[0]
        if "claude-b" not in targets:
            targets["claude-b"] = claude_tabs[1]

    return targets


def main():
    parser = argparse.ArgumentParser(description="Unified Boylenet Virtual Browser Oracle Client")
    parser.add_argument("prompt", help="Prompt query to submit to the oracle")
    parser.add_argument(
        "--oracle",
        choices=["gemini", "chatgpt", "claude-a", "claude-b", "all"],
        default="gemini",
        help="Target oracle engine (default: gemini)",
    )
    parser.add_argument(
        "--node",
        choices=["181", "137", "auto", "bittorrent", "battlestation"],
        default="auto",
        help="Target host node (default: auto)",
    )
    parser.add_argument("--host", default=None, help="Explicit host IP/domain for CDP bridge")
    parser.add_argument("--timeout", type=int, default=120, help="Per-oracle response timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output results in structured JSON format")
    parser.add_argument("--consensus", action="store_true", help="Evaluate consensus matrix across oracle verdicts")
    parser.add_argument("--unanimous", action="store_true", help="Require unanimous agreement for consensus")

    args = parser.parse_args()

    # Determine host
    if args.host:
        target_host = args.host
    elif args.node in KNOWN_NODES:
        target_host = KNOWN_NODES[args.node]
    elif args.node == "auto":
        # Check node 181 first, fallback to 137 if unreachable
        t181 = get_tabs("127.0.0.1")
        if t181:
            target_host = "127.0.0.1"
        else:
            target_host = "10.0.10.137"
    else:
        target_host = "127.0.0.1"

    targets = resolve_targets(target_host)

    if not targets:
        print(f"[ORACLE FATAL] No matching browser tabs found on {target_host}:9222", file=sys.stderr)
        sys.exit(1)

    if args.oracle != "all":
        tab = targets.get(args.oracle)
        if not tab:
            available = list(targets.keys())
            print(f"[ORACLE ERROR] Target '{args.oracle}' not found. Available targets: {available}", file=sys.stderr)
            sys.exit(1)

        if args.oracle == "gemini":
            resp = query_gemini(tab, args.prompt, timeout=args.timeout)
        elif args.oracle == "chatgpt":
            resp = query_chatgpt(tab, args.prompt, timeout=args.timeout)
        elif args.oracle == "claude-a":
            resp = query_claude(tab, args.prompt, timeout=args.timeout, label="CLAUDE-A")
        elif args.oracle == "claude-b":
            resp = query_claude(tab, args.prompt, timeout=args.timeout, label="CLAUDE-B")
        else:
            resp = "Unknown target"

        if args.json:
            print(json.dumps({args.oracle: resp}, indent=2))
        else:
            print(resp)
        return

    # --oracle all: Concurrent multi-oracle fanout
    results: Dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {}
        if "gemini" in targets:
            futures[pool.submit(query_gemini, targets["gemini"], args.prompt, args.timeout)] = "gemini"
        if "chatgpt" in targets:
            futures[pool.submit(query_chatgpt, targets["chatgpt"], args.prompt, args.timeout)] = "chatgpt"
        if "claude-a" in targets:
            futures[pool.submit(query_claude, targets["claude-a"], args.prompt, args.timeout, "CLAUDE-A")] = "claude-a"
        if "claude-b" in targets:
            futures[pool.submit(query_claude, targets["claude-b"], args.prompt, args.timeout, "CLAUDE-B")] = "claude-b"

        for f in concurrent.futures.as_completed(futures):
            name = futures[f]
            try:
                results[name] = f.result()
            except Exception as e:
                results[name] = f"[ERROR: {e}]"

    consensus_data = None
    if args.consensus:
        try:
            sys.path.insert(0, "/home/mboyle/teamwork_projects/frontier_blueprint_integration/src")
            from smt_invariants.consensus import ConsensusMatrix
            from smt_invariants.models import ConsensusScore

            scores = []
            for name, val in results.items():
                cat = "INCONCLUSIVE"
                upper = val.strip().upper()
                if "PASS" in upper or "VALID" in upper or upper == "YES" or upper == "TRUE":
                    cat = "PASS"
                elif "REJECT" in upper or "INVALID" in upper or "FAIL" in upper or upper == "NO" or upper == "FALSE":
                    cat = "REJECT"
                scores.append(ConsensusScore(model=name, category=cat, notes=val[:100]))

            matrix = ConsensusMatrix(models=list(results.keys()))
            consensus_res = matrix.evaluate(scores, require_unanimous=args.unanimous)
            consensus_data = consensus_res.model_dump()
        except Exception as e:
            consensus_data = {"error": f"Failed to compute consensus: {e}"}

    if args.json:
        out = {"responses": results}
        if consensus_data:
            out["consensus"] = consensus_data
        print(json.dumps(out, indent=2))
    else:
        for oracle_name, text in results.items():
            print(f"=== {oracle_name.upper()} ===")
            print(text)
            print()
        if consensus_data:
            print("=== CONSENSUS MATRIX ===")
            print(f"Decision: {consensus_data.get('decision')}")
            print(f"Supermajority: {consensus_data.get('supermajority')} | Unanimous: {consensus_data.get('is_unanimous')}")
            print(f"Tallies: {consensus_data.get('tallies')}")
            print(f"Notes: {consensus_data.get('notes')}")


if __name__ == "__main__":
    main()
