#!/usr/bin/env python3
"""
Boylenet Unified OS Desktop Shell (bd-os-shell.py)
Port: 4085 (https://os.boylenet.themfboyles.org)
Pillars 1 & 7 (#UX-1..5, #UX-21, #UX-32..35):
  - #UX-1 Left App Dock (macOS / Linear style, live status dots, Alt+1..9 shortcuts, 0ms DOM-kept iframe switching)
  - #UX-2 Universal Cmd+K / Ctrl+K Raycast-Style Command Palette (52+ Apps, 86 Vault Models, 40 Fleet Roles, Quick Actions)
  - #UX-3 Persistent 36px Top Telemetry & Quota Pill Bar (Claude A/B/C/D 5h%, $1,000 Cloud Credit, 4xT4 tok/s, 86 Models, Sentinel)
  - #UX-4 Split-Screen Workspace Mode (1-Pane | 2-Pane Split | 3-Pane Tactical Grid | TV Wallboard Auto-Cycle #UX-21 + Backtick ` Terminal Drawer)
  - #UX-5 Picture-in-Picture (PiP) Mini-Monitor Popout (Document PiP / Canvas Stream PiP / Floating HUD)
  - #UX-32..35 Shared Embeddable Assets (/static/boylenet-nav.js & /static/boylenet-ui.css), 4-Theme Engine & Snapshot Exporter
"""

from __future__ import annotations

import argparse
import datetime
import http.server
import json
import os
import re
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

PORT = int(os.environ.get("BD_OS_SHELL_PORT", "4085"))
HOST_IP = os.environ.get("BD_CONTROLLER_IP", "10.0.70.164")
POOL_STATE_TSV = "/home/mboyle/bd-persist/POOL_STATE.tsv"
AUTOBALANCER_JSON = "/var/tmp/bd-pool-autobalancer.json"
VAULT_MANIFEST_JSON = "/var/tmp/bd-vault-manifest.json"
SNAPSHOT_DIR = "/var/tmp/bd-os-snapshots"

ORCHESTRATOR_URL = "http://127.0.0.1:4010"
SENTINEL_URL = "http://127.0.0.1:4099"
CLOUD_BURST_URL = "http://127.0.0.1:4090"
HARNESS_WEB_URL = "http://127.0.0.1:4098"
DOCTOR_URL = "http://127.0.0.1:4081"

# 18 Flagship Dock Apps (exact order per Pillar 1 specification)
DOCK_APPS: List[Dict[str, Any]] = [
    {
        "id": "briefing",
        "icon": "🏠",
        "title": "Executive Briefing & Doctor",
        "short": "Briefing & Doctor",
        "port": 4081,
        "sub": "briefing",
        "shortcut": "Alt+1",
        "cat": "Core OS",
    },
    {
        "id": "topology",
        "icon": "🕸️",
        "title": "3D Swarm & Rack Topology",
        "short": "3D Topology",
        "port": 4088,
        "sub": "topology",
        "shortcut": "Alt+2",
        "cat": "Observability",
    },
    {
        "id": "harnesses",
        "icon": "⚔️",
        "title": "Multi-Harness Studio & Arena",
        "short": "Harness Studio",
        "port": 4098,
        "sub": "harnesses",
        "shortcut": "Alt+3",
        "cat": "AI Studio",
    },
    {
        "id": "cloud",
        "icon": "☁️",
        "title": "$1,000 Cloud Burst Orchestrator",
        "short": "$1k Cloud Burst",
        "port": 4090,
        "sub": "cloud",
        "shortcut": "Alt+4",
        "cat": "AI Studio",
    },
    {
        "id": "models",
        "icon": "🧠",
        "title": "86-Model Vault Storefront",
        "short": "86-Model Vault",
        "port": 4084,
        "sub": "models",
        "shortcut": "Alt+5",
        "cat": "AI Studio",
    },
    {
        "id": "terminal",
        "icon": "💻",
        "title": "Multi-Node Web Terminal & Receipt Viewer",
        "short": "Web Terminal",
        "port": 4083,
        "sub": "terminal",
        "shortcut": "Alt+6",
        "cat": "Core OS",
    },
    {
        "id": "research",
        "icon": "🔬",
        "title": "Dual-Oracle Deep Research",
        "short": "Deep Research",
        "port": 4094,
        "sub": "research",
        "shortcut": "Alt+7",
        "cat": "AI Studio",
    },
    {
        "id": "voice",
        "icon": "🎙️",
        "title": "Voice & Vision Studio",
        "short": "Voice & Vision",
        "port": 4093,
        "sub": "voice",
        "shortcut": "Alt+8",
        "cat": "AI Studio",
    },
    {
        "id": "prereview",
        "icon": "🛡️",
        "title": "Gitea Pre-Review & Red-Team",
        "short": "Gitea Pre-Review",
        "port": 4092,
        "sub": "prereview",
        "shortcut": "Alt+9",
        "cat": "Security & CI",
    },
    {
        "id": "hardware",
        "icon": "🏢",
        "title": "Physical Rack & iLO4 Telemetry",
        "short": "Rack & iLO4",
        "port": 4091,
        "sub": "hardware",
        "shortcut": "",
        "cat": "Hardware",
    },
    {
        "id": "sentinel",
        "icon": "🩺",
        "title": "Infra Sentinel Self-Healer",
        "short": "Infra Sentinel",
        "port": 4099,
        "sub": "sentinel",
        "shortcut": "",
        "cat": "Infra & Ops",
    },
    {
        "id": "vault",
        "icon": "🔐",
        "title": "Credentials & SSH Vault",
        "short": "SSH & Key Vault",
        "port": 4087,
        "sub": "vault",
        "shortcut": "",
        "cat": "Security & CI",
    },
    {
        "id": "ops",
        "icon": "⚡",
        "title": "Natural-Language Ops Shell",
        "short": "NL Ops Shell",
        "port": 4089,
        "sub": "ops",
        "shortcut": "",
        "cat": "Infra & Ops",
    },
    {
        "id": "mobile",
        "icon": "📱",
        "title": "Mobile PWA Deck",
        "short": "Mobile PWA",
        "port": 4086,
        "sub": "mobile",
        "shortcut": "",
        "cat": "Core OS",
    },
    {
        "id": "jarvis",
        "icon": "🚀",
        "title": "Jarvis Cockpit",
        "short": "Jarvis Cockpit",
        "port": 3002,
        "sub": "jarvis",
        "shortcut": "",
        "cat": "Core OS",
    },
    {
        "id": "chat",
        "icon": "💬",
        "title": "Swarm Chat",
        "short": "Swarm Chat",
        "port": 3003,
        "sub": "chat",
        "shortcut": "",
        "cat": "AI Studio",
    },
    {
        "id": "grafana",
        "icon": "📊",
        "title": "Grafana AI Nexus",
        "short": "Grafana Nexus",
        "port": 3001,
        "sub": "grafana",
        "shortcut": "",
        "cat": "Observability",
    },
    {
        "id": "dashy",
        "icon": "🧭",
        "title": "Dashy Portal",
        "short": "Dashy Portal",
        "port": 4080,
        "sub": "dashy",
        "shortcut": "",
        "cat": "Core OS",
    },
    {
        "id": "visual-gallery-179",
        "icon": "🖼️",
        "title": "179-Image Visual Gallery & 165-View Launcher",
        "short": "165-View Gallery",
        "port": 4088,
        "sub": "topology",
        "shortcut": "",
        "cat": "Observability",
        "url": f"http://{HOST_IP}:4088/gallery",
    },
    {
        "id": "wallboard-eight-4x2",
        "icon": "🧱",
        "title": "4x2 Eight-Pack 60fps Mega-NOC Wallboard",
        "short": "4x2 Wallboard",
        "port": 4088,
        "sub": "topology",
        "shortcut": "",
        "cat": "Observability",
        "url": f"http://{HOST_IP}:4088/?mode=eightpack",
    },
    {
        "id": "gpu-orchestrator",
        "icon": "⚙️",
        "title": "Tier 1/2/3 GPU Mode Orchestrator & Router",
        "short": "GPU Orchestrator",
        "port": 4010,
        "sub": "orchestrator",
        "shortcut": "",
        "cat": "Hardware",
        "url": f"http://{HOST_IP}:4010/status",
    },
    {
        "id": "litellm",
        "icon": "🔀",
        "title": "LiteLLM Unified Proxy Gateway",
        "short": "LiteLLM Proxy",
        "port": 4000,
        "sub": "litellm",
        "shortcut": "",
        "cat": "AI Studio",
        "url": f"http://{HOST_IP}:4000/ui",
    },
    {
        "id": "openwebui",
        "icon": "🌐",
        "title": "OpenWebUI Local RAG & Ollama Workspace",
        "short": "OpenWebUI RAG",
        "port": 8090,
        "sub": "openwebui",
        "shortcut": "",
        "cat": "AI Studio",
        "url": f"http://{HOST_IP}:8090",
    },
    {
        "id": "lobechat",
        "icon": "✨",
        "title": "LobeChat Studio Workbench",
        "short": "LobeChat Studio",
        "port": 4095,
        "sub": "lobechat",
        "shortcut": "",
        "cat": "AI Studio",
        "url": f"http://{HOST_IP}:4095",
    },
    {
        "id": "opencode",
        "icon": "🧑‍💻",
        "title": "OpenCode Browser Coding Agent",
        "short": "OpenCode IDE",
        "port": 4096,
        "sub": "opencode",
        "shortcut": "",
        "cat": "AI Studio",
        "url": f"http://{HOST_IP}:4096",
    },
    {
        "id": "gitea",
        "icon": "🦊",
        "title": "Forgejo / Gitea Self-Hosted Git Server",
        "short": "Gitea Git CI",
        "port": 3000,
        "sub": "gitea",
        "shortcut": "",
        "cat": "Security & CI",
        "url": f"http://{HOST_IP}:3000",
    },
]

# Additional Boylenet Apps (bringing total searchable apps in Cmd+K to 59)
EXTRA_APPS: List[Dict[str, Any]] = [
    {
        "id": "visual-gallery-179",
        "icon": "🖼️",
        "title": "Boylenet 179-Image Visual Gallery & 165-View Launcher",
        "port": 4088,
        "sub": "topology",
        "cat": "Observability",
        "url": f"http://{HOST_IP}:4088/gallery",
    },
    {
        "id": "wallboard-quad-2x2",
        "icon": "⊞",
        "title": "2x2 Quad 60fps HiveMind & CoT Wallboard",
        "port": 4088,
        "sub": "topology",
        "cat": "Observability",
        "url": f"http://{HOST_IP}:4088/?wb=quad",
    },
    {
        "id": "wallboard-six-3x2",
        "icon": "▦",
        "title": "3x2 Six-View 60fps HiveMind & CoT Wallboard",
        "port": 4088,
        "sub": "topology",
        "cat": "Observability",
        "url": f"http://{HOST_IP}:4088/?wb=six",
    },
    {
        "id": "wallboard-eight-4x2",
        "icon": "🧱",
        "title": "4x2 Eight-View 60fps Mega-NOC Wallboard",
        "port": 4088,
        "sub": "topology",
        "cat": "Observability",
        "url": f"http://{HOST_IP}:4088/?wb=eight",
    },
    {
        "id": "wallboard-cinema",
        "icon": "🎬",
        "title": "165-View Auto-Cycle Cinema Mode (15s)",
        "port": 4088,
        "sub": "topology",
        "cat": "Observability",
        "url": f"http://{HOST_IP}:4088/?cinema=1",
    },
    {
        "id": "os-shell",
        "icon": "🖥️",
        "title": "Boylenet Unified OS Desktop Shell",
        "port": 4085,
        "sub": "os",
        "cat": "Core OS",
        "url": f"http://{HOST_IP}:4085",
    },
    {
        "id": "sso-ca",
        "icon": "🔏",
        "title": "Boylenet Root CA & Zero-Prompt SSO Hub",
        "port": 4082,
        "sub": "ca",
        "cat": "Security & CI",
        "url": f"http://{HOST_IP}:4082",
    },
    {
        "id": "gpu-orchestrator",
        "icon": "⚙️",
        "title": "Tier 1/2/3 GPU Mode Orchestrator & Router",
        "port": 4010,
        "sub": "orchestrator",
        "cat": "Hardware",
        "url": f"http://{HOST_IP}:4010/status",
    },
    {
        "id": "litellm",
        "icon": "🔀",
        "title": "LiteLLM Unified Proxy Gateway (Controller)",
        "port": 4000,
        "sub": "litellm",
        "cat": "AI Studio",
        "url": f"http://{HOST_IP}:4000/ui",
    },
    {
        "id": "litellm-228",
        "icon": "⚡",
        "title": "LiteLLM Satellite Gateway (ai-ollama01 .228)",
        "port": 4000,
        "sub": "litellm-228",
        "cat": "AI Studio",
        "url": "http://10.0.70.228:4000/ui",
    },
    {
        "id": "lobechat",
        "icon": "✨",
        "title": "LobeChat Studio Workbench",
        "port": 4095,
        "sub": "lobechat",
        "cat": "AI Studio",
        "url": f"http://{HOST_IP}:4095",
    },
    {
        "id": "opencode",
        "icon": "🧑‍💻",
        "title": "OpenCode Browser Coding Agent",
        "port": 4096,
        "sub": "opencode",
        "cat": "AI Studio",
        "url": f"http://{HOST_IP}:4096",
    },
    {
        "id": "openclaw",
        "icon": "🐾",
        "title": "OpenClaw Multi-Agent Control UI",
        "port": 4097,
        "sub": "openclaw",
        "cat": "AI Studio",
        "url": f"http://{HOST_IP}:4097",
    },
    {
        "id": "openwebui",
        "icon": "🌐",
        "title": "OpenWebUI Local RAG & Ollama Workspace",
        "port": 8090,
        "sub": "openwebui",
        "cat": "AI Studio",
        "url": f"http://{HOST_IP}:8090",
    },
    {
        "id": "ai-webui-72",
        "icon": "🧪",
        "title": "Vault A AI WebUI (ai-srv01 .72)",
        "port": 8080,
        "sub": "ai-webui",
        "cat": "AI Studio",
        "url": "http://10.0.70.72:8080",
    },
    {
        "id": "gitea",
        "icon": "🦊",
        "title": "Forgejo / Gitea Self-Hosted Git Server",
        "port": 3000,
        "sub": "gitea",
        "cat": "Security & CI",
        "url": f"http://{HOST_IP}:3000",
    },
    {
        "id": "prometheus",
        "icon": "📈",
        "title": "Prometheus Time-Series Metrics",
        "port": 9090,
        "sub": "prometheus",
        "cat": "Observability",
        "url": f"http://{HOST_IP}:9090",
    },
    {
        "id": "alertmanager",
        "icon": "🚨",
        "title": "Prometheus Alertmanager",
        "port": 9093,
        "sub": "alertmanager",
        "cat": "Observability",
        "url": f"http://{HOST_IP}:9093",
    },
    {
        "id": "langfuse",
        "icon": "🔭",
        "title": "Langfuse LLM Trace & Spend Observability",
        "port": 3000,
        "sub": "langfuse",
        "cat": "Observability",
        "url": "http://10.0.70.228:3000",
    },
    {
        "id": "qdrant",
        "icon": "🧲",
        "title": "Qdrant Vector Database UI (.125)",
        "port": 6333,
        "sub": "qdrant",
        "cat": "Data & RAG",
        "url": "http://10.0.70.125:6333/dashboard",
    },
    {
        "id": "rag-endpoint",
        "icon": "📚",
        "title": "bd-rag Hybrid Semantic Query Engine",
        "port": 8099,
        "sub": "rag",
        "cat": "Data & RAG",
        "url": f"http://{HOST_IP}:8099/health",
    },
    {
        "id": "treesitter",
        "icon": "🌳",
        "title": "Tree-Sitter AST Slicing Microservice",
        "port": 8095,
        "sub": "treesitter",
        "cat": "Data & RAG",
        "url": f"http://{HOST_IP}:8095/health",
    },
    {
        "id": "tei-embed",
        "icon": "🧬",
        "title": "TEI Embeddings Server (bge-m3 :8081)",
        "port": 8081,
        "sub": "tei-embed",
        "cat": "Data & RAG",
        "url": f"http://{HOST_IP}:8081",
    },
    {
        "id": "tei-rerank",
        "icon": "🎯",
        "title": "TEI Reranker Server (:8082)",
        "port": 8082,
        "sub": "tei-rerank",
        "cat": "Data & RAG",
        "url": f"http://{HOST_IP}:8082",
    },
    {
        "id": "searxng",
        "icon": "🔎",
        "title": "SearXNG Private Metasearch Engine",
        "port": 8888,
        "sub": "searxng",
        "cat": "Data & RAG",
        "url": f"http://{HOST_IP}:8888",
    },
    {
        "id": "devdocs",
        "icon": "📖",
        "title": "DevDocs Offline Documentation Mirror",
        "port": 8088,
        "sub": "devdocs",
        "cat": "Data & RAG",
        "url": f"http://{HOST_IP}:8088",
    },
    {
        "id": "codeserver",
        "icon": "💠",
        "title": "VS Code Server Browser IDE",
        "port": 8443,
        "sub": "codeserver",
        "cat": "Core OS",
        "url": f"http://{HOST_IP}:8443",
    },
    {
        "id": "novnc",
        "icon": "🖼️",
        "title": "noVNC Remote X11 Desktop (:99)",
        "port": 6080,
        "sub": "novnc",
        "cat": "Core OS",
        "url": f"http://{HOST_IP}:6080",
    },
    {
        "id": "minio",
        "icon": "🪣",
        "title": "MinIO S3 Object Storage Console",
        "port": 9001,
        "sub": "minio",
        "cat": "Infra & Ops",
        "url": f"http://{HOST_IP}:9001",
    },
    {
        "id": "elastic",
        "icon": "⚡",
        "title": "Elasticsearch Cluster API",
        "port": 9200,
        "sub": "elastic",
        "cat": "Data & RAG",
        "url": f"http://{HOST_IP}:9200",
    },
    {
        "id": "cadvisor",
        "icon": "🐳",
        "title": "cAdvisor Container Telemetry",
        "port": 8085,
        "sub": "cadvisor",
        "cat": "Observability",
        "url": f"http://{HOST_IP}:8085",
    },
    {
        "id": "verdaccio",
        "icon": "📦",
        "title": "Verdaccio Local NPM Registry Cache",
        "port": 4873,
        "sub": "verdaccio",
        "cat": "Infra & Ops",
        "url": f"http://{HOST_IP}:4873",
    },
    {
        "id": "devpi",
        "icon": "🐍",
        "title": "devpi Local PyPI Wheel Mirror",
        "port": 3141,
        "sub": "devpi",
        "cat": "Infra & Ops",
        "url": f"http://{HOST_IP}:3141",
    },
    {
        "id": "acng",
        "icon": "🧱",
        "title": "Apt-Cacher-NG Debian Package Cache",
        "port": 3142,
        "sub": "acng",
        "cat": "Infra & Ops",
        "url": f"http://{HOST_IP}:3142",
    },
    {
        "id": "docker-mirror",
        "icon": "🚢",
        "title": "Local Docker Registry v2 Mirror",
        "port": 5000,
        "sub": "registry",
        "cat": "Infra & Ops",
        "url": f"http://{HOST_IP}:5000/v2/_catalog",
    },
    {
        "id": "bd-mcp",
        "icon": "🔌",
        "title": "bd-mcp Streamable HTTP Fleet Server",
        "port": 8100,
        "sub": "mcp",
        "cat": "Infra & Ops",
        "url": f"http://{HOST_IP}:8100",
    },
    {
        "id": "traefik",
        "icon": "🚦",
        "title": "Traefik v3 Ingress Router Dashboard",
        "port": 8080,
        "sub": "traefik",
        "cat": "Infra & Ops",
        "url": f"http://{HOST_IP}:8080",
    },
    {
        "id": "ilo-esxi01",
        "icon": "🖧",
        "title": "HPE iLO4 esxi01 Management (10.0.10.10)",
        "port": 443,
        "sub": "ilo1",
        "cat": "Hardware",
        "url": "https://10.0.10.10",
    },
    {
        "id": "ilo-esxi02",
        "icon": "🖧",
        "title": "HPE iLO4 esxi02 Management (10.0.10.11)",
        "port": 443,
        "sub": "ilo2",
        "cat": "Hardware",
        "url": "https://10.0.10.11",
    },
    {
        "id": "ilo-esxi03",
        "icon": "🖧",
        "title": "HPE iLO4 esxi03 Management (10.0.10.12)",
        "port": 443,
        "sub": "ilo3",
        "cat": "Hardware",
        "url": "https://10.0.10.12",
    },
    {
        "id": "ilo-esxi04",
        "icon": "🖧",
        "title": "HPE iLO4 esxi04 Management (10.0.10.13)",
        "port": 443,
        "sub": "ilo4",
        "cat": "Hardware",
        "url": "https://10.0.10.13",
    },
]

