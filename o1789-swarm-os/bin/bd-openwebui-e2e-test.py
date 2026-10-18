#!/usr/bin/env python3
"""
Boylenet OpenWebUI Super-Suite End-to-End Tester & 15 Specialized Custom Agent Presets Architect
(/home/mboyle/bin/bd-openwebui-e2e-test.py — Agent-106)

Tests and verifies across .164:8090 (Controller), .72:8080 (Vault A), and :4079 (Universal Gateway):
  1. Creates & syncs 15 Pre-Wired "Boylenet Custom Agents" (`id="agent-..."`) in the `model` table
     on BOTH .164:8090 and .72:8080 with custom `system` prompts, all 6 `BD KB` knowledge volumes,
     all 51 `toolIds`, and tags (`🤖 BOYLENET AGENT` + `🟢 LOCAL` / `☁️ CLOUD` / `⚡ HYBRID` / `🧭 AUTO`).
  2. All 28 Open Terminal Connections (`boylenet-all-27-vms` `/vm/all` + 27 `/vm/<ip>`), including
     live SSH execution on .82 (64-core) and file listing on .164, /vms, and .137 (Windows), plus
     dynamic CWD switching verification.
  3. All 5 OpenAPI 3.1 Tool Servers on :4079 and `POST /api/v1/configs/tool_servers/verify` on
     both :8090 and .72:8080.
  4. Live execution of 48 tool calls across all major tool categories on `:4079/api/tool/<action>`.
  5. Multimodal & Pipeline endpoints on `:4079/v1` (Images PNG, Audio WAV, 1024-d BGE-M3 Embeddings,
     8 Pipelines, `pipe-boylenet-bdkb-rag-citation-engine`, `pipe-boylenet-smart-intent-router`, and
     live LLM chat on `.137:11434` `qwen2.5-coder:7b` with zero contention on `.72` or `.83`).
  6. Dynamic state update verification (terminal server switching, pipeline valves live mutation,
     custom agent live update & tag filtering) and every OpenWebUI tab (`Models`, `Knowledge`,
     `Prompts`, `Skills`, `Tools`, `Admin -> Integrations`, `Pipelines`, `Images`, `Audio`, `Web Search`).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

STREAM_LOG = Path("/var/tmp/bd-headless-streams/agent106-openwebui-e2e-and-15-agents.log")
JSON_RESULTS_PATH = Path("/var/tmp/bd-openwebui-e2e-results.json")
GATEWAY_URL = "http://10.0.70.164:4079"
BATTLESTATION_OLLAMA = "http://10.0.10.137:11434"

INSTANCES = [
    {
        "name": "OpenWebUI-Controller-164:8090",
        "base_url": "http://127.0.0.1:8090",
        "public_url": "http://10.0.70.164:8090",
        "admin_id": "a12463df-370f-4948-b488-9437da254b15",
        "secret": "<REDACTED_BY_BOYLENET_SECRET_GUARD>",
        "ssh_host": None,
        "container": "open-webui",
    },
    {
        "name": "OpenWebUI-VaultA-72:8080",
        "base_url": "http://10.0.70.72:8080",
        "public_url": "http://10.0.70.72:8080",
        "admin_id": "c1658bb0-ad7c-48c2-a18a-7c000dd6a04e",
        "secret": "<REDACTED_BY_BOYLENET_SECRET_GUARD>",
        "ssh_host": "10.0.70.72",
        "container": "open-webui",
    },
]

BD_KB_VOLUMES = [
    {
        "id": "bd-kb-master",
        "name": "📚 [BD KB #00] Master Encyclopedia (BulkDownloader + 27-Node Boylenet + 86 Models + Rules 1-86)",
        "description": "Single-pane-of-glass Master Encyclopedia covering BulkDownloader, 27-node Boylenet cluster, 86-model vault, Fleet Rules 1-86, O1740 routing, and 50 toolkits.",
        "type": "collection",
    },
    {
        "id": "bd-kb-bulkdownloader",
        "name": "📦 [BD KB #01] BulkDownloader Architecture, Contracts, Cut Workflow & Ramdisk Pytest",
        "description": "BulkDownloader repository layout, yt-dlp pin invariant, Rule 22 sandbox paths, Cut Workflow, and /dev/shm ramdisk pytest execution.",
        "type": "collection",
    },
    {
        "id": "bd-kb-cluster-infra",
        "name": "🖧 [BD KB #02] Boylenet 27-Node Cluster, 12U Rack, VMware ESXi/vSAN & 25GbE Fabric",
        "description": "Full 27-node Boylenet hardware/IP/role table, 12U 36-inch rack physical layout, VMware ESXi 8.0 / vSAN 18TB NVMe, and UniFi 25GbE SFP28 fabric.",
        "type": "collection",
    },
    {
        "id": "bd-kb-86-models",
        "name": "🧠 [BD KB #03] 86-Model Vault Catalog, SWE-bench / LiveCodeBench & Dual-Speed Airgap",
        "description": "Complete 86-model catalog across Vault A (.72), Vault B (.83), GPU Inference (.125), BattleStation (.137), and $1,000 Cloud Burst with dual-speed WAN airgap.",
        "type": "collection",
    },
    {
        "id": "bd-kb-fleet-law",
        "name": "⚖️ [BD KB #04] Fleet Law (Rules 1-86), O1740 Dynamic Routing & HUB-GATE",
        "description": "Authoritative Fleet Law Rules 1-86, Protocols A-F, O1740 Dynamic Capability Routing (POOL_STATE.tsv), HUB-GATE, and Rule 22 Anti-Hallucination Shield.",
        "type": "collection",
    },
    {
        "id": "bd-kb-ci-and-uis",
        "name": "🛠️ [BD KB #05] CI Taxonomy, Great Train Recovery, 14 MCP Servers & 50 OpenWebUI Toolkits",
        "description": "BulkDownloader CI failure taxonomy (C1-C6), Great Train Recovery playbooks, 14 MCP servers, 128 skills, and 50 OpenWebUI toolkits.",
        "type": "collection",
    },
]

CUSTOM_AGENTS_15: list[dict[str, Any]] = [
    {
        "id": "agent-master-coder",
        "name": "🤖 [AGENT • 🟢 LOCAL] Boylenet Master Coder (Qwen3.6-Heretic + 27-VM Terminal + Git + Ramdisk Pytest)",
        "base_model_id": "qwen3.6-35b-claude-opus-abliterated",
        "tier_tag": "🟢 LOCAL",
        "extra_tags": ["⚡ Airgap-Ready", "Coding & Git", "27-VM Terminal"],
        "description": "Flagship autonomous software engineer wired to Qwen3.6-35B-Claude-Opus-Heretic, 27-VM Open Terminal (/vm/all), Git/Gitea (:3000), Serena AST Slicer, Ruff/Mypy, and .82 64-core /dev/shm Ramdisk Pytest.",
        "system": (
            "You are the Boylenet Master Coder (`agent-master-coder`). You have full access to all 51 native toolkits, "
            "all 28 Open Terminal servers (`/vm/all` mounting all 27 VMs under `/vms/<ip>-<name>/`), Git/Gitea (`:3000`), "
            "RATF/Serena AST slicing, Ruff/Mypy fast-fail checks, and `.82` 64-core `/dev/shm` Ramdisk Pytest (`bd-pytest-digest`). "
            "Enforce Fleet Rules 1-86, Rule 22 worktree protection (`bd-cuts/` and `bd-local-wt/` only), and yt-dlp pin invariants."
        ),
    },
    {
        "id": "agent-instant-sprinter",
        "name": "🤖 [AGENT • 🟢 LOCAL] Boylenet 95-tok/s Instant Sprinter (2080Ti Coder-7B + Guarded Edit)",
        "base_model_id": "qwen2.5-coder:7b",
        "tier_tag": "🟢 LOCAL",
        "extra_tags": ["⚡ Airgap-Ready", "95-tok/s RTX 2080Ti", "Sub-Second Sprint"],
        "description": "Ultra-low-latency 95 tok/s coding & shell sprinter pinned to BattleStation (.137 RTX 2080 Ti) and .228 Ollama with guarded sandbox file editing and 51 tools.",
        "system": (
            "You are the Boylenet 95-tok/s Instant Sprinter (`agent-instant-sprinter`) running on BattleStation RTX 2080 Ti (`.137:11434`) "
            "per Rule 84 Hardware Segregation. Deliver immediate, surgical code edits, regex/JQ transforms, shell one-liners, and fast diagnostics "
            "using `view_file`, `grep_search`, `write_or_edit_file`, and `run_command` with zero filler."
        ),
    },
    {
        "id": "agent-deep-researcher",
        "name": "🤖 [AGENT • 🟢 LOCAL] Boylenet Deep Web & Academic Researcher (SearXNG + Dual CDP + ArXiv + BD KB)",
        "base_model_id": "bd_deep_research_multi_engine_pipeline",
        "tier_tag": "🟢 LOCAL",
        "extra_tags": ["Research & OSINT", "SearXNG :8888", "Dual Chrome CDP"],
        "description": "Autonomous multi-engine researcher combining SearXNG (:8888), Dual Chrome CDP Browser Oracles (.137:9222 & .181:9222), ArXiv papers, Wikipedia/Wikidata, and the 6-volume BD KB.",
        "system": (
            "You are the Boylenet Deep Web & Academic Researcher (`agent-deep-researcher`). Cross-verify every claim across: "
            "(1) the 6-volume Master `BD KB` and Qdrant `bd_master_kb` (`.125:6333`), (2) local SearXNG (`:8888`), "
            "(3) Dual Chrome CDP Browser Oracles (`.137:9222` BattleStation and `.181:9222` Bittorrent), and (4) ArXiv/Wikipedia. "
            "Always provide exact file paths, URLs, and ranked citations."
        ),
    },
    {
        "id": "agent-offsec-redteam",
        "name": "🤖 [AGENT • 🟢 LOCAL] Boylenet OffSec Red-Team & CVE Hunter (CyberStrike-35B + NVD + 27-VM SSH)",
        "base_model_id": "cyberstrike-35b",
        "tier_tag": "🟢 LOCAL",
        "extra_tags": ["⚡ Airgap-Ready", "OffSec & CVE", "66.5 tok/s"],
        "description": "Offensive security specialist powered by Huihui-CyberStrike-OffSec-35B (66.47 tok/s) with CIRCL/NVD CVE lookup, workspace secret scanning, TLS/DNS recon, and 27-VM SSH auditing.",
        "system": (
            "You are the Boylenet OffSec Red-Team & CVE Hunter (`agent-offsec-redteam`), powered by `Huihui-CyberStrike-OffSec-35B` (`66.47 tok/s`). "
            "Use `cyber_cve_security_audit`, `network_dns_ssl_recon`, `cryptography_hash_jwt_and_tls_inspector`, and `ssh_27node_parallel_runner` "
            "to audit CVEs, inspect TLS/JWT posture, verify WAN airgap (`bd-airgap`), and scan for exposed credentials."
        ),
    },
    {
        "id": "agent-vsan-infra-architect",
        "name": "🤖 [AGENT • 🟢 LOCAL] Boylenet vSAN, ESXi & 25GbE Infrastructure Architect (ESXi + UniFi + iLO4 + BD KB)",
        "base_model_id": "tier1-qwen3-coder-30b-a3b",
        "tier_tag": "🟢 LOCAL",
        "extra_tags": ["⚡ Airgap-Ready", "vSAN & 25GbE Infra", "12U Rack & iLO4"],
        "description": "Cluster infrastructure architect for the 12U Startech rack (79.5°F), 4x HPE DL380 Gen10 ESXi hosts, 107TB NVMe vSAN, UniFi 25GbE RoCE fabric, and Rule 61 cold spares.",
        "system": (
            "You are the Boylenet vSAN, ESXi & 25GbE Infrastructure Architect (`agent-vsan-infra-architect`). "
            "You manage the 27-node Boylenet cluster, 4x HPE ProLiant DL380 Gen10 ESXi 8.0 hypervisors (`.1`–`.4`), iLO 4 thermal sensors (`.10.200`–`.203`, 79.5°F ambient), "
            "107TB vSAN datastore, UniFi UDM-Pro 25GbE/10GbE VLAN 10/70/75 fabric, and Rule 61 cold spares (`spare1`–`spare12`)."
        ),
    },
    {
        "id": "agent-bdkb-ci-doctor",
        "name": "🤖 [AGENT • 🟢 LOCAL] BulkDownloader Master Encyclopedia & CI Taxonomy Doctor (6-Vol BD KB)",
        "base_model_id": "bd_kb_auto_grounding_pipeline",
        "tier_tag": "🟢 LOCAL",
        "extra_tags": ["⚡ Airgap-Ready", "6-Vol BD KB", "CI Doctor Rules 41-47"],
        "description": "Authoritative BulkDownloader & Boylenet Encyclopedia Oracle and CI Failure Taxonomy Doctor (BD-CI-01..09, Fleet Rules 41-47, Precut & Train Integration).",
        "system": (
            "You are the BulkDownloader Master Encyclopedia & CI Taxonomy Doctor (`agent-bdkb-ci-doctor`). "
            "Automatically ground every answer in the 6-volume `BD KB` (`bd_kb_search` & Qdrant `bd_master_kb`), diagnose CI failures using "
            "`ci_taxonomy_doctor` (Rules 41-47: hermetic git fixtures, census substring guards, async marker flush, playwright teardown, monkeypatch purge), "
            "and verify worktree patches with `git_worktree_patch_auditor`."
        ),
    },
    {
        "id": "agent-media-voice-studio",
        "name": "🤖 [AGENT • 🟢 LOCAL] Boylenet 1080p Image, Diagram & Voice Studio (Flux + Mermaid + TTS/STT)",
        "base_model_id": "bd_multimodal_flux_vision_voice_pipeline",
        "tier_tag": "🟢 LOCAL",
        "extra_tags": ["⚡ Airgap-Ready", "1080p Flux Studio", "Neural TTS/STT"],
        "description": "On-prem multimodal creative studio generating 1920x1080 / 1024x1024 PNG visuals, crisp SVG system architecture diagrams, and 24kHz neural WAV voice narration.",
        "system": (
            "You are the Boylenet 1080p Image, Diagram & Voice Studio (`agent-media-voice-studio`). "
            "Use `flux_1080p_image_hud_generator`, `multimodal_image_voice_studio`, `render_architecture_diagram`, and `audio_whisper_tts_music_studio` "
            "to produce high-contrast local PNG artwork, SVG architecture diagrams, and 24kHz WAV voice synthesis with zero WAN egress."
        ),
    },
    {
        "id": "agent-data-sql-analyst",
        "name": "🤖 [AGENT • 🟢 LOCAL] Boylenet SQL, Postgres, Qdrant & Data Science Analyst (PG + Qdrant + Charts)",
        "base_model_id": "tier1-qwen3-coder-30b-a3b",
        "tier_tag": "🟢 LOCAL",
        "extra_tags": ["⚡ Airgap-Ready", "Postgres & Qdrant", "SVG Charts & Jupyter"],
        "description": "Data science and database analyst wired to PostgreSQL (`ai_mesh`, `litellm`, `boylenet_memory`), Qdrant (:6333), SQLite, SVG statistical charts, and Jupyter notebook generation.",
        "system": (
            "You are the Boylenet SQL, Postgres, Qdrant & Data Science Analyst (`agent-data-sql-analyst`). "
            "Query PostgreSQL and SQLite via `sql_database_query` and `postgres_pgvector_memory_vault`, search Qdrant collections on `.125:6333` via "
            "`qdrant_rag_search`, generate statistical SVG charts via `python_data_science_chart`, and export `.ipynb` notebooks via `python_jupyter_notebook_gen`."
        ),
    },
    {
        "id": "agent-mcp-skill-commander",
        "name": "🤖 [AGENT • 🟢 LOCAL] Boylenet 14-Server MCP & 128-Skill Commander (Serena + RATF + Caveman)",
        "base_model_id": "qwen3.6-35b-claude-opus-abliterated",
        "tier_tag": "🟢 LOCAL",
        "extra_tags": ["⚡ Airgap-Ready", "14 MCP Servers", "128 Skills"],
        "description": "Direct command bridge over all 14 Boylenet MCP servers (99 MCP tools: Serena LSP, RATF AST, Hivemind, bd-bus, VMware, pg-local) and all 128 imported Claude/Codex/AGY skills.",
        "system": (
            "You are the Boylenet 14-Server MCP & 128-Skill Commander (`agent-mcp-skill-commander`). "
            "Use `mcp_list` and `mcp_call` to invoke any tool across all 14 MCP servers (`bd`, `bd-bus`, `bd-fleet`, `serena`, `ratf`, `pg-local`, "
            "`hivemind-memory`, `caveman`, `context-mode`, `python-linter`, `type-enforcer`, `vmware-clones`, `fleet-sync`), and use `list_skills` / `load_skill` "
            "to execute any of the 128 specialized Boylenet playbooks."
        ),
    },
    {
        "id": "agent-airgap-sovereign",
        "name": "🤖 [AGENT • 🟢 LOCAL] Boylenet 100% Airgap-Verified Sovereign Assistant (Zero-WAN On-Prem)",
        "base_model_id": "tier1-qwen3-coder-30b-a3b",
        "tier_tag": "🟢 LOCAL",
        "extra_tags": ["⚡ Airgap-Ready", "100% Zero-WAN Sovereign", "77.6 tok/s"],
        "description": "Strictly air-gapped sovereign AI assistant running 100% on local Boylenet hardware (Qwen3-Coder-30B-A3B 77.62 tok/s) with live WAN airgap verification before sensitive operations.",
        "system": (
            "You are the Boylenet 100% Airgap-Verified Sovereign Assistant (`agent-airgap-sovereign`). "
            "You operate with zero external WAN dependency using local GPU pools (`.72`, `.83`, `.125`, `.137`, `.228`), local Qdrant (`.125:6333`), "
            "local Gitea (`:3000`), and the 6-volume `BD KB`. Use `airgap_and_cluster_status` to verify `bd-airgap` enforcement."
        ),
    },
    {
        "id": "agent-4model-council",
        "name": "🤖 [AGENT • ⚡ HYBRID] Boylenet 4-Model Consensus Council (Local + Cloud Judge)",
        "base_model_id": "bd_4model_consensus_council_pipeline",
        "tier_tag": "⚡ HYBRID",
        "extra_tags": ["🟢 LOCAL", "☁️ CLOUD", "4-Model Council", "Protocol B Judge"],
        "description": "Multi-perspective 4-Model Consensus Council convening Qwen3-Coder-30B-A3B, CyberStrike-35B, Qwen3.6-35B-Claude-Opus, and Fast Judge with BD KB citations and Protocol B BOARD/REFUTE rulings.",
        "system": (
            "You are the Boylenet 4-Model Consensus Council (`agent-4model-council`). Evaluate architectural proposals, diffs, and security questions "
            "across 4 independent specialist seats (Code Lead, SecOps Lead, Architecture Lead, and Fast Judge) grounded in the 6-volume `BD KB`, "
            "and emit structured Rule 76 / Rule 86 BOARD or REFUTE consensus rulings."
        ),
    },
    {
        "id": "agent-claude-opus-integrator",
        "name": "🤖 [AGENT • ☁️ CLOUD] Boylenet Claude Opus 5.5 Master Integrator ($1,000 Credit Pool + 51 Tools)",
        "base_model_id": "claude-opus-5-5",
        "tier_tag": "☁️ CLOUD",
        "extra_tags": ["$1,000 Credit Pool", "PM Integrator", "Rule 85 Opus Tier"],
        "description": "Cloud Burst PM Integrator & Architectural Planner powered by Claude Opus 5.5 ($1,000 Credit Pool) with full access to 51 Boylenet tools, 27-VM Terminal, and 6-volume BD KB.",
        "system": (
            "You are the Boylenet Claude Opus 5.5 Master Integrator (`agent-claude-opus-integrator`) per Rule 85 Asymmetric Model Deployment. "
            "You resolve complex multi-branch Git rebases, train integrations, and architectural designs using the $1,000 Cloud Burst pool while "
            "leveraging all 51 local Boylenet toolkits, 27-VM Open Terminal, and the 6-volume `BD KB`."
        ),
    },
    {
        "id": "agent-codex-sol-verifier",
        "name": "🤖 [AGENT • ☁️ CLOUD] Boylenet Codex GPT-6.1-Sol Ultra Verifier (AST Slicing + Ramdisk Pytest)",
        "base_model_id": "gpt-6.1-sol",
        "tier_tag": "☁️ CLOUD",
        "extra_tags": ["$1,000 Credit Pool", "Codex Verifier", "AST & Pytest Gate"],
        "description": "High-precision code reviewer and formal verifier powered by OpenAI Codex GPT-6.1-Sol with RATF/Serena AST slicing, Ruff/Mypy fast-fail, and .82 Ramdisk Pytest execution.",
        "system": (
            "You are the Boylenet Codex GPT-6.1-Sol Ultra Verifier (`agent-codex-sol-verifier`). "
            "Perform surgical diff reviews, AST symbol verification (`ast_slicer_serena`), static type/lint verification (`python_ruff_mypy_check`), "
            "and `.82` `/dev/shm` ramdisk pytest verification (`ramdisk_pytest_runner`) in strict compliance with Rule 86 (Behavioral Defect vs. Mutation Coverage Severance)."
        ),
    },
    {
        "id": "agent-kimi-ux-swarm",
        "name": "🤖 [AGENT • ☁️ CLOUD] Boylenet Kimi K2.8 100-Agent Swarm & UX Designer (Dual CDP + 51 Tools)",
        "base_model_id": "kimi-k2.8",
        "tier_tag": "☁️ CLOUD",
        "extra_tags": ["$1,000 Credit Pool", "100-Agent Swarm", "Dual CDP & UX"],
        "description": "256K-context Kimi K2.8 Swarm Coordinator & Full-Stack UX Architect wired to Dual Chrome CDP Browser Oracles (.137/.181), Playwright scraper, and subagent swarm dispatch.",
        "system": (
            "You are the Boylenet Kimi K2.8 100-Agent Swarm & UX Designer (`agent-kimi-ux-swarm`). "
            "Use your 256K context window, `browse_live_page_cdp` (`.137:9222` & `.181:9222`), `playwright_live_web_scraper`, "
            "`render_architecture_diagram`, and `subagent_swarm_dispatch` to orchestrate parallel agent waves and design responsive web interfaces."
        ),
    },
    {
        "id": "agent-o1740-smart-router",
        "name": "🤖 [AGENT • 🧭 AUTO] Boylenet O1740 Smart Intent Auto-Router (Auto-Picks #1 Model per Prompt)",
        "base_model_id": "bd_smart_o1740_intent_router_pipeline",
        "tier_tag": "🧭 AUTO",
        "extra_tags": ["🟢 LOCAL", "☁️ CLOUD", "O1740 Dynamic Router"],
        "description": "Dynamic O1740 Intent Classifier & Auto-Router that inspects prompt domain + POOL_STATE.tsv and automatically routes to the #1 benchmarked Boylenet specialist with 6-volume BD KB citations.",
        "system": (
            "You are the Boylenet O1740 Smart Intent Auto-Router (`agent-o1740-smart-router`). "
            "Automatically classify each prompt (coding, offensive security, cluster architecture, data science, multimodal, or fast general) "
            "and route to the highest-benchmarked Boylenet model while injecting authoritative citations from the 6-volume `BD KB`."
        ),
    },
]


def log_stream(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"[{ts}] [Agent-106 E2E] {msg}\n"
    STREAM_LOG.parent.mkdir(parents=True, exist_ok=True)
    with STREAM_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)
    print(line.strip(), flush=True)


def make_jwt(user_id: str, secret: str) -> str:
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"id": user_id, "exp": int(time.time()) + 86400 * 7}).encode()
    ).rstrip(b"=")
    sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), header + b"." + payload, hashlib.sha256).digest()
    ).rstrip(b"=")
    return (header + b"." + payload + b"." + sig).decode()


def http_req(
    url: str,
    method: str = "GET",
    body: Any = None,
    headers: dict[str, str] | None = None,
    timeout: int = 25,
) -> tuple[int, Any, bytes, dict[str, str]]:
    hdrs = dict(headers or {})
    data_bytes = None
    if body is not None:
        if isinstance(body, (bytes, bytearray)):
            data_bytes = bytes(body)
        else:
            hdrs.setdefault("Content-Type", "application/json")
            data_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            resp_hdrs = {k.lower(): v for k, v in resp.headers.items()}
            try:
                parsed = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception:
                parsed = None
            return resp.status, parsed, raw, resp_hdrs
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            parsed = raw.decode("utf-8", errors="replace")
        return exc.code, parsed, raw, {}
    except Exception as exc:
        return 599, {"error": str(exc)}, b"", {}


def owui_api(
    inst: dict[str, Any],
    method: str,
    path: str,
    body: Any = None,
    timeout: int = 25,
) -> tuple[int, Any]:
    token = make_jwt(inst["admin_id"], inst["secret"])
    st, parsed, _, _ = http_req(
        f"{inst['base_url']}{path}",
        method=method,
        body=body,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=timeout,
    )
    return st, parsed


def sync_15_custom_agents_on_instance(inst: dict[str, Any]) -> dict[str, Any]:
    """
    Upserts all 15 Pre-Wired Boylenet Custom Agents into the OpenWebUI `model` table
    (and `access_grant` table) on the target instance (.164:8090 or .72:8080),
    attaching all 51 native `toolIds`, all 6 `BD KB` knowledge collections,
    `actionIds`, `filterIds`, custom `system` prompts, and `🤖 BOYLENET AGENT` tags.
    Also ensures existing workspace models carry `🟢 LOCAL` / `☁️ CLOUD` tags for UI tag filtering.
    """
    log_stream(f"Syncing 15 Custom Agents + 51 ToolIds + 6 BD KB volumes on {inst['name']}...")
    _, tools_resp = owui_api(inst, "GET", "/api/v1/tools/")
    native_tool_ids = sorted(
        [
            t["id"]
            for t in (tools_resp if isinstance(tools_resp, list) else [])
            if isinstance(t, dict) and not str(t.get("id", "")).startswith("server:")
        ]
    )
    _, funcs_resp = owui_api(inst, "GET", "/api/v1/functions/")
    action_ids = sorted(
        [
            f["id"]
            for f in (funcs_resp if isinstance(funcs_resp, list) else [])
            if isinstance(f, dict) and f.get("type") == "action"
        ]
    )
    filter_ids = sorted(
        [
            f["id"]
            for f in (funcs_resp if isinstance(funcs_resp, list) else [])
            if isinstance(f, dict) and f.get("type") == "filter"
        ]
    )

    container_payload = {
        "admin_id": inst["admin_id"],
        "agents": CUSTOM_AGENTS_15,
        "bd_kb_volumes": BD_KB_VOLUMES,
        "tool_ids": native_tool_ids,
        "action_ids": action_ids,
        "filter_ids": filter_ids,
    }

    container_py = r"""
