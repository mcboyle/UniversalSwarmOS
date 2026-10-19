from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.machinery
import importlib.util
import json
import os
import threading
import time
from typing import Any, Dict, List
import urllib.parse
import urllib.request

PORT = int(os.environ.get("BD_DEEP_RESEARCH_PORT", "4094"))
HISTORY_PATH = "/var/tmp/bd-deep-research-history.json"
_HISTORY_LOCK = threading.Lock()


def _load_engine_module():
    cli_path = "/home/mboyle/bin/bd-deep-research"
    loader = importlib.machinery.SourceFileLoader("bd_deep_research_mod", cli_path)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load {cli_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENGINE = _load_engine_module()


def load_history() -> List[Dict[str, Any]]:
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_to_history(record: Dict[str, Any]) -> None:
    with _HISTORY_LOCK:
        hist = load_history()
        hist = [h for h in hist if h.get("query") != record.get("query")]
        hist.insert(0, record)
        hist = hist[:20]
        try:
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(hist, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


def check_searxng_fast() -> Dict[str, Any]:
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(
            "http://10.0.70.164:8888/search?q=avx512&format=json",
            headers={"User-Agent": ENGINE.USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=2.5) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        return {
            "online": True,
            "endpoint": "http://10.0.70.164:8888",
            "format": "json",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "sample_hits": len(data.get("results", [])),
        }
    except Exception as exc:
        return {
            "online": False,
            "endpoint": "http://10.0.70.164:8888",
            "error": str(exc),
        }


def get_cluster_status() -> Dict[str, Any]:
    searx = check_searxng_fast()
    oracles = ENGINE.probe_dual_oracles(timeout=1.8)
    qdrant_meta, _ = ENGINE.query_qdrant_and_local_rag("status", start_id=1, max_rag=0)
    return {
        "status": "ok",
        "service": "bd-deep-research-web",
        "port": PORT,
        "searxng": searx,
        "oracles": oracles,
        "qdrant": qdrant_meta,
        "engines": [
            {"id": k, "label": v["label"], "model": v["model"], "kind": v["kind"]}
            for k, v in ENGINE.SYNTHESIS_ENGINES.items()
        ],
    }


HTML_STUDIO = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Boylenet Deep Research & Dual-Oracle Citation Studio (:4094)</title>
<style>
  :root {
    --bg-deep: #040710;
    --bg-glass: rgba(11, 18, 34, 0.82);
    --bg-card: rgba(16, 25, 46, 0.78);
    --bg-card-hover: rgba(24, 37, 68, 0.92);
    --bg-input: rgba(7, 12, 24, 0.95);
    --border: rgba(56, 189, 248, 0.2);
    --border-bright: rgba(0, 229, 255, 0.55);
    --cyan: #00e5ff;
    --sky: #38bdf8;
    --purple: #a855f7;
    --emerald: #10b981;
    --amber: #f59e0b;
    --rose: #f43f5e;
    --text: #f1f5f9;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    min-height: 100vh;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background:
      radial-gradient(circle at 15% 12%, rgba(0, 229, 255, 0.09), transparent 36%),
      radial-gradient(circle at 85% 82%, rgba(168, 85, 247, 0.09), transparent 40%),
      var(--bg-deep);
    color: var(--text);
    display: flex;
    flex-direction: column;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 13px 24px;
    background: rgba(6, 10, 20, 0.9);
    backdrop-filter: blur(16px);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 50;
    flex-wrap: wrap;
    gap: 12px;
  }
  .brand { display: flex; align-items: center; gap: 13px; }
  .brand-icon {
    width: 38px; height: 38px; border-radius: 10px;
    background: linear-gradient(135deg, var(--cyan), var(--purple));
    display: flex; align-items: center; justify-content: center;
    font-weight: 900; font-size: 18px; color: #040710;
    box-shadow: 0 0 22px rgba(0, 229, 255, 0.35);
  }
  .brand-title { font-size: 16.5px; font-weight: 800; letter-spacing: 0.25px; color: #fff; }
  .brand-sub { font-size: 11.5px; color: var(--muted); margin-top: 2px; }
  .telemetry-bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .status-pill {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 11px; border-radius: 999px; font-size: 11px; font-weight: 600;
    background: rgba(15, 23, 42, 0.85); border: 1px solid var(--border);
    color: #cbd5e1;
  }
  .status-pill .dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--emerald); box-shadow: 0 0 8px var(--emerald);
  }
  .status-pill.warn .dot { background: var(--amber); box-shadow: 0 0 8px var(--amber); }
  .nav-links { display: flex; gap: 6px; flex-wrap: wrap; }
  .nav-links a {
    color: var(--text); text-decoration: none; font-size: 11.5px; font-weight: 600;
    padding: 6px 11px; border-radius: 7px; border: 1px solid var(--border);
    background: rgba(15, 23, 42, 0.75); transition: all 0.15s ease;
  }
  .nav-links a:hover {
    border-color: var(--cyan); color: var(--cyan);
    box-shadow: 0 0 12px rgba(0, 229, 255, 0.22);
  }
  .layout {
    display: grid;
    grid-template-columns: 330px 1fr;
    flex: 1;
    max-width: 1760px;
    width: 100%;
    margin: 0 auto;
    gap: 20px;
    padding: 20px 24px 36px;
  }
  @media (max-width: 1100px) {
    .layout { grid-template-columns: 1fr; }
  }
  .sidebar {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .glass-panel {
    background: var(--bg-glass);
    backdrop-filter: blur(16px);
    border: 1px solid var(--border);
    border-radius: 13px;
    padding: 15px;
    box-shadow: 0 10px 32px rgba(0, 0, 0, 0.42);
  }
  .panel-hdr {
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--cyan);
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  label {
    display: block;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    color: var(--muted);
    margin: 8px 0 4px;
    letter-spacing: 0.4px;
  }
  select, input[type="text"], textarea {
    width: 100%;
    background: var(--bg-input);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 9px 11px;
    font-size: 13px;
    font-family: inherit;
    transition: all 0.15s ease;
  }
  select:focus, input:focus, textarea:focus {
    outline: none;
    border-color: var(--cyan);
    box-shadow: 0 0 0 2px rgba(0, 229, 255, 0.15);
  }
  .preset-btn, .hist-item {
    display: block;
    width: 100%;
    text-align: left;
    background: rgba(15, 23, 42, 0.72);
    color: #e2e8f0;
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 12px;
    margin-bottom: 6px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .preset-btn:hover, .hist-item:hover {
    border-color: var(--cyan);
    background: rgba(0, 229, 255, 0.09);
    color: #fff;
  }
  .hist-meta {
    font-size: 10.5px;
    color: var(--muted);
    margin-top: 3px;
    font-family: 'JetBrains Mono', monospace;
  }
  .main-col {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .search-hero {
    background: linear-gradient(145deg, rgba(14, 22, 43, 0.92), rgba(9, 15, 30, 0.92));
    border: 1px solid rgba(0, 229, 255, 0.32);
    border-radius: 14px;
    padding: 16px 18px;
    box-shadow: 0 12px 38px rgba(0, 0, 0, 0.5), 0 0 24px rgba(0, 229, 255, 0.08);
  }
  .search-bar-row {
    display: flex;
    gap: 10px;
    align-items: stretch;
  }
  .search-input {
    flex: 1;
    font-size: 15px !important;
    padding: 13px 16px !important;
    border-radius: 10px !important;
    border: 1px solid rgba(56, 189, 248, 0.35) !important;
  }
  .run-btn {
    background: linear-gradient(135deg, var(--cyan), #0284c7);
    color: #030712;
    font-weight: 800;
    font-size: 13.5px;
    border: none;
    border-radius: 10px;
    padding: 0 22px;
    cursor: pointer;
    letter-spacing: 0.3px;
    box-shadow: 0 0 20px rgba(0, 229, 255, 0.32);
    transition: all 0.15s ease;
    white-space: nowrap;
  }
  .run-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 0 28px rgba(0, 229, 255, 0.55);
  }
  .run-btn:disabled {
    opacity: 0.55;
    cursor: wait;
  }
  /* Pipeline Stage Stepper */
  .pipeline-stepper {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
  @media (max-width: 850px) {
    .pipeline-stepper { grid-template-columns: 1fr; }
  }
  .stage-step {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 11px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 5px;
    transition: all 0.2s ease;
  }
  .stage-step.active {
    border-color: var(--cyan);
    background: rgba(0, 229, 255, 0.1);
    box-shadow: 0 0 20px rgba(0, 229, 255, 0.18);
  }
  .stage-step.done {
    border-color: rgba(16, 185, 129, 0.45);
    background: rgba(16, 185, 129, 0.08);
  }
  .stage-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11.5px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.6px;
  }
  .stage-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px;
    padding: 2px 8px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.9);
    color: var(--cyan);
    border: 1px solid var(--border);
  }
  .stage-step.done .stage-badge {
    color: var(--emerald);
    border-color: rgba(16, 185, 129, 0.4);
  }
  .stage-desc {
    font-size: 12px;
    color: #cbd5e1;
  }
  /* Source Cards Grid */
  .sources-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(265px, 1fr));
    gap: 11px;
  }
  .source-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 11px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 7px;
    transition: all 0.18s ease;
    position: relative;
  }
  .source-card:hover, .source-card.highlight {
    border-color: var(--cyan);
    background: var(--bg-card-hover);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0, 229, 255, 0.2);
  }
  .source-card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
  }
  .source-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 26px;
    height: 22px;
    padding: 0 7px;
    border-radius: 6px;
    background: linear-gradient(135deg, rgba(0, 229, 255, 0.22), rgba(56, 189, 248, 0.12));
    border: 1px solid var(--cyan);
    color: var(--cyan);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11.5px;
    font-weight: 800;
  }
  .source-method {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 5px;
    background: rgba(168, 85, 247, 0.16);
    color: #e9d5ff;
    border: 1px solid rgba(168, 85, 247, 0.35);
  }
  .source-title {
    color: #fff;
    font-size: 13px;
    font-weight: 700;
    text-decoration: none;
    line-height: 1.35;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .source-title:hover { color: var(--cyan); }
  .source-domain {
    font-size: 11px;
    color: var(--sky);
    font-family: 'JetBrains Mono', monospace;
  }
  .source-snippet {
    font-size: 11.5px;
    color: var(--muted);
    line-height: 1.45;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .source-foot {
    font-size: 10px;
    color: #64748b;
    font-family: 'JetBrains Mono', monospace;
    display: flex;
    justify-content: space-between;
    margin-top: auto;
    padding-top: 4px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
  }
  /* Synthesized Brief Card */
  .report-panel {
    background: rgba(9, 14, 28, 0.9);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 22px 26px;
    box-shadow: 0 14px 40px rgba(0, 0, 0, 0.55);
  }
  .report-meta-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
    padding-bottom: 14px;
    margin-bottom: 16px;
    border-bottom: 1px solid var(--border);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11.5px;
    color: #93c5fd;
  }
  details.think-box {
    background: rgba(88, 28, 135, 0.16);
    border: 1px solid rgba(168, 85, 247, 0.42);
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 16px;
  }
  details.think-box summary {
    cursor: pointer;
    font-weight: 700;
    font-size: 12.5px;
    color: #d8b4fe;
  }
  .think-content {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid rgba(168, 85, 247, 0.25);
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #cbd5e1;
    white-space: pre-wrap;
  }
  .report-body {
    font-size: 14.5px;
    line-height: 1.72;
    color: #e2e8f0;
  }
  .report-body h1, .report-body h2, .report-body h3 {
    color: #fff;
    margin-top: 22px;
    margin-bottom: 10px;
    font-weight: 800;
  }
  .report-body h2 {
    font-size: 18px;
    border-bottom: 1px solid rgba(56, 189, 248, 0.2);
    padding-bottom: 6px;
    color: var(--cyan);
  }
  .report-body h3 { font-size: 15.5px; color: #7dd3fc; }
  .report-body ul, .report-body ol { padding-left: 22px; }
  .report-body li { margin-bottom: 7px; }
  .report-body code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12.5px;
    background: rgba(15, 23, 42, 0.9);
    border: 1px solid rgba(56, 189, 248, 0.25);
    padding: 2px 6px;
    border-radius: 5px;
    color: #7dd3fc;
  }
  .report-body pre {
    background: #03060d;
    border: 1px solid rgba(56, 189, 248, 0.3);
    border-radius: 9px;
    padding: 14px;
    overflow-x: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12.5px;
    line-height: 1.55;
    color: #e2e8f0;
  }
  .report-body pre code {
    background: transparent;
    border: none;
    padding: 0;
    color: inherit;
  }
  .cite-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 1px 7px;
    margin: 0 2px;
    border-radius: 999px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 800;
    background: rgba(0, 229, 255, 0.16);
    color: var(--cyan);
    border: 1px solid rgba(0, 229, 255, 0.45);
    text-decoration: none;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .cite-pill:hover {
    background: var(--cyan);
    color: #030712;
    box-shadow: 0 0 12px rgba(0, 229, 255, 0.6);
  }
</style>
</head>
<body>
<header>
  <div class="brand">
    <div class="brand-icon">R</div>
    <div>
      <div class="brand-title">Boylenet Deep Research &amp; Dual-Oracle Citation Studio (:4094)</div>
      <div class="brand-sub">Stage 1: SearXNG (:8888) &bull; Stage 2: Dual-Oracle CDP (.137 + .181) + Qdrant (.125:6333) &bull; Stage 3: Cited Multi-Engine Synthesis</div>
    </div>
  </div>
  <div class="telemetry-bar" id="telemetryBar">
    <span class="status-pill"><span class="dot"></span>SearXNG :8888 JSON</span>
    <span class="status-pill"><span class="dot"></span>BattleStation .137:9222</span>
    <span class="status-pill"><span class="dot"></span>Bittorrent .181:9222</span>
    <span class="status-pill"><span class="dot"></span>Qdrant .125:6333</span>
    <span class="status-pill"><span class="dot"></span>4xT4 .228:4000</span>
  </div>
  <div class="nav-links">
    <a href="http://dashy.boylenet.themfboyles.org" target="_blank">Dashy (:4080)</a>
    <a href="http://harnesses.boylenet.themfboyles.org" target="_blank">Harnesses (:4098)</a>
    <a href="http://searxng.boylenet.themfboyles.org" target="_blank">SearXNG (:8888)</a>
    <a href="http://qdrant.boylenet.themfboyles.org" target="_blank">Qdrant (:6333)</a>
    <a href="http://jarvis.boylenet.themfboyles.org" target="_blank">Cockpit (:3002)</a>
  </div>
</header>

<div class="layout">
  <aside class="sidebar">
    <div class="glass-panel">
      <div class="panel-hdr">
        <span>Synthesis &amp; Extraction Controls</span>
        <span>:4094</span>
      </div>
      <label for="engineSelect">Stage 3 Synthesis Engine</label>
      <select id="engineSelect">
        <option value="qwen3-coder-30b-a3b">Local 4xT4 Qwen3-Coder-30B-A3B (.228:4000/v1)</option>
        <option value="deepseek-think">DeepSeek &lt;think&gt; Reasoning (V4-Flash / R1)</option>
        <option value="tier2-deepseek-r1-70b">Local 4xT4 DeepSeek-R1-70B &lt;think&gt;</option>
        <option value="claude-a">Claude Pool A (Sonnet 4.6 / Opus 4.7)</option>
        <option value="claude-b">Claude Pool B (Sonnet 4.6 / Opus 4.7)</option>
        <option value="claude-c">Claude Pool C (Sonnet 4.6 / Opus 4.7)</option>
        <option value="claude-d">Claude Pool D (Sonnet 4.6 / Opus 4.7)</option>
        <option value="codex">OpenAI Codex Flagship (gpt-6-sol)</option>
        <option value="kimi">Kimi Code CLI (kimi-for-coding)</option>
      </select>

      <label for="cdpSelect">Stage 2 Dual-Oracle CDP Mode</label>
      <select id="cdpSelect">
        <option value="auto">Auto (Fast HTTP + Dual-Oracle CDP Fallback)</option>
        <option value="always">Force Dual-Oracle Live Browser (.137 + .181)</option>
        <option value="off">HTTP Fast-Fetch Only</option>
      </select>

      <label for="topNSelect">Top Web Sources (N) + Qdrant KB</label>
      <select id="topNSelect">
        <option value="5" selected>Top 5 Web URLs + 2 Qdrant KB Chunks</option>
        <option value="3">Top 3 Web URLs + 2 Qdrant KB Chunks</option>
        <option value="8">Top 8 Web URLs + 2 Qdrant KB Chunks</option>
      </select>
    </div>

    <div class="glass-panel">
      <div class="panel-hdr">
        <span>1-Click Deep Research Presets</span>
      </div>
      <button class="preset-btn" onclick="runPreset('AVX-512 MoE inference optimization Xeon Skylake')">
        AVX-512 MoE inference optimization Xeon Skylake
      </button>
      <button class="preset-btn" onclick="runPreset('llama.cpp RPC multi-node tensor split Tesla T4 optimization')">
        llama.cpp RPC multi-node tensor split Tesla T4 optimization
      </button>
      <button class="preset-btn" onclick="runPreset('Qdrant HNSW quantization vector search tuning high throughput')">
        Qdrant HNSW quantization vector search tuning high throughput
      </button>
      <button class="preset-btn" onclick="runPreset('Chrome DevTools Protocol headless DOM extraction anti-bot patterns')">
        Chrome DevTools Protocol headless DOM extraction patterns
      </button>
    </div>

    <div class="glass-panel" style="flex:1">
      <div class="panel-hdr">
        <span>Recent Cited Research Runs</span>
        <span id="histCount">0</span>
      </div>
      <div id="historyList"></div>
    </div>
  </aside>

  <main class="main-col">
    <div class="search-hero">
      <div class="search-bar-row">
        <input type="text" id="queryInput" class="search-input"
          value="AVX-512 MoE inference optimization Xeon Skylake"
          placeholder="Ask any deep technical question... (SearXNG :8888 -> Dual-Oracle CDP -> Cited Synthesis)"
          onkeydown="if(event.key==='Enter') startResearch();" />
        <button class="run-btn" id="runBtn" onclick="startResearch()">Run Deep Research &rarr;</button>
      </div>
    </div>

    <!-- 3-Stage Live Pipeline Stepper -->
    <div class="pipeline-stepper">
      <div class="stage-step" id="step1Card">
        <div class="stage-top">
          <span>Stage 1 &bull; Searching SearXNG :8888</span>
          <span class="stage-badge" id="step1Badge">READY</span>
        </div>
        <div class="stage-desc" id="step1Desc">Meta-search fanout via http://10.0.70.164:8888/search?format=json (&lt;500ms)</div>
      </div>

      <div class="stage-step" id="step2Card">
        <div class="stage-top">
          <span>Stage 2 &bull; Extracting Sources via Dual-Oracle</span>
          <span class="stage-badge" id="step2Badge">READY</span>
        </div>
        <div class="stage-desc" id="step2Desc">BattleStation (.137:9222) + Bittorrent (.181:9222) + HTTP Fast-Fetch + Qdrant (.125:6333)</div>
      </div>

      <div class="stage-step" id="step3Card">
        <div class="stage-top">
          <span>Stage 3 &bull; Synthesizing Cited Brief</span>
          <span class="stage-badge" id="step3Badge">READY</span>
        </div>
        <div class="stage-desc" id="step3Desc">Inline numbered citations ([1], [2], ...) &amp; verified source ledger</div>
      </div>
    </div>

    <!-- Extracted Grounded Sources Grid -->
    <div class="glass-panel">
      <div class="panel-hdr">
        <span>Grounded Web &amp; Qdrant Sources (Clickable Citation Cards)</span>
        <span id="sourcesSummaryBadge">0 sources</span>
      </div>
      <div class="sources-grid" id="sourcesGrid"></div>
    </div>

    <!-- Synthesized Technical Report -->
    <div class="report-panel">
      <div class="report-meta-bar" id="reportMetaBar">
        <span id="reportEngineInfo">Engine: Local 4xT4 Qwen3-Coder-30B-A3B (.228:4000/v1)</span>
        <span id="reportTimingInfo">Awaiting query or loading latest cached research run...</span>
      </div>
      <details class="think-box" id="thinkBox" style="display:none">
        <summary>&lt;think&gt; DeepSeek / Reasoning Trace</summary>
        <div class="think-content" id="thinkContent"></div>
      </details>
      <div class="report-body" id="reportBody"></div>
    </div>
  </main>
</div>

<script>
let currentSources = [];
let historyRecords = [];

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function setStageState(stageNum, state, badgeText, descText) {
  const card = document.getElementById('step' + stageNum + 'Card');
  const badge = document.getElementById('step' + stageNum + 'Badge');
  const desc = document.getElementById('step' + stageNum + 'Desc');
  card.className = 'stage-step' + (state ? ' ' + state : '');
  if (badgeText) badge.textContent = badgeText;
  if (descText) desc.textContent = descText;
}

function highlightSourceCard(id) {
  document.querySelectorAll('.source-card').forEach(el => el.classList.remove('highlight'));
  const target = document.getElementById('source-card-' + id);
  if (target) {
    target.classList.add('highlight');
    target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function renderSourcesGrid(sources) {
  currentSources = sources || [];
  const grid = document.getElementById('sourcesGrid');
  document.getElementById('sourcesSummaryBadge').textContent = currentSources.length + ' grounded sources';
  if (!currentSources.length) {
    grid.innerHTML = '<div style="color:var(--muted);font-size:12.5px;">No sources extracted yet.</div>';
    return;
  }
  grid.innerHTML = currentSources.map(s => `
    <div class="source-card" id="source-card-${s.id}">
      <div class="source-card-top">
        <span class="source-num">[${s.id}]</span>
        <span class="source-method">${escapeHtml(s.fetch_method)}</span>
      </div>
      <a class="source-title" href="${escapeHtml(s.url)}" target="_blank" rel="noopener">${escapeHtml(s.title)}</a>
      <div class="source-domain">${escapeHtml(s.domain)}</div>
      <div class="source-snippet">${escapeHtml((s.searxng_snippet || s.excerpt || '').slice(0, 240))}</div>
      <div class="source-foot">
        <span>${s.chars || 0} chars</span>
        <span>sha256:${escapeHtml(s.sha256 || '')}</span>
      </div>
    </div>
  `).join('');
}

function renderMarkdownWithCitations(md, sources) {
  if (!md) return '';
  const srcMap = {};
  (sources || []).forEach(s => { srcMap[s.id] = s; });

  // Extract fenced code blocks first
  const codeBlocks = [];
  let text = String(md).replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push(`<pre><code>${escapeHtml(code.trim())}</code></pre>`);
    return `@@CODEBLOCK_${idx}@@`;
  });

  text = escapeHtml(text);

  // Inline code
  text = text.replace(/`([^`\n]+)`/g, '<code>$1</code>');

  // Headings
  text = text.replace(/^### (.*)$/gm, '<h3>$1</h3>');
  text = text.replace(/^## (.*)$/gm, '<h2>$1</h2>');
  text = text.replace(/^# (.*)$/gm, '<h1>$1</h1>');

  // Bold & italic
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');

  // Markdown links [title](url)
  text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" style="color:var(--cyan)">$1</a>');

  // Inline numbered citations [1], [2], etc.
  text = text.replace(/\[(\d+)\]/g, (full, numStr) => {
    const num = parseInt(numStr, 10);
    const s = srcMap[num];
    const url = s ? escapeHtml(s.url) : '#source-card-' + num;
    const title = s ? escapeHtml(s.title + ' (' + s.domain + ')') : 'Source ' + num;
    return `<a class="cite-pill" href="${url}" target="_blank" title="${title}" onmouseenter="highlightSourceCard(${num})">[${num}]</a>`;
  });

  // Bullet lists & paragraphs
  const lines = text.split('\n');
  const out = [];
  let inList = false;
  for (const ln of lines) {
    const trimmed = ln.trim();
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (!inList) { out.push('<ul>'); inList = true; }
      out.push('<li>' + trimmed.slice(2) + '</li>');
    } else {
      if (inList) { out.push('</ul>'); inList = false; }
      if (trimmed === '---') {
        out.push('<hr style="border:none;border-top:1px solid var(--border);margin:18px 0">');
      } else if (trimmed.startsWith('<h') || trimmed.startsWith('@@CODEBLOCK_')) {
        out.push(trimmed);
      } else if (trimmed) {
        out.push('<p style="margin:0 0 11px">' + trimmed + '</p>');
      }
    }
  }
  if (inList) out.push('</ul>');

  let finalHtml = out.join('\n');
  codeBlocks.forEach((cb, i) => {
    finalHtml = finalHtml.replace(`@@CODEBLOCK_${i}@@`, cb);
  });
  return finalHtml;
}

function displayFullRecord(rec) {
  if (!rec) return;
  document.getElementById('queryInput').value = rec.query || '';
  const s1 = rec.stage1_searxng || {};
  const s2 = rec.stage2_extraction || {};
  const s3 = rec.stage3_synthesis || {};

  setStageState(1, 'done', (s1.elapsed_ms || 0) + ' ms',
    `Found ${s1.selected_count || 0} URLs via SearXNG (${s1.mode || 'json'})`);
  setStageState(2, 'done', (s2.elapsed_ms || 0) + ' ms',
    `Extracted ${s2.sources_count || 0} sources (Dual-Oracle .137 + .181 & Qdrant .125:6333)`);
  setStageState(3, 'done', (s3.elapsed_s || 0) + ' s',
    `Synthesized with ${(rec.citations_used || []).length} inline citations via ${s3.model_used || rec.engine}`);

  renderSourcesGrid(rec.sources || []);

  document.getElementById('reportEngineInfo').textContent =
    `Engine: ${s3.engine_label || rec.engine} | Model: ${s3.model_used || rec.engine}`;
  document.getElementById('reportTimingInfo').textContent =
    `Total: ${rec.total_elapsed_s || 0}s (SearXNG ${s1.elapsed_ms || 0}ms | Extraction ${s2.elapsed_ms || 0}ms | Synthesis ${s3.elapsed_s || 0}s) | Citations: [${(rec.citations_used || []).join(', ')}]`;

  const thinkBox = document.getElementById('thinkBox');
  const thinkContent = document.getElementById('thinkContent');
  if (s3.reasoning) {
    thinkBox.style.display = 'block';
    thinkContent.textContent = s3.reasoning;
  } else {
    thinkBox.style.display = 'none';
  }

  document.getElementById('reportBody').innerHTML =
    renderMarkdownWithCitations(rec.report || s3.full_report || '', rec.sources || []);
}

function runPreset(q) {
  document.getElementById('queryInput').value = q;
  startResearch();
}

async function startResearch() {
  const query = document.getElementById('queryInput').value.trim();
  if (!query) return;
  const engine = document.getElementById('engineSelect').value;
  const cdp = document.getElementById('cdpSelect').value;
  const topN = parseInt(document.getElementById('topNSelect').value, 10) || 5;

  const btn = document.getElementById('runBtn');
  btn.disabled = true;
  btn.textContent = 'Researching...';

  setStageState(1, 'active', 'RUNNING', 'Querying SearXNG :8888 JSON endpoint...');
  setStageState(2, '', 'WAITING', 'Waiting for Stage 1 URLs...');
  setStageState(3, '', 'WAITING', 'Waiting for Stage 2 grounded sources...');
  document.getElementById('reportBody').innerHTML =
    '<div style="color:var(--cyan);font-family:monospace;">Executing 3-Stage Deep-Web &amp; Dual-Oracle Research Pipeline...</div>';

  const url = `/api/research-stream?q=${encodeURIComponent(query)}&engine=${encodeURIComponent(engine)}&top_n=${topN}&cdp=${encodeURIComponent(cdp)}`;
  const es = new EventSource(url);

  es.addEventListener('stage1_done', (e) => {
    const s1 = JSON.parse(e.data);
    setStageState(1, 'done', s1.elapsed_ms + ' ms',
      `Discovered ${s1.selected_count} web URLs via ${s1.mode}`);
    setStageState(2, 'active', 'EXTRACTING',
      'Fetching clean text via Dual-Oracle (.137 + .181), HTTP & Qdrant (.125:6333)...');
  });

  es.addEventListener('stage2_done', (e) => {
    const s2 = JSON.parse(e.data);
    setStageState(2, 'done', s2.elapsed_ms + ' ms',
      `Extracted ${s2.sources_count} grounded sources (Web + Qdrant KB)`);
    renderSourcesGrid(s2.sources || []);
    setStageState(3, 'active', 'SYNTHESIZING',
      `Synthesizing cited report via ${engine}...`);
  });

  es.addEventListener('complete', (e) => {
    const rec = JSON.parse(e.data);
    displayFullRecord(rec);
    es.close();
    btn.disabled = false;
    btn.textContent = 'Run Deep Research →';
    refreshHistory();
  });

  es.onerror = async () => {
    es.close();
    try {
      const resp = await fetch('/api/research', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query, engine, top_n: topN, cdp_mode: cdp})
      });
      const rec = await resp.json();
      displayFullRecord(rec);
      refreshHistory();
    } catch (err) {
      document.getElementById('reportBody').innerHTML =
        `<div style="color:var(--rose)">Error: ${escapeHtml(err.message)}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = 'Run Deep Research →';
    }
  };
}