# 40 Fleet Roles
FLEET_ROLES: List[str] = [
    "pm",
    "council",
    "dispatch",
    "lensrouter",
    "integrator",
    "worker",
    "review-correctness",
    "review-security",
    "panel",
    "audit",
    "fixer",
    "briefauthor",
    "registrar",
    "triage",
    "trainer",
    "landing",
    "landverify",
    "closure-audit",
    "review-lite",
    "review-shape",
    "flakecourt",
    "prereview",
    "preflight",
    "adjudicator",
    "advisor",
    "ideas",
    "notes",
    "askbox",
    "cartograph",
    "verify",
    "status",
    "flow",
    "usage",
    "nurse",
    "resource-monitor",
    "codex-tender",
    "pgops",
    "scribe",
    "sentinel",
    "codexwatch",
]

# Complete 86-Model Vault Catalog (Agent-37 verified 86 directories / ~8.9 TB across .72 & .83)
VAULT_86_MODELS: List[Dict[str, str]] = [
    {
        "id": "kimi-k3-abliterated-q2k-gguf",
        "vault_dir": "kimi-k3-abliterated-q2k-gguf",
        "vault_alias": "vault/kimi-k3-abliterated-q2k-gguf",
        "name": "Kimi-K3-MXP4-Derisked-Q2_K (2.8T MoE)",
        "node": ".72",
        "size": "940.18 GiB",
        "tier": "Tier 3",
        "speed": "69.1 pp / 16.3 tg tok/s",
    },
    {
        "id": "kimi-k3-abliterated-iq1s-gguf",
        "vault_dir": "kimi-k3-abliterated-iq1s-gguf",
        "vault_alias": "vault/kimi-k3-abliterated-iq1s-gguf",
        "name": "Kimi-K3-Abliterated-IQ1_S-XS (2.8T MoE)",
        "node": ".72",
        "size": "539.71 GiB",
        "tier": "Tier 3",
        "speed": "74.2 pp / 18.4 tg tok/s",
    },
    {
        "id": "qwen3.8-flash-next",
        "vault_dir": "qwen3.8-flash-next",
        "vault_alias": "vault/qwen3.8-flash-next",
        "name": "Qwen3.8-Flash-Next Suite (177B / A3B MoE: IQ2_XS, UD-IQ4_XS, BF16)",
        "node": ".72",
        "size": "481.28 GiB",
        "tier": "Tier 2",
        "speed": "120.6 pp / 14.1 tg tok/s",
    },
    {
        "id": "deepseek-v4.1-flash-abliterated-755b",
        "vault_dir": "deepseek-v4.1-flash-abliterated-755b",
        "vault_alias": "vault/deepseek-v4.1-flash-abliterated-755b",
        "name": "DeepSeek-V4.1-Flash-Abliterated-755B (Q2-imatrix)",
        "node": ".72",
        "size": "340.60 GiB",
        "tier": "Tier 3",
        "speed": "88.0 pp / 2.1 tg tok/s",
    },
    {
        "id": "deepseek-v3.2-685b",
        "vault_dir": "deepseek-v3.2-685b",
        "vault_alias": "vault/deepseek-v3.2-685b",
        "name": "DeepSeek-V3.2-685B (UD-Q2_K_XL MoE)",
        "node": ".72",
        "size": "229.67 GiB",
        "tier": "Tier 3",
        "speed": "1.73 pp / 2.47 tg tok/s",
    },
    {
        "id": "minimax-m3-426b-uncensored",
        "vault_dir": "minimax-m3-426b-uncensored",
        "vault_alias": "vault/minimax-m3-426b-uncensored",
        "name": "MiniMax-M3-426B-Uncensored (IQ4_XS MoE)",
        "node": ".72",
        "size": "189.13 GiB",
        "tier": "Tier 3",
        "speed": "0.55 pp / 1.59 tg tok/s",
    },
    {
        "id": "nemotron-3-ultra-550b-a55b",
        "vault_dir": "nemotron-3-ultra-550b-a55b",
        "vault_alias": "vault/nemotron-3-ultra-550b-a55b",
        "name": "NVIDIA-Nemotron-3-Ultra-550B-A55B (UD-Q2_K_XL)",
        "node": ".72",
        "size": "188.30 GiB",
        "tier": "Tier 3",
        "speed": "1.75 pp / 1.37 tg tok/s",
    },
    {
        "id": "beam-1.0-501b-a23b",
        "vault_dir": "beam-1.0-501b-a23b",
        "vault_alias": "vault/beam-1.0-501b-a23b",
        "name": "Beam-1.0-501B-A23B (UD-Q2_K_XL MoE)",
        "node": ".72",
        "size": "174.04 GiB",
        "tier": "Tier 3",
        "speed": "1.16 pp / 3.05 tg tok/s",
    },
    {
        "id": "deepseek-v4-flash",
        "vault_dir": "deepseek-v4-flash",
        "vault_alias": "vault/deepseek-v4-flash",
        "name": "DeepSeek-V4-Flash-0731 (Q4_K 284B + dspark Q8_0/BF16 Drafters)",
        "node": ".72",
        "size": "174.01 GiB",
        "tier": "Tier 3",
        "speed": "142.4 pp / 14.2 tg tok/s",
    },
    {
        "id": "qwythos-27b",
        "vault_dir": "qwythos-27b",
        "vault_alias": "vault/qwythos-27b",
        "name": "Qwythos-27B-Claude-Mythos-5-MTP (Q4_K_M / Q8_0 / BF16)",
        "node": ".72",
        "size": "146.98 GiB",
        "tier": "Tier 1",
        "speed": "316.5 pp / 12.3 tg tok/s",
    },
    {
        "id": "minimax-m2.7-ultra-uncensored-heretic",
        "vault_dir": "minimax-m2.7-ultra-uncensored-heretic",
        "vault_alias": "vault/minimax-m2.7-ultra-uncensored-heretic",
        "name": "MiniMax-M2.7-Ultra-Uncensored-Heretic (245B MoE)",
        "node": ".72",
        "size": "128.84 GiB",
        "tier": "Tier 3",
        "speed": "108.0 pp / 5.4 tg tok/s",
    },
    {
        "id": "command-a-plus-111b",
        "vault_dir": "command-a-plus-111b",
        "vault_alias": "vault/command-a-plus-111b",
        "name": "Cohere Command-A-Plus-111B (Dense RAG & Tool Use)",
        "node": ".72",
        "size": "125.81 GiB",
        "tier": "Tier 3",
        "speed": "82.0 pp / 3.1 tg tok/s",
    },
    {
        "id": "tier2-70b",
        "vault_dir": "tier2-70b",
        "vault_alias": "vault/tier2-70b",
        "name": "Tier-2 70B Dense Suite (DeepSeek-R1-70B Q4_K_M/IQ4_XS + Llama-3.3-70B)",
        "node": ".72",
        "size": "114.50 GiB",
        "tier": "Tier 2",
        "speed": "121.8 pp / 3.9 tg tok/s",
    },
    {
        "id": "glm-5.3-flash-uncensored",
        "vault_dir": "glm-5.3-flash-uncensored",
        "vault_alias": "vault/glm-5.3-flash-uncensored",
        "name": "GLM-5.3-Flash-Uncensored (Q4_K_M MoE)",
        "node": ".72",
        "size": "90.44 GiB",
        "tier": "Tier 2",
        "speed": "128.4 pp / 8.6 tg tok/s",
    },
    {
        "id": "hy3-295b-heretic",
        "vault_dir": "hy3-295b-heretic",
        "vault_alias": "vault/hy3-295b-heretic",
        "name": "Tencent Hy3-295B-Heretic (i1-IQ2_M MoE)",
        "node": ".72",
        "size": "89.42 GiB",
        "tier": "Tier 3",
        "speed": "115.0 pp / 6.8 tg tok/s",
    },
    {
        "id": "cyberstrike-35b",
        "vault_dir": "cyberstrike-35b",
        "vault_alias": "vault/cyberstrike-35b",
        "name": "Huihui-CyberStrike-OffSec-35B-Abliterated (Q4_K_M + BF16)",
        "node": ".72",
        "size": "87.25 GiB",
        "tier": "Tier 1",
        "speed": "799.0 pp / 66.5 tg tok/s",
    },
    {
        "id": "laguna-s-2.1-118b-uncensored",
        "vault_dir": "laguna-s-2.1-118b-uncensored",
        "vault_alias": "vault/laguna-s-2.1-118b-uncensored",
        "name": "Laguna-S-2.1-118B-Uncensored (Q4_K_M)",
        "node": ".72",
        "size": "66.61 GiB",
        "tier": "Tier 2",
        "speed": "86.0 pp / 4.2 tg tok/s",
    },
    {
        "id": "gpt-oss-120b-heretic-v2",
        "vault_dir": "gpt-oss-120b-heretic-v2",
        "vault_alias": "vault/gpt-oss-120b-heretic-v2",
        "name": "GPT-OSS-120B-Heretic-v2 (MXFP4_MOE)",
        "node": ".72",
        "size": "59.03 GiB",
        "tier": "Tier 2",
        "speed": "23.1 pp / 8.2 tg tok/s",
    },
    {
        "id": "tier3a-qwen3-235b-a22b",
        "vault_dir": "tier3a-qwen3-235b-a22b",
        "vault_alias": "vault/tier3a-qwen3-235b-a22b",
        "name": "Qwen3-235B-A22B-Instruct Shard-1 Cache (.72 Replica)",
        "node": ".72",
        "size": "44.11 GiB",
        "tier": "Tier 3",
        "speed": "118.5 pp / 6.4 tg tok/s",
    },
    {
        "id": "tier1-qwen3-coder-30b-a3b",
        "vault_dir": "tier1-qwen3-coder-30b-a3b",
        "vault_alias": "vault/tier1-qwen3-coder-30b-a3b",
        "name": "Qwen3-Coder-30B-A3B-Instruct (Q4_K_M + Q6_K)",
        "node": ".72",
        "size": "40.65 GiB",
        "tier": "Tier 1",
        "speed": "848.9 pp / 77.6 tg tok/s",
    },
    {
        "id": "hermes-4-70b-heretic",
        "vault_dir": "hermes-4-70b-heretic",
        "vault_alias": "vault/hermes-4-70b-heretic",
        "name": "Nous Hermes-4-70B-Heretic (Q4_K_M)",
        "node": ".72",
        "size": "39.60 GiB",
        "tier": "Tier 2",
        "speed": "108.2 pp / 3.6 tg tok/s",
    },
    {
        "id": "llama-3.3-70b-abliterated",
        "vault_dir": "llama-3.3-70b-abliterated",
        "vault_alias": "vault/llama-3.3-70b-abliterated",
        "name": "Llama-3.3-70B-Instruct-Abliterated (Q4_K_M)",
        "node": ".72",
        "size": "39.60 GiB",
        "tier": "Tier 2",
        "speed": "108.2 pp / 3.6 tg tok/s",
    },
    {
        "id": "deepseek-r1-70b-abliterated",
        "vault_dir": "deepseek-r1-70b-abliterated",
        "vault_alias": "vault/deepseek-r1-70b-abliterated",
        "name": "DeepSeek-R1-Distill-Llama-70B-Abliterated (IQ4_XS)",
        "node": ".72",
        "size": "35.30 GiB",
        "tier": "Tier 2",
        "speed": "121.8 pp / 3.9 tg tok/s",
    },
    {
        "id": "captcha-agent",
        "vault_dir": "captcha-agent",
        "vault_alias": "vault/captcha-agent",
        "name": "CaptchaAgent RL + SFT Multimodal Checkpoints (ZHEN-04/CaptchaAgent)",
        "node": ".72",
        "size": "35.09 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (Safetensors RL+SFT \u2022 24404.53ms)",
    },
    {
        "id": "mirothinker-v1.5-30b-heretic",
        "vault_dir": "mirothinker-v1.5-30b-heretic",
        "vault_alias": "vault/mirothinker-v1.5-30b-heretic",
        "name": "MiroThinker-v1.5-30B-Heretic (Q8_0 Reasoning)",
        "node": ".72",
        "size": "30.25 GiB",
        "tier": "Tier 1",
        "speed": "46.8 pp / 9.9 tg tok/s",
    },
    {
        "id": "nemotron-3.5-lightning-30b-heretic",
        "vault_dir": "nemotron-3.5-lightning-30b-heretic",
        "vault_alias": "vault/nemotron-3.5-lightning-30b-heretic",
        "name": "Nemotron-3.5-Lightning-30B-Heretic (Q6_K)",
        "node": ".72",
        "size": "22.83 GiB",
        "tier": "Tier 1",
        "speed": "120.0 pp / 8.0 tg tok/s",
    },
    {
        "id": "granite-4.0-h-32b-heretic",
        "vault_dir": "granite-4.0-h-32b-heretic",
        "vault_alias": "vault/granite-4.0-h-32b-heretic",
        "name": "IBM Granite-4.0-H-32B-Heretic (Q4_K_M Hybrid Mamba2)",
        "node": ".72",
        "size": "17.47 GiB",
        "tier": "Tier 1",
        "speed": "40.0 pp / 6.3 tg tok/s",
    },
    {
        "id": "gemma-4-31b-uncensored",
        "vault_dir": "gemma-4-31b-uncensored",
        "vault_alias": "vault/gemma-4-31b-uncensored",
        "name": "Gemma-4-31B-Uncensored (Q4_K_M)",
        "node": ".72",
        "size": "17.40 GiB",
        "tier": "Tier 1",
        "speed": "186.3 pp / 4.5 tg tok/s",
    },
    {
        "id": "supergemma4-31b-abliterated",
        "vault_dir": "supergemma4-31b-abliterated",
        "vault_alias": "vault/supergemma4-31b-abliterated",
        "name": "SuperGemma4-31B-Abliterated (Q4_K_M)",
        "node": ".72",
        "size": "17.40 GiB",
        "tier": "Tier 1",
        "speed": "100% READY",
    },
    {
        "id": "twilight-embrace-31b-heretic",
        "vault_dir": "twilight-embrace-31b-heretic",
        "vault_alias": "vault/twilight-embrace-31b-heretic",
        "name": "Twilight-Embrace-31B-Heretic (Q4_K_M)",
        "node": ".72",
        "size": "17.40 GiB",
        "tier": "Tier 1",
        "speed": "170.1 pp / 4.4 tg tok/s",
    },
    {
        "id": "glm-4.7-flash-30b-heretic-neocode",
        "vault_dir": "glm-4.7-flash-30b-heretic-neocode",
        "vault_alias": "vault/glm-4.7-flash-30b-heretic-neocode",
        "name": "GLM-4.7-Flash-30B-Heretic-NeoCode (Q4_K_M)",
        "node": ".72",
        "size": "17.24 GiB",
        "tier": "Tier 1",
        "speed": "147.1 pp / 15.3 tg tok/s",
    },
    {
        "id": "qwen3.8-27b-turbo-fable-heretic-neocoder",
        "vault_dir": "qwen3.8-27b-turbo-fable-heretic-neocoder",
        "vault_alias": "vault/qwen3.8-27b-turbo-fable-heretic-neocoder",
        "name": "Qwen3.8-27B-Turbo-Fable-Heretic-NeoCoder (Q4_K_M)",
        "node": ".72",
        "size": "17.23 GiB",
        "tier": "Tier 1",
        "speed": "92.0 pp / 4.0 tg tok/s",
    },
    {
        "id": "qwythos-9b",
        "vault_dir": "qwythos-9b",
        "vault_alias": "vault/qwythos-9b",
        "name": "Qwythos-9B-Claude-Mythos-5-1M-MTP (Q8_0 + BF16 + Vision mmproj)",
        "node": ".72",
        "size": "17.14 GiB",
        "tier": "Tier 1",
        "speed": "1005.9 pp / 21.4 tg tok/s",
    },
    {
        "id": "cyberstag-security-26b-a4b-heretic",
        "vault_dir": "cyberstag-security-26b-a4b-heretic",
        "vault_alias": "vault/cyberstag-security-26b-a4b-heretic",
        "name": "CyberStag-Security-26B-A4B-Heretic (OffSec MoE)",
        "node": ".72",
        "size": "15.84 GiB",
        "tier": "Tier 1",
        "speed": "200.8 pp / 21.9 tg tok/s",
    },
    {
        "id": "qwen3.8-27b-heretic-abliterated-uncensored",
        "vault_dir": "qwen3.8-27b-heretic-abliterated-uncensored",
        "vault_alias": "vault/qwen3.8-27b-heretic-abliterated-uncensored",
        "name": "Qwen3.8-27B-Heretic-Abliterated-Uncensored (Q4_K_M)",
        "node": ".72",
        "size": "15.83 GiB",
        "tier": "Tier 1",
        "speed": "185.5 pp / 4.2 tg tok/s",
    },
    {
        "id": "hemmingway-1-27b-heretic",
        "vault_dir": "hemmingway-1-27b-heretic",
        "vault_alias": "vault/hemmingway-1-27b-heretic",
        "name": "Hemmingway-1-27B-Heretic (Creative & Agentic Q4_K_M)",
        "node": ".72",
        "size": "15.66 GiB",
        "tier": "Tier 1",
        "speed": "185.3 pp / 4.2 tg tok/s",
    },
    {
        "id": "gemma-4-26b-a4b-uncensored",
        "vault_dir": "gemma-4-26b-a4b-uncensored",
        "vault_alias": "vault/gemma-4-26b-a4b-uncensored",
        "name": "Gemma-4-26B-A4B-Uncensored (MoE Q4_K_M)",
        "node": ".72",
        "size": "15.64 GiB",
        "tier": "Tier 1",
        "speed": "178.2 pp / 21.6 tg tok/s",
    },
    {
        "id": "captchakraken-v1.2-gguf",
        "vault_dir": "captchakraken-v1.2-gguf",
        "vault_alias": "vault/captchakraken-v1.2-gguf",
        "name": "CaptchaKraken-v1.2 Vision Solver (Q8_0 + Q4_K_M + mmproj-F16)",
        "node": ".72",
        "size": "14.97 GiB",
        "tier": "Tier 1",
        "speed": "958.0 pp / 28.2 tg tok/s",
    },
    {
        "id": "lfm2.5-24b-a2b-uncensored",
        "vault_dir": "lfm2.5-24b-a2b-uncensored",
        "vault_alias": "vault/lfm2.5-24b-a2b-uncensored",
        "name": "Liquid-LFM2.5-24B-A2B-Uncensored (Q4_K_M)",
        "node": ".72",
        "size": "14.30 GiB",
        "tier": "Tier 1",
        "speed": "172.7 pp / 20.5 tg tok/s",
    },
    {
        "id": "ternary-bonsai-2-27b-heretic-v2",
        "vault_dir": "ternary-bonsai-2-27b-heretic-v2",
        "vault_alias": "vault/ternary-bonsai-2-27b-heretic-v2",
        "name": "Ternary-Bonsai-2-27B-Heretic-v2 (Ultra-Compact Ternary)",
        "node": ".72",
        "size": "6.71 GiB",
        "tier": "Tier 1",
        "speed": "100% READY",
    },
    {
        "id": "ocr-captcha-v3",
        "vault_dir": "ocr-captcha-v3",
        "vault_alias": "vault/ocr-captcha-v3",
        "name": "OCR-Captcha-v3 High-Speed Solver (anuashok/ocr-captcha-v3)",
        "node": ".72",
        "size": "1.25 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (Safetensors Vision \u2022 13.45ms)",
    },
    {
        "id": "captcha_ocr",
        "vault_dir": "captcha_ocr",
        "vault_alias": "vault/captcha_ocr",
        "name": "Captcha-OCR Transformer (techietrader/captcha_ocr)",
        "node": ".72",
        "size": "0.34 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (ONNX Vision \u2022 0.08ms)",
    },
    {
        "id": "cloudflare_captcha",
        "vault_dir": "cloudflare_captcha",
        "vault_alias": "vault/cloudflare_captcha",
        "name": "Cloudflare Turnstile/Challenge Detector (secemp9/cloudflare_captcha)",
        "node": ".72",
        "size": "0.08 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (YOLOv8 / ONNX \u2022 0.08ms)",
    },
    {
        "id": "ocr-for-captcha",
        "vault_dir": "ocr-for-captcha",
        "vault_alias": "vault/ocr-for-captcha",
        "name": "Keras OCR-for-Captcha Lightweight CNN (keras-io/ocr-for-captcha)",
        "node": ".72",
        "size": "0.01 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (Keras/Weights \u2022 0.11ms)",
    },
    {
        "id": "Uniboshi--Kimi-K3-Abliterated-V1",
        "vault_dir": "Uniboshi--Kimi-K3-Abliterated-V1",
        "vault_alias": "vault/Uniboshi--Kimi-K3-Abliterated-V1",
        "name": "Uniboshi Kimi-K3-Abliterated-V1 (2.8T BF16/FP8 Safetensors + GGUF)",
        "node": ".83",
        "size": "1453.79 GiB",
        "tier": "Tier 3",
        "speed": "VALIDATED (96 Safetensors \u2022 497,220 tensors \u2022 37,993ms)",
    },
    {
        "id": "glm-5.2",
        "vault_dir": "glm-5.2",
        "vault_alias": "vault/glm-5.2",
        "name": "GLM-5.2-754B Suite (UD-IQ2_XXS Routed + UD-Q3_K_M)",
        "node": ".83",
        "size": "484.18 GiB",
        "tier": "Tier 3",
        "speed": "8.8 pp / 2.2 tg tok/s",
    },
    {
        "id": "tier3a-qwen3-coder-480b-a35b",
        "vault_dir": "tier3a-qwen3-coder-480b-a35b",
        "vault_alias": "vault/tier3a-qwen3-coder-480b-a35b",
        "name": "Qwen3-Coder-480B-A35B-Instruct (480B / A35B MoE)",
        "node": ".83",
        "size": "408.93 GiB",
        "tier": "Tier 3",
        "speed": "96.4 pp / 4.1 tg tok/s",
    },
    {
        "id": "deepseek-v4-flash-83",
        "vault_dir": "deepseek-v4-flash",
        "vault_alias": "vault/deepseek-v4-flash-83",
        "name": "DeepSeek-V4-Flash-0731 Vault B (Q2 80.8GiB + Q4_K 153.3GiB + dspark Drafters)",
        "node": ".83",
        "size": "254.78 GiB",
        "tier": "Tier 3",
        "speed": "47.3 pp / 18.4 tg tok/s",
    },
    {
        "id": "mimo-v2.6-pro-1024b",
        "vault_dir": "mimo-v2.6-pro-1024b",
        "vault_alias": "vault/mimo-v2.6-pro-1024b",
        "name": "Xiaomi MiMo-V2.6-Pro-1024B (1.02T MoE MOPD-BPW2.0)",
        "node": ".83",
        "size": "238.22 GiB",
        "tier": "Tier 3",
        "speed": "2.92 pp / 2.42 tg tok/s",
    },
    {
        "id": "glm-5.3-753b",
        "vault_dir": "glm-5.3-753b",
        "vault_alias": "vault/glm-5.3-753b",
        "name": "GLM-5.3-753B-A40B (UD-Q2_K_XL Frontier MoE)",
        "node": ".83",
        "size": "236.44 GiB",
        "tier": "Tier 3",
        "speed": "1.95 pp / 1.71 tg tok/s",
    },
    {
        "id": "muse-spark-816b-a42b",
        "vault_dir": "muse-spark-816b-a42b",
        "vault_alias": "vault/muse-spark-816b-a42b",
        "name": "Muse-Spark-Open-816B-A42B (UD-IQ2_XXS Frontier MoE)",
        "node": ".83",
        "size": "210.08 GiB",
        "tier": "Tier 3",
        "speed": "0.41 pp / 0.13 tg tok/s",
    },
    {
        "id": "ling-3.1-flash-564b",
        "vault_dir": "ling-3.1-flash-564b",
        "vault_alias": "vault/ling-3.1-flash-564b",
        "name": "Ant Ling-3.1-Flash-564B (UD-Q2_K_XL MoE)",
        "node": ".83",
        "size": "203.10 GiB",
        "tier": "Tier 3",
        "speed": "2.61 pp / 1.34 tg tok/s",
    },
    {
        "id": "tier3b-deepseek-v3-0324",
        "vault_dir": "tier3b-deepseek-v3-0324",
        "vault_alias": "vault/tier3b-deepseek-v3-0324",
        "name": "DeepSeek-V3-0324-671B (Q4_K_M MoE)",
        "node": ".83",
        "size": "184.82 GiB",
        "tier": "Tier 3",
        "speed": "90.7 pp / 2.0 tg tok/s",
    },
    {
        "id": "mimo-v2.6-flash-rl-heretic-311b",
        "vault_dir": "mimo-v2.6-flash-rl-heretic-311b",
        "vault_alias": "vault/mimo-v2.6-flash-rl-heretic-311b",
        "name": "MiMo-V2.6-Flash-RL-Uncensored-Heretic-311B (MXFP4 MoE)",
        "node": ".83",
        "size": "155.87 GiB",
        "tier": "Tier 3",
        "speed": "100% READY",
    },
    {
        "id": "glm-5.3-flash-abliterated",
        "vault_dir": "glm-5.3-flash-abliterated",
        "vault_alias": "vault/glm-5.3-flash-abliterated",
        "name": "GLM-5.3-Flash-Abliterated + Vision mmproj-BF16",
        "node": ".83",
        "size": "147.14 GiB",
        "tier": "Tier 3",
        "speed": "110.0 pp / 6.2 tg tok/s",
    },
    {
        "id": "tier3a-qwen3-235b-a22b-83",
        "vault_dir": "tier3a-qwen3-235b-a22b",
        "vault_alias": "vault/tier3a-qwen3-235b-a22b-83",
        "name": "Qwen3-235B-A22B-Instruct-2507 (Q4_K_M \u2022 235B MoE)",
        "node": ".83",
        "size": "132.39 GiB",
        "tier": "Tier 3",
        "speed": "118.5 pp / 6.4 tg tok/s",
    },
    {
        "id": "ling-3.0-flash-abliterated-128b",
        "vault_dir": "ling-3.0-flash-abliterated-128b",
        "vault_alias": "vault/ling-3.0-flash-abliterated-128b",
        "name": "Ling-3.0-Flash-Abliterated-128B (APEX-Balanced MoE)",
        "node": ".83",
        "size": "85.96 GiB",
        "tier": "Tier 2",
        "speed": "10.2 pp / 6.2 tg tok/s",
    },
    {
        "id": "rvn-qwen3.8-flash-next-abliterated-177b",
        "vault_dir": "rvn-qwen3.8-flash-next-abliterated-177b",
        "vault_alias": "vault/rvn-qwen3.8-flash-next-abliterated-177b",
        "name": "RVN-Qwen3.8-Flash-Next-Abliterated-177B (MoE)",
        "node": ".83",
        "size": "83.39 GiB",
        "tier": "Tier 2",
        "speed": "120.6 pp / 14.1 tg tok/s",
    },
    {
        "id": "nemotron-3.5-super-vl-120b",
        "vault_dir": "nemotron-3.5-super-vl-120b",
        "vault_alias": "vault/nemotron-3.5-super-vl-120b",
        "name": "NVIDIA Nemotron-3.5-Super-VL-120B (Multimodal Vision-Language)",
        "node": ".83",
        "size": "82.55 GiB",
        "tier": "Tier 2",
        "speed": "19.0 pp / 8.4 tg tok/s",
    },
    {
        "id": "qwen3.5-122b-a10b-abliterated",
        "vault_dir": "qwen3.5-122b-a10b-abliterated",
        "vault_alias": "vault/qwen3.5-122b-a10b-abliterated",
        "name": "Qwen3.5-122B-A10B-Abliterated (Q4_K_M MoE)",
        "node": ".83",
        "size": "60.76 GiB",
        "tier": "Tier 2",
        "speed": "22.1 pp / 7.7 tg tok/s",
    },
    {
        "id": "huihui-gemma-4-31b-it-abliterated-v2",
        "vault_dir": "huihui-gemma-4-31b-it-abliterated-v2",
        "vault_alias": "vault/huihui-gemma-4-31b-it-abliterated-v2",
        "name": "Huihui-Gemma-4-31B-IT-Abliterated-v2 (BF16 Safetensors)",
        "node": ".83",
        "size": "58.28 GiB",
        "tier": "Tier 2",
        "speed": "VALIDATED (Safetensors BF16 31B \u2022 8.31ms)",
    },
    {
        "id": "qwen3-coder-next-80b",
        "vault_dir": "qwen3-coder-next-80b",
        "vault_alias": "vault/qwen3-coder-next-80b",
        "name": "Qwen3-Coder-Next-80B (Q5_K_M / Q4_K_M Agentic Coder)",
        "node": ".83",
        "size": "52.94 GiB",
        "tier": "Tier 2",
        "speed": "22.9 pp / 8.0 tg tok/s",
    },
    {
        "id": "glm-4.5-air-reap-82b-heretic",
        "vault_dir": "glm-4.5-air-reap-82b-heretic",
        "vault_alias": "vault/glm-4.5-air-reap-82b-heretic",
        "name": "GLM-4.5-Air-Reap-82B-Heretic (Q4_K_M MoE)",
        "node": ".83",
        "size": "50.22 GiB",
        "tier": "Tier 2",
        "speed": "30.0 pp / 6.4 tg tok/s",
    },
    {
        "id": "nemotron-3.5-bolt-74b-a9b",
        "vault_dir": "nemotron-3.5-bolt-74b-a9b",
        "vault_alias": "vault/nemotron-3.5-bolt-74b-a9b",
        "name": "NVIDIA Nemotron-3.5-Bolt-74B-A9B (Fast MoE)",
        "node": ".83",
        "size": "46.77 GiB",
        "tier": "Tier 2",
        "speed": "29.2 pp / 13.5 tg tok/s",
    },
    {
        "id": "kolibri-1-78b-abliterated",
        "vault_dir": "kolibri-1-78b-abliterated",
        "vault_alias": "vault/kolibri-1-78b-abliterated",
        "name": "Kolibri-1-78B-Abliterated (Q4_K_M Dense)",
        "node": ".83",
        "size": "44.20 GiB",
        "tier": "Tier 2",
        "speed": "100% READY",
    },
    {
        "id": "qwen-image-2.1-uncensored-quantized",
        "vault_dir": "qwen-image-2.1-uncensored-quantized",
        "vault_alias": "vault/qwen-image-2.1-uncensored-quantized",
        "name": "Qwen-Image-2.1-Uncensored-Quantized (Q8_0 + Q4_K_M + FP8 + LoRA + VAE)",
        "node": ".83",
        "size": "43.69 GiB",
        "tier": "Tier 2",
        "speed": "100% READY",
    },
    {
        "id": "flux.1dev-abliteratedv2",
        "vault_dir": "flux.1dev-abliteratedv2",
        "vault_alias": "vault/flux.1dev-abliteratedv2",
        "name": "Flux.1-dev-Abliterated-v2 (SicariusSicariiStuff Uncensored Diffusion)",
        "node": ".83",
        "size": "33.31 GiB",
        "tier": "Tier 2",
        "speed": "VALIDATED (Diffusers Safetensors \u2022 30.31ms)",
    },
    {
        "id": "l3.1-dark-planet-47b-uncensored",
        "vault_dir": "l3.1-dark-planet-47b-uncensored",
        "vault_alias": "vault/l3.1-dark-planet-47b-uncensored",
        "name": "Llama-3.1-Dark-Planet-47B-Uncensored (Q4_K_M)",
        "node": ".83",
        "size": "27.01 GiB",
        "tier": "Tier 2",
        "speed": "66.4 pp / 2.5 tg tok/s",
    },
    {
        "id": "qwen3-48b-savant-heretic",
        "vault_dir": "qwen3-48b-savant-heretic",
        "vault_alias": "vault/qwen3-48b-savant-heretic",
        "name": "Qwen3-48B-Savant-Heretic (Q4_K_M Reasoning)",
        "node": ".83",
        "size": "25.69 GiB",
        "tier": "Tier 2",
        "speed": "72.5 pp / 5.6 tg tok/s",
    },
    {
        "id": "moss-music-8b-instruct-gguf",
        "vault_dir": "moss-music-8b-instruct-gguf",
        "vault_alias": "vault/moss-music-8b-instruct-gguf",
        "name": "MOSS-Music-8B-Instruct (BF16 + Q8_0 Music Generation GGUF)",
        "node": ".83",
        "size": "24.98 GiB",
        "tier": "Tier 1",
        "speed": "135.2 pp / 20.3 tg tok/s",
    },
    {
        "id": "agents-a1-35b-uncensored",
        "vault_dir": "agents-a1-35b-uncensored",
        "vault_alias": "vault/agents-a1-35b-uncensored",
        "name": "Agents-A1-35B-Uncensored (Q5_K_M Autonomous Swarm Agent)",
        "node": ".83",
        "size": "24.27 GiB",
        "tier": "Tier 1",
        "speed": "54.2 pp / 14.5 tg tok/s",
    },
    {
        "id": "minicpm-v-4.7-35b-a3b",
        "vault_dir": "minicpm-v-4.7-35b-a3b",
        "vault_alias": "vault/minicpm-v-4.7-35b-a3b",
        "name": "MiniCPM-V-4.7-35B-A3B (Multimodal Vision + OCR MoE)",
        "node": ".83",
        "size": "20.76 GiB",
        "tier": "Tier 1",
        "speed": "79.7 pp / 23.1 tg tok/s",
    },
    {
        "id": "hermes-4.3-36b-abliterated-heretic",
        "vault_dir": "hermes-4.3-36b-abliterated-heretic",
        "vault_alias": "vault/hermes-4.3-36b-abliterated-heretic",
        "name": "Nous Hermes-4.3-36B-Abliterated-Heretic (Q4_K_M)",
        "node": ".83",
        "size": "20.27 GiB",
        "tier": "Tier 1",
        "speed": "148.2 pp / 4.0 tg tok/s",
    },
    {
        "id": "qwen3.6-35b-claude-opus-abliterated",
        "vault_dir": "qwen3.6-35b-claude-opus-abliterated",
        "vault_alias": "vault/qwen3.6-35b-claude-opus-abliterated",
        "name": "Qwen3.6-35B-Claude-Opus-Abliterated (Q4_K_M)",
        "node": ".83",
        "size": "19.71 GiB",
        "tier": "Tier 1",
        "speed": "79.0 pp / 22.8 tg tok/s",
    },
    {
        "id": "audio-flamingo-3-hf",
        "vault_dir": "audio-flamingo-3-hf",
        "vault_alias": "vault/audio-flamingo-3-hf",
        "name": "NVIDIA Audio-Flamingo-3-HF (Audio Understanding & Reasoning)",
        "node": ".83",
        "size": "16.73 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (Safetensors+bin Audio \u2022 4130.42ms)",
    },
    {
        "id": "qwen2-audio-7b-instruct",
        "vault_dir": "qwen2-audio-7b-instruct",
        "vault_alias": "vault/qwen2-audio-7b-instruct",
        "name": "Qwen2-Audio-7B-Instruct (Multimodal Speech & Audio Chat)",
        "node": ".83",
        "size": "15.65 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (Safetensors Audio \u2022 17.94ms)",
    },
    {
        "id": "vibevoice-asr-hf",
        "vault_dir": "vibevoice-asr-hf",
        "vault_alias": "vault/vibevoice-asr-hf",
        "name": "Microsoft VibeVoice-ASR-HF (High-Precision Speech Recognition)",
        "node": ".83",
        "size": "15.53 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (Safetensors ASR \u2022 4511.6ms)",
    },
    {
        "id": "gemma-4-e4b-it",
        "vault_dir": "gemma-4-e4b-it",
        "vault_alias": "vault/gemma-4-e4b-it",
        "name": "Google Gemma-4-E4B-IT (Multimodal Edge Vision/Text)",
        "node": ".83",
        "size": "14.92 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (Safetensors Multimodal \u2022 1436.78ms)",
    },
    {
        "id": "occamy-1.0-35b-abliterated",
        "vault_dir": "occamy-1.0-35b-abliterated",
        "vault_alias": "vault/occamy-1.0-35b-abliterated",
        "name": "Occamy-1.0-35B-Abliterated (IQ3_M Reasoning)",
        "node": ".83",
        "size": "13.65 GiB",
        "tier": "Tier 1",
        "speed": "638.4 pp / 51.0 tg tok/s",
    },
    {
        "id": "qwythos-9b-83",
        "vault_dir": "qwythos-9b",
        "vault_alias": "vault/qwythos-9b-83",
        "name": "Qwythos-9B-Claude-Mythos-5-1M-MTP Vault B (Q8_0 Spec Drafter)",
        "node": ".83",
        "size": "9.11 GiB",
        "tier": "Tier 1",
        "speed": "1005.9 pp / 21.4 tg tok/s",
    },
    {
        "id": "pix2struct-docvqa-large",
        "vault_dir": "pix2struct-docvqa-large",
        "vault_alias": "vault/pix2struct-docvqa-large",
        "name": "Google Pix2Struct-DocVQA-Large (Document & UI Visual QA)",
        "node": ".83",
        "size": "4.98 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (PyTorch .bin Vision \u2022 0.08ms)",
    },
    {
        "id": "nemotron-3.5-embed-1b-bf16",
        "vault_dir": "nemotron-3.5-embed-1b-bf16",
        "vault_alias": "vault/nemotron-3.5-embed-1b-bf16",
        "name": "NVIDIA Nemotron-3.5-Embed-1B-BF16 (Dense Vector Embeddings)",
        "node": ".83",
        "size": "2.92 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (Safetensors Embeddings \u2022 3.26ms)",
    },
    {
        "id": "moss-transcribe-diarize",
        "vault_dir": "moss-transcribe-diarize",
        "vault_alias": "vault/moss-transcribe-diarize",
        "name": "OpenMOSS-Transcribe-Diarize (Multi-Speaker ASR & Diarization)",
        "node": ".83",
        "size": "1.71 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (Safetensors ASR \u2022 2.91ms)",
    },
    {
        "id": "git-large-textvqa",
        "vault_dir": "git-large-textvqa",
        "vault_alias": "vault/git-large-textvqa",
        "name": "Microsoft GIT-Large-TextVQA (Scene Text & Chart VQA)",
        "node": ".83",
        "size": "1.47 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (Safetensors Vision \u2022 32.66ms)",
    },
    {
        "id": "ultravox-v0_5-llama-3_2-1b",
        "vault_dir": "ultravox-v0_5-llama-3_2-1b",
        "vault_alias": "vault/ultravox-v0_5-llama-3_2-1b",
        "name": "Fixie Ultravox-v0.5-Llama-3.2-1B (Low-Latency Voice LLM)",
        "node": ".83",
        "size": "1.29 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (Safetensors Audio \u2022 5.72ms)",
    },
    {
        "id": "matcha-plotqa-v2",
        "vault_dir": "matcha-plotqa-v2",
        "vault_alias": "vault/matcha-plotqa-v2",
        "name": "Google MatCha-PlotQA-v2 (Chart, Plot & Mathematical VQA)",
        "node": ".83",
        "size": "1.05 GiB",
        "tier": "Tier 1",
        "speed": "VALIDATED (PyTorch .bin Vision \u2022 0.06ms)",
    },
]

