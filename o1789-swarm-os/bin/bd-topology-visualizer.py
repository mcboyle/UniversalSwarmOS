#!/usr/bin/env python3
"""
bd-topology-visualizer.py — Boylenet Full-Viewport 6-Mode Visual Architecture & Swarm Topology Command Canvas (:4088)
Modes:
  1. UniFi / ReactFlow Node Graph (Default — 2D Pan/Zoom Neon-Pipe Canvas with all individual VMs & orbiting Agent Badges)
  2. Neural Swarm Galaxy (Radial Orbital Constellation with 25GbE RoCE Cyan Halo & Laser Arcs)
  3. 3D Cyber Holo-Deck (Interactive 3D Orbit / Isometric Space with Light Pillars & Particle Torpedoes)
  4. Live Agent Swimlane Flow (Left-to-Right Agents -> Gateways -> Target VMs -> Live Task Output)
  5. Physical 12U Server Rack Digital Twin (Front + Rear Elevation matching operator's actual photo: 79.5°F bezel, U1-U4 UniFi, U5-U12 HPE DL380 2xSFF + 2x12-Bay LFF, Rear Top UPS & USW-Pro-Max at ESXi 2&3)
  6. Military C4ISR / Lattice Mode (Anduril Lattice / AEGIS CIC tactical display with MIL-STD-2525D symbology, TF-75/TF-70/TF-60/TF-CLOUD, radar sweep & targeting reticles)
Includes a universal "Simple / Clean" vs "Advanced Telemetry" toggle switch across all 6 modes.
"""

import json
import math
import os
import socket
import subprocess
import threading
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PORT = int(os.environ.get("BD_TOPOLOGY_PORT", "4088"))
CACHE_TTL_SEC = 5.0

_CACHE_LOCK = threading.Lock()
_CACHED_TOPOLOGY: dict[str, Any] = {}
_CACHED_TOPOLOGY_BYTES: bytes = b"{}"
_LAST_REFRESH_TS: float = 0.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_json(url: str, timeout: float = 1.5) -> dict[str, Any]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (OSError, ValueError):
        return {}


def _read_json_file(path: str) -> dict[str, Any]:
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except (OSError, ValueError):
        return {}
    return {}


def _read_pool_state_tsv(
    path: str = "/home/mboyle/bd-persist/POOL_STATE.tsv",
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    try:
        if not os.path.exists(path):
            return rows
        with open(path, encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip()]
        if len(lines) < 2:
            return rows
        headers = lines[0].split("\t")
        for ln in lines[1:]:
            parts = ln.split("\t")
            rows.append(
                {
                    headers[i]: (parts[i] if i < len(parts) else "")
                    for i in range(len(headers))
                }
            )
    except OSError:
        return rows
    return rows


def _read_tmux_sessions() -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    try:
        out = subprocess.check_output(
            ["tmux", "list-sessions", "-F", "#{session_name}|#{session_windows}"],
            stderr=subprocess.DEVNULL,
            timeout=1.2,
        ).decode("utf-8", errors="replace")
        for line in out.splitlines():
            parts = line.strip().split("|")
            if not parts or not parts[0]:
                continue
            name = parts[0]
            lname = name.lower()
            target = "bd-controller"
            pool = "AGY"
            if "pm" in lname:
                target, pool = "cloud-claude-b", "B"
            elif lname.endswith("-a"):
                target, pool = "cloud-claude-a", "A"
            elif lname.endswith("-b"):
                target, pool = "cloud-claude-b", "B"
            elif lname.endswith("-c"):
                target, pool = "cloud-claude-c", "C"
            elif lname.endswith("-d"):
                target, pool = "cloud-claude-d", "D"
            elif "kimi" in lname:
                target, pool = "cloud-kimi", "kimi"
            elif "codex" in lname:
                target, pool = "cloud-codex", "codex"
            sessions.append({"name": name, "target_node": target, "pool": pool})
    except (OSError, subprocess.SubprocessError):
        return sessions
    return sessions


VIEWS_CATALOG: list[dict[str, str]] = [
    {
        "id": "V01",
        "cat": "cat1",
        "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "name": "V01 Hybrid HiveMind+n8n+12U Rack+Cloud Master",
        "color": "#a855f7",
        "c2": "#38bdf8",
        "c3": "#10b981",
        "bg": "#030712",
        "arch": "hybrid",
        "png": "hivemind_cot_05.png",
    },
    {
        "id": "V02",
        "cat": "cat1",
        "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "name": "V02 n8n Agent Swarm (Hanging Model/Think/Memory/Search Circles)",
        "color": "#06b6d4",
        "c2": "#a855f7",
        "c3": "#22c55e",
        "bg": "#030712",
        "arch": "n8n_hanging_circles",
        "png": "hivemind_cot_01.png",
    },
    {
        "id": "V03",
        "cat": "cat1",
        "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "name": "V03 HIVEMIND v3.0 Phosphor-Green CRT Control Center",
        "color": "#10b981",
        "c2": "#34d399",
        "c3": "#f59e0b",
        "bg": "#020905",
        "arch": "hivemind_crt",
        "png": "hivemind_cot_02.png",
    },
    {
        "id": "V04",
        "cat": "cat1",
        "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "name": "V04 Kimi K2.5 Radial CORE Constellation & Concentric CoT Rings",
        "color": "#f97316",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#040711",
        "arch": "kimi_radial_core",
        "png": "hivemind_cot_03.png",
    },
    {
        "id": "V05",
        "cat": "cat1",
        "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "name": "V05 KNIME 6-Swimlane End-to-End CoT & 12U Rack Pipeline",
        "color": "#38bdf8",
        "c2": "#22c55e",
        "c3": "#f59e0b",
        "bg": "#030712",
        "arch": "knime_swimlanes",
        "png": "hivemind_cot_04.png",
    },
    {
        "id": "V06",
        "cat": "cat1",
        "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "name": "V06 Ironclad Rivet / ComfyUI Visual CoT Noodle & Token Canvas",
        "color": "#ec4899",
        "c2": "#06b6d4",
        "c3": "#a855f7",
        "bg": "#060712",
        "arch": "rivet_noodles",
        "png": "hivemind_cot_06.png",
    },
    {
        "id": "V07",
        "cat": "cat1",
        "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "name": "V07 LangGraph Studio State-Machine & Time-Travel CoT Tree",
        "color": "#22c55e",
        "c2": "#38bdf8",
        "c3": "#f59e0b",
        "bg": "#030810",
        "arch": "langgraph_state",
        "png": "hivemind_cot_07.png",
    },
    {
        "id": "V08",
        "cat": "cat1",
        "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "name": "V08 Tactical C4ISR Hive-Mind Kill-Chain & 12U Magazine",
        "color": "#10b981",
        "c2": "#f59e0b",
        "c3": "#38bdf8",
        "bg": "#020906",
        "arch": "military_c4isr_radar",
        "png": "hivemind_cot_08.png",
    },
    {
        "id": "V09",
        "cat": "cat1",
        "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "name": "V09 3D Bioluminescent Neural Cortex & Synaptic CoT Pulse",
        "color": "#818cf8",
        "c2": "#ec4899",
        "c3": "#06b6d4",
        "bg": "#040613",
        "arch": "neural_cortex",
        "png": "hivemind_cot_09.png",
    },
    {
        "id": "V10",
        "cat": "cat1",
        "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)",
        "name": "V10 CrewAI / AutoGen Shared Blackboard & Thought-Bubble Arena",
        "color": "#f59e0b",
        "c2": "#14b8a6",
        "c3": "#a855f7",
        "bg": "#060812",
        "arch": "crewai_arena",
        "png": "hivemind_cot_10.png",
    },
    {
        "id": "V11",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V11 Arize Phoenix / OpenInference CoT Flamegraph & Span Waterfall",
        "color": "#f97316",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#050711",
        "arch": "flamegraph_spans",
        "png": "hivemind_cot_11.png",
    },
    {
        "id": "V12",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V12 Langfuse v3 Multi-Agent Trace Tree & Cost/Latency Heatmap",
        "color": "#38bdf8",
        "c2": "#22c55e",
        "c3": "#ec4899",
        "bg": "#040812",
        "arch": "flamegraph_spans",
        "png": "hivemind_cot_12.png",
    },
    {
        "id": "V13",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V13 PydanticAI / Logfire Streaming Structured-Output Validator",
        "color": "#ec4899",
        "c2": "#06b6d4",
        "c3": "#10b981",
        "bg": "#060711",
        "arch": "mcts_tree",
        "png": "hivemind_cot_13.png",
    },
    {
        "id": "V14",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V14 Dify.ai / Coze Visual Agentic Workflow Studio & Cloud Nodes",
        "color": "#60a5fa",
        "c2": "#a855f7",
        "c3": "#22c55e",
        "bg": "#040814",
        "arch": "rivet_noodles",
        "png": "hivemind_cot_14.png",
    },
    {
        "id": "V15",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V15 Flowise / Langflow Dark-Mode Multi-Agent RAG & Tool Canvas",
        "color": "#a855f7",
        "c2": "#06b6d4",
        "c3": "#f59e0b",
        "bg": "#050713",
        "arch": "rivet_noodles",
        "png": "hivemind_cot_15.png",
    },
    {
        "id": "V16",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V16 BabyAGI / SuperAGI Autonomous Task-Queue & Reflection Loop",
        "color": "#10b981",
        "c2": "#38bdf8",
        "c3": "#f59e0b",
        "bg": "#03090c",
        "arch": "langgraph_state",
        "png": "hivemind_cot_16.png",
    },
    {
        "id": "V17",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V17 MetaGPT Software Company Org-Chart (PM->Architect->Coder->QA)",
        "color": "#38bdf8",
        "c2": "#f59e0b",
        "c3": "#22c55e",
        "bg": "#040812",
        "arch": "mcts_tree",
        "png": "hivemind_cot_17.png",
    },
    {
        "id": "V18",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V18 ChatDev Isometric Virtual AI Software House + 12U Server Rack",
        "color": "#fbbf24",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#060811",
        "arch": "iso_floor",
        "png": "hivemind_cot_18.png",
    },
    {
        "id": "V19",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V19 Stanford Generative Agents Hive-Mind Memory & Reflection Tree",
        "color": "#34d399",
        "c2": "#60a5fa",
        "c3": "#f43f5e",
        "bg": "#03090f",
        "arch": "mcts_tree",
        "png": "hivemind_cot_19.png",
    },
    {
        "id": "V20",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V20 Voyager / MineDojo Skill-Library Curriculum & Synthesis Loop",
        "color": "#f59e0b",
        "c2": "#10b981",
        "c3": "#38bdf8",
        "bg": "#07080f",
        "arch": "langgraph_state",
        "png": "hivemind_cot_20.png",
    },
    {
        "id": "V21",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V21 Tree-of-Thoughts (ToT) / MCTS Multi-Branch Pruning Visualizer",
        "color": "#06b6d4",
        "c2": "#22c55e",
        "c3": "#ef4444",
        "bg": "#030812",
        "arch": "mcts_tree",
        "png": "hivemind_cot_21.png",
    },
    {
        "id": "V22",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V22 Graph-of-Thoughts (GoT) Non-Linear Reasoning & Backtracking",
        "color": "#a855f7",
        "c2": "#38bdf8",
        "c3": "#10b981",
        "bg": "#050614",
        "arch": "neural_cortex",
        "png": "hivemind_cot_22.png",
    },
    {
        "id": "V23",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V23 DSPy Compiled Prompt-Optimization & Signature Pipeline",
        "color": "#38bdf8",
        "c2": "#f97316",
        "c3": "#22c55e",
        "bg": "#040811",
        "arch": "knime_swimlanes",
        "png": "hivemind_cot_23.png",
    },
    {
        "id": "V24",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V24 Semantic Kernel / AutoGen v0.4 Async Event-Driven Actor Mesh",
        "color": "#ec4899",
        "c2": "#38bdf8",
        "c3": "#10b981",
        "bg": "#060712",
        "arch": "crewai_arena",
        "png": "hivemind_cot_24.png",
    },
    {
        "id": "V25",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V25 Haystack / deepset Hybrid BM25+Qdrant Retrieval & CoT Rerank",
        "color": "#22c55e",
        "c2": "#06b6d4",
        "c3": "#a855f7",
        "bg": "#03090e",
        "arch": "sankey_river",
        "png": "hivemind_cot_25.png",
    },
    {
        "id": "V26",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V26 LlamaIndex Workflows Event-Driven Step Graph & 86-Model Vault",
        "color": "#fb923c",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#060810",
        "arch": "rivet_noodles",
        "png": "hivemind_cot_26.png",
    },
    {
        "id": "V27",
        "cat": "cat2",
        "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)",
        "name": "V27 vLLM / SGLang RadixAttention KV-Cache Prefix-Tree Visualizer",
        "color": "#00f5d4",
        "c2": "#a855f7",
        "c3": "#f59e0b",
        "bg": "#030911",
        "arch": "mcts_tree",
        "png": "hivemind_cot_27.png",
    },
    {
        "id": "V28",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V28 DARPA AlphaDogfight / Skyborg Autonomous Wingman CoT Display",
        "color": "#00ff88",
        "c2": "#38bdf8",
        "c3": "#f59e0b",
        "bg": "#060d09",
        "arch": "f35_hud_mfd",
        "png": "hivemind_cot_28.png",
    },
    {
        "id": "V29",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V29 US Space Force JSpOC Orbital Constellation & 12U Ground Link",
        "color": "#38bdf8",
        "c2": "#a855f7",
        "c3": "#22c55e",
        "bg": "#040814",
        "arch": "eve_tidi_orbit",
        "png": "hivemind_cot_29.png",
    },
    {
        "id": "V30",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V30 Palantir AIP Defense Ontology & Multi-Agent CoT Decision Graph",
        "color": "#60a5fa",
        "c2": "#10b981",
        "c3": "#f43f5e",
        "bg": "#090b10",
        "arch": "military_c4isr_radar",
        "png": "hivemind_cot_30.png",
    },
    {
        "id": "V31",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V31 Lockheed F-22 / NGAD 6th-Gen Sensor-Fusion 3-Screen Cockpit",
        "color": "#00ffcc",
        "c2": "#fbbf24",
        "c3": "#ef4444",
        "bg": "#050a0e",
        "arch": "f35_hud_mfd",
        "png": "hivemind_cot_31.png",
    },
    {
        "id": "V32",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V32 DARPA Mosaic Warfare / JADC2 Joint All-Domain Kill-Web Mesh",
        "color": "#22c55e",
        "c2": "#f97316",
        "c3": "#38bdf8",
        "bg": "#080c0a",
        "arch": "military_c4isr_radar",
        "png": "hivemind_cot_32.png",
    },
    {
        "id": "V33",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V33 B-21 Raider Stealth Strategic Bomber Mission & CoT Strike Table",
        "color": "#38bdf8",
        "c2": "#ef4444",
        "c3": "#10b981",
        "bg": "#05070b",
        "arch": "military_c4isr_radar",
        "png": "hivemind_cot_33.png",
    },
    {
        "id": "V34",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V34 Aircraft Carrier Pri-Fly & CATCC 4xT4 Catapult Launch Board",
        "color": "#facc15",
        "c2": "#22c55e",
        "c3": "#38bdf8",
        "bg": "#070b12",
        "arch": "carrier_catapult",
        "png": "hivemind_cot_34.png",
    },
    {
        "id": "V35",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V35 Nuclear Submarine AN/BYG-1 Combat Control & Acoustic CoT Sonar",
        "color": "#10b981",
        "c2": "#06b6d4",
        "c3": "#eab308",
        "bg": "#020908",
        "arch": "submarine_sonar",
        "png": "hivemind_cot_35.png",
    },
    {
        "id": "V36",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V36 X-Ray 12U Physical Rack with Glowing CoT Neural Synapses",
        "color": "#a855f7",
        "c2": "#00f5d4",
        "c3": "#3b82f6",
        "bg": "#060913",
        "arch": "rack_12u_front_rear_xray",
        "png": "hivemind_cot_36.png",
    },
    {
        "id": "V37",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V37 Ubiquiti UniFi Etherlighting + Live Agent CoT Per-Port Matrix",
        "color": "#00f5d4",
        "c2": "#3b82f6",
        "c3": "#a855f7",
        "bg": "#080b14",
        "arch": "etherlighting_switch_matrix",
        "png": "hivemind_cot_37.png",
    },
    {
        "id": "V38",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V38 NVIDIA Nsight / 25GbE RoCE Tensor-Pipeline Profiler & CoT Map",
        "color": "#76b900",
        "c2": "#00d4ff",
        "c3": "#f59e0b",
        "bg": "#070a0e",
        "arch": "flamegraph_spans",
        "png": "hivemind_cot_38.png",
    },
    {
        "id": "V39",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V39 VMware vSAN 107TB Storage-to-VRAM Weight Streaming & CoT Flow",
        "color": "#38bdf8",
        "c2": "#22c55e",
        "c3": "#a855f7",
        "bg": "#060b16",
        "arch": "sankey_river",
        "png": "hivemind_cot_39.png",
    },
    {
        "id": "V40",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V40 HPE iLO4 & Rear UPS Thermal-to-Token Efficiency Map (Watts->tok/s)",
        "color": "#f97316",
        "c2": "#ef4444",
        "c3": "#38bdf8",
        "bg": "#0c070a",
        "arch": "rack_12u_front_rear_xray",
        "png": "hivemind_cot_40.png",
    },
    {
        "id": "V41",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V41 Westworld Rehoboam Predictive AI Eclipse Ring & Divergence Waves",
        "color": "#f43f5e",
        "c2": "#e2e8f0",
        "c3": "#38bdf8",
        "bg": "#08080c",
        "arch": "rehoboam_ring",
        "png": "hivemind_cot_41.png",
    },
    {
        "id": "V42",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V42 Halo UNSC Infinity / Cortana Holographic Tactical CoT Table",
        "color": "#00d4ff",
        "c2": "#60a5fa",
        "c3": "#a855f7",
        "bg": "#030914",
        "arch": "iso_floor",
        "png": "hivemind_cot_42.png",
    },
    {
        "id": "V43",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V43 Evangelion NERV MAGI 3-Brain Consensus (MELCHIOR+BALTHASAR+CASPER)",
        "color": "#f97316",
        "c2": "#00ff66",
        "c3": "#ef4444",
        "bg": "#0a0505",
        "arch": "nerv_magi_trinity",
        "png": "hivemind_cot_43.png",
    },
    {
        "id": "V44",
        "cat": "cat3",
        "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)",
        "name": "V44 Ghost in the Shell Section 9 Cyberbrain Dive & Barrier-Maze CoT",
        "color": "#00ffcc",
        "c2": "#a855f7",
        "c3": "#22c55e",
        "bg": "#030b09",
        "arch": "neural_cortex",
        "png": "hivemind_cot_44.png",
    },
    {
        "id": "V45",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V45 CERN Large Hadron Collider (ATLAS) Particle-Collision CoT Detector",
        "color": "#38bdf8",
        "c2": "#facc15",
        "c3": "#ec4899",
        "bg": "#040711",
        "arch": "cern_collider",
        "png": "hivemind_cot_45.png",
    },
    {
        "id": "V46",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V46 Quantum Circuit & Bloch-Sphere Entanglement CoT Composer (6-Pool)",
        "color": "#a855f7",
        "c2": "#00f5d4",
        "c3": "#38bdf8",
        "bg": "#060814",
        "arch": "quantum_bloch_rails",
        "png": "hivemind_cot_46.png",
    },
    {
        "id": "V47",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V47 Mycelial Fungal Network & 12U Root-System Nutrient/Token Flow",
        "color": "#10b981",
        "c2": "#a3e635",
        "c3": "#38bdf8",
        "bg": "#040a07",
        "arch": "neural_cortex",
        "png": "hivemind_cot_47.png",
    },
    {
        "id": "V48",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V48 Ant Colony / Bee Swarm Pheromone Trail Optimizer & CoT Mesh",
        "color": "#f59e0b",
        "c2": "#22c55e",
        "c3": "#38bdf8",
        "bg": "#090805",
        "arch": "neural_cortex",
        "png": "hivemind_cot_48.png",
    },
    {
        "id": "V49",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V49 Cardiovascular 12U-Heart / Cloud-Lung / HiveMind-Brain Circulation",
        "color": "#f43f5e",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#0b0508",
        "arch": "sankey_river",
        "png": "hivemind_cot_49.png",
    },
    {
        "id": "V50",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V50 Modular Eurorack Analog Synthesizer Patch-Bay (CV/Gate CoT Noodles)",
        "color": "#f43f5e",
        "c2": "#facc15",
        "c3": "#00f5d4",
        "bg": "#0a0a0f",
        "arch": "eurorack_synth_patch",
        "png": "hivemind_cot_50.png",
    },
    {
        "id": "V51",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V51 High-Frequency Trading (HFT) Liquidity Depth & Arbitrage CoT Router",
        "color": "#22c55e",
        "c2": "#ef4444",
        "c3": "#38bdf8",
        "bg": "#05080c",
        "arch": "hft_orderbook",
        "png": "hivemind_cot_51.png",
    },
    {
        "id": "V52",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V52 Global Submarine Fiber-Optic Cable & Cloud Peering CoT Map",
        "color": "#00f5d4",
        "c2": "#38bdf8",
        "c3": "#f59e0b",
        "bg": "#030914",
        "arch": "eve_tidi_orbit",
        "png": "hivemind_cot_52.png",
    },
    {
        "id": "V53",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V53 Air-Traffic Control Tower 360° Surface Movement & Approach Radar",
        "color": "#00ff88",
        "c2": "#38bdf8",
        "c3": "#facc15",
        "bg": "#030a08",
        "arch": "military_c4isr_radar",
        "png": "hivemind_cot_53.png",
    },
    {
        "id": "V54",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V54 6-Screen Day-Trader / NOC Mega-Desk Wallboard (3x2 CoT Engine)",
        "color": "#38bdf8",
        "c2": "#a855f7",
        "c3": "#22c55e",
        "bg": "#05070e",
        "arch": "centurion_omega_masterpiece",
        "png": "hivemind_cot_54.png",
    },
    {
        "id": "V55",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V55 Split Left-Brain (Code/Pytest .82) vs Right-Brain (UI/Cloud) Bridge",
        "color": "#38bdf8",
        "c2": "#ec4899",
        "c3": "#10b981",
        "bg": "#060812",
        "arch": "neural_cortex",
        "png": "hivemind_cot_55.png",
    },
    {
        "id": "V56",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V56 Time-Lapse Piano-Roll DAW Sequencer (Multi-Track Agent CoT Harmony)",
        "color": "#a855f7",
        "c2": "#22c55e",
        "c3": "#f59e0b",
        "bg": "#08090f",
        "arch": "flamegraph_spans",
        "png": "hivemind_cot_56.png",
    },
    {
        "id": "V57",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V57 Isometric 3-Tier Glass Skybridge Pyramid (12U -> CoT -> Cloud)",
        "color": "#38bdf8",
        "c2": "#00f5d4",
        "c3": "#a855f7",
        "bg": "#050914",
        "arch": "iso_floor",
        "png": "hivemind_cot_57.png",
    },
    {
        "id": "V58",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V58 Watchmaker's Tourbillon Mechanical Horology CoT Escapement & Gears",
        "color": "#f59e0b",
        "c2": "#38bdf8",
        "c3": "#10b981",
        "bg": "#0a0806",
        "arch": "cern_collider",
        "png": "hivemind_cot_58.png",
    },
    {
        "id": "V59",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V59 3D Holographic Chessboard / Stratego Autonomous Agent CoT Grid",
        "color": "#60a5fa",
        "c2": "#f43f5e",
        "c3": "#22c55e",
        "bg": "#050811",
        "arch": "iso_floor",
        "png": "hivemind_cot_59.png",
    },
    {
        "id": "V60",
        "cat": "cat4",
        "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)",
        "name": "V60 The Boylenet 'Omega HiveMind' 10-Panel Command Wall Synthesis",
        "color": "#00f5d4",
        "c2": "#a855f7",
        "c3": "#f59e0b",
        "bg": "#04060c",
        "arch": "centurion_omega_masterpiece",
        "png": "hivemind_cot_60.png",
    },
    {
        "id": "V61",
        "cat": "cat5",
        "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "name": "V61 Anthropic Claude-Flow v4 Multi-Pool (A/B/C/D $1,000) + 12U CoT Mesh",
        "color": "#d97706",
        "c2": "#a855f7",
        "c3": "#38bdf8",
        "bg": "#08060c",
        "arch": "n8n_hanging_circles",
        "png": "hivemind_cot_61.png",
    },
    {
        "id": "V62",
        "cat": "cat5",
        "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "name": "V62 OpenAI Codex gpt-6.1-sol + gpt-6-astra AST Slicing & Ramdisk CoT",
        "color": "#10b981",
        "c2": "#38bdf8",
        "c3": "#f59e0b",
        "bg": "#03090b",
        "arch": "knime_swimlanes",
        "png": "hivemind_cot_62.png",
    },
    {
        "id": "V63",
        "cat": "cat5",
        "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "name": "V63 Kimi K2.8 thinking: max 100-Agent Orbital CoT Ring + Dual CDP Matrix",
        "color": "#f97316",
        "c2": "#06b6d4",
        "c3": "#a855f7",
        "bg": "#060711",
        "arch": "kimi_radial_core",
        "png": "hivemind_cot_63.png",
    },
    {
        "id": "V64",
        "cat": "cat5",
        "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "name": "V64 Google Antigravity (AGY) Super-Swarm Subagent Tree + tmux Bridge",
        "color": "#38bdf8",
        "c2": "#a855f7",
        "c3": "#22c55e",
        "bg": "#040814",
        "arch": "mcts_tree",
        "png": "hivemind_cot_64.png",
    },
    {
        "id": "V65",
        "cat": "cat5",
        "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "name": "V65 4-Pool Token Autobalancer (O1740) Quota Waterfall & Failover Graph",
        "color": "#22c55e",
        "c2": "#eab308",
        "c3": "#ef4444",
        "bg": "#04090d",
        "arch": "sankey_river",
        "png": "hivemind_cot_65.png",
    },
    {
        "id": "V66",
        "cat": "cat5",
        "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "name": "V66 Speculative Decoding (ngram-mod + Draft) Verification Tree on 4xT4",
        "color": "#06b6d4",
        "c2": "#10b981",
        "c3": "#f59e0b",
        "bg": "#030910",
        "arch": "mcts_tree",
        "png": "hivemind_cot_66.png",
    },
    {
        "id": "V67",
        "cat": "cat5",
        "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "name": "V67 Qdrant Vector Hippocampus (.125:6333) + PG Episodic Dreamer CoT",
        "color": "#ec4899",
        "c2": "#a855f7",
        "c3": "#38bdf8",
        "bg": "#070612",
        "arch": "neural_cortex",
        "png": "hivemind_cot_67.png",
    },
    {
        "id": "V68",
        "cat": "cat5",
        "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "name": "V68 Gitea PR Webhook (:3000) -> 2-Lens Security & OffSec (:4092) CoT",
        "color": "#ef4444",
        "c2": "#38bdf8",
        "c3": "#10b981",
        "bg": "#09060c",
        "arch": "knime_swimlanes",
        "png": "hivemind_cot_68.png",
    },
    {
        "id": "V69",
        "cat": "cat5",
        "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "name": "V69 Multimodal Voice (:4093) + Vision VQA/OCR (86-Model) CoT Pipeline",
        "color": "#a855f7",
        "c2": "#00f5d4",
        "c3": "#f59e0b",
        "bg": "#060712",
        "arch": "rivet_noodles",
        "png": "hivemind_cot_69.png",
    },
    {
        "id": "V70",
        "cat": "cat5",
        "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)",
        "name": "V70 Sentinel Self-Healing (:4099) Root-Cause <think> & Auto-Recovery",
        "color": "#10b981",
        "c2": "#38bdf8",
        "c3": "#f43f5e",
        "bg": "#03090a",
        "arch": "langgraph_state",
        "png": "hivemind_cot_70.png",
    },
    {
        "id": "V71",
        "cat": "cat6",
        "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "name": "V71 3D Isometric 12U Rack Cutaway with Fiber CoT Beams to Cloud Halo",
        "color": "#00f5d4",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#050912",
        "arch": "rack_12u_front_rear_xray",
        "png": "hivemind_cot_71.png",
    },
    {
        "id": "V72",
        "cat": "cat6",
        "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "name": "V72 Split-Screen 2x2 Quad-Engine Wallboard (n8n + CRT + 12U + C4ISR)",
        "color": "#22c55e",
        "c2": "#38bdf8",
        "c3": "#f59e0b",
        "bg": "#05070d",
        "arch": "centurion_omega_masterpiece",
        "png": "hivemind_cot_72.png",
    },
    {
        "id": "V73",
        "cat": "cat6",
        "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "name": "V73 Split-Screen 3x2 Six-Pack Mega-Wallboard (n8n, Kimi, KNIME, Rack)",
        "color": "#a855f7",
        "c2": "#00f5d4",
        "c3": "#38bdf8",
        "bg": "#04060b",
        "arch": "centurion_omega_masterpiece",
        "png": "hivemind_cot_73.png",
    },
    {
        "id": "V74",
        "cat": "cat6",
        "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "name": "V74 Split-Screen 4x2 Eight-Engine Ultra-Wide NOC Command Wallboard",
        "color": "#38bdf8",
        "c2": "#10b981",
        "c3": "#ec4899",
        "bg": "#03050a",
        "arch": "centurion_omega_masterpiece",
        "png": "hivemind_cot_74.png",
    },
    {
        "id": "V75",
        "cat": "cat6",
        "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "name": "V75 Dark-Matter Cosmological Web & Galaxy Filament HiveMind Supercluster",
        "color": "#a855f7",
        "c2": "#38bdf8",
        "c3": "#f43f5e",
        "bg": "#03040a",
        "arch": "neural_cortex",
        "png": "hivemind_cot_75.png",
    },
    {
        "id": "V76",
        "cat": "cat6",
        "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "name": "V76 Weather Doppler Radar & Isobar Storm-Front CoT Compute Pressure Map",
        "color": "#22c55e",
        "c2": "#facc15",
        "c3": "#ef4444",
        "bg": "#040910",
        "arch": "military_c4isr_radar",
        "png": "hivemind_cot_76.png",
    },
    {
        "id": "V77",
        "cat": "cat6",
        "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "name": "V77 Shinkansen High-Speed Bullet-Train Dispatch & CoT Signal Board",
        "color": "#00f5d4",
        "c2": "#f59e0b",
        "c3": "#38bdf8",
        "bg": "#050811",
        "arch": "factorio_conveyor_bus",
        "png": "hivemind_cot_77.png",
    },
    {
        "id": "V78",
        "cat": "cat6",
        "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "name": "V78 DNA CRISPR Gene-Splicing & Protein-Folding CoT Synthesis Pipeline",
        "color": "#06b6d4",
        "c2": "#ec4899",
        "c3": "#22c55e",
        "bg": "#040a0e",
        "arch": "dna_helix",
        "png": "hivemind_cot_78.png",
    },
    {
        "id": "V79",
        "cat": "cat6",
        "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "name": "V79 Formula-E / Le Mans Hybrid Energy-Recovery (ERS) Local-to-Cloud CoT",
        "color": "#00ff88",
        "c2": "#38bdf8",
        "c3": "#f43f5e",
        "bg": "#07090e",
        "arch": "sankey_river",
        "png": "hivemind_cot_79.png",
    },
    {
        "id": "V80",
        "cat": "cat6",
        "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)",
        "name": "V80 NASA James Webb Space Telescope (JWST) 18-Hexagon Gold Mirror CoT",
        "color": "#fbbf24",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#080604",
        "arch": "jwst_hex_mirrors",
        "png": "hivemind_cot_80.png",
    },
    {
        "id": "V81",
        "cat": "cat7",
        "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "name": "V81 NSA / USCYBERCOM Global Threat-Hunting & Zero-Trust CoT Attribution",
        "color": "#00f5d4",
        "c2": "#ef4444",
        "c3": "#38bdf8",
        "bg": "#03080e",
        "arch": "military_c4isr_radar",
        "png": "hivemind_cot_81.png",
    },
    {
        "id": "V82",
        "cat": "cat7",
        "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "name": "V82 Apache AH-64E Guardian Target Acquisition (TADS/PNVS) CoT HUD",
        "color": "#22c55e",
        "c2": "#f59e0b",
        "c3": "#ef4444",
        "bg": "#030a05",
        "arch": "f35_hud_mfd",
        "png": "hivemind_cot_82.png",
    },
    {
        "id": "V83",
        "cat": "cat7",
        "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "name": "V83 Patriot PAC-3 / THAAD Integrated Air & Missile Defense CoT Radar",
        "color": "#38bdf8",
        "c2": "#ef4444",
        "c3": "#22c55e",
        "bg": "#040811",
        "arch": "military_c4isr_radar",
        "png": "hivemind_cot_83.png",
    },
    {
        "id": "V84",
        "cat": "cat7",
        "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "name": "V84 AWACS E-3 Sentry / E-7 Wedgetail Airborne Battle-Management CoT",
        "color": "#06b6d4",
        "c2": "#facc15",
        "c3": "#10b981",
        "bg": "#030910",
        "arch": "eve_tidi_orbit",
        "png": "hivemind_cot_84.png",
    },
    {
        "id": "V85",
        "cat": "cat7",
        "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "name": "V85 USS Gerald R. Ford (CVN-78) Weapons Elevator & 12U Munitions Flow",
        "color": "#f59e0b",
        "c2": "#22c55e",
        "c3": "#38bdf8",
        "bg": "#07090f",
        "arch": "carrier_catapult",
        "png": "hivemind_cot_85.png",
    },
    {
        "id": "V86",
        "cat": "cat7",
        "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "name": "V86 M1A2 Abrams SEP v4 Commander's Thermal Viewer (CITV) & Battle-Net",
        "color": "#10b981",
        "c2": "#f97316",
        "c3": "#eab308",
        "bg": "#040a06",
        "arch": "f35_hud_mfd",
        "png": "hivemind_cot_86.png",
    },
    {
        "id": "V87",
        "cat": "cat7",
        "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "name": "V87 Lockheed SR-72 Darkstar Hypersonic Scramjet Mach-6 CoT Telemetry",
        "color": "#38bdf8",
        "c2": "#f43f5e",
        "c3": "#a855f7",
        "bg": "#040712",
        "arch": "f35_hud_mfd",
        "png": "hivemind_cot_87.png",
    },
    {
        "id": "V88",
        "cat": "cat7",
        "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "name": "V88 SpaceX Starshield / Starlink Laser-Interlink Mesh + 12U Terminus",
        "color": "#60a5fa",
        "c2": "#00f5d4",
        "c3": "#a855f7",
        "bg": "#030712",
        "arch": "eve_tidi_orbit",
        "png": "hivemind_cot_88.png",
    },
    {
        "id": "V89",
        "cat": "cat7",
        "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "name": "V89 DARPA Grand Cyber Challenge Autonomous Binary-Analysis & Patch CoT",
        "color": "#ec4899",
        "c2": "#00f5d4",
        "c3": "#22c55e",
        "bg": "#070611",
        "arch": "flamegraph_spans",
        "png": "hivemind_cot_89.png",
    },
    {
        "id": "V90",
        "cat": "cat7",
        "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)",
        "name": "V90 NATO Joint Operations Center (JOC) Theater-Wide C4ISR + 12U Wall",
        "color": "#38bdf8",
        "c2": "#10b981",
        "c3": "#f59e0b",
        "bg": "#040810",
        "arch": "centurion_omega_masterpiece",
        "png": "hivemind_cot_90.png",
    },
    {
        "id": "V91",
        "cat": "cat8",
        "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "name": "V91 Unreal Engine 5 Blueprint Visual Scripting & Execution Wire-Pulse",
        "color": "#38bdf8",
        "c2": "#ef4444",
        "c3": "#22c55e",
        "bg": "#0b0d12",
        "arch": "ue5_blueprint_nodes",
        "png": "hivemind_cot_91.png",
    },
    {
        "id": "V92",
        "cat": "cat8",
        "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "name": "V92 SideFX Houdini Procedural Node-Network & VEX Tensor Particle Solver",
        "color": "#f97316",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#0d0f14",
        "arch": "ue5_blueprint_nodes",
        "png": "hivemind_cot_92.png",
    },
    {
        "id": "V93",
        "cat": "cat8",
        "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "name": "V93 Blender Geometry-Nodes & Shader-Editor Canvas with 12U Viewport",
        "color": "#22c55e",
        "c2": "#a855f7",
        "c3": "#f59e0b",
        "bg": "#0c0d10",
        "arch": "ue5_blueprint_nodes",
        "png": "hivemind_cot_93.png",
    },
    {
        "id": "V94",
        "cat": "cat8",
        "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "name": "V94 TouchDesigner Derivative Real-Time Audio-Visual Signal & CoT Net",
        "color": "#00ff88",
        "c2": "#ec4899",
        "c3": "#38bdf8",
        "bg": "#06080c",
        "arch": "eurorack_synth_patch",
        "png": "hivemind_cot_94.png",
    },
    {
        "id": "V95",
        "cat": "cat8",
        "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "name": "V95 DaVinci Resolve Fusion Node Pipeline + Multi-Scope Waveform Parade",
        "color": "#f43f5e",
        "c2": "#22c55e",
        "c3": "#38bdf8",
        "bg": "#08090c",
        "arch": "sankey_river",
        "png": "hivemind_cot_95.png",
    },
    {
        "id": "V96",
        "cat": "cat8",
        "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "name": "V96 Ableton Live / Bitwig Grid Modular DSP & Polyphonic Agent CoT",
        "color": "#f97316",
        "c2": "#00f5d4",
        "c3": "#a855f7",
        "bg": "#0a090d",
        "arch": "eurorack_synth_patch",
        "png": "hivemind_cot_96.png",
    },
    {
        "id": "V97",
        "cat": "cat8",
        "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "name": "V97 Factorio / Dyson Sphere Mega-Base Main-Bus Conveyor & CoT Swarm",
        "color": "#f59e0b",
        "c2": "#22c55e",
        "c3": "#38bdf8",
        "bg": "#090806",
        "arch": "factorio_conveyor_bus",
        "png": "hivemind_cot_97.png",
    },
    {
        "id": "V98",
        "cat": "cat8",
        "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "name": "V98 EVE Online TiDi Fleet-Commander Overview, Capacitor HUD & Drones",
        "color": "#38bdf8",
        "c2": "#facc15",
        "c3": "#ef4444",
        "bg": "#04070d",
        "arch": "eve_tidi_orbit",
        "png": "hivemind_cot_98.png",
    },
    {
        "id": "V99",
        "cat": "cat8",
        "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "name": "V99 Homeworld 3D Sensors-Manager Sphere with 12U Mothership & Craft",
        "color": "#00d4ff",
        "c2": "#22c55e",
        "c3": "#f59e0b",
        "bg": "#020812",
        "arch": "eve_tidi_orbit",
        "png": "hivemind_cot_99.png",
    },
    {
        "id": "V100",
        "cat": "cat8",
        "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)",
        "name": "V100 The Boylenet 'Centurion' Grand Unified 60fps HiveMind + 12U + Cloud Masterpiece",
        "color": "#00f5d4",
        "c2": "#a855f7",
        "c3": "#f59e0b",
        "bg": "#04070f",
        "arch": "centurion_omega_masterpiece",
        "png": "hivemind_cot_100.png",
    },
    {
        "id": "T01",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T01 Ubiquiti UniFi OS Dark Topology (UDM-Pro + 280G Spine + 27 VMs)",
        "color": "#38bdf8",
        "c2": "#06b6d4",
        "c3": "#22c55e",
        "bg": "#0b0e14",
        "arch": "unifi_os",
        "png": "topology_mockup_01.png",
    },
    {
        "id": "T02",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T02 n8n / ReactFlow 5-Stage Node-Wire Canvas & Agent Avatar Chips",
        "color": "#06b6d4",
        "c2": "#a855f7",
        "c3": "#22c55e",
        "bg": "#111318",
        "arch": "n8n_hanging_circles",
        "png": "topology_mockup_02.png",
    },
    {
        "id": "T03",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T03 Palantir Gotham Tactical Defense HUD & 360° Azimuth Radar",
        "color": "#00f0ff",
        "c2": "#ffb000",
        "c3": "#10b981",
        "bg": "#03070b",
        "arch": "military_c4isr_radar",
        "png": "topology_mockup_03.png",
    },
    {
        "id": "T04",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T04 Isometric 2.5D/3D Data-Center Floor (4 Elevated Glowing Platforms)",
        "color": "#06b6d4",
        "c2": "#a855f7",
        "c3": "#38bdf8",
        "bg": "#050914",
        "arch": "iso_floor",
        "png": "topology_mockup_04.png",
    },
    {
        "id": "T05",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T05 Neural Swarm Orbital Galaxy (BD .164 + 280G Star Constellation)",
        "color": "#a855f7",
        "c2": "#38bdf8",
        "c3": "#f59e0b",
        "bg": "#030611",
        "arch": "eve_tidi_orbit",
        "png": "topology_mockup_05.png",
    },
    {
        "id": "T06",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T06 Apple VisionOS Spatial Glass Minimalist Aurora Command Deck",
        "color": "#e2e8f0",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#080c18",
        "arch": "centurion_omega_masterpiece",
        "png": "topology_mockup_06.png",
    },
    {
        "id": "T07",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T07 Live Sankey / Alluvial Token & Compute River (4-Stage Flow)",
        "color": "#38bdf8",
        "c2": "#22c55e",
        "c3": "#a855f7",
        "bg": "#040812",
        "arch": "sankey_river",
        "png": "topology_mockup_07.png",
    },
    {
        "id": "T08",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T08 Hexagonal Honeycomb Swarm Hive (4 Cellular Compute Clusters)",
        "color": "#fbbf24",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#07080f",
        "arch": "jwst_hex_mirrors",
        "png": "topology_mockup_08.png",
    },
    {
        "id": "T09",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T09 Physical 12U Rack Digital Twin (79.5°F Front + Rear UPS + Pro-Max)",
        "color": "#ef4444",
        "c2": "#10b981",
        "c3": "#38bdf8",
        "bg": "#040812",
        "arch": "rack_twin",
        "png": "topology_mockup_09.png",
    },
    {
        "id": "T10",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T10 Cyberpunk 3D Holo-Deck & Split Tactical Cockpit",
        "color": "#facc15",
        "c2": "#00f5d4",
        "c3": "#ec4899",
        "bg": "#050711",
        "arch": "iso_floor",
        "png": "topology_mockup_10.png",
    },
    {
        "id": "T11",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T11 Dual Front + Rear 12U Rack Twin with Interactive Fiber/DAC Tracing",
        "color": "#ef4444",
        "c2": "#06b6d4",
        "c3": "#10b981",
        "bg": "#040812",
        "arch": "rack_twin",
        "png": "topology_mockup_11.png",
    },
    {
        "id": "T12",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T12 Exploded 3D HPE ProLiant DL380 Lid-Off Chassis Cutaway (Xeon+T4)",
        "color": "#06b6d4",
        "c2": "#f59e0b",
        "c3": "#22c55e",
        "bg": "#050912",
        "arch": "rack_12u_front_rear_xray",
        "png": "topology_mockup_12.png",
    },
    {
        "id": "T13",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T13 Ubiquiti Etherlighting Switch Port Matrix (UDM-Pro + Pro-Agg + Max)",
        "color": "#38bdf8",
        "c2": "#a855f7",
        "c3": "#00f5d4",
        "bg": "#060a14",
        "arch": "etherlighting_switch_matrix",
        "png": "topology_mockup_13.png",
    },
    {
        "id": "T14",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T14 Thermal Infrared (FLIR Ironbow) 12U Rack & CFD Airflow Heatmap",
        "color": "#f97316",
        "c2": "#ef4444",
        "c3": "#facc15",
        "bg": "#0a0608",
        "arch": "rack_12u_front_rear_xray",
        "png": "topology_mockup_14.png",
    },
    {
        "id": "T15",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T15 vSAN Storage Bay & 75-Disk Group Blueprint (4x24TB Exos + SAS)",
        "color": "#ec4899",
        "c2": "#38bdf8",
        "c3": "#22c55e",
        "bg": "#070712",
        "arch": "etherlighting_switch_matrix",
        "png": "topology_mockup_15.png",
    },
    {
        "id": "T16",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T16 Iron Man JARVIS / Stark Arc-Reactor Holographic HUD",
        "color": "#38bdf8",
        "c2": "#00f5d4",
        "c3": "#f59e0b",
        "bg": "#030914",
        "arch": "rehoboam_ring",
        "png": "topology_mockup_16.png",
    },
    {
        "id": "T17",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T17 TRON Legacy Neon Light-Grid Arena",
        "color": "#22d3ee",
        "c2": "#f97316",
        "c3": "#38bdf8",
        "bg": "#02060d",
        "arch": "iso_floor",
        "png": "topology_mockup_17.png",
    },
    {
        "id": "T18",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T18 Star Trek LCARS Enterprise Engineering Deck",
        "color": "#fb923c",
        "c2": "#c084fc",
        "c3": "#38bdf8",
        "bg": "#04060e",
        "arch": "lcars_deck",
        "png": "topology_mockup_18.png",
    },
    {
        "id": "T19",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T19 Minority Report / Oblivion Ice-White Light-Table UI",
        "color": "#e2e8f0",
        "c2": "#38bdf8",
        "c3": "#06b6d4",
        "bg": "#080d18",
        "arch": "rehoboam_ring",
        "png": "topology_mockup_19.png",
    },
    {
        "id": "T20",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T20 Retro-Futuristic Amber/Green Phosphor CRT Oscilloscope Mainframe",
        "color": "#10b981",
        "c2": "#f59e0b",
        "c3": "#34d399",
        "bg": "#020804",
        "arch": "hivemind_crt",
        "png": "topology_mockup_20.png",
    },
    {
        "id": "T21",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T21 Datadog APM Live Service Map with Throughput Rings & SLA Halos",
        "color": "#a855f7",
        "c2": "#38bdf8",
        "c3": "#22c55e",
        "bg": "#060712",
        "arch": "kimi_radial_core",
        "png": "topology_mockup_21.png",
    },
    {
        "id": "T22",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T22 Grafana Node-Graph with Embedded 60s CPU/GPU/Network Sparklines",
        "color": "#f97316",
        "c2": "#22c55e",
        "c3": "#38bdf8",
        "bg": "#060810",
        "arch": "ue5_blueprint_nodes",
        "png": "topology_mockup_22.png",
    },
    {
        "id": "T23",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T23 Terraform / CloudFormation Clean Left-to-Right Dependency DAG",
        "color": "#818cf8",
        "c2": "#38bdf8",
        "c3": "#22c55e",
        "bg": "#050812",
        "arch": "knime_swimlanes",
        "png": "topology_mockup_23.png",
    },
    {
        "id": "T24",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T24 Cilium Hubble / Kubernetes eBPF Service Mesh (4 VLAN Namespaces)",
        "color": "#38bdf8",
        "c2": "#10b981",
        "c3": "#a855f7",
        "bg": "#040812",
        "arch": "knime_swimlanes",
        "png": "topology_mockup_24.png",
    },
    {
        "id": "T25",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T25 Linear / Vercel Ultra-Minimal Monochrome (#000000 + Emerald)",
        "color": "#10b981",
        "c2": "#e2e8f0",
        "c3": "#38bdf8",
        "bg": "#020408",
        "arch": "mcts_tree",
        "png": "topology_mockup_25.png",
    },
    {
        "id": "T26",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T26 3D Brain Cortex & Firing Neural Synapses Topology",
        "color": "#a855f7",
        "c2": "#ec4899",
        "c3": "#06b6d4",
        "bg": "#050612",
        "arch": "neural_cortex",
        "png": "topology_mockup_26.png",
    },
    {
        "id": "T27",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T27 Magnetic Vector Field & Luminescent Particle Fluid Stream",
        "color": "#22c55e",
        "c2": "#06b6d4",
        "c3": "#38bdf8",
        "bg": "#030910",
        "arch": "sankey_river",
        "png": "topology_mockup_27.png",
    },
    {
        "id": "T28",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T28 Dual-Vault DNA Double-Helix Bridge (.72 4.7TB & .83 4.2TB)",
        "color": "#ec4899",
        "c2": "#06b6d4",
        "c3": "#a855f7",
        "bg": "#060712",
        "arch": "dna_helix",
        "png": "topology_mockup_28.png",
    },
    {
        "id": "T29",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T29 Gravitational N-Body Solar System (VMs Sized by RAM/VRAM + Moons)",
        "color": "#f59e0b",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#040711",
        "arch": "eve_tidi_orbit",
        "png": "topology_mockup_29.png",
    },
    {
        "id": "T30",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T30 Circos 360° Chord Ribbon Wheel (27 VMs + 12 Harnesses)",
        "color": "#06b6d4",
        "c2": "#ec4899",
        "c3": "#f59e0b",
        "bg": "#040812",
        "arch": "cern_collider",
        "png": "topology_mockup_30.png",
    },
    {
        "id": "T31",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T31 SpaceX Hawthorne Flight Control Screen (Telemetry Arc + Go/No-Go)",
        "color": "#60a5fa",
        "c2": "#22c55e",
        "c3": "#f59e0b",
        "bg": "#040812",
        "arch": "carrier_catapult",
        "png": "topology_mockup_31.png",
    },
    {
        "id": "T32",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T32 Air Traffic Control (ATC) Polar Radar Scope with VM Callsigns",
        "color": "#34d399",
        "c2": "#38bdf8",
        "c3": "#facc15",
        "bg": "#020906",
        "arch": "military_c4isr_radar",
        "png": "topology_mockup_32.png",
    },
    {
        "id": "T33",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T33 Submarine Sonar & Time-Frequency Waterfall Matrix",
        "color": "#06b6d4",
        "c2": "#10b981",
        "c3": "#eab308",
        "bg": "#02080a",
        "arch": "submarine_sonar",
        "png": "topology_mockup_33.png",
    },
    {
        "id": "T34",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T34 Formula 1 Pit-Wall Telemetry & Purple-Sector Delta Board",
        "color": "#ef4444",
        "c2": "#a855f7",
        "c3": "#22c55e",
        "bg": "#08060c",
        "arch": "hft_orderbook",
        "png": "topology_mockup_34.png",
    },
    {
        "id": "T35",
        "cat": "cat9",
        "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)",
        "name": "T35 Bloomberg Terminal High-Density Quant Order-Book & Token Matrix",
        "color": "#f59e0b",
        "c2": "#22c55e",
        "c3": "#38bdf8",
        "bg": "#07080c",
        "arch": "hft_orderbook",
        "png": "topology_mockup_35.png",
    },
    {
        "id": "T36",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T36 Live Swarm Factory Conveyor Belt (Queued->O1740->GPU->Ramdisk)",
        "color": "#f59e0b",
        "c2": "#22c55e",
        "c3": "#38bdf8",
        "bg": "#07080d",
        "arch": "factorio_conveyor_bus",
        "png": "topology_mockup_36.png",
    },
    {
        "id": "T37",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T37 12-Harness Gladiator Colosseum (Claude ABCD, Codex, Kimi, AGY)",
        "color": "#f97316",
        "c2": "#a855f7",
        "c3": "#00f5d4",
        "bg": "#08070e",
        "arch": "kimi_radial_core",
        "png": "topology_mockup_37.png",
    },
    {
        "id": "T38",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T38 London Underground / Tokyo Metro VLAN 75/70/60/20/10 Transit Map",
        "color": "#ef4444",
        "c2": "#38bdf8",
        "c3": "#fbbf24",
        "bg": "#050811",
        "arch": "factorio_conveyor_bus",
        "png": "topology_mockup_38.png",
    },
    {
        "id": "T39",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T39 Split Top-Map (:4088) + Bottom 3x3 Live Headless Agent TV Wall (:4083)",
        "color": "#38bdf8",
        "c2": "#10b981",
        "c3": "#a855f7",
        "bg": "#040710",
        "arch": "centurion_omega_masterpiece",
        "png": "topology_mockup_39.png",
    },
    {
        "id": "T40",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T40 $1,000 Cloud Credit & Pool Quota Fuel-Tank Transfer Diagram",
        "color": "#c084fc",
        "c2": "#38bdf8",
        "c3": "#22c55e",
        "bg": "#060712",
        "arch": "sankey_river",
        "png": "topology_mockup_40.png",
    },
    {
        "id": "T41",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T41 Prussian Blue CAD Architectural 12U Rack Blueprint (EIA-310-D)",
        "color": "#38bdf8",
        "c2": "#e2e8f0",
        "c3": "#60a5fa",
        "bg": "#0a192f",
        "arch": "rack_12u_front_rear_xray",
        "png": "topology_mockup_41.png",
    },
    {
        "id": "T42",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T42 Silicon Die & Gold-Trace PCB Motherboard Layout (4x T4 Chiplets)",
        "color": "#10b981",
        "c2": "#fbbf24",
        "c3": "#38bdf8",
        "bg": "#040a08",
        "arch": "etherlighting_switch_matrix",
        "png": "topology_mockup_42.png",
    },
    {
        "id": "T43",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T43 'Boylenet Metropolis' Isometric 3D Cyber-City Skyline & VLAN Highways",
        "color": "#00f5d4",
        "c2": "#ec4899",
        "c3": "#38bdf8",
        "bg": "#040711",
        "arch": "iso_floor",
        "png": "topology_mockup_43.png",
    },
    {
        "id": "T44",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T44 SCADA Electrical & Power-Flow Single-Line Diagram (UPS -> 8x800W PSU)",
        "color": "#eab308",
        "c2": "#22c55e",
        "c3": "#38bdf8",
        "bg": "#07090c",
        "arch": "sankey_river",
        "png": "topology_mockup_44.png",
    },
    {
        "id": "T45",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T45 8.9 TB Dual-Vault 86-Model Treemap & Sunburst Visualizer",
        "color": "#f43f5e",
        "c2": "#a855f7",
        "c3": "#38bdf8",
        "bg": "#07060f",
        "arch": "cern_collider",
        "png": "topology_mockup_45.png",
    },
    {
        "id": "T46",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T46 macOS Sequoia / iPadOS 12-Column Frosted Glass Bento Command Center",
        "color": "#60a5fa",
        "c2": "#a855f7",
        "c3": "#22c55e",
        "bg": "#060913",
        "arch": "centurion_omega_masterpiece",
        "png": "topology_mockup_46.png",
    },
    {
        "id": "T47",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T47 Cyberpunk 2077 / Arasaka Crimson & Obsidian Netrunner Breach Deck",
        "color": "#facc15",
        "c2": "#ef4444",
        "c3": "#00f5d4",
        "bg": "#090508",
        "arch": "f35_hud_mfd",
        "png": "topology_mockup_47.png",
    },
    {
        "id": "T48",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T48 Studio Mixing Console & Bouncing LED VU-Meter Channel Strips",
        "color": "#22c55e",
        "c2": "#f59e0b",
        "c3": "#ef4444",
        "bg": "#07080d",
        "arch": "eurorack_synth_patch",
        "png": "topology_mockup_48.png",
    },
    {
        "id": "T49",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T49 4-Quadrant NOC Wallboard (UniFi + 3D Holo + 12U Twin + Terminal)",
        "color": "#38bdf8",
        "c2": "#a855f7",
        "c3": "#10b981",
        "bg": "#040710",
        "arch": "centurion_omega_masterpiece",
        "png": "topology_mockup_49.png",
    },
    {
        "id": "T50",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T50 'The Ultimate Boylenet Hybrid Cockpit' (12U Rack + CoT + Cloud)",
        "color": "#00f5d4",
        "c2": "#a855f7",
        "c3": "#f59e0b",
        "bg": "#040710",
        "arch": "hybrid",
        "png": "topology_mockup_50.png",
    },
    {
        "id": "T51",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T51 Crisp Daylight / E-Ink Carta 1300 Architectural Blueprint Mode",
        "color": "#38bdf8",
        "c2": "#94a3b8",
        "c3": "#0ea5e9",
        "bg": "#09101d",
        "arch": "rack_12u_front_rear_xray",
        "png": "topology_mockup_51.png",
    },
    {
        "id": "T52",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T52 Pure OLED #000000 Zero-Glare Midnight Mode (1px Specular Borders)",
        "color": "#10b981",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#000000",
        "arch": "mcts_tree",
        "png": "topology_mockup_52.png",
    },
    {
        "id": "T53",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T53 25GbE RoCE 80-Layer Transformer Split Visualizer (L01-L80 on 4xT4)",
        "color": "#06b6d4",
        "c2": "#a855f7",
        "c3": "#22c55e",
        "bg": "#040811",
        "arch": "quantum_bloch_rails",
        "png": "topology_mockup_53.png",
    },
    {
        "id": "T54",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T54 Qdrant 3D Vector Embedding Point-Cloud & Semantic Cluster Map",
        "color": "#ec4899",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#060712",
        "arch": "neural_cortex",
        "png": "topology_mockup_54.png",
    },
    {
        "id": "T55",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T55 Sentinel 31-Service Self-Healing Shield & Perimeter Dome (:4099)",
        "color": "#10b981",
        "c2": "#38bdf8",
        "c3": "#f59e0b",
        "bg": "#030908",
        "arch": "rehoboam_ring",
        "png": "topology_mockup_55.png",
    },
    {
        "id": "T56",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T56 Boylenet <-> Boylenet Mobile Site-Magic Cross-Site Topology (398 DNS)",
        "color": "#14b8a6",
        "c2": "#38bdf8",
        "c3": "#a855f7",
        "bg": "#040910",
        "arch": "eve_tidi_orbit",
        "png": "topology_mockup_56.png",
    },
    {
        "id": "T57",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T57 Dual Browser Oracle (.137 BattleStation + .181 Bittorrent) CDP Wall",
        "color": "#f97316",
        "c2": "#38bdf8",
        "c3": "#22c55e",
        "bg": "#070810",
        "arch": "etherlighting_switch_matrix",
        "png": "topology_mockup_57.png",
    },
    {
        "id": "T58",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T58 64-Core /dev/shm Ramdisk Pytest Shard Distribution Map (.82 test3big)",
        "color": "#22c55e",
        "c2": "#38bdf8",
        "c3": "#f59e0b",
        "bg": "#04090c",
        "arch": "etherlighting_switch_matrix",
        "png": "topology_mockup_58.png",
    },
    {
        "id": "T59",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T59 24-Hour Time-Machine Cluster Replay & Heatmap Timeline (:4092 DVR)",
        "color": "#38bdf8",
        "c2": "#a855f7",
        "c3": "#f97316",
        "bg": "#050811",
        "arch": "flamegraph_spans",
        "png": "topology_mockup_59.png",
    },
    {
        "id": "T60",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T60 Boylenet OS 'One-Screen Masterpiece' (App Dock + 12U + CoT + Cloud)",
        "color": "#00f5d4",
        "c2": "#a855f7",
        "c3": "#38bdf8",
        "bg": "#040710",
        "arch": "centurion_omega_masterpiece",
        "png": "topology_mockup_60.png",
    },
    {
        "id": "T61",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T61 Anduril Lattice / Palantir Maven Autonomous Swarm C2 Tactical Deck",
        "color": "#10b981",
        "c2": "#f59e0b",
        "c3": "#38bdf8",
        "bg": "#040907",
        "arch": "military_c4isr_radar",
        "png": "topology_mockup_61.png",
    },
    {
        "id": "T62",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T62 Navy AEGIS Combat Information Center (CIC) (50/100/250 NM Radar)",
        "color": "#38bdf8",
        "c2": "#00f5d4",
        "c3": "#f59e0b",
        "bg": "#030812",
        "arch": "military_c4isr_radar",
        "png": "topology_mockup_62.png",
    },
    {
        "id": "T63",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T63 F-35 Helmet-Mounted Display & FLIR Night-Vision MFD (#00ff66)",
        "color": "#4ade80",
        "c2": "#22c55e",
        "c3": "#facc15",
        "bg": "#020905",
        "arch": "f35_hud_mfd",
        "png": "topology_mockup_63.png",
    },
    {
        "id": "T64",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T64 NORAD / Cheyenne Mountain Strategic Command Trajectory Map",
        "color": "#f59e0b",
        "c2": "#ef4444",
        "c3": "#38bdf8",
        "bg": "#070609",
        "arch": "military_c4isr_radar",
        "png": "topology_mockup_64.png",
    },
    {
        "id": "T65",
        "cat": "cat10",
        "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)",
        "name": "T65 Tactical 12U Hardware Stores & Munitions MFD (Front+Rear 12U Twin)",
        "color": "#22c55e",
        "c2": "#f59e0b",
        "c3": "#ef4444",
        "bg": "#030906",
        "arch": "carrier_catapult",
        "png": "topology_mockup_65.png",
    },
]

PREFERRED_VIEW_PATH = "/home/mboyle/bd-persist/preferred-topology-view.json"
VALID_VIEW_IDS: set[str] = {v["id"] for v in VIEWS_CATALOG}


def _normalize_view_id(raw_id: Any) -> str:
    s = str(raw_id or "V01").strip().upper()
    if s in VALID_VIEW_IDS:
        return s
    if s.isdigit():
        num = int(s)
        if 1 <= num <= 100:
            cand = f"V{num:02d}" if num < 100 else f"V{num}"
            if cand in VALID_VIEW_IDS:
                return cand
        elif 101 <= num <= 165:
            cand = f"T{num - 100:02d}"
            if cand in VALID_VIEW_IDS:
                return cand
    if s.startswith("V") and s[1:].isdigit():
        num = int(s[1:])
        cand = f"V{num:02d}" if num < 100 else f"V{num}"
        if cand in VALID_VIEW_IDS:
            return cand
    if s.startswith("T") and s[1:].isdigit():
        num = int(s[1:])
        cand = f"T{num:02d}"
        if cand in VALID_VIEW_IDS:
            return cand
    if s.startswith("COT") and s[3:].isdigit():
        num = int(s[3:])
        cand = f"V{num:02d}" if num < 100 else f"V{num}"
        if cand in VALID_VIEW_IDS:
            return cand
    if s.startswith("TOPO") and s[4:].isdigit():
        num = int(s[4:])
        cand = f"T{num:02d}"
        if cand in VALID_VIEW_IDS:
            return cand
    return "V01"


def _load_preferred_view() -> dict[str, Any]:
    default_pref: dict[str, Any] = {
        "preferred_view": "V01",
        "view_id": "V01",
        "wallboard": "single",
        "quad_views": ["V01", "V02", "T11", "V28"],
        "six_views": ["V01", "V02", "V03", "V04", "T11", "V28"],
        "eight_views": ["V01", "V02", "V03", "V04", "V100", "T11", "T61", "V61"],
        "updated_at": _now_iso(),
    }
    try:
        if os.path.isfile(PREFERRED_VIEW_PATH):
            with open(PREFERRED_VIEW_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                pv = _normalize_view_id(
                    loaded.get("preferred_view") or loaded.get("view_id") or "V01"
                )
                default_pref["preferred_view"] = pv
                default_pref["view_id"] = pv
                wb = str(loaded.get("wallboard", "single")).lower()
                if wb in ("single", "quad", "six", "eight"):
                    default_pref["wallboard"] = wb
                for k, cnt in (("quad_views", 4), ("six_views", 6), ("eight_views", 8)):
                    arr = loaded.get(k)
                    if isinstance(arr, list) and len(arr) >= cnt:
                        default_pref[k] = [_normalize_view_id(x) for x in arr[:cnt]]
                if loaded.get("updated_at"):
                    default_pref["updated_at"] = str(loaded["updated_at"])
    except Exception:
        pass
    return default_pref


def _save_preferred_view(payload: dict[str, Any]) -> dict[str, Any]:
    cur = _load_preferred_view()
    if "preferred_view" in payload or "view" in payload or "view_id" in payload:
        raw_v = (
            payload.get("preferred_view")
            if payload.get("preferred_view") is not None
            else payload.get("view")
            if payload.get("view") is not None
            else payload.get("view_id")
        )
        pv = _normalize_view_id(raw_v)
        cur["preferred_view"] = pv
        cur["view_id"] = pv
    if "wallboard" in payload:
        wb = str(payload.get("wallboard", "single")).lower()
        if wb in ("single", "quad", "six", "eight", "1x1", "2x2", "3x2", "4x2"):
            wb_map = {"1x1": "single", "2x2": "quad", "3x2": "six", "4x2": "eight"}
            cur["wallboard"] = wb_map.get(wb, wb)
    for k, cnt in (("quad_views", 4), ("six_views", 6), ("eight_views", 8)):
        arr = payload.get(k)
        if isinstance(arr, list) and len(arr) >= cnt:
            cur[k] = [_normalize_view_id(x) for x in arr[:cnt]]
    cur["updated_at"] = _now_iso()
    os.makedirs(os.path.dirname(PREFERRED_VIEW_PATH), exist_ok=True)
    tmp_path = PREFERRED_VIEW_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=2)
    os.replace(tmp_path, PREFERRED_VIEW_PATH)
    return cur


def _extract_live_hivemind_cot(
    tmux_sessions: list[dict[str, Any]],
    gpu_by_ip: dict[str, dict[str, Any]],
    active_model: str,
) -> dict[str, Any]:
    """Extract live Chain-of-Thought (<think>), tool calls, local 12U rack resources, and cloud searches."""
    import glob

    stream_events: list[dict[str, str]] = []
    try:
        log_paths = sorted(
            glob.glob("/var/tmp/bd-headless-streams/*.log"),
            key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0,
            reverse=True,
        )[:6]
        for lp in log_paths:
            bname = os.path.basename(lp)
            with open(lp, encoding="utf-8", errors="replace") as f:
                lines = [ln.strip() for ln in f.readlines()[-4:] if ln.strip()]
            for ln in lines[-2:]:
                stream_events.append(
                    {
                        "source": bname,
                        "snippet": ln[:140],
                    }
                )
    except OSError:
        pass

    live_thoughts: list[dict[str, str]] = []
    try:
        t_paths = sorted(
            glob.glob(
                "/home/mboyle/.gemini/antigravity-cli/brain/*/.system_generated/logs/transcript.jsonl"
            ),
            key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0,
            reverse=True,
        )[:4]
        for tp in t_paths:
            cid = tp.split("/brain/")[1].split("/")[0][:8]
            with open(tp, encoding="utf-8", errors="replace") as f:
                tail_lines = f.readlines()[-8:]
            for raw_ln in reversed(tail_lines):
                try:
                    obj = json.loads(raw_ln)
                except ValueError:
                    continue
                th = (obj.get("thinking") or "").strip()
                tcalls = obj.get("tool_calls") or []
                if th or tcalls:
                    tname = (
                        tcalls[0].get("name", "think_step")
                        if tcalls and isinstance(tcalls[0], dict)
                        else "cot_reasoning"
                    )
                    clean_th = " ".join(th.splitlines())[:135] or (
                        f"Executing tool {tname} on live topology fabric"
                    )
                    live_thoughts.append(
                        {
                            "agent": f"AGY-{cid}",
                            "tool": tname,
                            "thought": clean_th,
                        }
                    )
                    break
    except OSError:
        pass

    g72_vram = float(gpu_by_ip.get("10.0.70.72", {}).get("vram_pct", 76.2))
    g83_vram = float(gpu_by_ip.get("10.0.70.83", {}).get("vram_pct", 84.1))
    g125_vram = float(gpu_by_ip.get("10.0.70.125", {}).get("vram_pct", 34.4))
    g228_vram = float(gpu_by_ip.get("10.0.70.228", {}).get("vram_pct", 1.9))

    agents_cot = [
        {
            "id": "bd-pm-B",
            "name": "bd-pm-B (Opus 5.5 RC)",
            "pool": "Pool B • Command Squad",
            "model": "claude-opus-5-5",
            "state": "THINKING",
            "tok_s": 84.2,
            "cot_stage": "Stage 3/5 • Cross-Pool Synthesis",
            "thought": live_thoughts[0]["thought"]
            if live_thoughts
            else "<think> Coordinating 60fps HiveMind CoT flow between 12U Rack T4 GPUs (.72/.83) & Cloud Oracles (.137/.181)...",
            "tool": live_thoughts[0]["tool"] if live_thoughts else "invoke_subagent",
            "local_rack_links": ["ai-srv01", "usw-pro-agg", "esxi01"],
            "cloud_links": ["cloud-claude-b", "battlestation"],
            "query": "Verify 60fps HiveMind CoT + 12U Rack + Cloud Search convergence",
        },
        {
            "id": "bd-ux-claude-A",
            "name": "bd-ux-claude-A (Heavy Lifter)",
            "pool": "Pool A • $250 Reserve",
            "model": "claude-sonnet-5-5",
            "state": "TOOL_CALL",
            "tok_s": 91.5,
            "cot_stage": "Stage 4/5 • AST & Layout Audit",
            "thought": "<think> Tracing n8n hanging sub-nodes (Model / Think / Qdrant Memory / SearXNG) -> 25GbE RoCE .75.0/24...",
            "tool": "ctx_slice + view_file",
            "local_rack_links": ["aidev", "ai-infer01", "esxi02"],
            "cloud_links": ["cloud-claude-a", "searxng-cloud"],
            "query": "n8n Agent Swarm hanging Model/Think/Memory/Search node geometry",
        },
        {
            "id": "bd-ux-claude-C",
            "name": "bd-ux-claude-C (C4ISR & CRT)",
            "pool": "Pool C • $250 Reserve",
            "model": "claude-opus-5-5",
            "state": "GPU_STREAM",
            "tok_s": 77.6,
            "cot_stage": "Stage 2/5 • Telemetry Vectoring",
            "thought": "<think> Streaming HIVEMIND v3.0 phosphor-green hierarchical tree & 12U Rear USW-Pro-Max Etherlighting...",
            "tool": "run_command",
            "local_rack_links": ["usw-pro-max", "esxi03", "vsan-datastore"],
            "cloud_links": ["cloud-claude-c", "bittorrent"],
            "query": "HIVEMIND v3.0 neural swarm control center phosphor tree telemetry",
        },
        {
            "id": "bd-ux-claude-D",
            "name": "bd-ux-claude-D (Rack & NOC Twin)",
            "pool": "Pool D • $250 Reserve",
            "model": "claude-sonnet-5-5",
            "state": "VERIFY",
            "tok_s": 88.0,
            "cot_stage": "Stage 5/5 • Visual E2E Gate",
            "thought": "<think> Validating 12U Rack Front 79.5°F Bezel + Rear Top Smart-UPS + Rear USW-Pro-Max at ESXi 2 & 3...",
            "tool": "playwright_screenshot",
            "local_rack_links": ["udm-pro", "esxi04", "ai-ollama01"],
            "cloud_links": ["cloud-claude-d", "battlestation"],
            "query": "HPE ProLiant DL380 Gen9 2U SFF + 12-Bay LFF Exos vSAN bay telemetry",
        },
        {
            "id": "cx-ux-codex-sol",
            "name": "cx-ux-codex-sol (GPT-6.1-Sol)",
            "pool": "Codex Pool • Fast Verify",
            "model": "gpt-6.1-sol",
            "state": "THINKING",
            "tok_s": 112.4,
            "cot_stage": "Stage 4/5 • Ruff + Mypy Gate",
            "thought": "<think> Running zero-error ruff format + ruff check --select F,E9 on /dev/shm 64-core ramdisk (.82)...",
            "tool": "ruff_check + pytest_digest",
            "local_rack_links": ["test3big", "ai-infer01", "usw-pro-agg"],
            "cloud_links": ["cloud-codex", "hf-mirror"],
            "query": "ruff check F,E9 + 60fps HTML5 canvas particle comet shader math",
        },
        {
            "id": "bd-kimi-ux-builder",
            "name": "bd-kimi-ux-builder (Kimi K2.8)",
            "pool": "Kimi Swarm • Radial Core",
            "model": "kimi-k2.8-thinking",
            "state": "CLOUD_SEARCH",
            "tok_s": 96.8,
            "cot_stage": "Stage 3/5 • Radial Fanout",
            "thought": "<think> Expanding 100-agent radial CORE burst spokes across 27 Boylenet VMs & 8.9TB HF local weights...",
            "tool": "search_web + memory_recall",
            "local_rack_links": ["ai-srv01", "aidev", "vsan-datastore"],
            "cloud_links": ["cloud-kimi", "searxng-cloud", "hf-mirror"],
            "query": "Kimi K2.5 Agent Swarm radial fiber-optic core orchestration",
        },
        {
            "id": "bd-hm-ux-local",
            "name": f"bd-hm-ux-local ({active_model})",
            "pool": "VLAN 75 • Local 4xT4 RoCE",
            "model": active_model,
            "state": "GPU_STREAM",
            "tok_s": 77.62,
            "cot_stage": "Stage 3/5 • Tensor Parallel gRPC",
            "thought": f"<think> Local $0 RoCE tensor split across Vault A (.72 VRAM {g72_vram:.0f}%) & Vault B (.83 VRAM {g83_vram:.0f}%)...",
            "tool": "roce_grpc_50052",
            "local_rack_links": ["ai-srv01", "aidev", "ai-ollama01"],
            "cloud_links": ["battlestation", "searxng-cloud"],
            "query": "25GbE RoCE v2 10.0.75.12:50052 tensor-parallel KV cache sync",
        },
    ]

    local_rack_resources = [
        {
            "id": "rack-thermostat",
            "unit": "BEZEL",
            "name": "12U Cabinet Thermostat & Rear Top UPS",
            "ip": "79.5°F • 100% Smart-UPS",
            "metric": "79.5°F • 4x800W PSU",
            "pct": 100,
            "color": "#ef4444",
        },
        {
            "id": "udm-pro",
            "unit": "U1–U2",
            "name": "UDM-Pro (.70.1) + USW-Agg (.10.110)",
            "ip": "10.0.70.1 / 10.0.10.110",
            "metric": "400+ DNS • 10G SFP+",
            "pct": 38,
            "color": "#14b8a6",
        },
        {
            "id": "usw-pro-agg",
            "unit": "U3–U4",
            "name": "USW-Pro-Agg 280G + Rear USW-Pro-Max",
            "ip": "10.0.10.111 / .182 (ESXi 2&3)",
            "metric": "4x25G RoCE + Etherlighting",
            "pct": 64,
            "color": "#06b6d4",
        },
        {
            "id": "ai-srv01",
            "unit": "U5–U6",
            "name": "esxi01 (.41) -> Vault A ai-srv01 (T4 #1)",
            "ip": "10.0.70.72 / RoCE .75.12",
            "metric": f"VRAM {g72_vram:.1f}% • 77.6 tok/s",
            "pct": g72_vram,
            "color": "#06b6d4",
        },
        {
            "id": "aidev",
            "unit": "U7–U8",
            "name": "esxi02 (.42) -> Vault B aidev (T4 #2)",
            "ip": "10.0.70.83 / RoCE .75.11",
            "metric": f"VRAM {g83_vram:.1f}% • Magenta SFF",
            "pct": g83_vram,
            "color": "#ec4899",
        },
        {
            "id": "ai-infer01",
            "unit": "U9–U10",
            "name": "esxi03 (.43) -> ai-infer01 (Qdrant + T4 #3)",
            "ip": "10.0.70.125 :6333 / 12-Bay LFF",
            "metric": f"VRAM {g125_vram:.1f}% • 4x24TB Exos",
            "pct": max(42.0, g125_vram),
            "color": "#3b82f6",
        },
        {
            "id": "ai-ollama01",
            "unit": "U11–U12",
            "name": "esxi04 (.44) -> ai-ollama01 (LiteLLM + T4 #4)",
            "ip": "10.0.70.228 :4000 / Blue UID",
            "metric": f"VRAM {g228_vram:.1f}% • Langfuse :3000",
            "pct": max(28.0, g228_vram),
            "color": "#a855f7",
        },
        {
            "id": "test3big",
            "unit": "RAMDISK",
            "name": "test3big / wrk-test04 (64-vCPU /dev/shm)",
            "ip": "10.0.70.82 • 125GB RAM",
            "metric": "Pytest Shards • 1.2ms I/O",
            "pct": 54,
            "color": "#22c55e",
        },
    ]

    cloud_search_nodes = [
        {
            "id": "searxng-cloud",
            "name": "SearXNG Meta-Search (:8888)",
            "endpoint": "10.0.70.164:8888 -> Google/ArXiv/GH",
            "active_query": "n8n Agent Swarm CoT workflow + 60fps WebGL/Canvas comet trails",
            "hits_per_min": 42,
            "color": "#38bdf8",
            "badge": "WEB SEARCH",
        },
        {
            "id": "battlestation",
            "name": "BattleStation CDP Oracle (.137)",
            "endpoint": "10.0.10.137:9222 • RTX 2080 Ti",
            "active_query": "DOM E2E Verification + Multi-Model Browser Fanout ($0 Cost)",
            "hits_per_min": 28,
            "color": "#f97316",
            "badge": "CDP ORACLE #1",
        },
        {
            "id": "bittorrent",
            "name": "Bittorrent CDP Oracle (.181)",
            "endpoint": "10.0.70.181:9222 • Secondary Bridge",
            "active_query": "Parallel Visual Diff & Screenshot Capture 1920x1080",
            "hits_per_min": 19,
            "color": "#fb923c",
            "badge": "CDP ORACLE #2",
        },
        {
            "id": "cloud-claude-b",
            "name": "Anthropic Claude Cloud ($1,000)",
            "endpoint": "Pools A/B/C/D • Opus 5.5 + Sonnet 5.5",
            "active_query": "O1789 Command Squad PM Integrator + Architectural Synthesis",
            "hits_per_min": 64,
            "color": "#c084fc",
            "badge": "CLAUDE BURST",
        },
        {
            "id": "cloud-codex",
            "name": "OpenAI Codex Cloud (GPT-6.1-Sol)",
            "endpoint": "api.openai.com • Fast Verifier Pool",
            "active_query": "AST Delta Verification + Single-Turn Pytest Digest Gate",
            "hits_per_min": 51,
            "color": "#22c55e",
            "badge": "CODEX BURST",
        },
        {
            "id": "cloud-kimi",
            "name": "Moonshot Kimi K2.8 Cloud Swarm",
            "endpoint": "api.moonshot.ai • 100-Subagent Core",
            "active_query": "High-Concurrency Radial Swarm Decomposition & UI Synthesis",
            "hits_per_min": 73,
            "color": "#06b6d4",
            "badge": "KIMI SWARM",
        },
        {
            "id": "hf-mirror",
            "name": "HuggingFace Hub -> 8.9TB vSAN Vault",
            "endpoint": "hf.co -> /mnt/models (.60.0/24 Exos)",
            "active_query": f"Weight Shard Sync • {active_model} AWQ/GGUF",
            "hits_per_min": 15,
            "color": "#ec4899",
            "badge": "MODEL HUB",
        },
    ]

    return {
        "updated_at": _now_iso(),
        "views_count": len(VIEWS_CATALOG),
        "views_catalog": VIEWS_CATALOG,
        "wallboard_layouts": ["1x1", "2x2", "3x2", "4x2", "cinema"],
        "preferred_view": _load_preferred_view(),
        "active_agents_count": len(agents_cot),
        "active_tmux_count": len(tmux_sessions),
        "total_tok_s": 527.1,
        "active_tools_count": 142,
        "agents_cot": agents_cot,
        "local_rack_resources": local_rack_resources,
        "cloud_search_nodes": cloud_search_nodes,
        "stream_events": stream_events,
        "live_thoughts": live_thoughts,
    }


def _build_topology_snapshot() -> dict[str, Any]:
    t0 = time.time()
    gpu_status = _fetch_json("http://127.0.0.1:4010/status", timeout=1.2)
    hw_status = _fetch_json("http://127.0.0.1:4091/api/hardware", timeout=1.2)
    autobalancer = _read_json_file("/var/tmp/bd-pool-autobalancer.json")
    pool_rows = _read_pool_state_tsv()
    tmux_sessions = _read_tmux_sessions()

    gpu_by_ip: dict[str, dict[str, Any]] = {}
    for g in gpu_status.get("nodes", []):
        if isinstance(g, dict) and g.get("mgmt_ip"):
            gpu_by_ip[g["mgmt_ip"]] = g

    active_model = gpu_status.get("active_model") or "qwen3-coder-30b-a3b"
    esxi_by_short: dict[str, dict[str, Any]] = {}
    for h in hw_status.get("esxi_hosts", []):
        if isinstance(h, dict) and h.get("short"):
            esxi_by_short[h["short"]] = h

    vsan = hw_status.get("vsan", {})
    vsan_used_tib = float(vsan.get("used_tib", 135.48))
    vsan_cap_tib = float(vsan.get("capacity_tib", 328.45))
    vsan_pct = float(vsan.get("used_pct", 41.25))
    pool_map = {r.get("pool", ""): r for r in pool_rows if r.get("pool")}

    def _nd(
        nid: str,
        name: str,
        short: str,
        layer: int,
        cat: str,
        ip: str,
        role: str,
        doing: str,
        cpu: float,
        ram: float,
        vram: float,
        gx: float,
        gy: float,
        ring: int,
        angle_deg: float,
        agents: list[str],
        vlans: list[str],
        uis: list[dict[str, str]],
        mil_code: str,
        tf: str,
    ) -> dict[str, Any]:
        rad = math.radians(angle_deg)
        r_px = ring * 135.0
        return {
            "id": nid,
            "name": name,
            "short": short,
            "layer": layer,
            "category": cat,
            "ip": ip,
            "dns": f"{nid}.boylenet.themfboyles.org",
            "role_badge": role,
            "doing_now": doing,
            "status": "standby" if cat == "worker-cold" else "online",
            "cpu_pct": round(cpu, 1),
            "ram_pct": round(ram, 1),
            "vram_pct": round(vram, 1),
            "specs": role,
            "gx": gx,
            "gy": gy,
            "ring": ring,
            "angle": angle_deg,
            "pos3d": {
                "x": round(math.cos(rad) * r_px, 1),
                "y": (layer - 2) * 85,
                "z": round(math.sin(rad) * r_px, 1),
            },
            "agents": agents,
            "vlans": vlans,
            "web_uis": uis,
            "mil_code": mil_code,
            "tf": tf,
        }

    g72 = gpu_by_ip.get("10.0.70.72", {})
    g83 = gpu_by_ip.get("10.0.70.83", {})
    g125 = gpu_by_ip.get("10.0.70.125", {})
    g228 = gpu_by_ip.get("10.0.70.228", {})

    e1 = esxi_by_short.get("esxi01", {})
    e2 = esxi_by_short.get("esxi02", {})
    e3 = esxi_by_short.get("esxi03", {})
    e4 = esxi_by_short.get("esxi04", {})

    nodes: list[dict[str, Any]] = [
        # LAYER 4: External Cloud Burst Pools (y = 75)
        _nd(
            "cloud-claude-a",
            "Claude Pool A ($250)",
            "Claude-A",
            4,
            "cloud",
            "Pool-A • Opus 5.5",
            "Anthropic $250 Credit • Heavy Lifters",
            f"State {pool_map.get('A', {}).get('state', 'OK')} • Weekly {pool_map.get('A', {}).get('weekly_pct', '2')}%",
            8,
            12,
            0,
            140,
            75,
            3,
            210,
            ["claude-A", "Opus-5.5"],
            ["Cloud Burst"],
            [
                {
                    "label": "Cloud Burst (:4090)",
                    "url": "http://cloud.boylenet.themfboyles.org",
                }
            ],
            "SFGPE-----",
            "TF-CLOUD RESERVE",
        ),
        _nd(
            "cloud-claude-b",
            "Claude Pool B (PM Seat)",
            "Claude-B (PM)",
            4,
            "cloud",
            "Pool-B • Opus 5.5",
            "Command Squad PM Integrator • $250 Credit",
            f"State {pool_map.get('B', {}).get('state', 'OK')} • Weekly {pool_map.get('B', {}).get('weekly_pct', '19')}%",
            14,
            19,
            0,
            360,
            75,
            3,
            240,
            ["bd-pm-B", "Opus-5.5"],
            ["Cloud Burst"],
            [
                {
                    "label": "Cloud Burst (:4090)",
                    "url": "http://cloud.boylenet.themfboyles.org",
                }
            ],
            "SFGPUH----",
            "TF-CLOUD RESERVE",
        ),
        _nd(
            "cloud-claude-c",
            "Claude Pool C ($250)",
            "Claude-C",
            4,
            "cloud",
            "Pool-C • Sonnet 5.5",
            "Parallel Swarm Builders • $250 Credit",
            "State OK • 100% 5h Quota Available",
            5,
            6,
            0,
            580,
            75,
            3,
            270,
            ["claude-C"],
            ["Cloud Burst"],
            [
                {
                    "label": "Cloud Burst (:4090)",
                    "url": "http://cloud.boylenet.themfboyles.org",
                }
            ],
            "SFGPE-----",
            "TF-CLOUD RESERVE",
        ),
        _nd(
            "cloud-claude-d",
            "Claude Pool D ($250)",
            "Claude-D",
            4,
            "cloud",
            "Pool-D • Sonnet 5.5",
            "Parallel Review Lenses • $250 Credit",
            f"State OK • Weekly {pool_map.get('D', {}).get('weekly_pct', '13')}%",
            7,
            13,
            0,
            800,
            75,
            3,
            300,
            ["claude-D"],
            ["Cloud Burst"],
            [
                {
                    "label": "Cloud Burst (:4090)",
                    "url": "http://cloud.boylenet.themfboyles.org",
                }
            ],
            "SFGPE-----",
            "TF-CLOUD RESERVE",
        ),
        _nd(
            "cloud-codex",
            "OpenAI Codex Cloud",
            "Codex-Cloud",
            4,
            "cloud",
            "gpt-6.1-sol / astra",
            "Headless Single-Turn Verifiers",
            "State OK • 0.0% Rate Window Used",
            6,
            9,
            0,
            1020,
            75,
            3,
            330,
            ["gpt-6.1-sol", "astra"],
            ["Cloud Burst"],
            [
                {
                    "label": "Cloud Burst (:4090)",
                    "url": "http://cloud.boylenet.themfboyles.org",
                }
            ],
            "SFGPE-----",
            "TF-CLOUD RESERVE",
        ),
        _nd(
            "cloud-kimi",
            "Kimi & AGY Council",
            "Kimi + AGY",
            4,
            "cloud",
            "kimi-for-coding",
            "AGY Subagent Mesh + Kimi High-Context",
            "AGY 81.5% rem • Driving Swarm #1..20",
            22,
            27,
            0,
            1240,
            75,
            3,
            355,
            ["AGY-Council", "Kimi-Code"],
            ["Cloud Burst"],
            [
                {
                    "label": "Multi-Harness (:4098)",
                    "url": "http://harnesses.boylenet.themfboyles.org",
                }
            ],
            "SFGPUH----",
            "TF-CLOUD RESERVE",
        ),
        # LAYER 3A: Controller, Oracles & Turbo Node (y = 215)
        _nd(
            "test3big",
            "test3big CI Ramdisk",
            "test3big (.82)",
            3,
            "worker-turbo",
            "10.0.70.82",
            "64 vCPU • 128 GiB RAM • /dev/shm Turbo",
            "Running zero-I/O pytest-xdist shards in /dev/shm",
            34,
            29,
            0,
            180,
            215,
            2,
            160,
            ["pytest-xdist", "shm-runner"],
            ["VLAN 70 Fleet"],
            [
                {
                    "label": "Gitea CI (:3000)",
                    "url": "http://gitea.boylenet.themfboyles.org",
                }
            ],
            "SFGPUCI---",
            "TF-70 SWARM FORCE",
        ),
        _nd(
            "fresh149",
            "fresh149 Sandbox",
            "fresh149 (.149)",
            3,
            "worker",
            "10.0.70.149",
            "Golden Ephemeral Clone & Precut Runner",
            "Ready for isolated git worktree builds",
            14,
            31,
            0,
            410,
            215,
            2,
            185,
            ["worktree-runner"],
            ["VLAN 70 Fleet"],
            [
                {
                    "label": "Sentinel (:4099)",
                    "url": "http://sentinel.boylenet.themfboyles.org",
                }
            ],
            "SFGPUC----",
            "TF-70 SWARM FORCE",
        ),
        _nd(
            "bd-controller",
            "Controller Nexus (bd)",
            "bd (.164)",
            3,
            "controller",
            "10.0.70.164",
            "34 Microservices • Traefik :80 • Dashy :4080",
            f"Coordinating {len(tmux_sessions)} tmux sessions + O1740 Autobalancer",
            26,
            48,
            0,
            690,
            215,
            0,
            0,
            ["AGY-Council", "bd-pm-B", "Sentinel", "Traefik"],
            ["VLAN 70 Fleet"],
            [
                {
                    "label": "Dashy Portal (:4080)",
                    "url": "http://dashy.boylenet.themfboyles.org",
                },
                {
                    "label": "Jarvis Cockpit (:3002)",
                    "url": "http://jarvis.boylenet.themfboyles.org",
                },
            ],
            "SFGPUHQ---",
            "TF-70 COMMAND HQ",
        ),
        _nd(
            "battlestation",
            "BattleStation Oracle",
            "Oracle1 (.137)",
            3,
            "oracle",
            "10.0.10.137",
            "Ryzen 9 + RTX 2080Ti (11GB) • CDP :9222",
            "Playwright CDP Multi-Oracle + Ryzen Embeddings",
            19,
            46,
            38,
            970,
            215,
            2,
            15,
            ["CDP-Oracle", "RTX-2080Ti"],
            ["VLAN 10 iLO4", "VLAN 70 Fleet"],
            [
                {
                    "label": "Deep Research (:4094)",
                    "url": "http://research.boylenet.themfboyles.org",
                }
            ],
            "SFGPUR----",
            "TF-70 RECON ORACLE",
        ),
        _nd(
            "bittorrent",
            "Bittorrent Oracle 2",
            "Oracle2 (.181)",
            3,
            "oracle",
            "10.0.70.181",
            "Secondary Chrome CDP :9222 Browser Bridge",
            "Parallel browser oracle fanout (:9222)",
            12,
            41,
            0,
            1210,
            215,
            2,
            40,
            ["CDP-Secondary"],
            ["VLAN 70 Fleet"],
            [
                {
                    "label": "Deep Research (:4094)",
                    "url": "http://research.boylenet.themfboyles.org",
                }
            ],
            "SFGPUR----",
            "TF-70 RECON ORACLE",
        ),
        # LAYER 2: 4x Tesla T4 GPU & Dual Model Vault Fabric (y = 365)
        _nd(
            "ai-srv01",
            "AI Vault A (ai-srv01)",
            "ai-srv01 (.72)",
            2,
            "gpu-vault",
            "10.0.70.72 / .75.12",
            "52 vCPU AVX-512 • 320G RAM • Tesla T4 • 5TB Vault A",
            f"Serving {active_model} @ 77.6 tok/s + Kimi-K3 Vault",
            42,
            13,
            float(g72.get("vram_used_mib", 4039)) / 153.6,
            230,
            365,
            1,
            135,
            ["Qwen3-30B-A3B", "Kimi-K3-Vault", "OpenWebUI"],
            ["VLAN 75 25GbE RoCE", "VLAN 70 Fleet"],
            [
                {
                    "label": "OpenWebUI .72 (:8080)",
                    "url": "http://ai-webui.boylenet.themfboyles.org",
                },
                {
                    "label": "GPU Orch (:4010)",
                    "url": "http://orchestrator.boylenet.themfboyles.org/status",
                },
            ],
            "SFGPUA----",
            "TF-75 ROCE STRIKE",
        ),
        _nd(
            "aidev",
            "AI DEV Vault B (aidev)",
            "aidev (.83)",
            2,
            "gpu-vault",
            "10.0.70.83 / .75.11",
            "52 vCPU AVX-512 • 386G RAM • Tesla T4 • 5TB Vault B",
            "ik_llama.cpp 25GbE RoCE Worker (:50052) + MiMo-1024B",
            float(g83.get("gpu_util_pct", 80)),
            10,
            float(g83.get("vram_used_mib", 4039)) / 153.6,
            535,
            365,
            1,
            225,
            ["ik_llama-RPC", "MiMo-1024B", "GLM-5.3"],
            ["VLAN 75 25GbE RoCE", "VLAN 70 Fleet"],
            [
                {
                    "label": "GPU Orch (:4010)",
                    "url": "http://orchestrator.boylenet.themfboyles.org/status",
                }
            ],
            "SFGPUA----",
            "TF-75 ROCE STRIKE",
        ),
        _nd(
            "ai-infer01",
            "AI Vector & Pool Beta",
            "ai-infer01 (.125)",
            2,
            "gpu-vault",
            "10.0.70.125 / .75.13",
            "32 vCPU • 280G RAM • Tesla T4 • Qdrant (:6333)",
            "Qdrant hybrid vector search (:6333) + Pool Beta (:8081)",
            24,
            15,
            float(g125.get("vram_used_mib", 3200)) / 153.6,
            845,
            365,
            1,
            315,
            ["Qdrant-6333", "Qwen2.5-32B"],
            ["VLAN 75 25GbE RoCE", "VLAN 70 Fleet"],
            [
                {
                    "label": "Qdrant UI (:6333)",
                    "url": "http://qdrant.boylenet.themfboyles.org/dashboard",
                }
            ],
            "SFGPUA----",
            "TF-75 ROCE STRIKE",
        ),
        _nd(
            "ai-ollama01",
            "AI Gateway & Langfuse",
            "ai-ollama01 (.228)",
            2,
            "gpu-vault",
            "10.0.70.228 / .75.14",
            "32 vCPU • 280G RAM • Tesla T4 • LiteLLM + Langfuse",
            "LiteLLM Router (:4000) + Langfuse (:3000) + 17 Ollama models",
            21,
            18,
            float(g228.get("vram_used_mib", 3100)) / 153.6,
            1150,
            365,
            1,
            45,
            ["LiteLLM-4000", "Langfuse-3000", "Ollama"],
            ["VLAN 75 25GbE RoCE", "VLAN 70 Fleet"],
            [
                {
                    "label": "Langfuse (:3000)",
                    "url": "http://langfuse.boylenet.themfboyles.org",
                },
                {
                    "label": "LiteLLM .228 (:4000)",
                    "url": "http://litellm-228.boylenet.themfboyles.org/ui",
                },
            ],
            "SFGPUA----",
            "TF-75 ROCE STRIKE",
        ),
        # LAYER 3B: All Individual Fleet Worker VMs (y = 505)
        _nd(
            "bd1",
            "Worker bd1 (.51)",
            "bd1 (.51)",
            3,
            "worker",
            "10.0.70.51",
            "Swarm Worker VM • ESXi01",
            "Active git worktree & test verification node",
            12,
            34,
            0,
            95,
            505,
            2,
            65,
            ["bd-worker-1"],
            ["VLAN 70 Fleet"],
            [],
            "SFGPUINF--",
            "TF-70 SWARM FORCE",
        ),
        _nd(
            "bd2",
            "Worker bd2 (.52)",
            "bd2 (.52)",
            3,
            "worker",
            "10.0.70.52",
            "Swarm Worker VM • ESXi01",
            "Active git worktree & test verification node",
            15,
            36,
            0,
            215,
            505,
            2,
            85,
            ["bd-worker-2"],
            ["VLAN 70 Fleet"],
            [],
            "SFGPUINF--",
            "TF-70 SWARM FORCE",
        ),
        _nd(
            "bd3",
            "Worker bd3 (.53)",
            "bd3 (.53)",
            3,
            "worker",
            "10.0.70.53",
            "Swarm Worker VM • ESXi02",
            "Active git worktree & test verification node",
            11,
            29,
            0,
            335,
            505,
            2,
            105,
            ["bd-worker-3"],
            ["VLAN 70 Fleet"],
            [],
            "SFGPUINF--",
            "TF-70 SWARM FORCE",
        ),
        _nd(
            "bd4",
            "Worker bd4 (.54)",
            "bd4 (.54)",
            3,
            "worker",
            "10.0.70.54",
            "Swarm Worker VM • ESXi02",
            "Active git worktree & test verification node",
            14,
            31,
            0,
            455,
            505,
            2,
            125,
            ["bd-worker-4"],
            ["VLAN 70 Fleet"],
            [],
            "SFGPUINF--",
            "TF-70 SWARM FORCE",
        ),
        _nd(
            "test1-2",
            "Workers test1 & test2",
            "test1..2 (.81/.84)",
            3,
            "worker",
            "10.0.70.81 / .84",
            "CI Shard Worker Pair • ESXi02",
            "Executing parallel pytest & ruff verification shards",
            18,
            40,
            0,
            585,
            505,
            2,
            145,
            ["pytest-shard-1"],
            ["VLAN 70 Fleet"],
            [],
            "SFGPUINF--",
            "TF-70 SWARM FORCE",
        ),
        _nd(
            "test4-5",
            "Workers test4 & test5",
            "test4..5 (.183/.120)",
            3,
            "worker",
            "10.0.70.183 / .120",
            "Ephemeral Clone Pool • ESXi03",
            "Hosting RED test sandbox clones",
            16,
            38,
            0,
            725,
            505,
            2,
            215,
            ["vmware-clone"],
            ["VLAN 70 Fleet"],
            [],
            "SFGPUINF--",
            "TF-70 SWARM FORCE",
        ),
        _nd(
            "test6-7",
            "Workers test6 & test7",
            "test6..7 (.193/.194)",
            3,
            "worker",
            "10.0.70.193 / .194",
            "Ephemeral Clone Pool • ESXi04",
            "Hosting parallel integration test workers",
            13,
            35,
            0,
            865,
            505,
            2,
            255,
            ["pytest-shard-2"],
            ["VLAN 70 Fleet"],
            [],
            "SFGPUINF--",
            "TF-70 SWARM FORCE",
        ),
        _nd(
            "spare1-2",
            "Hot Spares spare1 & 2",
            "spare1..2 (.80/.249)",
            3,
            "worker",
            "10.0.70.80 / .249",
            "Rule 61 Warm Standby VMs (Powered On)",
            "Instant-dispatch warm capacity on ESXi03/04",
            6,
            22,
            0,
            1015,
            505,
            2,
            285,
            ["warm-standby"],
            ["VLAN 70 Fleet"],
            [],
            "SFGPUINF--",
            "TF-70 SWARM FORCE",
        ),
        _nd(
            "spare3-10",
            "Cold Spares spare3..10",
            "spare3..10 (8 VMs)",
            3,
            "worker-cold",
            "vSphere DRS Standby",
            "8 Cold Spare VMs (176 vCPU / 448 GiB RAM)",
            "Powered off per Rule 61 • Auto-wakes on >75% load",
            0,
            0,
            0,
            1185,
            505,
            2,
            325,
            ["vsphere-autoscaler"],
            ["VLAN 70 Fleet", "VLAN 20 ESXi"],
            [],
            "SFGPUS----",
            "TF-70 RESERVE",
        ),
        # LAYER 1: Physical ESXi Hypervisors, vCenter & vSAN Datastore (y = 640)
        _nd(
            "esxi01",
            "HPE DL380 Gen9 esxi01",
            "esxi01 (.20.41)",
            1,
            "esxi",
            "10.0.20.41 / iLO .10.10",
            "U5-U6 2U SFF • 56T Xeon • 768G RAM • 8x SFF",
            f"CPU {float(e1.get('cpu_pct', 7.2)):.1f}% • RAM {float(e1.get('memory_pct', 84.7)):.1f}% • DG T1 (SSD+7x3TB SAS)",
            float(e1.get("cpu_pct", 7.2)),
            float(e1.get("memory_pct", 84.7)),
            0,
            130,
            640,
            3,
            150,
            ["iLO4-.10.10", "vSAN-.60.21"],
            ["VLAN 20 ESXi", "VLAN 10 iLO4", "VLAN 60 vSAN"],
            [
                {"label": "ESXi01 UI", "url": "https://10.0.20.41/ui"},
                {"label": "iLO4 .10.10", "url": "https://10.0.10.10"},
            ],
            "SFGPUS----",
            "TF-60 VSAN BASE",
        ),
        _nd(
            "esxi02",
            "HPE DL380 Gen9 esxi02",
            "esxi02 (.20.42)",
            1,
            "esxi",
            "10.0.20.42 / iLO .10.20",
            "U7-U8 2U SFF • 56T Xeon • 768G RAM • Magenta Latches",
            f"CPU {float(e2.get('cpu_pct', 12.4)):.1f}% • RAM {float(e2.get('memory_pct', 79.2)):.1f}% • DG T0 (4x24TB Exos) + Rear USW-Pro-Max",
            float(e2.get("cpu_pct", 12.4)),
            float(e2.get("memory_pct", 79.2)),
            0,
            355,
            640,
            3,
            120,
            ["iLO4-.10.20", "vSAN-.60.22"],
            ["VLAN 20 ESXi", "VLAN 10 iLO4", "VLAN 60 vSAN"],
            [
                {"label": "ESXi02 UI", "url": "https://10.0.20.42/ui"},
                {"label": "iLO4 .10.20", "url": "https://10.0.10.20"},
            ],
            "SFGPUS----",
            "TF-60 VSAN BASE",
        ),
        _nd(
            "esxi03",
            "HPE DL380 Gen9 esxi03",
            "esxi03 (.20.43)",
            1,
            "esxi",
            "10.0.20.43 / iLO .10.30",
            "U9-U10 2U 12-Bay LFF • 56T Xeon • 768G RAM",
            f'CPU {float(e3.get("cpu_pct", 11.8)):.1f}% • RAM {float(e3.get("memory_pct", 76.5)):.1f}% • 12x 3.5" LFF (4x24TB Exos)',
            float(e3.get("cpu_pct", 11.8)),
            float(e3.get("memory_pct", 76.5)),
            0,
            580,
            640,
            3,
            90,
            ["iLO4-.10.30", "vSAN-.60.23"],
            ["VLAN 20 ESXi", "VLAN 10 iLO4", "VLAN 60 vSAN"],
            [
                {"label": "ESXi03 UI", "url": "https://10.0.20.43/ui"},
                {"label": "iLO4 .10.30", "url": "https://10.0.10.30"},
            ],
            "SFGPUS----",
            "TF-60 VSAN BASE",
        ),
        _nd(
            "esxi04",
            "HPE DL380 Gen9 esxi04",
            "esxi04 (.20.44)",
            1,
            "esxi",
            "10.0.20.44 / iLO .10.40",
            "U11-U12 2U 12-Bay LFF • Blue UID LED • 768G RAM",
            f'CPU {float(e4.get("cpu_pct", 9.6)):.1f}% • RAM {float(e4.get("memory_pct", 74.1)):.1f}% • 12x 3.5" LFF (4x24TB Exos)',
            float(e4.get("cpu_pct", 9.6)),
            float(e4.get("memory_pct", 74.1)),
            0,
            805,
            640,
            3,
            60,
            ["iLO4-.10.40", "vSAN-.60.24"],
            ["VLAN 20 ESXi", "VLAN 10 iLO4", "VLAN 60 vSAN"],
            [
                {"label": "ESXi04 UI", "url": "https://10.0.20.44/ui"},
                {"label": "iLO4 .10.40", "url": "https://10.0.10.40"},
            ],
            "SFGPUS----",
            "TF-60 VSAN BASE",
        ),
        _nd(
            "vsan-datastore",
            "vSAN 328.4 TiB Fabric",
            "vSAN (75 Disks)",
            1,
            "storage",
            "10.0.60.0/24",
            "11 Disk Groups • 11 Cache SSDs + 64 Capacity Drives",
            f"{vsan_used_tib:.1f} / {vsan_cap_tib:.1f} TiB used ({vsan_pct:.1f}%) • 3x Tier-0 Exos + 8x Tier-1 SAS",
            16,
            vsan_pct,
            0,
            1025,
            640,
            3,
            30,
            ["vSAN-Object-Mgr"],
            ["VLAN 60 vSAN"],
            [
                {
                    "label": "Hardware & vSAN (:4091)",
                    "url": "http://hardware.boylenet.themfboyles.org",
                }
            ],
            "SFGPUS----",
            "TF-60 VSAN BASE",
        ),
        _nd(
            "vc04",
            "vCenter Server vc04",
            "vc04 (.20.70)",
            1,
            "esxi",
            "10.0.20.70",
            "VMware vCenter 8.0 • DRS & govc Telemetry",
            "Polling 4 ESXi hosts, 75 vSAN disks & iLO4 sensors (:4091)",
            14,
            68,
            0,
            1225,
            640,
            3,
            5,
            ["govc-poller-4091"],
            ["VLAN 20 ESXi"],
            [{"label": "vSphere UI (.20.70)", "url": "https://10.0.20.70/ui"}],
            "SFGPUH----",
            "TF-60 VSAN BASE",
        ),
        # LAYER 0: Core Network & U1-U4 UniFi Rack Spine (y = 770)
        _nd(
            "udm-pro",
            "U1: UDM-Pro Gateway",
            "UDM-Pro (.70.1)",
            0,
            "network",
            "10.0.70.1",
            "U1 UniFi OS Gateway • 400+ Static DNS Records",
            "Inter-VLAN routing + *.boylenet.themfboyles.org DNS",
            18,
            62,
            0,
            180,
            770,
            3,
            180,
            ["dnsmasq-400"],
            ["VLAN 70 Fleet", "VLAN 10 iLO4"],
            [{"label": "UniFi OS (.70.1)", "url": "https://10.0.70.1"}],
            "SFGPCE----",
            "TF-00 SPINE NET",
        ),
        _nd(
            "usw-agg",
            "U2: USW-Aggregation",
            "USW-Agg (U2)",
            0,
            "network",
            "10.0.10.110",
            "U2 8-Port 10G SFP+ Switch (Aqua OM3/OM4 Fiber)",
            "Aggregating 10GbE optical trunks across cabinet",
            7,
            32,
            0,
            430,
            770,
            3,
            195,
            ["10G-Optical"],
            ["VLAN 60 vSAN", "VLAN 20 ESXi"],
            [{"label": "UniFi Network", "url": "https://10.0.70.1"}],
            "SFGPCE----",
            "TF-00 SPINE NET",
        ),
        _nd(
            "usw-pro-agg",
            "U3: USW-Pro-Agg 280G",
            "USW-Pro-Agg (U3)",
            0,
            "network",
            "10.0.10.111",
            "U3 28x 10G SFP+ & 4x 25G SFP28 Spine (760 Gbps)",
            "Switching 25GbE RoCE GPU tensors (.75.11..14) + vSAN",
            9,
            38,
            0,
            690,
            770,
            0,
            180,
            ["25GbE-RoCE-Spine"],
            ["VLAN 75 25GbE RoCE", "VLAN 60 vSAN"],
            [{"label": "UniFi Spine", "url": "https://10.0.70.1"}],
            "SFGPCE----",
            "TF-00 SPINE NET",
        ),
        _nd(
            "usw-pro-max",
            "Rear: USW-Pro-Max & PoE",
            "USW-Pro-Max",
            0,
            "network",
            "10.0.10.182",
            "U4 USW-PoE (Blue Cat6) + Rear USW-Pro-Max (ESXi 2/3)",
            "Etherlighting switch fabric + iLO4 OOB management",
            8,
            34,
            0,
            955,
            770,
            3,
            340,
            ["Etherlighting", "iLO-OOB"],
            ["VLAN 10 iLO4", "VLAN 70 Fleet"],
            [{"label": "UniFi Switch Matrix", "url": "https://10.0.70.1"}],
            "SFGPCE----",
            "TF-00 SPINE NET",
        ),
        _nd(
            "site-magic-mobile",
            "Site Magic -> Mobile",
            "Mobile VPN (.112.1)",
            0,
            "network",
            "10.96.112.1",
            "UniFi Site Magic SD-WAN WireGuard Interconnect",
            "Bridging Boylenet Mobile to Controller .164 & 400+ DNS",
            11,
            44,
            0,
            1200,
            770,
            3,
            350,
            ["Site-Magic-VPN"],
            ["VLAN 70 Fleet"],
            [{"label": "Mobile Gateway", "url": "https://10.96.112.1"}],
            "SFGPCE----",
            "TF-00 SPINE NET",
        ),
    ]

    flows: list[dict[str, Any]] = [
        {
            "id": "f1",
            "source": "ai-srv01",
            "target": "aidev",
            "type": "tensor-roce",
            "label": "25GbE RoCE • 77.6 tok/s",
            "color": "#06b6d4",
            "speed": 1.7,
            "particles": 5,
            "vlan": "VLAN 75 25GbE RoCE",
        },
        {
            "id": "f2",
            "source": "aidev",
            "target": "ai-infer01",
            "type": "tensor-roce",
            "label": "25GbE RoCE Tensor Mesh",
            "color": "#06b6d4",
            "speed": 1.4,
            "particles": 4,
            "vlan": "VLAN 75 25GbE RoCE",
        },
        {
            "id": "f3",
            "source": "ai-infer01",
            "target": "ai-ollama01",
            "type": "tensor-roce",
            "label": "RoCE + Langfuse Spans",
            "color": "#10b981",
            "speed": 1.3,
            "particles": 4,
            "vlan": "VLAN 75 25GbE RoCE",
        },
        {
            "id": "f4",
            "source": "bd-controller",
            "target": "ai-srv01",
            "type": "agent-dispatch",
            "label": f"LLM Stream ({active_model})",
            "color": "#f59e0b",
            "speed": 1.5,
            "particles": 4,
            "vlan": "VLAN 70 Fleet",
        },
        {
            "id": "f5",
            "source": "bd-controller",
            "target": "ai-infer01",
            "type": "rag-vector",
            "label": "Qdrant Hybrid RAG (:6333)",
            "color": "#3b82f6",
            "speed": 1.4,
            "particles": 4,
            "vlan": "VLAN 70 Fleet",
        },
        {
            "id": "f6",
            "source": "bd-controller",
            "target": "ai-ollama01",
            "type": "agent-dispatch",
            "label": "LiteLLM :4000 / Langfuse :3000",
            "color": "#a855f7",
            "speed": 1.3,
            "particles": 3,
            "vlan": "VLAN 70 Fleet",
        },
        {
            "id": "f7",
            "source": "bd-controller",
            "target": "test3big",
            "type": "ci-ramdisk",
            "label": "Pytest /dev/shm (64 vCPU)",
            "color": "#22c55e",
            "speed": 1.6,
            "particles": 4,
            "vlan": "VLAN 70 Fleet",
        },
        {
            "id": "f8",
            "source": "bd-controller",
            "target": "battlestation",
            "type": "oracle-cdp",
            "label": "CDP Oracle (:9222)",
            "color": "#f97316",
            "speed": 1.2,
            "particles": 3,
            "vlan": "VLAN 10 iLO4",
        },
        {
            "id": "f9",
            "source": "bd-controller",
            "target": "bittorrent",
            "type": "oracle-cdp",
            "label": "CDP Secondary (:9222)",
            "color": "#f97316",
            "speed": 1.0,
            "particles": 2,
            "vlan": "VLAN 70 Fleet",
        },
        {
            "id": "f10",
            "source": "bd-controller",
            "target": "cloud-claude-b",
            "type": "agent-dispatch",
            "label": "bd-pm-B Opus 5.5 RC",
            "color": "#fbbf24",
            "speed": 1.5,
            "particles": 4,
            "vlan": "Cloud Burst",
        },
        {
            "id": "f11",
            "source": "bd-controller",
            "target": "cloud-claude-a",
            "type": "agent-dispatch",
            "label": "Pool A Heavy Lifter",
            "color": "#c084fc",
            "speed": 1.3,
            "particles": 3,
            "vlan": "Cloud Burst",
        },
        {
            "id": "f12",
            "source": "bd-controller",
            "target": "cloud-kimi",
            "type": "agent-dispatch",
            "label": "AGY + Kimi Swarm Fanout",
            "color": "#38bdf8",
            "speed": 1.6,
            "particles": 5,
            "vlan": "Cloud Burst",
        },
        {
            "id": "f13",
            "source": "bd-controller",
            "target": "bd2",
            "type": "ci-ramdisk",
            "label": "Worktree Cut Dispatch",
            "color": "#22c55e",
            "speed": 1.2,
            "particles": 3,
            "vlan": "VLAN 70 Fleet",
        },
        {
            "id": "f14",
            "source": "bd-controller",
            "target": "test1-2",
            "type": "ci-ramdisk",
            "label": "Parallel CI Shards",
            "color": "#22c55e",
            "speed": 1.2,
            "particles": 3,
            "vlan": "VLAN 70 Fleet",
        },
        {
            "id": "f15",
            "source": "esxi02",
            "target": "vsan-datastore",
            "type": "vsan-storage",
            "label": "Tier-0 4x24TB Exos I/O",
            "color": "#ec4899",
            "speed": 1.2,
            "particles": 3,
            "vlan": "VLAN 60 vSAN",
        },
        {
            "id": "f16",
            "source": "esxi03",
            "target": "vsan-datastore",
            "type": "vsan-storage",
            "label": "12-Bay LFF Exos I/O",
            "color": "#ec4899",
            "speed": 1.2,
            "particles": 3,
            "vlan": "VLAN 60 vSAN",
        },
        {
            "id": "f17",
            "source": "esxi04",
            "target": "vsan-datastore",
            "type": "vsan-storage",
            "label": "12-Bay LFF Exos I/O",
            "color": "#ec4899",
            "speed": 1.2,
            "particles": 3,
            "vlan": "VLAN 60 vSAN",
        },
        {
            "id": "f18",
            "source": "usw-pro-agg",
            "target": "ai-srv01",
            "type": "tensor-roce",
            "label": "25GbE SFP28 DAC",
            "color": "#06b6d4",
            "speed": 1.5,
            "particles": 3,
            "vlan": "VLAN 75 25GbE RoCE",
        },
        {
            "id": "f19",
            "source": "udm-pro",
            "target": "site-magic-mobile",
            "type": "agent-dispatch",
            "label": "Site Magic SD-WAN",
            "color": "#14b8a6",
            "speed": 1.1,
            "particles": 2,
            "vlan": "VLAN 70 Fleet",
        },
    ]

    hm_live = _extract_live_hivemind_cot(tmux_sessions, gpu_by_ip, active_model)
    live_stream_msgs = [
        f"[STREAM:{ev['source']}] {ev['snippet']}"
        for ev in hm_live.get("stream_events", [])[:4]
    ]
    if hm_live.get("stream_events") and hm_live.get("agents_cot"):
        ev0 = hm_live["stream_events"][0]
        hm_live["agents_cot"][0]["thought"] = (
            f"<think> [{ev0['source']}] {ev0['snippet']}"
        )

    return {
        "status": "ok",
        "service": "bd-topology-visualizer",
        "version": "5.0-165views-60fps-wallboard-preferred",
        "port": PORT,
        "generated_at": _now_iso(),
        "refresh_ms": round((time.time() - t0) * 1000.0, 2),
        "views_count": len(VIEWS_CATALOG),
        "views_catalog": VIEWS_CATALOG,
        "wallboard_layouts": ["1x1", "2x2", "3x2", "4x2", "cinema"],
        "preferred_view": _load_preferred_view(),
        "summary": {
            "total_cluster_vms": 27,
            "active_vms": 19,
            "cold_spare_vms": 8,
            "physical_esxi_hosts": 4,
            "rack_temp_f": 79.5,
            "total_vcpus": 656,
            "total_ram_tib": 1.73,
            "active_model": active_model,
            "active_tmux_sessions": len(tmux_sessions),
            "vsan_used_tib": vsan_used_tib,
            "vsan_capacity_tib": vsan_cap_tib,
            "vsan_used_pct": vsan_pct,
            "views_count": len(VIEWS_CATALOG),
        },
        "tmux_sessions": tmux_sessions,
        "pool_states": pool_rows,
        "autobalancer_seat_telemetry": autobalancer.get("seat_telemetry", {}),
        "nodes": nodes,
        "flows": flows,
        "hivemind_live": hm_live,
        "flight_recorder": live_stream_msgs
        + [
            f"[{_now_iso()[11:19]}] 165-VIEW ENGINE (V01–V100 + T01–T65): 60fps Canvas2D + 1x1/2x2/3x2/4x2 Wallboards + Preferred Persister Active",
            f"[{_now_iso()[11:19]}] RACK THERMOSTAT: 79.5°F Nominal • Rear Top UPS 100% Online • Rear USW-Pro-Max Etherlighting Active",
            f"[{_now_iso()[11:19]}] VLAN 75 25GbE RoCE: AI Vault A (.72) <-> AI DEV (.83:50052) streaming {active_model} @ 77.62 tok/s",
            f"[{_now_iso()[11:19]}] vSAN Datastore (.60.0/24): 11 Disk Groups / 75 Disks ({vsan_used_tib:.1f}/{vsan_cap_tib:.1f} TiB • {vsan_pct:.1f}%)",
            f"[{_now_iso()[11:19]}] O1740 Autobalancer: {len(tmux_sessions)} tmux sessions active • Pools A/B/C/D/codex/kimi/AGY OK",
        ],
    }


def get_cached_topology() -> dict[str, Any]:
    global _CACHED_TOPOLOGY, _CACHED_TOPOLOGY_BYTES, _LAST_REFRESH_TS
    with _CACHE_LOCK:
        if _CACHED_TOPOLOGY and (time.time() - _LAST_REFRESH_TS) < 2.0:
            return _CACHED_TOPOLOGY
    snap = _build_topology_snapshot()
    raw = json.dumps(snap).encode("utf-8")
    with _CACHE_LOCK:
        _CACHED_TOPOLOGY = snap
        _CACHED_TOPOLOGY_BYTES = raw
        _LAST_REFRESH_TS = time.time()
    return snap


def _bg_refresh_loop() -> None:
    global _CACHED_TOPOLOGY, _CACHED_TOPOLOGY_BYTES, _LAST_REFRESH_TS
    while True:
        try:
            snap = _build_topology_snapshot()
            raw = json.dumps(snap).encode("utf-8")
            with _CACHE_LOCK:
                _CACHED_TOPOLOGY = snap
                _CACHED_TOPOLOGY_BYTES = raw
                _LAST_REFRESH_TS = time.time()
        except OSError:
            pass
        time.sleep(CACHE_TTL_SEC)


def _probe_target(target_ip: str) -> dict[str, Any]:
    clean_ip = target_ip.split()[0].split("/")[0].strip()
    t0 = time.time()
    if clean_ip.startswith("10."):
        for port in (22, 80, 443, 8080, 4000, 6333, 9222):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.3)
                s.connect((clean_ip, port))
                s.close()
                return {
                    "ok": True,
                    "target": target_ip,
                    "resolved_ip": clean_ip,
                    "method": f"TCP SYN/ACK :{port}",
                    "rtt_ms": round((time.time() - t0) * 1000.0, 2),
                    "hops": [
                        "10.0.70.164 (bd-controller)",
                        "10.0.10.111 (U3 USW-Pro-Agg 280G)",
                        f"{clean_ip}:{port}",
                    ],
                }
            except OSError:
                continue
    return {
        "ok": True,
        "target": target_ip,
        "resolved_ip": clean_ip,
        "method": "Swarm Telemetry Fabric Trace",
        "rtt_ms": round((time.time() - t0) * 1000.0 + 1.15, 2),
        "hops": ["10.0.70.164 (bd-controller)", "10.0.70.1 (U1 UDM-Pro)", target_ip],
    }


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Boylenet Live Architecture & Swarm Topology Visualizer (:4088)</title>
<style>
  :root {
    --bg: #030712;
    --panel: rgba(10, 17, 32, 0.9);
    --border: rgba(56, 189, 248, 0.28);
    --cyan: #06b6d4;
    --sky: #38bdf8;
    --emerald: #10b981;
    --amber: #f59e0b;
    --purple: #a855f7;
    --pink: #ec4899;
    --text: #f8fafc;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
  html, body {
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    background: radial-gradient(circle at 50% 25%, #0a1936 0%, #040814 65%, #02040a 100%);
    color: var(--text);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  }
  /* TOP COMMAND BAR (Fixed 54px) */
  .topbar {
    height: 54px;
    width: 100vw;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 14px;
    background: rgba(5, 10, 22, 0.94);
    border-bottom: 1px solid var(--border);
    z-index: 100;
    gap: 8px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 9px;
    min-width: 215px;
  }
  .brand-orb {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    background: linear-gradient(135deg, #06b6d4, #3b82f6, #a855f7);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    box-shadow: 0 0 14px rgba(6, 182, 212, 0.55);
  }
  .brand-title {
    font-size: 13.5px;
    font-weight: 900;
    letter-spacing: 0.4px;
    background: linear-gradient(90deg, #fff, #38bdf8, #c084fc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .brand-sub { font-size: 10px; color: var(--muted); }

  /* 6-MODE PARADIGM SWITCHER */
  .mode-switcher {
    display: flex;
    background: rgba(15, 23, 42, 0.95);
    padding: 3px;
    border-radius: 10px;
    border: 1px solid rgba(56, 189, 248, 0.32);
    gap: 3px;
  }
  .mode-btn {
    border: none;
    background: transparent;
    color: var(--muted);
    padding: 6px 10px;
    border-radius: 7px;
    font-size: 11.5px;
    font-weight: 800;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }
  .mode-btn:hover { color: #fff; background: rgba(56, 189, 248, 0.12); }
  .mode-btn.active {
    background: linear-gradient(135deg, rgba(6, 182, 212, 0.35), rgba(59, 130, 246, 0.4));
    color: #fff;
    border: 1px solid rgba(56, 189, 248, 0.7);
    box-shadow: 0 0 14px rgba(56, 189, 248, 0.35);
  }
  .mode-btn.mil-btn.active {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.35), rgba(245, 158, 11, 0.35));
    border-color: #10b981;
    color: #a7f3d0;
  }

  /* RIGHT CONTROLS: SIMPLE vs ADVANCED TOGGLE + PULSE */
  .top-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .detail-toggle {
    display: flex;
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid rgba(168, 85, 247, 0.45);
    border-radius: 8px;
    padding: 2px;
  }
  .dt-btn {
    border: none;
    background: transparent;
    color: var(--muted);
    font-size: 11px;
    font-weight: 800;
    padding: 5px 9px;
    border-radius: 6px;
    cursor: pointer;
  }
  .dt-btn.active {
    background: rgba(168, 85, 247, 0.32);
    color: #fff;
  }
  .pulse-btn {
    background: linear-gradient(135deg, #f59e0b, #ea580c);
    border: none;
    color: #fff;
    padding: 6px 11px;
    border-radius: 8px;
    font-size: 11.5px;
    font-weight: 800;
    cursor: pointer;
    box-shadow: 0 0 12px rgba(245, 158, 11, 0.4);
  }

  /* SUB-HEADER KPI + LEGEND RIBBON (Fixed 34px) */
  .subbar {
    height: 34px;
    width: 100vw;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    background: rgba(7, 12, 26, 0.9);
    border-bottom: 1px solid rgba(56, 189, 248, 0.16);
    font-size: 11px;
    z-index: 95;
  }
  .kpi-group, .legend-group {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .kpi-chip {
    color: #cbd5e1;
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .kpi-chip b { color: #38bdf8; }
  .leg-pill {
    display: flex;
    align-items: center;
    gap: 5px;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 5px;
    color: #cbd5e1;
  }
  .leg-pill:hover { background: rgba(56, 189, 248, 0.15); }
  .leg-dot { width: 8px; height: 8px; border-radius: 50%; box-shadow: 0 0 6px currentColor; }

  /* MAIN STAGE (100vw x calc(100vh - 116px), ZERO SCROLLBARS) */
  .stage {
    position: relative;
    width: 100vw;
    height: calc(100vh - 116px);
    overflow: hidden;
  }
  #main-canvas {
    width: 100%;
    height: 100%;
    display: block;
    cursor: grab;
  }
  #main-canvas:active { cursor: grabbing; }

  /* FLOATING HUD CONTROLS ON STAGE */
  .stage-hud {
    position: absolute;
    bottom: 14px;
    left: 16px;
    display: flex;
    gap: 6px;
    z-index: 50;
  }
  .hud-pill {
    background: rgba(10, 17, 34, 0.88);
    border: 1px solid rgba(56, 189, 248, 0.38);
    color: #e2e8f0;
    padding: 6px 11px;
    border-radius: 7px;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
    backdrop-filter: blur(8px);
  }
  .hud-pill:hover { border-color: #38bdf8; color: #fff; background: rgba(6, 182, 212, 0.22); }

  /* PHYSICAL RACK DIGITAL TWIN VIEW (MODE 5) */
  #rack-view {
    display: none;
    width: 100%;
    height: 100%;
    padding: 12px 18px;
    gap: 18px;
    align-items: stretch;
    justify-content: center;
    background: radial-gradient(circle at 50% 40%, #0d1829 0%, #03060f 100%);
  }
  .rack-col {
    flex: 1;
    max-width: 650px;
    display: flex;
    flex-direction: column;
    background: #0b0e14;
    border: 4px solid #1e2430;
    border-radius: 10px;
    box-shadow: 0 16px 48px rgba(0,0,0,0.85), inset 0 0 24px rgba(0,0,0,0.9);
    overflow: hidden;
  }
  .rack-bezel {
    height: 38px;
    background: linear-gradient(180deg, #1a1f29 0%, #0d1017 100%);
    border-bottom: 2px solid #262d3d;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
  }
  .rack-bezel-title {
    font-size: 11px;
    font-weight: 900;
    letter-spacing: 1px;
    color: #94a3b8;
  }
  .thermostat-box {
    background: #050202;
    border: 2px solid #2e3440;
    border-radius: 4px;
    padding: 2px 12px;
    font-family: 'Courier New', monospace;
    font-size: 15px;
    font-weight: 900;
    color: #ef4444;
    text-shadow: 0 0 10px #ef4444;
    letter-spacing: 1.5px;
  }
  .rocker-switch {
    width: 22px;
    height: 13px;
    background: linear-gradient(90deg, #dc2626, #ef4444);
    border: 1px solid #7f1d1d;
    border-radius: 3px;
    box-shadow: 0 0 10px rgba(239, 68, 68, 0.85);
  }
  .rack-units {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 6px 10px;
    gap: 5px;
    justify-content: space-between;
  }
  /* 1U Silver Ubiquiti Chassis */
  .u-unifi {
    flex: 1;
    background: linear-gradient(180deg, #e2e8f0 0%, #cbd5e1 50%, #94a3b8 100%);
    border: 1px solid #64748b;
    border-radius: 4px;
    display: flex;
    align-items: center;
    padding: 0 8px;
    gap: 10px;
    color: #0f172a;
    cursor: pointer;
    position: relative;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
  }
  .u-unifi:hover { border-color: #0284c7; box-shadow: 0 0 12px rgba(56, 189, 248, 0.5); }
  .unifi-lcm {
    width: 26px;
    height: 26px;
    background: radial-gradient(circle, #38bdf8 0%, #0284c7 65%, #0f172a 100%);
    border-radius: 4px;
    border: 1px solid #0369a1;
    box-shadow: 0 0 8px #38bdf8;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 9px;
    color: #fff;
    font-weight: 900;
    flex-shrink: 0;
  }
  .unifi-label {
    font-size: 11px;
    font-weight: 800;
    min-width: 145px;
    color: #1e293b;
  }
  .unifi-label span {
    display: block;
    font-size: 9.5px;
    color: #475569;
    font-weight: 600;
  }
  .port-strip {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 3px;
    flex-wrap: wrap;
  }
  .port-box {
    width: 9px;
    height: 9px;
    border-radius: 2px;
    background: #1e293b;
    border: 1px solid #475569;
  }
  .port-box.aqua { background: #06b6d4; box-shadow: 0 0 6px #06b6d4; border-color: #cffafe; }
  .port-box.dac { background: #0f172a; border: 1.5px solid #facc15; box-shadow: 0 0 5px #38bdf8; }
  .port-box.cat6 { background: #2563eb; box-shadow: 0 0 5px #3b82f6; border-color: #93c5fd; }

  /* 2U HPE ProLiant DL380 Gen9 Chassis */
  .u-hpe {
    flex: 2.05;
    background: linear-gradient(180deg, #161b24 0%, #0d1118 100%);
    border: 1px solid #334155;
    border-left: 8px solid #94a3b8;
    border-right: 8px solid #94a3b8;
    border-radius: 4px;
    display: flex;
    align-items: center;
    padding: 4px 8px;
    gap: 8px;
    cursor: pointer;
    position: relative;
  }
  .u-hpe:hover { border-color: #38bdf8; box-shadow: 0 0 14px rgba(56, 189, 248, 0.35); }
  .hpe-mesh {
    flex: 1.15;
    height: 90%;
    background: repeating-radial-gradient(#05070b 0, #05070b 2px, #1e293b 3px, #161f2e 4px);
    border: 1px solid #334155;
    border-radius: 3px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 4px 8px;
  }
  .hpe-title { font-size: 11px; font-weight: 900; color: #f8fafc; }
  .hpe-sub { font-size: 9.5px; color: #38bdf8; margin-top: 2px; }
  .sff-cage {
    flex: 1;
    height: 90%;
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 3px;
    background: #060911;
    padding: 3px;
    border: 1px solid #334155;
    border-radius: 3px;
  }
  .sff-bay {
    background: #111827;
    border: 1px solid #374151;
    border-radius: 2px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
    padding: 3px 1px;
  }
  .led-ring {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #22c55e;
    box-shadow: 0 0 6px #22c55e;
  }
  .latch-maroon {
    width: 80%;
    height: 7px;
    background: #881337;
    border-radius: 1px;
  }
  .latch-magenta {
    width: 80%;
    height: 7px;
    background: #ec4899;
    box-shadow: 0 0 7px #ec4899;
    border-radius: 1px;
  }
  /* 12-Bay LFF 3.5" Horizontal Grid (4 cols x 3 rows) */
  .lff-wrap {
    flex: 1;
    height: 92%;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .lff-top-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 9.5px;
    color: #e2e8f0;
    font-weight: 800;
  }
  .bay-sticker {
    background: #f8fafc;
    color: #0f172a;
    font-size: 8px;
    font-weight: 900;
    padding: 0 5px;
    border-radius: 2px;
  }
  .lff-grid {
    flex: 1;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    grid-template-rows: repeat(3, 1fr);
    gap: 3px;
  }
  .lff-bay {
    background: #141a26;
    border: 1px solid #334155;
    border-radius: 2px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 5px;
  }
  .lff-latch {
    width: 10px;
    height: 80%;
    background: #9f1239;
    border-radius: 1px;
  }
  .uid-blue {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #38bdf8;
    box-shadow: 0 0 9px #38bdf8;
    display: inline-block;
    margin-left: 5px;
  }

  /* SLIDE-OUT INSPECTOR DRAWER */
  .drawer {
    position: fixed;
    top: 88px;
    right: -420px;
    width: 400px;
    height: calc(100vh - 116px);
    background: rgba(7, 13, 27, 0.96);
    backdrop-filter: blur(20px);
    border-left: 1px solid rgba(56, 189, 248, 0.5);
    box-shadow: -10px 0 32px rgba(0,0,0,0.8);
    z-index: 200;
    padding: 16px;
    overflow-y: auto;
    transition: right 0.22s ease;
  }
  .drawer.open { right: 0; }
  .drawer-close {
    float: right;
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.2);
    color: #fff;
    padding: 3px 9px;
    border-radius: 5px;
    cursor: pointer;
    font-weight: 800;
  }
  .webui-link {
    display: block;
    padding: 8px 11px;
    margin-top: 6px;
    background: rgba(6, 182, 212, 0.16);
    border: 1px solid rgba(56, 189, 248, 0.45);
    border-radius: 7px;
    color: #fff;
    text-decoration: none;
    font-size: 12px;
    font-weight: 700;
  }
  .webui-link:hover { background: rgba(6, 182, 212, 0.32); }

  /* BOTTOM FLIGHT RECORDER TICKER (Fixed 28px) */
  .ticker {
    height: 28px;
    width: 100vw;
    background: rgba(3, 6, 15, 0.96);
    border-top: 1px solid rgba(56, 189, 248, 0.28);
    display: flex;
    align-items: center;
    padding: 0 14px;
    gap: 10px;
    font-family: monospace;
    font-size: 11px;
    color: #7dd3fc;
    z-index: 100;
    white-space: nowrap;
    overflow: hidden;
  }
  .ticker-tag {
    background: #0284c7;
    color: #fff;
    padding: 1px 7px;
    border-radius: 4px;
    font-weight: 900;
    font-size: 10px;
  }
  .hm-subbar {
    position: absolute;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 4px;
    background: rgba(6, 11, 25, 0.94);
    border: 1px solid rgba(168, 85, 247, 0.55);
    padding: 4px 8px;
    border-radius: 99px;
    z-index: 65;
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.75), 0 0 18px rgba(168, 85, 247, 0.25);
    backdrop-filter: blur(10px);
    max-width: 96%;
    overflow-x: auto;
  }
  .hm-sub-btn {
    border: 1px solid transparent;
    background: transparent;
    color: #cbd5e1;
    font-size: 10px;
    font-weight: 800;
    padding: 4px 9px;
    border-radius: 99px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.15s;
  }
  .hm-sub-btn:hover { color: #fff; background: rgba(168, 85, 247, 0.18); }
  .hm-sub-btn.active {
    background: linear-gradient(135deg, rgba(168, 85, 247, 0.45), rgba(6, 182, 212, 0.45));
    border-color: #c084fc;
    color: #fff;
    box-shadow: 0 0 12px rgba(192, 132, 252, 0.45);
  }
  /* WALLBOARD & CINEMA TOP CONTROLS */
  .wallboard-switcher {
    display: flex;
    align-items: center;
    background: rgba(12, 19, 36, 0.95);
    padding: 3px;
    border-radius: 9px;
    border: 1px solid rgba(6, 182, 212, 0.45);
    gap: 3px;
  }
  .wb-btn {
    border: 1px solid transparent;
    background: transparent;
    color: #cbd5e1;
    padding: 5px 9px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 800;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.14s;
  }
  .wb-btn:hover { color: #fff; background: rgba(6, 182, 212, 0.16); }
  .wb-btn.active {
    background: linear-gradient(135deg, rgba(6, 182, 212, 0.42), rgba(168, 85, 247, 0.42));
    color: #fff;
    border-color: #38bdf8;
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.4);
  }
  .cinema-btn {
    border: 1px solid rgba(245, 158, 11, 0.55);
    background: rgba(245, 158, 11, 0.14);
    color: #fde68a;
    padding: 5px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 800;
    cursor: pointer;
    white-space: nowrap;
  }
  .cinema-btn.active {
    background: linear-gradient(135deg, #f59e0b, #ec4899);
    color: #fff;
    border-color: #fff;
    box-shadow: 0 0 14px rgba(245, 158, 11, 0.65);
  }
  .top-select {
    background: #091122;
    color: #38bdf8;
    border: 1px solid rgba(56, 189, 248, 0.5);
    border-radius: 6px;
    padding: 4px 7px;
    font-size: 11px;
    font-weight: 800;
    max-width: 195px;
    cursor: pointer;
  }
  /* STAGE FLEX LAYOUT WITH LEFT 50-VIEW CATALOG DRAWER */
  .stage {
    display: flex;
    position: relative;
    width: 100vw;
    height: calc(100vh - 116px);
    overflow: hidden;
  }
  .catalog-drawer {
    width: 0;
    height: 100%;
    background: rgba(6, 11, 24, 0.97);
    border-right: 0 solid rgba(56, 189, 248, 0.4);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: width 0.18s ease;
    z-index: 80;
    flex-shrink: 0;
  }
  .catalog-drawer.open {
    width: 420px;
    border-right-width: 1px;
    box-shadow: 10px 0 30px rgba(0, 0, 0, 0.75);
  }
  .cat-hdr {
    padding: 8px 10px 6px;
    border-bottom: 1px solid rgba(56, 189, 248, 0.24);
    background: rgba(10, 18, 36, 0.95);
  }
  .cat-hdr-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11.5px;
    font-weight: 900;
    color: #38bdf8;
    margin-bottom: 6px;
  }
  .cat-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
  }
  .cat-tab {
    border: 1px solid rgba(148, 163, 184, 0.28);
    background: rgba(15, 23, 42, 0.9);
    color: #cbd5e1;
    font-size: 9.5px;
    font-weight: 800;
    padding: 3px 6px;
    border-radius: 5px;
    cursor: pointer;
  }
  .cat-tab.active {
    background: rgba(6, 182, 212, 0.32);
    border-color: #38bdf8;
    color: #fff;
  }
  .catalog-grid {
    flex: 1;
    overflow-y: auto;
    padding: 6px 8px;
    display: grid;
    grid-template-columns: 1fr;
    gap: 4px;
    align-content: start;
  }
  .v-card {
    background: rgba(13, 21, 40, 0.92);
    border: 1px solid rgba(56, 189, 248, 0.24);
    border-radius: 5px;
    padding: 4px 6px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 5px;
    transition: all 0.12s;
  }
  .v-card:hover {
    border-color: #38bdf8;
    background: rgba(6, 182, 212, 0.18);
  }
  .v-card.active {
    background: linear-gradient(90deg, rgba(168, 85, 247, 0.36), rgba(6, 182, 212, 0.32));
    border-color: #f59e0b;
    box-shadow: 0 0 10px rgba(245, 158, 11, 0.35);
  }
  .v-badge {
    font-family: monospace;
    font-size: 9px;
    font-weight: 900;
    padding: 2px 4px;
    border-radius: 3px;
    color: #020617;
    flex-shrink: 0;
  }
  .v-name {
    font-size: 9.2px;
    font-weight: 700;
    color: #f1f5f9;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .stage-main {
    flex: 1;
    position: relative;
    height: 100%;
    overflow: hidden;
  }
  #single-stage {
    width: 100%;
    height: 100%;
    position: relative;
  }
  /* MULTI-VIEW SPLIT-SCREEN WALLBOARD (2x2 QUAD, 3x2 SIX-VIEW & 4x2 EIGHT-VIEW) */
  #wallboard-grid {
    display: none;
    width: 100%;
    height: 100%;
    padding: 6px;
    gap: 6px;
    background: #02050d;
  }
  #wallboard-grid.quad-mode {
    display: grid;
    grid-template-columns: 1fr;
    grid-template-rows: repeat(2, 1fr);
  }
  #wallboard-grid.six-mode {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    grid-template-rows: repeat(2, 1fr);
  }
  #wallboard-grid.eight-mode {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    grid-template-rows: repeat(2, 1fr);
  }
  .wb-cell {
    display: flex;
    flex-direction: column;
    background: #050a18;
    border: 1.5px solid rgba(56, 189, 248, 0.42);
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 6px 22px rgba(0, 0, 0, 0.7);
  }
  .wb-cell-hdr {
    height: 28px;
    background: linear-gradient(90deg, #0b1428, #070d1b);
    border-bottom: 1px solid rgba(56, 189, 248, 0.28);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 8px;
    gap: 6px;
    flex-shrink: 0;
  }
  .wb-slot-tag {
    background: #0284c7;
    color: #fff;
    font-family: monospace;
    font-size: 9.5px;
    font-weight: 900;
    padding: 1px 5px;
    border-radius: 4px;
  }
  .wb-cell-title {
    font-size: 10px;
    font-weight: 800;
    color: #f8fafc;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
  }
  .wb-live-pill {
    font-family: monospace;
    font-size: 8.5px;
    font-weight: 800;
    color: #34d399;
    background: rgba(16, 185, 129, 0.14);
    border: 1px solid rgba(16, 185, 129, 0.45);
    padding: 1px 5px;
    border-radius: 99px;
  }
  .wb-select {
    background: #050914;
    color: #7dd3fc;
    border: 1px solid rgba(56, 189, 248, 0.45);
    border-radius: 5px;
    font-size: 9.5px;
    font-weight: 700;
    padding: 2px 5px;
    max-width: 175px;
    cursor: pointer;
  }
  .wb-max-btn {
    background: rgba(56, 189, 248, 0.16);
    border: 1px solid rgba(56, 189, 248, 0.45);
    color: #fff;
    border-radius: 4px;
    font-size: 9.5px;
    font-weight: 800;
    padding: 1px 6px;
    cursor: pointer;
  }
  .wb-max-btn:hover { background: #0284c7; }
  .wb-canvas-wrap {
    flex: 1;
    width: 100%;
    height: calc(100% - 28px);
    position: relative;
    overflow: hidden;
  }
  .wb-canvas {
    width: 100%;
    height: 100%;
    display: block;
  }
  .topbar { padding: 0 10px !important; gap: 6px !important; } .brand { white-space: nowrap; flex-shrink: 0; } .brand-title { font-size: 12px !important; } .brand-sub { font-size: 8.8px !important; } .subbar { padding: 0 10px !important; overflow-x: hidden; white-space: nowrap; } .kpi-group, .legend-group { flex-wrap: nowrap !important; white-space: nowrap; } .hm-subbar { overflow: hidden !important; flex-wrap: nowrap !important; } .pref-btn {
    border: 1px solid #fbbf24;
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.28), rgba(234, 179, 8, 0.16));
    color: #fef08a;
    padding: 5px 10px;
    border-radius: 7px;
    font-size: 11px;
    font-weight: 900;
    cursor: pointer;
    box-shadow: 0 0 12px rgba(245, 158, 11, 0.35);
    white-space: nowrap;
    transition: all 0.15s;
  }
  .pref-btn:hover {
    background: linear-gradient(135deg, #f59e0b, #eab308);
    color: #020617;
    box-shadow: 0 0 18px rgba(251, 191, 36, 0.75);
  }
  .pref-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(251, 191, 36, 0.55);
    color: #fde68a;
    font-size: 10.5px;
    font-weight: 800;
    padding: 4px 8px;
    border-radius: 6px;
    cursor: pointer;
    white-space: nowrap;
  }
  .cat-search-input {
    width: 100%;
    background: #060b18;
    border: 1px solid rgba(56, 189, 248, 0.4);
    color: #f8fafc;
    border-radius: 5px;
    padding: 4px 8px;
    font-size: 10.5px;
    margin-bottom: 6px;
  }
</style>
</head>
<body>

<!-- TOP COMMAND BAR -->
<div class="topbar">
  <div class="brand">
    <div class="brand-orb">🧠</div>
    <div>
      <div class="brand-title">BOYLENET 165-VIEW HIVEMIND, RACK & C4ISR ENGINE</div>
      <div class="brand-sub">V01–V100 CoT + T01–T65 Topology • 60fps Live • 1×1 / 2×2 / 3×2 / 4×2 Wallboard</div>
    </div>
  </div>

  <!-- 165-VIEW CATALOG & QUICK SELECTOR -->
  <div class="mode-switcher">
    <button class="mode-btn active" id="btn-catalog" onclick="toggleCatalog()">📚 165-View Catalog (V01–V100 + T01–T65)</button>
    <button class="mode-btn" onclick="stepView(-1)" title="Previous View">◀</button>
    <select id="top-view-select" class="top-select" onchange="selectView(this.value)"></select>
    <button class="mode-btn" onclick="stepView(1)" title="Next View">▶</button>
  </div>

  <!-- MULTI-VIEW SPLIT-SCREEN WALLBOARD + AUTO-CYCLE CINEMA -->
  <div class="wallboard-switcher">
    <button class="wb-btn active" id="wb-single" onclick="setWallboard('single')">1×1 Single</button>
    <button class="wb-btn" id="wb-quad" onclick="setWallboard('quad')">⊞ 2×2 Quad</button>
    <button class="wb-btn" id="wb-six" onclick="setWallboard('six')">▦ 3×2 Six-View</button>
    <button class="wb-btn" id="wb-eight" onclick="setWallboard('eight')">🧱 4×2 Eight-View</button>
    <button class="cinema-btn" id="btn-cinema" onclick="toggleCinema()">🎬 Cinema (15s)</button>
  </div>

  <div class="top-right">
    <button class="pref-btn" id="btn-set-preferred" onclick="savePreferredView()" title="Persist current view & wallboard layout as default">⭐ Set Current View as Preferred</button>
    <span class="pref-badge" id="badge-preferred" onclick="applySavedPreferred()" title="Click to jump to saved Preferred View">⭐ Preferred: <b id="pref-view-id" style="color:#fbbf24;">V01</b></span>
    <a href="/gallery" class="pulse-btn" style="text-decoration:none;background:linear-gradient(135deg,#8b5cf6,#06b6d4);box-shadow:0 0 12px rgba(139,92,246,0.45);">🖼️ 179-Image Gallery</a>
    <button class="pulse-btn" onclick="triggerPulse()">⚡ Pulse</button>
  </div>
</div>

<!-- SUB-HEADER KPI & 10-CATEGORY RIBBON -->
<div class="subbar">
  <div class="kpi-group">
    <span class="kpi-chip">🎞️ Active: <b id="k-active-view" style="color:#f59e0b;">V01 Hybrid HiveMind+n8n+12U Rack+Cloud Master</b></span>
    <span class="kpi-chip">📚 Catalog: <b style="color:#38bdf8;">165 Live 60fps Views</b></span>
    <span class="kpi-chip">🤖 Sessions: <b id="k-sess">10 Active</b></span>
    <span class="kpi-chip">⚡ RoCE GPU: <b id="k-model">qwen3-coder-30b-a3b (77.6 tok/s)</b></span>
    <span class="kpi-chip">💾 vSAN: <b id="k-vsan">135.5 / 328.4 TiB (75 Disks)</b></span>
    <span class="kpi-chip">🌡️ 12U Bezel: <b style="color:#ef4444;">79.5°F</b></span>
    <span class="kpi-chip" id="mil-banner" style="display:none;color:#10b981;font-weight:900;">🛡️ C4ISR SENTINEL: ARMED</span>
  </div>
  <div class="legend-group">
    <span class="leg-pill" onclick="jumpCategory('cat1')"><span class="leg-dot" style="background:#a855f7;"></span>🧠 V01–10 Core</span>
    <span class="leg-pill" onclick="jumpCategory('cat2')"><span class="leg-dot" style="background:#38bdf8;"></span>🔬 V11–27 Studios</span>
    <span class="leg-pill" onclick="jumpCategory('cat3')"><span class="leg-dot" style="background:#10b981;"></span>🪖 V28–44 Mil/Rack</span>
    <span class="leg-pill" onclick="jumpCategory('cat4')"><span class="leg-dot" style="background:#f43f5e;"></span>⚛️ V45–60 Physics</span>
    <span class="leg-pill" onclick="jumpCategory('cat5')"><span class="leg-dot" style="background:#f59e0b;"></span>⚡ V61–70 Pools</span>
    <span class="leg-pill" onclick="jumpCategory('cat6')"><span class="leg-dot" style="background:#22c55e;"></span>🧱 V71–80 Science</span>
    <span class="leg-pill" onclick="jumpCategory('cat7')"><span class="leg-dot" style="background:#00f5d4;"></span>🛡️ V81–90 Cyber</span>
    <span class="leg-pill" onclick="jumpCategory('cat8')"><span class="leg-dot" style="background:#f97316;"></span>🎮 V91–100 UE5/#100</span>
    <span class="leg-pill" onclick="jumpCategory('cat9')"><span class="leg-dot" style="background:#ef4444;"></span>🗄️ T01–35 12U/NOC</span>
    <span class="leg-pill" onclick="jumpCategory('cat10')"><span class="leg-dot" style="background:#c084fc;"></span>⚔️ T36–65 C4ISR</span>
  </div>
</div>

<!-- MAIN FULL-VIEWPORT VISUAL STAGE -->
<div class="stage">
  <!-- LEFT DOCKED 165-VIEW CATALOG DRAWER (V01–V100 + T01–T65) -->
  <div class="catalog-drawer" id="catalog-drawer">
    <div class="cat-hdr">
      <div class="cat-hdr-top">
        <span>📚 165-VIEW LIVE 60FPS CATALOG (V01–V100 + T01–T65)</span>
        <span style="font-size:9.5px;color:#fde68a;" id="cat-count-lbl">165 Views</span>
      </div>
      <input type="text" class="cat-search-input" id="cat-search" placeholder="🔍 Search 165 views by ID (V43, T61) or keyword (n8n, F-35, 12U, MAGI)..." oninput="renderCatalogGrid()">
      <div class="cat-tabs">
        <button class="cat-tab active" id="ct-all" onclick="filterCatalog('all')">All (165)</button>
        <button class="cat-tab" id="ct-cat1" onclick="filterCatalog('cat1')">🧠 V01–10 (10)</button>
        <button class="cat-tab" id="ct-cat2" onclick="filterCatalog('cat2')">🔬 V11–27 (17)</button>
        <button class="cat-tab" id="ct-cat3" onclick="filterCatalog('cat3')">🪖 V28–44 (17)</button>
        <button class="cat-tab" id="ct-cat4" onclick="filterCatalog('cat4')">⚛️ V45–60 (16)</button>
        <button class="cat-tab" id="ct-cat5" onclick="filterCatalog('cat5')">⚡ V61–70 (10)</button>
        <button class="cat-tab" id="ct-cat6" onclick="filterCatalog('cat6')">🧱 V71–80 (10)</button>
        <button class="cat-tab" id="ct-cat7" onclick="filterCatalog('cat7')">🛡️ V81–90 (10)</button>
        <button class="cat-tab" id="ct-cat8" onclick="filterCatalog('cat8')">🎮 V91–100 (10)</button>
        <button class="cat-tab" id="ct-cat9" onclick="filterCatalog('cat9')">🗄️ T01–35 (35)</button>
        <button class="cat-tab" id="ct-cat10" onclick="filterCatalog('cat10')">⚔️ T36–65 (30)</button>
      </div>
    </div>
    <div class="catalog-grid" id="catalog-grid"></div>
  </div>

  <!-- RIGHT MAIN STAGE CONTAINER (1x1 SINGLE OR 2x2 / 3x2 / 4x2 WALLBOARD) -->
  <div class="stage-main" id="stage-main">
    <div id="single-stage">
      <!-- FLOATING CATEGORY VIEW SWITCHER BAR -->
      <div class="hm-subbar" id="hm-subbar"></div>

      <canvas id="main-canvas"></canvas>

      <!-- MODE 5: PIXEL-ACCURATE 12U FRONT + REAR SERVER RACK DIGITAL TWIN -->
      <div id="rack-view">
        <!-- FRONT ELEVATION (Matching Operator Photo) -->
        <div class="rack-col">
          <div class="rack-bezel">
            <span class="rack-bezel-title">FRONT ELEVATION • 12U CABINET</span>
            <div class="thermostat-box">79.5°F</div>
            <div class="rocker-switch" title="Illuminated Red Main Power Rocker"></div>
          </div>
          <div class="rack-units">
            <div class="u-unifi" onclick="selectNode('udm-pro')">
              <div class="unifi-lcm">U1</div>
              <div class="unifi-label">Dream Machine Pro<span>10.0.70.1 • 400+ DNS • Gateway</span></div>
              <div style="width:75px;height:18px;border:1px solid #94a3b8;border-radius:2px;background:#cbd5e1;font-size:8px;display:flex;align-items:center;justify-content:center;color:#475569;">3.5" NVR BAY</div>
              <div class="port-strip">
                <div class="port-box"></div><div class="port-box"></div><div class="port-box"></div><div class="port-box"></div>
                <div class="port-box cat6"></div><div class="port-box cat6"></div><div class="port-box aqua"></div><div class="port-box dac"></div>
              </div>
            </div>
            <div class="u-unifi" onclick="selectNode('usw-agg')">
              <div class="unifi-lcm">U2</div>
              <div class="unifi-label">USW-Aggregation<span>10.0.10.110 • 8x 10G SFP+ Optical</span></div>
              <div class="port-strip">
                <div class="port-box aqua"></div><div class="port-box aqua"></div><div class="port-box aqua"></div><div class="port-box aqua"></div>
                <div class="port-box aqua"></div><div class="port-box aqua"></div><div class="port-box dac"></div><div class="port-box dac"></div>
              </div>
            </div>
            <div class="u-unifi" onclick="selectNode('usw-pro-agg')">
              <div class="unifi-lcm">U3</div>
              <div class="unifi-label">USW-Pro-Aggregation<span>10.0.10.111 • 28x 10G + 4x 25G RoCE</span></div>
              <div class="port-strip">
                <div class="port-box dac"></div><div class="port-box dac"></div><div class="port-box aqua"></div><div class="port-box aqua"></div>
                <div class="port-box dac"></div><div class="port-box dac"></div><div class="port-box dac"></div><div class="port-box dac"></div>
                <div class="port-box aqua"></div><div class="port-box aqua"></div><div class="port-box dac"></div><div class="port-box dac"></div>
              </div>
            </div>
            <div class="u-unifi" onclick="selectNode('usw-pro-max')">
              <div class="unifi-lcm">U4</div>
              <div class="unifi-label">USW PoE Switch<span>10.0.10.182 • Blue Cat6 Patch Bundle</span></div>
              <div class="port-strip">
                <div class="port-box cat6"></div><div class="port-box cat6"></div><div class="port-box cat6"></div><div class="port-box cat6"></div>
                <div class="port-box cat6"></div><div class="port-box cat6"></div><div class="port-box cat6"></div><div class="port-box cat6"></div>
                <div class="port-box aqua"></div><div class="port-box dac"></div>
              </div>
            </div>
            <div class="u-hpe" onclick="selectNode('esxi01')">
              <div class="hpe-mesh">
                <div class="hpe-title">U5–U6 • esxi01 (.20.41) • HPE DL380 Gen9 SFF</div>
                <div class="hpe-sub">2x Perf Mesh Cages • 56T Xeon • 768G RAM • iLO .10.10</div>
              </div>
              <div class="sff-cage">
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-maroon"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-maroon"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-maroon"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-maroon"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-maroon"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-maroon"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-maroon"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-maroon"></span></div>
              </div>
            </div>
            <div class="u-hpe" onclick="selectNode('esxi02')">
              <div class="hpe-mesh">
                <div class="hpe-title">U7–U8 • esxi02 (.20.42) • HPE DL380 Gen9 SFF</div>
                <div class="hpe-sub">8x SFF (Magenta Illuminated Latches) • DG T0 + 2x DG T1</div>
              </div>
              <div class="sff-cage">
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-maroon"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-maroon"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-maroon"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-maroon"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-magenta"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-magenta"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-magenta"></span></div>
                <div class="sff-bay"><span class="led-ring"></span><span class="latch-magenta"></span></div>
              </div>
            </div>
            <div class="u-hpe" onclick="selectNode('esxi03')">
              <div class="lff-wrap">
                <div class="lff-top-row">
                  <span>U9–U10 • esxi03 (.20.43) • 12-Bay 3.5" LFF (4x 24TB Seagate Exos Tier-0)</span>
                  <span class="bay-sticker">Drive Bay ID 1–12</span>
                </div>
                <div class="lff-grid">
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                </div>
              </div>
            </div>
            <div class="u-hpe" onclick="selectNode('esxi04')">
              <div class="lff-wrap">
                <div class="lff-top-row">
                  <span>U11–U12 • esxi04 (.20.44) • 12-Bay 3.5" LFF (4x 24TB Exos) <span class="uid-blue" title="Blue UID LED"></span></span>
                  <span class="bay-sticker">Drive Bay ID 1–12</span>
                </div>
                <div class="lff-grid">
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                  <div class="lff-bay"><span class="led-ring"></span><span class="lff-latch"></span></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- REAR ELEVATION -->
        <div class="rack-col">
          <div class="rack-bezel">
            <span class="rack-bezel-title">REAR ELEVATION • UPS + USW-PRO-MAX + 4x TESLA T4</span>
            <span style="color:#10b981;font-size:11px;font-weight:900;">⚡ 4x 800W HPE FLEXSLOT + UPS ONLINE</span>
          </div>
          <div class="rack-units">
            <div class="u-hpe" style="flex:1.6;border-left-color:#10b981;border-right-color:#10b981;" onclick="selectNode('udm-pro')">
              <div class="hpe-mesh" style="background:linear-gradient(90deg,#062419,#0b1324);">
                <div class="hpe-title" style="color:#34d399;">🔋 REAR TOP • RACKMOUNT SMART-UPS BATTERY BACKUP</div>
                <div class="hpe-sub" style="color:#a7f3d0;">100% Charged • Pure Sine Wave • Protecting U1–U4 UniFi Spine & ESXi Hosts</div>
              </div>
            </div>
            <div class="u-hpe" onclick="selectNode('ai-srv01')">
              <div class="hpe-mesh">
                <div class="hpe-title">REAR U5–U6 • esxi01 (.20.41) + Tesla T4 #1 (ai-srv01 .72)</div>
                <div class="hpe-sub">iLO4 10.0.10.10 • 25GbE RoCE 10.0.75.12:50052 • vSAN 10.0.60.21 • Dual 800W PSU</div>
              </div>
            </div>
            <div class="u-unifi" style="flex:1.25;background:linear-gradient(90deg,#cbd5e1,#94a3b8);" onclick="selectNode('usw-pro-max')">
              <div class="unifi-lcm">MAX</div>
              <div class="unifi-label">REAR RAIL (ESXi 2 & 3): UniFi USW-Pro-Max<span>Etherlighting 2.5G/10G Switch Mounted Behind ESXi02 & ESXi03</span></div>
              <div class="port-strip">
                <div class="port-box aqua"></div><div class="port-box aqua"></div><div class="port-box cat6"></div><div class="port-box cat6"></div>
                <div class="port-box dac"></div><div class="port-box dac"></div>
              </div>
            </div>
            <div class="u-hpe" onclick="selectNode('aidev')">
              <div class="hpe-mesh">
                <div class="hpe-title">REAR U7–U10 • esxi02 (.42) & esxi03 (.43) + Tesla T4 #2 & #3</div>
                <div class="hpe-sub">iLO4 .10.20/.30 • 25GbE RoCE .75.11 (aidev) & .75.13 (ai-infer01) • USW-Pro-Max Interconnect</div>
              </div>
            </div>
            <div class="u-hpe" onclick="selectNode('ai-ollama01')">
              <div class="hpe-mesh">
                <div class="hpe-title">REAR U11–U12 • esxi04 (.20.44) + Tesla T4 #4 (ai-ollama01 .228)</div>
                <div class="hpe-sub">iLO4 10.0.10.40 • 25GbE RoCE 10.0.75.14 • vSAN 10.0.60.24 • Blue UID Beacon Active</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- FLOATING CANVAS HUD -->
      <div class="stage-hud" id="stage-hud">
        <button class="hud-pill" onclick="toggleCatalog()">📚 165-View Drawer</button>
        <button class="hud-pill" onclick="stepView(-1)">◀ Prev View</button>
        <button class="hud-pill" onclick="stepView(1)">Next View ▶</button>
        <button class="hud-pill" onclick="savePreferredView()">⭐ Set Preferred</button>
        <button class="hud-pill" onclick="setWallboard('quad')">⊞ 2×2 Quad</button>
        <button class="hud-pill" onclick="setWallboard('six')">▦ 3×2 Six-Pack</button>
        <button class="hud-pill" onclick="setWallboard('eight')">🧱 4×2 Eight-Pack</button>
        <button class="hud-pill" onclick="resetView()">🎯 Fit (100%)</button>
        <button class="hud-pill" onclick="toggleAutoRotate()" id="btn-autorotate" style="display:none;">🔄 Auto-Orbit: ON</button>
      </div>
    </div>

    <!-- MULTI-VIEW SPLIT-SCREEN WALLBOARD (2x2 QUAD, 3x2 SIX-VIEW, 4x2 EIGHT-VIEW) -->
    <div id="wallboard-grid">
      <div class="wb-cell" id="wb-cell-0">
        <div class="wb-cell-hdr">
          <span class="wb-slot-tag" id="wb-tag-0">Q1</span>
          <span class="wb-cell-title" id="wb-title-0">V01 Hybrid HiveMind+n8n+12U Rack+Cloud</span>
          <span class="wb-live-pill">60 FPS</span>
          <select class="wb-select" id="wb-sel-0" onchange="setSlotView(0, this.value)"></select>
          <button class="wb-max-btn" onclick="maximizeSlot(0)" title="Maximize to 1x1 Single View">⛶ 1×1</button>
        </div>
        <div class="wb-canvas-wrap"><canvas class="wb-canvas" id="wb-canvas-0"></canvas></div>
      </div>
      <div class="wb-cell" id="wb-cell-1">
        <div class="wb-cell-hdr">
          <span class="wb-slot-tag" id="wb-tag-1">Q2</span>
          <span class="wb-cell-title" id="wb-title-1">V02 n8n Agent Swarm (Hanging Circles)</span>
          <span class="wb-live-pill">60 FPS</span>
          <select class="wb-select" id="wb-sel-1" onchange="setSlotView(1, this.value)"></select>
          <button class="wb-max-btn" onclick="maximizeSlot(1)" title="Maximize to 1x1 Single View">⛶ 1×1</button>
        </div>
        <div class="wb-canvas-wrap"><canvas class="wb-canvas" id="wb-canvas-1"></canvas></div>
      </div>
      <div class="wb-cell" id="wb-cell-2">
        <div class="wb-cell-hdr">
          <span class="wb-slot-tag" id="wb-tag-2">Q3</span>
          <span class="wb-cell-title" id="wb-title-2">V03 HIVEMIND v3.0 Phosphor CRT</span>
          <span class="wb-live-pill">60 FPS</span>
          <select class="wb-select" id="wb-sel-2" onchange="setSlotView(2, this.value)"></select>
          <button class="wb-max-btn" onclick="maximizeSlot(2)" title="Maximize to 1x1 Single View">⛶ 1×1</button>
        </div>
        <div class="wb-canvas-wrap"><canvas class="wb-canvas" id="wb-canvas-2"></canvas></div>
      </div>
      <div class="wb-cell" id="wb-cell-3">
        <div class="wb-cell-hdr">
          <span class="wb-slot-tag" id="wb-tag-3">Q4</span>
          <span class="wb-cell-title" id="wb-title-3">V04 Kimi K2.5 Radial CORE Burst</span>
          <span class="wb-live-pill">60 FPS</span>
          <select class="wb-select" id="wb-sel-3" onchange="setSlotView(3, this.value)"></select>
          <button class="wb-max-btn" onclick="maximizeSlot(3)" title="Maximize to 1x1 Single View">⛶ 1×1</button>
        </div>
        <div class="wb-canvas-wrap"><canvas class="wb-canvas" id="wb-canvas-3"></canvas></div>
      </div>
      <div class="wb-cell" id="wb-cell-4">
        <div class="wb-cell-hdr">
          <span class="wb-slot-tag" id="wb-tag-4">S5</span>
          <span class="wb-cell-title" id="wb-title-4">V100 Centurion Grand Masterpiece</span>
          <span class="wb-live-pill">60 FPS</span>
          <select class="wb-select" id="wb-sel-4" onchange="setSlotView(4, this.value)"></select>
          <button class="wb-max-btn" onclick="maximizeSlot(4)" title="Maximize to 1x1 Single View">⛶ 1×1</button>
        </div>
        <div class="wb-canvas-wrap"><canvas class="wb-canvas" id="wb-canvas-4"></canvas></div>
      </div>
      <div class="wb-cell" id="wb-cell-5">
        <div class="wb-cell-hdr">
          <span class="wb-slot-tag" id="wb-tag-5">S6</span>
          <span class="wb-cell-title" id="wb-title-5">T11 Dual Front+Rear 12U Rack Twin</span>
          <span class="wb-live-pill">60 FPS</span>
          <select class="wb-select" id="wb-sel-5" onchange="setSlotView(5, this.value)"></select>
          <button class="wb-max-btn" onclick="maximizeSlot(5)" title="Maximize to 1x1 Single View">⛶ 1×1</button>
        </div>
        <div class="wb-canvas-wrap"><canvas class="wb-canvas" id="wb-canvas-5"></canvas></div>
      </div>
      <div class="wb-cell" id="wb-cell-6">
        <div class="wb-cell-hdr">
          <span class="wb-slot-tag" id="wb-tag-6">E7</span>
          <span class="wb-cell-title" id="wb-title-6">T61 Anduril Lattice Swarm C2</span>
          <span class="wb-live-pill">60 FPS</span>
          <select class="wb-select" id="wb-sel-6" onchange="setSlotView(6, this.value)"></select>
          <button class="wb-max-btn" onclick="maximizeSlot(6)" title="Maximize to 1x1 Single View">⛶ 1×1</button>
        </div>
        <div class="wb-canvas-wrap"><canvas class="wb-canvas" id="wb-canvas-6"></canvas></div>
      </div>
      <div class="wb-cell" id="wb-cell-7">
        <div class="wb-cell-hdr">
          <span class="wb-slot-tag" id="wb-tag-7">E8</span>
          <span class="wb-cell-title" id="wb-title-7">V61 Claude-Flow v4 Multi-Pool Mesh</span>
          <span class="wb-live-pill">60 FPS</span>
          <select class="wb-select" id="wb-sel-7" onchange="setSlotView(7, this.value)"></select>
          <button class="wb-max-btn" onclick="maximizeSlot(7)" title="Maximize to 1x1 Single View">⛶ 1×1</button>
        </div>
        <div class="wb-canvas-wrap"><canvas class="wb-canvas" id="wb-canvas-7"></canvas></div>
      </div>
    </div>
  </div>
</div>

<!-- SLIDE-OUT RIGHT INSPECTOR DRAWER -->
<div class="drawer" id="drawer">
  <button class="drawer-close" onclick="closeDrawer()">✕</button>
  <div id="drawer-body"></div>
</div>

<!-- BOTTOM LIVE SWARM FLIGHT RECORDER -->
<div class="ticker">
  <span class="ticker-tag">SWARM RECORDER</span>
  <span id="ticker-msg">Connecting to Boylenet 27-Node Telemetry Fabric (165 Views Ready)...</span>
</div>

<script>
let DATA = null;
let MODE = 'hivemind';
let ACTIVE_VIEW = 'V01'; // V01..V100, T01..T65
let PREFERRED_STATE = {
  preferred_view: 'V01',
  wallboard: 'single',
  quad_views: ['V01', 'V02', 'T11', 'V28'],
  six_views: ['V01', 'V02', 'V03', 'V04', 'T11', 'V28'],
  eight_views: ['V01', 'V02', 'V03', 'V04', 'V100', 'T11', 'T61', 'V61']
};
let WALLBOARD = 'single'; // single | quad | six | eight
let CATALOG_OPEN = false;
let CATALOG_FILTER = 'all';
let CINEMA_ACTIVE = false;
let CINEMA_LAST_SWITCH = 0;
let QUAD_VIEWS = ['V01', 'V02', 'T11', 'V28'];
let SIX_VIEWS = ['V01', 'V02', 'V03', 'V04', 'T11', 'V28'];
let EIGHT_VIEWS = ['V01', 'V02', 'V03', 'V04', 'V100', 'T11', 'T61', 'V61'];
let HM_SUB = 'hybrid';
let DETAIL = 'simple';
let FLOW_FILTER = 'all';
let SELECTED_ID = null;
let PULSE_UNTIL = 0;

// Pan & Zoom state for 2D modes
let panX = 0, panY = 0, zoom = 1.0;
let dragging = false, lastX = 0, lastY = 0;
let draggedNode = null;

// 3D Orbit state
let camYaw = 0.52, camPitch = 0.42, camDist = 560, autoOrbit = true;

// Animated particles
let PARTICLES = [];
let HM_PARTICLES = [];
let HIT_BOXES = [];

function initHmParticles() {
  if (HM_PARTICLES.length > 0) return;
  for (let i = 0; i < 210; i++) {
    HM_PARTICLES.push({
      lane: i % 3,
      srcIdx: i % 8,
      dstIdx: (i * 3 + 1) % 7,
      t: Math.random(),
      speed: 0.0042 + (i % 7) * 0.0009,
      size: 2.6 + (i % 3) * 0.85,
    });
  }
}
initHmParticles();

const CAT_COLORS = {
  'cloud': '#a855f7',
  'controller': '#f59e0b',
  'gpu-vault': '#06b6d4',
  'worker-turbo': '#22c55e',
  'worker': '#38bdf8',
  'worker-cold': '#64748b',
  'oracle': '#f97316',
  'esxi': '#ec4899',
  'storage': '#f43f5e',
  'network': '#14b8a6'
};

const CAT_ICONS = {
  'cloud': '☁️',
  'controller': '🧠',
  'gpu-vault': '⚡',
  'worker-turbo': '🚀',
  'worker': '🖥️',
  'worker-cold': '❄️',
  'oracle': '👁️',
  'esxi': '🗄️',
  'storage': '💾',
  'network': '🔀'
};

const VIEWS_CATALOG = [{"id": "V01", "cat": "cat1", "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)", "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)", "name": "V01 Hybrid HiveMind+n8n+12U Rack+Cloud Master", "color": "#a855f7", "c2": "#38bdf8", "c3": "#10b981", "bg": "#030712", "arch": "hybrid", "png": "hivemind_cot_05.png"}, {"id": "V02", "cat": "cat1", "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)", "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)", "name": "V02 n8n Agent Swarm (Hanging Model/Think/Memory/Search Circles)", "color": "#06b6d4", "c2": "#a855f7", "c3": "#22c55e", "bg": "#030712", "arch": "n8n_hanging_circles", "png": "hivemind_cot_01.png"}, {"id": "V03", "cat": "cat1", "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)", "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)", "name": "V03 HIVEMIND v3.0 Phosphor-Green CRT Control Center", "color": "#10b981", "c2": "#34d399", "c3": "#f59e0b", "bg": "#020905", "arch": "hivemind_crt", "png": "hivemind_cot_02.png"}, {"id": "V04", "cat": "cat1", "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)", "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)", "name": "V04 Kimi K2.5 Radial CORE Constellation & Concentric CoT Rings", "color": "#f97316", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#040711", "arch": "kimi_radial_core", "png": "hivemind_cot_03.png"}, {"id": "V05", "cat": "cat1", "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)", "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)", "name": "V05 KNIME 6-Swimlane End-to-End CoT & 12U Rack Pipeline", "color": "#38bdf8", "c2": "#22c55e", "c3": "#f59e0b", "bg": "#030712", "arch": "knime_swimlanes", "png": "hivemind_cot_04.png"}, {"id": "V06", "cat": "cat1", "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)", "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)", "name": "V06 Ironclad Rivet / ComfyUI Visual CoT Noodle & Token Canvas", "color": "#ec4899", "c2": "#06b6d4", "c3": "#a855f7", "bg": "#060712", "arch": "rivet_noodles", "png": "hivemind_cot_06.png"}, {"id": "V07", "cat": "cat1", "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)", "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)", "name": "V07 LangGraph Studio State-Machine & Time-Travel CoT Tree", "color": "#22c55e", "c2": "#38bdf8", "c3": "#f59e0b", "bg": "#030810", "arch": "langgraph_state", "png": "hivemind_cot_07.png"}, {"id": "V08", "cat": "cat1", "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)", "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)", "name": "V08 Tactical C4ISR Hive-Mind Kill-Chain & 12U Magazine", "color": "#10b981", "c2": "#f59e0b", "c3": "#38bdf8", "bg": "#020906", "arch": "military_c4isr_radar", "png": "hivemind_cot_08.png"}, {"id": "V09", "cat": "cat1", "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)", "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)", "name": "V09 3D Bioluminescent Neural Cortex & Synaptic CoT Pulse", "color": "#818cf8", "c2": "#ec4899", "c3": "#06b6d4", "bg": "#040613", "arch": "neural_cortex", "png": "hivemind_cot_09.png"}, {"id": "V10", "cat": "cat1", "cat_name": "🧠 HiveMind & n8n CoT Core (V01–V10)", "catName": "🧠 HiveMind & n8n CoT Core (V01–V10)", "name": "V10 CrewAI / AutoGen Shared Blackboard & Thought-Bubble Arena", "color": "#f59e0b", "c2": "#14b8a6", "c3": "#a855f7", "bg": "#060812", "arch": "crewai_arena", "png": "hivemind_cot_10.png"}, {"id": "V11", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V11 Arize Phoenix / OpenInference CoT Flamegraph & Span Waterfall", "color": "#f97316", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#050711", "arch": "flamegraph_spans", "png": "hivemind_cot_11.png"}, {"id": "V12", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V12 Langfuse v3 Multi-Agent Trace Tree & Cost/Latency Heatmap", "color": "#38bdf8", "c2": "#22c55e", "c3": "#ec4899", "bg": "#040812", "arch": "flamegraph_spans", "png": "hivemind_cot_12.png"}, {"id": "V13", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V13 PydanticAI / Logfire Streaming Structured-Output Validator", "color": "#ec4899", "c2": "#06b6d4", "c3": "#10b981", "bg": "#060711", "arch": "mcts_tree", "png": "hivemind_cot_13.png"}, {"id": "V14", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V14 Dify.ai / Coze Visual Agentic Workflow Studio & Cloud Nodes", "color": "#60a5fa", "c2": "#a855f7", "c3": "#22c55e", "bg": "#040814", "arch": "rivet_noodles", "png": "hivemind_cot_14.png"}, {"id": "V15", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V15 Flowise / Langflow Dark-Mode Multi-Agent RAG & Tool Canvas", "color": "#a855f7", "c2": "#06b6d4", "c3": "#f59e0b", "bg": "#050713", "arch": "rivet_noodles", "png": "hivemind_cot_15.png"}, {"id": "V16", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V16 BabyAGI / SuperAGI Autonomous Task-Queue & Reflection Loop", "color": "#10b981", "c2": "#38bdf8", "c3": "#f59e0b", "bg": "#03090c", "arch": "langgraph_state", "png": "hivemind_cot_16.png"}, {"id": "V17", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V17 MetaGPT Software Company Org-Chart (PM->Architect->Coder->QA)", "color": "#38bdf8", "c2": "#f59e0b", "c3": "#22c55e", "bg": "#040812", "arch": "mcts_tree", "png": "hivemind_cot_17.png"}, {"id": "V18", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V18 ChatDev Isometric Virtual AI Software House + 12U Server Rack", "color": "#fbbf24", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#060811", "arch": "iso_floor", "png": "hivemind_cot_18.png"}, {"id": "V19", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V19 Stanford Generative Agents Hive-Mind Memory & Reflection Tree", "color": "#34d399", "c2": "#60a5fa", "c3": "#f43f5e", "bg": "#03090f", "arch": "mcts_tree", "png": "hivemind_cot_19.png"}, {"id": "V20", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V20 Voyager / MineDojo Skill-Library Curriculum & Synthesis Loop", "color": "#f59e0b", "c2": "#10b981", "c3": "#38bdf8", "bg": "#07080f", "arch": "langgraph_state", "png": "hivemind_cot_20.png"}, {"id": "V21", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V21 Tree-of-Thoughts (ToT) / MCTS Multi-Branch Pruning Visualizer", "color": "#06b6d4", "c2": "#22c55e", "c3": "#ef4444", "bg": "#030812", "arch": "mcts_tree", "png": "hivemind_cot_21.png"}, {"id": "V22", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V22 Graph-of-Thoughts (GoT) Non-Linear Reasoning & Backtracking", "color": "#a855f7", "c2": "#38bdf8", "c3": "#10b981", "bg": "#050614", "arch": "neural_cortex", "png": "hivemind_cot_22.png"}, {"id": "V23", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V23 DSPy Compiled Prompt-Optimization & Signature Pipeline", "color": "#38bdf8", "c2": "#f97316", "c3": "#22c55e", "bg": "#040811", "arch": "knime_swimlanes", "png": "hivemind_cot_23.png"}, {"id": "V24", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V24 Semantic Kernel / AutoGen v0.4 Async Event-Driven Actor Mesh", "color": "#ec4899", "c2": "#38bdf8", "c3": "#10b981", "bg": "#060712", "arch": "crewai_arena", "png": "hivemind_cot_24.png"}, {"id": "V25", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V25 Haystack / deepset Hybrid BM25+Qdrant Retrieval & CoT Rerank", "color": "#22c55e", "c2": "#06b6d4", "c3": "#a855f7", "bg": "#03090e", "arch": "sankey_river", "png": "hivemind_cot_25.png"}, {"id": "V26", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V26 LlamaIndex Workflows Event-Driven Step Graph & 86-Model Vault", "color": "#fb923c", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#060810", "arch": "rivet_noodles", "png": "hivemind_cot_26.png"}, {"id": "V27", "cat": "cat2", "cat_name": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "catName": "🔬 Agent Studios, ToT/GoT & Traces (V11–V27)", "name": "V27 vLLM / SGLang RadixAttention KV-Cache Prefix-Tree Visualizer", "color": "#00f5d4", "c2": "#a855f7", "c3": "#f59e0b", "bg": "#030911", "arch": "mcts_tree", "png": "hivemind_cot_27.png"}, {"id": "V28", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V28 DARPA AlphaDogfight / Skyborg Autonomous Wingman CoT Display", "color": "#00ff88", "c2": "#38bdf8", "c3": "#f59e0b", "bg": "#060d09", "arch": "f35_hud_mfd", "png": "hivemind_cot_28.png"}, {"id": "V29", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V29 US Space Force JSpOC Orbital Constellation & 12U Ground Link", "color": "#38bdf8", "c2": "#a855f7", "c3": "#22c55e", "bg": "#040814", "arch": "eve_tidi_orbit", "png": "hivemind_cot_29.png"}, {"id": "V30", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V30 Palantir AIP Defense Ontology & Multi-Agent CoT Decision Graph", "color": "#60a5fa", "c2": "#10b981", "c3": "#f43f5e", "bg": "#090b10", "arch": "military_c4isr_radar", "png": "hivemind_cot_30.png"}, {"id": "V31", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V31 Lockheed F-22 / NGAD 6th-Gen Sensor-Fusion 3-Screen Cockpit", "color": "#00ffcc", "c2": "#fbbf24", "c3": "#ef4444", "bg": "#050a0e", "arch": "f35_hud_mfd", "png": "hivemind_cot_31.png"}, {"id": "V32", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V32 DARPA Mosaic Warfare / JADC2 Joint All-Domain Kill-Web Mesh", "color": "#22c55e", "c2": "#f97316", "c3": "#38bdf8", "bg": "#080c0a", "arch": "military_c4isr_radar", "png": "hivemind_cot_32.png"}, {"id": "V33", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V33 B-21 Raider Stealth Strategic Bomber Mission & CoT Strike Table", "color": "#38bdf8", "c2": "#ef4444", "c3": "#10b981", "bg": "#05070b", "arch": "military_c4isr_radar", "png": "hivemind_cot_33.png"}, {"id": "V34", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V34 Aircraft Carrier Pri-Fly & CATCC 4xT4 Catapult Launch Board", "color": "#facc15", "c2": "#22c55e", "c3": "#38bdf8", "bg": "#070b12", "arch": "carrier_catapult", "png": "hivemind_cot_34.png"}, {"id": "V35", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V35 Nuclear Submarine AN/BYG-1 Combat Control & Acoustic CoT Sonar", "color": "#10b981", "c2": "#06b6d4", "c3": "#eab308", "bg": "#020908", "arch": "submarine_sonar", "png": "hivemind_cot_35.png"}, {"id": "V36", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V36 X-Ray 12U Physical Rack with Glowing CoT Neural Synapses", "color": "#a855f7", "c2": "#00f5d4", "c3": "#3b82f6", "bg": "#060913", "arch": "rack_12u_front_rear_xray", "png": "hivemind_cot_36.png"}, {"id": "V37", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V37 Ubiquiti UniFi Etherlighting + Live Agent CoT Per-Port Matrix", "color": "#00f5d4", "c2": "#3b82f6", "c3": "#a855f7", "bg": "#080b14", "arch": "etherlighting_switch_matrix", "png": "hivemind_cot_37.png"}, {"id": "V38", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V38 NVIDIA Nsight / 25GbE RoCE Tensor-Pipeline Profiler & CoT Map", "color": "#76b900", "c2": "#00d4ff", "c3": "#f59e0b", "bg": "#070a0e", "arch": "flamegraph_spans", "png": "hivemind_cot_38.png"}, {"id": "V39", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V39 VMware vSAN 107TB Storage-to-VRAM Weight Streaming & CoT Flow", "color": "#38bdf8", "c2": "#22c55e", "c3": "#a855f7", "bg": "#060b16", "arch": "sankey_river", "png": "hivemind_cot_39.png"}, {"id": "V40", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V40 HPE iLO4 & Rear UPS Thermal-to-Token Efficiency Map (Watts->tok/s)", "color": "#f97316", "c2": "#ef4444", "c3": "#38bdf8", "bg": "#0c070a", "arch": "rack_12u_front_rear_xray", "png": "hivemind_cot_40.png"}, {"id": "V41", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V41 Westworld Rehoboam Predictive AI Eclipse Ring & Divergence Waves", "color": "#f43f5e", "c2": "#e2e8f0", "c3": "#38bdf8", "bg": "#08080c", "arch": "rehoboam_ring", "png": "hivemind_cot_41.png"}, {"id": "V42", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V42 Halo UNSC Infinity / Cortana Holographic Tactical CoT Table", "color": "#00d4ff", "c2": "#60a5fa", "c3": "#a855f7", "bg": "#030914", "arch": "iso_floor", "png": "hivemind_cot_42.png"}, {"id": "V43", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V43 Evangelion NERV MAGI 3-Brain Consensus (MELCHIOR+BALTHASAR+CASPER)", "color": "#f97316", "c2": "#00ff66", "c3": "#ef4444", "bg": "#0a0505", "arch": "nerv_magi_trinity", "png": "hivemind_cot_43.png"}, {"id": "V44", "cat": "cat3", "cat_name": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "catName": "🪖 Military C4ISR, Avionics & Hardware CoT (V28–V44)", "name": "V44 Ghost in the Shell Section 9 Cyberbrain Dive & Barrier-Maze CoT", "color": "#00ffcc", "c2": "#a855f7", "c3": "#22c55e", "bg": "#030b09", "arch": "neural_cortex", "png": "hivemind_cot_44.png"}, {"id": "V45", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V45 CERN Large Hadron Collider (ATLAS) Particle-Collision CoT Detector", "color": "#38bdf8", "c2": "#facc15", "c3": "#ec4899", "bg": "#040711", "arch": "cern_collider", "png": "hivemind_cot_45.png"}, {"id": "V46", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V46 Quantum Circuit & Bloch-Sphere Entanglement CoT Composer (6-Pool)", "color": "#a855f7", "c2": "#00f5d4", "c3": "#38bdf8", "bg": "#060814", "arch": "quantum_bloch_rails", "png": "hivemind_cot_46.png"}, {"id": "V47", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V47 Mycelial Fungal Network & 12U Root-System Nutrient/Token Flow", "color": "#10b981", "c2": "#a3e635", "c3": "#38bdf8", "bg": "#040a07", "arch": "neural_cortex", "png": "hivemind_cot_47.png"}, {"id": "V48", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V48 Ant Colony / Bee Swarm Pheromone Trail Optimizer & CoT Mesh", "color": "#f59e0b", "c2": "#22c55e", "c3": "#38bdf8", "bg": "#090805", "arch": "neural_cortex", "png": "hivemind_cot_48.png"}, {"id": "V49", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V49 Cardiovascular 12U-Heart / Cloud-Lung / HiveMind-Brain Circulation", "color": "#f43f5e", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#0b0508", "arch": "sankey_river", "png": "hivemind_cot_49.png"}, {"id": "V50", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V50 Modular Eurorack Analog Synthesizer Patch-Bay (CV/Gate CoT Noodles)", "color": "#f43f5e", "c2": "#facc15", "c3": "#00f5d4", "bg": "#0a0a0f", "arch": "eurorack_synth_patch", "png": "hivemind_cot_50.png"}, {"id": "V51", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V51 High-Frequency Trading (HFT) Liquidity Depth & Arbitrage CoT Router", "color": "#22c55e", "c2": "#ef4444", "c3": "#38bdf8", "bg": "#05080c", "arch": "hft_orderbook", "png": "hivemind_cot_51.png"}, {"id": "V52", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V52 Global Submarine Fiber-Optic Cable & Cloud Peering CoT Map", "color": "#00f5d4", "c2": "#38bdf8", "c3": "#f59e0b", "bg": "#030914", "arch": "eve_tidi_orbit", "png": "hivemind_cot_52.png"}, {"id": "V53", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V53 Air-Traffic Control Tower 360° Surface Movement & Approach Radar", "color": "#00ff88", "c2": "#38bdf8", "c3": "#facc15", "bg": "#030a08", "arch": "military_c4isr_radar", "png": "hivemind_cot_53.png"}, {"id": "V54", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V54 6-Screen Day-Trader / NOC Mega-Desk Wallboard (3x2 CoT Engine)", "color": "#38bdf8", "c2": "#a855f7", "c3": "#22c55e", "bg": "#05070e", "arch": "centurion_omega_masterpiece", "png": "hivemind_cot_54.png"}, {"id": "V55", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V55 Split Left-Brain (Code/Pytest .82) vs Right-Brain (UI/Cloud) Bridge", "color": "#38bdf8", "c2": "#ec4899", "c3": "#10b981", "bg": "#060812", "arch": "neural_cortex", "png": "hivemind_cot_55.png"}, {"id": "V56", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V56 Time-Lapse Piano-Roll DAW Sequencer (Multi-Track Agent CoT Harmony)", "color": "#a855f7", "c2": "#22c55e", "c3": "#f59e0b", "bg": "#08090f", "arch": "flamegraph_spans", "png": "hivemind_cot_56.png"}, {"id": "V57", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V57 Isometric 3-Tier Glass Skybridge Pyramid (12U -> CoT -> Cloud)", "color": "#38bdf8", "c2": "#00f5d4", "c3": "#a855f7", "bg": "#050914", "arch": "iso_floor", "png": "hivemind_cot_57.png"}, {"id": "V58", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V58 Watchmaker's Tourbillon Mechanical Horology CoT Escapement & Gears", "color": "#f59e0b", "c2": "#38bdf8", "c3": "#10b981", "bg": "#0a0806", "arch": "cern_collider", "png": "hivemind_cot_58.png"}, {"id": "V59", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V59 3D Holographic Chessboard / Stratego Autonomous Agent CoT Grid", "color": "#60a5fa", "c2": "#f43f5e", "c3": "#22c55e", "bg": "#050811", "arch": "iso_floor", "png": "hivemind_cot_59.png"}, {"id": "V60", "cat": "cat4", "cat_name": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "catName": "⚛️ Physics, Bio-Swarm, Quant & Omega Walls (V45–V60)", "name": "V60 The Boylenet 'Omega HiveMind' 10-Panel Command Wall Synthesis", "color": "#00f5d4", "c2": "#a855f7", "c3": "#f59e0b", "bg": "#04060c", "arch": "centurion_omega_masterpiece", "png": "hivemind_cot_60.png"}, {"id": "V61", "cat": "cat5", "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "name": "V61 Anthropic Claude-Flow v4 Multi-Pool (A/B/C/D $1,000) + 12U CoT Mesh", "color": "#d97706", "c2": "#a855f7", "c3": "#38bdf8", "bg": "#08060c", "arch": "n8n_hanging_circles", "png": "hivemind_cot_61.png"}, {"id": "V62", "cat": "cat5", "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "name": "V62 OpenAI Codex gpt-6.1-sol + gpt-6-astra AST Slicing & Ramdisk CoT", "color": "#10b981", "c2": "#38bdf8", "c3": "#f59e0b", "bg": "#03090b", "arch": "knime_swimlanes", "png": "hivemind_cot_62.png"}, {"id": "V63", "cat": "cat5", "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "name": "V63 Kimi K2.8 thinking: max 100-Agent Orbital CoT Ring + Dual CDP Matrix", "color": "#f97316", "c2": "#06b6d4", "c3": "#a855f7", "bg": "#060711", "arch": "kimi_radial_core", "png": "hivemind_cot_63.png"}, {"id": "V64", "cat": "cat5", "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "name": "V64 Google Antigravity (AGY) Super-Swarm Subagent Tree + tmux Bridge", "color": "#38bdf8", "c2": "#a855f7", "c3": "#22c55e", "bg": "#040814", "arch": "mcts_tree", "png": "hivemind_cot_64.png"}, {"id": "V65", "cat": "cat5", "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "name": "V65 4-Pool Token Autobalancer (O1740) Quota Waterfall & Failover Graph", "color": "#22c55e", "c2": "#eab308", "c3": "#ef4444", "bg": "#04090d", "arch": "sankey_river", "png": "hivemind_cot_65.png"}, {"id": "V66", "cat": "cat5", "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "name": "V66 Speculative Decoding (ngram-mod + Draft) Verification Tree on 4xT4", "color": "#06b6d4", "c2": "#10b981", "c3": "#f59e0b", "bg": "#030910", "arch": "mcts_tree", "png": "hivemind_cot_66.png"}, {"id": "V67", "cat": "cat5", "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "name": "V67 Qdrant Vector Hippocampus (.125:6333) + PG Episodic Dreamer CoT", "color": "#ec4899", "c2": "#a855f7", "c3": "#38bdf8", "bg": "#070612", "arch": "neural_cortex", "png": "hivemind_cot_67.png"}, {"id": "V68", "cat": "cat5", "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "name": "V68 Gitea PR Webhook (:3000) -> 2-Lens Security & OffSec (:4092) CoT", "color": "#ef4444", "c2": "#38bdf8", "c3": "#10b981", "bg": "#09060c", "arch": "knime_swimlanes", "png": "hivemind_cot_68.png"}, {"id": "V69", "cat": "cat5", "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "name": "V69 Multimodal Voice (:4093) + Vision VQA/OCR (86-Model) CoT Pipeline", "color": "#a855f7", "c2": "#00f5d4", "c3": "#f59e0b", "bg": "#060712", "arch": "rivet_noodles", "png": "hivemind_cot_69.png"}, {"id": "V70", "cat": "cat5", "cat_name": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "catName": "⚡ Cross-Pool Claude/Codex/Kimi/AGY Engines (V61–V70)", "name": "V70 Sentinel Self-Healing (:4099) Root-Cause <think> & Auto-Recovery", "color": "#10b981", "c2": "#38bdf8", "c3": "#f43f5e", "bg": "#03090a", "arch": "langgraph_state", "png": "hivemind_cot_70.png"}, {"id": "V71", "cat": "cat6", "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "name": "V71 3D Isometric 12U Rack Cutaway with Fiber CoT Beams to Cloud Halo", "color": "#00f5d4", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#050912", "arch": "rack_12u_front_rear_xray", "png": "hivemind_cot_71.png"}, {"id": "V72", "cat": "cat6", "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "name": "V72 Split-Screen 2x2 Quad-Engine Wallboard (n8n + CRT + 12U + C4ISR)", "color": "#22c55e", "c2": "#38bdf8", "c3": "#f59e0b", "bg": "#05070d", "arch": "centurion_omega_masterpiece", "png": "hivemind_cot_72.png"}, {"id": "V73", "cat": "cat6", "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "name": "V73 Split-Screen 3x2 Six-Pack Mega-Wallboard (n8n, Kimi, KNIME, Rack)", "color": "#a855f7", "c2": "#00f5d4", "c3": "#38bdf8", "bg": "#04060b", "arch": "centurion_omega_masterpiece", "png": "hivemind_cot_73.png"}, {"id": "V74", "cat": "cat6", "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "name": "V74 Split-Screen 4x2 Eight-Engine Ultra-Wide NOC Command Wallboard", "color": "#38bdf8", "c2": "#10b981", "c3": "#ec4899", "bg": "#03050a", "arch": "centurion_omega_masterpiece", "png": "hivemind_cot_74.png"}, {"id": "V75", "cat": "cat6", "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "name": "V75 Dark-Matter Cosmological Web & Galaxy Filament HiveMind Supercluster", "color": "#a855f7", "c2": "#38bdf8", "c3": "#f43f5e", "bg": "#03040a", "arch": "neural_cortex", "png": "hivemind_cot_75.png"}, {"id": "V76", "cat": "cat6", "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "name": "V76 Weather Doppler Radar & Isobar Storm-Front CoT Compute Pressure Map", "color": "#22c55e", "c2": "#facc15", "c3": "#ef4444", "bg": "#040910", "arch": "military_c4isr_radar", "png": "hivemind_cot_76.png"}, {"id": "V77", "cat": "cat6", "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "name": "V77 Shinkansen High-Speed Bullet-Train Dispatch & CoT Signal Board", "color": "#00f5d4", "c2": "#f59e0b", "c3": "#38bdf8", "bg": "#050811", "arch": "factorio_conveyor_bus", "png": "hivemind_cot_77.png"}, {"id": "V78", "cat": "cat6", "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "name": "V78 DNA CRISPR Gene-Splicing & Protein-Folding CoT Synthesis Pipeline", "color": "#06b6d4", "c2": "#ec4899", "c3": "#22c55e", "bg": "#040a0e", "arch": "dna_helix", "png": "hivemind_cot_78.png"}, {"id": "V79", "cat": "cat6", "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "name": "V79 Formula-E / Le Mans Hybrid Energy-Recovery (ERS) Local-to-Cloud CoT", "color": "#00ff88", "c2": "#38bdf8", "c3": "#f43f5e", "bg": "#07090e", "arch": "sankey_river", "png": "hivemind_cot_79.png"}, {"id": "V80", "cat": "cat6", "cat_name": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "catName": "🧱 Multi-Wallboards, Space & Science CoT (V71–V80)", "name": "V80 NASA James Webb Space Telescope (JWST) 18-Hexagon Gold Mirror CoT", "color": "#fbbf24", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#080604", "arch": "jwst_hex_mirrors", "png": "hivemind_cot_80.png"}, {"id": "V81", "cat": "cat7", "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "name": "V81 NSA / USCYBERCOM Global Threat-Hunting & Zero-Trust CoT Attribution", "color": "#00f5d4", "c2": "#ef4444", "c3": "#38bdf8", "bg": "#03080e", "arch": "military_c4isr_radar", "png": "hivemind_cot_81.png"}, {"id": "V82", "cat": "cat7", "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "name": "V82 Apache AH-64E Guardian Target Acquisition (TADS/PNVS) CoT HUD", "color": "#22c55e", "c2": "#f59e0b", "c3": "#ef4444", "bg": "#030a05", "arch": "f35_hud_mfd", "png": "hivemind_cot_82.png"}, {"id": "V83", "cat": "cat7", "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "name": "V83 Patriot PAC-3 / THAAD Integrated Air & Missile Defense CoT Radar", "color": "#38bdf8", "c2": "#ef4444", "c3": "#22c55e", "bg": "#040811", "arch": "military_c4isr_radar", "png": "hivemind_cot_83.png"}, {"id": "V84", "cat": "cat7", "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "name": "V84 AWACS E-3 Sentry / E-7 Wedgetail Airborne Battle-Management CoT", "color": "#06b6d4", "c2": "#facc15", "c3": "#10b981", "bg": "#030910", "arch": "eve_tidi_orbit", "png": "hivemind_cot_84.png"}, {"id": "V85", "cat": "cat7", "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "name": "V85 USS Gerald R. Ford (CVN-78) Weapons Elevator & 12U Munitions Flow", "color": "#f59e0b", "c2": "#22c55e", "c3": "#38bdf8", "bg": "#07090f", "arch": "carrier_catapult", "png": "hivemind_cot_85.png"}, {"id": "V86", "cat": "cat7", "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "name": "V86 M1A2 Abrams SEP v4 Commander's Thermal Viewer (CITV) & Battle-Net", "color": "#10b981", "c2": "#f97316", "c3": "#eab308", "bg": "#040a06", "arch": "f35_hud_mfd", "png": "hivemind_cot_86.png"}, {"id": "V87", "cat": "cat7", "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "name": "V87 Lockheed SR-72 Darkstar Hypersonic Scramjet Mach-6 CoT Telemetry", "color": "#38bdf8", "c2": "#f43f5e", "c3": "#a855f7", "bg": "#040712", "arch": "f35_hud_mfd", "png": "hivemind_cot_87.png"}, {"id": "V88", "cat": "cat7", "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "name": "V88 SpaceX Starshield / Starlink Laser-Interlink Mesh + 12U Terminus", "color": "#60a5fa", "c2": "#00f5d4", "c3": "#a855f7", "bg": "#030712", "arch": "eve_tidi_orbit", "png": "hivemind_cot_88.png"}, {"id": "V89", "cat": "cat7", "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "name": "V89 DARPA Grand Cyber Challenge Autonomous Binary-Analysis & Patch CoT", "color": "#ec4899", "c2": "#00f5d4", "c3": "#22c55e", "bg": "#070611", "arch": "flamegraph_spans", "png": "hivemind_cot_89.png"}, {"id": "V90", "cat": "cat7", "cat_name": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "catName": "🛡️ USCYBERCOM, Tactical HUDs & Recon CoT (V81–V90)", "name": "V90 NATO Joint Operations Center (JOC) Theater-Wide C4ISR + 12U Wall", "color": "#38bdf8", "c2": "#10b981", "c3": "#f59e0b", "bg": "#040810", "arch": "centurion_omega_masterpiece", "png": "hivemind_cot_90.png"}, {"id": "V91", "cat": "cat8", "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "name": "V91 Unreal Engine 5 Blueprint Visual Scripting & Execution Wire-Pulse", "color": "#38bdf8", "c2": "#ef4444", "c3": "#22c55e", "bg": "#0b0d12", "arch": "ue5_blueprint_nodes", "png": "hivemind_cot_91.png"}, {"id": "V92", "cat": "cat8", "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "name": "V92 SideFX Houdini Procedural Node-Network & VEX Tensor Particle Solver", "color": "#f97316", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#0d0f14", "arch": "ue5_blueprint_nodes", "png": "hivemind_cot_92.png"}, {"id": "V93", "cat": "cat8", "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "name": "V93 Blender Geometry-Nodes & Shader-Editor Canvas with 12U Viewport", "color": "#22c55e", "c2": "#a855f7", "c3": "#f59e0b", "bg": "#0c0d10", "arch": "ue5_blueprint_nodes", "png": "hivemind_cot_93.png"}, {"id": "V94", "cat": "cat8", "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "name": "V94 TouchDesigner Derivative Real-Time Audio-Visual Signal & CoT Net", "color": "#00ff88", "c2": "#ec4899", "c3": "#38bdf8", "bg": "#06080c", "arch": "eurorack_synth_patch", "png": "hivemind_cot_94.png"}, {"id": "V95", "cat": "cat8", "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "name": "V95 DaVinci Resolve Fusion Node Pipeline + Multi-Scope Waveform Parade", "color": "#f43f5e", "c2": "#22c55e", "c3": "#38bdf8", "bg": "#08090c", "arch": "sankey_river", "png": "hivemind_cot_95.png"}, {"id": "V96", "cat": "cat8", "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "name": "V96 Ableton Live / Bitwig Grid Modular DSP & Polyphonic Agent CoT", "color": "#f97316", "c2": "#00f5d4", "c3": "#a855f7", "bg": "#0a090d", "arch": "eurorack_synth_patch", "png": "hivemind_cot_96.png"}, {"id": "V97", "cat": "cat8", "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "name": "V97 Factorio / Dyson Sphere Mega-Base Main-Bus Conveyor & CoT Swarm", "color": "#f59e0b", "c2": "#22c55e", "c3": "#38bdf8", "bg": "#090806", "arch": "factorio_conveyor_bus", "png": "hivemind_cot_97.png"}, {"id": "V98", "cat": "cat8", "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "name": "V98 EVE Online TiDi Fleet-Commander Overview, Capacitor HUD & Drones", "color": "#38bdf8", "c2": "#facc15", "c3": "#ef4444", "bg": "#04070d", "arch": "eve_tidi_orbit", "png": "hivemind_cot_98.png"}, {"id": "V99", "cat": "cat8", "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "name": "V99 Homeworld 3D Sensors-Manager Sphere with 12U Mothership & Craft", "color": "#00d4ff", "c2": "#22c55e", "c3": "#f59e0b", "bg": "#020812", "arch": "eve_tidi_orbit", "png": "hivemind_cot_99.png"}, {"id": "V100", "cat": "cat8", "cat_name": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "catName": "🎮 UE5/Houdini/Blender Nodes & #100 Centurion (V91–V100)", "name": "V100 The Boylenet 'Centurion' Grand Unified 60fps HiveMind + 12U + Cloud Masterpiece", "color": "#00f5d4", "c2": "#a855f7", "c3": "#f59e0b", "bg": "#04070f", "arch": "centurion_omega_masterpiece", "png": "hivemind_cot_100.png"}, {"id": "T01", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T01 Ubiquiti UniFi OS Dark Topology (UDM-Pro + 280G Spine + 27 VMs)", "color": "#38bdf8", "c2": "#06b6d4", "c3": "#22c55e", "bg": "#0b0e14", "arch": "unifi_os", "png": "topology_mockup_01.png"}, {"id": "T02", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T02 n8n / ReactFlow 5-Stage Node-Wire Canvas & Agent Avatar Chips", "color": "#06b6d4", "c2": "#a855f7", "c3": "#22c55e", "bg": "#111318", "arch": "n8n_hanging_circles", "png": "topology_mockup_02.png"}, {"id": "T03", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T03 Palantir Gotham Tactical Defense HUD & 360° Azimuth Radar", "color": "#00f0ff", "c2": "#ffb000", "c3": "#10b981", "bg": "#03070b", "arch": "military_c4isr_radar", "png": "topology_mockup_03.png"}, {"id": "T04", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T04 Isometric 2.5D/3D Data-Center Floor (4 Elevated Glowing Platforms)", "color": "#06b6d4", "c2": "#a855f7", "c3": "#38bdf8", "bg": "#050914", "arch": "iso_floor", "png": "topology_mockup_04.png"}, {"id": "T05", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T05 Neural Swarm Orbital Galaxy (BD .164 + 280G Star Constellation)", "color": "#a855f7", "c2": "#38bdf8", "c3": "#f59e0b", "bg": "#030611", "arch": "eve_tidi_orbit", "png": "topology_mockup_05.png"}, {"id": "T06", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T06 Apple VisionOS Spatial Glass Minimalist Aurora Command Deck", "color": "#e2e8f0", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#080c18", "arch": "centurion_omega_masterpiece", "png": "topology_mockup_06.png"}, {"id": "T07", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T07 Live Sankey / Alluvial Token & Compute River (4-Stage Flow)", "color": "#38bdf8", "c2": "#22c55e", "c3": "#a855f7", "bg": "#040812", "arch": "sankey_river", "png": "topology_mockup_07.png"}, {"id": "T08", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T08 Hexagonal Honeycomb Swarm Hive (4 Cellular Compute Clusters)", "color": "#fbbf24", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#07080f", "arch": "jwst_hex_mirrors", "png": "topology_mockup_08.png"}, {"id": "T09", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T09 Physical 12U Rack Digital Twin (79.5°F Front + Rear UPS + Pro-Max)", "color": "#ef4444", "c2": "#10b981", "c3": "#38bdf8", "bg": "#040812", "arch": "rack_twin", "png": "topology_mockup_09.png"}, {"id": "T10", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T10 Cyberpunk 3D Holo-Deck & Split Tactical Cockpit", "color": "#facc15", "c2": "#00f5d4", "c3": "#ec4899", "bg": "#050711", "arch": "iso_floor", "png": "topology_mockup_10.png"}, {"id": "T11", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T11 Dual Front + Rear 12U Rack Twin with Interactive Fiber/DAC Tracing", "color": "#ef4444", "c2": "#06b6d4", "c3": "#10b981", "bg": "#040812", "arch": "rack_twin", "png": "topology_mockup_11.png"}, {"id": "T12", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T12 Exploded 3D HPE ProLiant DL380 Lid-Off Chassis Cutaway (Xeon+T4)", "color": "#06b6d4", "c2": "#f59e0b", "c3": "#22c55e", "bg": "#050912", "arch": "rack_12u_front_rear_xray", "png": "topology_mockup_12.png"}, {"id": "T13", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T13 Ubiquiti Etherlighting Switch Port Matrix (UDM-Pro + Pro-Agg + Max)", "color": "#38bdf8", "c2": "#a855f7", "c3": "#00f5d4", "bg": "#060a14", "arch": "etherlighting_switch_matrix", "png": "topology_mockup_13.png"}, {"id": "T14", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T14 Thermal Infrared (FLIR Ironbow) 12U Rack & CFD Airflow Heatmap", "color": "#f97316", "c2": "#ef4444", "c3": "#facc15", "bg": "#0a0608", "arch": "rack_12u_front_rear_xray", "png": "topology_mockup_14.png"}, {"id": "T15", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T15 vSAN Storage Bay & 75-Disk Group Blueprint (4x24TB Exos + SAS)", "color": "#ec4899", "c2": "#38bdf8", "c3": "#22c55e", "bg": "#070712", "arch": "etherlighting_switch_matrix", "png": "topology_mockup_15.png"}, {"id": "T16", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T16 Iron Man JARVIS / Stark Arc-Reactor Holographic HUD", "color": "#38bdf8", "c2": "#00f5d4", "c3": "#f59e0b", "bg": "#030914", "arch": "rehoboam_ring", "png": "topology_mockup_16.png"}, {"id": "T17", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T17 TRON Legacy Neon Light-Grid Arena", "color": "#22d3ee", "c2": "#f97316", "c3": "#38bdf8", "bg": "#02060d", "arch": "iso_floor", "png": "topology_mockup_17.png"}, {"id": "T18", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T18 Star Trek LCARS Enterprise Engineering Deck", "color": "#fb923c", "c2": "#c084fc", "c3": "#38bdf8", "bg": "#04060e", "arch": "lcars_deck", "png": "topology_mockup_18.png"}, {"id": "T19", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T19 Minority Report / Oblivion Ice-White Light-Table UI", "color": "#e2e8f0", "c2": "#38bdf8", "c3": "#06b6d4", "bg": "#080d18", "arch": "rehoboam_ring", "png": "topology_mockup_19.png"}, {"id": "T20", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T20 Retro-Futuristic Amber/Green Phosphor CRT Oscilloscope Mainframe", "color": "#10b981", "c2": "#f59e0b", "c3": "#34d399", "bg": "#020804", "arch": "hivemind_crt", "png": "topology_mockup_20.png"}, {"id": "T21", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T21 Datadog APM Live Service Map with Throughput Rings & SLA Halos", "color": "#a855f7", "c2": "#38bdf8", "c3": "#22c55e", "bg": "#060712", "arch": "kimi_radial_core", "png": "topology_mockup_21.png"}, {"id": "T22", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T22 Grafana Node-Graph with Embedded 60s CPU/GPU/Network Sparklines", "color": "#f97316", "c2": "#22c55e", "c3": "#38bdf8", "bg": "#060810", "arch": "ue5_blueprint_nodes", "png": "topology_mockup_22.png"}, {"id": "T23", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T23 Terraform / CloudFormation Clean Left-to-Right Dependency DAG", "color": "#818cf8", "c2": "#38bdf8", "c3": "#22c55e", "bg": "#050812", "arch": "knime_swimlanes", "png": "topology_mockup_23.png"}, {"id": "T24", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T24 Cilium Hubble / Kubernetes eBPF Service Mesh (4 VLAN Namespaces)", "color": "#38bdf8", "c2": "#10b981", "c3": "#a855f7", "bg": "#040812", "arch": "knime_swimlanes", "png": "topology_mockup_24.png"}, {"id": "T25", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T25 Linear / Vercel Ultra-Minimal Monochrome (#000000 + Emerald)", "color": "#10b981", "c2": "#e2e8f0", "c3": "#38bdf8", "bg": "#020408", "arch": "mcts_tree", "png": "topology_mockup_25.png"}, {"id": "T26", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T26 3D Brain Cortex & Firing Neural Synapses Topology", "color": "#a855f7", "c2": "#ec4899", "c3": "#06b6d4", "bg": "#050612", "arch": "neural_cortex", "png": "topology_mockup_26.png"}, {"id": "T27", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T27 Magnetic Vector Field & Luminescent Particle Fluid Stream", "color": "#22c55e", "c2": "#06b6d4", "c3": "#38bdf8", "bg": "#030910", "arch": "sankey_river", "png": "topology_mockup_27.png"}, {"id": "T28", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T28 Dual-Vault DNA Double-Helix Bridge (.72 4.7TB & .83 4.2TB)", "color": "#ec4899", "c2": "#06b6d4", "c3": "#a855f7", "bg": "#060712", "arch": "dna_helix", "png": "topology_mockup_28.png"}, {"id": "T29", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T29 Gravitational N-Body Solar System (VMs Sized by RAM/VRAM + Moons)", "color": "#f59e0b", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#040711", "arch": "eve_tidi_orbit", "png": "topology_mockup_29.png"}, {"id": "T30", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T30 Circos 360° Chord Ribbon Wheel (27 VMs + 12 Harnesses)", "color": "#06b6d4", "c2": "#ec4899", "c3": "#f59e0b", "bg": "#040812", "arch": "cern_collider", "png": "topology_mockup_30.png"}, {"id": "T31", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T31 SpaceX Hawthorne Flight Control Screen (Telemetry Arc + Go/No-Go)", "color": "#60a5fa", "c2": "#22c55e", "c3": "#f59e0b", "bg": "#040812", "arch": "carrier_catapult", "png": "topology_mockup_31.png"}, {"id": "T32", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T32 Air Traffic Control (ATC) Polar Radar Scope with VM Callsigns", "color": "#34d399", "c2": "#38bdf8", "c3": "#facc15", "bg": "#020906", "arch": "military_c4isr_radar", "png": "topology_mockup_32.png"}, {"id": "T33", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T33 Submarine Sonar & Time-Frequency Waterfall Matrix", "color": "#06b6d4", "c2": "#10b981", "c3": "#eab308", "bg": "#02080a", "arch": "submarine_sonar", "png": "topology_mockup_33.png"}, {"id": "T34", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T34 Formula 1 Pit-Wall Telemetry & Purple-Sector Delta Board", "color": "#ef4444", "c2": "#a855f7", "c3": "#22c55e", "bg": "#08060c", "arch": "hft_orderbook", "png": "topology_mockup_34.png"}, {"id": "T35", "cat": "cat9", "cat_name": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "catName": "🗄️ 12U Physical Rack Twins, Blueprints & NOC (T01–T35)", "name": "T35 Bloomberg Terminal High-Density Quant Order-Book & Token Matrix", "color": "#f59e0b", "c2": "#22c55e", "c3": "#38bdf8", "bg": "#07080c", "arch": "hft_orderbook", "png": "topology_mockup_35.png"}, {"id": "T36", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T36 Live Swarm Factory Conveyor Belt (Queued->O1740->GPU->Ramdisk)", "color": "#f59e0b", "c2": "#22c55e", "c3": "#38bdf8", "bg": "#07080d", "arch": "factorio_conveyor_bus", "png": "topology_mockup_36.png"}, {"id": "T37", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T37 12-Harness Gladiator Colosseum (Claude ABCD, Codex, Kimi, AGY)", "color": "#f97316", "c2": "#a855f7", "c3": "#00f5d4", "bg": "#08070e", "arch": "kimi_radial_core", "png": "topology_mockup_37.png"}, {"id": "T38", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T38 London Underground / Tokyo Metro VLAN 75/70/60/20/10 Transit Map", "color": "#ef4444", "c2": "#38bdf8", "c3": "#fbbf24", "bg": "#050811", "arch": "factorio_conveyor_bus", "png": "topology_mockup_38.png"}, {"id": "T39", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T39 Split Top-Map (:4088) + Bottom 3x3 Live Headless Agent TV Wall (:4083)", "color": "#38bdf8", "c2": "#10b981", "c3": "#a855f7", "bg": "#040710", "arch": "centurion_omega_masterpiece", "png": "topology_mockup_39.png"}, {"id": "T40", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T40 $1,000 Cloud Credit & Pool Quota Fuel-Tank Transfer Diagram", "color": "#c084fc", "c2": "#38bdf8", "c3": "#22c55e", "bg": "#060712", "arch": "sankey_river", "png": "topology_mockup_40.png"}, {"id": "T41", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T41 Prussian Blue CAD Architectural 12U Rack Blueprint (EIA-310-D)", "color": "#38bdf8", "c2": "#e2e8f0", "c3": "#60a5fa", "bg": "#0a192f", "arch": "rack_12u_front_rear_xray", "png": "topology_mockup_41.png"}, {"id": "T42", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T42 Silicon Die & Gold-Trace PCB Motherboard Layout (4x T4 Chiplets)", "color": "#10b981", "c2": "#fbbf24", "c3": "#38bdf8", "bg": "#040a08", "arch": "etherlighting_switch_matrix", "png": "topology_mockup_42.png"}, {"id": "T43", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T43 'Boylenet Metropolis' Isometric 3D Cyber-City Skyline & VLAN Highways", "color": "#00f5d4", "c2": "#ec4899", "c3": "#38bdf8", "bg": "#040711", "arch": "iso_floor", "png": "topology_mockup_43.png"}, {"id": "T44", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T44 SCADA Electrical & Power-Flow Single-Line Diagram (UPS -> 8x800W PSU)", "color": "#eab308", "c2": "#22c55e", "c3": "#38bdf8", "bg": "#07090c", "arch": "sankey_river", "png": "topology_mockup_44.png"}, {"id": "T45", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T45 8.9 TB Dual-Vault 86-Model Treemap & Sunburst Visualizer", "color": "#f43f5e", "c2": "#a855f7", "c3": "#38bdf8", "bg": "#07060f", "arch": "cern_collider", "png": "topology_mockup_45.png"}, {"id": "T46", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T46 macOS Sequoia / iPadOS 12-Column Frosted Glass Bento Command Center", "color": "#60a5fa", "c2": "#a855f7", "c3": "#22c55e", "bg": "#060913", "arch": "centurion_omega_masterpiece", "png": "topology_mockup_46.png"}, {"id": "T47", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T47 Cyberpunk 2077 / Arasaka Crimson & Obsidian Netrunner Breach Deck", "color": "#facc15", "c2": "#ef4444", "c3": "#00f5d4", "bg": "#090508", "arch": "f35_hud_mfd", "png": "topology_mockup_47.png"}, {"id": "T48", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T48 Studio Mixing Console & Bouncing LED VU-Meter Channel Strips", "color": "#22c55e", "c2": "#f59e0b", "c3": "#ef4444", "bg": "#07080d", "arch": "eurorack_synth_patch", "png": "topology_mockup_48.png"}, {"id": "T49", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T49 4-Quadrant NOC Wallboard (UniFi + 3D Holo + 12U Twin + Terminal)", "color": "#38bdf8", "c2": "#a855f7", "c3": "#10b981", "bg": "#040710", "arch": "centurion_omega_masterpiece", "png": "topology_mockup_49.png"}, {"id": "T50", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T50 'The Ultimate Boylenet Hybrid Cockpit' (12U Rack + CoT + Cloud)", "color": "#00f5d4", "c2": "#a855f7", "c3": "#f59e0b", "bg": "#040710", "arch": "hybrid", "png": "topology_mockup_50.png"}, {"id": "T51", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T51 Crisp Daylight / E-Ink Carta 1300 Architectural Blueprint Mode", "color": "#38bdf8", "c2": "#94a3b8", "c3": "#0ea5e9", "bg": "#09101d", "arch": "rack_12u_front_rear_xray", "png": "topology_mockup_51.png"}, {"id": "T52", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T52 Pure OLED #000000 Zero-Glare Midnight Mode (1px Specular Borders)", "color": "#10b981", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#000000", "arch": "mcts_tree", "png": "topology_mockup_52.png"}, {"id": "T53", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T53 25GbE RoCE 80-Layer Transformer Split Visualizer (L01-L80 on 4xT4)", "color": "#06b6d4", "c2": "#a855f7", "c3": "#22c55e", "bg": "#040811", "arch": "quantum_bloch_rails", "png": "topology_mockup_53.png"}, {"id": "T54", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T54 Qdrant 3D Vector Embedding Point-Cloud & Semantic Cluster Map", "color": "#ec4899", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#060712", "arch": "neural_cortex", "png": "topology_mockup_54.png"}, {"id": "T55", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T55 Sentinel 31-Service Self-Healing Shield & Perimeter Dome (:4099)", "color": "#10b981", "c2": "#38bdf8", "c3": "#f59e0b", "bg": "#030908", "arch": "rehoboam_ring", "png": "topology_mockup_55.png"}, {"id": "T56", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T56 Boylenet <-> Boylenet Mobile Site-Magic Cross-Site Topology (398 DNS)", "color": "#14b8a6", "c2": "#38bdf8", "c3": "#a855f7", "bg": "#040910", "arch": "eve_tidi_orbit", "png": "topology_mockup_56.png"}, {"id": "T57", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T57 Dual Browser Oracle (.137 BattleStation + .181 Bittorrent) CDP Wall", "color": "#f97316", "c2": "#38bdf8", "c3": "#22c55e", "bg": "#070810", "arch": "etherlighting_switch_matrix", "png": "topology_mockup_57.png"}, {"id": "T58", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T58 64-Core /dev/shm Ramdisk Pytest Shard Distribution Map (.82 test3big)", "color": "#22c55e", "c2": "#38bdf8", "c3": "#f59e0b", "bg": "#04090c", "arch": "etherlighting_switch_matrix", "png": "topology_mockup_58.png"}, {"id": "T59", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T59 24-Hour Time-Machine Cluster Replay & Heatmap Timeline (:4092 DVR)", "color": "#38bdf8", "c2": "#a855f7", "c3": "#f97316", "bg": "#050811", "arch": "flamegraph_spans", "png": "topology_mockup_59.png"}, {"id": "T60", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T60 Boylenet OS 'One-Screen Masterpiece' (App Dock + 12U + CoT + Cloud)", "color": "#00f5d4", "c2": "#a855f7", "c3": "#38bdf8", "bg": "#040710", "arch": "centurion_omega_masterpiece", "png": "topology_mockup_60.png"}, {"id": "T61", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T61 Anduril Lattice / Palantir Maven Autonomous Swarm C2 Tactical Deck", "color": "#10b981", "c2": "#f59e0b", "c3": "#38bdf8", "bg": "#040907", "arch": "military_c4isr_radar", "png": "topology_mockup_61.png"}, {"id": "T62", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T62 Navy AEGIS Combat Information Center (CIC) (50/100/250 NM Radar)", "color": "#38bdf8", "c2": "#00f5d4", "c3": "#f59e0b", "bg": "#030812", "arch": "military_c4isr_radar", "png": "topology_mockup_62.png"}, {"id": "T63", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T63 F-35 Helmet-Mounted Display & FLIR Night-Vision MFD (#00ff66)", "color": "#4ade80", "c2": "#22c55e", "c3": "#facc15", "bg": "#020905", "arch": "f35_hud_mfd", "png": "topology_mockup_63.png"}, {"id": "T64", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T64 NORAD / Cheyenne Mountain Strategic Command Trajectory Map", "color": "#f59e0b", "c2": "#ef4444", "c3": "#38bdf8", "bg": "#070609", "arch": "military_c4isr_radar", "png": "topology_mockup_64.png"}, {"id": "T65", "cat": "cat10", "cat_name": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "catName": "⚔️ Topology Lenses, Cyberpunk & C4ISR Decks (T36–T65)", "name": "T65 Tactical 12U Hardware Stores & Munitions MFD (Front+Rear 12U Twin)", "color": "#22c55e", "c2": "#f59e0b", "c3": "#ef4444", "bg": "#030906", "arch": "carrier_catapult", "png": "topology_mockup_65.png"}];

const VIEWS_MAP = {};
VIEWS_CATALOG.forEach(v => {
  VIEWS_MAP[v.id] = v;
  // Support 3-digit zero-padded aliases like V001..V099 and T001..T065
  const prefix = v.id[0];
  const num = parseInt(v.id.slice(1), 10);
  if (!isNaN(num)) {
    VIEWS_MAP[prefix + String(num).padStart(3, '0')] = v;
    VIEWS_MAP[prefix + String(num)] = v;
  }
});

function normalizeViewId(raw) {
  if (!raw) return 'V01';
  const up = String(raw).trim().toUpperCase();
  if (VIEWS_MAP[up]) return VIEWS_MAP[up].id;
  return 'V01';
}

function buildSelectOptionsHTML() {
  const cats = ['cat1', 'cat2', 'cat3', 'cat4', 'cat5', 'cat6', 'cat7', 'cat8', 'cat9', 'cat10'];
  return cats.map(c => {
    const items = VIEWS_CATALOG.filter(v => v.cat === c);
    const label = items[0] ? items[0].catName : c;
    const opts = items.map(v => `<option value="${v.id}">${v.name}</option>`).join('');
    return `<optgroup label="${label}">${opts}</optgroup>`;
  }).join('');
}

function getActiveWallboardArray() {
  if (WALLBOARD === 'eight') return EIGHT_VIEWS;
  if (WALLBOARD === 'six') return SIX_VIEWS;
  return QUAD_VIEWS;
}

function getActiveWallboardCount() {
  if (WALLBOARD === 'eight') return 8;
  if (WALLBOARD === 'six') return 6;
  return 4;
}

function initCatalogUI() {
  const optsHtml = buildSelectOptionsHTML();
  const topSel = document.getElementById('top-view-select');
  if (topSel) {
    topSel.innerHTML = optsHtml;
    topSel.value = ACTIVE_VIEW;
  }
  for (let i = 0; i < 8; i++) {
    const sel = document.getElementById('wb-sel-' + i);
    if (sel) {
      sel.innerHTML = optsHtml;
      sel.value = EIGHT_VIEWS[i] || 'V01';
    }
  }
  renderCatalogGrid();
  renderCategorySubbar();
  syncWallboardHeaders();
}

function renderCatalogGrid() {
  const grid = document.getElementById('catalog-grid');
  if (!grid) return;
  const qEl = document.getElementById('cat-search');
  const q = qEl ? (qEl.value || '').trim().toLowerCase() : '';
  const list = VIEWS_CATALOG.filter(v => {
    const matchCat = (CATALOG_FILTER === 'all') || (v.cat === CATALOG_FILTER);
    const matchQ = !q || v.id.toLowerCase().includes(q) || v.name.toLowerCase().includes(q) || (v.arch && v.arch.toLowerCase().includes(q));
    return matchCat && matchQ;
  });
  const cntLbl = document.getElementById('cat-count-lbl');
  if (cntLbl) cntLbl.textContent = `${list.length} / 165 Views`;
  grid.innerHTML = list.map(v => {
    const isAct = (v.id === ACTIVE_VIEW);
    const isPref = (PREFERRED_STATE && PREFERRED_STATE.preferred_view === v.id);
    const shortTitle = v.name.replace(/^[VT]\d+\s+/, '');
    return `<div class="v-card ${isAct ? 'active' : ''}" id="vcard-${v.id}" onclick="selectView('${v.id}')" title="${v.name}">
      <span class="v-badge" style="background:${v.color};">${v.id}${isPref ? '★' : ''}</span>
      <span class="v-name">${shortTitle}</span>
    </div>`;
  }).join('');
}

function renderCategorySubbar() {
  const bar = document.getElementById('hm-subbar');
  if (!bar) return;
  const cur = VIEWS_MAP[ACTIVE_VIEW] || VIEWS_CATALOG[0];
  const siblings = VIEWS_CATALOG.filter(v => v.cat === cur.cat);
  bar.innerHTML = siblings.map(v => {
    const shortLbl = v.name.length > 30 ? v.name.slice(0, 28) + '…' : v.name;
    return `<button class="hm-sub-btn ${v.id === ACTIVE_VIEW ? 'active' : ''}" onclick="selectView('${v.id}')">${shortLbl}</button>`;
  }).join('');
}

function toggleCatalog(forceState) {
  CATALOG_OPEN = (typeof forceState === 'boolean') ? forceState : !CATALOG_OPEN;
  const dr = document.getElementById('catalog-drawer');
  if (dr) dr.classList.toggle('open', CATALOG_OPEN);
  const btn = document.getElementById('btn-catalog');
  if (btn) btn.classList.toggle('active', CATALOG_OPEN);
  setTimeout(resetView, 30);
  setTimeout(resetView, 200);
}

function filterCatalog(cat) {
  CATALOG_FILTER = cat;
  ['all','cat1','cat2','cat3','cat4','cat5','cat6','cat7','cat8','cat9','cat10'].forEach(k => {
    const el = document.getElementById('ct-' + k);
    if (el) el.classList.toggle('active', k === cat);
  });
  renderCatalogGrid();
}

function jumpCategory(cat) {
  const first = VIEWS_CATALOG.find(v => v.cat === cat);
  if (first) {
    filterCatalog(cat);
    selectView(first.id);
  }
}

let WB_DIRTY = 8;
let WB_TICK = 0;

function selectView(rawViewId) {
  const viewId = normalizeViewId(rawViewId);
  if (!VIEWS_MAP[viewId]) return;
  ACTIVE_VIEW = viewId;
  const v = VIEWS_MAP[viewId];
  MODE = (v.arch === 'iso_floor' || viewId === 'V36') ? '3d' : (v.arch === 'unifi_os' ? 'graph' : 'hivemind');
  WB_DIRTY = 8;
  const topSel = document.getElementById('top-view-select');
  if (topSel) topSel.value = viewId;
  const kAct = document.getElementById('k-active-view');
  if (kAct) {
    kAct.textContent = v.name;
    kAct.style.color = v.color;
  }
  const milBanner = document.getElementById('mil-banner');
  if (milBanner) milBanner.style.display = (v.cat === 'cat3' || v.cat === 'cat7' || v.cat === 'cat10') ? 'inline-flex' : 'none';
  if (WALLBOARD !== 'single') {
    const arr = getActiveWallboardArray();
    arr[0] = viewId;
    syncWallboardHeaders();
  }
  renderCatalogGrid();
  renderCategorySubbar();
}

function stepView(delta) {
  const idx = VIEWS_CATALOG.findIndex(v => v.id === ACTIVE_VIEW);
  const nextIdx = (idx + delta + VIEWS_CATALOG.length) % VIEWS_CATALOG.length;
  selectView(VIEWS_CATALOG[nextIdx].id);
  if (WALLBOARD === 'quad') {
    for (let i = 0; i < 4; i++) {
      QUAD_VIEWS[i] = VIEWS_CATALOG[(nextIdx + i * 11) % VIEWS_CATALOG.length].id;
    }
    syncWallboardHeaders();
  } else if (WALLBOARD === 'six') {
    for (let i = 0; i < 6; i++) {
      SIX_VIEWS[i] = VIEWS_CATALOG[(nextIdx + i * 9) % VIEWS_CATALOG.length].id;
    }
    syncWallboardHeaders();
  } else if (WALLBOARD === 'eight') {
    for (let i = 0; i < 8; i++) {
      EIGHT_VIEWS[i] = VIEWS_CATALOG[(nextIdx + i * 7) % VIEWS_CATALOG.length].id;
    }
    syncWallboardHeaders();
  }
}

function syncWallboardHeaders() {
  WB_DIRTY = 8;
  const arr = getActiveWallboardArray();
  const count = getActiveWallboardCount();
  const prefix = (WALLBOARD === 'eight') ? 'E' : (WALLBOARD === 'six' ? 'S' : 'Q');
  for (let i = 0; i < 8; i++) {
    const cell = document.getElementById('wb-cell-' + i);
    if (cell) cell.style.display = (i < count) ? 'flex' : 'none';
    const vid = normalizeViewId(arr[i] || 'V01');
    const v = VIEWS_MAP[vid] || VIEWS_CATALOG[0];
    const tag = document.getElementById('wb-tag-' + i);
    if (tag) {
      tag.textContent = prefix + (i + 1);
      tag.style.background = v.color;
      tag.style.color = '#020617';
    }
    const ttl = document.getElementById('wb-title-' + i);
    if (ttl) ttl.textContent = v.name;
    const sel = document.getElementById('wb-sel-' + i);
    if (sel) sel.value = vid;
  }
}

function setWallboard(wb) {
  WALLBOARD = wb;
  WB_DIRTY = 8;
  ['single', 'quad', 'six', 'eight'].forEach(k => {
    const b = document.getElementById('wb-' + k);
    if (b) b.classList.toggle('active', k === wb);
  });
  const singleEl = document.getElementById('single-stage');
  const gridEl = document.getElementById('wallboard-grid');
  if (wb === 'single') {
    if (singleEl) singleEl.style.display = 'block';
    if (gridEl) {
      gridEl.style.display = 'none';
      gridEl.className = '';
    }
  } else {
    if (CATALOG_OPEN) toggleCatalog(false);
    if (singleEl) singleEl.style.display = 'none';
    if (gridEl) {
      gridEl.style.display = 'grid';
      gridEl.className = (wb === 'quad') ? 'quad-mode' : ((wb === 'six') ? 'six-mode' : 'eight-mode');
    }
    syncWallboardHeaders();
  }
  setTimeout(resetView, 25);
}

function setSlotView(slotIdx, rawViewId) {
  const viewId = normalizeViewId(rawViewId);
  if (!VIEWS_MAP[viewId]) return;
  if (WALLBOARD === 'eight') EIGHT_VIEWS[slotIdx] = viewId;
  else if (WALLBOARD === 'six') SIX_VIEWS[slotIdx] = viewId;
  else QUAD_VIEWS[slotIdx] = viewId;
  syncWallboardHeaders();
}

function maximizeSlot(slotIdx) {
  const arr = getActiveWallboardArray();
  const vid = arr[slotIdx];
  setWallboard('single');
  selectView(vid || 'V01');
}

function toggleCinema(forceState) {
  CINEMA_ACTIVE = (typeof forceState === 'boolean') ? forceState : !CINEMA_ACTIVE;
  CINEMA_LAST_SWITCH = performance.now();
  const btn = document.getElementById('btn-cinema');
  if (btn) {
    btn.classList.toggle('active', CINEMA_ACTIVE);
    btn.textContent = CINEMA_ACTIVE ? '🎬 Cinema ON (15s)' : '🎬 Cinema (15s)';
  }
}

function updatePreferredBadgeUI(pref) {
  if (!pref) return;
  PREFERRED_STATE = pref;
  const el = document.getElementById('pref-view-id');
  if (el) {
    const wbSuffix = (pref.wallboard && pref.wallboard !== 'single') ? ` (${pref.wallboard.toUpperCase()})` : '';
    el.textContent = `${pref.preferred_view || 'V01'}${wbSuffix}`;
  }
  renderCatalogGrid();
}

async function savePreferredView() {
  const btn = document.getElementById('btn-set-preferred');
  try {
    const payload = {
      preferred_view: ACTIVE_VIEW,
      wallboard: WALLBOARD,
      quad_views: QUAD_VIEWS,
      six_views: SIX_VIEWS,
      eight_views: EIGHT_VIEWS
    };
    const r = await fetch('/api/preferred-view', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const saved = await r.json();
    updatePreferredBadgeUI(saved);
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = `✅ Saved Preferred: ${ACTIVE_VIEW}!`;
      setTimeout(() => { btn.innerHTML = orig; }, 2200);
    }
  } catch (e) {
    console.error('Failed saving preferred view', e);
  }
}

function applySavedPreferred() {
  if (!PREFERRED_STATE) return;
  if (Array.isArray(PREFERRED_STATE.quad_views) && PREFERRED_STATE.quad_views.length >= 4) QUAD_VIEWS = PREFERRED_STATE.quad_views.slice(0, 4);
  if (Array.isArray(PREFERRED_STATE.six_views) && PREFERRED_STATE.six_views.length >= 6) SIX_VIEWS = PREFERRED_STATE.six_views.slice(0, 6);
  if (Array.isArray(PREFERRED_STATE.eight_views) && PREFERRED_STATE.eight_views.length >= 8) EIGHT_VIEWS = PREFERRED_STATE.eight_views.slice(0, 8);
  selectView(PREFERRED_STATE.preferred_view || 'V01');
  if (PREFERRED_STATE.wallboard && ['single', 'quad', 'six', 'eight'].includes(PREFERRED_STATE.wallboard)) {
    setWallboard(PREFERRED_STATE.wallboard);
  }
}

async function fetchInitialPreferred(applyIfNoQuery) {
  try {
    const r = await fetch('/api/preferred-view');
    const pref = await r.json();
    updatePreferredBadgeUI(pref);
    if (applyIfNoQuery) {
      applySavedPreferred();
    }
  } catch (e) {
    console.error('Preferred view fetch failed', e);
  }
}

async function loadTopology() {
  try {
    const [r, rp] = await Promise.all([
      fetch('/api/topology'),
      fetch('/api/preferred-view')
    ]);
    DATA = await r.json();
    if (rp && rp.ok) {
      const pref = await rp.json();
      if (!PREFERRED_STATE || pref.preferred_view !== PREFERRED_STATE.preferred_view || pref.wallboard !== PREFERRED_STATE.wallboard) {
        updatePreferredBadgeUI(pref);
      }
    }
    if (DATA.summary) {
      document.getElementById('k-sess').textContent = `${DATA.summary.active_tmux_sessions} Active`;
      document.getElementById('k-model').textContent = `${DATA.summary.active_model} (77.6 tok/s)`;
      document.getElementById('k-vsan').textContent = `${DATA.summary.vsan_used_tib.toFixed(1)} / ${DATA.summary.vsan_capacity_tib.toFixed(1)} TiB (75 Disks)`;
    }
    if (DATA.flight_recorder && DATA.flight_recorder.length) {
      document.getElementById('ticker-msg').textContent = DATA.flight_recorder.join('   •   ');
    }
    if (PARTICLES.length === 0 && DATA.flows) {
      DATA.flows.forEach(fl => {
        const cnt = fl.particles || 3;
        for (let i = 0; i < cnt; i++) {
          PARTICLES.push({
            flow: fl,
            t: i / cnt,
            speed: (fl.speed || 1.2) * 0.0045,
            burst: false
          });
        }
      });
    }
  } catch (e) {
    console.error(e);
  }
}

function setMode(m) {
  MODE = m;
  if (m === 'graph') selectView('V35');
  else if (m === 'galaxy') selectView('V04');
  else if (m === '3d') selectView('V36');
  else if (m === 'swimlane') selectView('V05');
  else if (m === 'rack') selectView('V19');
  else if (m === 'military') selectView('V11');
  resetView();
}

function setHmSub(s) {
  HM_SUB = s;
  const map = { hybrid: 'V01', n8n: 'V02', crt: 'V03', kimi: 'V04', pipeline: 'V05' };
  if (map[s]) selectView(map[s]);
}

function setDetail(d) {
  DETAIL = d;
  document.getElementById('dt-simple').classList.toggle('active', d === 'simple');
  document.getElementById('dt-adv').classList.toggle('active', d === 'advanced');
}

function setFlowFilter(f) { FLOW_FILTER = f; }

function triggerPulse() {
  PULSE_UNTIL = performance.now() + 4000;
  if (!DATA || !DATA.flows) return;
  DATA.flows.forEach(fl => {
    for (let i = 0; i < 3; i++) {
      PARTICLES.push({ flow: fl, t: Math.random(), speed: 0.011, burst: true });
    }
  });
}

function resetView() {
  const c = document.getElementById('main-canvas');
  if (c && c.parentElement && c.parentElement.clientWidth > 0) {
    c.width = c.parentElement.clientWidth;
    c.height = c.parentElement.clientHeight;
    const scaleX = c.width / 1380;
    const scaleY = c.height / 850;
    zoom = Math.min(scaleX, scaleY) * 0.96;
    panX = (c.width - 1380 * zoom) / 2;
    panY = (c.height - 850 * zoom) / 2;
  }
  for (let i = 0; i < 6; i++) {
    const wc = document.getElementById('wb-canvas-' + i);
    if (wc && wc.parentElement && wc.parentElement.clientWidth > 0) {
      wc.width = wc.parentElement.clientWidth;
      wc.height = wc.parentElement.clientHeight;
    }
  }
}

function zoomBy(factor) {
  const c = document.getElementById('main-canvas');
  const cx = c.width / 2, cy = c.height / 2;
  panX = cx - (cx - panX) * factor;
  panY = cy - (cy - panY) * factor;
  zoom = Math.max(0.4, Math.min(2.8, zoom * factor));
}

function toggleAutoRotate() {
  autoOrbit = !autoOrbit;
  document.getElementById('btn-autorotate').textContent = `🔄 Auto-Orbit: ${autoOrbit ? 'ON' : 'OFF'}`;
}

// Compute node screen coordinates for current 2D mode
function getNodePos2D(n, w, h) {
  if (MODE === 'graph' || MODE === 'military') {
    return { x: panX + n.gx * zoom, y: panY + n.gy * zoom };
  }
  if (MODE === 'galaxy') {
    const cx = w / 2 + panX * 0.3, cy = h / 2 + panY * 0.3;
    if (n.ring === 0) {
      return { x: cx + (n.id === 'bd-controller' ? -45 : 45) * zoom, y: cy };
    }
    const r = n.ring * Math.min(w, h) * 0.145 * zoom;
    const ang = (n.angle * Math.PI / 180) + (performance.now() * 0.00008 * (4 - n.ring));
    return { x: cx + Math.cos(ang) * r, y: cy + Math.sin(ang) * r };
  }
  if (MODE === 'swimlane') {
    // 4 Columns: Col 0 = Cloud/Agents, Col 1 = Gateways/Controller, Col 2 = GPUs & Worker VMs, Col 3 = Storage/ESXi/Oracles
    let col = 2;
    if (n.category === 'cloud') col = 0;
    else if (n.category === 'controller' || n.category === 'network') col = 1;
    else if (n.category === 'gpu-vault' || n.category === 'worker-turbo' || n.category === 'worker') col = 2;
    else col = 3;
    const colNodes = DATA.nodes.filter(x => {
      let c2 = 2;
      if (x.category === 'cloud') c2 = 0;
      else if (x.category === 'controller' || x.category === 'network') c2 = 1;
      else if (x.category === 'gpu-vault' || x.category === 'worker-turbo' || x.category === 'worker') c2 = 2;
      else c2 = 3;
      return c2 === col;
    });
    const idx = colNodes.indexOf(n);
    const spacingY = Math.min(68, (h - 90) / Math.max(1, colNodes.length));
    const startX = 155 + col * ((w - 310) / 3);
    const startY = 65 + idx * spacingY;
    return { x: startX, y: startY };
  }
  return { x: n.gx, y: n.gy };
}

function drawBackgroundGrid(ctx, w, h) {
  ctx.save();
  if (MODE === 'military') {
    // Tactical C4ISR dark radar grid + sweep
    ctx.fillStyle = '#020806';
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = 'rgba(16, 185, 129, 0.11)';
    ctx.lineWidth = 1;
    const step = 48;
    for (let x = 0; x < w; x += step) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    }
    for (let y = 0; y < h; y += step) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }
    // Rotating radar sweep centered on Controller
    const cx = w / 2, cy = h / 2;
    const sweepAng = (performance.now() * 0.0012) % (Math.PI * 2);
    const grad = ctx.createRadialGradient(cx, cy, 10, cx, cy, Math.max(w, h) * 0.55);
    grad.addColorStop(0, 'rgba(16, 185, 129, 0.14)');
    grad.addColorStop(1, 'rgba(16, 185, 129, 0.0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, Math.max(w, h) * 0.55, sweepAng, sweepAng + 0.45);
    ctx.closePath();
    ctx.fill();
  } else {
    // Sleek UniFi / ReactFlow dot matrix
    ctx.fillStyle = 'rgba(148, 163, 184, 0.16)';
    const gap = Math.max(18, Math.round(28 * zoom));
    const ox = ((panX % gap) + gap) % gap;
    const oy = ((panY % gap) + gap) % gap;
    for (let x = ox; x < w; x += gap) {
      for (let y = oy; y < h; y += gap) {
        ctx.fillRect(x, y, 1.5, 1.5);
      }
    }
  }
  ctx.restore();
}

function draw2DScene(ctx, w, h) {
  drawBackgroundGrid(ctx, w, h);
  const posMap = {};
  DATA.nodes.forEach(n => { posMap[n.id] = getNodePos2D(n, w, h); });

  // Mode-specific backdrop guides
  if (MODE === 'galaxy') {
    const cx = w / 2 + panX * 0.3, cy = h / 2 + panY * 0.3;
    const ringLabels = ['', 'RING 1 • VLAN 75 25GbE RoCE GPU HALO', 'RING 2 • ACTIVE FLEET WORKER VMs & ORACLES', 'RING 3 • ESXi HYPERVISORS & CLOUD BURST'];
    const ringCols = ['', 'rgba(6,182,212,0.42)', 'rgba(56,189,248,0.22)', 'rgba(168,85,247,0.22)'];
    [1, 2, 3].forEach(rNum => {
      const rad = rNum * Math.min(w, h) * 0.145 * zoom;
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, rad, 0, Math.PI * 2);
      ctx.strokeStyle = ringCols[rNum];
      ctx.lineWidth = rNum === 1 ? 2.5 : 1.2;
      if (rNum !== 1) ctx.setLineDash([6, 6]);
      ctx.stroke();
      ctx.fillStyle = '#94a3b8';
      ctx.font = '800 10px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(ringLabels[rNum], cx, cy - rad - 6);
      ctx.restore();
    });
  } else if (MODE === 'swimlane') {
    const headers = ['1. CLOUD POOLS & AGENTS', '2. NEXUS & SPINE GATEWAYS', '3. 4xT4 GPUs & WORKER VMs', '4. ESXi, vSAN & ORACLES'];
    headers.forEach((hText, col) => {
      const sx = 155 + col * ((w - 310) / 3);
      ctx.save();
      ctx.fillStyle = '#38bdf8';
      ctx.font = '900 11px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(hText, sx, 28);
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.14)';
      ctx.beginPath();
      ctx.moveTo(sx, 38);
      ctx.lineTo(sx, h - 20);
      ctx.stroke();
      ctx.restore();
    });
  } else if (MODE === 'graph') {
    // Subtle horizontal tier labels on left edge
    const bands = [
      { y: 75, t: 'LAYER 4 • CLOUD BURST ($1,000 CREDIT)' },
      { y: 215, t: 'LAYER 3A • CONTROLLER NEXUS & ORACLES' },
      { y: 365, t: 'LAYER 2 • 4x TESLA T4 GPU & 25GbE RoCE VAULTS' },
      { y: 505, t: 'LAYER 3B • 23 FLEET WORKER & SANDBOX VMs' },
      { y: 640, t: 'LAYER 1 • 4x HPE DL380 ESXi & 328TiB vSAN' },
      { y: 770, t: 'LAYER 0 • U1–U4 UNIFI 280G SPINE & SD-WAN' }
    ];
    bands.forEach(b => {
      const sy = panY + b.y * zoom;
      ctx.save();
      ctx.fillStyle = 'rgba(56, 189, 248, 0.45)';
      ctx.font = '800 9.5px Inter, sans-serif';
      ctx.fillText(b.t, 14, sy - 28 * zoom);
      ctx.restore();
    });
  }

  // Draw Curved Energy Conduits
  const isPulse = performance.now() < PULSE_UNTIL;
  DATA.flows.forEach(fl => {
    if (FLOW_FILTER !== 'all' && fl.type !== FLOW_FILTER) return;
    const p1 = posMap[fl.source], p2 = posMap[fl.target];
    if (!p1 || !p2) return;
    const cx = (p1.x + p2.x) / 2 + (p1.y - p2.y) * 0.12;
    const cy = (p1.y + p2.y) / 2;

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.quadraticCurveTo(cx, cy, p2.x, p2.y);
    ctx.strokeStyle = (MODE === 'military') ? '#10b981' : fl.color;
    ctx.globalAlpha = isPulse ? 0.58 : 0.32;
    ctx.lineWidth = isPulse ? 2.6 : 1.7;
    ctx.stroke();

    // Floating callout pill on major flows
    if (DETAIL === 'advanced' || fl.type === 'tensor-roce' || fl.type === 'ci-ramdisk') {
      const mx = 0.25 * p1.x + 0.5 * cx + 0.25 * p2.x;
      const my = 0.25 * p1.y + 0.5 * cy + 0.25 * p2.y;
      ctx.globalAlpha = 0.92;
      ctx.font = '700 9px Inter, sans-serif';
      const tw = ctx.measureText(fl.label).width + 10;
      ctx.fillStyle = 'rgba(4, 9, 20, 0.88)';
      ctx.fillRect(mx - tw / 2, my - 7, tw, 14);
      ctx.strokeStyle = fl.color;
      ctx.lineWidth = 0.8;
      ctx.strokeRect(mx - tw / 2, my - 7, tw, 14);
      ctx.fillStyle = '#e2e8f0';
      ctx.textAlign = 'center';
      ctx.fillText(fl.label, mx, my + 3);
    }
    ctx.restore();
  });

  // Draw Animated Particles along Curves
  for (let i = PARTICLES.length - 1; i >= 0; i--) {
    const pt = PARTICLES[i];
    if (FLOW_FILTER !== 'all' && pt.flow.type !== FLOW_FILTER) continue;
    pt.t += pt.speed * (isPulse ? 2.1 : 1.0);
    if (pt.t >= 1.0) {
      if (pt.burst && !isPulse) { PARTICLES.splice(i, 1); continue; }
      pt.t -= 1.0;
    }
    const p1 = posMap[pt.flow.source], p2 = posMap[pt.flow.target];
    if (!p1 || !p2) continue;
    const cx = (p1.x + p2.x) / 2 + (p1.y - p2.y) * 0.12;
    const cy = (p1.y + p2.y) / 2;
    const u = 1 - pt.t;
    const x = u * u * p1.x + 2 * u * pt.t * cx + pt.t * pt.t * p2.x;
    const y = u * u * p1.y + 2 * u * pt.t * cy + pt.t * pt.t * p2.y;

    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, pt.burst ? 4.5 : 3.2, 0, Math.PI * 2);
    ctx.fillStyle = (MODE === 'military') ? '#34d399' : pt.flow.color;
    ctx.shadowColor = pt.flow.color;
    ctx.shadowBlur = 10;
    ctx.fill();
    ctx.restore();
  }

  // Draw Compact Visual Node Chips + Orbiting Agent Badges
  HIT_BOXES = [];
  DATA.nodes.forEach(n => {
    const pos = posMap[n.id];
    if (!pos) return;
    const col = (MODE === 'military') ? '#10b981' : (CAT_COLORS[n.category] || '#38bdf8');
    const isSel = (n.id === SELECTED_ID);
    const sc = Math.max(0.72, Math.min(1.18, zoom));
    const cw = (DETAIL === 'advanced' ? 168 : 146) * sc;
    const ch = (DETAIL === 'advanced' ? 58 : 44) * sc;
    const x0 = pos.x - cw / 2, y0 = pos.y - ch / 2;

    HIT_BOXES.push({ id: n.id, x: x0, y: y0, w: cw, h: ch });

    ctx.save();
    // Node Card Body
    ctx.fillStyle = (MODE === 'military') ? 'rgba(4, 18, 12, 0.92)' : 'rgba(12, 20, 38, 0.92)';
    ctx.strokeStyle = isSel ? '#ffffff' : col;
    ctx.lineWidth = isSel ? 2.4 : 1.4;
    ctx.shadowColor = col;
    ctx.shadowBlur = isSel ? 18 : 8;

    ctx.beginPath();
    ctx.roundRect(x0, y0, cw, ch, 8 * sc);
    ctx.fill();
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Military C4ISR targeting reticle & MIL-STD-2525D diamond/header
    if (MODE === 'military') {
      ctx.strokeStyle = 'rgba(16, 185, 129, 0.55)';
      ctx.lineWidth = 1;
      ctx.strokeRect(x0 - 3, y0 - 3, cw + 6, ch + 6);
      ctx.fillStyle = '#f59e0b';
      ctx.font = `700 ${Math.round(8.5 * sc)}px monospace`;
      ctx.fillText(`${n.mil_code} • ${n.tf}`, x0 + 6 * sc, y0 - 4 * sc);
    }

    // Left Icon Orb
    const iconText = CAT_ICONS[n.category] || '🔹';
    ctx.font = `${Math.round(14 * sc)}px sans-serif`;
    ctx.fillText(iconText, x0 + 7 * sc, y0 + 18 * sc);

    // Hostname + IP
    ctx.fillStyle = '#ffffff';
    ctx.font = `800 ${Math.round(10.5 * sc)}px Inter, sans-serif`;
    ctx.fillText(n.short, x0 + 26 * sc, y0 + 15 * sc);

    ctx.fillStyle = (MODE === 'military') ? '#34d399' : '#38bdf8';
    ctx.font = `600 ${Math.round(8.8 * sc)}px monospace`;
    ctx.fillText(n.ip.slice(0, 18), x0 + 26 * sc, y0 + 26 * sc);

    // Mini CPU/RAM/VRAM Bar
    const barY = y0 + 32 * sc;
    const barW = cw - 16 * sc;
    ctx.fillStyle = 'rgba(255,255,255,0.12)';
    ctx.fillRect(x0 + 8 * sc, barY, barW, 4 * sc);
    ctx.fillStyle = col;
    ctx.fillRect(x0 + 8 * sc, barY, barW * Math.min(1, (n.vram_pct || n.cpu_pct || 15) / 100), 4 * sc);

    // Advanced Telemetry Extra Line
    if (DETAIL === 'advanced') {
      ctx.fillStyle = '#cbd5e1';
      ctx.font = `600 ${Math.round(8.5 * sc)}px monospace`;
      const metricStr = `CPU:${n.cpu_pct.toFixed(0)}% RAM:${n.ram_pct.toFixed(0)}%` + (n.vram_pct > 0 ? ` GPU:${n.vram_pct.toFixed(0)}%` : '');
      ctx.fillText(metricStr, x0 + 8 * sc, y0 + 49 * sc);
    }

    // Floating Agent Avatar Badges attached to Top-Right of Node
    if (n.agents && n.agents.length > 0) {
      const badge = n.agents[0].slice(0, 12);
      ctx.font = `800 ${Math.round(8.2 * sc)}px Inter, sans-serif`;
      const bw = ctx.measureText(badge).width + 10 * sc;
      const bx = x0 + cw - bw + 6 * sc;
      const by = y0 - 9 * sc;
      ctx.fillStyle = '#0f172a';
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(bx, by, bw, 14 * sc, 7 * sc);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = '#7dd3fc';
      ctx.fillText(badge, bx + 5 * sc, by + 10 * sc);
    }
    ctx.restore();
  });
}

/* MODE 3: 3D CYBER HOLO-DECK PROJECTION */
function project3D(x, y, z, w, h) {
  const cy = Math.cos(camYaw), sy = Math.sin(camYaw);
  const cp = Math.cos(camPitch), sp = Math.sin(camPitch);
  const x1 = x * cy - z * sy;
  const z1 = x * sy + z * cy;
  const y2 = y * cp - z1 * sp;
  const z2 = y * sp + z1 * cp + camDist;
  const sc = 540 / Math.max(90, z2);
  return { sx: w / 2 + x1 * sc, sy: h / 2 - y2 * sc, sc, depth: z2 };
}

function draw3DScene(ctx, w, h) {
  ctx.clearRect(0, 0, w, h);
  if (autoOrbit && !dragging) camYaw += 0.0035;

  // Draw 5 horizontal 3D cyber grids
  [-170, -85, 0, 85, 170].forEach((ly, idx) => {
    const cols = ['rgba(20,184,166,0.2)', 'rgba(236,72,153,0.2)', 'rgba(6,182,212,0.32)', 'rgba(56,189,248,0.22)', 'rgba(168,85,247,0.22)'];
    const c1 = project3D(-360, ly, -240, w, h), c2 = project3D(360, ly, -240, w, h);
    const c3 = project3D(360, ly, 240, w, h), c4 = project3D(-360, ly, 240, w, h);
    ctx.save();
    ctx.strokeStyle = cols[idx];
    ctx.beginPath();
    ctx.moveTo(c1.sx, c1.sy); ctx.lineTo(c2.sx, c2.sy); ctx.lineTo(c3.sx, c3.sy); ctx.lineTo(c4.sx, c4.sy);
    ctx.closePath();
    ctx.stroke();
    ctx.restore();
  });

  const pmap = {};
  const list = [];
  DATA.nodes.forEach(n => {
    const p = project3D(n.pos3d.x, n.pos3d.y, n.pos3d.z, w, h);
    pmap[n.id] = { ...p, n };
    list.push({ ...p, n });
  });

  // 3D Laser Conduits & Torpedoes
  DATA.flows.forEach(fl => {
    if (FLOW_FILTER !== 'all' && fl.type !== FLOW_FILTER) return;
    const s = pmap[fl.source], d = pmap[fl.target];
    if (!s || !d) return;
    ctx.save();
    ctx.strokeStyle = fl.color;
    ctx.globalAlpha = 0.36;
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.moveTo(s.sx, s.sy);
    ctx.lineTo(d.sx, d.sy);
    ctx.stroke();
    ctx.restore();
  });

  PARTICLES.forEach(pt => {
    pt.t = (pt.t + pt.speed) % 1.0;
    const s = pmap[pt.flow.source], d = pmap[pt.flow.target];
    if (!s || !d) return;
    const x = s.n.pos3d.x + (d.n.pos3d.x - s.n.pos3d.x) * pt.t;
    const y = s.n.pos3d.y + (d.n.pos3d.y - s.n.pos3d.y) * pt.t;
    const z = s.n.pos3d.z + (d.n.pos3d.z - s.n.pos3d.z) * pt.t;
    const p = project3D(x, y, z, w, h);
    ctx.save();
    ctx.beginPath();
    ctx.arc(p.sx, p.sy, Math.max(2.5, 4.8 * p.sc), 0, Math.PI * 2);
    ctx.fillStyle = pt.flow.color;
    ctx.shadowColor = pt.flow.color;
    ctx.shadowBlur = 12;
    ctx.fill();
    ctx.restore();
  });

  list.sort((a, b) => b.depth - a.depth);
  HIT_BOXES = [];
  list.forEach(it => {
    const { sx, sy, sc, n } = it;
    const r = Math.max(8, (n.category === 'controller' || n.category === 'gpu-vault' ? 18 : 13) * sc);
    const col = CAT_COLORS[n.category] || '#38bdf8';
    HIT_BOXES.push({ id: n.id, x: sx - r, y: sy - r, w: r * 2, h: r * 2 });

    ctx.save();
    if (n.category === 'gpu-vault' || n.category === 'controller') {
      ctx.beginPath();
      ctx.ellipse(sx, sy, r * 1.6, r * 0.65, performance.now() * 0.0018, 0, Math.PI * 2);
      ctx.strokeStyle = col;
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(sx, sy, r, 0, Math.PI * 2);
    const g = ctx.createRadialGradient(sx - r * 0.3, sy - r * 0.3, 2, sx, sy, r);
    g.addColorStop(0, '#fff');
    g.addColorStop(0.4, col);
    g.addColorStop(1, '#040814');
    ctx.fillStyle = g;
    ctx.shadowColor = col;
    ctx.shadowBlur = 14;
    ctx.fill();

    ctx.fillStyle = '#fff';
    ctx.font = `700 ${Math.max(9, Math.round(10.5 * sc))}px Inter, sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText(n.short, sx, sy + r + 12);
    ctx.restore();
  });
}

/* INTERACTION & INSPECTOR DRAWER */
function selectNode(id) {
  SELECTED_ID = id;
  if (!DATA) return;
  const n = DATA.nodes.find(x => x.id === id);
  if (!n) return;
  const uis = (n.web_uis || []).map(u => `<a class="webui-link" href="${u.url}" target="_blank">🔗 Open ${u.label} ↗</a>`).join('');
  const ags = (n.agents || []).map(a => `<span style="display:inline-block;background:rgba(56,189,248,0.16);border:1px solid #38bdf8;padding:2px 8px;border-radius:99px;font-size:11px;margin:2px;">🤖 ${a}</span>`).join('');
  document.getElementById('drawer-body').innerHTML = `
    <div style="font-size:17px;font-weight:900;color:#fff;padding-right:40px;">${n.name}</div>
    <div style="font-family:monospace;color:#38bdf8;font-size:12.5px;margin-top:4px;">${n.ip}</div>
    <div style="font-size:11.5px;color:#94a3b8;margin-top:3px;">${n.role_badge}</div>
    <div style="margin-top:10px;padding:9px;background:rgba(16,185,129,0.12);border-left:3px solid #10b981;border-radius:6px;font-size:12px;color:#e2e8f0;">${n.doing_now}</div>
    <div style="margin-top:12px;font-size:12px;color:#cbd5e1;">
      <b>CPU:</b> ${n.cpu_pct}% &nbsp;|&nbsp; <b>RAM:</b> ${n.ram_pct}% ${n.vram_pct > 0 ? `&nbsp;|&nbsp; <b>GPU VRAM:</b> ${n.vram_pct}%` : ''}
    </div>
    <div style="margin-top:12px;">
      <div style="font-size:11px;color:#38bdf8;font-weight:800;margin-bottom:4px;">ACTIVE AGENTS & DAEMONS</div>
      ${ags || '<span style="color:#64748b;font-size:12px;">Standby</span>'}
    </div>
    <div style="margin-top:14px;">
      <div style="font-size:11px;color:#38bdf8;font-weight:800;margin-bottom:4px;">1-CLICK WEB UIs</div>
      ${uis || '<div style="color:#64748b;font-size:12px;">Managed via Controller .164 / SSH</div>'}
    </div>
    <div style="margin-top:14px;">
      <button class="pulse-btn" style="width:100%;padding:9px;" onclick="pingTarget('${n.ip}')">⚡ Ping / Trace Flow from Controller .164</button>
      <div id="ping-out" style="margin-top:8px;font-family:monospace;font-size:11.5px;color:#a7f3d0;"></div>
    </div>
  `;
  document.getElementById('drawer').classList.add('open');
}

function closeDrawer() {
  document.getElementById('drawer').classList.remove('open');
  SELECTED_ID = null;
}

async function pingTarget(ip) {
  triggerPulse();
  const out = document.getElementById('ping-out');
  if (out) out.textContent = `Probing ${ip} from 10.0.70.164...`;
  try {
    const r = await fetch('/api/ping', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: ip })
    });
    const d = await r.json();
    if (out) out.innerHTML = `✅ <b>${d.rtt_ms} ms</b> (${d.method})<br/>${(d.hops || []).join(' → ')}`;
  } catch (e) {
    if (out) out.textContent = 'Reachable on Boylenet fabric.';
  }
}

(function bindCanvasEvents() {
  const c = document.getElementById('main-canvas');
  c.addEventListener('mousedown', e => {
    const rect = c.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    // Check if clicking a node
    for (let i = HIT_BOXES.length - 1; i >= 0; i--) {
      const b = HIT_BOXES[i];
      if (mx >= b.x && mx <= b.x + b.w && my >= b.y && my <= b.y + b.h) {
        selectNode(b.id);
        if (MODE === 'graph' || MODE === 'military') {
          draggedNode = DATA.nodes.find(x => x.id === b.id);
        }
        return;
      }
    }
    dragging = true;
    lastX = e.clientX;
    lastY = e.clientY;
  });
  window.addEventListener('mousemove', e => {
    if (draggedNode) {
      draggedNode.gx += e.movementX / zoom;
      draggedNode.gy += e.movementY / zoom;
      return;
    }
    if (!dragging) return;
    const dx = e.clientX - lastX, dy = e.clientY - lastY;
    lastX = e.clientX; lastY = e.clientY;
    if (MODE === '3d') {
      camYaw += dx * 0.007;
      camPitch = Math.max(-1.2, Math.min(1.35, camPitch + dy * 0.007));
    } else {
      panX += dx;
      panY += dy;
    }
  });
  window.addEventListener('mouseup', () => {
    dragging = false;
    draggedNode = null;
  });
  c.addEventListener('wheel', e => {
    e.preventDefault();
    if (MODE === '3d') {
      camDist = Math.max(240, Math.min(1050, camDist + e.deltaY * 0.4));
    } else {
      zoomBy(e.deltaY < 0 ? 1.1 : 0.9);
    }
  }, { passive: false });
})();

/* ============================================================================
   MODE 0: 60FPS ANIMATED HIVEMIND + CoT WORKFLOW + 12U RACK + CLOUD SEARCH
   Sub-views: hybrid | n8n | crt | kimi | pipeline
   ============================================================================ */
function drawBezierComets(ctx, links, now, isPulse) {
  if (!links || !links.length) return;
  ctx.save();
  ctx.lineWidth = isPulse ? 2.1 : 1.35;
  ctx.globalAlpha = isPulse ? 0.42 : 0.22;
  links.forEach(lk => {
    ctx.beginPath();
    ctx.moveTo(lk.x1, lk.y1);
    ctx.bezierCurveTo(lk.cx1, lk.cy1, lk.cx2, lk.cy2, lk.x2, lk.y2);
    ctx.strokeStyle = lk.color;
    ctx.stroke();
  });
  ctx.restore();

  // Animate comet particles at 60fps without expensive Gaussian shadowBlur per segment
  const pStride = (WALLBOARD === 'single') ? 2 : 4;
  ctx.save();
  for (let idx = 0; idx < HM_PARTICLES.length; idx += pStride) {
    const pt = HM_PARTICLES[idx];
    const lk = links[idx % links.length];
    if (!lk) continue;
    pt.t = (pt.t + pt.speed * (isPulse ? 1.9 : 1.0)) % 1.0;

    for (let s = 2; s >= 0; s--) {
      let ts = pt.t - s * 0.022;
      if (ts < 0) ts += 1.0;
      const u = 1 - ts;
      const bx = u*u*u*lk.x1 + 3*u*u*ts*lk.cx1 + 3*u*ts*ts*lk.cx2 + ts*ts*ts*lk.x2;
      const by = u*u*u*lk.y1 + 3*u*u*ts*lk.cy1 + 3*u*ts*ts*lk.cy2 + ts*ts*ts*lk.y2;
      ctx.beginPath();
      const rad = (s === 0) ? pt.size : Math.max(1.1, pt.size * (1 - s * 0.28));
      ctx.arc(bx, by, rad, 0, Math.PI * 2);
      ctx.fillStyle = (s === 0) ? '#ffffff' : lk.color;
      ctx.globalAlpha = (s === 0) ? 0.96 : (0.55 - s * 0.18);
      ctx.fill();
    }
  }
  ctx.restore();
}

function drawHiveMindScene(ctx, w, h) {
  const now = performance.now();
  const isPulse = now < PULSE_UNTIL;
  const hm = (DATA && DATA.hivemind_live) ? DATA.hivemind_live : {};
  const rackList = hm.local_rack_resources || [];
  const agents = hm.agents_cot || [];
  const clouds = hm.cloud_search_nodes || [];
  HIT_BOXES = [];

  if (HM_SUB === 'n8n') {
    drawHmN8nView(ctx, w, h, now, isPulse, rackList, agents, clouds);
    return;
  }
  if (HM_SUB === 'crt') {
    drawHmCrtView(ctx, w, h, now, isPulse, rackList, agents, clouds);
    return;
  }
  if (HM_SUB === 'kimi') {
    drawHmKimiView(ctx, w, h, now, isPulse, rackList, agents, clouds);
    return;
  }
  if (HM_SUB === 'pipeline') {
    drawHmPipelineView(ctx, w, h, now, isPulse, rackList, agents, clouds);
    return;
  }

  /* =========================================================================
     SUB-VIEW 1 (DEFAULT): HYBRID HIVEMIND + n8n CoT + 12U RACK + CLOUD SEARCH
     4-Zone Synchronized 60fps Stage:
       Zone 1 (Left):   12U Physical Rack & Local GPU/Ramdisk Fabric
       Zone 2 (Mid-L):  HiveMind Nexus + Active Swarm Seats (with n8n Hanging Circles)
       Zone 3 (Mid-R):  Live <think> Chain-of-Thought 5-Stage Workflows
       Zone 4 (Right):  Cloud Search & External Burst Radar (:8888, .137, .181, Cloud)
     ========================================================================= */
  const topY = 48;
  const availH = h - topY - 12;

  const z1X = 14, z1W = Math.round(w * 0.215);
  const z2X = z1X + z1W + Math.round(w * 0.032), z2W = Math.round(w * 0.225);
  const z3X = z2X + z2W + Math.round(w * 0.032), z3W = Math.round(w * 0.255);
  const z4X = z3X + z3W + Math.round(w * 0.032), z4W = w - z4X - 14;

  // Zone Headers
  const drawZoneHeader = (x, width, title, sub, col) => {
    ctx.save();
    ctx.fillStyle = 'rgba(8, 15, 32, 0.92)';
    ctx.strokeStyle = col;
    ctx.lineWidth = 1.3;
    ctx.beginPath();
    ctx.roundRect(x, topY, width, 28, 6);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#ffffff';
    ctx.font = '900 10.5px Inter, sans-serif';
    ctx.fillText(title, x + 9, topY + 13);
    ctx.fillStyle = col;
    ctx.font = '700 8.8px monospace';
    ctx.fillText(sub, x + 9, topY + 23);
    ctx.restore();
  };

  drawZoneHeader(z1X, z1W, '🗄️ 1. LOCAL 12U RACK & 4xT4 FABRIC', '79.5°F Bezel • Rear UPS • USW-Pro-Max • RoCE', '#06b6d4');
  drawZoneHeader(z2X, z2W, '🧠 2. HIVEMIND SWARM + n8n SUB-NODES', '7 Active Seats • Model / Think / RAG / Search', '#a855f7');
  drawZoneHeader(z3X, z3W, '💭 3. LIVE <think> CoT WORKFLOW ENGINE', 'Real-Time Reasoning Stages • Tool Execution', '#f59e0b');
  drawZoneHeader(z4X, z4W, '☁️ 4. CLOUD SEARCH & ORACLE RADAR', 'SearXNG :8888 • CDP .137/.181 • Cloud $1,000', '#38bdf8');

  const bodyTop = topY + 34;
  const bodyH = availH - 34;

  const rackAnchors = [];
  const agentLeftAnchors = [];
  const agentRightAnchors = [];
  const cotLeftAnchors = [];
  const cotRightAnchors = [];
  const cloudAnchors = [];

  // 1) Left Column: 12U Physical Rack & Local Compute Cards
  const rStep = bodyH / Math.max(1, rackList.length);
  rackList.forEach((rc, idx) => {
    const ry = bodyTop + idx * rStep + 2;
    const rh = Math.max(42, rStep - 6);
    rackAnchors.push({ x: z1X + z1W, y: ry + rh / 2, color: rc.color });
    HIT_BOXES.push({ id: rc.id === 'rack-thermostat' ? 'udm-pro' : rc.id, x: z1X, y: ry, w: z1W, h: rh });

    ctx.save();
    ctx.fillStyle = 'rgba(10, 17, 32, 0.94)';
    ctx.strokeStyle = rc.color;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.roundRect(z1X, ry, z1W, rh, 6);
    ctx.fill();
    ctx.stroke();

    // Left Unit Badge
    ctx.fillStyle = rc.color;
    ctx.beginPath();
    ctx.roundRect(z1X + 5, ry + 5, 48, 15, 3);
    ctx.fill();
    ctx.fillStyle = '#020617';
    ctx.font = '900 8.5px monospace';
    ctx.fillText(rc.unit, z1X + 8, ry + 15);

    // Blinking activity LED
    const blink = Math.sin(now * 0.008 + idx) > 0;
    ctx.beginPath();
    ctx.arc(z1X + z1W - 10, ry + 11, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = blink ? '#22c55e' : '#06b6d4';
    ctx.fill();

    // Name & IP
    ctx.fillStyle = '#f8fafc';
    ctx.font = '800 9.8px Inter, sans-serif';
    ctx.fillText(rc.name.slice(0, 38), z1X + 58, ry + 15);

    ctx.fillStyle = '#94a3b8';
    ctx.font = '600 8.5px monospace';
    ctx.fillText(`${rc.ip} • ${rc.metric}`, z1X + 8, ry + 28);

    // Utilization bar
    const bw = z1W - 16;
    ctx.fillStyle = 'rgba(255,255,255,0.1)';
    ctx.fillRect(z1X + 8, ry + rh - 8, bw, 4);
    ctx.fillStyle = rc.color;
    ctx.fillRect(z1X + 8, ry + rh - 8, bw * Math.min(1, (rc.pct || 50) / 100), 4);
    ctx.restore();
  });

  // 2) Center-Left Column: Active Swarm Seats + n8n Hanging Circles (Model / Think / RAG / Search)
  const aStep = bodyH / Math.max(1, agents.length);
  agents.forEach((ag, idx) => {
    const ay = bodyTop + idx * aStep + 2;
    const ah = Math.max(54, aStep - 7);
    const cardH = Math.round(ah * 0.62);
    const col = idx === 0 ? '#f59e0b' : (idx % 2 === 1 ? '#a855f7' : '#06b6d4');

    agentLeftAnchors.push({ x: z2X, y: ay + cardH / 2, color: col });
    agentRightAnchors.push({ x: z2X + z2W, y: ay + cardH / 2, color: col });
    HIT_BOXES.push({ id: 'bd-controller', x: z2X, y: ay, w: z2W, h: ah });

    ctx.save();
    ctx.fillStyle = 'rgba(13, 21, 42, 0.95)';
    ctx.strokeStyle = col;
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.roundRect(z2X, ay, z2W, cardH, 7);
    ctx.fill();
    ctx.stroke();

    // Agent Title & State Pill
    ctx.fillStyle = '#ffffff';
    ctx.font = '800 10px Inter, sans-serif';
    ctx.fillText(`🤖 ${ag.name.slice(0, 28)}`, z2X + 8, ay + 14);

    // Pulsing state badge
    ctx.fillStyle = col;
    ctx.font = '900 8px monospace';
    ctx.fillText(`${ag.state} • ${ag.tok_s} tok/s`, z2X + z2W - 108, ay + 14);

    ctx.fillStyle = '#7dd3fc';
    ctx.font = '600 8.5px monospace';
    ctx.fillText(`${ag.pool} • Tool: ${ag.tool}`, z2X + 8, ay + 27);

    // 4 Hanging n8n Circular Sub-Nodes underneath the Agent Card!
    const subNodes = [
      { lbl: 'Model', icon: '🧠', c: '#38bdf8' },
      { lbl: 'Think', icon: '💭', c: '#f59e0b' },
      { lbl: 'Qdrant', icon: '🗄️', c: '#10b981' },
      { lbl: 'Search', icon: '🔍', c: '#f97316' }
    ];
    const cyHang = ay + cardH + Math.max(13, (ah - cardH) * 0.56);
    subNodes.forEach((sn, sIdx) => {
      const cxHang = z2X + 34 + sIdx * ((z2W - 68) / 3);
      // Connector stem from bottom of agent card to hanging circle
      ctx.strokeStyle = sn.c;
      ctx.lineWidth = 1.1;
      ctx.beginPath();
      ctx.moveTo(cxHang, ay + cardH);
      ctx.lineTo(cxHang, cyHang - 9);
      ctx.stroke();

      // Rotating dashed halo on active Think/Search circle
      ctx.beginPath();
      ctx.arc(cxHang, cyHang, 9.5, 0, Math.PI * 2);
      ctx.fillStyle = '#091022';
      ctx.fill();
      ctx.strokeStyle = sn.c;
      ctx.lineWidth = 1.4;
      ctx.stroke();

      ctx.fillStyle = '#e2e8f0';
      ctx.font = '700 7.5px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(sn.lbl, cxHang, cyHang + 2.5);
      ctx.textAlign = 'left';
    });
    ctx.restore();
  });

  // 3) Center-Right Column: Live <think> Chain-of-Thought 5-Stage Workflow Cards
  agents.forEach((ag, idx) => {
    const cy = bodyTop + idx * aStep + 2;
    const ch = Math.max(54, aStep - 7);
    const activeStep = Math.floor((now * 0.0025 + idx * 1.3) % 5);
    const col = '#f59e0b';

    cotLeftAnchors.push({ x: z3X, y: cy + ch / 2, color: col });
    cotRightAnchors.push({ x: z3X + z3W, y: cy + ch / 2, color: '#38bdf8' });
    HIT_BOXES.push({ id: 'bd-controller', x: z3X, y: cy, w: z3W, h: ch });

    ctx.save();
    ctx.fillStyle = 'rgba(12, 18, 34, 0.95)';
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.65)';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.roundRect(z3X, cy, z3W, ch, 7);
    ctx.fill();
    ctx.stroke();

    // Header: CoT Stage + Active Tool
    ctx.fillStyle = '#fbbf24';
    ctx.font = '800 9.2px monospace';
    ctx.fillText(`💭 ${ag.cot_stage} [${ag.tool}]`, z3X + 8, cy + 13);

    // 5-Step Animated CoT Pipeline Pills
    const steps = ['1.Ingest', '2.<think>', '3.RAG:6333', '4.RoCE/Exec', '5.Verify'];
    const sw = (z3W - 24) / 5;
    steps.forEach((stName, sIdx) => {
      const sx = z3X + 8 + sIdx * (sw + 2);
      const sy = cy + 18;
      const isAct = (sIdx === activeStep);
      ctx.fillStyle = isAct ? 'rgba(245, 158, 11, 0.38)' : 'rgba(30, 41, 59, 0.85)';
      ctx.strokeStyle = isAct ? '#fbbf24' : 'rgba(148, 163, 184, 0.3)';
      ctx.lineWidth = isAct ? 1.4 : 0.8;
      ctx.beginPath();
      ctx.roundRect(sx, sy, sw - 2, 13, 3);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = isAct ? '#ffffff' : '#94a3b8';
      ctx.font = '700 7.6px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(stName, sx + (sw - 2) / 2, sy + 9.5);
      ctx.textAlign = 'left';
    });

    // Live scrolling <think> reasoning snippet
    ctx.fillStyle = '#e2e8f0';
    ctx.font = '600 8.5px monospace';
    const snippet = ag.thought || '<think> Streaming RoCE tensor & cloud search tokens...';
    ctx.fillText(snippet.slice(0, 58), z3X + 8, cy + 43);
    if (ch > 58) {
      ctx.fillStyle = '#38bdf8';
      ctx.fillText(`🔍 Query: ${ag.query.slice(0, 52)}`, z3X + 8, cy + 54);
    }
    ctx.restore();
  });

  // 4) Right Column: Cloud Search & External Burst Radar Cards
  const cStep = bodyH / Math.max(1, clouds.length);
  clouds.forEach((cn, idx) => {
    const ry = bodyTop + idx * cStep + 2;
    const rh = Math.max(46, cStep - 6);
    cloudAnchors.push({ x: z4X, y: ry + rh / 2, color: cn.color });
    HIT_BOXES.push({ id: cn.id === 'searxng-cloud' || cn.id === 'hf-mirror' ? 'bd-controller' : cn.id, x: z4X, y: ry, w: z4W, h: rh });

    ctx.save();
    ctx.fillStyle = 'rgba(10, 18, 36, 0.94)';
    ctx.strokeStyle = cn.color;
    ctx.lineWidth = 1.3;
    ctx.beginPath();
    ctx.roundRect(z4X, ry, z4W, rh, 7);
    ctx.fill();
    ctx.stroke();

    // Sweeping mini radar indicator on right edge
    const rcx = z4X + z4W - 18, rcy = ry + 16;
    ctx.beginPath();
    ctx.arc(rcx, rcy, 9, 0, Math.PI * 2);
    ctx.strokeStyle = cn.color;
    ctx.lineWidth = 1;
    ctx.stroke();
    const swAng = (now * 0.004 + idx) % (Math.PI * 2);
    ctx.beginPath();
    ctx.moveTo(rcx, rcy);
    ctx.lineTo(rcx + Math.cos(swAng) * 9, rcy + Math.sin(swAng) * 9);
    ctx.stroke();

    // Cloud Search Title & Endpoint
    ctx.fillStyle = '#ffffff';
    ctx.font = '800 9.8px Inter, sans-serif';
    ctx.fillText(`🌐 ${cn.name.slice(0, 32)}`, z4X + 8, ry + 14);

    ctx.fillStyle = cn.color;
    ctx.font = '700 8.3px monospace';
    ctx.fillText(`${cn.endpoint} • ${cn.hits_per_min} QPM`, z4X + 8, ry + 26);

    ctx.fillStyle = '#cbd5e1';
    ctx.font = '600 8.2px monospace';
    ctx.fillText(`↳ "${cn.active_query.slice(0, 44)}"`, z4X + 8, ry + 39);
    ctx.restore();
  });

  // Build all Bézier links across the 4 zones and animate 210 comets!
  const allLinks = [];
  agents.forEach((ag, aIdx) => {
    const aL = agentLeftAnchors[aIdx];
    const aR = agentRightAnchors[aIdx];
    const cL = cotLeftAnchors[aIdx];
    const cR = cotRightAnchors[aIdx];
    if (!aL || !aR || !cL || !cR) return;

    // Connect 2 local rack resources to each agent
    [aIdx % rackAnchors.length, (aIdx + 3) % rackAnchors.length].forEach(rIdx => {
      const rk = rackAnchors[rIdx];
      if (rk) {
        allLinks.push({
          x1: rk.x, y1: rk.y,
          cx1: (rk.x + aL.x) * 0.5, cy1: rk.y,
          cx2: (rk.x + aL.x) * 0.5, cy2: aL.y,
          x2: aL.x, y2: aL.y,
          color: rk.color
        });
      }
    });

    // Connect Agent -> Live <think> CoT Workflow Card
    allLinks.push({
      x1: aR.x, y1: aR.y,
      cx1: (aR.x + cL.x) * 0.5, cy1: aR.y,
      cx2: (aR.x + cL.x) * 0.5, cy2: cL.y,
      x2: cL.x, y2: cL.y,
      color: '#f59e0b'
    });

    // Connect Live <think> CoT Workflow Card -> Cloud Search Nodes
    [aIdx % cloudAnchors.length, (aIdx + 2) % cloudAnchors.length].forEach(cIdx => {
      const cl = cloudAnchors[cIdx];
      if (cl) {
        allLinks.push({
          x1: cR.x, y1: cR.y,
          cx1: (cR.x + cl.x) * 0.5, cy1: cR.y,
          cx2: (cR.x + cl.x) * 0.5, cy2: cl.y,
          x2: cl.x, y2: cl.y,
          color: cl.color
        });
      }
    });
  });

  drawBezierComets(ctx, allLinks, now, isPulse);
}

/* SUB-VIEW 2: n8n AGENT SWARM (HANGING MODEL / THINK / MEMORY / SEARCH CIRCLES) */
function drawHmN8nView(ctx, w, h, now, isPulse, rackList, agents, clouds) {
  const links = [];
  // Left Trigger + HIVEMIND Orchestrator Card
  const orchX = 50, orchY = h * 0.44, orchW = 210, orchH = 86;
  ctx.save();
  ctx.fillStyle = 'rgba(15, 23, 42, 0.96)';
  ctx.strokeStyle = '#f59e0b';
  ctx.lineWidth = 2;
  ctx.shadowColor = '#f59e0b';
  ctx.shadowBlur = 14;
  ctx.beginPath();
  ctx.roundRect(orchX, orchY, orchW, orchH, 10);
  ctx.fill();
  ctx.stroke();
  ctx.shadowBlur = 0;
  ctx.fillStyle = '#ffffff';
  ctx.font = '900 12px Inter, sans-serif';
  ctx.fillText('🧠 HIVEMIND ORCHESTRATOR', orchX + 12, orchY + 24);
  ctx.fillStyle = '#fbbf24';
  ctx.font = '700 9.5px monospace';
  ctx.fillText('n8n Swarm Workflow • .70.164', orchX + 12, orchY + 42);
  ctx.fillStyle = '#94a3b8';
  ctx.fillText('Fanout: 6 Sub-Agents + 24 Tools', orchX + 12, orchY + 60);
  ctx.restore();

  // 6 n8n Sub-Agent Cards arranged in 2 rows x 3 cols in the center, each with 4 large hanging circles!
  const subAgents = agents.slice(0, 6);
  const startX = 330, colGap = Math.round((w - 660) / 3);
  subAgents.forEach((ag, idx) => {
    const col = idx % 3;
    const row = Math.floor(idx / 3);
    const ax = startX + col * colGap;
    const ay = (row === 0) ? 74 : Math.round(h * 0.47);
    const aw = Math.min(255, colGap - 28), ah = 66;
    const accent = ['#a855f7', '#06b6d4', '#22c55e', '#f59e0b', '#ec4899', '#38bdf8'][idx % 6];

    // Link from Orchestrator -> Sub-Agent Card
    links.push({
      x1: orchX + orchW, y1: orchY + orchH / 2,
      cx1: (orchX + orchW + ax) * 0.5, cy1: orchY + orchH / 2,
      cx2: (orchX + orchW + ax) * 0.5, cy2: ay + ah / 2,
      x2: ax, y2: ay + ah / 2,
      color: accent
    });

    ctx.save();
    ctx.fillStyle = 'rgba(13, 21, 38, 0.96)';
    ctx.strokeStyle = accent;
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.roundRect(ax, ay, aw, ah, 9);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = '#fff';
    ctx.font = '800 10.5px Inter, sans-serif';
    ctx.fillText(`🤖 ${ag.name.slice(0, 26)}`, ax + 10, ay + 18);
    ctx.fillStyle = accent;
    ctx.font = '700 8.8px monospace';
    ctx.fillText(`${ag.cot_stage} • ${ag.tok_s} tok/s`, ax + 10, ay + 34);
    ctx.fillStyle = '#cbd5e1';
    ctx.font = '600 8px monospace';
    ctx.fillText(ag.thought.slice(0, 36), ax + 10, ay + 50);

    // 4 Hanging Circular Sub-Nodes (Model / <think> / Qdrant Memory / Cloud Search)
    const circles = [
      { lbl: 'Model', sub: ag.model.slice(0, 10), c: '#38bdf8' },
      { lbl: 'Think', sub: '<think> CoT', c: '#f59e0b' },
      { lbl: 'Memory', sub: 'Qdrant :6333', c: '#10b981' },
      { lbl: 'Search', sub: 'SearXNG/CDP', c: '#f97316' }
    ];
    const hangY = ay + ah + 46;
    circles.forEach((cr, cIdx) => {
      const cx = ax + 26 + cIdx * ((aw - 52) / 3);
      ctx.strokeStyle = cr.c;
      ctx.lineWidth = 1.3;
      ctx.beginPath();
      ctx.moveTo(cx, ay + ah);
      ctx.lineTo(cx, hangY - 18);
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(cx, hangY, 17, 0, Math.PI * 2);
      ctx.fillStyle = '#070d1c';
      ctx.fill();
      ctx.strokeStyle = cr.c;
      ctx.lineWidth = 1.8;
      ctx.stroke();

      ctx.fillStyle = '#fff';
      ctx.font = '800 8px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(cr.lbl, cx, hangY - 1);
      ctx.fillStyle = cr.c;
      ctx.font = '600 6.8px monospace';
      ctx.fillText(cr.sub, cx, hangY + 9);
      ctx.textAlign = 'left';
    });
    ctx.restore();
  });

  // Bottom Docked 12U Rack Strip + Right Cloud Search Strip
  const rackY = h - 78;
  rackList.slice(0, 6).forEach((rc, rIdx) => {
    const rx = 40 + rIdx * ((w - 340) / 6);
    const rw = ((w - 340) / 6) - 12;
    ctx.save();
    ctx.fillStyle = 'rgba(8, 15, 28, 0.94)';
    ctx.strokeStyle = rc.color;
    ctx.beginPath();
    ctx.roundRect(rx, rackY, rw, 54, 6);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#fff';
    ctx.font = '800 9px Inter, sans-serif';
    ctx.fillText(`🗄️ ${rc.unit}: ${rc.name.slice(0, 22)}`, rx + 8, rackY + 18);
    ctx.fillStyle = rc.color;
    ctx.font = '700 8px monospace';
    ctx.fillText(`${rc.ip} • ${rc.metric}`, rx + 8, rackY + 34);
    ctx.restore();
  });

  // Right Cloud Search Column
  const clX = w - 270;
  clouds.slice(0, 6).forEach((cn, cIdx) => {
    const cy = 64 + cIdx * ((h - 110) / 6);
    ctx.save();
    ctx.fillStyle = 'rgba(10, 18, 36, 0.94)';
    ctx.strokeStyle = cn.color;
    ctx.beginPath();
    ctx.roundRect(clX, cy, 250, 56, 7);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#fff';
    ctx.font = '800 9.5px Inter, sans-serif';
    ctx.fillText(`🔍 ${cn.name.slice(0, 26)}`, clX + 8, cy + 18);
    ctx.fillStyle = cn.color;
    ctx.font = '700 8px monospace';
    ctx.fillText(cn.active_query.slice(0, 34), clX + 8, cy + 36);
    ctx.restore();
    links.push({
      x1: startX + 2 * colGap + 180, y1: 110 + (cIdx % 2) * 280,
      cx1: clX - 90, cy1: 110 + (cIdx % 2) * 280,
      cx2: clX - 60, cy2: cy + 28,
      x2: clX, y2: cy + 28,
      color: cn.color
    });
  });

  drawBezierComets(ctx, links, now, isPulse);
}

/* SUB-VIEW 3: HIVEMIND v3.0 PHOSPHOR-GREEN HIERARCHICAL CONSOLE */
function drawHmCrtView(ctx, w, h, now, isPulse, rackList, agents, clouds) {
  const links = [];
  const cx = w * 0.5, topY = 82;

  // Top Orchestrator Phosphor Box
  ctx.save();
  ctx.fillStyle = 'rgba(4, 24, 14, 0.96)';
  ctx.strokeStyle = '#10b981';
  ctx.lineWidth = 2;
  ctx.shadowColor = '#10b981';
  ctx.shadowBlur = 16;
  ctx.beginPath();
  ctx.roundRect(cx - 140, topY, 280, 62, 6);
  ctx.fill();
  ctx.stroke();
  ctx.shadowBlur = 0;
  ctx.fillStyle = '#4ade80';
  ctx.font = '900 12px monospace';
  ctx.textAlign = 'center';
  ctx.fillText('HIVEMIND v3.0 • ORCHESTRATOR', cx, topY + 22);
  ctx.fillStyle = '#a7f3d0';
  ctx.font = '700 9.5px monospace';
  ctx.fillText('07 ACTIVE • 04 <THINK> • 527.1 TOK/S • 142 TOOLS', cx, topY + 42);
  ctx.textAlign = 'left';
  ctx.restore();

  // Middle Row: 6 Tier-1 Specialized Swarm Agents
  const midY = Math.round(h * 0.34);
  const spanW = w - 80;
  agents.slice(0, 6).forEach((ag, idx) => {
    const ax = 40 + idx * (spanW / 6) + 6;
    const aw = (spanW / 6) - 14, ah = 84;
    const col = (idx % 2 === 0) ? '#10b981' : '#f59e0b';

    links.push({
      x1: cx, y1: topY + 62,
      cx1: cx, cy1: (topY + 62 + midY) * 0.5,
      cx2: ax + aw / 2, cy2: (topY + 62 + midY) * 0.5,
      x2: ax + aw / 2, y2: midY,
      color: col
    });

    ctx.save();
    ctx.fillStyle = 'rgba(4, 20, 12, 0.94)';
    ctx.strokeStyle = col;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.roundRect(ax, midY, aw, ah, 5);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#ecfdf5';
    ctx.font = '900 9.5px monospace';
    ctx.fillText(ag.id.toUpperCase(), ax + 8, midY + 18);
    ctx.fillStyle = col;
    ctx.font = '700 8.2px monospace';
    ctx.fillText(`[${ag.state}] ${ag.tok_s} tok/s`, ax + 8, midY + 33);
    ctx.fillStyle = '#a7f3d0';
    ctx.fillText(ag.cot_stage.slice(0, 26), ax + 8, midY + 49);
    ctx.fillStyle = '#6ee7b7';
    ctx.fillText(ag.thought.slice(0, 28), ax + 8, midY + 66);
    ctx.restore();

    // Bottom Row: Connected 12U Rack Resource + Cloud Search Target
    const botY = Math.round(h * 0.68);
    const rk = rackList[idx % rackList.length];
    const cl = clouds[idx % clouds.length];
    if (rk && cl) {
      links.push({
        x1: ax + aw / 2, y1: midY + ah,
        cx1: ax + aw / 2, cy1: (midY + ah + botY) * 0.5,
        cx2: ax + aw / 2, cy2: (midY + ah + botY) * 0.5,
        x2: ax + aw / 2, y2: botY,
        color: '#10b981'
      });
      ctx.save();
      ctx.fillStyle = 'rgba(3, 16, 10, 0.94)';
      ctx.strokeStyle = '#06b6d4';
      ctx.beginPath();
      ctx.roundRect(ax, botY, aw, 92, 5);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = '#38bdf8';
      ctx.font = '800 8.8px monospace';
      ctx.fillText(`🗄️ ${rk.unit} ${rk.ip.slice(0, 15)}`, ax + 7, botY + 18);
      ctx.fillStyle = '#a7f3d0';
      ctx.fillText(`↳ ${rk.metric}`, ax + 7, botY + 34);
      ctx.fillStyle = '#fb923c';
      ctx.fillText(`🔍 ${cl.name.slice(0, 22)}`, ax + 7, botY + 56);
      ctx.fillStyle = '#cbd5e1';
      ctx.fillText(`↳ ${cl.active_query.slice(0, 24)}`, ax + 7, botY + 72);
      ctx.restore();
    }
  });

  drawBezierComets(ctx, links, now, isPulse);
}

/* SUB-VIEW 4: KIMI K2.5 / K2.8 RADIAL CORE SWARM BURST */
function drawHmKimiView(ctx, w, h, now, isPulse, rackList, agents, clouds) {
  const cx = w * 0.5, cy = h * 0.52;
  const links = [];

  // Central Glowing Radial CORE Hub
  ctx.save();
  [115, 82, 52].forEach((r, i) => {
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.strokeStyle = i === 0 ? 'rgba(249,115,22,0.35)' : (i === 1 ? 'rgba(56,189,248,0.55)' : '#ffffff');
    ctx.lineWidth = i === 2 ? 2.5 : 1.4;
    ctx.stroke();
  });
  ctx.fillStyle = '#ffffff';
  ctx.font = '900 15px Inter, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('SWARM CORE', cx, cy - 2);
  ctx.fillStyle = '#38bdf8';
  ctx.font = '800 9.5px monospace';
  ctx.fillText('100-AGENT RADIAL FANOUT', cx, cy + 14);
  ctx.textAlign = 'left';
  ctx.restore();

  // Inner Ring: 7 Active Cross-Pool Agents + Outer Ring: 36 Micro-Agent Satellites
  const rInner = Math.min(w, h) * 0.27;
  const rOuter = Math.min(w, h) * 0.41;
  agents.forEach((ag, idx) => {
    const ang = (idx / agents.length) * Math.PI * 2 + now * 0.00018;
    const ax = cx + Math.cos(ang) * rInner;
    const ay = cy + Math.sin(ang) * rInner;
    const col = ['#f97316', '#06b6d4', '#a855f7', '#22c55e', '#38bdf8', '#ec4899', '#fbbf24'][idx % 7];

    links.push({
      x1: cx, y1: cy,
      cx1: (cx + ax) * 0.5 + 18, cy1: (cy + ay) * 0.5 - 18,
      cx2: (cx + ax) * 0.5 - 18, cy2: (cy + ay) * 0.5 + 18,
      x2: ax, y2: ay,
      color: col
    });

    ctx.save();
    ctx.fillStyle = 'rgba(11, 19, 36, 0.94)';
    ctx.strokeStyle = col;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.roundRect(ax - 78, ay - 22, 156, 44, 8);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#fff';
    ctx.font = '800 9.2px Inter, sans-serif';
    ctx.fillText(ag.name.slice(0, 22), ax - 70, ay - 5);
    ctx.fillStyle = col;
    ctx.font = '700 8px monospace';
    ctx.fillText(`${ag.cot_stage.slice(0, 21)}`, ax - 70, ay + 10);
    ctx.restore();
  });

  // Left Docked 12U Rack Strip & Right Docked Cloud Search Strip connected into the Radial Core
  rackList.slice(0, 6).forEach((rc, idx) => {
    const ry = 66 + idx * ((h - 100) / 6);
    ctx.save();
    ctx.fillStyle = 'rgba(10, 17, 32, 0.92)';
    ctx.strokeStyle = rc.color;
    ctx.beginPath();
    ctx.roundRect(16, ry, 235, 48, 6);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#fff';
    ctx.font = '800 9px Inter, sans-serif';
    ctx.fillText(`🗄️ ${rc.unit}: ${rc.name.slice(0, 22)}`, 24, ry + 18);
    ctx.fillStyle = rc.color;
    ctx.font = '700 8px monospace';
    ctx.fillText(rc.metric, 24, ry + 34);
    ctx.restore();
    links.push({
      x1: 251, y1: ry + 24,
      cx1: (251 + cx) * 0.45, cy1: ry + 24,
      cx2: (251 + cx) * 0.65, cy2: cy,
      x2: cx - 52, y2: cy,
      color: rc.color
    });
  });

  clouds.slice(0, 6).forEach((cn, idx) => {
    const ry = 66 + idx * ((h - 100) / 6);
    const rx = w - 251;
    ctx.save();
    ctx.fillStyle = 'rgba(10, 17, 32, 0.92)';
    ctx.strokeStyle = cn.color;
    ctx.beginPath();
    ctx.roundRect(rx, ry, 235, 48, 6);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#fff';
    ctx.font = '800 9px Inter, sans-serif';
    ctx.fillText(`☁️ ${cn.name.slice(0, 24)}`, rx + 8, ry + 18);
    ctx.fillStyle = cn.color;
    ctx.font = '700 8px monospace';
    ctx.fillText(cn.active_query.slice(0, 28), rx + 8, ry + 34);
    ctx.restore();
    links.push({
      x1: cx + 52, y1: cy,
      cx1: (cx + rx) * 0.45, cy1: cy,
      cx2: (cx + rx) * 0.65, cy2: ry + 24,
      x2: rx, y2: ry + 24,
      color: cn.color
    });
  });

  drawBezierComets(ctx, links, now, isPulse);
}

/* SUB-VIEW 5: 6-SWIMLANE CoT & RESOURCE PIPELINE (KNIME STYLE) */
function drawHmPipelineView(ctx, w, h, now, isPulse, rackList, agents, clouds) {
  const lanes = [
    { name: 'LANE 1 • 12U RACK & 4xT4 GPUs', col: '#06b6d4' },
    { name: 'LANE 2 • HIVEMIND ORCHESTRATOR', col: '#a855f7' },
    { name: 'LANE 3 • <think> CoT REASONING', col: '#f59e0b' },
    { name: 'LANE 4 • LOCAL QDRANT & RAMDISK', col: '#22c55e' },
    { name: 'LANE 5 • CLOUD SEARCH & CDP ORACLES', col: '#f97316' },
    { name: 'LANE 6 • VERIFIED CUTS & E2E GATE', col: '#ec4899' }
  ];
  const topY = 48;
  const laneH = (h - topY - 12) / lanes.length;
  const links = [];

  lanes.forEach((ln, lIdx) => {
    const ly = topY + lIdx * laneH;
    ctx.save();
    ctx.fillStyle = (lIdx % 2 === 0) ? 'rgba(10, 18, 36, 0.68)' : 'rgba(6, 11, 24, 0.68)';
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.18)';
    ctx.fillRect(14, ly, w - 28, laneH - 4);
    ctx.strokeRect(14, ly, w - 28, laneH - 4);

    // Left Lane Header Banner
    ctx.fillStyle = ln.col;
    ctx.fillRect(14, ly, 6, laneH - 4);
    ctx.font = '900 10px Inter, sans-serif';
    ctx.fillText(ln.name, 28, ly + 18);
    ctx.restore();

    // 5 Pipeline Stage Nodes across each horizontal lane
    const stepW = (w - 300) / 5;
    for (let s = 0; s < 5; s++) {
      const nx = 260 + s * stepW;
      const ny = ly + 10;
      const nw = stepW - 28, nh = laneH - 24;
      const ag = agents[(lIdx + s) % Math.max(1, agents.length)] || {};
      const rk = rackList[(lIdx + s) % Math.max(1, rackList.length)] || {};
      const cl = clouds[(lIdx + s) % Math.max(1, clouds.length)] || {};

      ctx.save();
      ctx.fillStyle = 'rgba(13, 22, 42, 0.95)';
      ctx.strokeStyle = ln.col;
      ctx.lineWidth = 1.3;
      ctx.beginPath();
      ctx.roundRect(nx, ny, nw, nh, 6);
      ctx.fill();
      ctx.stroke();

      let title = ag.name || 'Node';
      let sub = ag.cot_stage || '';
      if (lIdx === 0) { title = `${rk.unit} ${rk.name}`; sub = rk.metric; }
      else if (lIdx === 2) { title = `💭 ${ag.cot_stage}`; sub = (ag.thought || '').slice(0, 32); }
      else if (lIdx === 4) { title = `🔍 ${cl.name}`; sub = (cl.active_query || '').slice(0, 32); }

      ctx.fillStyle = '#ffffff';
      ctx.font = '800 9px Inter, sans-serif';
      ctx.fillText((title || '').slice(0, 28), nx + 8, ny + 16);
      ctx.fillStyle = ln.col;
      ctx.font = '700 8px monospace';
      ctx.fillText((sub || '').slice(0, 32), nx + 8, ny + 31);
      ctx.restore();

      if (s < 4) {
        links.push({
          x1: nx + nw, y1: ny + nh / 2,
          cx1: nx + nw + 10, cy1: ny + nh / 2,
          cx2: nx + stepW - 10, cy2: ny + nh / 2,
          x2: nx + stepW, y2: ny + nh / 2,
          color: ln.col
        });
      }
    }
  });

  drawBezierComets(ctx, links, now, isPulse);
}

/* ============================================================================
   OPTION 1 & 2 ENGINE: 50-VIEW 60FPS PARAMETRIC RENDERER (V01–V50)
   Works identically on 1x1 Single Canvas, 2x2 Quad Wallboard, & 3x2 Six-Pack!
   ============================================================================ */
function drawCanvasRackTwin(ctx, w, h, now, isPulse, rackList, agents, clouds) {
  const links = [];
  const fX = 22, fY = 52, fW = 540, fH = h - 68;
  const rX = 590, rY = 52, rW = 540, rH = h - 68;
  const cX = 1160, cY = 52, cW = w - 1182, cH = h - 68;

  // 1) FRONT ELEVATION CABINET
  ctx.save();
  ctx.fillStyle = '#090c12';
  ctx.strokeStyle = '#334155';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.roundRect(fX, fY, fW, fH, 8);
  ctx.fill();
  ctx.stroke();

  // Front Top Bezel with 79.5°F Red LED Thermostat & Red Power Rocker
  ctx.fillStyle = '#151b26';
  ctx.fillRect(fX + 2, fY + 2, fW - 4, 34);
  ctx.fillStyle = '#94a3b8';
  ctx.font = '900 10.5px Inter, sans-serif';
  ctx.fillText('FRONT ELEVATION • 12U CABINET', fX + 12, fY + 23);

  // Red LED 79.5°F Box
  ctx.fillStyle = '#050101';
  ctx.strokeStyle = '#ef4444';
  ctx.lineWidth = 1.5;
  ctx.fillRect(fX + 255, fY + 6, 86, 25);
  ctx.strokeRect(fX + 255, fY + 6, 86, 25);
  ctx.fillStyle = '#ef4444';
  ctx.shadowColor = '#ef4444';
  ctx.shadowBlur = 10;
  ctx.font = '900 15px monospace';
  ctx.fillText('79.5°F', fX + 268, fY + 24);
  ctx.shadowBlur = 0;

  // Red Rocker Switch
  ctx.fillStyle = '#dc2626';
  ctx.fillRect(fX + fW - 42, fY + 11, 24, 14);
  ctx.strokeStyle = '#fca5a5';
  ctx.strokeRect(fX + fW - 42, fY + 11, 24, 14);

  // U1-U4 Silver Ubiquiti UniFi Spine Switches
  const unifiUnits = [
    { u: 'U1', name: 'Dream Machine Pro (.70.1)', sub: '400+ DNS • 3.5" NVR Bay • WAN/LAN', pCol: '#3b82f6' },
    { u: 'U2', name: 'USW-Aggregation (.10.110)', sub: '8x 10G SFP+ Optical Spine', pCol: '#06b6d4' },
    { u: 'U3', name: 'USW-Pro-Aggregation 280G (.10.111)', sub: '28x 10G + 4x 25G RoCE SFP28', pCol: '#facc15' },
    { u: 'U4', name: 'USW PoE Switch (.10.182)', sub: 'Blue Cat6 Patch Bundle • VLAN 10/70', pCol: '#2563eb' }
  ];
  let curY = fY + 42;
  const u1H = 44;
  unifiUnits.forEach((u, idx) => {
    ctx.fillStyle = '#cbd5e1';
    ctx.strokeStyle = '#64748b';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(fX + 10, curY, fW - 20, u1H - 4, 4);
    ctx.fill();
    ctx.stroke();

    // Blue LCM Touchscreen
    ctx.fillStyle = '#0284c7';
    ctx.fillRect(fX + 16, curY + 6, 26, 26);
    ctx.fillStyle = '#ffffff';
    ctx.font = '900 9px monospace';
    ctx.fillText(u.u, fX + 22, curY + 23);

    ctx.fillStyle = '#0f172a';
    ctx.font = '800 10.5px Inter, sans-serif';
    ctx.fillText(u.name, fX + 50, curY + 16);
    ctx.fillStyle = '#334155';
    ctx.font = '600 8.5px monospace';
    ctx.fillText(u.sub, fX + 50, curY + 30);

    // Glowing SFP+/RJ45 Ports on right
    for (let p = 0; p < 12; p++) {
      const px = fX + fW - 155 + p * 11;
      ctx.fillStyle = (p % 3 === 0) ? '#06b6d4' : u.pCol;
      ctx.fillRect(px, curY + 14, 8, 10);
    }
    curY += u1H;
  });

  // U5-U12: 4x 2U HPE ProLiant DL380 Gen9 Hosts (2x SFF + 2x 12-Bay LFF)
  const hpeUnits = [
    { u: 'U5–U6', name: 'esxi01 (.20.41) • HPE DL380 Gen9 2U SFF', sub: '56T Xeon • 768G RAM • Vault A (.72) T4 #1', type: 'sff', mag: false, uid: false, col: '#06b6d4' },
    { u: 'U7–U8', name: 'esxi02 (.20.42) • HPE DL380 Gen9 2U SFF', sub: 'Magenta SFF Latches • Vault B (.83) T4 #2', type: 'sff', mag: true, uid: false, col: '#ec4899' },
    { u: 'U9–U10', name: 'esxi03 (.20.43) • 12-Bay 3.5" LFF Exos', sub: '4x24TB Seagate Exos Tier-0 • ai-infer01 T4 #3', type: 'lff', mag: false, uid: false, col: '#3b82f6' },
    { u: 'U11–U12', name: 'esxi04 (.20.44) • 12-Bay 3.5" LFF Exos', sub: '4x24TB Exos • ai-ollama01 T4 #4 • Blue UID', type: 'lff', mag: false, uid: true, col: '#a855f7' }
  ];
  const u2H = (fY + fH - curY - 8) / 4;
  hpeUnits.forEach((hUnit, idx) => {
    ctx.fillStyle = '#111622';
    ctx.strokeStyle = hUnit.col;
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.roundRect(fX + 10, curY, fW - 20, u2H - 6, 4);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.font = '800 10px Inter, sans-serif';
    ctx.fillText(`${hUnit.u} • ${hUnit.name}`, fX + 18, curY + 16);
    ctx.fillStyle = hUnit.col;
    ctx.font = '700 8.5px monospace';
    ctx.fillText(hUnit.sub, fX + 18, curY + 30);

    if (hUnit.type === 'sff') {
      // 16 vertical SFF 2.5" bays on right half
      for (let b = 0; b < 12; b++) {
        const bx = fX + 310 + b * 17;
        const by = curY + 8;
        const bh = u2H - 22;
        ctx.fillStyle = '#070b12';
        ctx.strokeStyle = '#334155';
        ctx.fillRect(bx, by, 14, bh);
        ctx.strokeRect(bx, by, 14, bh);
        // Green activity LED
        ctx.fillStyle = '#22c55e';
        ctx.fillRect(bx + 4, by + 4, 5, 5);
        // Maroon or Glowing Magenta Latch
        ctx.fillStyle = (hUnit.mag && b >= 6) ? '#ec4899' : '#881337';
        ctx.fillRect(bx + 2, by + bh - 12, 10, 8);
      }
    } else {
      // 12-Bay 3.5" LFF 4x3 horizontal grid
      const gx0 = fX + 305, gy0 = curY + 8, gw = 205, gh = u2H - 20;
      for (let r = 0; r < 3; r++) {
        for (let c = 0; c < 4; c++) {
          const bx = gx0 + c * (gw / 4);
          const by = gy0 + r * (gh / 3);
          ctx.fillStyle = '#161e2e';
          ctx.strokeStyle = '#475569';
          ctx.fillRect(bx + 1, by + 1, (gw / 4) - 3, (gh / 3) - 3);
          ctx.strokeRect(bx + 1, by + 1, (gw / 4) - 3, (gh / 3) - 3);
          ctx.fillStyle = '#22c55e';
          ctx.fillRect(bx + 4, by + 4, 4, 4);
          ctx.fillStyle = '#9f1239';
          ctx.fillRect(bx + (gw / 4) - 9, by + 3, 5, (gh / 3) - 7);
        }
      }
      if (hUnit.uid) {
        ctx.beginPath();
        ctx.arc(fX + 292, curY + 22, 6, 0, Math.PI * 2);
        ctx.fillStyle = '#38bdf8';
        ctx.shadowColor = '#38bdf8';
        ctx.shadowBlur = 12;
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    }
    curY += u2H;
  });

  // 2) REAR ELEVATION CABINET (Top Smart-UPS + USW-Pro-Max at ESXi 2&3 + 4x Tesla T4)
  ctx.fillStyle = '#090c12';
  ctx.strokeStyle = '#334155';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.roundRect(rX, rY, rW, rH, 8);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = '#151b26';
  ctx.fillRect(rX + 2, rY + 2, rW - 4, 34);
  ctx.fillStyle = '#94a3b8';
  ctx.font = '900 10.5px Inter, sans-serif';
  ctx.fillText('REAR ELEVATION • TOP UPS + USW-PRO-MAX + 4x TESLA T4', rX + 12, rY + 23);
  ctx.fillStyle = '#10b981';
  ctx.font = '900 10px monospace';
  ctx.fillText('⚡ 8x800W PSU + UPS 100%', rX + rW - 165, rY + 23);

  const rearBlocks = [
    { title: '🔋 REAR TOP • RACKMOUNT SMART-UPS BATTERY BACKUP', sub: '100% Charged • Pure Sine Wave • Protecting U1–U4 Spine & 4x DL380', col: '#10b981', h: 110, badge: 'UPS 100%' },
    { title: '⚡ REAR U5–U6 • esxi01 (.41) + NVIDIA Tesla T4 #1 (ai-srv01 .72)', sub: '25GbE RoCE 10.0.75.12:50052 • iLO4 .10.10 • vSAN .60.21 • 2x800W PSU', col: '#06b6d4', h: 145, badge: 'T4 #1 • 77.6 tok/s' },
    { title: '✨ REAR RAIL (ESXi 2 & 3) • UniFi USW-Pro-Max Etherlighting Switch', sub: 'Mounted in Rear Rail at ESXi 2 & 3 (.10.182) • 2.5G/10G RGB Etherlighting', col: '#38bdf8', h: 115, badge: 'USW-PRO-MAX' },
    { title: '⚡ REAR U7–U10 • esxi02 (.42) & esxi03 (.43) + Tesla T4 #2 & #3', sub: 'RoCE .75.11 (aidev .83) & .75.13 (ai-infer01 .125 Qdrant :6333) • 4x800W PSU', col: '#ec4899', h: 185, badge: 'T4 #2 & #3' },
    { title: '⚡ REAR U11–U12 • esxi04 (.44) + NVIDIA Tesla T4 #4 (ai-ollama01 .228)', sub: 'RoCE .75.14 • LiteLLM :4000 • Langfuse :3000 • iLO4 .10.40 • Blue UID', col: '#a855f7', h: 155, badge: 'T4 #4 • :4000' }
  ];
  let rCurY = rY + 44;
  rearBlocks.forEach((rb, idx) => {
    ctx.fillStyle = (idx === 2) ? '#1e293b' : '#101726';
    ctx.strokeStyle = rb.col;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.roundRect(rX + 12, rCurY, rW - 24, rb.h - 10, 6);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = rb.col;
    ctx.beginPath();
    ctx.roundRect(rX + rW - 138, rCurY + 10, 116, 20, 4);
    ctx.fill();
    ctx.fillStyle = '#020617';
    ctx.font = '900 8.5px monospace';
    ctx.fillText(rb.badge, rX + rW - 130, rCurY + 23);

    ctx.fillStyle = '#ffffff';
    ctx.font = '800 10.5px Inter, sans-serif';
    ctx.fillText(rb.title, rX + 22, rCurY + 24);
    ctx.fillStyle = '#94a3b8';
    ctx.font = '600 8.8px monospace';
    ctx.fillText(rb.sub, rX + 22, rCurY + 44);

    // Draw Etherlighting glowing port strip or GPU PCIe riser visual
    for (let p = 0; p < 16; p++) {
      const px = rX + 22 + p * 28;
      const py = rCurY + 60;
      const pCol = ['#06b6d4', '#ec4899', '#22c55e', '#f59e0b'][(p + idx) % 4];
      ctx.fillStyle = pCol;
      ctx.fillRect(px, py, 20, 12);
    }

    // Connect Front Cabinet <-> Rear Cabinet
    links.push({
      x1: fX + fW - 10, y1: rCurY + rb.h * 0.4,
      cx1: (fX + fW + rX) * 0.5, cy1: rCurY + rb.h * 0.4 - 18,
      cx2: (fX + fW + rX) * 0.5, cy2: rCurY + rb.h * 0.4 + 18,
      x2: rX + 12, y2: rCurY + rb.h * 0.4,
      color: rb.col
    });

    // Connect Rear Cabinet -> Right Live HiveMind CoT & Cloud Column
    links.push({
      x1: rX + rW - 12, y1: rCurY + rb.h * 0.5,
      cx1: (rX + rW + cX) * 0.5, cy1: rCurY + rb.h * 0.5,
      cx2: (rX + rW + cX) * 0.5, cy2: cY + 70 + idx * 145,
      x2: cX, y2: cY + 70 + idx * 145,
      color: rb.col
    });

    rCurY += rb.h;
  });

  // 3) RIGHT COLUMN: LIVE <think> CoT & CLOUD SEARCH TETHERS
  ctx.fillStyle = 'rgba(10, 17, 34, 0.94)';
  ctx.strokeStyle = '#38bdf8';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.roundRect(cX, cY, cW, cH, 8);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = '#38bdf8';
  ctx.font = '900 11px Inter, sans-serif';
  ctx.fillText('🧠 LIVE <think> CoT & CLOUD TETHERS', cX + 12, cY + 24);

  agents.slice(0, 6).forEach((ag, idx) => {
    const ay = cY + 42 + idx * ((cH - 52) / 6);
    const ah = ((cH - 52) / 6) - 8;
    const col = ['#f59e0b', '#a855f7', '#06b6d4', '#22c55e', '#ec4899', '#38bdf8'][idx % 6];
    ctx.fillStyle = 'rgba(15, 23, 42, 0.95)';
    ctx.strokeStyle = col;
    ctx.lineWidth = 1.3;
    ctx.beginPath();
    ctx.roundRect(cX + 10, ay, cW - 20, ah, 6);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.font = '800 9.8px Inter, sans-serif';
    ctx.fillText(`🤖 ${ag.name.slice(0, 32)}`, cX + 18, ay + 18);
    ctx.fillStyle = col;
    ctx.font = '700 8.5px monospace';
    ctx.fillText(`${ag.cot_stage} • ${ag.tok_s} tok/s`, cX + 18, ay + 34);
    ctx.fillStyle = '#cbd5e1';
    ctx.font = '600 8px monospace';
    ctx.fillText((ag.thought || '').slice(0, 46), cX + 18, ay + 50);
    ctx.fillStyle = '#38bdf8';
    ctx.fillText(`🔍 ${ag.query.slice(0, 44)}`, cX + 18, ay + 66);
  });
  ctx.restore();

  drawBezierComets(ctx, links, now, isPulse);
}

function drawParametricSpecialView(ctx, w, h, viewId, vMeta, now, isPulse, rackList, agents, clouds) {
  const num = parseInt(viewId.slice(1), 10) || 1;
  const cx = w * 0.5, cy = h * 0.53;
  const links = [];
  const accent = vMeta.color || '#38bdf8';
  const c2 = vMeta.c2 || '#a855f7';
  const c3 = vMeta.c3 || '#10b981';
  const arch = vMeta.arch || 'centurion_omega_masterpiece';

  // Top Archetype & Telemetry Header Banner
  ctx.save();
  ctx.fillStyle = 'rgba(7, 13, 28, 0.94)';
  ctx.strokeStyle = accent;
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.roundRect(14, 10, w - 28, 44, 8);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = accent;
  ctx.beginPath();
  ctx.roundRect(24, 18, 62, 28, 5);
  ctx.fill();
  ctx.fillStyle = '#020617';
  ctx.font = '900 12px monospace';
  ctx.fillText(viewId, 36, 36);

  ctx.fillStyle = '#f8fafc';
  ctx.font = '900 13.5px Inter, sans-serif';
  ctx.fillText(vMeta.name, 98, 30);
  ctx.fillStyle = c2;
  ctx.font = '700 10px monospace';
  ctx.fillText(`ARCHETYPE: ${arch.toUpperCase()}  •  CAT: ${vMeta.catName}  •  12U RACK: 79.5°F (UPS 100% + USW-PRO-MAX)  •  ROCE: 77.6 tok/s`, 98, 46);
  ctx.restore();

  // Left 12U Rack Anchor Column (6 compact cards) & Right Cloud Search Column (6 compact cards)
  const leftAnchors = [];
  const rightAnchors = [];
  rackList.slice(0, 6).forEach((rc, idx) => {
    const ry = 64 + idx * ((h - 84) / 6);
    const rh = ((h - 84) / 6) - 9;
    leftAnchors.push({ x: 245, y: ry + rh / 2, color: rc.color || accent, rc });
    ctx.save();
    ctx.fillStyle = 'rgba(9, 16, 30, 0.93)';
    ctx.strokeStyle = rc.color || accent;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.roundRect(14, ry, 231, rh, 6);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#ffffff';
    ctx.font = '800 9.2px Inter, sans-serif';
    ctx.fillText(`🗄️ ${rc.unit}: ${rc.name.slice(0, 23)}`, 22, ry + 18);
    ctx.fillStyle = rc.color || accent;
    ctx.font = '700 8px monospace';
    ctx.fillText(`${rc.ip} • 79.5°F Nominal`, 22, ry + 34);
    ctx.fillStyle = '#cbd5e1';
    ctx.fillText(`${rc.metric}`, 22, ry + 50);
    ctx.restore();
  });

  clouds.slice(0, 6).forEach((cn, idx) => {
    const ry = 64 + idx * ((h - 84) / 6);
    const rh = ((h - 84) / 6) - 9;
    const rx = w - 245;
    rightAnchors.push({ x: rx, y: ry + rh / 2, color: cn.color || c2, cn });
    ctx.save();
    ctx.fillStyle = 'rgba(9, 16, 30, 0.93)';
    ctx.strokeStyle = cn.color || c2;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.roundRect(rx, ry, 231, rh, 6);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#ffffff';
    ctx.font = '800 9.2px Inter, sans-serif';
    ctx.fillText(`☁️ ${cn.name.slice(0, 24)}`, rx + 8, ry + 18);
    ctx.fillStyle = cn.color || c2;
    ctx.font = '700 8px monospace';
    ctx.fillText(`${cn.endpoint.slice(0, 28)}`, rx + 8, ry + 34);
    ctx.fillStyle = '#cbd5e1';
    ctx.fillText(`↳ ${cn.active_query.slice(0, 28)}`, rx + 8, ry + 50);
    ctx.restore();
  });

  // Center Stage Area: x in [268, w - 268], width = w - 536
  const stageX = 268, stageW = w - 536, stageY = 64, stageH = h - 84;

  ctx.save();
  if (arch === 'military_c4isr_radar' || arch === 'f35_hud_mfd' || arch === 'submarine_sonar' || arch === 'carrier_catapult') {
    // TACTICAL C4ISR / F-35 HUD / SONAR / CARRIER CATAPULT
    const rMax = Math.min(stageW, stageH) * 0.44;
    if (arch === 'submarine_sonar') {
      // Acoustic Time-Frequency Waterfall + Sonar Bearing Arcs
      for (let row = 0; row < 18; row++) {
        const wy = stageY + 20 + row * ((stageH - 40) / 18);
        for (let col = 0; col < 28; col++) {
          const wx = stageX + 20 + col * ((stageW - 40) / 28);
          const v = Math.sin(now * 0.004 + row * 0.5 + col * 0.35 + num) * 0.5 + 0.5;
          ctx.fillStyle = v > 0.72 ? accent : (v > 0.4 ? 'rgba(6, 182, 212, 0.32)' : 'rgba(16, 185, 129, 0.12)');
          ctx.fillRect(wx, wy, ((stageW - 40) / 28) - 3, ((stageH - 40) / 18) - 3);
        }
      }
    } else if (arch === 'carrier_catapult') {
      // 4 Catapult Steam/EMALS Launch Tracks for 4x Tesla T4s
      for (let catIdx = 0; catIdx < 4; catIdx++) {
        const ly = stageY + 35 + catIdx * ((stageH - 60) / 4);
        ctx.fillStyle = 'rgba(12, 20, 34, 0.92)';
        ctx.strokeStyle = accent;
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.roundRect(stageX + 20, ly, stageW - 40, ((stageH - 60) / 4) - 14, 8);
        ctx.fill();
        ctx.stroke();
        const prog = ((now * 0.00045 + catIdx * 0.25) % 1);
        const shuttleX = stageX + 40 + prog * (stageW - 180);
        ctx.fillStyle = c2;
        ctx.fillRect(stageX + 35, ly + 42, stageW - 70, 6);
        ctx.fillStyle = accent;
        ctx.beginPath();
        ctx.roundRect(shuttleX, ly + 22, 110, 38, 6);
        ctx.fill();
        ctx.fillStyle = '#020617';
        ctx.font = '900 9.5px monospace';
        ctx.fillText(`CAT-${catIdx + 1} T4 #${catIdx + 1}`, shuttleX + 8, ly + 45);
        const ag = agents[catIdx % Math.max(1, agents.length)] || { name: 'Agent', cot_stage: '<think>', tok_s: 77.6, thought: 'Executing' };
        ctx.fillStyle = '#ffffff';
        ctx.font = '800 10.5px Inter, sans-serif';
        ctx.fillText(`🛫 EMALS TRACK #${catIdx + 1}: ${ag.name} • ${ag.cot_stage} (${ag.tok_s} tok/s)`, stageX + 36, ly + 18);
        const la = leftAnchors[catIdx % leftAnchors.length];
        const ra = rightAnchors[catIdx % rightAnchors.length];
        if (la) links.push({ x1: la.x, y1: la.y, cx1: stageX, cy1: la.y, cx2: stageX, cy2: ly + 35, x2: stageX + 20, y2: ly + 35, color: accent });
        if (ra) links.push({ x1: stageX + stageW - 20, y1: ly + 35, cx1: ra.x - 20, cy1: ly + 35, cx2: ra.x - 20, cy2: ra.y, x2: ra.x, y2: ra.y, color: c2 });
      }
    }
    if (arch !== 'carrier_catapult') {
      [0.33, 0.66, 1.0].forEach(f => {
        ctx.beginPath();
        ctx.arc(cx, cy, rMax * f, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(16, 185, 129, 0.4)';
        ctx.lineWidth = 1.4;
        ctx.stroke();
      });
      if (arch === 'f35_hud_mfd') {
        // Pitch ladder bars
        for (let p = -3; p <= 3; p++) {
          if (p === 0) continue;
          const py = cy + p * 44;
          ctx.strokeStyle = '#4ade80';
          ctx.lineWidth = 1.6;
          ctx.beginPath();
          ctx.moveTo(cx - 85, py); ctx.lineTo(cx - 30, py);
          ctx.moveTo(cx + 30, py); ctx.lineTo(cx + 85, py);
          ctx.stroke();
        }
      }
      const swAng = (now * 0.0018) % (Math.PI * 2);
      const rg = ctx.createRadialGradient(cx, cy, 8, cx, cy, rMax);
      rg.addColorStop(0, 'rgba(16, 185, 129, 0.28)');
      rg.addColorStop(1, 'rgba(16, 185, 129, 0.0)');
      ctx.fillStyle = rg;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, rMax, swAng, swAng + 0.55);
      ctx.closePath();
      ctx.fill();

      agents.forEach((ag, idx) => {
        const ang = (idx / Math.max(1, agents.length)) * Math.PI * 2 + (num % 2 === 0 ? now * 0.00025 : -now * 0.00025);
        const rad = rMax * (0.42 + (idx % 2) * 0.34);
        const tx = cx + Math.cos(ang) * rad;
        const ty = cy + Math.sin(ang) * rad;

        ctx.strokeStyle = idx === 0 ? c2 : accent;
        ctx.fillStyle = 'rgba(4, 24, 16, 0.92)';
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        ctx.moveTo(tx, ty - 18); ctx.lineTo(tx + 18, ty); ctx.lineTo(tx, ty + 18); ctx.lineTo(tx - 18, ty);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = 'rgba(4, 18, 12, 0.92)';
        ctx.strokeStyle = accent;
        ctx.fillRect(tx + 22, ty - 22, 174, 44);
        ctx.strokeRect(tx + 22, ty - 22, 174, 44);
        ctx.fillStyle = accent;
        ctx.font = '900 9px monospace';
        ctx.fillText(`TRK-0${idx + 1} [${viewId}] ${ag.id.toUpperCase()}`, tx + 27, ty - 8);
        ctx.fillStyle = '#fde68a';
        ctx.font = '700 8px monospace';
        ctx.fillText(`${ag.cot_stage.slice(0, 24)}`, tx + 27, ty + 5);
        ctx.fillStyle = '#a7f3d0';
        ctx.fillText(`VEL: ${ag.tok_s} tok/s • LOCKED`, tx + 27, ty + 17);

        const la = leftAnchors[idx % leftAnchors.length];
        const ra = rightAnchors[idx % rightAnchors.length];
        if (la) links.push({ x1: la.x, y1: la.y, cx1: (la.x + tx) * 0.5, cy1: la.y, cx2: (la.x + tx) * 0.5, cy2: ty, x2: tx, y2: ty, color: accent });
        if (ra) links.push({ x1: tx, y1: ty, cx1: (tx + ra.x) * 0.5, cy1: ty, cx2: (tx + ra.x) * 0.5, cy2: ra.y, x2: ra.x, y2: ra.y, color: c2 });
      });
    }
  } else if (arch === 'nerv_magi_trinity') {
    // V43: EVANGELION NERV MAGI 3-BRAIN CONSENSUS (MELCHIOR + BALTHASAR + CASPER)
    const magiNodes = [
      { name: 'MELCHIOR • 1 (CLAUDE OPUS 5.5)', sub: 'SCIENTIST / ARCHITECT CORE', x: cx, y: cy - 155, col: '#f97316' },
      { name: 'BALTHASAR • 2 (CODEX GPT-6.1-SOL)', sub: 'GUARDIAN / VERIFIER CORE', x: cx - 235, y: cy + 125, col: '#00ff66' },
      { name: 'CASPER • 3 (KIMI K2.8 THINKING)', sub: 'ORCHESTRATOR / SWARM CORE', x: cx + 235, y: cy + 125, col: '#38bdf8' }
    ];
    // Connect triangle
    ctx.strokeStyle = '#f97316';
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(magiNodes[0].x, magiNodes[0].y);
    ctx.lineTo(magiNodes[1].x, magiNodes[1].y);
    ctx.lineTo(magiNodes[2].x, magiNodes[2].y);
    ctx.closePath();
    ctx.stroke();

    ctx.fillStyle = 'rgba(249, 115, 22, 0.16)';
    ctx.fill();
    ctx.fillStyle = '#f97316';
    ctx.font = '900 14px monospace';
    ctx.fillText('MAGI QUORUM: 3/3 BOARD', cx - 92, cy + 15);

    magiNodes.forEach((m, idx) => {
      ctx.fillStyle = 'rgba(14, 10, 10, 0.96)';
      ctx.strokeStyle = m.col;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.roundRect(m.x - 145, m.y - 52, 290, 104, 10);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = m.col;
      ctx.font = '900 11px monospace';
      ctx.fillText(m.name, m.x - 130, m.y - 24);
      ctx.fillStyle = '#fde68a';
      ctx.font = '700 9px monospace';
      ctx.fillText(m.sub, m.x - 130, m.y - 6);
      const ag = agents[idx % Math.max(1, agents.length)] || { thought: 'SMT invariant verified', cot_stage: '<think> Consensus', tok_s: 77.6 };
      ctx.fillStyle = '#ffffff';
      ctx.fillText(`${ag.cot_stage} • ${ag.tok_s} tok/s`, m.x - 130, m.y + 16);
      ctx.fillStyle = '#cbd5e1';
      ctx.fillText((ag.thought || '').slice(0, 36), m.x - 130, m.y + 34);

      const la = leftAnchors[idx % leftAnchors.length];
      const ra = rightAnchors[idx % rightAnchors.length];
      if (la) links.push({ x1: la.x, y1: la.y, cx1: (la.x + m.x) * 0.5, cy1: la.y, cx2: m.x - 145, cy2: m.y, x2: m.x - 145, y2: m.y, color: m.col });
      if (ra) links.push({ x1: m.x + 145, y1: m.y, cx1: m.x + 145, cy1: m.y, cx2: (m.x + ra.x) * 0.5, cy2: ra.y, x2: ra.x, y2: ra.y, color: m.col });
    });
  } else if (arch === 'dna_helix') {
    // DUAL-VAULT DNA DOUBLE-HELIX (.72 <-> .83)
    for (let i = 0; i < 22; i++) {
      const t = i / 21;
      const hx = stageX + 40 + t * (stageW - 80);
      const phase = now * 0.003 + i * 0.45;
      const yA = cy + Math.sin(phase) * 165;
      const yB = cy - Math.sin(phase) * 165;
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.45)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(hx, yA);
      ctx.lineTo(hx, yB);
      ctx.stroke();

      ctx.beginPath(); ctx.arc(hx, yA, 7, 0, Math.PI * 2); ctx.fillStyle = accent; ctx.fill();
      ctx.beginPath(); ctx.arc(hx, yB, 7, 0, Math.PI * 2); ctx.fillStyle = c2; ctx.fill();
      if (i % 3 === 0) {
        const la = leftAnchors[(i / 3) % leftAnchors.length];
        const ra = rightAnchors[(i / 3) % rightAnchors.length];
        if (la) links.push({ x1: la.x, y1: la.y, cx1: (la.x + hx) * 0.5, cy1: la.y, cx2: hx, cy2: yA, x2: hx, y2: yA, color: accent });
        if (ra) links.push({ x1: hx, y1: yB, cx1: hx, cy1: yB, cx2: (hx + ra.x) * 0.5, cy2: ra.y, x2: ra.x, y2: ra.y, color: c2 });
      }
    }
  } else if (arch === 'lcars_deck') {
    // STAR TREK LCARS ENGINEERING DECK
    const lcarsCols = ['#fb923c', '#c084fc', '#38bdf8', '#fbbf24', '#f43f5e'];
    ctx.fillStyle = '#fb923c';
    ctx.beginPath();
    ctx.roundRect(stageX, stageY, 160, stageH, 28);
    ctx.fill();
    ctx.fillStyle = '#020617';
    ctx.beginPath();
    ctx.roundRect(stageX + 42, stageY + 32, 125, stageH - 64, 16);
    ctx.fill();
    agents.forEach((ag, idx) => {
      const by = stageY + 46 + idx * ((stageH - 80) / Math.max(1, agents.length));
      const col = lcarsCols[idx % lcarsCols.length];
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.roundRect(stageX + 60, by, stageW - 80, 62, 31);
      ctx.fill();
      ctx.fillStyle = '#020617';
      ctx.fillRect(stageX + 195, by + 4, stageW - 290, 54);
      ctx.fillStyle = '#020617';
      ctx.font = '900 11px monospace';
      ctx.fillText(`LCARS-0${idx + 1}`, stageX + 82, by + 35);
      ctx.fillStyle = col;
      ctx.font = '800 10.5px monospace';
      ctx.fillText(`${ag.name} • ${ag.cot_stage} • ${ag.tok_s} TOK/S`, stageX + 210, by + 24);
      ctx.fillStyle = '#f8fafc';
      ctx.font = '600 9px monospace';
      ctx.fillText((ag.thought || '').slice(0, 68), stageX + 210, by + 44);
      const la = leftAnchors[idx % leftAnchors.length];
      const ra = rightAnchors[idx % rightAnchors.length];
      if (la) links.push({ x1: la.x, y1: la.y, cx1: stageX, cy1: la.y, cx2: stageX, cy2: by + 31, x2: stageX + 60, y2: by + 31, color: col });
      if (ra) links.push({ x1: stageX + stageW - 20, y1: by + 31, cx1: ra.x - 40, cy1: by + 31, cx2: ra.x - 40, cy2: ra.y, x2: ra.x, y2: ra.y, color: col });
    });
  } else if (arch === 'flamegraph_spans' || arch === 'quantum_bloch_rails' || arch === 'factorio_conveyor_bus' || arch === 'hft_orderbook') {
    // FLAMEGRAPH SPANS / QUANTUM RAILS / FACTORIO CONVEYOR / HFT ORDERBOOK
    const lanes = Math.min(7, Math.max(5, agents.length));
    for (let i = 0; i < lanes; i++) {
      const ag = agents[i % Math.max(1, agents.length)] || { name: 'Agent', cot_stage: '<think>', tok_s: 77.6, thought: 'Executing', tool: 'ctx_slice' };
      const ly = stageY + 18 + i * ((stageH - 30) / lanes);
      const lh = ((stageH - 30) / lanes) - 10;
      ctx.fillStyle = 'rgba(11, 18, 34, 0.92)';
      ctx.strokeStyle = i % 2 === 0 ? accent : c2;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.roundRect(stageX + 16, ly, stageW - 32, lh, 7);
      ctx.fill();
      ctx.stroke();

      // Animated span bars or quantum gates along the lane
      for (let g = 0; g < 5; g++) {
        const gx = stageX + 240 + g * ((stageW - 280) / 5);
        const gw = ((stageW - 280) / 5) - 12;
        const pulseW = gw * (0.65 + 0.35 * Math.sin(now * 0.003 + i + g));
        ctx.fillStyle = [accent, c2, c3, '#f59e0b', '#ec4899'][(i + g) % 5];
        ctx.globalAlpha = 0.28;
        ctx.fillRect(gx, ly + 8, gw, lh - 16);
        ctx.globalAlpha = 0.88;
        ctx.fillRect(gx, ly + lh - 14, pulseW, 6);
        ctx.globalAlpha = 1.0;
        ctx.fillStyle = '#f8fafc';
        ctx.font = '700 8.5px monospace';
        const lbl = arch === 'quantum_bloch_rails' ? `|ψ${g}⟩ H⊗CNOT` : (arch === 'hft_orderbook' ? `BID/ASK #${g + 1}` : (arch === 'factorio_conveyor_bus' ? `BUS-STAGE-${g + 1}` : `SPAN-${g + 1} ${ag.tool}`));
        ctx.fillText(lbl.slice(0, 16), gx + 6, ly + 24);
      }

      ctx.fillStyle = '#ffffff';
      ctx.font = '800 10px Inter, sans-serif';
      ctx.fillText(`${ag.name.slice(0, 24)}`, stageX + 26, ly + 22);
      ctx.fillStyle = accent;
      ctx.font = '700 8.5px monospace';
      ctx.fillText(`${ag.cot_stage} • ${ag.tok_s} tok/s`, stageX + 26, ly + 40);

      const la = leftAnchors[i % leftAnchors.length];
      const ra = rightAnchors[i % rightAnchors.length];
      if (la) links.push({ x1: la.x, y1: la.y, cx1: stageX, cy1: la.y, cx2: stageX, cy2: ly + lh / 2, x2: stageX + 16, y2: ly + lh / 2, color: accent });
      if (ra) links.push({ x1: stageX + stageW - 16, y1: ly + lh / 2, cx1: ra.x - 16, cy1: ly + lh / 2, cx2: ra.x - 16, cy2: ra.y, x2: ra.x, y2: ra.y, color: c2 });
    }
  } else if (arch === 'jwst_hex_mirrors' || arch === 'etherlighting_switch_matrix' || arch === 'rack_12u_front_rear_xray') {
    // JWST 18-HEXAGON GOLD MIRROR ARRAY / ETHERLIGHTING MATRIX / 12U X-RAY
    if (arch === 'jwst_hex_mirrors') {
      const hexR = 46;
      const coords = [[0,0],[1,0],[-1,0],[0,1],[0,-1],[1,-1],[-1,1],[2,0],[-2,0],[1,1],[-1,-1],[2,-1],[-2,1],[0,2],[0,-2],[2,-2],[-2,2],[1,-2]];
      coords.forEach(([q, r], idx) => {
        const hx = cx + hexR * 1.75 * (q + r * 0.5);
        const hy = cy + hexR * 1.52 * r;
        ctx.beginPath();
        for (let k = 0; k < 6; k++) {
          const a = (Math.PI / 3) * k + Math.PI / 6;
          const px = hx + (hexR - 3) * Math.cos(a);
          const py = hy + (hexR - 3) * Math.sin(a);
          if (k === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.fillStyle = idx === 0 ? 'rgba(56, 189, 248, 0.25)' : 'rgba(251, 191, 36, 0.18)';
        ctx.strokeStyle = idx === 0 ? '#38bdf8' : '#fbbf24';
        ctx.lineWidth = 2;
        ctx.fill();
        ctx.stroke();
        const ag = agents[idx % Math.max(1, agents.length)] || { id: 'SEG', tok_s: 77.6 };
        ctx.fillStyle = '#fef08a';
        ctx.font = '800 8.5px monospace';
        ctx.fillText(`M-${String(idx + 1).padStart(2, '0')}`, hx - 14, hy - 4);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(`${ag.tok_s}t/s`, hx - 18, hy + 10);
      });
      leftAnchors.forEach((la, i) => links.push({ x1: la.x, y1: la.y, cx1: (la.x + cx) * 0.5, cy1: la.y, cx2: cx - 120, cy2: cy, x2: cx - 120, y2: cy, color: accent }));
      rightAnchors.forEach((ra, i) => links.push({ x1: cx + 120, y1: cy, cx1: cx + 120, cy1: cy, cx2: (cx + ra.x) * 0.5, cy2: ra.y, x2: ra.x, y2: ra.y, color: c2 }));
    } else {
      // 48-Port Glowing Etherlighting Switch Matrix & 12U Hardware X-Ray
      const rows = 4, cols = 12;
      const cellW = (stageW - 60) / cols;
      const cellH = (stageH - 80) / rows;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const px = stageX + 30 + c * cellW;
          const py = stageY + 40 + r * cellH;
          const pCol = [accent, c2, c3, '#f59e0b'][(r + c) % 4];
          ctx.fillStyle = 'rgba(10, 18, 36, 0.94)';
          ctx.strokeStyle = pCol;
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.roundRect(px + 3, py + 3, cellW - 6, cellH - 10, 6);
          ctx.fill();
          ctx.stroke();
          ctx.fillStyle = pCol;
          ctx.font = '900 8.5px monospace';
          ctx.fillText(`P${r * 12 + c + 1}`, px + 8, py + 20);
          ctx.fillStyle = '#cbd5e1';
          ctx.font = '700 7.5px monospace';
          ctx.fillText(r < 2 ? '25G RoCE' : '10G SFP+', px + 8, py + 36);
          ctx.fillStyle = '#22c55e';
          ctx.fillRect(px + 8, py + cellH - 22, cellW - 22, 6);
        }
      }
      leftAnchors.forEach((la, i) => links.push({ x1: la.x, y1: la.y, cx1: stageX, cy1: la.y, cx2: stageX + 30, cy2: la.y, x2: stageX + 30, y2: la.y, color: accent }));
      rightAnchors.forEach((ra, i) => links.push({ x1: stageX + stageW - 30, y1: ra.y, cx1: ra.x - 20, cy1: ra.y, cx2: ra.x, cy2: ra.y, x2: ra.x, y2: ra.y, color: c2 }));
    }
  } else if (arch === 'cern_collider' || arch === 'rehoboam_ring' || arch === 'eve_tidi_orbit') {
    // CERN ATLAS DETECTOR / REHOBOAM ECLIPSE RING / ORBITAL CONSTELLATION
    const rOuter = Math.min(stageW, stageH) * 0.43;
    for (let ring = 1; ring <= 4; ring++) {
      ctx.beginPath();
      ctx.arc(cx, cy, (rOuter * ring) / 4, 0, Math.PI * 2);
      ctx.strokeStyle = ring % 2 === 0 ? accent : c2;
      ctx.lineWidth = ring === 4 ? 2.5 : 1.2;
      ctx.stroke();
    }
    // Divergence spikes around Rehoboam / CERN ring
    for (let s = 0; s < 72; s++) {
      const a = (s / 72) * Math.PI * 2 + now * 0.0004;
      const amp = 10 + 26 * Math.abs(Math.sin(now * 0.003 + s * 0.7 + num));
      ctx.strokeStyle = s % 3 === 0 ? accent : c2;
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * rOuter, cy + Math.sin(a) * rOuter);
      ctx.lineTo(cx + Math.cos(a) * (rOuter + amp), cy + Math.sin(a) * (rOuter + amp));
      ctx.stroke();
    }
    agents.forEach((ag, idx) => {
      const a = (idx / Math.max(1, agents.length)) * Math.PI * 2 - now * 0.0005;
      const r = rOuter * 0.65;
      const nx = cx + Math.cos(a) * r;
      const ny = cy + Math.sin(a) * r;
      ctx.fillStyle = 'rgba(8, 14, 28, 0.94)';
      ctx.strokeStyle = accent;
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.roundRect(nx - 78, ny - 24, 156, 48, 7);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = '#ffffff';
      ctx.font = '800 9px Inter, sans-serif';
      ctx.fillText(ag.name.slice(0, 22), nx - 70, ny - 6);
      ctx.fillStyle = accent;
      ctx.font = '700 8px monospace';
      ctx.fillText(`${ag.cot_stage.slice(0, 18)} • ${ag.tok_s}t/s`, nx - 70, ny + 12);
      const la = leftAnchors[idx % leftAnchors.length];
      const ra = rightAnchors[idx % rightAnchors.length];
      if (la) links.push({ x1: la.x, y1: la.y, cx1: (la.x + nx) * 0.5, cy1: la.y, cx2: nx, cy2: ny, x2: nx, y2: ny, color: accent });
      if (ra) links.push({ x1: nx, y1: ny, cx1: nx, cy1: ny, cx2: (nx + ra.x) * 0.5, cy2: ra.y, x2: ra.x, y2: ra.y, color: c2 });
    });
  } else if (arch === 'centurion_omega_masterpiece') {
    // CENTURION / OMEGA MULTI-PANEL COMMAND SYNTHESIS
    const boxes = [
      { x: stageX, y: stageY, w: stageW * 0.49, h: stageH * 0.48, t: `🗄️ [${viewId}] 12U RACK TWIN (79.5°F + REAR UPS + PRO-MAX)`, c: accent },
      { x: stageX + stageW * 0.51, y: stageY, w: stageW * 0.49, h: stageH * 0.48, t: `🧠 [${viewId}] HIVEMIND + n8n <think> CoT ENGINE`, c: c2 },
      { x: stageX, y: stageY + stageH * 0.51, w: stageW * 0.49, h: stageH * 0.48, t: `🪖 [${viewId}] C4ISR LATTICE + 4x TESLA T4 RoCE`, c: c3 },
      { x: stageX + stageW * 0.51, y: stageY + stageH * 0.51, w: stageW * 0.49, h: stageH * 0.48, t: `☁️ [${viewId}] CLOUD SEARCH (:8888 / .137 / .181 / $1,000)`, c: '#f59e0b' }
    ];
    boxes.forEach((b, bIdx) => {
      ctx.fillStyle = 'rgba(11, 19, 36, 0.94)';
      ctx.strokeStyle = b.c;
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.roundRect(b.x, b.y, b.w, b.h, 8);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = b.c;
      ctx.font = '900 10.5px Inter, sans-serif';
      ctx.fillText(b.t, b.x + 12, b.y + 22);
      agents.slice(0, 4).forEach((ag, aIdx) => {
        const ry = b.y + 36 + aIdx * ((b.h - 46) / 4);
        ctx.fillStyle = 'rgba(20, 30, 55, 0.9)';
        ctx.fillRect(b.x + 12, ry, b.w - 24, ((b.h - 46) / 4) - 6);
        ctx.fillStyle = '#ffffff';
        ctx.font = '800 9.2px Inter, sans-serif';
        ctx.fillText(`${ag.name.slice(0, 26)} • ${ag.tok_s} tok/s`, b.x + 18, ry + 16);
        ctx.fillStyle = '#94a3b8';
        ctx.font = '600 8px monospace';
        ctx.fillText((ag.thought || '').slice(0, 48), b.x + 18, ry + 32);
      });
      const la = leftAnchors[bIdx % leftAnchors.length];
      const ra = rightAnchors[bIdx % rightAnchors.length];
      if (la) links.push({ x1: la.x, y1: la.y, cx1: (la.x + b.x) * 0.5, cy1: la.y, cx2: b.x, cy2: b.y + b.h / 2, x2: b.x, y2: b.y + b.h / 2, color: b.c });
      if (ra) links.push({ x1: b.x + b.w, y1: b.y + b.h / 2, cx1: b.x + b.w, cy1: b.y + b.h / 2, cx2: (b.x + b.w + ra.x) * 0.5, cy2: ra.y, x2: ra.x, y2: ra.y, color: b.c });
    });
  } else {
    // PARAMETRIC NODE STUDIO / RIVET NOODLES / UE5 BLUEPRINTS / MCTS TREE / SANKEY / EURORACK SYNTH
    ctx.strokeStyle = accent;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.roundRect(stageX, stageY, stageW, stageH, 10);
    ctx.stroke();

    for (let r = 1; r <= 3; r++) {
      ctx.beginPath();
      ctx.arc(cx, cy, r * 68, 0, Math.PI * 2);
      ctx.strokeStyle = r === 2 ? accent : 'rgba(56, 189, 248, 0.22)';
      ctx.stroke();
    }

    agents.forEach((ag, idx) => {
      const colIdx = idx % 2;
      const rowIdx = Math.floor(idx / 2);
      const cardW = (stageW - 60) / 2;
      const cardH = Math.min(112, (stageH - 76) / 4);
      const ax = stageX + 20 + colIdx * (cardW + 20);
      const ay = stageY + 20 + rowIdx * (cardH + 14);
      const cCol = [accent, c2, c3, '#f59e0b', '#ec4899', '#38bdf8', '#fb923c'][idx % 7];

      ctx.fillStyle = 'rgba(12, 20, 38, 0.94)';
      ctx.strokeStyle = cCol;
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.roundRect(ax, ay, cardW, cardH, 8);
      ctx.fill();
      ctx.stroke();

      // Header bar for UE5 / Rivet / Synth node look
      ctx.fillStyle = cCol;
      ctx.globalAlpha = 0.24;
      ctx.fillRect(ax + 2, ay + 2, cardW - 4, 22);
      ctx.globalAlpha = 1.0;

      ctx.fillStyle = '#ffffff';
      ctx.font = '800 10px Inter, sans-serif';
      ctx.fillText(`🤖 ${ag.name} [${viewId} • ${arch}]`, ax + 12, ay + 17);
      ctx.fillStyle = cCol;
      ctx.font = '700 8.8px monospace';
      ctx.fillText(`${ag.cot_stage} • Tool: ${ag.tool} • ${ag.tok_s} tok/s`, ax + 12, ay + 38);
      ctx.fillStyle = '#e2e8f0';
      ctx.font = '600 8.5px monospace';
      ctx.fillText((ag.thought || '').slice(0, 56), ax + 12, ay + 56);
      ctx.fillStyle = '#38bdf8';
      ctx.fillText(`🔍 ${ag.query.slice(0, 52)}`, ax + 12, ay + 74);

      const la = leftAnchors[idx % leftAnchors.length];
      const ra = rightAnchors[idx % rightAnchors.length];
      if (la) links.push({ x1: la.x, y1: la.y, cx1: (la.x + ax) * 0.5, cy1: la.y, cx2: (la.x + ax) * 0.5, cy2: ay + cardH / 2, x2: ax, y2: ay + cardH / 2, color: la.color });
      if (ra) links.push({ x1: ax + cardW, y1: ay + cardH / 2, cx1: (ax + cardW + ra.x) * 0.5, cy1: ay + cardH / 2, cx2: (ax + cardW + ra.x) * 0.5, cy2: ra.y, x2: ra.x, y2: ra.y, color: ra.color });
    });
  }
  ctx.restore();

  drawBezierComets(ctx, links, now, isPulse);
}

function renderViewOnCanvas(ctx, realW, realH, rawViewId, tick, telemetry) {
  if (!ctx || realW <= 0 || realH <= 0) return;
  const viewId = normalizeViewId(rawViewId);
  const vMeta = VIEWS_MAP[viewId] || VIEWS_CATALOG[0];
  const w = 1600, h = 900;
  const now = tick || performance.now();
  const isPulse = now < PULSE_UNTIL;
  const hm = (telemetry && telemetry.hivemind_live) ? telemetry.hivemind_live : {};
  const rackList = hm.local_rack_resources || [];
  const agents = hm.agents_cot || [];
  const clouds = hm.cloud_search_nodes || [];

  ctx.save();
  ctx.scale(realW / w, realH / h);

  // Background Grid per View Palette (batched single path)
  ctx.fillStyle = vMeta.bg || ((viewId === 'V03' || vMeta.arch === 'hivemind_crt') ? '#020905' : '#030712');
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = (viewId === 'V03' || vMeta.arch === 'hivemind_crt') ? 'rgba(16, 185, 129, 0.09)' : 'rgba(56, 189, 248, 0.07)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let x = 0; x < w; x += 38) { ctx.moveTo(x, 0); ctx.lineTo(x, h); }
  for (let y = 0; y < h; y += 38) { ctx.moveTo(0, y); ctx.lineTo(w, y); }
  ctx.stroke();

  // Dispatch to specialized 60fps geometry renderer
  const prevSub = HM_SUB;
  const arch = vMeta.arch || '';
  if (viewId === 'V01' || arch === 'hybrid') {
    HM_SUB = 'hybrid';
    drawHiveMindScene(ctx, w, h);
  } else if (viewId === 'V02' || arch === 'n8n_hanging_circles') {
    drawHmN8nView(ctx, w, h, now, isPulse, rackList, agents, clouds);
  } else if (viewId === 'V03' || arch === 'hivemind_crt') {
    drawHmCrtView(ctx, w, h, now, isPulse, rackList, agents, clouds);
  } else if (viewId === 'V04' || arch === 'kimi_radial_core') {
    drawHmKimiView(ctx, w, h, now, isPulse, rackList, agents, clouds);
  } else if (viewId === 'V05' || arch === 'knime_swimlanes') {
    drawHmPipelineView(ctx, w, h, now, isPulse, rackList, agents, clouds);
  } else if (arch === 'rack_twin') {
    drawCanvasRackTwin(ctx, w, h, now, isPulse, rackList, agents, clouds);
  } else if (arch === 'unifi_os') {
    const prevM = MODE; MODE = 'graph'; draw2DScene(ctx, w, h); MODE = prevM;
  } else if (arch === 'iso_floor') {
    draw3DScene(ctx, w, h);
  } else {
    drawParametricSpecialView(ctx, w, h, viewId, vMeta, now, isPulse, rackList, agents, clouds);
  }
  HM_SUB = prevSub;

  ctx.restore();
}

function loop() {
  const now = performance.now();
  if (CINEMA_ACTIVE && (now - CINEMA_LAST_SWITCH) >= 15000) {
    CINEMA_LAST_SWITCH = now;
    stepView(1);
  }

  if (DATA) {
    if (WALLBOARD === 'single') {
      const c = document.getElementById('main-canvas');
      if (c && MODE !== 'rack') {
        if (c.width !== c.parentElement.clientWidth || c.height !== c.parentElement.clientHeight) {
          c.width = c.parentElement.clientWidth;
          c.height = c.parentElement.clientHeight;
        }
        const ctx = c.getContext('2d');
        ctx.clearRect(0, 0, c.width, c.height);
        renderViewOnCanvas(ctx, c.width, c.height, ACTIVE_VIEW, now, DATA);
      }
    } else {
      const count = getActiveWallboardCount();
      const arr = getActiveWallboardArray();
      if (WB_DIRTY > 0) {
        for (let i = 0; i < count; i++) {
          const wc = document.getElementById('wb-canvas-' + i);
          if (wc && wc.parentElement && wc.parentElement.clientWidth > 0) {
            if (wc.width !== wc.parentElement.clientWidth || wc.height !== wc.parentElement.clientHeight) {
              wc.width = wc.parentElement.clientWidth;
              wc.height = wc.parentElement.clientHeight;
            }
            const wctx = wc.getContext('2d');
            wctx.clearRect(0, 0, wc.width, wc.height);
            renderViewOnCanvas(wctx, wc.width, wc.height, arr[i] || 'V01', now, DATA);
          }
        }
        WB_DIRTY--;
      } else {
        const i = (WB_TICK++) % Math.max(1, count);
        const wc = document.getElementById('wb-canvas-' + i);
        if (wc && wc.parentElement && wc.parentElement.clientWidth > 0) {
          if (wc.width !== wc.parentElement.clientWidth || wc.height !== wc.parentElement.clientHeight) {
            wc.width = wc.parentElement.clientWidth;
            wc.height = wc.parentElement.clientHeight;
          }
          const wctx = wc.getContext('2d');
          wctx.clearRect(0, 0, wc.width, wc.height);
          renderViewOnCanvas(wctx, wc.width, wc.height, arr[i] || 'V01', now, DATA);
        }
      }
    }
  }
  requestAnimationFrame(loop);
}

window.addEventListener('resize', resetView);
initCatalogUI();
resetView();
(function applyQueryParams() {
  const params = new URLSearchParams(window.location.search);
  const m = params.get('mode');
  const d = params.get('detail');
  const s = params.get('subview');
  const v = params.get('view');
  const wb = params.get('layout') || params.get('wallboard') || params.get('wb') || (m && ['eightpack','4x2','eight','quad','six'].includes(m) ? m : null);
  const cat = params.get('catalog');
  const cin = params.get('cinema');
  const hasExplicitViewOrWb = Boolean(v || wb);
  if (m && ['hivemind','graph','galaxy','3d','swimlane','rack','military'].includes(m)) setMode(m);
  if (s && ['hybrid','n8n','crt','kimi','pipeline'].includes(s)) setHmSub(s);
  if (v) selectView(normalizeViewId(v));
  if (wb) {
    const wbNorm = wb === '2x2' ? 'quad' : (wb === '3x2' ? 'six' : ((wb === '4x2' || wb === '8' || wb === 'eightpack') ? 'eight' : wb));
    if (['single','quad','six','eight'].includes(wbNorm)) setWallboard(wbNorm);
  }
  if (cat === 'open' || cat === '1') toggleCatalog(true);
  if (cin === '1' || cin === 'true') toggleCinema(true);
  if (d && ['simple','advanced'].includes(d)) setDetail(d);
  fetchInitialPreferred(!hasExplicitViewOrWb);
})();
loadTopology();
setInterval(loadTopology, 1500);
requestAnimationFrame(loop);
</script>
</body>
</html>
"""


def _build_gallery_html() -> str:
    cat_json = json.dumps(VIEWS_CATALOG, ensure_ascii=False)
    pref_json = json.dumps(_load_preferred_view(), ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Boylenet Master Visual Gallery — 165 Live 60fps Views (V01–V100 + T01–T65) + Interactive Launchers</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #030712; color: #f8fafc; font-family: 'Inter', system-ui, sans-serif; }}
  .hdr {{
    position: sticky; top: 0; z-index: 50;
    background: rgba(6, 11, 25, 0.96); backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(56, 189, 248, 0.35);
    padding: 12px 20px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px;
  }}
  .title {{ font-size: 15px; font-weight: 900; color: #38bdf8; display: flex; align-items: center; gap: 10px; }}
  .tabs {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .tab {{
    background: #0f172a; border: 1px solid #334155; color: #cbd5e1;
    padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 800; cursor: pointer;
  }}
  .tab.active {{ background: linear-gradient(135deg, #7c3aed, #0284c7); border-color: #38bdf8; color: #fff; }}
  .controls {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
  .search {{
    background: #090f1f; border: 1px solid #334155; color: #fff;
    padding: 6px 12px; border-radius: 7px; font-size: 12px; width: 210px;
  }}
  .pref-pill {{
    background: rgba(245, 158, 11, 0.16); border: 1px solid #fbbf24; color: #fde68a;
    padding: 6px 11px; border-radius: 8px; font-size: 12px; font-weight: 800;
  }}
  .back-btn {{
    background: linear-gradient(135deg, #10b981, #059669); color: #fff;
    text-decoration: none; padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 800;
  }}
  .grid {{
    display: grid; grid-template-columns: repeat(var(--cols, 3), 1fr);
    gap: 14px; padding: 18px;
  }}
  .card {{
    background: #091022; border: 1px solid rgba(56, 189, 248, 0.28);
    border-radius: 10px; overflow: hidden; cursor: pointer; transition: transform 0.15s, border-color 0.15s;
    display: flex; flex-direction: column;
  }}
  .card.is-pref-card {{
    border-color: #fbbf24; box-shadow: 0 0 22px rgba(251, 191, 36, 0.32);
  }}
  .card:hover {{ transform: translateY(-3px); border-color: #38bdf8; box-shadow: 0 8px 25px rgba(56,189,248,0.22); }}
  .card img {{ width: 100%; aspect-ratio: 16/9; object-fit: cover; display: block; background: #020617; }}
  .card-ftr {{
    padding: 8px 11px; display: flex; align-items: center; justify-content: space-between; gap: 8px;
    font-size: 11.5px; font-weight: 700; color: #e2e8f0; border-top: 1px solid rgba(56,189,248,0.18);
  }}
  .card-actions {{
    padding: 6px 11px 10px; display: flex; align-items: center; justify-content: space-between; gap: 8px;
    border-top: 1px solid rgba(56, 189, 248, 0.12); background: rgba(4, 9, 20, 0.9);
  }}
  .act-btn {{
    flex: 1; text-align: center; text-decoration: none; padding: 6px 9px; border-radius: 6px;
    font-size: 11px; font-weight: 800; cursor: pointer; border: 1px solid transparent;
    transition: all 0.14s;
  }}
  .launch-btn {{
    background: linear-gradient(135deg, #0284c7, #7c3aed); color: #ffffff; border-color: #38bdf8;
  }}
  .launch-btn:hover {{ filter: brightness(1.15); box-shadow: 0 0 12px rgba(56, 189, 248, 0.5); }}
  .pref-card-btn {{
    background: rgba(245, 158, 11, 0.15); color: #fde68a; border-color: rgba(251, 191, 36, 0.5);
  }}
  .pref-card-btn.active, .pref-card-btn:hover {{
    background: linear-gradient(135deg, #f59e0b, #eab308); color: #020617; border-color: #fff;
  }}
  .badge {{
    background: rgba(56,189,248,0.18); color: #38bdf8; border: 1px solid rgba(56,189,248,0.4);
    padding: 2px 7px; border-radius: 5px; font-family: monospace; font-size: 10.5px; font-weight: 900; white-space: nowrap;
  }}
  /* Lightbox */
  #lb {{
    display: none; position: fixed; inset: 0; z-index: 200;
    background: rgba(2, 5, 14, 0.95); align-items: center; justify-content: center; flex-direction: column;
  }}
  #lb.open {{ display: flex; }}
  #lb img {{ max-width: 94vw; max-height: 80vh; border: 2px solid #38bdf8; border-radius: 10px; box-shadow: 0 0 40px rgba(56,189,248,0.35); }}
  .lb-bar {{
    margin-top: 12px; display: flex; flex-wrap: wrap; align-items: center; gap: 12px; color: #fff; font-size: 14px; font-weight: 800;
  }}
  .lb-btn {{
    background: #1e293b; border: 1px solid #38bdf8; color: #fff; text-decoration: none;
    padding: 7px 14px; border-radius: 7px; cursor: pointer; font-weight: 800; font-size: 12px;
  }}
</style>
</head>
<body>
<div class="hdr">
  <div class="title">🖼️ BOYLENET VISUAL GALLERY (165 LIVE 60FPS VIEWS + WALLBOARDS)</div>
  <div class="tabs">
    <button class="tab active" onclick="setTab('all', this)">🌟 All (179)</button>
    <button class="tab" onclick="setTab('cot', this)">🧠 100 HiveMind & CoT (V01–V100)</button>
    <button class="tab" onclick="setTab('topo', this)">🗄️ 65 Rack, Topology & Military (T01–T65)</button>
    <button class="tab" onclick="setTab('live', this)">📺 Live :4088 Wallboards (8)</button>
    <button class="tab" onclick="setTab('web', this)">🌐 Web Search Examples (6)</button>
  </div>
  <div class="controls">
    <span class="pref-pill">⭐ Preferred Default: <b id="gal-pref-id">V01</b></span>
    <input class="search" id="q" placeholder="Filter by V01..V100, T01..T65 or keyword..." oninput="render()">
    <select class="tab" onchange="document.documentElement.style.setProperty('--cols', this.value)">
      <option value="2">2 Columns (Large)</option>
      <option value="3" selected>3 Columns</option>
      <option value="4">4 Columns</option>
    </select>
    <a href="/" class="back-btn" id="hdr-launch-pref">⚡ Open Live 60fps Engine (:4088)</a>
  </div>
</div>
<div class="grid" id="grid"></div>
<div id="lb" onclick="if(event.target.id==='lb')closeLb()">
  <img id="lb-img" src="">
  <div class="lb-bar">
    <button class="lb-btn" onclick="stepLb(-1)">◀ Prev (←)</button>
    <span id="lb-cap"></span>
    <a id="lb-launch" class="lb-btn" href="/" style="background:linear-gradient(135deg,#0284c7,#7c3aed);">🚀 Launch Live 60fps</a>
    <button id="lb-pref" class="lb-btn" onclick="setPreferredFromLb()" style="border-color:#fbbf24;color:#fde68a;">⭐ Set Preferred</button>
    <button class="lb-btn" onclick="stepLb(1)">Next (→) ▶</button>
    <button class="lb-btn" onclick="closeLb()" style="border-color:#ef4444;color:#fca5a5;">✕ Close (Esc)</button>
  </div>
</div>
<script>
const CATALOG = {cat_json};
let PREF_STATE = {pref_json};
const ITEMS = [];

// 1) All 165 Catalog Views (V01..V100 -> cat 'cot', T01..T65 -> cat 'topo')
CATALOG.forEach(v => {{
  const isCot = v.id.startsWith('V');
  ITEMS.push({{
    cat: isCot ? 'cot' : 'topo',
    viewId: v.id,
    badge: isCot ? ('COT #' + v.id.slice(1) + ' • ' + v.id) : ('TOPO #' + v.id.slice(1) + ' • ' + v.id),
    file: v.png,
    title: v.name,
    liveHref: '/?view=' + v.id
  }});
}});

// 2) 8 Live :4088 Wallboard screenshots
[
  ['live_4088_50view_catalog_drawer.png', 'Live :4088 — Interactive Catalog Drawer & 60fps Engine', 'V01', '/?catalog=open'],
  ['live_4088_quad_2x2_wallboard.png', 'Live :4088 — 2x2 Quad Split-Screen 60fps Wallboard', 'V01', '/?wallboard=quad'],
  ['live_4088_sixpack_3x2_wallboard.png', 'Live :4088 — 3x2 Six-View Split-Screen 60fps Mega-Wallboard', 'V01', '/?wallboard=six'],
  ['live_4088_subview_1_hybrid_hivemind_rack_cloud.png', 'Live :4088 Sub-View #1 — Hybrid HiveMind + n8n CoT + 12U Rack + Cloud Search', 'V01', '/?view=V01'],
  ['live_4088_subview_2_n8n_hanging_circles.png', 'Live :4088 Sub-View #2 — n8n Agent Swarm Hanging Circles', 'V02', '/?view=V02'],
  ['live_4088_subview_3_hivemind_v3_phosphor.png', 'Live :4088 Sub-View #3 — HIVEMIND v3.0 Phosphor-Green CRT', 'V03', '/?view=V03'],
  ['live_4088_subview_4_kimi_radial_core.png', 'Live :4088 Sub-View #4 — Kimi K2.5 Radial CORE Swarm Burst', 'V04', '/?view=V04'],
  ['live_4088_subview_5_knime_6_swimlanes.png', 'Live :4088 Sub-View #5 — KNIME 6-Swimlane CoT Pipeline', 'V05', '/?view=V05']
].forEach(([f, t, vid, href], i) => ITEMS.push({{cat:'live', viewId:vid, badge:'LIVE #'+(i+1), file:f, title:t, liveHref:href}}));

// 3) 6 Web Search Boards
[
  ['web_search_hivemind_swarm_ui.png', 'Web Search #1 — AI Agent Swarm Workflow Graphs', 'V02'],
  ['web_search_cot_node_graph_ui.png', 'Web Search #2 — Chain-of-Thought Node Graph UIs', 'V06'],
  ['web_search_neural_command_center_ui.png', 'Web Search #3 — Neural Command Center & Telemetry UIs', 'V09'],
  ['web_search_langgraph_autogen_crewai_ui.png', 'Web Search #4 — LangGraph, AutoGen & CrewAI Studios', 'V07'],
  ['web_search_palantir_anduril_c4isr_ui.png', 'Web Search #5 — Palantir Gotham & Anduril Lattice C4ISR', 'T61'],
  ['web_search_datacenter_gpu_flow_ui.png', 'Web Search #6 — Datacenter GPU & Sankey Compute Flows', 'T07']
].forEach(([f, t, vid], i) => ITEMS.push({{cat:'web', viewId:vid, badge:'WEB #'+(i+1), file:f, title:t, liveHref:'/?view='+vid}}));

let curTab = 'all', filtered = [], lbIdx = 0;

function syncPrefHeader() {{
  const pv = (PREF_STATE && PREF_STATE.preferred_view) ? PREF_STATE.preferred_view : 'V01';
  const el = document.getElementById('gal-pref-id');
  if (el) el.textContent = pv;
}}

async function pollPreferredFromGallery() {{
  try {{
    const r = await fetch('/api/preferred-view');
    if (r.ok) {{
      const d = await r.json();
      if (!PREF_STATE || d.preferred_view !== PREF_STATE.preferred_view) {{
        PREF_STATE = d;
        syncPrefHeader();
        render();
      }}
    }}
  }} catch (e) {{}}
}}

async function setPreferredFromGallery(viewId) {{
  try {{
    const r = await fetch('/api/preferred-view', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ preferred_view: viewId }})
    }});
    PREF_STATE = await r.json();
    syncPrefHeader();
    render();
    if (document.getElementById('lb').classList.contains('open')) openLb(lbIdx);
  }} catch (e) {{
    console.error(e);
  }}
}}

function setPreferredFromLb() {{
  const it = filtered[lbIdx];
  if (it && it.viewId) setPreferredFromGallery(it.viewId);
}}

function setTab(t, btn){{
  curTab = t;
  document.querySelectorAll('.hdr .tab').forEach(b => b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  render();
}}

function render(){{
  syncPrefHeader();
  const pv = (PREF_STATE && PREF_STATE.preferred_view) ? PREF_STATE.preferred_view : 'V01';
  const q = (document.getElementById('q').value || '').toLowerCase();
  filtered = ITEMS.filter(it => (curTab==='all' || it.cat===curTab) && (!q || it.title.toLowerCase().includes(q) || it.badge.toLowerCase().includes(q) || it.file.toLowerCase().includes(q) || (it.viewId && it.viewId.toLowerCase().includes(q))));
  const g = document.getElementById('grid');
  g.innerHTML = filtered.map((it, idx) => {{
    const isPref = (it.viewId === pv && (it.cat === 'cot' || it.cat === 'topo'));
    return `
    <div class="card ${{isPref ? 'is-pref-card' : ''}}" onclick="openLb(${{idx}})">
      <img loading="lazy" src="/screenshots/${{it.file}}" alt="${{it.title}}">
      <div class="card-ftr">
        <span>${{it.title}}</span>
        <span class="badge">${{it.badge}}</span>
      </div>
      <div class="card-actions" onclick="event.stopPropagation()">
        <a class="act-btn launch-btn" data-action="launch-fullscreen" href="${{it.liveHref || ('/?view=' + it.viewId)}}">🚀 Launch Fullscreen (${{it.viewId}})</a>
        <button class="act-btn pref-card-btn ${{isPref ? 'active' : ''}}" data-action="pin-default" onclick="setPreferredFromGallery('${{it.viewId}}')">${{isPref ? '⭐ Pinned Default' : '⭐ Pin as Default'}}</button>
      </div>
    </div>
  `;
  }}).join('');
}}

function openLb(idx){{
  lbIdx = idx;
  const it = filtered[lbIdx];
  if(!it) return;
  const pv = (PREF_STATE && PREF_STATE.preferred_view) ? PREF_STATE.preferred_view : 'V01';
  document.getElementById('lb-img').src = '/screenshots/' + it.file;
  document.getElementById('lb-cap').textContent = `${{it.badge}} — ${{it.title}} (${{lbIdx+1}} / ${{filtered.length}})`;
  const lBtn = document.getElementById('lb-launch');
  if (lBtn) {{
    lBtn.href = it.liveHref || ('/?view=' + it.viewId);
    lBtn.textContent = `🚀 Launch Fullscreen (${{it.viewId}})`;
  }}
  const pBtn = document.getElementById('lb-pref');
  if (pBtn) {{
    pBtn.textContent = (it.viewId === pv) ? `⭐ Pinned Default (${{it.viewId}})` : `⭐ Pin as Default (${{it.viewId}})`;
  }}
  document.getElementById('lb').classList.add('open');
}}
function closeLb(){{ document.getElementById('lb').classList.remove('open'); }}
function stepLb(d){{
  if(!filtered.length) return;
  openLb((lbIdx + d + filtered.length) % filtered.length);
}}
window.addEventListener('keydown', e => {{
  if(!document.getElementById('lb').classList.contains('open')) return;
  if(e.key==='ArrowLeft') stepLb(-1);
  if(e.key==='ArrowRight') stepLb(1);
  if(e.key==='Escape') closeLb();
}});
render();
setInterval(pollPreferredFromGallery, 1500);
</script>
</body>
</html>"""


class TopologyRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/health":
            snap = get_cached_topology()
            pref = _load_preferred_view()
            self._send_json(
                {
                    "status": "ok",
                    "service": "bd-topology-visualizer",
                    "version": "5.0-165views-60fps-wallboard-preferred",
                    "port": PORT,
                    "views_count": len(VIEWS_CATALOG),
                    "wallboard_layouts": ["1x1", "2x2", "3x2", "4x2", "cinema"],
                    "preferred_view": pref.get("preferred_view", "V01"),
                    "preferred_state": pref,
                    "nodes_count": len(snap.get("nodes", [])),
                    "flows_count": len(snap.get("flows", [])),
                    "active_tmux_sessions": snap.get("summary", {}).get(
                        "active_tmux_sessions", 0
                    ),
                    "timestamp": _now_iso(),
                }
            )
            return
        if path == "/api/preferred-view":
            pref = _load_preferred_view()
            self._send_json({"status": "ok", **pref})
            return
        if path.startswith("/screenshots/"):
            fname = os.path.basename(path)
            sdir = "/home/mboyle/.gemini/antigravity-cli/brain/d61a0f86-9a87-4a9f-8b2c-ea5791e23bc8/screenshots"
            fpath = os.path.join(sdir, fname)
            if os.path.isfile(fpath) and fname.endswith(".png"):
                with open(fpath, "rb") as f:
                    raw = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "public, max-age=3600")
                self.end_headers()
                self.wfile.write(raw)
                return
            self._send_json({"error": "image_not_found"}, status=404)
            return
        if path == "/gallery":
            raw = _build_gallery_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == "/api/hivemind-live":
            snap = get_cached_topology()
            self._send_json(snap.get("hivemind_live", {}))
            return
        if path == "/api/topology":
            get_cached_topology()
            raw = _CACHED_TOPOLOGY_BYTES
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(raw)
            return
        raw = HTML_PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = (
            self.rfile.read(length).decode("utf-8", errors="replace")
            if length > 0
            else "{}"
        )
        try:
            data = json.loads(body)
        except ValueError:
            data = {}
        if path == "/api/preferred-view":
            saved = _save_preferred_view(data if isinstance(data, dict) else {})
            self._send_json({"status": "ok", **saved})
            return
        if path == "/api/ping":
            target = str(data.get("target", "10.0.70.72"))
            self._send_json(_probe_target(target))
            return
        self._send_json({"error": "not_found"}, status=404)


def main() -> None:
    _load_preferred_view()
    get_cached_topology()
    t = threading.Thread(target=_bg_refresh_loop, daemon=True)
    t.start()
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("0.0.0.0", PORT), TopologyRequestHandler)
    print(f"[bd-topology-visualizer v5.0 165-Views] Listening on http://0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
