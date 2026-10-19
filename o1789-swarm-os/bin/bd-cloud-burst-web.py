from __future__ import annotations
import importlib.machinery
import importlib.util
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

PORT = int(os.environ.get("BD_CLOUD_BURST_PORT", "4090"))
CLI_PATH = "/home/mboyle/bin/bd-cloud-burst"
loader = importlib.machinery.SourceFileLoader("bd_cloud_burst", CLI_PATH)
spec = importlib.util.spec_from_loader("bd_cloud_burst", loader)
assert spec is not None and spec.loader is not None
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Boylenet Hybrid Cloud + Local Burst Orchestrator (:4090)</title>
<style>
  :root {
    --bg: #050811;
    --panel: rgba(13, 21, 38, 0.86);
    --panel-alt: rgba(19, 30, 54, 0.78);
    --border: rgba(56, 189, 248, 0.25);
    --accent: #38bdf8;
    --accent2: #a855f7;
    --emerald: #10b981;
    --amber: #f59e0b;
    --danger: #ef4444;
    --text: #f1f5f9;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: radial-gradient(circle at 15% 10%, #0f172a 0%, #050811 65%, #020409 100%);
    color: var(--text);
    min-height: 100vh;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 24px;
    background: rgba(8, 13, 26, 0.92);
    border-bottom: 1px solid var(--border);
    backdrop-filter: blur(14px);
    position: sticky;
    top: 0;
    z-index: 20;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .brand-badge {
    background: linear-gradient(135deg, #38bdf8, #818cf8, #c084fc);
    color: #030712;
    font-weight: 800;
    padding: 6px 11px;
    border-radius: 8px;
    font-size: 13px;
    letter-spacing: 0.6px;
  }
  .brand h1 {
    margin: 0;
    font-size: 17px;
    font-weight: 700;
  }
  .brand-sub {
    font-size: 12px;
    color: var(--muted);
  }
  .nav-links {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }
  .nav-links a {
    color: var(--accent);
    text-decoration: none;
    font-size: 12px;
    padding: 6px 10px;
    border-radius: 7px;
    border: 1px solid rgba(56, 189, 248, 0.25);
    background: rgba(15, 23, 42, 0.7);
  }
  .nav-links a:hover {
    border-color: var(--accent);
    background: rgba(56, 189, 248, 0.14);
  }
  .layout {
    display: grid;
    grid-template-columns: 360px 1fr;
    gap: 18px;
    padding: 18px 24px;
    max-width: 1760px;
    margin: 0 auto;
  }
  .card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 15px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
    margin-bottom: 14px;
  }
  .card-title {
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    color: var(--accent);
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }
  label {
    display: block;
    font-size: 11px;
    color: var(--muted);
    margin: 8px 0 4px;
    font-weight: 600;
  }
  select, input, textarea {
    width: 100%;
    background: rgba(7, 12, 24, 0.9);
    color: var(--text);
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 12px;
    font-family: inherit;
  }
  textarea {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    min-height: 76px;
    resize: vertical;
  }
  .btn-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 10px;
  }
  button {
    cursor: pointer;
    border: none;
    border-radius: 8px;
    padding: 8px 13px;
    font-size: 12px;
    font-weight: 700;
    transition: all 0.16s ease;
  }
  .btn-primary {
    background: linear-gradient(135deg, #38bdf8, #6366f1);
    color: #020617;
  }
  .btn-purple {
    background: linear-gradient(135deg, #a855f7, #ec4899);
    color: #ffffff;
  }
  .btn-emerald {
    background: linear-gradient(135deg, #10b981, #059669);
    color: #022c22;
  }
  .btn-ghost {
    background: rgba(30, 41, 59, 0.85);
    color: var(--text);
    border: 1px solid rgba(148, 163, 184, 0.25);
  }
  button:hover {
    transform: translateY(-1px);
    filter: brightness(1.08);
  }
  .pool-pill {
    display: flex;
    justify-content: space-between;
    padding: 6px 9px;
    border-radius: 7px;
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid rgba(148, 163, 184, 0.16);
    margin-bottom: 5px;
    font-size: 11.5px;
  }
  .tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 14px;
    flex-wrap: wrap;
  }
  .tab {
    padding: 9px 15px;
    border-radius: 9px;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(56, 189, 248, 0.22);
    color: var(--muted);
    font-weight: 700;
    font-size: 12.5px;
    cursor: pointer;
  }
  .tab.active {
    background: linear-gradient(135deg, rgba(56, 189, 248, 0.22), rgba(168, 85, 247, 0.22));
    color: var(--text);
    border-color: var(--accent);
  }
  .grid-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    gap: 12px;
  }
  .lane-card {
    background: var(--panel-alt);
    border: 1px solid rgba(56, 189, 248, 0.25);
    border-radius: 10px;
    padding: 12px;
  }
  .lane-hdr {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
    font-weight: 700;
    margin-bottom: 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
  }
  pre {
    background: rgba(3, 6, 14, 0.92);
    border: 1px solid rgba(56, 189, 248, 0.18);
    border-radius: 8px;
    padding: 10px;
    font-size: 11.5px;
    line-height: 1.45;
    overflow-x: auto;
    white-space: pre-wrap;
    color: #e2e8f0;
    margin: 0;
    max-height: 360px;
  }
  .chip {
    display: inline-block;
    padding: 2px 7px;
    border-radius: 999px;
    font-size: 10.5px;
    font-weight: 700;
    background: rgba(56, 189, 248, 0.16);
    color: var(--accent);
    border: 1px solid rgba(56, 189, 248, 0.3);
  }
  .chip.ok {
    background: rgba(16, 185, 129, 0.18);
    color: #34d399;
    border-color: rgba(16, 185, 129, 0.35);
  }
</style>
</head>
<body>
<header>
  <div class="brand">
    <span class="brand-badge">CLOUD + LOCAL BURST :4090</span>
    <div>
      <h1>Boylenet Hybrid Cloud + Local Burst Orchestrator</h1>
      <div class="brand-sub">Claude ABCD Cloud (`claude-opus-5-5` / `claude-sonnet-5-5` / `fable-5-1`) • OpenAI Codex Cloud (`gpt-6.1-sol` Ultra) • Local 4xT4 GPU Swarm (`Hermes` / `Qwen3` / `DeepSeek`)</div>
    </div>
  </div>
  <div class="nav-links">
    <a href="http://harnesses.boylenet.themfboyles.org" target="_blank">Multi-Harness Arena (:4098)</a>
    <a href="http://sentinel.boylenet.themfboyles.org" target="_blank">Sentinel (:4099)</a>
    <a href="http://jarvis.boylenet.themfboyles.org" target="_blank">Jarvis Cockpit (:3002)</a>
    <a href="http://litellm.boylenet.themfboyles.org/ui" target="_blank">LiteLLM (:4000)</a>
    <a href="http://dashy.boylenet.themfboyles.org" target="_blank">Dashy Portal (:4080)</a>
  </div>
</header>

<div style="max-width:1760px;margin:14px auto 0;padding:0 24px;">
  <div style="background:linear-gradient(135deg, rgba(16,185,129,0.18), rgba(56,189,248,0.18), rgba(168,85,247,0.18));border:1px solid rgba(16,185,129,0.45);border-radius:12px;padding:12px 18px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
    <div>
      <span class="chip ok" style="font-size:11.5px;margin-right:8px;">💰 $1,000.00 FREE CLOUD CREDITS ACTIVE</span>
      <strong id="creditBannerTitle" style="font-size:13.5px;color:#f8fafc;">$1,000 Free Cloud Session Credit Pool ($250 x Pools A/B/C/D • Expires Nov 5 at 2:59 AM EST)</strong>
      <div style="font-size:11.5px;color:#cbd5e1;margin-top:3px;">
        Priority Routing: Burn <strong>$250/pool (`$1,000 total`)</strong> via <code>claude --cloud</code> (<code>claude-opus-5-5</code> / <code>claude-sonnet-5-5</code> / <code>fable-5-1</code>) + <code>codex cloud exec</code> (<code>gpt-6.1-sol</code>) BEFORE touching local 5h/weekly plan limits!
      </div>
    </div>
    <div style="text-align:right;">
      <div class="chip ok" style="font-size:11px;">Overage Protection: OFF ($0.00 Risk)</div>
      <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Pool A: $250 • Pool B: $250 • Pool C: $250 • Pool D: $250</div>
      <div style="margin-top:6px;display:flex;gap:8px;justify-content:flex-end;align-items:center;">
        <span id="quotaObservedAtBadge" class="chip" style="font-size:10.5px;">quota_observed_at: loading...</span>
        <button id="btnRefreshUsage" class="btn-ghost" style="padding:4px 10px;font-size:11px;" onclick="refreshUsageNow()">🔄 Refresh Usage</button>
      </div>
    </div>
  </div>
</div>

<!-- 5 Provider Interactive Cards / Tabs Strip -->
<div style="max-width:1760px;margin:12px auto 0;padding:0 24px;">
  <div id="providerCardsStrip" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;">
    <div class="lane-card provider-tab-card active" id="provCard-claude" data-provider="claude" onclick="selectProviderCard('claude')" style="cursor:pointer;border-color:#38bdf8;">
      <div class="lane-hdr"><span>🟣 Anthropic Claude $500</span><span class="chip ok" id="provState-claude">OK</span></div>
      <div style="font-size:11px;color:var(--muted);" id="provSub-claude">Pools A/B/C/D ($250x4 Cloud Credits)</div>
    </div>
    <div class="lane-card provider-tab-card" id="provCard-codex" data-provider="codex" onclick="selectProviderCard('codex')" style="cursor:pointer;">
      <div class="lane-hdr"><span>🟢 OpenAI Codex $500</span><span class="chip ok" id="provState-codex">OK</span></div>
      <div style="font-size:11px;color:var(--muted);" id="provSub-codex">GPT-6.1 Sol Ultra Cloud</div>
    </div>
    <div class="lane-card provider-tab-card" id="provCard-kimi" data-provider="kimi" onclick="selectProviderCard('kimi')" style="cursor:pointer;">
      <div class="lane-hdr"><span>🌙 Moonshot Kimi</span><span class="chip ok" id="provState-kimi">OK</span></div>
      <div style="font-size:11px;color:var(--muted);" id="provSub-kimi">kimi-for-coding / Kimi K2.8</div>
    </div>
    <div class="lane-card provider-tab-card" id="provCard-grok" data-provider="grok" onclick="selectProviderCard('grok')" style="cursor:pointer;">
      <div class="lane-hdr"><span>⚡ xAI Grok</span><span class="chip ok" id="provState-grok">OK</span></div>
      <div style="font-size:11px;color:var(--muted);" id="provSub-grok">grok-4.20 / grok-code-fast-1</div>
    </div>
    <div class="lane-card provider-tab-card" id="provCard-local" data-provider="local" onclick="selectProviderCard('local')" style="cursor:pointer;">
      <div class="lane-hdr"><span>🖥️ Local 4xT4 + 2080Ti</span><span class="chip ok" id="provState-local">ONLINE</span></div>
      <div style="font-size:11px;color:var(--muted);" id="provSub-local">64GB T4 Swarm (.125/.228) + 11GB 2080Ti (.137)</div>
    </div>
  </div>
  <div id="providerActiveDetail" style="margin-top:8px;padding:8px 14px;border-radius:8px;background:rgba(15,23,42,0.85);border:1px solid rgba(56,189,248,0.22);font-size:12px;color:#e2e8f0;">
    Active Provider Focus: <strong>Anthropic Claude $500</strong> — Pools A/B/C/D ($250x4 Cloud Session Credits • O1740 Dynamic Routing)
  </div>
</div>

<div class="layout">
  <aside>
    <div class="card">
      <div class="card-title">
        <span>Claude ABCD Cloud Pools (O1740)</span>
        <span id="recPoolBadge" class="chip ok">Pool A</span>
      </div>
      <div id="poolList">Loading pool telemetry...</div>
      <div style="margin-top:8px;font-size:11px;color:var(--muted);">
        Zero-Local-CPU Cloud execution routes to lowest 5h% OK pool &amp; burns $250/pool free Cloud Session Credits first.
      </div>
    </div>

    <div class="card">
      <div class="card-title">
        <span>GitHub Repo Presets (mcboyle/*)</span>
        <span class="chip">7 Repos</span>
      </div>
      <label>Connected GitHub Repository</label>
      <select id="repoPreset" onchange="refreshSetupBundle()"></select>
      <label>Cloud Setup Target Platform</label>
      <select id="setupTarget" onchange="refreshSetupBundle()">
        <option value="codex-cloud">OpenAI Codex Cloud (GPT-6.1 Sol Ultra)</option>
        <option value="claude-cloud">Anthropic Claude Cloud (Opus 5.5 / Fable 5.1 High)</option>
      </select>
      <div class="btn-row">
        <button class="btn-ghost" onclick="switchTab('setup')">View Setup Script &amp; Env Vars</button>
      </div>
    </div>

    <div class="card">
      <div class="card-title">
        <span>Recent Cloud Burst Ledger</span>
        <button class="btn-ghost" style="padding:3px 8px;font-size:10px;" onclick="loadStatus()">Refresh</button>
      </div>
      <div id="ledgerBox" style="font-size:11px;color:var(--muted);max-height:220px;overflow-y:auto;"></div>
    </div>
  </aside>

  <main>
    <div class="tabs">
      <div class="tab active" id="tabBtn-hybrid" onclick="switchTab('hybrid')">⚡ 1. Hybrid Cloud + Local GPU Burst Fanout</div>
      <div class="tab" id="tabBtn-claude" onclick="switchTab('claude')">🟣 2. Claude ABCD Cloud (`claude-opus-5-5` / `fable-5-1` / `$1,000 Credits`)</div>
      <div class="tab" id="tabBtn-codex" onclick="switchTab('codex')">🟢 3. OpenAI Codex Cloud (`gpt-6.1-sol` Ultra)</div>
      <div class="tab" id="tabBtn-setup" onclick="switchTab('setup')">🛠️ 4. Cloud Setup Script &amp; Env Vars Generator</div>
    </div>

    <!-- TAB 1: HYBRID BURST -->
    <section id="tab-hybrid">
      <div class="card">
        <div class="card-title">
          <span>Simultaneous Cloud (0% Local CPU) + Local 4xT4 GPU Burst Fanout</span>
          <span class="chip ok">Zero Local CPU Bottleneck</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">
          <div>
            <label>Claude Cloud Pools</label>
            <input id="hybPools" value="auto" placeholder="auto or A,B,C,D">
          </div>
          <div>
            <label>Claude Cloud Model</label>
            <select id="hybClaudeModel">
              <option value="claude-opus-5-5" selected>claude-opus-5-5 (Claude Opus 5.5 Flagship)</option>
              <option value="claude-sonnet-5-5">claude-sonnet-5-5 (Claude Sonnet 5.5 Fast)</option>
              <option value="fable-5-1">fable-5-1 (Fable 5.1 High Cloud)</option>
              <option value="claude-opus-4-7">claude-opus-4-7 (Opus 4.7 1M)</option>
              <option value="claude-sonnet-4-6">claude-sonnet-4-6 (Sonnet 4.6)</option>
            </select>
          </div>
          <div>
            <label>OpenAI Codex Cloud Model</label>
            <select id="hybCodexModel">
              <option value="gpt-6.1-sol" selected>gpt-6.1-sol (GPT-6.1 Sol Ultra)</option>
              <option value="gpt-6-sol">gpt-6-sol (GPT-6 Sol Flagship)</option>
              <option value="gpt-6-astra">gpt-6-astra (GPT-6 Astra Judgement)</option>
              <option value="gpt-5.6-terra">gpt-5.6-terra (GPT-5.6 Terra)</option>
              <option value="gpt-5.6-sol">gpt-5.6-sol (GPT-5.6 Sol)</option>
            </select>
          </div>
          <div>
            <label>Local 4xT4 GPU Lanes</label>
            <input id="hybLocalLanes" value="hermes,qwen3-coder,deepseek">
          </div>
        </div>
        <label>High-ROI Task / Coding / Audit Prompt</label>
        <textarea id="hybPrompt">Write a lock-free token-bucket rate limiter in Python with monotonic clock precision and prove its burst invariant.</textarea>
        <div class="btn-row">
          <button class="btn-primary" onclick="runHybridBurst()">🚀 Launch Hybrid Cloud + Local Burst Fanout</button>
        </div>
      </div>
      <div id="hybSummary" class="card" style="display:none;"></div>
      <div id="hybGrid" class="grid-cards"></div>
    </section>

    <!-- TAB 2: CLAUDE ABCD CLOUD -->
    <section id="tab-claude" style="display:none;">
      <div class="card">
        <div class="card-title">
          <span>Anthropic Claude ABCD Cloud Environments (`--cloud` / `--environment` / `$1,000 Credits`)</span>
          <span class="chip ok">$250 x 4 Pools Free Credits</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">
          <div>
            <label>Pool Selection</label>
            <select id="clPool">
              <option value="auto">Auto (Lowest 5h% OK Pool • $250 Credit)</option>
              <option value="A">Pool A (~/.claude-a • $250 Credit)</option>
              <option value="B">Pool B (~/.claude-b • $250 Credit)</option>
              <option value="C">Pool C (~/.claude-c • $250 Credit)</option>
              <option value="D">Pool D (~/.claude-d • $250 Credit)</option>
            </select>
          </div>
          <div>
            <label>Claude Cloud Model</label>
            <select id="clModel">
              <option value="claude-opus-5-5" selected>claude-opus-5-5 • Claude Opus 5.5</option>
              <option value="claude-sonnet-5-5">claude-sonnet-5-5 • Claude Sonnet 5.5</option>
              <option value="fable-5-1">fable-5-1 • Fable 5.1 High</option>
              <option value="claude-opus-4-7">claude-opus-4-7 • Claude Opus 4.7</option>
              <option value="claude-sonnet-4-6">claude-sonnet-4-6 • Claude Sonnet 4.6</option>
            </select>
          </div>
          <div>
            <label>Reasoning Effort</label>
            <select id="clEffort">
              <option value="high">high (Default)</option>
              <option value="xhigh">xhigh</option>
              <option value="max">max</option>
              <option value="medium">medium</option>
            </select>
          </div>
          <div>
            <label>Cloud Environment ID (Optional)</label>
            <input id="clEnvId" placeholder="ccpool_... (or leave blank)">
          </div>
        </div>
        <label>Claude Cloud Task Prompt or Review Target Branch/PR</label>
        <textarea id="clPrompt">Audit the retry backoff logic and propose a minimal zero-regression patch.</textarea>
        <div class="btn-row">
          <button class="btn-purple" onclick="runClaudeCloud()">☁️ Dispatch Claude Cloud Task (Uses $250 Pool Credit)</button>
          <button class="btn-emerald" onclick="runZeroCostReview()">🛡️ $0-Cost Local GPU (:4092) + Cloud Multi-Lens Review</button>
          <button class="btn-ghost" onclick="runClaudeUltraReview()">🔍 Optional `claude ultrareview --json` (Free Quota Note vs $1,000 Cloud Credits)</button>
        </div>
      </div>
      <div class="card">
        <div class="card-title"><span>Claude Cloud Output</span><span id="clMeta" class="chip">Ready</span></div>
        <pre id="clOutput">Select Pool A/B/C/D and model (claude-opus-5-5 / claude-sonnet-5-5 / fable-5-1) to run on Anthropic Cloud with 0% local CPU ($1,000 Free Cloud Session Credits active until Nov 5).</pre>
      </div>
    </section>

    <!-- TAB 3: OPENAI CODEX CLOUD -->
    <section id="tab-codex" style="display:none;">
      <div class="card">
        <div class="card-title">
          <span>OpenAI Codex Cloud Engine (`codex cloud exec/list/status/diff/apply`)</span>
          <span class="chip ok">GPT-6.1 Sol Ultra</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;">
          <div>
            <label>Codex Cloud Model</label>
            <select id="cxModel">
              <option value="gpt-6.1-sol" selected>gpt-6.1-sol (GPT-6.1 Sol Ultra)</option>
              <option value="gpt-6-sol">gpt-6-sol (GPT-6 Sol Flagship)</option>
              <option value="gpt-6-astra">gpt-6-astra (GPT-6 Astra Judgement)</option>
              <option value="gpt-5.6-terra">gpt-5.6-terra (GPT-5.6 Terra)</option>
              <option value="gpt-5.6-sol">gpt-5.6-sol (GPT-5.6 Sol)</option>
            </select>
          </div>
          <div>
            <label>Reasoning Effort</label>
            <select id="cxEffort">
              <option value="xhigh">xhigh / Ultra</option>
              <option value="high">high</option>
              <option value="medium">medium</option>
            </select>
          </div>
          <div>
            <label>Best-of-N Attempts</label>
            <select id="cxAttempts">
              <option value="1">1 attempt</option>
              <option value="2">2 attempts</option>
              <option value="3">3 attempts</option>
              <option value="4">4 attempts (Best-of-4)</option>
            </select>
          </div>
          <div>
            <label>Git Branch</label>
            <input id="cxBranch" value="main">
          </div>
          <div>
            <label>Cloud `--env` ID or Task ID</label>
            <input id="cxEnvOrTask" placeholder="env_... or task_...">
          </div>
        </div>
        <label>Codex Cloud Task Prompt</label>
        <textarea id="cxPrompt">Analyze repository hot paths and emit a deterministic O(1) lookup optimization.</textarea>
        <div class="btn-row">
          <button class="btn-emerald" onclick="runCodexCloudExec()">☁️ Submit Codex Cloud Task (`gpt-6.1-sol`)</button>
          <button class="btn-ghost" onclick="runCodexCloudList()">📋 `codex cloud list --json`</button>
          <button class="btn-ghost" onclick="runCodexTaskAction('status')">🔎 `status <TASK_ID>`</button>
          <button class="btn-ghost" onclick="runCodexTaskAction('diff')">📄 `diff <TASK_ID>`</button>
          <button class="btn-ghost" onclick="runCodexTaskAction('apply')">✅ `apply <TASK_ID>`</button>
        </div>
      </div>
      <div class="card">
        <div class="card-title"><span>OpenAI Codex Cloud Output</span><span id="cxMeta" class="chip">Ready</span></div>
        <pre id="cxOutput">Ready to dispatch tasks to OpenAI Codex Cloud (`gpt-6.1-sol` Ultra) or inspect active cloud tasks.</pre>
      </div>
    </section>

    <!-- TAB 4: CLOUD SETUP SCRIPT & ENV VARS GENERATOR -->
    <section id="tab-setup" style="display:none;">
      <div class="card">
        <div class="card-title">
          <span>Ready-to-Paste Cloud Environment Setup Script &amp; Environment Variables</span>
          <button class="btn-primary" onclick="copySetupScript()">📋 Copy Setup Script</button>
        </div>
        <p style="font-size:12px;color:var(--muted);margin-top:0;">
          Paste directly into <strong>Claude Desktop → New environment → Cloud (`Opus 5.5` / `Fable 5.1 High`)</strong> or <strong>OpenAI Codex Desktop → Create a cloud environment (`GPT-6.1 Sol Ultra`)</strong> for any of the 7 connected `mcboyle/*` repositories:
        </p>
        <label>Container Setup Script (`bash`)</label>
        <pre id="setupScriptBox">Loading...</pre>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;">
          <label style="margin:0;">Environment Variables (`.env` key=value)</label>
          <button class="btn-ghost" style="padding:4px 10px;font-size:11px;" onclick="copyEnvVars()">📋 Copy Env Vars</button>
        </div>
        <pre id="setupEnvBox" style="margin-top:6px;">Loading...</pre>
      </div>
    </section>
  </main>
</div>

<script>
const PROVIDER_DESCRIPTIONS = {
  claude: {title: 'Anthropic Claude $500', detail: 'Pools A/B/C/D ($250x4 Cloud Session Credits • O1740 Dynamic Routing • claude-opus-5-5 / claude-sonnet-5-5 / fable-5-1)', tab: 'claude'},
  codex: {title: 'OpenAI Codex $500', detail: 'OpenAI Codex Cloud Engine (gpt-6.1-sol Ultra / gpt-6-astra / gpt-5.6-terra • Best-of-N Cloud Containers)', tab: 'codex'},
  kimi: {title: 'Moonshot Kimi', detail: 'Kimi Code CLI Cloud (kimi-for-coding / Kimi K2.8) + Local Vault .72 Kimi-K3-2.8T MoE', tab: 'hybrid'},
  grok: {title: 'xAI Grok', detail: 'xAI Grok Cloud & Fast Code Lane (grok-4.20 / grok-code-fast-1 via LiteLLM & Hybrid Burst)', tab: 'hybrid'},
  local: {title: 'Local 4xT4 + 2080Ti', detail: '64GB 4xT4 GPU Swarm (.125/.228) + 11GB RTX 2080 Ti (.137) — $0 Marginal Cost Local GPU Lanes', tab: 'hybrid'}
};

function selectProviderCard(prov) {
  ['claude', 'codex', 'kimi', 'grok', 'local'].forEach(p => {
    const el = document.getElementById('provCard-' + p);
    if (el) {
      el.classList.toggle('active', p === prov);
      el.style.borderColor = (p === prov) ? '#38bdf8' : 'rgba(56, 189, 248, 0.25)';
    }
  });
  const info = PROVIDER_DESCRIPTIONS[prov] || PROVIDER_DESCRIPTIONS.claude;
  const detEl = document.getElementById('providerActiveDetail');
  if (detEl) {
    detEl.innerHTML = `Active Provider Focus: <strong>${esc(info.title)}</strong> — ${esc(info.detail)}`;
  }
  if (info.tab) switchTab(info.tab);
}

function switchTab(tab) {
  ['hybrid', 'claude', 'codex', 'setup'].forEach(t => {
    document.getElementById('tab-' + t).style.display = (t === tab) ? 'block' : 'none';
    document.getElementById('tabBtn-' + t).classList.toggle('active', t === tab);
  });
  if (tab === 'setup') refreshSetupBundle();
}

function esc(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function refreshUsageNow() {
  const btn = document.getElementById('btnRefreshUsage');
  if (btn) btn.textContent = '⏳ Refreshing...';
  try {
    await fetch('/api/refresh-usage', {method: 'POST'});
  } catch (e) {}
  await loadStatus();
  if (btn) btn.textContent = '🔄 Refresh Usage';
}

async function loadStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    if (d.cloud_session_credits && d.cloud_session_credits.banner) {
      document.getElementById('creditBannerTitle').textContent = d.cloud_session_credits.banner;
    }
    const qBadge = document.getElementById('quotaObservedAtBadge');
    if (qBadge && d.quota_observed_at) {
      qBadge.textContent = 'quota_observed_at: ' + d.quota_observed_at;
    }
    (d.providers || []).forEach(pr => {
      const stEl = document.getElementById('provState-' + pr.id);
      const subEl = document.getElementById('provSub-' + pr.id);
      if (stEl) stEl.textContent = pr.state || 'OK';
      if (subEl && pr.subtitle) subEl.textContent = pr.subtitle;
    });
    document.getElementById('recPoolBadge').textContent = 'Rec: Pool ' + (d.recommended_claude_pool || 'A');
    const poolHtml = (d.claude_pools || []).map(p => {
      const color = p.state === 'OK' ? '#10b981' : '#f59e0b';
      const credBadge = p.cloud_credit_remaining_usd ? ` • <span style="color:#38bdf8">$${esc(p.cloud_credit_remaining_usd)} credit</span>` : '';
      const obsSpan = p.quota_observed_at ? ` • <span style="color:#94a3b8;font-size:10px;">obs: ${esc(p.quota_observed_at)}</span>` : '';
      return `<div class="pool-pill" data-pool="${esc(p.pool)}"><span style="color:${color};font-weight:700;">● Pool ${esc(p.pool)} (${esc(p.state)})</span><span>5h: ${esc(p.five_hour_pct)}% • wk: ${esc(p.weekly_pct)}%${credBadge}${obsSpan}</span></div>`;
    }).join('');
    document.getElementById('poolList').innerHTML = poolHtml;

    const repoSel = document.getElementById('repoPreset');
    if (!repoSel.options.length) {
      (d.github_repo_presets || []).forEach(rp => {
        const opt = document.createElement('option');
        opt.value = rp.repo;
        opt.textContent = rp.label;
        repoSel.appendChild(opt);
      });
    }

    const ledger = d.recent_ledger || [];
    document.getElementById('ledgerBox').innerHTML = ledger.length
      ? ledger.map(e => `<div style="padding:4px 0;border-bottom:1px solid rgba(148,163,184,0.12);"><strong>${esc(e.engine)}</strong> • ${esc(e.model || (e.ok_lanes + '/' + e.total_lanes + ' lanes'))} • <span style="color:#38bdf8">${esc(e.elapsed_s || e.wall_elapsed_s)}s</span></div>`).join('')
      : 'No burst events logged yet.';
  } catch (e) {}
}

async function refreshSetupBundle() {
  const repo = document.getElementById('repoPreset').value || 'mcboyle/Bulkdownloader';
  const target = document.getElementById('setupTarget').value || 'codex-cloud';
  const r = await fetch(`/api/setup-script?target=${encodeURIComponent(target)}&repo=${encodeURIComponent(repo)}`);
  const d = await r.json();
  document.getElementById('setupScriptBox').textContent = d.setup_script || '';
  document.getElementById('setupEnvBox').textContent = d.env_dotenv || '';
}

function copySetupScript() {
  navigator.clipboard.writeText(document.getElementById('setupScriptBox').textContent);
}

function copyEnvVars() {
  navigator.clipboard.writeText(document.getElementById('setupEnvBox').textContent);
}

async function runHybridBurst() {
  const grid = document.getElementById('hybGrid');
  const sumBox = document.getElementById('hybSummary');
  sumBox.style.display = 'block';
  sumBox.innerHTML = '⏳ Dispatching simultaneous Cloud (Claude ABCD + Codex + Kimi) + Local 4xT4 GPU (Hermes + Qwen3 + DeepSeek) fanout...';
  grid.innerHTML = '';

  const payload = {
    prompt: document.getElementById('hybPrompt').value,
    pools: document.getElementById('hybPools').value,
    claude_model: document.getElementById('hybClaudeModel').value,
    codex_model: document.getElementById('hybCodexModel').value,
    local_lanes: document.getElementById('hybLocalLanes').value
  };
  const r = await fetch('/api/hybrid-burst', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const d = await r.json();
  sumBox.innerHTML = `<strong>✅ ${esc(d.consensus_summary || ('Completed ' + d.ok_lanes + '/' + d.total_lanes + ' lanes'))}</strong>`;
  grid.innerHTML = (d.candidates || []).map(c => `
    <div class="lane-card">
      <div class="lane-hdr">
        <span>${esc(c.lane)} <span class="chip">${esc(c.model || '')}</span></span>
        <span class="chip ${c.rc === 0 ? 'ok' : ''}">rc=${esc(c.rc)} • ${esc(c.elapsed_s)}s</span>
      </div>
      <div style="font-size:11px;color:var(--muted);margin-bottom:6px;">${esc(c.compute)}</div>
      <pre>${esc(c.answer || c.output || '')}</pre>
    </div>
  `).join('');
  loadStatus();
}

async function runClaudeCloud() {
  document.getElementById('clMeta').textContent = 'Running on Anthropic Cloud...';
  document.getElementById('clOutput').textContent = 'Dispatching to Claude Cloud Pool ($250 Free Cloud Session Credits active)...';
  const payload = {
    action: 'dispatch',
    pool: document.getElementById('clPool').value,
    model: document.getElementById('clModel').value,
    effort: document.getElementById('clEffort').value,
    environment_id: document.getElementById('clEnvId').value,
    prompt: document.getElementById('clPrompt').value
  };
  const r = await fetch('/api/claude-cloud', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const d = await r.json();
  document.getElementById('clMeta').textContent = `Pool ${d.pool} • model=${d.model} • rc=${d.rc} • ${d.elapsed_s}s`;
  document.getElementById('clOutput').textContent = d.answer || d.output || JSON.stringify(d, null, 2);
  loadStatus();
}

async function runZeroCostReview() {
  document.getElementById('clMeta').textContent = 'Running $0-Cost Multi-Lens Review...';
  document.getElementById('clOutput').textContent = 'Routing to Local GPU Multi-Lens Review (:4092) + Subscription Cloud Pools...';
  const payload = {
    action: 'review',
    pool: document.getElementById('clPool').value,
    target: document.getElementById('clPrompt').value.trim()
  };
  const r = await fetch('/api/claude-cloud', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const d = await r.json();
  document.getElementById('clMeta').textContent = `Pool ${d.pool} • ${d.mode} • rc=${d.rc}`;
  document.getElementById('clOutput').textContent = d.output || JSON.stringify(d, null, 2);
  loadStatus();
}

async function runClaudeUltraReview() {
  document.getElementById('clMeta').textContent = 'Checking Optional Cloud UltraReview...';
  document.getElementById('clOutput').textContent = 'Inspecting optional claude ultrareview --json (with Free Quota vs $1,000 Cloud Credit note)...';
  const payload = {
    action: 'ultrareview',
    pool: document.getElementById('clPool').value,
    target: document.getElementById('clPrompt').value.trim(),
    dry_probe: true
  };
  const r = await fetch('/api/claude-cloud', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const d = await r.json();
  document.getElementById('clMeta').textContent = `Pool ${d.pool} • ${d.mode || 'ultrareview'} • rc=${d.rc}`;
  document.getElementById('clOutput').textContent = `[Quota Note] ${d.quota_note || ''}\n\nCommand: ${d.command}\n\n${d.output || ''}`;
  loadStatus();
}

async function runCodexCloudExec() {
  document.getElementById('cxMeta').textContent = 'Submitting to Codex Cloud...';
  document.getElementById('cxOutput').textContent = 'Running OpenAI Codex Cloud task...';
  const payload = {
    action: 'exec',
    model: document.getElementById('cxModel').value,
    effort: document.getElementById('cxEffort').value,
    attempts: parseInt(document.getElementById('cxAttempts').value || '1', 10),
    branch: document.getElementById('cxBranch').value,
    env_id: document.getElementById('cxEnvOrTask').value,
    repo: document.getElementById('repoPreset').value || 'mcboyle/Bulkdownloader',
    prompt: document.getElementById('cxPrompt').value
  };
  const r = await fetch('/api/codex-cloud', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const d = await r.json();
  document.getElementById('cxMeta').textContent = `model=${d.model} • effort=${d.effort} • rc=${d.rc} • ${d.elapsed_s}s`;
  document.getElementById('cxOutput').textContent = d.output || JSON.stringify(d, null, 2);
  loadStatus();
}

async function runCodexCloudList() {
  const envId = document.getElementById('cxEnvOrTask').value;
  const r = await fetch('/api/codex-cloud', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: 'list', env_id: envId})
  });
  const d = await r.json();
  document.getElementById('cxMeta').textContent = `codex cloud list • rc=${d.rc} • ${d.elapsed_s}s`;
  document.getElementById('cxOutput').textContent = JSON.stringify(d, null, 2);
}

async function runCodexTaskAction(action) {
  const tid = document.getElementById('cxEnvOrTask').value.trim();
  if (!tid) {
    document.getElementById('cxOutput').textContent = 'Enter a TASK_ID in the Cloud --env ID or Task ID field first.';
    return;
  }
  const r = await fetch('/api/codex-cloud', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action, task_id: tid})
  });
  const d = await r.json();
  document.getElementById('cxMeta').textContent = `codex cloud ${action} • rc=${d.rc}`;
  document.getElementById('cxOutput').textContent = d.output || JSON.stringify(d, null, 2);
}

window.addEventListener('DOMContentLoaded', async () => {
  await loadStatus();
  await refreshSetupBundle();
  setInterval(loadStatus, 2500);
});
</script>
</body>
</html>
"""


class CloudBurstHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _send_json(self, obj: Dict[str, Any], code: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(
                {
                    "status": "ok",
                    "service": "bd-cloud-burst-web",
                    "port": PORT,
                    "url": "http://cloud.boylenet.themfboyles.org",
                    "cloud_session_credits_usd": 1000.0,
                    "cloud_session_credits_banner": "$1,000 Free Cloud Session Credit Pool ($250 x Pools A/B/C/D • Expires Nov 5)",
                    "overage_protection": "OFF ($0.00 risk)",
                    "claude_cloud_models": [m["id"] for m in cb.CLAUDE_CLOUD_MODELS],
                    "codex_cloud_models": [m["id"] for m in cb.CODEX_CLOUD_MODELS],
                    "github_repos": [r["repo"] for r in cb.GITHUB_REPO_PRESETS],
                    "local_gpu_lanes": [t["id"] for t in cb.LOCAL_BURST_TARGETS],
                }
            )
            return
        if parsed.path in ("/api/status", "/api/refresh-usage"):
            self._send_json(cb.get_orchestrator_status())
            return
        if parsed.path == "/api/setup-script":
            qs = urllib.parse.parse_qs(parsed.query)
            target = (qs.get("target") or ["codex-cloud"])[0]
            repo = (qs.get("repo") or ["mcboyle/Bulkdownloader"])[0]
            self._send_json(cb.generate_cloud_setup_bundle(target=target, repo=repo))
            return
        body = HTML_PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        if self.path == "/api/refresh-usage":
            self._send_json(cb.get_orchestrator_status())
            return
        if self.path == "/api/hybrid-burst":
            prompt = str(data.get("prompt") or "Say PONG")
            raw_pools = str(data.get("pools") or "auto").strip()
            if raw_pools.lower() == "auto":
                c_pools = [cb.pick_best_claude_pool("auto")]
            else:
                c_pools = [p.strip().upper() for p in raw_pools.split(",") if p.strip()]
            raw_local = str(data.get("local_lanes") or "hermes,qwen3-coder,deepseek")
            loc_lanes = [l.strip() for l in raw_local.split(",") if l.strip()]
            res = cb.run_hybrid_burst(
                prompt=prompt,
                claude_pools=c_pools,
                claude_model=str(data.get("claude_model") or "claude-opus-5-5"),
                codex_model=str(data.get("codex_model") or "gpt-6.1-sol"),
                include_kimi=bool(data.get("include_kimi", True)),
                local_lanes=loc_lanes,
                effort=str(data.get("effort") or "high"),
            )
            self._send_json(res)
            return
        if self.path == "/api/claude-cloud":
            action = str(data.get("action") or "dispatch")
            if action == "review":
                res = cb.run_zero_cost_multilens_review(
                    target=str(data.get("target") or ""),
                    pool=str(data.get("pool") or "auto"),
                )
                self._send_json(res)
                return
            if action == "ultrareview":
                res = cb.claude_cloud_ultrareview(
                    target=str(data.get("target") or ""),
                    pool=str(data.get("pool") or "auto"),
                    timeout_minutes=int(data.get("timeout_minutes") or 10),
                    dry_probe=bool(data.get("dry_probe", True)),
                )
                self._send_json(res)
                return
            res = cb.claude_cloud_dispatch(
                prompt=str(data.get("prompt") or "Say PONG"),
                pool=str(data.get("pool") or "auto"),
                model=str(data.get("model") or "claude-opus-5-5"),
                effort=str(data.get("effort") or "high"),
                environment_id=str(data.get("environment_id") or ""),
            )
            self._send_json(res)
            return
        if self.path == "/api/codex-cloud":
            action = str(data.get("action") or "list")
            if action == "list":
                self._send_json(
                    cb.codex_cloud_list(env_id=str(data.get("env_id") or ""))
                )
                return
            if action in ("status", "diff", "apply"):
                self._send_json(
                    cb.codex_cloud_task_action(action, str(data.get("task_id") or ""))
                )
                return
            res = cb.codex_cloud_exec(
                prompt=str(data.get("prompt") or "Say PONG"),
                env_id=str(data.get("env_id") or ""),
                model=str(data.get("model") or "gpt-6.1-sol"),
                effort=str(data.get("effort") or "xhigh"),
                attempts=int(data.get("attempts") or 1),
                branch=str(data.get("branch") or "main"),
                repo=str(data.get("repo") or "mcboyle/Bulkdownloader"),
            )
            self._send_json(res)
            return
        self._send_json({"rc": 1, "error": f"Unknown endpoint {self.path}"}, code=404)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), CloudBurstHandler)
    print(f"[bd-cloud-burst-web] Listening on 0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