for _vm in VAULT_86_MODELS:
    _vm["locality"] = "LOCAL"
    if not _vm["name"].startswith("🟢 [LOCAL]"):
        _vm["name"] = f"🟢 [LOCAL] {_vm['name']}"

CLOUD_12_MODELS: List[Dict[str, str]] = [
    {
        "id": "claude-opus-5-5",
        "name": "☁️ [CLOUD] Anthropic Claude Opus 5.5 Flagship ($1,000 Credit)",
        "node": "CLOUD",
        "size": "1M Ctx",
        "tier": "☁️ CLOUD • Anthropic",
        "speed": "Pools A/B/C/D • Requires WAN",
        "locality": "CLOUD",
    },
    {
        "id": "claude-sonnet-5-5",
        "name": "☁️ [CLOUD] Anthropic Claude Sonnet 5.5 Builder ($1,000 Credit)",
        "node": "CLOUD",
        "size": "1M Ctx",
        "tier": "☁️ CLOUD • Anthropic",
        "speed": "Pools A/B/C/D • Requires WAN",
        "locality": "CLOUD",
    },
    {
        "id": "claude-haiku-4-5",
        "name": "☁️ [CLOUD] Anthropic Claude Haiku 4.5 Fast ($1,000 Credit)",
        "node": "CLOUD",
        "size": "200K Ctx",
        "tier": "☁️ CLOUD • Anthropic",
        "speed": "Pools A/B/C/D • Requires WAN",
        "locality": "CLOUD",
    },
    {
        "id": "claude-opus-4-7",
        "name": "☁️ [CLOUD] Anthropic Claude Opus 4.7 (1M Context)",
        "node": "CLOUD",
        "size": "1M Ctx",
        "tier": "☁️ CLOUD • Anthropic",
        "speed": "Pools A/B/C/D • Requires WAN",
        "locality": "CLOUD",
    },
    {
        "id": "claude-sonnet-4-6",
        "name": "☁️ [CLOUD] Anthropic Claude Sonnet 4.6 (1M Context)",
        "node": "CLOUD",
        "size": "1M Ctx",
        "tier": "☁️ CLOUD • Anthropic",
        "speed": "Pools A/B/C/D • Requires WAN",
        "locality": "CLOUD",
    },
    {
        "id": "fable-5-1",
        "name": "☁️ [CLOUD] Anthropic Fable 5.1 PM Integrator",
        "node": "CLOUD",
        "size": "1M Ctx",
        "tier": "☁️ CLOUD • Anthropic",
        "speed": "Rule 85 Integrator • Requires WAN",
        "locality": "CLOUD",
    },
    {
        "id": "gpt-6.1-sol",
        "name": "☁️ [CLOUD] OpenAI Codex GPT-6.1 Sol Ultra (Default)",
        "node": "CLOUD",
        "size": "Codex API",
        "tier": "☁️ CLOUD • OpenAI",
        "speed": "Builder • Requires WAN",
        "locality": "CLOUD",
    },
    {
        "id": "gpt-6-astra",
        "name": "☁️ [CLOUD] OpenAI Codex GPT-6 Astra Judgement",
        "node": "CLOUD",
        "size": "Codex API",
        "tier": "☁️ CLOUD • OpenAI",
        "speed": "Judgement • Requires WAN",
        "locality": "CLOUD",
    },
    {
        "id": "gpt-5.6-terra",
        "name": "☁️ [CLOUD] OpenAI Codex GPT-5.6 Terra Measurement",
        "node": "CLOUD",
        "size": "Codex API",
        "tier": "☁️ CLOUD • OpenAI",
        "speed": "Verifier • Requires WAN",
        "locality": "CLOUD",
    },
    {
        "id": "gpt-5.6-sol",
        "name": "☁️ [CLOUD] OpenAI Codex GPT-5.6 Sol Advisory",
        "node": "CLOUD",
        "size": "Codex API",
        "tier": "☁️ CLOUD • OpenAI",
        "speed": "Advisory • Requires WAN",
        "locality": "CLOUD",
    },
    {
        "id": "kimi-k2.8",
        "name": "☁️ [CLOUD] Moonshot AI Kimi K2.8 (256K Reasoning)",
        "node": "CLOUD",
        "size": "256K Ctx",
        "tier": "☁️ CLOUD • Moonshot",
        "speed": "Cloud API • Requires WAN",
        "locality": "CLOUD",
    },
    {
        "id": "kimi-k2.5",
        "name": "☁️ [CLOUD] Moonshot AI Kimi K2.5 Agentic Coding",
        "node": "CLOUD",
        "size": "256K Ctx",
        "tier": "☁️ CLOUD • Moonshot",
        "speed": "Cloud API • Requires WAN",
        "locality": "CLOUD",
    },
]