async function refreshHistory() {
  try {
    const r = await fetch('/api/history');
    const d = await r.json();
    historyRecords = d.history || [];
    document.getElementById('histCount').textContent = historyRecords.length;
    const list = document.getElementById('historyList');
    list.innerHTML = historyRecords.map((h, idx) => `
      <button class="hist-item" onclick="displayFullRecord(historyRecords[${idx}])">
        <div style="font-weight:700">${escapeHtml(h.query)}</div>
        <div class="hist-meta">${escapeHtml(h.engine)} &bull; ${(h.sources || []).length} sources &bull; ${h.total_elapsed_s}s</div>
      </button>
    `).join('');
    if (historyRecords.length > 0 && !currentSources.length) {
      displayFullRecord(historyRecords[0]);
    }
  } catch (e) {}
}

async function refreshStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const pills = [];
    if (d.searxng) {
      pills.push(`<span class="status-pill ${d.searxng.online ? '' : 'warn'}"><span class="dot"></span>SearXNG :8888 (${d.searxng.latency_ms || 0}ms)</span>`);
    }
    (d.oracles || []).forEach(o => {
      pills.push(`<span class="status-pill ${o.online ? '' : 'warn'}"><span class="dot"></span>${escapeHtml(o.name)} ${escapeHtml(o.addr)} (${o.latency_ms}ms)</span>`);
    });
    if (d.qdrant) {
      pills.push(`<span class="status-pill ${d.qdrant.online ? '' : 'warn'}"><span class="dot"></span>Qdrant .125:6333 (${(d.qdrant.collections || []).length} cols)</span>`);
    }
    pills.push(`<span class="status-pill"><span class="dot"></span>4xT4 .228:4000</span>`);
    document.getElementById('telemetryBar').innerHTML = pills.join('');
  } catch (e) {}
}