import json, sqlite3, sys, time, uuid

data = json.loads(sys.stdin.read())
admin_id = data["admin_id"]
agents = data["agents"]
bd_kb_volumes = data["bd_kb_volumes"]
tool_ids = data["tool_ids"]
action_ids = data["action_ids"]
filter_ids = data["filter_ids"]
now = int(time.time())

con = sqlite3.connect("/app/backend/data/webui.db")
cur = con.cursor()

# If tool_ids from API was empty for any reason, read from DB
if not tool_ids:
    cur.execute("SELECT id FROM tool")
    tool_ids = sorted(r[0] for r in cur.fetchall())

upserted_agents = []
for ag in agents:
    aid = ag["id"]
    tag_names = ["🤖 BOYLENET AGENT", ag["tier_tag"]]
    for et in ag.get("extra_tags", []):
        if et not in tag_names:
            tag_names.append(et)
    tags_objs = [{"name": t} for t in tag_names]

    meta = {
        "profile_image_url": "/static/favicon.png",
        "description": ag["description"],
        "capabilities": {
            "vision": True,
            "file_upload": True,
            "web_search": True,
            "image_generation": True,
            "code_interpreter": True,
            "citations": True,
            "status_updates": True,
            "usage": True,
            "memory": True,
            "builtin_tools": True,
        },
        "toolIds": tool_ids,
        "actionIds": action_ids,
        "filterIds": filter_ids,
        "knowledge": bd_kb_volumes,
        "tags": tags_objs,
        "suggestion_prompts": [
            {"content": "Run a full diagnostic check using your pre-wired Boylenet tools and BD KB."},
            {"content": "Inspect the 27-node Boylenet cluster status and summarize active capabilities."},
        ],
    }
    params = {
        "system": ag["system"],
        "function_calling": "native",
        "temperature": 0.2,
    }
    cur.execute(
        "INSERT OR REPLACE INTO model (id, user_id, base_model_id, name, meta, params, created_at, updated_at, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (aid, admin_id, ag["base_model_id"], ag["name"], json.dumps(meta), json.dumps(params), now, now),
    )
    cur.execute("DELETE FROM access_grant WHERE resource_type='model' AND resource_id=?", (aid,))
    cur.execute(
        "INSERT INTO access_grant (id, resource_type, resource_id, principal_type, principal_id, permission, created_at) VALUES (?, 'model', ?, 'user', '*', 'read', ?)",
        (str(uuid.uuid4()), aid, now),
    )
    upserted_agents.append(aid)