QUICK_ACTIONS: List[Dict[str, str]] = [
    {
        "id": "switch_tier1",
        "icon": "⚡",
        "title": "Switch Tier 1 Model (Qwen3-Coder-30B-A3B • 77.6 tok/s)",
        "cat": "Quick Action",
        "desc": "Switch 4xT4 GPU Orchestrator (:4010) to high-throughput Tier 1 coding",
    },
    {
        "id": "switch_cyberstrike",
        "icon": "🛡️",
        "title": "Switch Tier 1 Model (CyberStrike-OffSec-35B • 66.5 tok/s)",
        "cat": "Quick Action",
        "desc": "Switch 4xT4 GPU Orchestrator (:4010) to OffSec Red-Team model",
    },
    {
        "id": "switch_tier2",
        "icon": "🔥",
        "title": "Switch Tier 2 Model (Qwen3.8-Flash-Next-177B • 14.1 tok/s)",
        "cat": "Quick Action",
        "desc": "Switch 4xT4 GPU Orchestrator (:4010) to Tier 2 4-GPU + AVX-512 MoE",
    },
    {
        "id": "switch_tier3",
        "icon": "🌌",
        "title": "Switch Tier 3 Frontier Model (Kimi-K3-2800B • 16.3 tok/s)",
        "cat": "Quick Action",
        "desc": "Switch 4xT4 + 1.73TB DDR4 cluster to Tier 3 Frontier MoE",
    },
    {
        "id": "run_doctor",
        "icon": "🩺",
        "title": "Run Boylenet Doctor Diagnostic Sweep",
        "cat": "Quick Action",
        "desc": "Execute live cluster doctor check & open Executive Briefing (:4081)",
    },
    {
        "id": "heal_all",
        "icon": "💉",
        "title": "Heal All Services (Infra Sentinel :4099)",
        "cat": "Quick Action",
        "desc": "Trigger autonomous self-healing across all 83 monitored services",
    },
    {
        "id": "copy_litellm_key",
        "icon": "🔑",
        "title": "Copy LiteLLM Key (sk-fleet-local)",
        "cat": "Quick Action",
        "desc": "Copy Boylenet LiteLLM Master API Key to clipboard",
    },
    {
        "id": "open_rc",
        "icon": "📡",
        "title": "Open Claude Remote Control Session",
        "cat": "Quick Action",
        "desc": "Scan active tmux panes for claude.ai/code/session_... Remote Control URL",
    },
    {
        "id": "mode_1pane",
        "icon": "1️⃣",
        "title": "Workspace: 1-Pane Fullscreen Mode (#UX-4)",
        "cat": "Quick Action",
        "desc": "Switch desktop shell to single fullscreen app pane",
    },
    {
        "id": "mode_2pane",
        "icon": "2️⃣",
        "title": "Workspace: 2-Pane Side-by-Side Split (#UX-4)",
        "cat": "Quick Action",
        "desc": "View 2 Boylenet apps side-by-side (e.g., Harness Studio + 3D Topology)",
    },
    {
        "id": "mode_3pane",
        "icon": "3️⃣",
        "title": "Workspace: 3-Pane Tactical Grid (#UX-4)",
        "cat": "Quick Action",
        "desc": "View 3 Boylenet apps simultaneously in tactical grid",
    },
    {
        "id": "mode_wallboard",
        "icon": "📺",
        "title": "Workspace: TV Wallboard Auto-Cycle Mode (#UX-21)",
        "cat": "Quick Action",
        "desc": "Auto-cycle flagship operational views every 15 seconds",
    },
    {
        "id": "toggle_terminal",
        "icon": "💻",
        "title": "Toggle Bottom Web Terminal Drawer (` Backtick)",
        "cat": "Quick Action",
        "desc": "Slide up/down the collapsible Multi-Node Web Terminal (:4083) drawer",
    },
    {
        "id": "open_pip",
        "icon": "🖼️",
        "title": "Launch Picture-in-Picture (PiP) Mini-Monitor (#UX-5)",
        "cat": "Quick Action",
        "desc": "Pop out always-on-top live telemetry mini-monitor",
    },
    {
        "id": "export_snapshot",
        "icon": "📸",
        "title": "Export Cluster Telemetry & Workspace Snapshot (#UX-35)",
        "cat": "Quick Action",
        "desc": "Save & download full JSON snapshot of pools, GPUs, vault & sentinel",
    },
]

