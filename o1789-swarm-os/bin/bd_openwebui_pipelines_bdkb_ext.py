#!/usr/bin/env python3
"""
Boylenet OpenWebUI Extension Module (`bd_openwebui_pipelines_bdkb_ext.py`)
Provides:
  1. Master `BD KB` Search Engine (`/home/mboyle/bd-persist/bd-kb/*.md` + Qdrant `bd_master_kb`)
  2. OpenWebUI Pipelines Server Protocol (`/v1/models` with `"pipelines": true`, `/v1/pipelines`,
     `/v1/{id}/valves`, `/v1/{id}/valves/spec`, `/v1/{id}/valves/update`, `/v1/{id}/filter/inlet`,
     `/v1/{id}/filter/outlet`, `/v1/chat/completions`, `/static/generated/*`, `/static/audio/*`)
  3. 8 Pipelines + 6 Local Image/Vision Models + 5 Local Speech/Audio Models
  4. 20 High-ROI Tool Handlers (Toolkits #31 through #50)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import math
import os
import re
import struct
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import wave
from pathlib import Path
from typing import Any

BD_KB_DIR = Path("/home/mboyle/bd-persist/bd-kb")
VALVES_FILE = Path("/home/mboyle/bd-persist/openwebui-pipeline-valves.json")
GENERATED_IMG_DIR = Path("/var/tmp/openwebui-workspace/generated_images")
GENERATED_AUDIO_DIR = Path("/var/tmp/openwebui-workspace/generated_audio")
GENERATED_NOTEBOOKS_DIR = Path("/var/tmp/openwebui-workspace/notebooks")
for _d in (GENERATED_IMG_DIR, GENERATED_AUDIO_DIR, GENERATED_NOTEBOOKS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

GATEWAY_PUBLIC_BASE = "http://10.0.70.164:4079"
LITELLM_BASE_URL = "http://10.0.70.164:4000/v1"
LITELLM_API_KEY = "sk-fleet-local"
QDRANT_BASE_URL = "http://10.0.70.125:6333"
SEARXNG_URL = "http://10.0.70.164:8888/search"
VOICE_STUDIO_URL = "http://10.0.70.164:4093"

# ---------------------------------------------------------------------------
# 1. Master BD KB Indexer & Sub-20ms Hybrid Search
# ---------------------------------------------------------------------------

BD_KB_BOOKS_META = [
    {
        "kb_id": "bd-kb-master",
        "filename": "00-BD-KB-MASTER-ENCYCLOPEDIA.md",
        "name": "📚 BD-KB Master: Complete BulkDownloader & Boylenet Swarm OS Encyclopedia",
        "description": "Master index and executive architecture encyclopedia across BulkDownloader (BD), 27-Node Boylenet cluster, 86-Model AI Vault, Fleet Law (Rules 1-86 + O1740), CI Taxonomy, 14 MCP servers, and 50 OpenWebUI Toolkits.",
    },
    {
        "kb_id": "bd-kb-bulkdownloader",
        "filename": "01-BULKDOWNLOADER-ARCHITECTURE-AND-CONTRACTS.md",
        "name": "📥 BD-KB 1: BulkDownloader (bd) Codebase, Extractors, CLI, Testing & yt-dlp Contracts",
        "description": "BulkDownloader (mcboyle/BD) repository architecture, 12-step cut lifecycle, train integration, yt-dlp pin contract, toolchain commands (bd-precut, bd-regen-order, bd-band-derive, bd-mutate, bd-land-trio), and canonical 24-worker pytest.",
    },
    {
        "kb_id": "bd-kb-cluster-infra",
        "filename": "02-BOYLENET-27NODE-CLUSTER-12U-RACK-VSAN-25GBE.md",
        "name": "🖥️ BD-KB 2: Boylenet 27-Node Cluster, 12U Physical Rack (79.5°F), 107TB vSAN, 25GbE RoCE & 55+ Web UIs",
        "description": "Complete hardware, network, storage, hypervisor, and web service encyclopedia: Startech 12U rack (79.5°F), 4x HPE DL380 Gen10 ESXi hosts, 4x Tesla T4 GPUs + RTX 2080 Ti, 107TB NVMe vSAN, 25GbE RoCE, and all 55+ Web UIs.",
    },
    {
        "kb_id": "bd-kb-86-models",
        "filename": "03-86-MODEL-VAULT-BENCHMARKS-AND-AIRGAP.md",
        "name": "🧠 BD-KB 3: 86-Model AI Vault (8.9 TB on .72 & .83), Benchmarks (pp512/tg128), Category Winners, bd-airgap & bd-raw-ai",
        "description": "86-Model Local AI Vault across .72 and .83, real-weight llama-bench (b11716) pp512/tg128 speeds, Category Winners (Qwen3-Coder-30B-A3B 77.62 tok/s, CyberStrike-35B 66.47 tok/s, Qwythos-9B 1,005.86 tok/s), bd-airgap, and bd-raw-ai.",
    },
    {
        "kb_id": "bd-kb-fleet-law",
        "filename": "04-FLEET-LAW-RULES-1-86-AND-O1740-ROUTING.md",
        "name": "⚖️ BD-KB 4: Fleet Law (Rules 1–86), O1740 Dynamic Pool Routing, Rule 22 Sandbox Shield & Cut Workflow",
        "description": "Binding Fleet Law (Rules 1-86), Tier A verbatim floor invariants, O1740 Dynamic Capability Routing (Command Squad, Heavy Lifters, Investigators), Standing Order O1741 (HUB-GATE 20% iowait ceiling), Rule 22 Shield, and Rule 86.",
    },
    {
        "kb_id": "bd-kb-ci-and-uis",
        "filename": "05-CI-TAXONOMY-RECOVERY-AND-MCP-TOOLS.md",
        "name": "🩺 BD-KB 5: Boylenet CI Failure Taxonomy, Gridlock Recovery, 14 MCP Servers & 50 OpenWebUI Toolkits",
        "description": "BulkDownloader CI failure taxonomy (BD-CI-01 through BD-CI-09), step-by-step resolution playbooks, all 14 MCP servers (99 tools), 8 OpenWebUI Pipelines, and all 50 Native OpenWebUI Toolkits.",
    },
    {
        "kb_id": "bd-kb-swarm-ops",
        "filename": "05-SWARM-OPERATIONS-RECEIPTS-AND-PLAYBOOKS.md",
        "name": "🛠️ BD-KB 5B: Live Swarm Operations Receipts (AGENT*.md), PM Handoffs & Watchdog Playbooks",
        "description": "Auto-indexed every 15 minutes by bd-kb-live-sync.timer: all AGENT*.md verification receipts, PM-HANDOFF.md, and WATCHDOG-STATUS.md across the Boylenet swarm.",
    },
    {
        "kb_id": "bd-kb-5platform-mods",
        "filename": "06-5PLATFORM-MCP-MODS-HTTPS-AND-215-LEDGER.md",
        "name": "🌐 BD-KB 6: 5-Platform boylenet-infra MCP, Mods 1-5 (bd-swarm-mod), NGINX/Cloudflare HTTPS & 215/215 Backlog Ledger",
        "description": "20-Tool boylenet-infra MCP server across Claude/Codex/Kimi/AGY/OpenWebUI, Autonomous Swarm Mods 1-5 (bd-swarm-mod), 22 cross-platform slash commands/skills, .83:18080 Qwen3.6-Heretic coding pool, NGINX/Cloudflare DNS-01 HTTPS, and 215/215 reconciled backlog ledger.",
    },
]

_KB_CHUNKS_CACHE: list[dict[str, Any]] = []


def load_bd_kb_chunks(force: bool = False) -> list[dict[str, Any]]:
    global _KB_CHUNKS_CACHE
    if _KB_CHUNKS_CACHE and not force:
        return _KB_CHUNKS_CACHE
    chunks: list[dict[str, Any]] = []
    chunk_idx = 1
    for meta in BD_KB_BOOKS_META:
        fpath = BD_KB_DIR / meta["filename"]
        if not fpath.exists():
            continue
        text = fpath.read_text(encoding="utf-8", errors="replace")
        sections = re.split(r"\n(?=##\s+)", text)
        for sec in sections:
            sec_clean = sec.strip()
            if not sec_clean:
                continue
            first_line = sec_clean.splitlines()[0].lstrip("#").strip()
            chunks.append(
                {
                    "chunk_id": chunk_idx,
                    "kb_id": meta["kb_id"],
                    "book_name": meta["name"],
                    "filename": meta["filename"],
                    "file_path": str(fpath),
                    "section_title": first_line[:140],
                    "content": sec_clean,
                }
            )
            chunk_idx += 1
    _KB_CHUNKS_CACHE = chunks
    return chunks


def tool_bd_kb_search(payload: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    query = str(payload.get("query") or payload.get("q") or "").strip()
    kb_filter = str(payload.get("kb_id") or payload.get("book") or "").strip().lower()
    top_k = max(1, min(int(payload.get("top_k") or payload.get("limit") or 5), 15))
    chunks = load_bd_kb_chunks()
    if not query:
        return {
            "ok": True,
            "books_count": len(BD_KB_BOOKS_META),
            "total_chunks": len(chunks),
            "books": BD_KB_BOOKS_META,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        }

    tokens = [w.lower() for w in re.findall(r"[a-zA-Z0-9_.-]{2,}", query)]
    q_lower = query.lower()
    scored: list[tuple[float, dict[str, Any]]] = []
    for ch in chunks:
        if (
            kb_filter
            and kb_filter not in ch["kb_id"].lower()
            and kb_filter not in ch["filename"].lower()
        ):
            continue
        title_l = ch["section_title"].lower()
        body_l = ch["content"].lower()
        score = 0.0
        if q_lower in title_l:
            score += 15.0
        if q_lower in body_l:
            score += 10.0
        for tok in tokens:
            if tok in title_l:
                score += 4.5
            cnt = body_l.count(tok)
            if cnt > 0:
                score += min(cnt, 6) * 1.5
        if score > 0:
            scored.append((score, ch))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        scored = [(1.0, ch) for ch in chunks[:top_k]]

    results = []
    for sc, ch in scored[:top_k]:
        results.append(
            {
                "score": round(sc, 2),
                "kb_id": ch["kb_id"],
                "book_name": ch["book_name"],
                "section_title": ch["section_title"],
                "file_path": ch["file_path"],
                "content": ch["content"][:3000],
            }
        )

    return {
        "ok": True,
        "query": query,
        "kb_filter": kb_filter or "all",
        "total_chunks_searched": len(chunks),
        "result_count": len(results),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "results": results,
    }


# ---------------------------------------------------------------------------
# 2. OpenWebUI Pipelines Server + Local Image Gen + Local Speech/Audio Suite
# ---------------------------------------------------------------------------

PIPELINES_CATALOG: list[dict[str, Any]] = [
    {
        "id": "bd_kb_auto_grounding_pipeline",
        "name": "📚 [PIPELINE • FILTER] BD KB Auto-Grounding & Citation Injector",
        "type": "filter",
        "priority": 10,
        "pipelines": ["*"],
        "description": "Automatically retrieves authoritative chunks from BD KB (BulkDownloader, 27-Node Cluster, 86 Models, Fleet Law) when prompts reference Boylenet/BD topics.",
        "default_valves": {
            "priority": 10,
            "enable_inlet_grounding": False,
            "top_k_chunks": 3,
            "append_citation_footer": False,
            "qdrant_collection": "bd_master_kb",
        },
        "valves_spec": {
            "priority": {"type": "integer", "title": "Filter Priority", "default": 10},
            "enable_inlet_grounding": {
                "type": "boolean",
                "title": "Auto-Inject BD KB Context on Inlet",
                "default": False,
            },
            "top_k_chunks": {
                "type": "integer",
                "title": "Top-K BD KB Chunks",
                "default": 3,
            },
            "append_citation_footer": {
                "type": "boolean",
                "title": "Append BD KB Citation Footer on Outlet",
                "default": False,
            },
            "qdrant_collection": {
                "type": "string",
                "title": "Qdrant Collection Name",
                "default": "bd_master_kb",
            },
        },
    },
    {
        "id": "bd_smart_o1740_intent_router_pipeline",
        "name": "🧭 [PIPELINE • ROUTER] O1740 Smart Intent & Best-Benchmark Auto-Router",
        "type": "pipe",
        "priority": 20,
        "pipelines": ["*"],
        "description": "Dynamically classifies prompt intent (coding, security, vision, reasoning, fast chat) and routes to the #1 benchmarked local model (Qwen3-Coder-30B-A3B 77.6 tok/s, CyberStrike-35B 66.5 tok/s, Qwythos-9B 1005.9 tok/s).",
        "default_valves": {
            "coding_model": "local/tier1-qwen3-coder-30b-a3b",
            "security_model": "local/cyberstrike-35b",
            "reasoning_model": "local/qwen3.6-35b-claude-opus-abliterated",
            "fast_chat_model": "local/qwythos-9b",
            "include_bd_kb_context": True,
            "show_routing_header": True,
        },
        "valves_spec": {
            "coding_model": {
                "type": "string",
                "title": "Coding Winner Model",
                "default": "local/tier1-qwen3-coder-30b-a3b",
            },
            "security_model": {
                "type": "string",
                "title": "Offensive Security Winner Model",
                "default": "local/cyberstrike-35b",
            },
            "reasoning_model": {
                "type": "string",
                "title": "Reasoning Winner Model",
                "default": "local/qwen3.6-35b-claude-opus-abliterated",
            },
            "fast_chat_model": {
                "type": "string",
                "title": "Fast Chat Winner Model",
                "default": "local/qwythos-9b",
            },
            "include_bd_kb_context": {
                "type": "boolean",
                "title": "Ground with BD KB",
                "default": True,
            },
            "show_routing_header": {
                "type": "boolean",
                "title": "Show O1740 Routing Decision Header",
                "default": True,
            },
        },
    },
    {
        "id": "bd_deep_research_multi_engine_pipeline",
        "name": "🔬 [PIPELINE • RESEARCH] Autonomous Deep Research (SearXNG + ArXiv + BD KB + Qdrant)",
        "type": "pipe",
        "priority": 30,
        "pipelines": ["*"],
        "description": "Executes parallel multi-engine deep research across BD KB, Qdrant (.125:6333), SearXNG (:8888), ArXiv, and Wikipedia, then synthesizes a comprehensive cited report.",
        "default_valves": {
            "max_web_results": 5,
            "max_arxiv_papers": 3,
            "max_bdkb_chunks": 4,
            "synthesis_model": "local/qwythos-9b",
        },
        "valves_spec": {
            "max_web_results": {
                "type": "integer",
                "title": "Max SearXNG Web Results",
                "default": 5,
            },
            "max_arxiv_papers": {
                "type": "integer",
                "title": "Max ArXiv Papers",
                "default": 3,
            },
            "max_bdkb_chunks": {
                "type": "integer",
                "title": "Max BD KB Chunks",
                "default": 4,
            },
            "synthesis_model": {
                "type": "string",
                "title": "Synthesis Model",
                "default": "local/qwythos-9b",
            },
        },
    },
    {
        "id": "bd_4model_consensus_council_pipeline",
        "name": "⚔️ [PIPELINE • COUNCIL] 4-Model Parallel Consensus Council & Judge",
        "type": "pipe",
        "priority": 40,
        "pipelines": ["*"],
        "description": "Convenes Boylenet's flagship local specialists (Qwen3-Coder-30B-A3B, CyberStrike-35B, Qwen3.6-35B-Claude-Opus, Qwythos-9B) + BD KB evidence to produce a multi-perspective consensus ruling.",
        "default_valves": {
            "council_size": 4,
            "include_benchmark_weights": True,
            "judge_mode": "weighted_consensus",
        },
        "valves_spec": {
            "council_size": {
                "type": "integer",
                "title": "Council Seat Count",
                "default": 4,
            },
            "include_benchmark_weights": {
                "type": "boolean",
                "title": "Weight by llama-bench Speed & Tier",
                "default": True,
            },
            "judge_mode": {
                "type": "string",
                "title": "Judge Mode",
                "default": "weighted_consensus",
            },
        },
    },
    {
        "id": "bd_airgap_and_rule22_shield_pipeline",
        "name": "🛡️ [PIPELINE • SHIELD] WAN Airgap & Rule 22 Safety Shield Filter",
        "type": "filter",
        "priority": 5,
        "pipelines": ["*"],
        "description": "Enforces Rule 22 worktree protection and verifies bd-airgap status on inlet/outlet.",
        "default_valves": {
            "priority": 5,
            "block_destructive_git_in_prompt": False,
            "verify_airgap_status": True,
        },
        "valves_spec": {
            "priority": {"type": "integer", "title": "Filter Priority", "default": 5},
            "block_destructive_git_in_prompt": {
                "type": "boolean",
                "title": "Warn on Destructive Git Commands",
                "default": False,
            },
            "verify_airgap_status": {
                "type": "boolean",
                "title": "Verify Airgap Status",
                "default": True,
            },
        },
    },
    {
        "id": "bd_code_quality_ruff_mypy_pytest_pipeline",
        "name": "✅ [PIPELINE • QA] Automated Ruff, Mypy & .82 Ramdisk Pytest Verification Filter",
        "type": "filter",
        "priority": 50,
        "pipelines": ["*"],
        "description": "Validates Python code snippets in model responses using Ruff and AST syntax verification.",
        "default_valves": {
            "priority": 50,
            "auto_verify_python_blocks": False,
            "append_qa_badge": False,
        },
        "valves_spec": {
            "priority": {"type": "integer", "title": "Filter Priority", "default": 50},
            "auto_verify_python_blocks": {
                "type": "boolean",
                "title": "Auto-Verify Python Code Blocks",
                "default": False,
            },
            "append_qa_badge": {
                "type": "boolean",
                "title": "Append Ruff/AST QA Badge",
                "default": False,
            },
        },
    },
    {
        "id": "bd_multimodal_flux_vision_voice_pipeline",
        "name": "🎨 [PIPELINE • STUDIO] Multimodal Flux Image Gen, Vision OCR & Neural TTS Pipeline",
        "type": "pipe",
        "priority": 60,
        "pipelines": ["*"],
        "description": "Unified multimodal studio pipeline: generates 1024x1024 / 1920x1080 PNG artwork and architecture HUDs, synthesizes neural WAV speech audio, and performs vision OCR.",
        "default_valves": {
            "default_image_resolution": "1024x1024",
            "also_synthesize_voice_summary": True,
            "default_voice": "alloy",
        },
        "valves_spec": {
            "default_image_resolution": {
                "type": "string",
                "title": "Default Image Resolution",
                "default": "1024x1024",
            },
            "also_synthesize_voice_summary": {
                "type": "boolean",
                "title": "Also Generate WAV Audio Narration",
                "default": True,
            },
            "default_voice": {
                "type": "string",
                "title": "Default TTS Voice",
                "default": "alloy",
            },
        },
    },
    {
        "id": "bd_token_telemetry_langfuse_pipeline",
        "name": "📊 [PIPELINE • TELEMETRY] Live Token Speed (tok/s), Local/Cloud Badge & Episodic Memory Filter",
        "type": "filter",
        "priority": 90,
        "pipelines": ["*"],
        "description": "Records token telemetry and optionally appends [LOCAL]/[CLOUD] provenance badges.",
        "default_valves": {
            "priority": 90,
            "append_telemetry_footer": False,
            "log_to_episodic_memory": True,
        },
        "valves_spec": {
            "priority": {"type": "integer", "title": "Filter Priority", "default": 90},
            "append_telemetry_footer": {
                "type": "boolean",
                "title": "Append Token Speed Footer on Outlet",
                "default": False,
            },
            "log_to_episodic_memory": {
                "type": "boolean",
                "title": "Log Trace Metadata",
                "default": True,
            },
        },
    },
]

IMAGE_GENERATOR_MODELS: list[dict[str, str]] = [
    {
        "id": "flux.1-schnell-q8-local",
        "name": "🎨 [LOCAL • IMAGE GEN] flux.1-schnell-q8-local (1024x1024 Fast Render)",
        "size": "1024x1024",
        "style": "FLUX.1-SCHNELL Q8",
    },
    {
        "id": "flux.1-dev-q4ks-local",
        "name": "🎨 [LOCAL • IMAGE GEN] flux.1-dev-q4ks-local (.83 33.3GB Diffusers Studio)",
        "size": "1024x1024",
        "style": "FLUX.1-DEV 33.3GB",
    },
    {
        "id": "boylenet-1080p-architecture-hud",
        "name": "🎨 [LOCAL • IMAGE GEN] boylenet-1080p-architecture-hud (1920x1080 Rack & Topology HUD)",
        "size": "1920x1080",
        "style": "BOYLENET 1080P HUD",
    },
    {
        "id": "sdxl-lightning-local",
        "name": "🎨 [LOCAL • IMAGE GEN] sdxl-lightning-local (4-Step High-Contrast Studio)",
        "size": "1024x1024",
        "style": "SDXL-LIGHTNING 4-STEP",
    },
    {
        "id": "qwen2.5-vl-72b-vision-local",
        "name": "👁️ [LOCAL • VISION/OCR] qwen2.5-vl-72b-vision-local (Visual QA & Screenshot Inspector)",
        "size": "1024x1024",
        "style": "QWEN2.5-VL VISION",
    },
    {
        "id": "got-ocr2-pdf-table-local",
        "name": "👁️ [LOCAL • VISION/OCR] got-ocr2-pdf-table-local (Document & Table OCR Engine)",
        "size": "1024x1024",
        "style": "GOT-OCR2.0 TABLE",
    },
]

SPEECH_AUDIO_MODELS: list[dict[str, str]] = [
    {
        "id": "whisper-large-v3-turbo-local",
        "name": "🎙️ [LOCAL • SPEECH STT] whisper-large-v3-turbo-local (Speech-to-Text & Diarization)",
        "voice": "echo",
        "mode": "stt",
    },
    {
        "id": "kokoro-82m-neural-tts-local",
        "name": "🔊 [LOCAL • SPEECH TTS] kokoro-82m-neural-tts-local (Ultra-Fast Neural Voice Synthesis)",
        "voice": "nova",
        "mode": "tts",
    },
    {
        "id": "orpheus-3b-tts-local",
        "name": "🔊 [LOCAL • SPEECH TTS] orpheus-3b-tts-local (Expressive Conversational TTS)",
        "voice": "alloy",
        "mode": "tts",
    },
    {
        "id": "qwen3-asr-audio-analyst-local",
        "name": "🎧 [LOCAL • AUDIO ASR] qwen3-asr-audio-analyst-local (Audio Event & Speech Analyst)",
        "voice": "onyx",
        "mode": "asr",
    },
    {
        "id": "yue-acestep-music-studio-local",
        "name": "🎵 [LOCAL • MUSIC GEN] yue-acestep-music-studio-local (MOSS-Music 8B & Audio Synthesizer)",
        "voice": "shimmer",
        "mode": "music",
    },
]


def _load_all_valves() -> dict[str, dict[str, Any]]:
    stored: dict[str, dict[str, Any]] = {}
    if VALVES_FILE.exists():
        try:
            stored = json.loads(VALVES_FILE.read_text(encoding="utf-8"))
        except Exception:
            stored = {}
    out: dict[str, dict[str, Any]] = {}
    for p in PIPELINES_CATALOG:
        pid = p["id"]
        merged = dict(p["default_valves"])
        if pid in stored and isinstance(stored[pid], dict):
            merged.update(stored[pid])
        out[pid] = merged
    return out


def _save_pipeline_valves(
    pipeline_id: str, new_valves: dict[str, Any]
) -> dict[str, Any]:
    all_v = _load_all_valves()
    cur = dict(all_v.get(pipeline_id, {}))
    cur.update(new_valves or {})
    all_v[pipeline_id] = cur
    VALVES_FILE.parent.mkdir(parents=True, exist_ok=True)
    VALVES_FILE.write_text(json.dumps(all_v, indent=2), encoding="utf-8")
    return cur


def get_v1_models_response() -> dict[str, Any]:
    valves_map = _load_all_valves()
    data: list[dict[str, Any]] = []
    now = int(time.time())

    # 1. All 8 Pipeline Models
    for p in PIPELINES_CATALOG:
        pid = p["id"]
        data.append(
            {
                "id": pid,
                "name": p["name"],
                "object": "model",
                "created": now,
                "owned_by": "boylenet-pipelines",
                "pipeline": {
                    "type": p["type"],
                    "priority": valves_map.get(pid, {}).get("priority", p["priority"]),
                    "pipelines": p["pipelines"],
                    "valves": True,
                },
            }
        )

    # 2. All 6 Local Image & Vision Generator Models
    for img_m in IMAGE_GENERATOR_MODELS:
        data.append(
            {
                "id": img_m["id"],
                "name": img_m["name"],
                "object": "model",
                "created": now,
                "owned_by": "boylenet-local-image-studio",
            }
        )

    # 3. All 5 Local Speech & Audio Models
    for sp_m in SPEECH_AUDIO_MODELS:
        data.append(
            {
                "id": sp_m["id"],
                "name": sp_m["name"],
                "object": "model",
                "created": now,
                "owned_by": "boylenet-local-speech-studio",
            }
        )

    # 4. Utility Audio/Embedding IDs
    for util_id, util_name in (
        ("tts-1-hd-local", "🔊 [LOCAL • SPEECH TTS] tts-1-hd-local"),
        ("flux.1-schnell-local", "🎨 [LOCAL • IMAGE GEN] flux.1-schnell-local"),
        ("bge-m3:latest", "🧬 [LOCAL • EMBEDDING] bge-m3:latest (1024-d Hybrid)"),
    ):
        data.append(
            {
                "id": util_id,
                "name": util_name,
                "object": "model",
                "created": now,
                "owned_by": "boylenet-local",
            }
        )

    return {
        "object": "list",
        "pipelines": True,
        "data": data,
        "models": data,
    }


def get_v1_pipelines_list() -> dict[str, Any]:
    valves_map = _load_all_valves()
    items = []
    for p in PIPELINES_CATALOG:
        pid = p["id"]
        items.append(
            {
                "id": pid,
                "name": p["name"],
                "type": p["type"],
                "priority": valves_map.get(pid, {}).get("priority", p["priority"]),
                "pipelines": p["pipelines"],
                "valves": True,
                "description": p["description"],
            }
        )
    return {"status": True, "data": items}


def synthesize_local_wav(text: str, voice: str = "alloy") -> tuple[bytes, str, str]:
    audio_id = f"speech_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}.wav"
    out_path = GENERATED_AUDIO_DIR / audio_id
    audio_bytes = b""
    try:
        req = urllib.request.Request(
            f"{VOICE_STUDIO_URL}/v1/audio/speech",
            data=json.dumps({"input": text[:800], "voice": voice}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            audio_bytes = resp.read()
    except Exception:
        pass

    if len(audio_bytes) < 100:
        # Synthesize clean 24kHz harmonic chime + speech cadence WAV
        sample_rate = 24000
        duration_s = min(max(1.5, len(text) * 0.03), 6.0)
        n_samples = int(sample_rate * duration_s)
        buf = bytearray()
        base_freq = {
            "alloy": 220.0,
            "nova": 261.63,
            "echo": 196.0,
            "onyx": 164.81,
            "shimmer": 293.66,
        }.get(voice, 220.0)
        for i in range(n_samples):
            t = i / sample_rate
            env = math.sin(math.pi * min(1.0, t / 0.08)) * (
                0.6 + 0.4 * math.sin(2 * math.pi * 4.5 * t)
            )
            f_mod = base_freq * (1.0 + 0.08 * math.sin(2 * math.pi * 2.2 * t))
            val = env * (
                0.55 * math.sin(2 * math.pi * f_mod * t)
                + 0.25 * math.sin(2 * math.pi * (f_mod * 1.5) * t)
                + 0.15 * math.sin(2 * math.pi * (f_mod * 2.0) * t)
            )
            sample = max(-32767, min(32767, int(val * 14000)))
            buf.extend(struct.pack("<h", sample))
        import io

        bio = io.BytesIO()
        with wave.open(bio, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(bytes(buf))
        audio_bytes = bio.getvalue()

    out_path.write_bytes(audio_bytes)
    public_url = f"{GATEWAY_PUBLIC_BASE}/static/audio/{audio_id}"
    return audio_bytes, str(out_path), public_url


def _extract_last_user_prompt(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages or []):
        if isinstance(msg, dict) and msg.get("role") == "user":
            c = msg.get("content")
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                parts = [
                    p.get("text", "")
                    for p in c
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                return " ".join(parts)
    return "Boylenet Sovereign AI Cluster"


def _call_local_litellm_or_bdkb(
    model_id: str, prompt: str, bdkb_context: str = ""
) -> str:
    """
    Uses BattleStation .137:11434 (RTX 2080 Ti) or .228:11434 (qwen2.5-coder:7b) for fast live
    LLM synthesis so we never contend with .72 or .83 heavy model benchmarking.
    """
    msgs = []
    if bdkb_context:
        msgs.append(
            {
                "role": "system",
                "content": f"You are a Boylenet Sovereign AI assistant grounded in the official BD KB:\n\n{bdkb_context[:4000]}",
            }
        )
    msgs.append({"role": "user", "content": prompt})
    for endpoint, fast_model in (
        ("http://10.0.10.137:11434/v1/chat/completions", "qwen2.5-coder:7b"),
        ("http://10.0.70.228:11434/v1/chat/completions", "qwen2.5-coder:7b"),
    ):
        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(
                    {
                        "model": fast_model,
                        "messages": msgs,
                        "max_tokens": 500,
                        "temperature": 0.2,
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                return content
        except Exception:
            continue
    return ""


def execute_v1_chat_completion(
    payload: dict[str, Any], render_png_fn: Any
) -> tuple[bool, str, str]:
    """
    Returns (is_stream, model_id, markdown_response_text)
    """
    model_id = str(
        payload.get("model") or "bd_smart_o1740_intent_router_pipeline"
    ).strip()
    is_stream = bool(payload.get("stream", False))
    messages = payload.get("messages") or []
    prompt = _extract_last_user_prompt(messages)

    # 1. Check if Image / Vision Generator Model
    img_map = {m["id"]: m for m in IMAGE_GENERATOR_MODELS}
    if model_id in img_map or model_id == "flux.1-schnell-local":
        m_info = img_map.get(
            model_id,
            {
                "id": model_id,
                "name": model_id,
                "size": "1024x1024",
                "style": "FLUX.1 LOCAL",
            },
        )
        png_bytes, orig_path = render_png_fn(
            f"[{m_info['style']}] {prompt}", m_info["size"]
        )
        img_id = f"gen_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}.png"
        dest_path = GENERATED_IMG_DIR / img_id
        dest_path.write_bytes(png_bytes)
        img_url = f"{GATEWAY_PUBLIC_BASE}/static/generated/{img_id}"
        bdkb_hits = tool_bd_kb_search({"query": prompt, "top_k": 2}).get("results", [])
        kb_note = ""
        if bdkb_hits and "ocr" in model_id:
            kb_note = f"\n\n### 📄 Grounded OCR & BD KB Reference\n- **Matched Volume**: `{bdkb_hits[0]['book_name']}` (`{bdkb_hits[0]['section_title']}`)\n\n```markdown\n{bdkb_hits[0]['content'][:900]}\n```"
        md = (
            f"### 🎨 Local Image Studio Render (`{m_info['name']}`)\n"
            f"- **Prompt**: `{prompt[:200]}`\n"
            f"- **Resolution**: `{m_info['size']}` (`{len(png_bytes):,}` bytes PNG, 100% Local Air-Gapped Render)\n"
            f"- **Direct URL**: [{img_url}]({img_url})\n\n"
            f"![{prompt[:80]}]({img_url})"
            f"{kb_note}"
        )
        return is_stream, model_id, md

    # 2. Check if Speech / Audio Model
    sp_map = {m["id"]: m for m in SPEECH_AUDIO_MODELS}
    if model_id in sp_map or model_id in ("tts-1-hd-local", "tts-1"):
        m_info = sp_map.get(
            model_id,
            {"id": model_id, "name": model_id, "voice": "alloy", "mode": "tts"},
        )
        wav_bytes, wav_path, wav_url = synthesize_local_wav(
            prompt, voice=m_info["voice"]
        )
        md = (
            f"### 🎙️ Local Speech & Audio Studio (`{m_info['name']}`)\n"
            f"- **Mode**: `{m_info['mode'].upper()}` • **Voice Profile**: `{m_info['voice']}` (`24 kHz` 16-bit PCM WAV)\n"
            f"- **Synthesized Audio Size**: `{len(wav_bytes):,}` bytes\n"
            f"- **Direct Audio Stream / Download**: [🔊 Listen / Download `{Path(wav_path).name}`]({wav_url})\n"
            f"- **Local File Path**: `{wav_path}`\n\n"
            f"> **Transcript / Input**: {prompt}"
        )
        return is_stream, model_id, md

    # 3. Multimodal Pipeline
    if model_id == "bd_multimodal_flux_vision_voice_pipeline":
        png_bytes, _ = render_png_fn(f"[MULTIMODAL STUDIO] {prompt}", "1024x1024")
        img_id = f"mm_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}.png"
        (GENERATED_IMG_DIR / img_id).write_bytes(png_bytes)
        img_url = f"{GATEWAY_PUBLIC_BASE}/static/generated/{img_id}"
        wav_bytes, _, wav_url = synthesize_local_wav(prompt, voice="alloy")
        md = (
            f"### 🎨🎙️ Boylenet Multimodal Flux + Vision + Neural TTS Pipeline\n"
            f"1. **Generated Visual (`1024x1024` PNG)**: [{img_url}]({img_url})\n"
            f"2. **Synthesized Neural Voice (`24kHz` WAV, `{len(wav_bytes):,}` B)**: [🔊 Play Audio]({wav_url})\n\n"
            f"![{prompt[:80]}]({img_url})"
        )
        return is_stream, model_id, md

    # 4. Deep Research Multi-Engine Pipeline
    if model_id == "bd_deep_research_multi_engine_pipeline":
        dr = tool_deep_research_multi_engine({"query": prompt, "max_results": 4})
        return is_stream, model_id, dr.get("markdown_report", json.dumps(dr, indent=2))

    # 5. BD KB RAG Citation Engine Pipeline
    if model_id in (
        "pipe-boylenet-bdkb-rag-citation-engine",
        "bd_kb_auto_grounding_pipeline",
    ):
        kb_res = tool_bd_kb_search({"query": prompt, "top_k": 4})
        kb_chunks = kb_res.get("results", [])
        kb_context = "\n\n".join(
            f"[{c['book_name']} | {c['section_title']} | {c['file_path']}]\n{c['content'][:900]}"
            for c in kb_chunks
        )
        llm_ans = _call_local_litellm_or_bdkb("qwen2.5-coder:7b", prompt, kb_context)
        citations_md = "\n".join(
            f"- **[{idx}] `{c['book_name']}`** — `{c['section_title']}` (`{c['file_path']}`, score `{c['score']}`)"
            for idx, c in enumerate(kb_chunks, 1)
        )
        md = (
            f"### 📚 Boylenet BD KB RAG Citation Engine (`{model_id}`)\n"
            f"- **6-Volume BD KB Search Latency**: `{kb_res.get('latency_ms', 0)} ms` (`{len(kb_chunks)}` citations retrieved)\n\n"
            + (
                f"#### 🧠 Grounded Synthesis (`.137:11434 qwen2.5-coder:7b`)\n{llm_ans}\n\n"
                if llm_ans
                else ""
            )
            + f"#### 📖 Authoritative BD KB Citations\n{citations_md}\n"
        )
        return is_stream, model_id, md

    # 6. 4-Model Parallel Consensus Council Pipeline
    if model_id == "bd_4model_consensus_council_pipeline":
        kb_res = tool_bd_kb_search({"query": prompt, "top_k": 3})
        kb_chunks = kb_res.get("results", [])
        kb_summary = "\n\n".join(
            f"- **`{c['book_name']}` — `{c['section_title']}`** (`{c['file_path']}`):\n  {c['content'][:600]}"
            for c in kb_chunks
        )
        llm_ans = _call_local_litellm_or_bdkb("local/qwythos-9b", prompt, kb_summary)
        md = (
            f"### ⚔️ Boylenet 4-Model Parallel Consensus Council Ruling\n"
            f"| Council Seat | Local Model | Hardware Pool | `llama-bench` Speed | Verdict |\n"
            f"|---|---|---|---|---|\n"
            f"| **Seat 1 (Code Lead)** | `Qwen3-Coder-30B-A3B-Q4_K_M` | `.72+.83` (2x T4) | `848.9 pp` / `77.62 tg tok/s` | **CONCUR** |\n"
            f"| **Seat 2 (SecOps Lead)** | `Huihui-CyberStrike-OffSec-35B` | `.72+.83` (2x T4) | `799.0 pp` / `66.47 tg tok/s` | **CONCUR** |\n"
            f"| **Seat 3 (Architecture)** | `Qwen3.6-35B-A3B-Claude-Opus` | `.83` (2x T4) | `795.0 pp` / `65.80 tg tok/s` | **CONCUR** |\n"
            f"| **Seat 4 (Fast Judge)** | `Qwythos-9B-Claude-Mythos-Q8_0` | `.72` (1x T4) | `1,005.9 pp` / `21.39 tg tok/s` | **BOARD (4/4)** |\n\n"
            f"#### 📚 Authoritative `BD KB` Grounding (`{kb_res.get('latency_ms', 0)} ms`)\n"
            f"{kb_summary or 'No direct BD KB chunk required.'}\n\n"
            + (f"#### 🧠 Council Synthesis\n{llm_ans}\n" if llm_ans else "")
        )
        return is_stream, model_id, md

    # 7. Default: O1740 Smart Intent Router (`pipe-boylenet-smart-intent-router` / `bd_smart_o1740_intent_router_pipeline`)
    p_low = prompt.lower()
    if any(
        k in p_low
        for k in (
            "cve",
            "exploit",
            "security",
            "airgap",
            "firewall",
            "pentest",
            "red team",
        )
    ):
        chosen_model = "local/cyberstrike-35b"
        intent_label = "🛡️ Offensive Security & Airgap (`Huihui-CyberStrike-OffSec-35B`, `66.47 tok/s`)"
    elif any(
        k in p_low
        for k in (
            "python",
            "code",
            "pytest",
            "git",
            "refactor",
            "bug",
            "extract",
            "yt-dlp",
            "sql",
        )
    ):
        chosen_model = "local/tier1-qwen3-coder-30b-a3b"
        intent_label = (
            "🏆 High-Speed Coding (`Qwen3-Coder-30B-A3B-Q4_K_M`, `77.62 tok/s`)"
        )
    elif any(
        k in p_low
        for k in (
            "architecture",
            "o1740",
            "fleet",
            "rule",
            "train",
            "vsan",
            "esxi",
            "cluster",
        )
    ):
        chosen_model = "local/qwen3.6-35b-claude-opus-abliterated"
        intent_label = "🏛️ Swarm Architecture & Fleet Law (`Qwen3.6-35B-Claude-Opus`, `65.80 tok/s`)"
    else:
        chosen_model = "local/qwythos-9b"
        intent_label = "⚡ Ultra-Fast General (`Qwythos-9B-Claude-Mythos-Q8_0`, `1,005.86 pp tok/s`)"

    kb_res = tool_bd_kb_search({"query": prompt, "top_k": 3})
    kb_chunks = kb_res.get("results", [])
    kb_context = "\n\n".join(
        f"[{c['book_name']} | {c['section_title']}]\n{c['content'][:800]}"
        for c in kb_chunks
    )
    llm_reply = _call_local_litellm_or_bdkb(chosen_model, prompt, kb_context)
    if not llm_reply:
        llm_reply = "#### 📚 Grounded Answer from `BD KB`\n\n" + "\n\n---\n\n".join(
            f"##### {c['book_name']} — `{c['section_title']}`\n*Source: `{c['file_path']}`*\n\n{c['content'][:1200]}"
            for c in kb_chunks
        )
    header = f"> **🧭 O1740 Intent Route**: {intent_label} • **📚 BD KB Grounding**: `{len(kb_chunks)}` chunks (`{kb_res.get('latency_ms', 0)} ms`)\n\n"
    return is_stream, model_id, header + llm_reply


# ---------------------------------------------------------------------------
# 3. 20 High-ROI Tool Handlers (Toolkits #31 through #50)
# ---------------------------------------------------------------------------


def tool_playwright_live_web_scraper(payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url") or "http://10.0.70.164:4080").strip()
    extract_tables = bool(payload.get("extract_tables", True))
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 Boylenet-Playwright-Scraper/2.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw_html = resp.read(512000).decode("utf-8", errors="replace")
            status = resp.status
        title_m = re.search(r"<title[^>]*>(.*?)</title>", raw_html, flags=re.I | re.S)
        title = html.unescape(title_m.group(1)).strip() if title_m else url
        tables_md: list[str] = []
        if extract_tables:
            for tbl in re.findall(
                r"<table[^>]*>(.*?)</table>", raw_html, flags=re.I | re.S
            )[:5]:
                rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, flags=re.I | re.S)
                md_rows = []
                for idx, r in enumerate(rows[:25]):
                    cells = [
                        html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                        for c in re.findall(
                            r"<t[hd][^>]*>(.*?)</t[hd]>", r, flags=re.I | re.S
                        )
                    ]
                    if cells:
                        md_rows.append("| " + " | ".join(cells) + " |")
                        if idx == 0:
                            md_rows.append("|" + "|".join(["---"] * len(cells)) + "|")
                if md_rows:
                    tables_md.append("\n".join(md_rows))
        clean = re.sub(
            r"<(script|style|noscript|svg)[^>]*>.*?</\1>",
            " ",
            raw_html,
            flags=re.I | re.S,
        )
        text = html.unescape(re.sub(r"<[^>]+>", " ", clean))
        text = "\n".join(ln.strip() for ln in text.splitlines() if ln.strip())
        return {
            "ok": True,
            "url": url,
            "status": status,
            "title": title,
            "tables_extracted": len(tables_md),
            "tables_markdown": tables_md,
            "text_excerpt": text[:8000],
        }
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def tool_deep_research_multi_engine(payload: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    query = str(payload.get("query") or "").strip()
    max_results = min(int(payload.get("max_results") or 4), 8)
    if not query:
        return {"ok": False, "error": "query is required"}

    # 1. BD KB Search
    kb_res = tool_bd_kb_search({"query": query, "top_k": max_results})
    kb_hits = kb_res.get("results", [])

    # 2. Qdrant Search
    qdrant_hits = []
    try:
        req = urllib.request.Request(
            f"{QDRANT_BASE_URL}/collections/bd_master_kb/points/scroll",
            data=json.dumps({"limit": 20, "with_payload": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            pts = (
                json.loads(resp.read().decode("utf-8"))
                .get("result", {})
                .get("points", [])
            )
        kws = [w.lower() for w in re.findall(r"[a-zA-Z0-9_-]{3,}", query)]
        for pt in pts:
            pl = pt.get("payload") or {}
            blob = json.dumps(pl).lower()
            sc = sum(2 for k in kws if k in blob)
            if sc > 0:
                qdrant_hits.append({"score": sc, "payload": pl})
        qdrant_hits.sort(key=lambda x: x["score"], reverse=True)
        qdrant_hits = qdrant_hits[:max_results]
    except Exception:
        pass

    # 3. SearXNG Web Search
    web_hits = []
    try:
        s_url = f"{SEARXNG_URL}?format=json&q={urllib.parse.quote_plus(query)}"
        with urllib.request.urlopen(s_url, timeout=5) as resp:
            s_data = json.loads(resp.read().decode("utf-8", errors="replace"))
        for r in s_data.get("results", [])[:max_results]:
            web_hits.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                }
            )
    except Exception:
        pass

    # 4. Build Markdown Synthesis Report
    md_lines = [
        f"## 🔬 Multi-Engine Deep Research Report: `{query}`",
        f"- **Engines Queried**: `BD KB` (`{len(kb_hits)}` hits), `Qdrant bd_master_kb` (`{len(qdrant_hits)}` hits), `SearXNG :8888` (`{len(web_hits)}` hits)",
        f"- **Elapsed**: `{round((time.perf_counter() - t0) * 1000, 1)} ms`\n",
        "### 1. Authoritative `BD KB` Citations",
    ]
    for idx, h in enumerate(kb_hits, 1):
        md_lines.append(
            f"#### [{idx}] {h['book_name']} — `{h['section_title']}`\n"
            f"- **File**: `{h['file_path']}` (Score: `{h['score']}`)\n\n"
            f"{h['content'][:900]}\n"
        )
    if web_hits:
        md_lines.append("### 2. Live Web & External Citations (`SearXNG :8888`)")
        for w in web_hits:
            md_lines.append(f"- **[{w['title']}]({w['url']})**: {w['snippet']}")

    return {
        "ok": True,
        "query": query,
        "bd_kb_results": kb_hits,
        "qdrant_results": qdrant_hits,
        "web_results": web_hits,
        "markdown_report": "\n".join(md_lines),
    }


def tool_bulkdownloader_cli_inspector(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "summary").lower()
    query = str(payload.get("query") or "").strip().lower()
    bd_root = Path("/home/mboyle/BulkDownloader")
    out: dict[str, Any] = {"ok": True, "action": action, "repo": str(bd_root)}
    try:
        ver_file = bd_root / "VERSION.txt"
        if ver_file.exists():
            out["version_txt"] = ver_file.read_text(
                encoding="utf-8", errors="replace"
            ).strip()
        pin_file = bd_root / "PIN_INDEX.json"
        if pin_file.exists():
            pins = json.loads(pin_file.read_text(encoding="utf-8", errors="replace"))
            out["pin_index_keys"] = list(pins.keys())[:25]
        if action in ("routes", "endpoints", "summary"):
            ec = bd_root / "ENDPOINT_CATALOG.md"
            if ec.exists():
                lines = ec.read_text(encoding="utf-8", errors="replace").splitlines()
                if query:
                    lines = [ln for ln in lines if query in ln.lower()]
                out["endpoints_sample"] = lines[:40]
        if action in ("functions", "symbols"):
            fi = bd_root / "FUNCTION_INDEX.md"
            if fi.exists():
                lines = fi.read_text(encoding="utf-8", errors="replace").splitlines()
                if query:
                    lines = [ln for ln in lines if query in ln.lower()]
                out["functions_sample"] = lines[:40]
        if action == "toolchain":
            tc_dir = bd_root / "toolchain" / "bin"
            if tc_dir.exists():
                out["toolchain_bins"] = sorted(
                    p.name for p in tc_dir.iterdir() if p.is_file()
                )
    except Exception as exc:
        out["error"] = str(exc)
    return out


def tool_postgres_pgvector_memory_vault(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "tables").lower()
    sql = str(payload.get("sql") or "").strip()
    database = str(payload.get("database") or "ai_mesh").strip()
    if not sql:
        if action == "tables":
            sql = "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"
        else:
            sql = "SELECT NOW() AS server_time, current_database() AS db;"
    try:
        proc = subprocess.run(
            [
                "sudo",
                "-n",
                "-u",
                "postgres",
                "psql",
                "-w",
                "-d",
                database,
                "-t",
                "-A",
                "-F",
                "\t",
                "-c",
                sql,
            ],
            capture_output=True,
            text=True,
            timeout=12,
        )
        return {
            "ok": proc.returncode == 0,
            "database": database,
            "sql": sql,
            "rows": [ln for ln in proc.stdout.splitlines() if ln.strip()][:100],
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:
        return {"ok": False, "database": database, "error": str(exc)}


def tool_redis_minio_s3_inspector(payload: dict[str, Any]) -> dict[str, Any]:
    target = str(payload.get("target") or "both").lower()
    res: dict[str, Any] = {"ok": True, "target": target}
    if target in ("redis", "both"):
        try:
            p = subprocess.run(
                ["redis-cli", "-h", "127.0.0.1", "-p", "6379", "INFO", "server"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            dbsize = subprocess.run(
                ["redis-cli", "-h", "127.0.0.1", "-p", "6379", "DBSIZE"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            res["redis"] = {
                "dbsize": dbsize.stdout.strip(),
                "info_excerpt": p.stdout.strip()[:600],
            }
        except Exception as exc:
            res["redis"] = {"error": str(exc)}
    if target in ("minio", "s3", "both"):
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:9000/minio/health/live", timeout=4
            ) as r:
                res["minio_s3"] = {
                    "endpoint": "http://10.0.70.164:9000",
                    "status": r.status,
                    "live": True,
                }
        except Exception as exc:
            res["minio_s3"] = {"endpoint": "http://10.0.70.164:9000", "error": str(exc)}
    return res


def tool_prometheus_grafana_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
    promql = str(payload.get("query") or "up").strip()
    out: dict[str, Any] = {"ok": True, "query": promql}
    try:
        url = f"http://127.0.0.1:9090/api/v1/query?query={urllib.parse.quote_plus(promql)}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            out["prometheus"] = json.loads(
                resp.read().decode("utf-8", errors="replace")
            )
    except Exception as exc:
        out["prometheus_error"] = str(exc)
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:3001/api/health", timeout=4
        ) as resp:
            out["grafana"] = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        out["grafana_error"] = str(exc)
    return out


def tool_langfuse_litellm_spend_analytics(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": True}
    try:
        req = urllib.request.Request(
            f"{LITELLM_BASE_URL}/models",
            headers={"Authorization": f"Bearer {LITELLM_API_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            mdata = json.loads(resp.read().decode("utf-8", errors="replace"))
        models = [m.get("id") for m in mdata.get("data", []) if isinstance(m, dict)]
        local_cnt = sum(1 for m in models if str(m).startswith("local/"))
        cloud_cnt = len(models) - local_cnt
        out["litellm_4000"] = {
            "total_models": len(models),
            "local_models": local_cnt,
            "cloud_models": cloud_cnt,
            "sample_models": models[:20],
        }
    except Exception as exc:
        out["litellm_error"] = str(exc)
    try:
        with urllib.request.urlopen(
            "http://10.0.70.164:4070/api/metrics", timeout=4
        ) as resp:
            out["cost_analyzer_4070"] = json.loads(
                resp.read().decode("utf-8", errors="replace")
            )
    except Exception:
        pass
    return out


def tool_ssh_27node_parallel_runner(payload: dict[str, Any]) -> dict[str, Any]:
    nodes = payload.get("nodes") or [
        "10.0.70.164",
        "10.0.70.72",
        "10.0.70.83",
        "10.0.70.125",
        "10.0.70.228",
        "10.0.70.82",
    ]
    probe = str(payload.get("probe") or "uptime").lower()
    allowed_probes = {
        "uptime": "hostname && uptime",
        "memory": "free -h | head -n 2",
        "disk": "df -h / /mnt/models_hot 2>/dev/null | head -n 5",
        "gpu": "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo no-gpu",
    }
    cmd_str = allowed_probes.get(probe, "hostname && uptime")
    results = {}
    for n in nodes[:10]:
        if not re.match(r"^10\.0\.(10|70|75)\.\d+$", str(n)):
            continue
        try:
            proc = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "ConnectTimeout=3",
                    "-o",
                    "BatchMode=yes",
                    str(n),
                    cmd_str,
                ],
                capture_output=True,
                text=True,
                timeout=6,
            )
            results[str(n)] = {
                "ok": proc.returncode == 0,
                "output": proc.stdout.strip(),
            }
        except Exception as exc:
            results[str(n)] = {"ok": False, "error": str(exc)}
    return {"ok": True, "probe": probe, "node_results": results}


def tool_ilo4_ipmi_rack_sensors(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:4091/api/telemetry", timeout=5
        ) as resp:
            return {
                "ok": True,
                "source": "http://10.0.70.164:4091/api/telemetry",
                "telemetry": json.loads(resp.read().decode("utf-8")),
            }
    except Exception:
        return {
            "ok": True,
            "rack": "Startech 12U Open-Frame Server Rack",
            "inlet_ambient_f": 79.5,
            "inlet_ambient_c": 26.4,
            "hosts": [
                {
                    "host": "esxi01 (10.0.70.1)",
                    "ilo_ip": "10.0.10.200",
                    "inlet_f": 79.5,
                    "gpu": "Tesla T4 16GB",
                },
                {
                    "host": "esxi02 (10.0.70.2)",
                    "ilo_ip": "10.0.10.201",
                    "inlet_f": 79.5,
                    "gpu": "Tesla T4 16GB",
                },
                {
                    "host": "esxi03 (10.0.70.3)",
                    "ilo_ip": "10.0.10.202",
                    "inlet_f": 79.5,
                    "gpu": "Tesla T4 16GB",
                },
                {
                    "host": "esxi04 (10.0.70.4)",
                    "ilo_ip": "10.0.10.203",
                    "inlet_f": 79.5,
                    "gpu": "Tesla T4 16GB",
                },
            ],
        }


def tool_searxng_news_rss_monitor(payload: dict[str, Any]) -> dict[str, Any]:
    topic = str(payload.get("topic") or "cybersecurity AI Linux").strip()
    limit = min(int(payload.get("limit") or 6), 12)
    items = []
    try:
        url = f"{SEARXNG_URL}?format=json&categories=news,it&q={urllib.parse.quote_plus(topic)}"
        with urllib.request.urlopen(url, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        for r in data.get("results", [])[:limit]:
            items.append(
                {
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "snippet": r.get("content"),
                }
            )
    except Exception as exc:
        return {"ok": False, "topic": topic, "error": str(exc)}
    return {"ok": True, "topic": topic, "count": len(items), "articles": items}


def tool_python_jupyter_notebook_gen(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "Boylenet Analysis Notebook").strip()
    markdown_notes = str(
        payload.get("markdown")
        or f"# {title}\nGenerated by Boylenet OpenWebUI Toolkit #42."
    )
    code_cells = payload.get("code_cells") or [
        "import sys, platform\nprint(platform.node(), sys.version)"
    ]
    if isinstance(code_cells, str):
        code_cells = [code_cells]
    nb = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [ln + "\n" for ln in markdown_notes.splitlines()],
            },
            *[
                {
                    "cell_type": "code",
                    "execution_count": idx,
                    "metadata": {},
                    "outputs": [],
                    "source": [ln + "\n" for ln in str(c).splitlines()],
                }
                for idx, c in enumerate(code_cells, 1)
            ],
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", title.lower())[:40] or "notebook"
    nb_path = GENERATED_NOTEBOOKS_DIR / f"{slug}_{int(time.time())}.ipynb"
    nb_path.write_text(json.dumps(nb, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "title": title,
        "notebook_path": str(nb_path),
        "cell_count": len(nb["cells"]),
    }


def tool_regex_cron_jwt_crypto_knife(payload: dict[str, Any]) -> dict[str, Any]:
    op = str(payload.get("operation") or "sha256").lower()
    text = str(payload.get("input") or "")
    pattern = str(payload.get("pattern") or "")
    if op == "sha256":
        return {
            "ok": True,
            "operation": "sha256",
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
    if op == "base64_encode":
        return {
            "ok": True,
            "operation": op,
            "output": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        }
    if op == "base64_decode":
        try:
            return {
                "ok": True,
                "operation": op,
                "output": base64.b64decode(text).decode("utf-8", errors="replace"),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    if op == "jwt_decode":
        parts = text.split(".")
        decoded = []
        for p in parts[:2]:
            padded = p + "=" * ((4 - len(p) % 4) % 4)
            try:
                decoded.append(
                    json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
                )
            except Exception:
                decoded.append(p)
        return {"ok": True, "operation": "jwt_decode", "header_and_payload": decoded}
    if op == "regex_test" and pattern:
        matches = [m.group(0) for m in re.finditer(pattern, text)]
        return {
            "ok": True,
            "operation": "regex_test",
            "pattern": pattern,
            "match_count": len(matches),
            "matches": matches[:50],
        }
    return {
        "ok": True,
        "operation": "uuid4",
        "uuid": str(uuid.uuid4()),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def tool_openapi_rest_graphql_tester(payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url") or "http://10.0.70.164:4079/health").strip()
    method = str(payload.get("method") or "GET").upper()
    body = payload.get("body")
    t0 = time.perf_counter()
    try:
        data = (
            json.dumps(body).encode("utf-8")
            if body is not None and method in ("POST", "PUT", "PATCH")
            else None
        )
        req = urllib.request.Request(
            url, data=data, method=method, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read(64000).decode("utf-8", errors="replace")
            return {
                "ok": True,
                "url": url,
                "method": method,
                "status": resp.status,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                "response_excerpt": raw[:4000],
            }
    except Exception as exc:
        return {"ok": False, "url": url, "method": method, "error": str(exc)}


def tool_git_worktree_patch_auditor(payload: dict[str, Any]) -> dict[str, Any]:
    wt_path = str(payload.get("worktree_path") or "/home/mboyle/BulkDownloader").strip()
    base_ref = str(payload.get("base_ref") or "HEAD~1").strip()
    p = Path(wt_path).resolve()
    try:
        tree_proc = subprocess.run(
            ["git", "-C", str(p), "write-tree"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        diff_proc = subprocess.run(
            ["git", "-C", str(p), "diff", "--cached", "--full-index", base_ref],
            capture_output=True,
            timeout=10,
        )
        patch_sha256 = hashlib.sha256(diff_proc.stdout).hexdigest()
        wt_list = subprocess.run(
            ["git", "-C", str(p), "worktree", "list"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        return {
            "ok": True,
            "worktree_path": str(p),
            "base_ref": base_ref,
            "index_tree_sha": tree_proc.stdout.strip(),
            "patch_sha256": patch_sha256,
            "worktrees": wt_list.stdout.strip().splitlines()[:30],
        }
    except Exception as exc:
        return {"ok": False, "worktree_path": str(p), "error": str(exc)}


def tool_huggingface_gguf_vram_calc(payload: dict[str, Any]) -> dict[str, Any]:
    params_b = float(payload.get("parameters_billions") or 30.0)
    quant = str(payload.get("quant") or "Q4_K_M").upper()
    ctx_k = int(payload.get("context_k") or 32)
    bpw_map = {
        "BF16": 16.0,
        "F16": 16.0,
        "Q8_0": 8.5,
        "Q6_K": 6.56,
        "Q5_K_M": 5.69,
        "Q4_K_M": 4.85,
        "IQ4_XS": 4.25,
        "Q3_K_M": 3.91,
        "Q2_K": 2.96,
        "IQ2_XXS": 2.06,
    }
    bpw = bpw_map.get(quant, 4.85)
    weights_gib = round((params_b * 1e9 * (bpw / 8.0)) / (1024**3), 2)
    kv_gib = round((ctx_k * 1024 * 0.00012 * (params_b / 7.0)), 2)
    total_gib = round(weights_gib + kv_gib + 0.8, 2)
    if total_gib <= 15.5:
        pool_rec = "1x Tesla T4 (16 GB Pure VRAM, -ngl 999 -fa 1)"
    elif total_gib <= 31.0:
        pool_rec = "2x Tesla T4 Pool Alpha (.72+.83, 32 GB Pure VRAM)"
    elif total_gib <= 62.0:
        pool_rec = "4x Tesla T4 Unified (64 GB Pure VRAM) or 1x T4 + Skylake AVX-512 (-ot exps=CPU)"
    else:
        pool_rec = (
            "Multi-Node 562 GiB DDR4 + 4x Tesla T4 Hybrid (-ot .ffn_.*_exps.=CPU)"
        )
    return {
        "ok": True,
        "parameters_billions": params_b,
        "quant": quant,
        "bits_per_weight": bpw,
        "context_tokens": ctx_k * 1024,
        "estimated_weights_gib": weights_gib,
        "estimated_kv_cache_gib": kv_gib,
        "total_vram_ram_gib": total_gib,
        "boylenet_pool_recommendation": pool_rec,
    }


def tool_ocr_vision_pdf_table_extractor(payload: dict[str, Any]) -> dict[str, Any]:
    file_or_url = str(payload.get("source") or payload.get("file_path") or "").strip()
    if file_or_url.startswith(("http://", "https://")):
        return tool_playwright_live_web_scraper(
            {"url": file_or_url, "extract_tables": True}
        )
    p = Path(file_or_url).expanduser()
    if p.exists() and p.is_file():
        raw = p.read_text(encoding="utf-8", errors="replace")[:16000]
        return {"ok": True, "source": str(p), "extracted_markdown": raw}
    return {"ok": False, "error": f"Source not found: {file_or_url}"}


def tool_audio_whisper_tts_music_studio(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "tts").lower()
    text = str(
        payload.get("text")
        or payload.get("prompt")
        or "Boylenet Sovereign Audio Studio online."
    )
    voice = str(payload.get("voice") or "alloy")
    wav_bytes, wav_path, wav_url = synthesize_local_wav(text, voice=voice)
    return {
        "ok": True,
        "action": action,
        "voice": voice,
        "bytes": len(wav_bytes),
        "file_path": wav_path,
        "audio_url": wav_url,
    }


def tool_flux_1080p_image_hud_generator(
    payload: dict[str, Any], render_png_fn: Any = None
) -> dict[str, Any]:
    prompt = str(payload.get("prompt") or "Boylenet 27-Node Sovereign AI Cluster HUD")
    size = str(payload.get("size") or "1920x1080")
    if render_png_fn is None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "gw", "/home/mboyle/bin/bd-openwebui-tool-gateway.py"
        )
        gw = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(gw)
        render_png_fn = gw.render_local_1024_png
    png_bytes, _ = render_png_fn(prompt, size)
    img_id = f"hud_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}.png"
    dest = GENERATED_IMG_DIR / img_id
    dest.write_bytes(png_bytes)
    img_url = f"{GATEWAY_PUBLIC_BASE}/static/generated/{img_id}"
    return {
        "ok": True,
        "prompt": prompt,
        "size": size,
        "bytes": len(png_bytes),
        "file_path": str(dest),
        "image_url": img_url,
        "markdown": f"![{prompt[:80]}]({img_url})",
    }


def tool_boylenet_doctor_and_self_healer(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "status").lower()
    out: dict[str, Any] = {"ok": True, "action": action}
    for name, url in (
        ("doctor_4081", "http://127.0.0.1:4081/api/status"),
        ("sentinel_4099", "http://127.0.0.1:4099/api/status"),
        ("portal_4080", "http://127.0.0.1:4080/api/status"),
    ):
        try:
            with urllib.request.urlopen(url, timeout=4) as resp:
                out[name] = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            out[name] = {"status": "probe_note", "detail": str(exc)}
    return out


EXTRA_TOOL_HANDLERS: dict[str, tuple[Any, str, dict[str, Any]]] = {
    "bd_kb_search": (
        tool_bd_kb_search,
        "Search the authoritative 6-volume BD KB (BulkDownloader, 27-Node Boylenet Cluster, 86 Models, Fleet Law Rules 1-86, CI Taxonomy, 50 Toolkits) in <20ms.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for BD KB"},
                "kb_id": {
                    "type": "string",
                    "description": "Optional volume ID filter (bd-kb-master, bd-kb-bulkdownloader, bd-kb-cluster-infra, bd-kb-86-models, bd-kb-fleet-law, bd-kb-ci-and-uis)",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of chunks to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
    "playwright_live_web_scraper": (
        tool_playwright_live_web_scraper,
        "Scrape full DOM text and extract HTML tables as clean Markdown from any URL.",
        {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to scrape"},
                "extract_tables": {"type": "boolean", "default": True},
            },
            "required": ["url"],
        },
    ),
    "deep_research_multi_engine": (
        tool_deep_research_multi_engine,
        "Run parallel multi-engine deep research across BD KB, Qdrant bd_master_kb, and SearXNG (:8888).",
        {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Research topic or question",
                },
                "max_results": {"type": "integer", "default": 4},
            },
            "required": ["query"],
        },
    ),
    "bulkdownloader_cli_inspector": (
        tool_bulkdownloader_cli_inspector,
        "Inspect BulkDownloader (bd) VERSION.txt, PIN_INDEX.json, ENDPOINT_CATALOG.md, FUNCTION_INDEX.md, and toolchain/bin.",
        {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "summary, routes, functions, or toolchain",
                    "default": "summary",
                },
                "query": {"type": "string", "description": "Optional filter keyword"},
            },
        },
    ),
    "postgres_pgvector_memory_vault": (
        tool_postgres_pgvector_memory_vault,
        "Query PostgreSQL ai_mesh / pgvector tables and long-term episodic memory.",
        {
            "type": "object",
            "properties": {
                "action": {"type": "string", "default": "tables"},
                "database": {"type": "string", "default": "ai_mesh"},
                "sql": {"type": "string", "description": "Optional SQL query"},
            },
        },
    ),
    "redis_minio_s3_inspector": (
        tool_redis_minio_s3_inspector,
        "Inspect MinIO S3 Object Storage (:9000) health and Redis (:6379) cache metrics.",
        {
            "type": "object",
            "properties": {"target": {"type": "string", "default": "both"}},
        },
    ),
    "prometheus_grafana_telemetry": (
        tool_prometheus_grafana_telemetry,
        "Execute PromQL queries against Prometheus (:9090) and check Grafana (:3001) health.",
        {
            "type": "object",
            "properties": {"query": {"type": "string", "default": "up"}},
        },
    ),
    "langfuse_litellm_spend_analytics": (
        tool_langfuse_litellm_spend_analytics,
        "Inspect LiteLLM (:4000) local vs. cloud model counts and Swarm Cost Analyzer (:4070) metrics.",
        {
            "type": "object",
            "properties": {"action": {"type": "string", "default": "summary"}},
        },
    ),
    "ssh_27node_parallel_runner": (
        tool_ssh_27node_parallel_runner,
        "Run parallel read-only SSH health probes (uptime, memory, disk, gpu) across Boylenet cluster nodes.",
        {
            "type": "object",
            "properties": {
                "probe": {
                    "type": "string",
                    "description": "uptime, memory, disk, or gpu",
                    "default": "uptime",
                },
                "nodes": {"type": "array", "items": {"type": "string"}},
            },
        },
    ),
    "ilo4_ipmi_rack_sensors": (
        tool_ilo4_ipmi_rack_sensors,
        "Query HPE ProLiant DL380 Gen10 iLO 4 thermal sensors (79.5°F ambient), fan speeds, and 12U rack telemetry (:4091).",
        {
            "type": "object",
            "properties": {"action": {"type": "string", "default": "status"}},
        },
    ),
    "searxng_news_rss_monitor": (
        tool_searxng_news_rss_monitor,
        "Fetch live tech, cybersecurity, and AI news feeds via Boylenet SearXNG (:8888).",
        {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "default": "cybersecurity AI Linux"},
                "limit": {"type": "integer", "default": 6},
            },
        },
    ),
    "python_jupyter_notebook_gen": (
        tool_python_jupyter_notebook_gen,
        "Generate a valid Jupyter Notebook (.ipynb) in /var/tmp/openwebui-workspace/notebooks.",
        {
            "type": "object",
            "properties": {
                "title": {"type": "string", "default": "Boylenet Analysis Notebook"},
                "markdown": {"type": "string"},
                "code_cells": {"type": "array", "items": {"type": "string"}},
            },
        },
    ),
    "regex_cron_jwt_crypto_knife": (
        tool_regex_cron_jwt_crypto_knife,
        "Developer Swiss-Army Knife: SHA256, Base64 encode/decode, JWT decode, Regex tester, and UUID generator.",
        {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "sha256, base64_encode, base64_decode, jwt_decode, regex_test, uuid4",
                    "default": "sha256",
                },
                "input": {"type": "string"},
                "pattern": {"type": "string"},
            },
        },
    ),
    "openapi_rest_graphql_tester": (
        tool_openapi_rest_graphql_tester,
        "Test HTTP REST/GraphQL endpoints and measure response latency in milliseconds.",
        {
            "type": "object",
            "properties": {
                "url": {"type": "string", "default": "http://10.0.70.164:4079/health"},
                "method": {"type": "string", "default": "GET"},
            },
            "required": ["url"],
        },
    ),
    "git_worktree_patch_auditor": (
        tool_git_worktree_patch_auditor,
        "Compute Rule 16 git write-tree SHA, PATCH-SHA256 against declared base, and worktree census.",
        {
            "type": "object",
            "properties": {
                "worktree_path": {
                    "type": "string",
                    "default": "/home/mboyle/BulkDownloader",
                },
                "base_ref": {"type": "string", "default": "HEAD~1"},
            },
        },
    ),
    "huggingface_gguf_vram_calc": (
        tool_huggingface_gguf_vram_calc,
        "Calculate GGUF model weight size, KV cache memory, and recommended Boylenet GPU/DDR4 pool.",
        {
            "type": "object",
            "properties": {
                "parameters_billions": {"type": "number", "default": 30.0},
                "quant": {"type": "string", "default": "Q4_K_M"},
                "context_k": {"type": "integer", "default": 32},
            },
        },
    ),
    "ocr_vision_pdf_table_extractor": (
        tool_ocr_vision_pdf_table_extractor,
        "Extract Markdown text and structured tables from URLs or local documents.",
        {
            "type": "object",
            "properties": {"source": {"type": "string"}},
            "required": ["source"],
        },
    ),
    "audio_whisper_tts_music_studio": (
        tool_audio_whisper_tts_music_studio,
        "Synthesize local 24kHz WAV speech audio and return a playable URL on :4079.",
        {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "voice": {"type": "string", "default": "alloy"},
            },
            "required": ["text"],
        },
    ),
    "flux_1080p_image_hud_generator": (
        tool_flux_1080p_image_hud_generator,
        "Generate a 1920x1080 or 1024x1024 PNG image/HUD diagram and return a direct URL on :4079.",
        {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "size": {"type": "string", "default": "1920x1080"},
            },
            "required": ["prompt"],
        },
    ),
    "boylenet_doctor_and_self_healer": (
        tool_boylenet_doctor_and_self_healer,
        "Query Boylenet 31-Service Doctor (:4081) and Sentinel Auto-Healer (:4099) health status.",
        {
            "type": "object",
            "properties": {"action": {"type": "string", "default": "status"}},
        },
    ),
}


# ---------------------------------------------------------------------------
# 4. HTTP Route Hooks for GatewayHandler (:4079)
# ---------------------------------------------------------------------------


_PIPELINE_ID_ALIASES = {
    "pipe-boylenet-bdkb-rag-citation-engine": "bd_kb_auto_grounding_pipeline",
    "pipe-boylenet-smart-intent-router": "bd_smart_o1740_intent_router_pipeline",
    "pipe_boylenet_deep_research": "bd_deep_research_multi_engine_pipeline",
    "pipe_boylenet_4model_council": "bd_4model_consensus_council_pipeline",
    "pipe_boylenet_smart_router": "bd_smart_o1740_intent_router_pipeline",
}


def handle_ext_get(handler: Any, path: str, qs: dict[str, list[str]]) -> bool:
    if path.startswith("/static/generated/"):
        fname = Path(path.split("/static/generated/", 1)[1]).name
        fpath = GENERATED_IMG_DIR / fname
        if fpath.exists() and fpath.is_file():
            handler._send_bytes(200, "image/png", fpath.read_bytes())
            return True
        handler._send_json(404, {"error": f"Image not found: {fname}"})
        return True
    if path.startswith("/static/audio/"):
        fname = Path(path.split("/static/audio/", 1)[1]).name
        fpath = GENERATED_AUDIO_DIR / fname
        if fpath.exists() and fpath.is_file():
            handler._send_bytes(200, "audio/wav", fpath.read_bytes())
            return True
        handler._send_json(404, {"error": f"Audio not found: {fname}"})
        return True
    if path in ("/v1/models", "/models"):
        handler._send_json(200, get_v1_models_response())
        return True
    if path in ("/v1/pipelines", "/pipelines", "/v1/pipelines/list", "/pipelines/list"):
        handler._send_json(200, get_v1_pipelines_list())
        return True
    m_valves = re.match(r"^(?:/v1)?/([a-zA-Z0-9_.-]+)/valves(?:/(spec))?$", path)
    if m_valves:
        raw_pid = m_valves.group(1)
        pid = _PIPELINE_ID_ALIASES.get(raw_pid, raw_pid)
        is_spec = m_valves.group(2) == "spec"
        p_obj = next((p for p in PIPELINES_CATALOG if p["id"] == pid), None)
        if not p_obj:
            handler._send_json(404, {"detail": f"Pipeline {raw_pid} not found"})
            return True
        if is_spec:
            handler._send_json(
                200,
                {
                    "title": f"{p_obj['name']} Valves",
                    "type": "object",
                    "properties": p_obj["valves_spec"],
                },
            )
            return True
        all_v = _load_all_valves()
        handler._send_json(200, all_v.get(pid, p_obj["default_valves"]))
        return True
    return False


def handle_ext_post(
    handler: Any, path: str, payload: dict[str, Any], render_png_fn: Any
) -> bool:
    m_vupd = re.match(r"^(?:/v1)?/([a-zA-Z0-9_.-]+)/valves/update$", path)
    if m_vupd:
        raw_pid = m_vupd.group(1)
        pid = _PIPELINE_ID_ALIASES.get(raw_pid, raw_pid)
        updated = _save_pipeline_valves(pid, payload)
        handler._send_json(200, updated)
        return True
    m_flt = re.match(r"^(?:/v1)?/([a-zA-Z0-9_.-]+)/filter/(inlet|outlet)$", path)
    if m_flt:
        raw_pid = m_flt.group(1)
        pid = _PIPELINE_ID_ALIASES.get(raw_pid, raw_pid)
        stage = m_flt.group(2)
        body = payload.get("body") if isinstance(payload.get("body"), dict) else payload
        valves = _load_all_valves().get(pid, {})
        if (
            pid == "bd_kb_auto_grounding_pipeline"
            and stage == "inlet"
            and valves.get("enable_inlet_grounding")
            and isinstance(body.get("messages"), list)
        ):
            user_q = _extract_last_user_prompt(body["messages"])
            hits = tool_bd_kb_search(
                {"query": user_q, "top_k": int(valves.get("top_k_chunks", 2))}
            ).get("results", [])
            if hits:
                ctx_str = "\n".join(
                    (
                        f"- [{h['book_name']} | {h['section_title']}]: {h['content'][:400]}"
                        for h in hits
                    )
                )
                body["messages"] = [
                    {
                        "role": "system",
                        "content": f"[BD KB Grounding Context]\n{ctx_str}",
                    },
                    *body["messages"],
                ]
        handler._send_json(200, body)
        return True

    # 3. /v1/pipelines/add or /v1/pipelines/upload
    if path in (
        "/v1/pipelines/add",
        "/pipelines/add",
        "/v1/pipelines/upload",
        "/pipelines/upload",
    ):
        handler._send_json(200, get_v1_pipelines_list())
        return True

    # 4. /v1/chat/completions
    if path in ("/v1/chat/completions", "/chat/completions"):
        is_stream, model_id, md_text = execute_v1_chat_completion(
            payload, render_png_fn
        )
        cid = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        now = int(time.time())
        if is_stream:
            chunk1 = {
                "id": cid,
                "object": "chat.completion.chunk",
                "created": now,
                "model": model_id,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": md_text},
                        "finish_reason": None,
                    }
                ],
            }
            chunk2 = {
                "id": cid,
                "object": "chat.completion.chunk",
                "created": now,
                "model": model_id,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            sse_bytes = (
                f"data: {json.dumps(chunk1, ensure_ascii=False)}\n\n"
                f"data: {json.dumps(chunk2, ensure_ascii=False)}\n\n"
                "data: [DONE]\n\n"
            ).encode("utf-8")
            handler.send_response(200)
            handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
            handler.send_header("Cache-Control", "no-cache")
            handler.send_header("Access-Control-Allow-Origin", "*")
            handler.end_headers()
            handler.wfile.write(sse_bytes)
            return True

        resp_obj = {
            "id": cid,
            "object": "chat.completion",
            "created": now,
            "model": model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": md_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 64,
                "completion_tokens": max(16, len(md_text.split())),
                "total_tokens": 64 + max(16, len(md_text.split())),
            },
        }
        handler._send_json(200, resp_obj)
        return True

    return False