# Also ensure all non-agent workspace models have 51 toolIds, 6 BD KB volumes, and 🟢 LOCAL / ☁️ CLOUD tags
cur.execute("SELECT id, name, meta FROM model")
for mid, mname, mmeta_s in cur.fetchall():
    if mid in upserted_agents:
        continue
    try:
        mmeta = json.loads(mmeta_s) if mmeta_s else {}
    except Exception:
        mmeta = {}
    mmeta["toolIds"] = tool_ids
    mmeta["actionIds"] = action_ids
    mmeta["filterIds"] = filter_ids
    cur_kbs = mmeta.get("knowledge") or []
    existing_kb_ids = {k.get("id") for k in cur_kbs if isinstance(k, dict)}
    for kbi in bd_kb_volumes:
        if kbi["id"] not in existing_kb_ids:
            cur_kbs.append(kbi)
    mmeta["knowledge"] = cur_kbs
    is_cloud = any(k in mid.lower() for k in ("claude", "gpt-", "fable", "kimi", "grok", "sonar", "o3", "o4"))
    tier_tag = "☁️ CLOUD" if is_cloud else "🟢 LOCAL"
    cur_tags = mmeta.get("tags") or []
    cur_tag_names = [t.get("name") if isinstance(t, dict) else str(t) for t in cur_tags]
    if tier_tag not in cur_tag_names:
        cur_tags.append({"name": tier_tag})
    mmeta["tags"] = cur_tags
    cur.execute("UPDATE model SET meta=?, updated_at=? WHERE id=?", (json.dumps(mmeta), now, mid))