window.addEventListener('DOMContentLoaded', () => {
  refreshStatus();
  refreshHistory();
});
</script>
</body>
</html>
"""


class StudioHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _send_json(self, obj: Dict[str, Any], code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
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
        if parsed.path in ("/health", "/api/status"):
            self._send_json(get_cluster_status())
            return
        if parsed.path == "/api/history":
            self._send_json({"status": "ok", "history": load_history()})
            return
        if parsed.path == "/api/research-stream":
            qs = urllib.parse.parse_qs(parsed.query)
            query = (qs.get("q") or [""])[0].strip()
            engine = (qs.get("engine") or ["qwen3-coder-30b-a3b"])[0].strip()
            top_n = int((qs.get("top_n") or ["5"])[0])
            cdp_mode = (qs.get("cdp") or ["auto"])[0].strip()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            def _emit(event: str, payload: Dict[str, Any]) -> None:
                try:
                    msg = f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    pass

            rec = ENGINE.run_deep_research_pipeline(
                query=query,
                engine=engine,
                top_n=top_n,
                cdp_mode=cdp_mode,
                include_qdrant=True,
                on_stage=_emit,
            )
            save_to_history(rec)
            _emit("complete", rec)
            return
        body = HTML_STUDIO.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = (
            self.rfile.read(length).decode("utf-8", errors="replace")
            if length > 0
            else "{}"
        )
        data = json.loads(raw or "{}")
        if self.path == "/api/research":
            query = str(data.get("query") or "").strip()
            if not query:
                self._send_json({"status": "error", "error": "missing query"}, 400)
                return
            engine = str(data.get("engine") or "qwen3-coder-30b-a3b").strip()
            top_n = int(data.get("top_n") or 5)
            cdp_mode = str(data.get("cdp_mode") or "auto").strip()
            include_qdrant = bool(data.get("include_qdrant", True))
            rec = ENGINE.run_deep_research_pipeline(
                query=query,
                engine=engine,
                top_n=top_n,
                cdp_mode=cdp_mode,
                include_qdrant=include_qdrant,
            )
            save_to_history(rec)
            self._send_json(rec)
            return
        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), StudioHandler)
    print(
        f"Boylenet Deep Research & Dual-Oracle Studio listening on 0.0.0.0:{PORT}",
        flush=True,
    )
    srv.serve_forever()
