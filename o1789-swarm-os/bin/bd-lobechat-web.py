#!/usr/bin/env python3
"""
Boylenet LobeChat Next-Gen AI Workspace Server & Synchronizer (`bd-lobechat-web.py`, `:4095`)
Exposes:
  1. 87 `🟢 LOCAL` Vault Models + 8 `☁️ CLOUD` Burst Models (`🟢 LOCAL` vs `☁️ CLOUD` labels & filter)
  2. `:4079` 50-Toolkit OpenAPI Specs (`/openapi.json`, `/web-osint/openapi.json`, `/data-science/openapi.json`, `/devops-infra/openapi.json`, `/media-ai/openapi.json`)
  3. Live `BD KB` Instant Search (`/api/bdkb/search` + Auto-Grounding toggle)
  4. Live `🛡️ Airgap` Status Badge (`/api/airgap` -> `bd-airgap status`)
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import time
from typing import Any, Dict, List, Tuple
import urllib.error
import urllib.parse
import urllib.request

PORT = int(os.environ.get("PORT", "3210"))
PUBLIC_PORT = int(os.environ.get("PUBLIC_PORT", "4095"))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "sk-fleet-local")
OPENAI_PROXY_URL = os.environ.get("OPENAI_PROXY_URL", "http://10.0.70.164:4000/v1").rstrip("/")
GATEWAY_4079_URL = os.environ.get("GATEWAY_4079_URL", "http://10.0.70.164:4079").rstrip("/")
ACCESS_CODE = os.environ.get("ACCESS_CODE", "boylenet-admin")
MODELS_JSON_PATH = os.environ.get("LOBE_MODELS_JSON", "/app/lobe_models_86.json")

OPENAPI_SUITES = [
    {"name": "Master 50-Toolkit OpenAPI", "url": "http://10.0.70.164:4079/openapi.json"},
    {"name": "Web & OSINT Suite", "url": "http://10.0.70.164:4079/web-osint/openapi.json"},
    {"name": "Data Science & RAG Suite", "url": "http://10.0.70.164:4079/data-science/openapi.json"},
    {"name": "DevOps, Infra & VMware Suite", "url": "http://10.0.70.164:4079/devops-infra/openapi.json"},
    {"name": "Media, Vision & Audio Suite", "url": "http://10.0.70.164:4079/media-ai/openapi.json"},
]

CLOUD_BURST_MODELS: List[Dict[str, str]] = [
    {"id": "cloud/claude-opus-4-7", "name": "☁️ CLOUD • Anthropic Claude Opus 4.7 ($1,000 Cloud Burst)", "locality": "CLOUD"},
    {"id": "cloud/claude-sonnet-4-6", "name": "☁️ CLOUD • Anthropic Claude Sonnet 4.6 ($1,000 Cloud Burst)", "locality": "CLOUD"},
    {"id": "cloud/gpt-5.4-pro", "name": "☁️ CLOUD • OpenAI GPT-5.4 Pro ($1,000 Cloud Burst)", "locality": "CLOUD"},
    {"id": "cloud/gemini-3.1-pro", "name": "☁️ CLOUD • Google Gemini 3.1 Pro ($1,000 Cloud Burst)", "locality": "CLOUD"},
    {"id": "cloud/grok-4.20-max", "name": "☁️ CLOUD • xAI Grok 4.20 Max ($1,000 Cloud Burst)", "locality": "CLOUD"},
    {"id": "cloud/deepseek-v4-cloud", "name": "☁️ CLOUD • DeepSeek-V4 Cloud API ($1,000 Cloud Burst)", "locality": "CLOUD"},
    {"id": "cloud/kimi-k2.5-cloud", "name": "☁️ CLOUD • Moonshot Kimi-K2.5 Cloud ($1,000 Cloud Burst)", "locality": "CLOUD"},
    {"id": "cloud/qwen3-max-cloud", "name": "☁️ CLOUD • Alibaba Qwen3-Max Cloud ($1,000 Cloud Burst)", "locality": "CLOUD"},
]


def load_catalog_models() -> List[Dict[str, str]]:
    base_models: List[Dict[str, str]] = []
    for candidate in (MODELS_JSON_PATH, "/var/tmp/lobe_models_86.json"):
        if os.path.exists(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    raw_list = json.load(f)
                for item in raw_list:
                    mid = str(item.get("id", "")).strip()
                    mname = str(item.get("name", mid)).strip()
                    if not mid:
                        continue
                    is_cloud = mid.startswith("cloud/") or "☁️ CLOUD" in mname
                    if is_cloud:
                        if not mname.startswith("☁️ CLOUD"):
                            mname = f"☁️ CLOUD • {mname}"
                        loc = "CLOUD"
                    else:
                        if not mname.startswith("🟢 LOCAL"):
                            mname = f"🟢 LOCAL • {mname}"
                        loc = "LOCAL"
                    base_models.append({"id": mid, "name": mname, "locality": loc})
                break
            except Exception:
                pass

    if not base_models:
        base_models = [
            {"id": "auto-local", "name": "🟢 LOCAL • Auto-Router (Tier 1/2/3 Smart Dispatch)", "locality": "LOCAL"},
            {"id": "tier1-qwen3-coder-30b-a3b", "name": "🟢 LOCAL • Tier 1 Qwen3-Coder-30B-A3B (77.6 tok/s)", "locality": "LOCAL"},
            {"id": "tier1-cyberstrike-35b-q4km", "name": "🟢 LOCAL • Tier 1 CyberStrike-OffSec-35B (66.5 tok/s)", "locality": "LOCAL"},
            {"id": "tier1-qwythos-9b-bf16", "name": "🟢 LOCAL • Tier 1 Qwythos-9B-1M Mythos (1005.9 pp512)", "locality": "LOCAL"},
            {"id": "tier2-deepseek-r1-70b", "name": "🟢 LOCAL • Tier 2 DeepSeek-R1-Distill-Llama-70B <think>", "locality": "LOCAL"},
            {"id": "deepseek-v4-flash", "name": "🟢 LOCAL • Tier 3 DeepSeek-V4-Flash MoE <think>", "locality": "LOCAL"},
        ]

    seen = {m["id"] for m in base_models}
    for cm in CLOUD_BURST_MODELS:
        if cm["id"] not in seen:
            base_models.append(dict(cm))
            seen.add(cm["id"])
    return base_models


def extract_think(content: str, reasoning_field: str = "") -> Tuple[str, str]:
    reasoning = (reasoning_field or "").strip()
    text = content or ""
    for pat in (r"<think>(.*?)</think>", r"\[THINK\](.*?)\[/THINK\]"):
        m = re.search(pat, text, flags=re.DOTALL | re.IGNORECASE)
        if m:
            r_sub = m.group(1).strip()
            reasoning = (reasoning + "\n" + r_sub).strip() if reasoning else r_sub
            text = (text[: m.start()] + text[m.end() :]).strip()
            break
    return (reasoning, text)


def query_gateway_tool(tool_name: str, payload: Dict[str, Any], timeout: float = 6.0) -> Dict[str, Any]:
    req = urllib.request.Request(
        f"{GATEWAY_4079_URL}/api/tool/{tool_name}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


HTML_UI = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LobeChat • Boylenet AI Workspace (:4095)</title>
<style>
  :root {
    --bg: #07090e;
    --sidebar: #0d111a;
    --panel: #131926;
    --border: #222c40;
    --accent: #00e5ff;
    --accent2: #8b5cf6;
    --text: #f1f5f9;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column;
  }
  header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 18px; background: var(--sidebar); border-bottom: 1px solid var(--border); flex-wrap: wrap; gap: 8px;
  }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 15px; flex-wrap: wrap; }
  .logo {
    width: 30px; height: 30px; border-radius: 8px;
    background: linear-gradient(135deg, #00e5ff, #8b5cf6);
    display: flex; align-items: center; justify-content: center; color: #050811; font-weight: 900;
  }
  .badge {
    font-size: 11px; padding: 3px 9px; border-radius: 999px;
    background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35);
  }
  .badge.airgap {
    background: rgba(0, 229, 255, 0.14); color: #38bdf8; border: 1px solid rgba(0, 229, 255, 0.4);
  }
  .badge.tools {
    background: rgba(139, 92, 246, 0.16); color: #c4b5fd; border: 1px solid rgba(139, 92, 246, 0.4);
  }
  .layout { display: grid; grid-template-columns: 350px 1fr; flex: 1; overflow: hidden; }
  .side {
    background: var(--sidebar); border-right: 1px solid var(--border); padding: 14px;
    display: flex; flex-direction: column; gap: 12px; overflow-y: auto;
  }
  label { font-size: 11px; text-transform: uppercase; color: var(--muted); font-weight: 700; display: block; margin-bottom: 5px; }
  select, input, textarea {
    width: 100%; background: #090c14; color: var(--text); border: 1px solid var(--border);
    border-radius: 8px; padding: 8px 10px; font-size: 12.5px;
  }
  .pill-row { display: flex; gap: 6px; margin-bottom: 6px; }
  .pill {
    flex: 1; text-align: center; padding: 5px 8px; font-size: 11px; font-weight: 700;
    border-radius: 6px; border: 1px solid var(--border); background: var(--panel); cursor: pointer; color: var(--text);
  }
  .pill.active { border-color: var(--accent); background: rgba(0, 229, 255, 0.15); color: #00e5ff; }
  .agent-card {
    padding: 9px 11px; border-radius: 8px; border: 1px solid var(--border);
    background: var(--panel); cursor: pointer; font-size: 12px;
  }
  .agent-card.active { border-color: var(--accent); background: rgba(0, 229, 255, 0.1); }
  .kb-box {
    padding: 10px; border-radius: 8px; border: 1px solid var(--border); background: #090d16; font-size: 12px;
  }
  .kb-results { max-height: 150px; overflow-y: auto; margin-top: 6px; font-size: 11.5px; color: #cbd5e1; display: flex; flex-direction: column; gap: 6px; }
  .kb-hit { padding: 6px 8px; border-radius: 6px; background: var(--panel); border-left: 3px solid var(--accent); }
  .openapi-links { display: flex; flex-direction: column; gap: 4px; font-size: 11.5px; }
  .openapi-links a { color: #38bdf8; text-decoration: none; }
  .openapi-links a:hover { text-decoration: underline; }
  .chat-col { display: flex; flex-direction: column; padding: 16px; gap: 12px; overflow: hidden; }
  .messages {
    flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px;
    padding: 14px; background: #090d16; border: 1px solid var(--border); border-radius: 10px;
  }
  .msg { padding: 12px 15px; border-radius: 9px; line-height: 1.55; font-size: 13.5px; white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; }
  .msg.user { background: rgba(59, 130, 246, 0.16); border: 1px solid rgba(59, 130, 246, 0.35); align-self: flex-end; max-width: 85%; }
  .msg.assistant { background: var(--panel); border: 1px solid var(--border); align-self: stretch; }
  details.think {
    margin-bottom: 10px; padding: 8px 12px; border-radius: 7px;
    background: rgba(139, 92, 246, 0.14); border: 1px solid rgba(139, 92, 246, 0.35);
    color: #d8b4fe; font-size: 12px;
  }
  .bar { display: flex; gap: 10px; align-items: center; }
  .btn {
    background: linear-gradient(135deg, #00e5ff, #8b5cf6); color: #050811;
    border: none; border-radius: 8px; padding: 9px 18px; font-weight: 800; cursor: pointer; white-space: nowrap;
  }
</style>
</head>
<body>
<header>
  <div class="brand">
    <div class="logo">🤯</div>
    <span>LobeChat • Boylenet AI Workspace (:4095)</span>
    <span class="badge">🟢 LOCAL 87 + ☁️ CLOUD 8 Ready</span>
    <span id="airgapBadge" class="badge airgap">🛡️ Airgap: LOCAL-FIRST ($0.00) • WAN ACTIVE</span>
    <span class="badge tools">🛠️ :4079 50-Toolkit &amp; BD KB Connected</span>
  </div>
  <div style="font-size:12px;color:var(--muted);">
    <a href="http://10.0.70.164:4079/openapi.json" target="_blank" style="color:#38bdf8;text-decoration:none;margin-right:8px;">:4079 50-Toolkit OpenAPI ↗</a>
    <a href="http://10.0.70.164:4096" target="_blank" style="color:var(--accent);text-decoration:none;margin-right:8px;">OpenCode (:4096) ↗</a>
    <a href="http://10.0.70.164:4097" target="_blank" style="color:var(--accent);text-decoration:none;margin-right:8px;">OpenClaw (:4097) ↗</a>
    <a href="http://10.0.70.164:3002" target="_blank" style="color:var(--accent);text-decoration:none;margin-right:8px;">Jarvis (:3002) ↗</a>
    <a href="http://10.0.70.164:4098" target="_blank" style="color:var(--accent);text-decoration:none;">Multi-Harness (:4098) ↗</a>
  </div>
</header>
<div class="layout">
  <aside class="side">
    <div>
      <label>Model Catalog (🟢 LOCAL Vault vs ☁️ CLOUD Burst)</label>
      <div class="pill-row">
        <div class="pill active" onclick="filterModels('ALL', this)">All (__TOTAL_COUNT__)</div>
        <div class="pill" onclick="filterModels('LOCAL', this)">🟢 LOCAL (__LOCAL_COUNT__)</div>
        <div class="pill" onclick="filterModels('CLOUD', this)">☁️ CLOUD (__CLOUD_COUNT__)</div>
      </div>
      <select id="model"></select>
    </div>
    <div class="kb-box">
      <label>📚 BD KB Instant Search (:4079 + Qdrant bd_master_kb)</label>
      <div style="display:flex;gap:6px;">
        <input id="kbInput" type="text" placeholder="Search 27 nodes, vSAN, O1740, 86 models..." onkeydown="if(event.key==='Enter')searchKb()">
        <button class="btn" style="padding:6px 10px;font-size:11.5px;" onclick="searchKb()">Search</button>
      </div>
      <label style="display:flex;align-items:center;gap:6px;margin-top:7px;text-transform:none;font-weight:600;color:#34d399;cursor:pointer;">
        <input id="autoKb" type="checkbox" checked style="width:auto;"> Auto-Ground Chat with BD KB Chunks
      </label>
      <div id="kbResults" class="kb-results"></div>
    </div>
    <div class="kb-box">
      <label>🛠️ :4079 50-Toolkit OpenAPI Suites (14 MCPs • 128 Skills)</label>
      <div class="openapi-links">
        <a href="http://10.0.70.164:4079/openapi.json" target="_blank">🔗 Master 50-Toolkit OpenAPI (/openapi.json)</a>
        <a href="http://10.0.70.164:4079/web-osint/openapi.json" target="_blank">🌐 Web, Playwright &amp; OSINT (/web-osint/openapi.json)</a>
        <a href="http://10.0.70.164:4079/data-science/openapi.json" target="_blank">📊 Data Science, Qdrant &amp; BD KB (/data-science/openapi.json)</a>
        <a href="http://10.0.70.164:4079/devops-infra/openapi.json" target="_blank">🖧 DevOps, 27-Node SSH &amp; vSAN (/devops-infra/openapi.json)</a>
        <a href="http://10.0.70.164:4079/media-ai/openapi.json" target="_blank">🎨 FLUX Image, Whisper &amp; Voice (/media-ai/openapi.json)</a>
      </div>
    </div>
    <div>
      <label>LobeChat Agent Assistants</label>
      <div id="agents" style="display:flex;flex-direction:column;gap:6px;">
        <div class="agent-card active" onclick="setAgent(this, 'You are LobeChat Boylenet Principal Architect grounded by BD KB and 50 Toolkits on :4079.')">🧠 <strong>Boylenet Principal Architect</strong><br><span style="color:var(--muted);font-size:11px;">BD KB + DeepSeek &lt;think&gt; + Qwen3-Coder</span></div>
        <div class="agent-card" onclick="setAgent(this, 'You are Hermes Tool-Calling Agent connected to :4079 50-Toolkits and 14 Fleet MCP servers.')">⚡ <strong>Hermes 50-Toolkit Agent</strong><br><span style="color:var(--muted);font-size:11px;">:4079 OpenAPI, AST ctx_slice, ruff, mypy</span></div>
        <div class="agent-card" onclick="setAgent(this, 'You are CyberStrike OffSec & Security Review Lens (Leg B) with Airgap verification.')">🛡️ <strong>CyberStrike Security &amp; Airgap Lens</strong><br><span style="color:var(--muted);font-size:11px;">SSRF, Auth, vSAN &amp; Airgap Invariants</span></div>
      </div>
    </div>
    <div>
      <label>System Role Instruction</label>
      <textarea id="sysPrompt" rows="3">You are LobeChat Boylenet Principal Architect grounded by BD KB and 50 Toolkits on :4079.</textarea>
    </div>
  </aside>
  <main class="chat-col">
    <div id="messages" class="messages">
      <div class="msg assistant">Welcome to LobeChat on Boylenet (:4095). Synchronized with <strong>🟢 LOCAL (87 models)</strong> + <strong>☁️ CLOUD (8 burst models)</strong>, <strong>📚 BD KB Instant Search</strong>, <strong>🛠️ :4079 50-Toolkit OpenAPI Gateway</strong>, and <strong>🛡️ Airgap Telemetry</strong>.</div>
    </div>
    <div class="bar">
      <input id="input" type="text" value="Summarize the Boylenet 27-node cluster, esxi01 vSAN T0/T1 disk groups, and O1740 routing in 3 bullets." onkeydown="if(event.key==='Enter')sendMsg()">
      <button class="btn" onclick="sendMsg()">Send ▶</button>
    </div>
  </main>
</div>
<script>
const MODELS = __MODELS_JSON__;
const sel = document.getElementById('model');
function filterModels(mode, el) {
  if (el) {
    document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
    el.classList.add('active');
  }
  const prev = sel.value;
  sel.innerHTML = '';
  MODELS.filter(m => mode === 'ALL' || m.locality === mode).forEach(m => {
    const o = document.createElement('option');
    o.value = m.id;
    o.textContent = `${m.name} (${m.id})`;
    sel.appendChild(o);
  });
  if ([...sel.options].some(o => o.value === prev)) sel.value = prev;
}
filterModels('ALL');

function setAgent(el, sys) {
  document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('sysPrompt').value = sys;
}

async function searchKb() {
  const q = document.getElementById('kbInput').value.trim();
  const box = document.getElementById('kbResults');
  box.innerHTML = 'Searching BD KB...';
  try {
    const r = await fetch('/api/bdkb/search?q=' + encodeURIComponent(q || 'Boylenet 27-node cluster'));
    const d = await r.json();
    const hits = d.results || [];
    if (!hits.length) {
      box.innerHTML = '<div>No chunks matched.</div>';
      return;
    }
    box.innerHTML = hits.map(h => `<div class="kb-hit"><strong>${h.section_title}</strong> <span style="color:#38bdf8;">(${h.kb_id}, score=${h.score})</span><br>${(h.content || '').slice(0, 220)}...</div>`).join('');
  } catch (e) {
    box.innerHTML = 'Error: ' + e;
  }
}

async function refreshAirgap() {
  try {
    const r = await fetch('/api/airgap');
    const d = await r.json();
    const el = document.getElementById('airgapBadge');
    if (d && d.ok !== false) {
      const mode = d.airgap_mode || d.mode || 'LOCAL-FIRST ($0.00) • WAN ACTIVE';
      el.textContent = '🛡️ Airgap: ' + mode;
    }
  } catch (e) {}
}
refreshAirgap();

async function sendMsg() {
  const inp = document.getElementById('input');
  const text = inp.value.trim();
  if (!text) return;
  inp.value = '';
  const box = document.getElementById('messages');
  const u = document.createElement('div');
  u.className = 'msg user';
  u.textContent = text;
  box.appendChild(u);

  const a = document.createElement('div');
  a.className = 'msg assistant';
  a.textContent = 'Thinking via ' + sel.value + '...';
  box.appendChild(a);
  box.scrollTop = box.scrollHeight;

  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        model: sel.value,
        system: document.getElementById('sysPrompt').value,
        prompt: text,
        use_bdkb: document.getElementById('autoKb').checked
      })
    });
    const d = await r.json();
    a.innerHTML = '';
    if (d.bdkb_citations && d.bdkb_citations.length) {
      const kbDiv = document.createElement('div');
      kbDiv.style.cssText = 'font-size:11.5px;color:#38bdf8;margin-bottom:8px;';
      kbDiv.textContent = '📚 BD KB Grounded: ' + d.bdkb_citations.join(' • ');
      a.appendChild(kbDiv);
    }
    if (d.reasoning) {
      const det = document.createElement('details');
      det.className = 'think';
      det.open = true;
      det.innerHTML = `<summary><strong>🧠 DeepSeek &lt;think&gt; Reasoning</strong></summary><div style="margin-top:6px;"></div>`;
      det.children[1].textContent = d.reasoning;
      a.appendChild(det);
    }
    const body = document.createElement('div');
    body.textContent = d.content || d.error || JSON.stringify(d);
    a.appendChild(body);
  } catch (e) {
    a.textContent = 'Error: ' + e;
  }
  box.scrollTop = box.scrollHeight;
}
</script>
</body>
</html>
"""


class LobeHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _send_json(self, obj: Dict[str, Any], code: int = 200) -> None:
        b = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        models = load_catalog_models()
        local_cnt = sum(1 for m in models if m.get("locality") == "LOCAL")
        cloud_cnt = sum(1 for m in models if m.get("locality") == "CLOUD")

        if parsed.path in ("/api/health", "/health"):
            self._send_json(
                {
                    "status": "ok",
                    "service": "lobechat",
                    "port": PORT,
                    "public_port": PUBLIC_PORT,
                    "openai_proxy_url": OPENAI_PROXY_URL,
                    "gateway_4079_url": GATEWAY_4079_URL,
                    "openapi_suites": OPENAPI_SUITES,
                    "toolkits_count": 50,
                    "bd_kb_enabled": True,
                    "airgap_badge": "🛡️ Airgap: LOCAL-FIRST ($0.00) • WAN ACTIVE",
                    "models": len(models),
                    "local_models_count": local_cnt,
                    "cloud_models_count": cloud_cnt,
                }
            )
            return

        if parsed.path == "/api/models":
            self._send_json(
                {
                    "data": models,
                    "local_count": local_cnt,
                    "cloud_count": cloud_cnt,
                }
            )
            return

        if parsed.path == "/api/toolkits":
            self._send_json(
                {
                    "ok": True,
                    "gateway_url": GATEWAY_4079_URL,
                    "toolkits_count": 50,
                    "openapi_suites": OPENAPI_SUITES,
                }
            )
            return

        if parsed.path == "/api/airgap":
            res = query_gateway_tool("airgap_and_cluster_status", {"action": "status"})
            res.setdefault("airgap_mode", "LOCAL-FIRST ($0.00) • WAN ACTIVE")
            self._send_json(res)
            return

        if parsed.path == "/api/bdkb/search":
            qs = urllib.parse.parse_qs(parsed.query)
            q = (qs.get("q") or qs.get("query") or ["Boylenet 27-node cluster"])[0]
            res = query_gateway_tool("bd_kb_search", {"query": q, "top_k": 4})
            self._send_json(res)
            return

        html_str = (
            HTML_UI.replace("__MODELS_JSON__", json.dumps(models))
            .replace("__PROXY_URL__", OPENAI_PROXY_URL)
            .replace("__ACCESS_CODE__", ACCESS_CODE)
            .replace("__TOTAL_COUNT__", str(len(models)))
            .replace("__LOCAL_COUNT__", str(local_cnt))
            .replace("__CLOUD_COUNT__", str(cloud_cnt))
        )
        b = html_str.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        if self.path == "/api/bdkb/search":
            q = str(data.get("query") or data.get("q") or "Boylenet")
            res = query_gateway_tool("bd_kb_search", {"query": q, "top_k": int(data.get("top_k", 4))})
            self._send_json(res)
            return

        if self.path == "/api/chat":
            model = str(data.get("model", "auto-local"))
            sys_prompt = str(data.get("system", "You are a Boylenet AI assistant."))
            prompt = str(data.get("prompt", "Hello"))
            use_bdkb = bool(data.get("use_bdkb", True))
            citations: List[str] = []
            if use_bdkb:
                kb_res = query_gateway_tool("bd_kb_search", {"query": prompt, "top_k": 2}, timeout=4.0)
                hits = kb_res.get("results") or []
                if hits:
                    ctx_blocks = []
                    for h in hits[:2]:
                        citations.append(f"{h.get('kb_id')}:{h.get('section_title')}")
                        ctx_blocks.append(f"[{h.get('section_title')}]\n{(h.get('content') or '')[:900]}")
                    sys_prompt = sys_prompt + "\n\n[BD KB Authoritative Context]:\n" + "\n---\n".join(ctx_blocks)

            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 1024,
            }
            req = urllib.request.Request(
                f"{OPENAI_PROXY_URL}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                },
                method="POST",
            )
            t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=180.0) as resp:
                    rj = json.loads(resp.read().decode("utf-8"))
                msg = (rj.get("choices") or [{}])[0].get("message") or {}
                reasoning, clean_text = extract_think(
                    str(msg.get("content") or ""), str(msg.get("reasoning_content") or "")
                )
                self._send_json(
                    {
                        "rc": 0,
                        "model": rj.get("model", model),
                        "elapsed_s": round(time.time() - t0, 2),
                        "reasoning": reasoning,
                        "content": clean_text,
                        "bdkb_citations": citations,
                    }
                )
            except Exception as exc:
                self._send_json({"rc": 1, "error": str(exc), "bdkb_citations": citations}, 502)
            return
        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Boylenet LobeChat (:4095) Server & Inspector")
    parser.add_argument("--status", action="store_true", help="Check live :4095 status")
    args = parser.parse_args()
    if args.status:
        with urllib.request.urlopen(f"http://127.0.0.1:{PUBLIC_PORT}/api/health", timeout=5) as r:
            print(r.read().decode("utf-8"))
        raise SystemExit(0)

    srv = ThreadingHTTPServer(("0.0.0.0", PORT), LobeHandler)
    print(f"LobeChat Studio listening on 0.0.0.0:{PORT} -> {OPENAI_PROXY_URL}", flush=True)
    srv.serve_forever()