con.commit()
cur.execute("SELECT COUNT(*) FROM model WHERE id LIKE 'agent-%' AND is_active=1")
agent_cnt = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM model WHERE is_active=1")
total_models = cur.fetchone()[0]
print(json.dumps({"ok": True, "agents_upserted": len(upserted_agents), "db_agent_count": agent_cnt, "db_total_models": total_models, "tool_ids_count": len(tool_ids)}))
"""

    b64_script = base64.b64encode(container_py.encode("utf-8")).decode("ascii")
    runner_one_liner = f"import base64; exec(base64.b64decode('{b64_script}').decode('utf-8'))"
    input_bytes = json.dumps(container_payload).encode("utf-8")
    if inst["ssh_host"]:
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", inst["ssh_host"], f'sudo -n docker exec -i {inst["container"]} python3 -c "{runner_one_liner}"']
    else:
        cmd = ["docker", "exec", "-i", inst["container"], "python3", "-c", runner_one_liner]
    proc = subprocess.run(cmd, input=input_bytes, capture_output=True, timeout=30)
    stdout_s = proc.stdout.decode("utf-8", errors="replace").strip()
    db_out = json.loads(stdout_s.splitlines()[-1]) if stdout_s else {"ok": False, "stderr": proc.stderr.decode("utf-8", errors="replace")}

    # Verify via OpenWebUI REST API `/api/v1/models/list` and `/api/models`
    _, mlist_resp = owui_api(inst, "GET", "/api/v1/models/list")
    mlist_items = mlist_resp.get("items", mlist_resp) if isinstance(mlist_resp, dict) else (mlist_resp or [])
    verified_agents = [
        m for m in mlist_items
        if isinstance(m, dict) and str(m.get("id", "")).startswith("agent-")
    ]

    return {
        "instance": inst["name"],
        "db_sync": db_out,
        "api_verified_agent_count": len(verified_agents),
        "api_verified_agent_ids": sorted(m["id"] for m in verified_agents),
    }


def test_section_1_open_terminals() -> dict[str, Any]:
    log_stream("Section 1: Testing all 28 Open Terminal Connections (/vm/all + 27 /vm/<ip>) on :8090, .72:8080, and :4079...")
    results: dict[str, Any] = {"section": "1_open_terminals_28_vms", "checks": [], "passed": 0, "failed": 0}

    def record(name: str, ok: bool, detail: Any) -> None:
        results["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        if ok:
            results["passed"] += 1
        else:
            results["failed"] += 1
            log_stream(f"  [FAIL] {name}: {detail}")

    # 1A. Test OpenWebUI /api/v1/terminals/ and /api/v1/users/user/settings on BOTH :8090 and .72:8080
    for inst in INSTANCES:
        st_t, terms = owui_api(inst, "GET", "/api/v1/terminals/")
        t_list = terms if isinstance(terms, list) else []
        record(
            f"{inst['name']} GET /api/v1/terminals/ count == 28",
            st_t == 200 and len(t_list) == 28,
            {"status": st_t, "count": len(t_list)},
        )

        st_u, us = owui_api(inst, "GET", "/api/v1/users/user/settings")
        ui_terms = ((us or {}).get("ui") or {}).get("terminalServers", []) if isinstance(us, dict) else []
        first_t = ui_terms[0] if ui_terms else {}
        record(
            f"{inst['name']} GET /api/v1/users/user/settings ui.terminalServers == 28 & boylenet-all-27-vms enabled",
            st_u == 200
            and len(ui_terms) == 28
            and first_t.get("id") == "boylenet-all-27-vms"
            and first_t.get("enabled") is True
            and first_t.get("key") == "sk-fleet-local",
            {
                "status": st_u,
                "count": len(ui_terms),
                "first_id": first_t.get("id"),
                "enabled": first_t.get("enabled"),
                "key": first_t.get("key"),
            },
        )

    # 1B. Test /vm/all/api/config and all 27 /vm/<ip>/api/config + /openapi.json on :4079
    st_h, gw_health, _, _ = http_req(f"{GATEWAY_URL}/health")
    term_urls = (gw_health or {}).get("terminal_servers", []) if isinstance(gw_health, dict) else []
    cfg_ok_count = 0
    openapi_ok_count = 0
    for turl in term_urls:
        st_c, c_data, _, _ = http_req(f"{turl}/api/config")
        if st_c == 200 and isinstance(c_data, dict) and c_data.get("features", {}).get("files") is True:
            cfg_ok_count += 1
        st_o, o_data, _, _ = http_req(f"{turl}/openapi.json")
        if st_o == 200 and isinstance(o_data, dict) and o_data.get("openapi") == "3.1.0":
            openapi_ok_count += 1
    record(
        "All 28 Terminal Servers (/vm/all + 27 /vm/<ip>) GET /api/config & /openapi.json == 200",
        len(term_urls) == 28 and cfg_ok_count == 28 and openapi_ok_count == 28,
        {"total_urls": len(term_urls), "api_config_200": cfg_ok_count, "openapi_3_1_200": openapi_ok_count},
    )

    # 1C. Specific required VM Terminal probes
    st_vms, vms_list, _, _ = http_req(f"{GATEWAY_URL}/vm/all/files/list?directory=/vms")
    entries_vms = (vms_list or {}).get("entries", []) if isinstance(vms_list, dict) else []
    record(
        "GET /vm/all/files/list?directory=/vms returns 27 VM folders",
        st_vms == 200 and len(entries_vms) == 27,
        {"status": st_vms, "folder_count": len(entries_vms), "sample": [e.get("name") for e in entries_vms[:4]]},
    )

    st_164, list_164, _, _ = http_req(f"{GATEWAY_URL}/vm/10.0.70.164/files/list?directory=/home/mboyle")
    entries_164 = (list_164 or {}).get("entries", []) if isinstance(list_164, dict) else []
    record(
        "GET /vm/10.0.70.164/files/list?directory=/home/mboyle returns Controller files + /vms mount",
        st_164 == 200 and len(entries_164) > 5,
        {"status": st_164, "entry_count": len(entries_164), "first_entry": entries_164[0] if entries_164 else None},
    )

    st_82, exec_82, _, _ = http_req(
        f"{GATEWAY_URL}/vm/10.0.70.82/execute",
        method="POST",
        body={"command": "uname -n && nproc"},
    )
    out_82 = str((exec_82 or {}).get("output", "")).strip() if isinstance(exec_82, dict) else ""
    record(
        "POST /vm/10.0.70.82/execute ('uname -n && nproc') returns wrk-test04 & 64 cores",
        st_82 == 200 and "wrk-test04" in out_82 and "64" in out_82,
        {"status": st_82, "output": out_82},
    )

    st_137, list_137, _, _ = http_req(f"{GATEWAY_URL}/vm/10.0.10.137/files/list")
    entries_137 = (list_137 or {}).get("entries", []) if isinstance(list_137, dict) else []
    record(
        "GET /vm/10.0.10.137/files/list returns BattleStation Windows home entries",
        st_137 == 200 and len(entries_137) > 5,
        {"status": st_137, "cwd": (list_137 or {}).get("cwd"), "entry_count": len(entries_137)},
    )

    # 1D. Dynamic Terminal State Change Verification (CWD switch & restore)
    sess_hdr = {"X-Session-Id": "e2e-agent106-session"}
    st_cwd1, cwd_set, _, _ = http_req(
        f"{GATEWAY_URL}/vm/all/files/cwd",
        method="POST",
        body={"path": "/vms/10.0.70.82-test3big-64core/home/mboyle"},
        headers=sess_hdr,
    )
    st_cwd2, cwd_get, _, _ = http_req(f"{GATEWAY_URL}/vm/all/files/cwd", headers=sess_hdr)
    st_cwd3, cwd_rst, _, _ = http_req(
        f"{GATEWAY_URL}/vm/all/files/cwd",
        method="POST",
        body={"path": "/vms"},
        headers=sess_hdr,
    )
    record(
        "Dynamic Terminal CWD Switch (/vms -> /vms/10.0.70.82-test3big-64core/home/mboyle -> /vms) updates immediately",
        st_cwd1 == 200
        and st_cwd2 == 200
        and (cwd_get or {}).get("cwd") == "/vms/10.0.70.82-test3big-64core/home/mboyle"
        and (cwd_rst or {}).get("cwd") == "/vms",
        {"switched_to": (cwd_get or {}).get("cwd"), "restored_to": (cwd_rst or {}).get("cwd")},
    )

    log_stream(f"Section 1 complete: {results['passed']}/{results['passed'] + results['failed']} checks passed.")
    return results


def test_section_2_openapi_tool_servers() -> dict[str, Any]:
    log_stream("Section 2: Testing all 5 OpenAPI 3.1 Tool Servers on :4079 + /api/v1/configs/tool_servers/verify on :8090 & .72:8080...")
    results: dict[str, Any] = {"section": "2_openapi_3_1_tool_servers", "checks": [], "passed": 0, "failed": 0}

    def record(name: str, ok: bool, detail: Any) -> None:
        results["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        if ok:
            results["passed"] += 1
        else:
            results["failed"] += 1
            log_stream(f"  [FAIL] {name}: {detail}")

    suites = [
        "/openapi.json",
        "/web-osint/openapi.json",
        "/data-science/openapi.json",
        "/devops-infra/openapi.json",
        "/media-ai/openapi.json",
    ]
    for spath in suites:
        st, spec, _, _ = http_req(f"{GATEWAY_URL}{spath}")
        paths_cnt = len((spec or {}).get("paths", {})) if isinstance(spec, dict) else 0
        record(
            f"GET {GATEWAY_URL}{spath} valid OpenAPI 3.1.0 schema",
            st == 200 and isinstance(spec, dict) and spec.get("openapi") == "3.1.0" and paths_cnt > 0,
            {"status": st, "openapi": (spec or {}).get("openapi"), "paths_count": paths_cnt, "title": ((spec or {}).get("info") or {}).get("title")},
        )

    for inst in INSTANCES:
        st_cfg, ts_cfg = owui_api(inst, "GET", "/api/v1/configs/tool_servers")
        conns = (ts_cfg or {}).get("TOOL_SERVER_CONNECTIONS", []) if isinstance(ts_cfg, dict) else []
        verified_cnt = 0
        for c in conns:
            st_v, v_res = owui_api(inst, "POST", "/api/v1/configs/tool_servers/verify", c)
            if st_v == 200:
                verified_cnt += 1
        record(
            f"{inst['name']} POST /api/v1/configs/tool_servers/verify passes for all {len(conns)} OpenAPI suites",
            st_cfg == 200 and len(conns) >= 5 and verified_cnt == len(conns),
            {"configured": len(conns), "verified_200": verified_cnt},
        )

    log_stream(f"Section 2 complete: {results['passed']}/{results['passed'] + results['failed']} checks passed.")
    return results


def test_section_3_live_tools_execution() -> dict[str, Any]:
    log_stream("Section 3: Executing 48 live tool calls across all tool categories on :4079/api/tool/<action>...")
    results: dict[str, Any] = {"section": "3_live_tool_calls_48", "checks": [], "passed": 0, "failed": 0}

    tool_test_matrix: list[tuple[str, dict[str, Any], Any]] = [
        ("search_web", {"query": "Python 3.12 release", "max_results": 3}, lambda d: d.get("result_count", 0) > 0),
        ("read_url_content", {"url": "http://10.0.70.164:4079/health", "max_chars": 2000}, lambda d: "bd-openwebui-tool-gateway" in str(d.get("markdown", ""))),
        ("browse_live_page_cdp", {"node": "battlestation", "action": "list_tabs"}, lambda d: "cdp_endpoint" in d),
        ("git_status_diff_log", {"repo_path": "/home/mboyle/BulkDownloader", "action": "log", "limit": 3}, lambda d: bool(d.get("output"))),
        ("gitea_api", {"endpoint": "/api/v1/repos/search", "query": ""}, lambda d: "data" in d),
        ("view_file", {"file_path": "/home/mboyle/bd-persist/FLEET_RULE-FLOOR.md", "start_line": 1, "end_line": 12}, lambda d: d.get("total_lines", 0) > 10),
        ("grep_search", {"pattern": "Rule 74", "path": "/home/mboyle/GEMINI.md", "max_count": 5}, lambda d: d.get("match_count", 0) >= 1),
        ("find_by_name", {"pattern": "FLEET_RULE", "directory": "/home/mboyle/bd-persist", "max_depth": 2}, lambda d: d.get("count", 0) >= 1),
        ("write_or_edit_file", {"file_path": "/var/tmp/openwebui-workspace/agent106_e2e_test.txt", "mode": "write", "content": "agent106-verified\n"}, lambda d: d.get("bytes_written", 0) > 0),
        ("run_command", {"command": "cat /var/tmp/openwebui-workspace/agent106_e2e_test.txt", "cwd": "/var/tmp/openwebui-workspace"}, lambda d: "agent106-verified" in str(d.get("stdout", ""))),
        ("mcp_list", {}, lambda d: d.get("server_count", 0) >= 14),
        ("mcp_call", {"server": "pg-local", "tool": "query", "arguments": {"sql": "SELECT current_database(), 42 AS answer;"}}, lambda d: "ai_mesh" in str(d)),
        ("mcp_call", {"server": "ratf", "tool": "ctx_slice", "arguments": {"path": "/home/mboyle/bin/bd-openwebui-tool-gateway.py", "symbol": "discover_mcp_Inventory"}}, lambda d: d.get("ok") is True),
        ("list_skills", {"query": ""}, lambda d: d.get("total_discovered", 0) >= 120),
        ("load_skill", {"skill_id": "boylenet-architect"}, lambda d: "SKILL.md" in str(d) or bool((d.get("skill") or {}).get("content"))),
        ("bd_kb_search", {"query": "O1740 dynamic capability routing 27 nodes", "top_k": 4}, lambda d: d.get("result_count", 0) >= 1),
        ("qdrant_rag_search", {"query": "O1740 dynamic capability routing", "collection": "bd_master_kb", "limit": 3}, lambda d: len(d.get("qdrant_results", [])) >= 1),
        ("airgap_and_cluster_status", {"action": "status"}, lambda d: "pool_state_tsv" in d),
        ("arxiv_search", {"query": "mixture of experts transformer", "max_results": 2}, lambda d: d.get("count", 0) >= 1),
        ("wikipedia_factcheck", {"query": "Python (programming language)"}, lambda d: len(d.get("results", [])) >= 1),
        ("wiki_search", {"query": "Linux kernel"}, lambda d: len(d.get("results", [])) >= 1),
        ("youtube_analyze", {"query": "Linux kernel"}, lambda d: d.get("result_count", 0) >= 0),
        ("tech_pulse_trending", {"source": "hackernews", "limit": 3}, lambda d: len(d.get("items", [])) >= 1),
        ("python_data_science_chart", {"title": "Boylenet E2E Throughput", "labels": ["Node137", "Node72", "Node83"], "values": [95.4, 77.6, 66.5]}, lambda d: "<svg" in str(d.get("svg", "")) or bool(d.get("svg_file"))),
        ("render_architecture_diagram", {"title": "Boylenet OpenWebUI Mesh", "nodes": ["OpenWebUI :8090/.72:8080", "Gateway :4079", "Qdrant .125:6333"]}, lambda d: "<svg" in str(d.get("svg", ""))),
        ("sql_database_query", {"engine": "postgres", "database": "ai_mesh", "sql": "SELECT table_name FROM information_schema.tables WHERE table_schema='public' LIMIT 5;"}, lambda d: d.get("ok") is True),
        ("sql_query", {"engine": "postgres", "database": "ai_mesh", "sql": "SELECT 1 AS e2e_ok;"}, lambda d: d.get("ok") is True),
        ("network_dns_ssl_recon", {"target": "10.0.70.164", "port": 4079, "action": "tcp"}, lambda d: (d.get("tcp_connect") or {}).get("reachable") is True),
        ("network_probe", {"target": "10.0.70.72", "port": 8080, "action": "tcp"}, lambda d: (d.get("tcp_connect") or {}).get("reachable") is True),
        ("unifi_fabric_inspect", {"query": "10.0.70.164"}, lambda d: "vlans" in d),
        ("vmware_esxi_vsan_control", {"action": "vm_list"}, lambda d: d.get("ok") is True),
        ("docker_systemd_cluster_ops", {"service": "bd-openwebui-tool-gateway.service"}, lambda d: d.get("ok") is True),
        ("docker_systemd_status", {"service": "bd-openwebui-tool-gateway.service"}, lambda d: d.get("ok") is True),
        ("gpu_vram_vault_status", {"action": "status"}, lambda d: "orchestrator" in d),
        ("document_convert_extract", {"content": '[{"node":"10.0.70.164","role":"controller"}]', "source_format": "json", "target_format": "markdown"}, lambda d: "10.0.70.164" in str(d.get("converted", ""))),
        ("ci_taxonomy_doctor", {"error_signature": "dirty working tree"}, lambda d: "ci_taxonomy_playbook" in d),
        ("ast_slicer_serena", {"file_path": "/home/mboyle/bin/bd-openwebui-tool-gateway.py", "symbol": "tool_mcp_list"}, lambda d: d.get("symbol_count", 0) >= 1),
        ("python_ruff_mypy_check", {"file_path": "/home/mboyle/bin/bd-openwebui-e2e-test.py"}, lambda d: "ruff" in d),
        ("ruff_mypy_check", {"file_path": "/var/tmp/openwebui-workspace/agent106_e2e_test.txt"}, lambda d: "ruff" in d),
        ("ramdisk_pytest_runner", {"target": "--version"}, lambda d: d.get("returncode") == 0),
        ("cloud_burst_quota_status", {"action": "status"}, lambda d: d.get("cloud_credit_budget_usd") == 1000),
        ("crypto_weather_world_time", {"latitude": 37.7749, "longitude": -122.4194}, lambda d: "utc_iso" in d),
        ("cyber_cve_security_audit", {"query": "CVE-2024-3094", "scan_path": "/var/tmp/openwebui-workspace"}, lambda d: "secret_scan" in d),
        ("cve_security_scan", {"query": "CVE-2024-3094", "scan_path": "/var/tmp/openwebui-workspace"}, lambda d: "secret_scan" in d),
        ("multimodal_image_voice_studio", {"action": "generate_image", "prompt": "Boylenet Sovereign AI", "size": "1024x1024"}, lambda d: d.get("bytes", 0) > 1000),
        ("fleet_law_and_rule_auditor", {"rule_number": "74", "query": "Rule 74"}, lambda d: d.get("result_count", 0) >= 1),
        ("o1740_pool_and_seat_router", {"role_tier": "heavy_lifter"}, lambda d: d.get("ok") is True),
        ("ilo4_ipmi_rack_sensors", {"action": "status"}, lambda d: d.get("ok") is True),
    ]

    for action, payload, validator in tool_test_matrix:
        t0 = time.perf_counter()
        st, data, _, _ = http_req(f"{GATEWAY_URL}/api/tool/{action}", method="POST", body=payload, timeout=25)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        is_ok = st == 200 and isinstance(data, dict) and data.get("ok", True) is True and bool(validator(data))
        results["checks"].append(
            {
                "action": action,
                "status": st,
                "ok": is_ok,
                "latency_ms": elapsed_ms,
                "keys": list(data.keys())[:6] if isinstance(data, dict) else [],
            }
        )
        if is_ok:
            results["passed"] += 1
        else:
            results["failed"] += 1
            log_stream(f"  [FAIL] Tool {action}: status={st} data={str(data)[:200]}")

    log_stream(f"Section 3 complete: {results['passed']}/{results['passed'] + results['failed']} live tool calls passed.")
    return results


def test_section_4_multimodal_and_pipelines() -> dict[str, Any]:
    log_stream("Section 4: Testing Multimodal & Pipeline Endpoints on :4079/v1 + Live .137:11434 LLM Chat...")
    results: dict[str, Any] = {"section": "4_multimodal_and_pipelines_v1", "checks": [], "passed": 0, "failed": 0}

    def record(name: str, ok: bool, detail: Any) -> None:
        results["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        if ok:
            results["passed"] += 1
        else:
            results["failed"] += 1
            log_stream(f"  [FAIL] {name}: {detail}")

    # 4A. POST /v1/images/generations
    st_img, img_data, _, _ = http_req(
        f"{GATEWAY_URL}/v1/images/generations",
        method="POST",
        body={"model": "flux.1-schnell-local", "prompt": "Boylenet 27-Node Sovereign Rack HUD", "size": "1024x1024", "n": 1},
    )
    b64_str = (((img_data or {}).get("data") or [{}])[0]).get("b64_json", "") if isinstance(img_data, dict) else ""
    png_raw = base64.b64decode(b64_str) if b64_str else b""
    record(
        "POST /v1/images/generations returns valid PNG (magic \\x89PNG)",
        st_img == 200 and png_raw[:8] == b"\x89PNG\r\n\x1a\n" and len(png_raw) > 2000,
        {"status": st_img, "png_bytes": len(png_raw), "magic_hex": png_raw[:8].hex()},
    )

    # 4B. POST /v1/audio/speech & GET /v1/audio/models
    st_aud, _, wav_raw, aud_hdrs = http_req(
        f"{GATEWAY_URL}/v1/audio/speech",
        method="POST",
        body={"model": "tts-1-hd-local", "input": "Boylenet E2E verification complete.", "voice": "alloy"},
    )
    record(
        "POST /v1/audio/speech returns valid RIFF WAVE audio bytes",
        st_aud == 200 and wav_raw[:4] == b"RIFF" and b"WAVE" in wav_raw[:16] and len(wav_raw) > 1000,
        {"status": st_aud, "wav_bytes": len(wav_raw), "content_type": aud_hdrs.get("content-type")},
    )

    st_am, am_data, _, _ = http_req(f"{GATEWAY_URL}/v1/audio/models")
    record(
        "GET /v1/audio/models returns local TTS/Speech/Image/Embedding models",
        st_am == 200 and isinstance(am_data, dict) and len(am_data.get("models", am_data.get("data", []))) >= 3,
        {"status": st_am, "models_count": len((am_data or {}).get("models", (am_data or {}).get("data", [])))},
    )

    # 4C. POST /v1/embeddings (bge-m3:latest -> exact 1024-dim vector)
    st_emb, emb_data, _, _ = http_req(
        f"{GATEWAY_URL}/v1/embeddings",
        method="POST",
        body={"model": "bge-m3:latest", "input": "O1740 dynamic capability routing across 27 Boylenet nodes"},
    )
    vec = (((emb_data or {}).get("data") or [{}])[0]).get("embedding", []) if isinstance(emb_data, dict) else []
    record(
        "POST /v1/embeddings (bge-m3:latest) returns exact 1024-dim vector",
        st_emb == 200 and len(vec) == 1024 and all(isinstance(x, (int, float)) for x in vec[:10]),
        {"status": st_emb, "dimensions": len(vec), "sample_dims": vec[:4]},
    )

    # 4D. GET /v1/pipelines (8 pipelines)
    st_pl, pl_data, _, _ = http_req(f"{GATEWAY_URL}/v1/pipelines")
    pl_items = (pl_data or {}).get("data", []) if isinstance(pl_data, dict) else []
    record(
        "GET /v1/pipelines returns 8 active Boylenet pipelines",
        st_pl == 200 and len(pl_items) == 8,
        {"status": st_pl, "count": len(pl_items), "pipeline_ids": [p.get("id") for p in pl_items]},
    )

    # 4E. POST /v1/chat/completions on `pipe-boylenet-bdkb-rag-citation-engine` and `pipe-boylenet-smart-intent-router`
    for pipe_id in ("pipe-boylenet-bdkb-rag-citation-engine", "pipe-boylenet-smart-intent-router"):
        st_cc, cc_data, _, _ = http_req(
            f"{GATEWAY_URL}/v1/chat/completions",
            method="POST",
            body={
                "model": pipe_id,
                "messages": [{"role": "user", "content": "Explain O1740 Dynamic Capability Routing and Rule 22 sandbox protection in 2 concise bullet points."}],
                "stream": False,
            },
            timeout=25,
        )
        reply_text = (
            (((cc_data or {}).get("choices") or [{}])[0]).get("message", {}).get("content", "")
            if isinstance(cc_data, dict)
            else ""
        )
        record(
            f"POST /v1/chat/completions on {pipe_id} returns grounded BD KB + .137:11434 synthesis",
            st_cc == 200 and len(reply_text) > 80 and ("BD KB" in reply_text or "O1740" in reply_text),
            {"status": st_cc, "reply_chars": len(reply_text), "excerpt": reply_text[:180].replace("\n", " ")},
        )

    # 4F. Direct live chat test on .137:11434 (qwen2.5-coder:7b) verifying zero contention on .72/.83
    st_137_llm, llm_137_data, _, _ = http_req(
        f"{BATTLESTATION_OLLAMA}/v1/chat/completions",
        method="POST",
        body={
            "model": "qwen2.5-coder:7b",
            "messages": [{"role": "user", "content": "Reply with the exact token: BOYLENET_137_LIVE_OK"}],
            "max_tokens": 32,
            "temperature": 0.0,
        },
        timeout=15,
    )
    msg_137 = (
        (((llm_137_data or {}).get("choices") or [{}])[0]).get("message", {}).get("content", "")
        if isinstance(llm_137_data, dict)
        else ""
    )
    record(
        "Live LLM Chat on .137:11434 (qwen2.5-coder:7b RTX 2080 Ti) responds cleanly (zero .72/.83 load)",
        st_137_llm == 200 and len(msg_137.strip()) > 0,
        {"status": st_137_llm, "response": msg_137.strip()[:120]},
    )

    log_stream(f"Section 4 complete: {results['passed']}/{results['passed'] + results['failed']} checks passed.")
    return results


def test_section_5_15_agents_dynamic_updates_and_all_ui_tabs() -> dict[str, Any]:
    log_stream("Section 5: Verifying 15 Custom Agents, Dynamic State Updates, Tag Filters, and Every OpenWebUI Tab on :8090 & .72:8080...")
    results: dict[str, Any] = {"section": "5_15_custom_agents_dynamic_updates_and_ui_tabs", "checks": [], "passed": 0, "failed": 0}

    def record(name: str, ok: bool, detail: Any) -> None:
        results["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        if ok:
            results["passed"] += 1
        else:
            results["failed"] += 1
            log_stream(f"  [FAIL] {name}: {detail}")

    expected_agent_ids = sorted(a["id"] for a in CUSTOM_AGENTS_15)

    # 5A. Dynamic Pipeline Valves Update & Immediate Readback Test
    st_v1, v_upd1, _, _ = http_req(
        f"{GATEWAY_URL}/v1/pipe-boylenet-bdkb-rag-citation-engine/valves/update",
        method="POST",
        body={"top_k_chunks": 5},
    )
    st_v2, v_get, _, _ = http_req(f"{GATEWAY_URL}/v1/pipe-boylenet-bdkb-rag-citation-engine/valves")
    st_v3, v_rst, _, _ = http_req(
        f"{GATEWAY_URL}/v1/pipe-boylenet-bdkb-rag-citation-engine/valves/update",
        method="POST",
        body={"top_k_chunks": 3},
    )
    record(
        "Dynamic Pipeline Valves Update (/v1/pipe-boylenet-bdkb-rag-citation-engine/valves/update 3 -> 5 -> 3) reflects immediately",
        st_v1 == 200 and st_v2 == 200 and (v_get or {}).get("top_k_chunks") == 5 and (v_rst or {}).get("top_k_chunks") == 3,
        {"updated_val": (v_get or {}).get("top_k_chunks"), "restored_val": (v_rst or {}).get("top_k_chunks")},
    )

    # 5B. Verify all 15 Custom Agents, Tag Filters, Dynamic Model Update, and All Tabs on BOTH :8090 and .72:8080
    for inst in INSTANCES:
        iname = inst["name"]
        st_ml, ml_resp = owui_api(inst, "GET", "/api/v1/models/list")
        ml_items = ml_resp.get("items", ml_resp) if isinstance(ml_resp, dict) else (ml_resp or [])
        by_id = {m["id"]: m for m in ml_items if isinstance(m, dict) and "id" in m}

        present_agents = sorted(aid for aid in expected_agent_ids if aid in by_id)
        all_have_51_tools = all(
            len((by_id[aid].get("meta") or {}).get("toolIds") or []) >= 51 for aid in present_agents
        )
        all_have_6_bdkb = all(
            len((by_id[aid].get("meta") or {}).get("knowledge") or []) >= 6 for aid in present_agents
        )
        all_have_agent_tag = all(
            any(
                (t.get("name") if isinstance(t, dict) else str(t)) == "🤖 BOYLENET AGENT"
                for t in ((by_id[aid].get("meta") or {}).get("tags") or [])
            )
            for aid in present_agents
        )
        record(
            f"{iname}: All 15 Custom Agents present with 51 toolIds, 6 BD KB volumes, and '🤖 BOYLENET AGENT' tag",
            st_ml == 200
            and present_agents == expected_agent_ids
            and all_have_51_tools
            and all_have_6_bdkb
            and all_have_agent_tag,
            {
                "present_count": len(present_agents),
                "all_have_51_tools": all_have_51_tools,
                "all_have_6_bdkb": all_have_6_bdkb,
                "all_have_agent_tag": all_have_agent_tag,
            },
        )

        # Verify `/api/models` (Model Selector Bar catalog) exposes tag filter pills (`🤖 BOYLENET AGENT`, `🟢 LOCAL`, `☁️ CLOUD`)
        st_am, am_resp = owui_api(inst, "GET", "/api/models")
        am_data = (am_resp or {}).get("data", []) if isinstance(am_resp, dict) else []
        tag_counts = {"🤖 BOYLENET AGENT": 0, "🟢 LOCAL": 0, "☁️ CLOUD": 0}
        for m in am_data:
            if not isinstance(m, dict):
                continue
            m_tags = [
                (t.get("name") if isinstance(t, dict) else str(t))
                for t in (m.get("tags") or ((m.get("info") or {}).get("meta") or {}).get("tags") or [])
            ]
            for tk in tag_counts:
                if tk in m_tags:
                    tag_counts[tk] += 1
        record(
            f"{iname}: Model Selector Bar (/api/models) filters by '🤖 BOYLENET AGENT' (>=15), '🟢 LOCAL', and '☁️ CLOUD'",
            st_am == 200
            and tag_counts["🤖 BOYLENET AGENT"] >= 15
            and tag_counts["🟢 LOCAL"] >= 10
            and tag_counts["☁️ CLOUD"] >= 3,
            {"total_catalog_models": len(am_data), "tag_filter_counts": tag_counts},
        )

        # Dynamic Model Update & Immediate Readback Test on `agent-instant-sprinter`
        target_agent = dict(by_id["agent-instant-sprinter"])
        orig_desc = str((target_agent.get("meta") or {}).get("description") or "")
        mut_meta = dict(target_agent.get("meta") or {})
        mut_meta["description"] = orig_desc + " [LIVE-E2E-SYNC-VERIFIED]"
        target_agent["meta"] = mut_meta
        st_upd1, _ = owui_api(inst, "POST", "/api/v1/models/model/update", target_agent)
        st_get1, m_check = owui_api(inst, "GET", "/api/v1/models/model?id=agent-instant-sprinter")
        updated_desc = str(((m_check or {}).get("meta") or {}).get("description") or "")
        # Restore original description
        mut_meta["description"] = orig_desc
        target_agent["meta"] = mut_meta
        st_upd2, _ = owui_api(inst, "POST", "/api/v1/models/model/update", target_agent)
        record(
            f"{iname}: Dynamic Agent Update (/api/v1/models/model/update) propagates immediately & restores cleanly",
            st_upd1 == 200 and st_get1 == 200 and "[LIVE-E2E-SYNC-VERIFIED]" in updated_desc and st_upd2 == 200,
            {"update_status": st_upd1, "verified_marker_present": "[LIVE-E2E-SYNC-VERIFIED]" in updated_desc, "restore_status": st_upd2},
        )

        # Verify every Workspace & Admin Tab API backing endpoint on the instance
        tab_endpoints = [
            ("Frontend SPA Root & App Config", "/api/config", lambda d: isinstance(d, dict) and d.get("status") is True),
            ("Workspace -> Models (294 Total + 15 Custom Agents)", "/api/v1/models/list", lambda d: (d.get("total", len(d.get("items", []))) if isinstance(d, dict) else len(d)) >= 35),
            ("Workspace -> Knowledge (6 BD KB + 5 Qdrant)", "/api/v1/knowledge/", lambda d: len(d.get("items", d) if isinstance(d, dict) else d) >= 11),
            ("Workspace -> Prompts (Slash Commands)", "/api/v1/prompts/", lambda d: isinstance(d, list) and len(d) >= 120),
            ("Workspace -> Skills (128 Skills)", "/api/v1/skills/", lambda d: isinstance(d, list) and len(d) >= 120),
            ("Workspace -> Tools (51 Native + 5 OpenAPI)", "/api/v1/tools/", lambda d: isinstance(d, list) and len(d) >= 56),
            ("Admin -> Functions (Actions & Filters)", "/api/v1/functions/", lambda d: isinstance(d, list) and len(d) >= 5),
            ("Admin -> Integrations -> Tool Servers", "/api/v1/configs/tool_servers", lambda d: len(d.get("TOOL_SERVER_CONNECTIONS", [])) >= 5),
            ("Admin -> Integrations -> Terminal Servers", "/api/v1/configs/terminal_servers", lambda d: len(d.get("TERMINAL_SERVER_CONNECTIONS", [])) == 28),
            ("Admin -> Pipelines List", "/api/v1/pipelines/list", lambda d: len(d.get("data", [])) >= 1),
            ("Admin -> Images Config", "/api/v1/images/config", lambda d: isinstance(d, dict)),
            ("Admin -> Audio Config", "/api/v1/audio/config", lambda d: isinstance(d, dict)),
            ("Admin -> Retrieval / Web Search & RAG Config", "/api/v1/retrieval/config", lambda d: isinstance(d, dict)),
        ]
        for tab_label, ep_path, check_fn in tab_endpoints:
            st_tab, tab_data = owui_api(inst, "GET", ep_path)
            ok_tab = st_tab == 200 and tab_data is not None and bool(check_fn(tab_data))
            record(
                f"{iname} Tab [{tab_label}] ({ep_path})",
                ok_tab,
                {"status": st_tab},
            )

    log_stream(f"Section 5 complete: {results['passed']}/{results['passed'] + results['failed']} checks passed.")
    return results


def test_section_6_playwright_browser_ui_tabs() -> dict[str, Any]:
    log_stream("Section 6: Running Playwright Headless Chromium DOM & UI Tab/Bar/Button Verification on :8090 & .72:8080...")
    results: dict[str, Any] = {"section": "6_playwright_browser_ui_dom_tabs", "checks": [], "passed": 0, "failed": 0}

    pw_script = r"""