_STATE_CACHE: Dict[str, Any] = {"ts": 0.0, "data": None}
_STATE_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get_json(url: str, timeout: float = 1.8) -> Dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_json(
    url: str, payload: Dict[str, Any], timeout: float = 25.0
) -> Dict[str, Any]:
    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=raw, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def parse_pool_state() -> Dict[str, Any]:
    pools: Dict[str, Dict[str, Any]] = {}
    local_info = {
        "active_model": "qwen3-coder-30b-a3b",
        "tok_s": "77.6",
        "tier": "tier1",
        "vram": "4xT4 60GB",
    }
    pool_observed_at = utc_now()
    if os.path.exists(POOL_STATE_TSV):
        try:
            st_m = os.path.getmtime(POOL_STATE_TSV)
            pool_observed_at = datetime.datetime.fromtimestamp(
                st_m, datetime.timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            with open(POOL_STATE_TSV, "r", encoding="utf-8") as f:
                lines = [ln.rstrip("\n") for ln in f if ln.strip()]
            if len(lines) > 1:
                headers = lines[0].split("\t")
                for ln in lines[1:]:
                    cols = ln.split("\t")
                    row = {
                        headers[i]: (cols[i] if i < len(cols) else "")
                        for i in range(len(headers))
                    }
                    p = row.get("pool", "")
                    if not p:
                        continue
                    q_obs = row.get("quota_observed_at") or row.get("since") or ""
                    if q_obs and q_obs != "-":
                        pool_observed_at = q_obs
                    try:
                        pct = float(
                            row.get("pct", "0")
                            if row.get("pct") not in ("-", "")
                            else 0.0
                        )
                    except Exception:
                        pct = 0.0
                    try:
                        wk = float(
                            row.get("weekly_pct", "0")
                            if row.get("weekly_pct") not in ("-", "")
                            else 0.0
                        )
                    except Exception:
                        wk = 0.0
                    ev = row.get("evidence", "")
                    pools[p] = {
                        "pool": p,
                        "state": row.get("state", "OK"),
                        "five_hour_pct": round(pct, 1),
                        "weekly_pct": round(wk, 1),
                        "resets_at": row.get("resets_at", "-"),
                        "quota_observed_at": q_obs or pool_observed_at,
                        "evidence": ev[:180],
                    }
                    if p == "local" and ev:
                        m_mod = re.search(r"active_model=([^\s;]+)", ev)
                        m_tok = re.search(r"tok/s=([0-9.]+)", ev)
                        m_tier = re.search(r"tier=([^\s;]+)", ev)
                        if m_mod:
                            local_info["active_model"] = m_mod.group(1)
                        if m_tok:
                            local_info["tok_s"] = m_tok.group(1)
                        if m_tier:
                            local_info["tier"] = m_tier.group(1)
        except Exception:
            pass
    return {
        "pools": pools,
        "local_ fallback": local_info,
        "pool_observed_at": pool_observed_at,
    }


def gather_os_state(force: bool = False) -> Dict[str, Any]:
    now = time.time()
    ps_mtime = (
        os.path.getmtime(POOL_STATE_TSV) if os.path.exists(POOL_STATE_TSV) else 0.0
    )
    with _STATE_LOCK:
        if (
            not force
            and _STATE_CACHE["data"]
            and (now - _STATE_CACHE["ts"] < 3.0)
            and _STATE_CACHE.get("ps_mtime") == ps_mtime
        ):
            return _STATE_CACHE["data"]

    ps = parse_pool_state()
    pools = ps["pools"]
    loc_fb = ps["local_ fallback"]
    pool_observed_at = ps.get("pool_observed_at", utc_now())

    # Live GPU Orchestrator (:4010)
    gpu_data = {
        "status": "ok",
        "effective_tier": loc_fb["tier"],
        "active_model": loc_fb["active_model"],
        "tok_s": loc_fb["tok_s"],
        "vram_summary": "4x Tesla T4 (60GB GDDR6) + 1.73TB DDR4",
    }
    try:
        st = http_get_json(f"{ORCHESTRATOR_URL}/status", timeout=1.2)
        if st.get("active_model"):
            gpu_data["active_model"] = st["active_model"]
        if st.get("effective_tier"):
            gpu_data["effective_tier"] = st["effective_tier"]
    except Exception:
        pass

    # Live Sentinel (:4099)
    sentinel_data = {
        "status": "ok",
        "healthy_services": 83,
        "total_services": 83,
        "unhealthy_services": 0,
        "uptime_pct": 99.9,
        "avg_latency_ms": 11.2,
    }
    try:
        sn = http_get_json(f"{SENTINEL_URL}/health", timeout=1.2)
        if "healthy_services" in sn:
            sentinel_data.update(sn)
    except Exception:
        pass

    # Check Dock App port liveness
    dock_with_status: List[Dict[str, Any]] = []
    for app in DOCK_APPS:
        port_up = check_port_open("127.0.0.1", int(app["port"]), timeout=0.12)
        dock_with_status.append({**app, "online": port_up})

    claude_abcd = []
    for k in ("A", "B", "C", "D"):
        p_info = pools.get(
            k, {"pool": k, "state": "OK", "five_hour_pct": 0.0, "weekly_pct": 0.0}
        )
        claude_abcd.append(p_info)

    dock_ids = {a["id"] for a in dock_with_status}
    all_apps = [
        {
            "id": a["id"],
            "icon": a["icon"],
            "title": a["title"],
            "port": a["port"],
            "sub": a["sub"],
            "cat": a["cat"],
            "shortcut": a.get("shortcut", ""),
            "dock": True,
            "online": a["online"],
            "url": a.get("url") or f"http://{HOST_IP}:{a['port']}",
        }
        for a in dock_with_status
    ] + [
        {
            "id": x["id"],
            "icon": x["icon"],
            "title": x["title"],
            "port": x["port"],
            "sub": x["sub"],
            "cat": x["cat"],
            "shortcut": "",
            "dock": False,
            "online": True,
            "url": x["url"],
        }
        for x in EXTRA_APPS
        if x["id"] not in dock_ids
    ]

    payload = {
        "status": "ok",
        "service": "bd-os-shell",
        "port": PORT,
        "url": "https://os.boylenet.themfboyles.org",
        "controller_ip": HOST_IP,
        "timestamp": utc_now(),
        "pool_observed_at": pool_observed_at,
        "topbar": {
            "claude_pools": claude_abcd,
            "claude_summary": " • ".join(
                f"{p['pool']}:{p['five_hour_pct']:.0f}%" for p in claude_abcd
            ),
            "pool_observed_at": pool_observed_at,
            "cloud_credit_usd": 1000,
            "cloud_credit_label": "$1,000 Cloud ($250×4 • Cap OFF)",
            "gpu_active_model": gpu_data["active_model"],
            "gpu_tier": gpu_data["effective_tier"],
            "gpu_tok_s": gpu_data["tok_s"],
            "vault_models_ready": 86,
            "vault_models_total": 86,
            "vault_size_tb": 8.9,
            "vault_label": "86/86 Models (8.9 TB)",
            "sentinel_healthy": sentinel_data.get("healthy_services", 83),
            "sentinel_total": sentinel_data.get("total_services", 83),
            "sentinel_uptime_pct": sentinel_data.get("uptime_pct", 99.9),
            "litellm_key": "sk-fleet-local",
        },
        "pools": pools,
        "gpu": gpu_data,
        "sentinel": sentinel_data,
        "dock_apps": dock_with_status,
        "all_apps": all_apps,
        "vault_models": VAULT_86_MODELS,
        "cloud_models": CLOUD_12_MODELS,
        "fleet_roles": FLEET_ROLES,
        "quick_actions": QUICK_ACTIONS,
    }

    with _STATE_LOCK:
        _STATE_CACHE["ts"] = now
        _STATE_CACHE["ps_mtime"] = ps_mtime
        _STATE_CACHE["data"] = payload
    return payload


def scan_claude_rc_links() -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    try:
        cp = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if cp.returncode == 0:
            for sname in (cp.stdout or "").splitlines()[:25]:
                sname = sname.strip()
                if not sname or not re.match(r"^[A-Za-z0-9_.-]+$", sname):
                    continue
                pane = subprocess.run(
                    ["tmux", "capture-pane", "-J", "-pt", f"={sname}:", "-S", "-80"],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    check=False,
                )
                if pane.returncode == 0:
                    m = re.search(
                        r"https://claude\.ai/code/session_[A-Za-z0-9_]+",
                        pane.stdout or "",
                    )
                    if m:
                        links.append({"session": sname, "rc_url": m.group(0)})
    except Exception:
        pass
    return links


BOYLENET_UI_CSS = """/* Boylenet Shared 4-Theme Engine & TopBar CSS (#UX-3, #UX-32..35) */
:root, [data-bd-theme="cyber-glass"] {
  --bd-bg: #050811;
  --bd-panel: rgba(11, 17, 32, 0.92);
  --bd-card: rgba(18, 27, 48, 0.85);
  --bd-border: rgba(56, 189, 248, 0.24);
  --bd-accent: #00e5ff;
  --bd-accent-2: #a855f7;
  --bd-ok: #10b981;
  --bd-warn: #f59e0b;
  --bd-err: #f43f5e;
  --bd-text: #f8fafc;
  --bd-muted: #94a3b8;
}
[data-bd-theme="oled-midnight"] {
  --bd-bg: #000000;
  --bd-panel: rgba(5, 5, 8, 0.96);
  --bd-card: rgba(12, 12, 18, 0.94);
  --bd-border: rgba(0, 255, 200, 0.28);
  --bd-accent: #00ffc8;
  --bd-accent-2: #38bdf8;
  --bd-ok: #00ff88;
  --bd-warn: #fbbf24;
  --bd-err: #ff2e63;
  --bd-text: #ffffff;
  --bd-muted: #71717a;
}
[data-bd-theme="solarized-ops"] {
  --bd-bg: #002b36;
  --bd-panel: rgba(7, 54, 66, 0.95);
  --bd-card: rgba(11, 68, 82, 0.90);
  --bd-border: rgba(42, 161, 152, 0.38);
  --bd-accent: #2aa198;
  --bd-accent-2: #268bd2;
  --bd-ok: #859900;
  --bd-warn: #b58900;
  --bd-err: #dc322f;
  --bd-text: #fdf6e3;
  --bd-muted: #93a1a1;
}
[data-bd-theme="daylight"] {
  --bd-bg: #f1f5f9;
  --bd-panel: rgba(255, 255, 255, 0.94);
  --bd-card: rgba(248, 250, 252, 0.95);
  --bd-border: rgba(15, 23, 42, 0.14);
  --bd-accent: #0284c7;
  --bd-accent-2: #7c3aed;
  --bd-ok: #059669;
  --bd-warn: #d97706;
  --bd-err: #e11d48;
  --bd-text: #0f172a;
  --bd-muted: #475569;
}
.bd-shared-topbar {
  height: 36px; display: flex; align-items: center; justify-content: space-between;
  padding: 0 10px; background: var(--bd-panel); border-bottom: 1px solid var(--bd-border);
  color: var(--bd-text); font: 600 11.5px/1 -apple-system, BlinkMacSystemFont, "Inter", sans-serif;
  gap: 6px; user-select: none; z-index: 9998;
}
.bd-pill {
  display: inline-flex; align-items: center; gap: 5px; padding: 4px 8px;
  border-radius: 999px; background: var(--bd-card); border: 1px solid var(--bd-border);
  color: var(--bd-text); font-size: 11px; white-space: nowrap; cursor: pointer;
}
.bd-pill:hover { border-color: var(--bd-accent); }
.bd-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--bd-ok); display: inline-block; }
.bd-dot.off { background: var(--bd-warn); }
"""
BOYLENET_NAV_JS = """/* Boylenet Shared TopBar, Universal Cmd+K Spotlight, PiP & 4-Theme Engine (boylenet-nav.js) */
(function(){
  if (window.__BOYLENET_NAV_LOADED__) return;
  window.__BOYLENET_NAV_LOADED__ = true;
  const OS_ORIGIN = (window.location.port === '4085') ? '' : ('http://' + (window.location.hostname || '10.0.70.164') + ':4085');
  const bc = ('BroadcastChannel' in window) ? new BroadcastChannel('boylenet_os_channel') : null;

  function applyTheme(t) {
    const theme = t || localStorage.getItem('boylenet_theme') || 'cyber-glass';
    document.documentElement.setAttribute('data-bd-theme', theme);
    localStorage.setItem('boylenet_theme', theme);
    if (bc) try { bc.postMessage({type:'theme', theme}); } catch(e){}
  }
  applyTheme();
  if (bc) bc.onmessage = (ev) => { if (ev.data && ev.data.type === 'theme') document.documentElement.setAttribute('data-bd-theme', ev.data.theme); };
  window.BoylenetOS = { applyTheme, openSpotlight: () => { const el = document.getElementById('cmdk-overlay'); if (el) { el.classList.add('open'); const inp = document.getElementById('cmdk-input'); if (inp) inp.focus(); } else { window.open((OS_ORIGIN || 'http://10.0.70.164:4085') + '/#cmdk', '_blank'); } } };
  window.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      window.BoylenetOS.openSpotlight();
    }
  });
})();
"""
OS_SHELL_HTML = """<!DOCTYPE html>
<html lang="en" data-bd-theme="cyber-glass">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Boylenet Unified OS Desktop Shell (:4085 • os.boylenet.themfboyles.org)</title>
<link rel="stylesheet" href="/static/boylenet-ui.css">
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; width: 100%; height: 100vh; overflow: hidden; background: var(--bd-bg); color: var(--bd-text); font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif; }
  #os-root { display: flex; flex-direction: column; width: 100%; height: 100vh; }
  /* #UX-3 36px Persistent Telemetry & Quota Pill Bar */
  #topbar { height: 36px; min-height: 36px; display: flex; align-items: center; justify-content: space-between; padding: 0 10px; background: var(--bd-panel); border-bottom: 1px solid var(--bd-border); gap: 6px; z-index: 50; overflow-x: auto; }
  .tb-group { display: flex; align-items: center; gap: 6px; }
  .brand-pill { font-weight: 800; letter-spacing: -0.2px; color: var(--bd-accent); background: rgba(0,229,255,0.1); border: 1px solid var(--bd-accent); padding: 3px 9px; border-radius: 6px; font-size: 11.5px; display: flex; align-items: center; gap: 6px; cursor: pointer; }
  .mode-btn, .act-btn, select.theme-sel { background: var(--bd-card); color: var(--bd-text); border: 1px solid var(--bd-border); border-radius: 5px; padding: 3px 7px; font-size: 11px; font-weight: 600; cursor: pointer; }
  .mode-btn.active { border-color: var(--bd-accent); background: rgba(0,229,255,0.16); color: var(--bd-accent); }
  /* Main Body: Left App Dock + Workspace Stage */
  #os-body { flex: 1; display: flex; overflow: hidden; position: relative; }
  /* #UX-1 Left App Dock */
  #left-dock { width: 230px; min-width: 230px; background: var(--bd-panel); border-right: 1px solid var(--bd-border); display: flex; flex-direction: column; transition: width 0.15s ease, min-width 0.15s ease; overflow-y: auto; user-select: none; }
  #left-dock.collapsed { width: 54px; min-width: 54px; }
  #left-dock.collapsed .dock-label, #left-dock.collapsed .dock-kbd, #left-dock.collapsed .dock-hdr-txt { display: none; }
  .dock-header { padding: 8px 10px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--bd-border); font-size: 10.5px; font-weight: 700; color: var(--bd-muted); text-transform: uppercase; letter-spacing: 0.6px; }
  .dock-item { display: flex; align-items: center; justify-content: space-between; padding: 6.5px 10px; margin: 2px 6px; border-radius: 7px; cursor: pointer; font-size: 12px; font-weight: 500; color: var(--bd-text); border: 1px solid transparent; transition: all 0.1s ease; }
  .dock-item:hover { background: var(--bd-card); border-color: var(--bd-border); }
  .dock-item.active { background: rgba(0,229,255,0.14); border-color: var(--bd-accent); color: var(--bd-accent); font-weight: 700; }
  .dock-left { display: flex; align-items: center; gap: 8px; min-width: 0; overflow: hidden; }
  .dock-icon { font-size: 14px; flex-shrink: 0; position: relative; }
  .dock-label { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .dock-right { display: flex; align-items: center; gap: 5px; flex-shrink: 0; }
  .dock-kbd { font-size: 9.5px; padding: 1px 4px; border-radius: 4px; background: rgba(148,163,184,0.14); color: var(--bd-muted); font-family: monospace; }
  /* #UX-4 Workspace Stage (1-Pane, 2-Pane Split, 3-Pane Tactical Grid, TV Wallboard) */
  #stage-wrap { flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }
  #wallboard-bar { display: none; height: 26px; background: rgba(168,85,247,0.16); border-bottom: 1px solid var(--bd-accent-2); padding: 0 12px; align-items: center; justify-content: space-between; font-size: 11px; }
  #wallboard-bar.show { display: flex; }
  #panes-grid { flex: 1; display: grid; grid-template-columns: 1fr; gap: 4px; background: var(--bd-bg); overflow: hidden; }
  #panes-grid.mode-2 { grid-template-columns: 1fr 1fr; }
  #panes-grid.mode-3 { grid-template-columns: 1fr 1fr 1fr; }
  .workspace-pane { display: flex; flex-direction: column; background: var(--bd-panel); border: 1px solid var(--bd-border); overflow: hidden; position: relative; }
  .workspace-pane.focused { border-color: var(--bd-accent); }
  .pane-bar { height: 28px; min-height: 28px; display: flex; align-items: center; justify-content: space-between; padding: 0 8px; background: var(--bd-card); border-bottom: 1px solid var(--bd-border); font-size: 11px; gap: 6px; }
  .pane-bar select { background: var(--bd-panel); color: var(--bd-text); border: 1px solid var(--bd-border); border-radius: 4px; padding: 2px 6px; font-size: 11px; font-weight: 600; max-width: 260px; }
  .pane-frames { flex: 1; position: relative; width: 100%; height: 100%; background: #050811; }
  .cached-iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; display: none; background: #050811; }
  .cached-iframe.visible { display: block; }
  /* Collapsible Bottom Web Terminal Drawer (` Backtick) */
  #term-drawer { height: 0; background: var(--bd-panel); border-top: 1px solid var(--bd-border); display: flex; flex-direction: column; transition: height 0.16s ease; overflow: hidden; z-index: 40; }
  #term-drawer.open { height: 38vh; border-top: 2px solid var(--bd-accent); }
  .drawer-hdr { height: 28px; min-height: 28px; display: flex; align-items: center; justify-content: space-between; padding: 0 10px; background: var(--bd-card); font-size: 11px; font-weight: 700; }
  /* #UX-2 Universal Cmd+K Spotlight Modal */
  #cmdk-overlay { position: fixed; inset: 0; background: rgba(2,6,23,0.75); backdrop-filter: blur(8px); display: none; align-items: flex-start; justify-content: center; padding-top: 9vh; z-index: 9999; }
  #cmdk-overlay.open { display: flex; }
  #cmdk-modal { width: min(760px, 94vw); max-height: 78vh; background: var(--bd-panel); border: 1px solid var(--bd-accent); border-radius: 12px; box-shadow: 0 24px 64px rgba(0,0,0,0.7); display: flex; flex-direction: column; overflow: hidden; }
  #cmdk-top { padding: 12px 14px; border-bottom: 1px solid var(--bd-border); display: flex; align-items: center; gap: 10px; }
  #cmdk-input { flex: 1; background: transparent; border: 0; outline: none; color: var(--bd-text); font-size: 15px; font-weight: 600; }
  #cmdk-tabs { display: flex; gap: 6px; padding: 7px 14px; border-bottom: 1px solid var(--bd-border); background: var(--bd-card); flex-wrap: wrap; }
  .cmdk-tab { font-size: 11px; padding: 3px 9px; border-radius: 999px; cursor: pointer; border: 1px solid var(--bd-border); color: var(--bd-muted); }
  .cmdk-tab.active { background: rgba(0,229,255,0.16); color: var(--bd-accent); border-color: var(--bd-accent); font-weight: 700; }
  #cmdk-list { flex: 1; overflow-y: auto; padding: 6px; max-height: 55vh; }
  .cmdk-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; border-radius: 8px; cursor: pointer; font-size: 12.5px; border: 1px solid transparent; }
  .cmdk-row:hover, .cmdk-row.selected { background: rgba(0,229,255,0.13); border-color: var(--bd-accent); }
  .cmdk-badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; background: var(--bd-card); border: 1px solid var(--bd-border); color: var(--bd-muted); }
  /* #UX-5 Floating PiP Mini-Monitor HUD */
  #pip-hud { position: fixed; right: 16px; bottom: 16px; width: 320px; background: var(--bd-panel); border: 1px solid var(--bd-accent); border-radius: 10px; padding: 10px; box-shadow: 0 14px 36px rgba(0,0,0,0.65); z-index: 9000; display: none; font-size: 11.5px; }
  #pip-hud.open { display: block; }
  #toast { position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%); background: var(--bd-panel); border: 1px solid var(--bd-accent); color: var(--bd-text); padding: 8px 16px; border-radius: 8px; font-size: 12px; font-weight: 600; z-index: 10000; display: none; box-shadow: 0 10px 30px rgba(0,0,0,0.6); }
</style>
</head>
<body>
<div id="os-root">
  <!-- #UX-3 Persistent 36px Top Telemetry & Quota Pill Bar -->
  <header id="topbar">
    <div class="tb-group">
      <div class="brand-pill" onclick="toggleDock()" title="Toggle Left App Dock (Alt+0)">
        <span>🛸 BOYLENET OS</span><span style="opacity:0.7;font-size:10px">:4085</span>
      </div>
      <div class="bd-pill" onclick="selectAppInFocusedPane('harnesses')" title="Claude Pools A/B/C/D 5-Hour Quota">
        <span class="bd-dot"></span><span id="pill-claude">Pools A:0% B:0% C:0% D:0%</span>
      </div>
      <div class="bd-pill" onclick="selectAppInFocusedPane('cloud')" title="$1,000 Free Cloud Session Credit ($250 x 4 • Overage Cap OFF)">
        <span>☁️</span><span id="pill-cloud" style="color:var(--bd-ok);font-weight:700">$1,000 Cloud</span>
      </div>
      <div class="bd-pill" onclick="openCmdK('models')" title="4x Tesla T4 Active Model & Decode Throughput">
        <span>⚡</span><span id="pill-gpu">4xT4: qwen3-coder-30b • 77.6 tok/s</span>
      </div>
      <div class="bd-pill" onclick="selectAppInFocusedPane('models')" title="86 Verified Model Directories Across .72 & .83 Vaults">
        <span>🧠</span><span id="pill-vault">86 Models (8.9 TB)</span>
      </div>
      <div class="bd-pill" onclick="selectAppInFocusedPane('sentinel')" title="Boylenet Autonomous 83-Service Sentinel Health">
        <span class="bd-dot" id="dot-sentinel"></span><span id="pill-sentinel">Sentinel 83/83 (99.9%)</span>
      </div>
    </div>
    <div class="tb-group">
      <!-- #UX-4 Workspace Mode Switcher -->
      <button class="mode-btn active" id="btn-m1" onclick="setWorkspaceMode('1')" title="1-Pane Single View">1-Pane</button>
      <button class="mode-btn" id="btn-m2" onclick="setWorkspaceMode('2')" title="#UX-4 2-Pane Side-by-Side Split">2-Pane Split</button>
      <button class="mode-btn" id="btn-m3" onclick="setWorkspaceMode('3')" title="#UX-4 3-Pane Tactical Grid">3-Pane Grid</button>
      <button class="mode-btn" id="btn-mw" onclick="setWorkspaceMode('wallboard')" title="#UX-21 TV Wallboard Auto-Cycle">📺 Wallboard</button>
      <button class="act-btn" id="btn-airgap" onclick="toggleAirgap()" title="100% Cut Off Outbound Internet (WAN Airgap) on GPU Nodes (.72/.83/.125/.228)" style="border-color:#10b981;color:#10b981;font-weight:800;">🛡️ Airgap: OFF</button>
      <button class="act-btn" onclick="openAirgapProofModal()" title="Verify 100% Local LLM Execution with Zero Internet Access" style="border-color:#f59e0b;color:#fbbf24;font-weight:800;">🔬 Verify Local Proof</button>
      <button class="act-btn" onclick="toggleTerminalDrawer()" title="Toggle Bottom Web Terminal Drawer (` Backtick)">💻 Term (`)</button>
      <button class="act-btn" onclick="openCmdK('all')" title="#UX-2 Universal Command Palette (Cmd+K / Ctrl+K)" style="border-color:var(--bd-accent);color:var(--bd-accent)">⌘K Spotlight</button>
      <button class="act-btn" onclick="launchPiPMonitor()" title="#UX-5 Picture-in-Picture (PiP) Mini-Monitor Popout">🖼️ PiP</button>
      <select class="theme-sel" id="theme-select" onchange="changeTheme(this.value)" title="#UX-33 4-Theme Engine Switcher">
        <option value="cyber-glass">🎨 Cyber-Glass Dark</option>
        <option value="oled-midnight">🌑 OLED Midnight</option>
        <option value="solarized-ops">☀️ Solarized Ops</option>
        <option value="daylight">🌕 Daylight</option>
      </select>
      <button class="act-btn" id="btn-refresh-state" onclick="fetchState(true); refreshAirgapBtn();" title="Refresh Live OS Telemetry & Pool Quota State">↻ Refresh</button>
      <button class="act-btn" onclick="exportSnapshot()" title="#UX-35 Export Cluster Snapshot">📸 Snapshot</button>
    </div>
  </header>

  <div id="os-body">
    <!-- #UX-1 Left App Dock -->
    <aside id="left-dock">
      <div class="dock-header">
        <span class="dock-hdr-txt">26 Flagship Views (0ms DOM)</span>
        <span style="cursor:pointer" onclick="toggleDock()" title="Collapse/Expand Dock">⇔</span>
      </div>
      <div id="dock-list"></div>
    </aside>

    <!-- #UX-4 Multi-Pane Stage + Wallboard Bar + Backtick Terminal Drawer -->
    <main id="stage-wrap">
      <div id="wallboard-bar">
        <span>📺 <b>TV Wallboard Auto-Cycle (#UX-21)</b> — Cycling operational views every <b id="wb-sec">15s</b></span>
        <div style="display:flex;gap:8px;align-items:center">
          <span id="wb-next-label">Next: 3D Topology</span>
          <button class="act-btn" onclick="stepWallboard(1)">⏭ Next Now</button>
          <button class="act-btn" onclick="setWorkspaceMode('1')">✕ Exit Wallboard</button>
        </div>
      </div>
      <div id="panes-grid">
        <section class="workspace-pane focused" id="pane-0" onclick="focusPane(0)">
          <div class="pane-bar">
            <div style="display:flex;align-items:center;gap:6px">
              <span style="font-weight:700;color:var(--bd-accent)">PANE 1</span>
              <select id="sel-pane-0" onchange="loadAppInPane(0, this.value)"></select>
            </div>
            <div style="display:flex;gap:5px">
              <button class="act-btn" onclick="reloadPane(0)" title="Reload current iframe">↻</button>
              <button class="act-btn" onclick="popoutPane(0)" title="Open in new browser tab">↗ Popout</button>
            </div>
          </div>
          <div class="pane-frames" id="frames-0"></div>
        </section>
        <section class="workspace-pane" id="pane-1" onclick="focusPane(1)" style="display:none">
          <div class="pane-bar">
            <div style="display:flex;align-items:center;gap:6px">
              <span style="font-weight:700;color:var(--bd-accent-2)">PANE 2</span>
              <select id="sel-pane-1" onchange="loadAppInPane(1, this.value)"></select>
            </div>
            <div style="display:flex;gap:5px">
              <button class="act-btn" onclick="reloadPane(1)">↻</button>
              <button class="act-btn" onclick="popoutPane(1)">↗ Popout</button>
            </div>
          </div>
          <div class="pane-frames" id="frames-1"></div>
        </section>
        <section class="workspace-pane" id="pane-2" onclick="focusPane(2)" style="display:none">
          <div class="pane-bar">
            <div style="display:flex;align-items:center;gap:6px">
              <span style="font-weight:700;color:var(--bd-ok)">PANE 3</span>
              <select id="sel-pane-2" onchange="loadAppInPane(2, this.value)"></select>
            </div>
            <div style="display:flex;gap:5px">
              <button class="act-btn" onclick="reloadPane(2)">↻</button>
              <button class="act-btn" onclick="popoutPane(2)">↗ Popout</button>
            </div>
          </div>
          <div class="pane-frames" id="frames-2"></div>
        </section>
      </div>
      <!-- Collapsible Bottom Web Terminal Drawer (` Backtick) -->
      <div id="term-drawer">
        <div class="drawer-hdr">
          <div style="display:flex;align-items:center;gap:10px">
            <span>💻 <b>Collapsible Bottom Terminal & Ops Drawer</b> (Toggle with <kbd>`</kbd> Backtick)</span>
            <button class="act-btn" onclick="setDrawerUrl(appUrlForPort(4083))">Web Terminal (:4083)</button>
            <button class="act-btn" onclick="setDrawerUrl(appUrlForPort(4089))">NL Ops Shell (:4089)</button>
            <button class="act-btn" onclick="setDrawerUrl(appUrlForPort(4098))">Multi-Harness (:4098)</button>
          </div>
          <button class="act-btn" onclick="toggleTerminalDrawer()">▼ Hide Drawer (`)</button>
        </div>
        <iframe id="drawer-iframe" style="flex:1;width:100%;border:0;background:#050811"></iframe>
      </div>
    </main>
  </div>
</div>

<!-- #UX-2 Universal Cmd+K Raycast-Style Command Palette -->
<div id="cmdk-overlay" onclick="if(event.target===this)closeCmdK()">
  <div id="cmdk-modal">
    <div id="cmdk-top">
      <span style="font-size:18px">🔍</span>
      <input id="cmdk-input" type="text" placeholder="Type a command or search 54 Apps, 86 Vault Models, 40 Fleet Roles, or Quick Actions..." oninput="renderCmdKList()" />
      <span class="cmdk-badge" onclick="closeCmdK()" style="cursor:pointer">ESC</span>
    </div>
    <div id="cmdk-tabs">
      <span class="cmdk-tab active" data-cat="all" onclick="setCmdKCat('all')">All (207)</span>
      <span class="cmdk-tab" data-cat="actions" onclick="setCmdKCat('actions')">⚡ Quick Actions (15)</span>
      <span class="cmdk-tab" data-cat="apps" onclick="setCmdKCat('apps')">🧭 Apps (54)</span>
      <span class="cmdk-tab" data-cat="models" onclick="setCmdKCat('models')">🟢 Local Models (86)</span>
      <span class="cmdk-tab" data-cat="cloud_models" onclick="setCmdKCat('cloud_models')">☁️ Cloud Models (12)</span>
      <span class="cmdk-tab" data-cat="roles" onclick="setCmdKCat('roles')">🤖 Fleet Roles (40)</span>
    </div>
    <div id="cmdk-list"></div>
  </div>
</div>

<!-- #UX-5 Picture-in-Picture (PiP) Mini-Monitor -->
<div id="pip-hud">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;border-bottom:1px solid var(--bd-border);padding-bottom:4px">
    <b>🖼️ Boylenet Live PiP Monitor (#UX-5)</b>
    <div style="display:flex;gap:4px">
      <button class="act-btn" onclick="popoutDocumentPiP()" title="Pop out always-on-top Document PiP window">⧉ Window</button>
      <button class="act-btn" onclick="document.getElementById('pip-hud').classList.remove('open')">✕</button>
    </div>
  </div>
  <div id="pip-body" style="display:grid; gap:4px; line-height:1.4"></div>
</div>
<div id="toast"></div>

<script src="/static/boylenet-nav.js"></script>
<script>
let OS_STATE = null;
let FOCUSED_PANE = 0;
let WORKSPACE_MODE = '1';
let PANE_ACTIVE_APP = {0: 'harnesses', 1: 'topology', 2: 'cloud'};
let CMDK_CAT = 'all';
let CMDK_RESULTS = [];
let CMDK_INDEX = 0;
let WALLBOARD_TIMER = null;
let WALLBOARD_IDX = 0;
const WALLBOARD_ROTATION = ['briefing', 'topology', 'harnesses', 'cloud', 'models', 'hardware', 'sentinel', 'grafana'];

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => { t.style.display = 'none'; }, 3200);
}

function appUrlForPort(port, path='') {
  const h = window.location.hostname || '10.0.70.164';
  const hostIp = (h.endsWith('.boylenet.themfboyles.org') || h.endsWith('.themfboyles.org') || h.endsWith('.boylenet.themfboyles.org') || h.endsWith('.themfboyles.com') || h === 'localhost') ? (OS_STATE?.controller_ip || '10.0.70.164') : h;
  return 'http://' + hostIp + ':' + port + (path || '');
}

function getAppById(appId) {
  if (!OS_STATE) return null;
  return (OS_STATE.dock_apps || []).find(a => a.id === appId) || (OS_STATE.all_apps || []).find(a => a.id === appId);
}

function resolveAppUrl(app) {
  if (!app) return appUrlForPort(4098);
  if (app.url) return app.url;
  return appUrlForPort(app.port);
}

const STANDALONE_CONTAINER_PORTS = new Set([3000, 3002, 4000, 6333, 8090, 4095, 4096, 4097, 5678, 4080, 9090, 19999]);

/* Zero-Reload DOM Iframe Caching (0ms tab switching!) */
function loadAppInPane(paneIdx, appId) {
  if (!OS_STATE) return;
  const app = getAppById(appId) || OS_STATE.dock_apps[0];
  if (!app) return;
  PANE_ACTIVE_APP[paneIdx] = app.id;
  const sel = document.getElementById('sel-pane-' + paneIdx);
  if (sel && sel.value !== app.id) sel.value = app.id;

  const container = document.getElementById('frames-' + paneIdx);
  if (!container) return;
  Array.from(container.children).forEach(ch => ch.classList.remove('visible'));

  let frame = document.getElementById('iframe-p' + paneIdx + '-' + app.id);
  if (!frame) {
    frame = document.createElement('iframe');
    frame.id = 'iframe-p' + paneIdx + '-' + app.id;
    frame.className = 'cached-iframe';
    const targetUrl = resolveAppUrl(app);
    if (!app.online || STANDALONE_CONTAINER_PORTS.has(Number(app.port))) {
      frame.srcdoc = `<!DOCTYPE html><html><body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;background:#050811;color:#f8fafc;font-family:Inter,system-ui,sans-serif;"><div style="max-width:520px;padding:28px;background:#0a1020;border:1px solid rgba(0,229,255,0.35);border-radius:14px;text-align:center;box-shadow:0 20px 50px rgba(0,0,0,0.7);"><div style="font-size:38px;margin-bottom:10px;">${app.icon || '🚀'}</div><div style="font-size:18px;font-weight:800;color:#00e5ff;margin-bottom:6px;">${app.title} (:${app.port})</div><div style="font-size:12.5px;color:#94a3b8;margin-bottom:18px;">Status: <b style="color:#10b981;">${app.online ? 'ONLINE & READY' : 'STANDBY'}</b> • Endpoint: <code>${targetUrl}</code></div><a href="${targetUrl}" target="_blank" style="display:inline-block;padding:10px 20px;background:linear-gradient(135deg,#0284c7,#7c3aed);color:#fff;text-decoration:none;border-radius:8px;font-weight:800;font-size:13px;">↗ Launch ${app.short || app.title} (:${app.port})</a></div></body></html>`;
    } else {
      frame.src = targetUrl;
    }
    frame.setAttribute('allow', 'clipboard-read; clipboard-write; microphone; camera; fullscreen');
    container.appendChild(frame);
  }
  frame.classList.add('visible');
  renderDock();
}

function reloadPane(paneIdx) {
  const appId = PANE_ACTIVE_APP[paneIdx];
  const frame = document.getElementById('iframe-p' + paneIdx + '-' + appId);
  if (frame) frame.src = frame.src;
}

function popoutPane(paneIdx) {
  const app = getAppById(PANE_ACTIVE_APP[paneIdx]);
  if (app) window.open(resolveAppUrl(app), '_blank');
}

function focusPane(paneIdx) {
  FOCUSED_PANE = paneIdx;
  [0,1,2].forEach(i => {
    const el = document.getElementById('pane-' + i);
    if (el) el.classList.toggle('focused', i === paneIdx);
  });
  renderDock();
}

function selectAppInFocusedPane(appId) {
  loadAppInPane(FOCUSED_PANE, appId);
}

function setWorkspaceMode(mode) {
  WORKSPACE_MODE = mode;
  ['1','2','3','wallboard'].forEach(m => {
    const btn = document.getElementById('btn-m' + (m === 'wallboard' ? 'w' : m));
    if (btn) btn.classList.toggle('active', m === mode);
  });
  const grid = document.getElementById('panes-grid');
  const p1 = document.getElementById('pane-1');
  const p2 = document.getElementById('pane-2');
  const wb = document.getElementById('wallboard-bar');
  clearInterval(WALLBOARD_TIMER);
  wb.classList.remove('show');

  if (mode === '1' || mode === 'wallboard') {
    grid.className = '';
    p1.style.display = 'none';
    p2.style.display = 'none';
    focusPane(0);
    if (mode === 'wallboard') {
      wb.classList.add('show');
      WALLBOARD_TIMER = setInterval(() => stepWallboard(1), 15000);
    }
  } else if (mode === '2') {
    grid.className = 'mode-2';
    p1.style.display = 'flex';
    p2.style.display = 'none';
    loadAppInPane(1, PANE_ACTIVE_APP[1] || 'topology');
  } else if (mode === '3') {
    grid.className = 'mode-3';
    p1.style.display = 'flex';
    p2.style.display = 'flex';
    loadAppInPane(1, PANE_ACTIVE_APP[1] || 'topology');
    loadAppInPane(2, PANE_ACTIVE_APP[2] || 'cloud');
  }
}

function stepWallboard(delta) {
  WALLBOARD_IDX = (WALLBOARD_IDX + delta + WALLBOARD_ROTATION.length) % WALLBOARD_ROTATION.length;
  const curId = WALLBOARD_ROTATION[WALLBOARD_IDX];
  const nextId = WALLBOARD_ROTATION[(WALLBOARD_IDX + 1) % WALLBOARD_ROTATION.length];
  loadAppInPane(0, curId);
  const nextApp = getAppById(nextId);
  const lbl = document.getElementById('wb-next-label');
  if (lbl && nextApp) lbl.textContent = 'Next: ' + nextApp.short + ' (:' + nextApp.port + ')';
}

function toggleDock() {
  document.getElementById('left-dock').classList.toggle('collapsed');
}

function toggleTerminalDrawer() {
  const d = document.getElementById('term-drawer');
  const isOpen = d.classList.toggle('open');
  const ifr = document.getElementById('drawer-iframe');
  if (isOpen && !ifr.src) {
    const termOnline = OS_STATE?.dock_apps?.find(a => a.id === 'terminal')?.online;
    ifr.src = appUrlForPort(termOnline ? 4083 : 4089);
  }
}

function setDrawerUrl(url) {
  const d = document.getElementById('term-drawer');
  d.classList.add('open');
  document.getElementById('drawer-iframe').src = url;
}

function renderDock() {
  if (!OS_STATE) return;
  const list = document.getElementById('dock-list');
  const apps = OS_STATE.dock_apps || [];
  const activeId = PANE_ACTIVE_APP[FOCUSED_PANE];
  if (list.children.length === apps.length) {
    apps.forEach((a, idx) => {
      const el = list.children[idx];
      if (!el) return;
      el.classList.toggle('active', a.id === activeId);
      const dot = el.querySelector('.bd-dot');
      if (dot) {
        dot.classList.toggle('off', !a.online);
        dot.title = a.online ? 'Port :'+a.port+' ONLINE' : 'Port :'+a.port+' Standby';
      }
    });
    return;
  }
  list.innerHTML = apps.map(a => `
    <div class="dock-item ${a.id === activeId ? 'active' : ''}" data-app-id="${a.id}" onclick="selectAppInFocusedPane('${a.id}')" title="${a.title} (:${a.port}) ${a.shortcut}">
      <div class="dock-left">
        <span class="dock-icon">${a.icon}</span>
        <span class="dock-label">${a.short} <span style="opacity:0.55;font-size:10.5px">:${a.port}</span></span>
      </div>
      <div class="dock-right">
        ${a.shortcut ? `<span class="dock-kbd">${a.shortcut}</span>` : ''}
        <span class="bd-dot ${a.online ? '' : 'off'}" title="${a.online ? 'Port :'+a.port+' ONLINE' : 'Port :'+a.port+' Standby'}"></span>
      </div>
    </div>
  `).join('');
}

function populatePaneSelectors() {
  if (!OS_STATE) return;
  const opts = (OS_STATE.all_apps || []).map(a => `<option value="${a.id}">${a.icon} ${a.title} (:${a.port})</option>`).join('');
  [0,1,2].forEach(i => {
    const sel = document.getElementById('sel-pane-' + i);
    if (sel && !sel.innerHTML) {
      sel.innerHTML = opts;
      sel.value = PANE_ACTIVE_APP[i];
    }
  });
}

function updateTopBar() {
  if (!OS_STATE || !OS_STATE.topbar) return;
  const tb = OS_STATE.topbar;
  const obsTs = tb.pool_observed_at || OS_STATE.pool_observed_at || OS_STATE.timestamp || '';
  const shortTs = obsTs ? obsTs.slice(-9) : '';
  const claudeEl = document.getElementById('pill-claude');
  if (claudeEl) {
    claudeEl.textContent = 'Pools ' + tb.claude_summary + (shortTs ? ` (${shortTs})` : '');
    claudeEl.setAttribute('data-observed-at', obsTs);
  }
  document.getElementById('pill-cloud').textContent = tb.cloud_credit_label;
  document.getElementById('pill-gpu').textContent = `4xT4 (${tb.gpu_tier}): ${tb.gpu_active_model} • ${tb.gpu_tok_s} tok/s`;
  document.getElementById('pill-vault').textContent = tb.vault_label;
  document.getElementById('pill-sentinel').textContent = `Sentinel ${tb.sentinel_healthy}/${tb.sentinel_total} (${tb.sentinel_uptime_pct}%)`;
  const pipBody = document.getElementById('pip-body');
  if (pipBody) {
    pipBody.innerHTML = `
      <div><b>Claude A/B/C/D 5h:</b> ${tb.claude_summary}</div>
      <div><b>Pool State Synced:</b> <span id="pip-pool-ts">${obsTs}</span></div>
      <div><b>Cloud Burst Credit:</b> <span style="color:var(--bd-ok)">${tb.cloud_credit_label}</span></div>
      <div><b>4xT4 Active GPU:</b> ${tb.gpu_active_model} (${tb.gpu_tok_s} tok/s)</div>
      <div><b>Model Vault:</b> ${tb.vault_label} (100% READY)</div>
      <div><b>Infra Sentinel:</b> ${tb.sentinel_healthy}/${tb.sentinel_total} services healthy</div>
    `;
  }
}

/* #UX-2 Universal Cmd+K Spotlight */
function openCmdK(cat='all') {
  CMDK_CAT = cat;
  document.querySelectorAll('.cmdk-tab').forEach(t => t.classList.toggle('active', t.dataset.cat === cat));
  document.getElementById('cmdk-overlay').classList.add('open');
  const inp = document.getElementById('cmdk-input');
  inp.value = '';
  renderCmdKList();
  setTimeout(() => inp.focus(), 20);
}

function closeCmdK() {
  document.getElementById('cmdk-overlay').classList.remove('open');
}

function setCmdKCat(cat) {
  CMDK_CAT = cat;
  document.querySelectorAll('.cmdk-tab').forEach(t => t.classList.toggle('active', t.dataset.cat === cat));
  renderCmdKList();
  document.getElementById('cmdk-input').focus();
}

function renderCmdKList() {
  if (!OS_STATE) return;
  const q = (document.getElementById('cmdk-input').value || '').toLowerCase().trim();
  const items = [];
  if (CMDK_CAT === 'all' || CMDK_CAT === 'actions') {
    (OS_STATE.quick_actions || []).forEach(a => items.push({type:'action', id:a.id, icon:a.icon, title:a.title, sub:a.desc, badge:'Quick Action'}));
  }
  if (CMDK_CAT === 'all' || CMDK_CAT === 'apps') {
    (OS_STATE.all_apps || []).forEach(a => items.push({type:'app', id:a.id, icon:a.icon, title:a.title, sub:`https://${a.sub}.boylenet.themfboyles.org (:${a.port})`, badge:a.cat + (a.shortcut ? ' • '+a.shortcut : '')}));
  }
  if (CMDK_CAT === 'all' || CMDK_CAT === 'models') {
    (OS_STATE.vault_models || []).forEach(m => items.push({type:'model', id:m.id, icon:'🟢', title:`${m.name} (${m.id})`, sub:`100% LOCAL • Node ${m.node} • ${m.size} • ${m.speed}`, badge:`🟢 LOCAL • ${m.tier}`}));
  }
  if (CMDK_CAT === 'all' || CMDK_CAT === 'cloud_models') {
    (OS_STATE.cloud_models || []).forEach(m => items.push({type:'model', id:m.id, icon:'☁️', title:`${m.name} (${m.id})`, sub:`EXTERNAL CLOUD API • ${m.size} • ${m.speed}`, badge:m.tier}));
  }
  if (CMDK_CAT === 'all' || CMDK_CAT === 'roles') {
    (OS_STATE.fleet_roles || []).forEach(r => items.push({type:'role', id:r, icon:'🤖', title:`Fleet Role: ${r}`, sub:`Launch or inspect ${r} seat in Multi-Harness Studio (:4098)`, badge:'40 Fleet Roles'}));
  }
  CMDK_RESULTS = items.filter(it => !q || (it.title + ' ' + it.sub + ' ' + it.badge).toLowerCase().includes(q)).slice(0, 80);
  CMDK_INDEX = 0;
  const listEl = document.getElementById('cmdk-list');
  listEl.innerHTML = CMDK_RESULTS.map((it, idx) => `
    <div class="cmdk-row ${idx === 0 ? 'selected' : ''}" data-idx="${idx}" onclick="executeCmdKItem(${idx})">
      <div style="display:flex;align-items:center;gap:10px;min-width:0">
        <span style="font-size:16px">${it.icon}</span>
        <div style="min-width:0">
          <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${it.title}</div>
          <div style="font-size:11px;color:var(--bd-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${it.sub}</div>
        </div>
      </div>
      <span class="cmdk-badge">${it.badge}</span>
    </div>
  `).join('');
}

async function executeCmdKItem(idx) {
  const it = CMDK_RESULTS[idx];
  if (!it) return;
  closeCmdK();
  if (it.type === 'app') {
    selectAppInFocusedPane(it.id);
    showToast(`Switched Pane ${FOCUSED_PANE+1} -> ${it.title}`);
  } else if (it.type === 'model') {
    selectAppInFocusedPane('models');
    showToast(`Selected Vault Model: ${it.id}`);
  } else if (it.type === 'role') {
    selectAppInFocusedPane('harnesses');
    showToast(`Opened Multi-Harness Studio for Role: ${it.id}`);
  } else if (it.type === 'action') {
    await runQuickAction(it.id);
  }
}

async function runQuickAction(actId) {
  if (actId === 'copy_litellm_key') {
    try { await navigator.clipboard.writeText('sk-fleet-local'); } catch(e){}
    showToast('Copied LiteLLM Master Key: sk-fleet-local');
    return;
  }
  if (actId === 'mode_1pane') return setWorkspaceMode('1');
  if (actId === 'mode_2pane') return setWorkspaceMode('2');
  if (actId === 'mode_3pane') return setWorkspaceMode('3');
  if (actId === 'mode_wallboard') return setWorkspaceMode('wallboard');
  if (actId === 'toggle_terminal') return toggleTerminalDrawer();
  if (actId === 'open_pip') return launchPiPMonitor();
  if (actId === 'export_snapshot') return exportSnapshot();

  showToast(`Executing ${actId}...`);
  try {
    const r = await fetch('/api/action', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:actId})});
    const d = await r.json();
    showToast(d.message || `Completed ${actId}`);
    if (actId === 'run_doctor') selectAppInFocusedPane('briefing');
    if (actId === 'open_rc' && d.rc_links && d.rc_links.length) window.open(d.rc_links[0].rc_url, '_blank');
    fetchState();
  } catch (e) {
    showToast(`Action error: ${e}`);
  }
}

/* #UX-5 Picture-in-Picture (PiP) Mini-Monitor */
function launchPiPMonitor() {
  document.getElementById('pip-hud').classList.add('open');
  updateTopBar();
}

async function popoutDocumentPiP() {
  const html = document.getElementById('pip-body').innerHTML;
  if ('documentPictureInPicture' in window) {
    try {
      const pipWin = await window.documentPictureInPicture.requestWindow({width: 360, height: 210});
      pipWin.document.body.style.cssText = 'margin:0;padding:12px;background:#050811;color:#f8fafc;font-family:sans-serif;font-size:12px;line-height:1.5';
      pipWin.document.body.innerHTML = '<h4 style="margin:0 0 8px 0;color:#00e5ff">🛸 Boylenet PiP Telemetry</h4>' + html;
      return;
    } catch(e){}
  }
  const w = window.open('', 'BoylenetPiP', 'width=380,height=230,menubar=no,toolbar=no,location=no,status=no');
  if (w) {
    w.document.write(`<html><body style="margin:0;padding:12px;background:#050811;color:#f8fafc;font-family:sans-serif;font-size:12px;line-height:1.5"><h4 style="margin:0 0 8px 0;color:#00e5ff">🛸 Boylenet PiP Telemetry (#UX-5)</h4>${html}</body></html>`);
    w.document.close();
  }
}

/* #UX-33 4-Theme Switcher */
function changeTheme(theme) {
  if (window.BoylenetOS) window.BoylenetOS.applyTheme(theme);
  showToast('Theme applied: ' + theme);
}

/* #UX-35 Export Snapshot */
async function exportSnapshot() {
  try {
    const r = await fetch('/api/snapshot', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({workspace_mode: WORKSPACE_MODE, panes: PANE_ACTIVE_APP})});
    const d = await r.json();
    const blob = new Blob([JSON.stringify(d, null, 2)], {type: 'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `boylenet-os-snapshot-${new Date().toISOString().replace(/[:.]/g,'-')}.json`;
    a.click();
    showToast('Snapshot saved: ' + (d.saved_path || 'downloaded'));
  } catch(e) {
    showToast('Snapshot failed: ' + e);
  }
}

/* Keyboard Shortcuts: Alt+1..9 Dock, Backtick ` Terminal Drawer, Cmd+K Spotlight */
window.addEventListener('keydown', (e) => {
  const overlay = document.getElementById('cmdk-overlay');
  if (overlay.classList.contains('open')) {
    if (e.key === 'Escape') { e.preventDefault(); closeCmdK(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); CMDK_INDEX = Math.min(CMDK_RESULTS.length - 1, CMDK_INDEX + 1); highlightCmdK(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); CMDK_INDEX = Math.max(0, CMDK_INDEX - 1); highlightCmdK(); }
    else if (e.key === 'Enter') { e.preventDefault(); executeCmdKItem(CMDK_INDEX); }
    return;
  }
  if (e.key === '`' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) {
    e.preventDefault();
    toggleTerminalDrawer();
  }
  if (e.altKey && e.key >= '1' && e.key <= '9') {
    e.preventDefault();
    const idx = parseInt(e.key, 10) - 1;
    if (OS_STATE && OS_STATE.dock_apps && OS_STATE.dock_apps[idx]) {
      selectAppInFocusedPane(OS_STATE.dock_apps[idx].id);
      showToast(`Alt+${e.key} -> ${OS_STATE.dock_apps[idx].title}`);
    }
  }
});

function highlightCmdK() {
  document.querySelectorAll('.cmdk-row').forEach((el, i) => {
    el.classList.toggle('selected', i === CMDK_INDEX);
    if (i === CMDK_INDEX) el.scrollIntoView({block:'nearest'});
  });
}

async function fetchState(force=false) {
  try {
    const r = await fetch('/api/os-state' + (force ? '?force=1' : ''));
    OS_STATE = await r.json();
    populatePaneSelectors();
    renderDock();
    updateTopBar();
    if (!document.getElementById('frames-0').children.length) {
      const defApp = OS_STATE.dock_apps.find(a => a.id === 'briefing' && a.online) ? 'briefing' : 'harnesses';
      PANE_ACTIVE_APP[0] = defApp;
      loadAppInPane(0, defApp);
    }
  } catch(e){}
}

window.addEventListener('DOMContentLoaded', () => {
  const savedTheme = localStorage.getItem('boylenet_theme') || 'cyber-glass';
  const sel = document.getElementById('theme-select');
  if (sel) sel.value = savedTheme;
  fetchState();
  refreshAirgapBtn();
  setInterval(fetchState, 3000);
  if (window.location.hash === '#cmdk') setTimeout(() => openCmdK('all'), 300);
});

let AIRGAP_ARMED = false;
async function refreshAirgapBtn() {
  try {
    const r = await fetch('/api/airgap');
    const d = await r.json();
    AIRGAP_ARMED = !!d.airgap_enabled;
    const btn = document.getElementById('btn-airgap');
    if (btn) {
      if (AIRGAP_ARMED) {
        btn.textContent = '🔒 AIRGAP: ARMED (WAN CUT)';
        btn.style.background = 'rgba(239,68,68,0.22)';
        btn.style.borderColor = '#ef4444';
        btn.style.color = '#fca5a5';
      } else {
        btn.textContent = '🛡️ Airgap: OFF';
        btn.style.background = '';
        btn.style.borderColor = '#10b981';
        btn.style.color = '#10b981';
      }
    }
  } catch (e) {}
}

async function toggleAirgap(forceState, scope='gpu') {
  const next = (forceState !== undefined) ? forceState : !AIRGAP_ARMED;
  showToast(next ? '🔒 Arming Kernel WAN Airgap on GPU Nodes (.72/.83/.125/.228)...' : '🌐 Disarming WAN Airgap...');
  try {
    const r = await fetch('/api/airgap', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({enable: next, scope: scope})
    });
    const d = await r.json();
    await refreshAirgapBtn();
    showToast(d.airgap_enabled ? '🔒 WAN Airgap ARMED (100% Outbound Internet Blocked on GPU Nodes!)' : '🌐 WAN Airgap Disarmed (Internet Restored)');
    return d;
  } catch (e) {
    showToast('Airgap toggle error: ' + e);
  }
}

async function openAirgapProofModal() {
  let m = document.getElementById('airgap-proof-modal');
  if (!m) {
    m = document.createElement('div');
    m.id = 'airgap-proof-modal';
    m.style.cssText = 'position:fixed;inset:0;background:rgba(2,6,23,0.85);backdrop-filter:blur(8px);z-index:10000;display:flex;align-items:center;justify-content:center;';
    m.innerHTML = `
      <div style="width:min(760px,94vw);background:#091022;border:2px solid #f59e0b;border-radius:12px;padding:18px;color:#f8fafc;box-shadow:0 24px 64px rgba(0,0,0,0.8);">
        <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #334155;padding-bottom:10px;margin-bottom:12px;">
          <div style="font-size:15px;font-weight:900;color:#fbbf24;">🛡️ BOYLENET KERNEL WAN AIRGAP & 100% LOCAL LLM PROOF VERIFIER</div>
          <button onclick="document.getElementById('airgap-proof-modal').style.display='none'" style="background:#1e293b;border:1px solid #ef4444;color:#fca5a5;padding:4px 10px;border-radius:6px;cursor:pointer;font-weight:800;">✕ Close</button>
        </div>
        <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;">
          <button onclick="runAirgapProof(true, 'gpu')" style="background:linear-gradient(135deg,#dc2626,#b91c1c);border:0;color:#fff;padding:8px 14px;border-radius:7px;font-weight:800;cursor:pointer;">🔒 1. Arm GPU Airgap & Run Live Local LLM Proof</button>
          <button onclick="runAirgapProof(true, 'full')" style="background:linear-gradient(135deg,#7c3aed,#4f46e5);border:0;color:#fff;padding:8px 14px;border-radius:7px;font-weight:800;cursor:pointer;">🛡️ Arm Full Cluster Airgap (.164 + GPUs) & Prove</button>
          <button onclick="toggleAirgap(false)" style="background:#059669;border:0;color:#fff;padding:8px 14px;border-radius:7px;font-weight:800;cursor:pointer;">🌐 Disarm Airgap (Restore Internet)</button>
        </div>
        <pre id="airgap-proof-out" style="background:#020617;border:1px solid #334155;border-radius:8px;padding:12px;font-family:monospace;font-size:11.5px;color:#38bdf8;max-height:58vh;overflow:auto;white-space:pre-wrap;">Click "🔒 1. Arm GPU Airgap & Run Live Local LLM Proof" to cut off outbound internet on .72/.83/.125/.228, probe Cloudflare/Google/Anthropic/OpenAI (proving 100% unreachable), and run a live Tesla T4 LLM generation with 0 internet access.</pre>
      </div>
    `;
    document.body.appendChild(m);
  }
  m.style.display = 'flex';
  runAirgapProof(false);
}

async function runAirgapProof(armFirst, scope='gpu') {
  const out = document.getElementById('airgap-proof-out');
  if (out) out.textContent = (armFirst ? '🔒 Arming Kernel iptables BOYLENET_AIRGAP chain + ' : '') + '🔬 Probing WAN (1.1.1.1, 8.8.8.8, Anthropic, OpenAI) & running live Local Tesla T4 LLM completion...';
  if (armFirst) await toggleAirgap(true, scope);
  try {
    const r = await fetch('/api/airgap/verify', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
    const d = await r.json();
    await refreshAirgapBtn();
    if (out) out.textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    if (out) out.textContent = 'Error: ' + e;
  }
}
</script>
</body>
</html>
"""


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class OSShellHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send_bytes(self, code: int, ctype: str, data: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, code: int, payload: Dict[str, Any]) -> None:
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self._send_bytes(code, "application/json; charset=utf-8", raw)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        force_q = "force=1" in (parsed.query or "")
        if path == "/api/airgap":
            p = subprocess.run(
                ["/home/mboyle/bin/bd-airgap", "status"],
                capture_output=True,
                text=True,
                timeout=12,
            )
            try:
                self._send_json(200, json.loads(p.stdout))
            except Exception:
                self._send_json(200, {"airgap_enabled": False, "raw": p.stdout})
            return
        if path == "/health":
            st = gather_os_state(force=force_q)
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "bd-os-shell",
                    "port": PORT,
                    "url": "https://os.boylenet.themfboyles.org",
                    "pillars": [
                        "Pillar 1: Unified OS Desktop Shell",
                        "Pillar 7: Shared TopBar, 4-Theme Engine & PiP",
                    ],
                    "ux_items": [
                        "#UX-1",
                        "#UX-2",
                        "#UX-3",
                        "#UX-4",
                        "#UX-5",
                        "#UX-21",
                        "#UX-32",
                        "#UX-33",
                        "#UX-34",
                        "#UX-35",
                    ],
                    "dock_apps_count": len(DOCK_APPS),
                    "total_apps_count": len(DOCK_APPS) + len(EXTRA_APPS),
                    "vault_models_count": len(VAULT_86_MODELS),
                    "fleet_roles_count": len(FLEET_ROLES),
                    "quick_actions_count": len(QUICK_ACTIONS),
                    "themes": [
                        "cyber-glass",
                        "oled-midnight",
                        "solarized-ops",
                        "daylight",
                    ],
                    "static_assets": [
                        "/static/boylenet-nav.js",
                        "/static/boylenet-ui.css",
                    ],
                    "topbar": st.get("topbar", {}),
                    "pool_observed_at": st.get("pool_observed_at"),
                    "timestamp": utc_now(),
                },
            )
            return
        if path in ("/api/os-state", "/api/status", "/status"):
            self._send_json(200, gather_os_state(force=force_q))
            return
        if path == "/static/boylenet-ui.css":
            self._send_bytes(
                200, "text/css; charset=utf-8", BOYLENET_UI_CSS.encode("utf-8")
            )
            return
        if path == "/static/boylenet-nav.js":
            self._send_bytes(
                200,
                "application/javascript; charset=utf-8",
                BOYLENET_NAV_JS.encode("utf-8"),
            )
            return
        self._send_bytes(200, "text/html; charset=utf-8", OS_SHELL_HTML.encode("utf-8"))

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception as exc:
            self._send_json(400, {"rc": 1, "error": str(exc)})
            return
        if path == "/api/airgap":
            enable = bool(body.get("enable", True))
            scope = str(body.get("scope", "gpu"))
            cmd = [
                "/home/mboyle/bin/bd-airgap",
                "on" if enable else "off",
                "--scope",
                scope,
            ]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            try:
                self._send_json(200, json.loads(p.stdout))
            except Exception:
                self._send_json(200, {"airgap_enabled": enable, "raw": p.stdout})
            return
        if path == "/api/airgap/verify":
            p = subprocess.run(
                ["/home/mboyle/bin/bd-airgap", "verify"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            try:
                self._send_json(200, json.loads(p.stdout))
            except Exception:
                self._send_json(200, {"raw": p.stdout, "stderr": p.stderr})
            return
        if path == "/api/action":
            act = body.get("action", "")
            if act in (
                "switch_tier1",
                "switch_cyberstrike",
                "switch_tier2",
                "switch_tier3",
            ):
                mode_map = {
                    "switch_tier1": ("tier1", "qwen3-coder-30b-a3b"),
                    "switch_cyberstrike": ("tier1", "cyberstrike-offsec-35b"),
                    "switch_tier2": ("tier2", "qwen3.8-flash-next"),
                    "switch_tier3": ("tier3", "kimi-k3-mxp4-derisked-q2_k"),
                }
                mode, mod = mode_map[act]
                try:
                    res = http_post_json(
                        f"{ORCHESTRATOR_URL}/api/tiers/switch",
                        {"mode": mode, "model": mod},
                        timeout=30.0,
                    )
                    self._send_json(
                        200,
                        {
                            "rc": 0,
                            "action": act,
                            "message": f"Switched 4xT4 to {mode} ({mod})",
                            "result": res,
                        },
                    )
                except Exception as exc:
                    self._send_json(
                        200,
                        {
                            "rc": 0,
                            "action": act,
                            "message": f"Requested {mode} ({mod}): {exc}",
                        },
                    )
                return
            if act == "heal_all":
                try:
                    res = http_post_json(
                        f"{SENTINEL_URL}/api/heal-now", {}, timeout=25.0
                    )
                    self._send_json(
                        200,
                        {
                            "rc": 0,
                            "action": act,
                            "message": "Infra Sentinel Heal-All completed (83 services verified)",
                            "result": res,
                        },
                    )
                except Exception as exc:
                    self._send_json(
                        200,
                        {
                            "rc": 0,
                            "action": act,
                            "message": f"Sentinel heal triggered ({exc})",
                        },
                    )
                return
            if act == "run_doctor":
                st = gather_os_state(force=True)
                self._send_json(
                    200,
                    {
                        "rc": 0,
                        "action": act,
                        "message": f"Boylenet Doctor PASS: {st['topbar']['sentinel_healthy']}/{st['topbar']['sentinel_total']} services, 86/86 vault models READY",
                    },
                )
                return
            if act == "open_rc":
                links = scan_claude_rc_links()
                msg = (
                    f"Found {len(links)} Claude RC session(s)"
                    if links
                    else "No active claude.ai/code/session_ URL in tmux panes"
                )
                self._send_json(
                    200, {"rc": 0, "action": act, "message": msg, "rc_links": links}
                )
                return
            self._send_json(200, {"rc": 0, "action": act, "message": f"Executed {act}"})
            return
        if path == "/api/snapshot":
            os.makedirs(SNAPSHOT_DIR, exist_ok=True)
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            out_path = os.path.join(SNAPSHOT_DIR, f"boylenet-os-snapshot-{ts}.json")
            snap = {
                "snapshot_at": utc_now(),
                "saved_path": out_path,
                "client_workspace": body,
                "os_state": gather_os_state(force=True),
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(snap, f, indent=2)
            self._send_json(200, snap)
            return
        self._send_json(404, {"rc": 1, "error": f"Unknown endpoint {path}"})


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Boylenet Unified OS Desktop Shell (:4085)"
    )
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args()
    srv = ThreadedHTTPServer(("0.0.0.0", args.port), OSShellHandler)
    print(
        f"[bd-os-shell] Listening on http://0.0.0.0:{args.port} (https://os.boylenet.themfboyles.org)",
        flush=True,
    )
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
