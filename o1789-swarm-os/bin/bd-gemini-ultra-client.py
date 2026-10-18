#!/usr/bin/env python3
"""
bd-gemini-ultra-client.py -- Autonomous driver for Gemini Ultra web UI via Chrome DevTools Protocol.
Bridges consumer Gemini Ultra into Boylenet terminal workflows via Windows VM 10.0.70.181:9222.
"""
import sys
import json
import time
import urllib.request
from websocket import create_connection

BRIDGE_URL = "http://127.0.0.1:9222/json/list"

def get_gemini_tab():
    try:
        req = urllib.request.urlopen(BRIDGE_URL, timeout=3)
        tabs = json.loads(req.read().decode())
        for t in tabs:
            if t.get("type") == "page" and "gemini.google.com" in t.get("url", ""):
                return t
        for t in tabs:
            if t.get("type") == "page":
                return t
    except Exception as e:
        print(f"Error fetching tabs from bridge: {e}", file=sys.stderr)
    return None

def query_gemini_ultra(prompt: str, timeout: int = 120) -> str:
    tab = get_gemini_tab()
    if not tab:
        raise RuntimeError("No active Gemini tab found on 10.0.70.181:9222")

    ws_url = tab.get("webSocketDebuggerUrl")
    ws = create_connection(ws_url, timeout=10, suppress_origin=True)

    _seq = 0

    def send_cdp(method, params=None):
        nonlocal _seq
        _seq += 1
        cid = _seq
        msg = {"id": cid, "method": method, "params": params or {}}
        ws.send(json.dumps(msg))
        while True:
            raw = ws.recv()
            resp = json.loads(raw)
            if resp.get("id") == cid:
                return resp.get("result", {})

    def eval_js(expr):
        res = send_cdp("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        return res.get("result", {}).get("value")

    # Check if signed in
    sign_in = eval_js("document.body.innerText.includes('Sign in') && !document.querySelector('textarea, rich-textarea, .ql-editor')")
    if sign_in:
        ws.close()
        raise RuntimeError("Gemini Ultra requires sign-in on 10.0.70.181. Please log in once via RDP (10.0.70.181:3389).")

    # Inject prompt using native CDP Input
    focus_js = """
    (() => {
        const editor = document.querySelector('.ql-editor, rich-textarea, textarea, [contenteditable="true"]');
        if (!editor) return false;
        editor.focus();
        return true;
    })()
    """
    eval_js(focus_js)
    time.sleep(0.3)

    # Native CDP text insertion
    send_cdp("Input.insertText", {"text": prompt})
    time.sleep(0.5)

    # Record baseline message count before sending
    initial_count = eval_js("document.querySelectorAll('message-content').length") or 0

    # Click Send message button
    click_js = """
    (() => {
        const btn = document.querySelector('button[aria-label="Send message"], button[aria-label*="Send"], .send-button');
        if (btn) {
            btn.click();
            return true;
        }
        return false;
    })()
    """
    success = eval_js(click_js)
    if not success:
        ws.close()
        raise RuntimeError("Could not click Send message button on Gemini page.")

    # Wait for response completion
    t0 = time.time()
    time.sleep(1.0)  # brief pause for generation to commence
    while time.time() - t0 < timeout:
        check_js = """
        (() => {
            const stopBtn = document.querySelector('mat-icon[fonticon="stop"], button[aria-label*="Stop"]');
            const msgs = document.querySelectorAll('message-content');
            let text = "";
            if (msgs.length > 0) {
                text = msgs[msgs.length - 1].textContent.trim();
            }
            return { isTyping: !!stopBtn, count: msgs.length, text: text };
        })()
        """
        state = eval_js(check_js)
        if state:
            count = state.get("count", 0)
            is_typing = state.get("isTyping", False)
            text = state.get("text", "")
            if count > initial_count and not is_typing and len(text) > 0:
                ws.close()
                return text
        time.sleep(0.5)

    ws.close()
    return "Timeout waiting for Gemini response."

def main():
    if len(sys.argv) < 2:
        print("Usage: bd-gemini-ultra-client.py '<prompt>'", file=sys.stderr)
        sys.exit(1)
    prompt = sys.argv[1]
    try:
        ans = query_gemini_ultra(prompt)
        print(ans)
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