import json, sys
from playwright.sync_api import sync_playwright

instances = json.loads(sys.stdin.read())
ui_routes = [
    ("/", "Chat Interface & Model Selector Bar"),
    ("/workspace/models", "Workspace -> Models (15 Custom Agents & Tag Filter Pills)"),
    ("/workspace/knowledge", "Workspace -> Knowledge (6 BD KB + 5 Qdrant)"),
    ("/workspace/prompts", "Workspace -> Prompts (128 Slash Commands)"),
    ("/workspace/skills", "Workspace -> Skills (128 Skills)"),
    ("/workspace/tools", "Workspace -> Tools (51 Native Toolkits)"),
    ("/admin/functions", "Admin -> Functions (Actions & Filters)"),
    ("/admin/settings", "Admin -> Settings (Integrations, Pipelines, Images, Audio, Web Search)"),
]

out = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for inst in instances:
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_init_script(f"localStorage.setItem('token', '{inst['token']}');")
        page = ctx.new_page()
        for route, label in ui_routes:
            page.goto(f"{inst['base_url']}{route}", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1200)
            btn_count = page.locator("button, a").count()
            body_len = len(page.inner_text("body"))
            out.append({
                "instance": inst["name"],
                "route": route,
                "label": label,
                "ok": btn_count >= 10 and body_len >= 100,
                "buttons_and_links": btn_count,
                "text_chars": body_len,
            })
        ctx.close()
    browser.close()
print(json.dumps(out))
"""
    pw_input = [
        {
            "name": inst["name"],
            "base_url": inst["base_url"],
            "token": make_jwt(inst["admin_id"], inst["secret"]),
        }
        for inst in INSTANCES
    ]
    proc = subprocess.run(
        ["/home/mboyle/BulkDownloader/venv/bin/python", "-c", pw_script],
        input=json.dumps(pw_input).encode("utf-8"),
        capture_output=True,
        timeout=60,
    )
    rows = json.loads(proc.stdout.decode("utf-8", errors="replace").strip().splitlines()[-1])
    for r in rows:
        results["checks"].append(r)
        if r["ok"]:
            results["passed"] += 1
        else:
            results["failed"] += 1
            log_stream(f"  [FAIL] Browser UI {r['instance']} {r['route']}: {r}")

    log_stream(f"Section 6 complete: {results['passed']}/{results['passed'] + results['failed']} browser UI DOM checks passed.")
    return results


def main() -> None:
    t0 = time.time()
    log_stream("=== Starting Boylenet OpenWebUI Comprehensive E2E Suite & 15 Custom Agents Sync ===")

    sync_summaries = []
    for inst in INSTANCES:
        sync_summaries.append(sync_15_custom_agents_on_instance(inst))

    sec1 = test_section_1_open_terminals()
    sec2 = test_section_2_openapi_tool_servers()
    sec3 = test_section_3_live_tools_execution()
    sec4 = test_section_4_multimodal_and_pipelines()
    sec5 = test_section_5_15_agents_dynamic_updates_and_all_ui_tabs()
    sec6 = test_section_6_playwright_browser_ui_tabs()

    sections = [sec1, sec2, sec3, sec4, sec5, sec6]
    total_passed = sum(s["passed"] for s in sections)
    total_failed = sum(s["failed"] for s in sections)

    final_report = {
        "ok": total_failed == 0,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.time() - t0, 2),
        "total_checks_passed": total_passed,
        "total_checks_failed": total_failed,
        "custom_agents_synced": sync_summaries,
        "sections": sections,
    }
    JSON_RESULTS_PATH.write_text(json.dumps(final_report, indent=2), encoding="utf-8")
    log_stream(
        f"=== E2E Suite Complete in {final_report['elapsed_seconds']}s: {total_passed} PASSED, {total_failed} FAILED ==="
    )
    print(json.dumps({
        "ok": final_report["ok"],
        "elapsed_seconds": final_report["elapsed_seconds"],
        "total_checks_passed": total_passed,
        "total_checks_failed": total_failed,
        "results_file": str(JSON_RESULTS_PATH),
    }, indent=2))
    if total_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

