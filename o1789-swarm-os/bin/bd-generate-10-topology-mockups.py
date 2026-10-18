#!/usr/bin/env python3
"""
bd-generate-10-topology-mockups.py
Generates 10 radically distinct, full-bleed 1920x1080 visual topology mockups for
Boylenet Architecture Topology & Live Swarm Visualizer (:4088) and captures all 10
screenshots via Browser Oracle CDP (10.0.10.137:9222 BattleStation / 10.0.70.181:9222 Bittorrent).
"""
from __future__ import annotations

import base64
import json
import math
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List
from websocket import create_connection

GALLERY_HTML_PATH = Path("/var/tmp/topology-mockups-gallery.html")
SCREENSHOT_DIR = Path(
    "/home/mboyle/.gemini/antigravity-cli/brain/d61a0f86-9a87-4a9f-8b2c-ea5791e23bc8/screenshots"
)
ORACLE_HOSTS = ["10.0.10.137", "10.0.70.181"]


def build_style_01_unifi() -> str:
    """Style 1: Ubiquiti UniFi OS Dark Topology Map."""
    # Helper for UniFi node boxes
    def unifi_node(x: int, y: int, title: str, sub: str, ip: str, badge: str, color: str = "#006fff", icon_type: str = "vm", w: int = 176, h: int = 64) -> str:
        icon_svg = ""
        if icon_type == "gateway":
            icon_svg = '<rect x="10" y="16" width="32" height="32" rx="8" fill="#1e293b" stroke="#94a3b8" stroke-width="1.5"/><circle cx="26" cy="32" r="7" fill="none" stroke="#38bdf8" stroke-width="2"/><circle cx="26" cy="32" r="2.5" fill="#38bdf8"/>'
        elif icon_type == "switch":
            icon_svg = '<rect x="8" y="18" width="36" height="28" rx="6" fill="#e2e8f0" stroke="#38bdf8" stroke-width="1.5"/><rect x="12" y="23" width="28" height="7" rx="1" fill="#0f172a"/><rect x="12" y="33" width="28" height="7" rx="1" fill="#0f172a"/><circle cx="15" cy="26.5" r="1.5" fill="#00e5ff"/><circle cx="20" cy="26.5" r="1.5" fill="#00e5ff"/><circle cx="25" cy="26.5" r="1.5" fill="#10b981"/><circle cx="30" cy="26.5" r="1.5" fill="#10b981"/><circle cx="35" cy="26.5" r="1.5" fill="#00e5ff"/>'
        elif icon_type == "esxi":
            icon_svg = '<rect x="9" y="14" width="34" height="36" rx="6" fill="#1e293b" stroke="#60a5fa" stroke-width="1.5"/><line x1="13" y1="23" x2="39" y2="23" stroke="#60a5fa" stroke-width="1.5"/><line x1="13" y1="32" x2="39" y2="32" stroke="#60a5fa" stroke-width="1.5"/><line x1="13" y1="41" x2="39" y2="41" stroke="#60a5fa" stroke-width="1.5"/><circle cx="36" cy="19" r="2" fill="#10b981"/>'
        elif icon_type == "gpu":
            icon_svg = '<rect x="9" y="14" width="34" height="36" rx="8" fill="#042f2e" stroke="#00e5ff" stroke-width="1.8"/><circle cx="26" cy="32" r="10" fill="none" stroke="#00e5ff" stroke-width="1.6" stroke-dasharray="3,2"/><circle cx="26" cy="32" r="4" fill="#00e5ff"/>'
        elif icon_type == "cloud":
            icon_svg = '<rect x="9" y="14" width="34" height="36" rx="8" fill="#2e1065" stroke="#c084fc" stroke-width="1.6"/><path d="M18 36 h16 a5 5 0 0 0 0 -10 a7 7 0 0 0 -13 -2 a4 4 0 0 0 -3 12 z" fill="#c084fc" opacity="0.85"/>'
        else:
            icon_svg = f'<rect x="10" y="16" width="32" height="32" rx="7" fill="#172033" stroke="{color}" stroke-width="1.5"/><circle cx="26" cy="32" r="6" fill="{color}" opacity="0.25"/><circle cx="26" cy="32" r="3" fill="{color}"/>'

        return f"""
        <g transform="translate({x},{y})">
          <rect width="{w}" height="{h}" rx="10" fill="#131824" stroke="#263248" stroke-width="1.4"/>
          <rect x="0" y="0" width="4" height="{h}" rx="2" fill="{color}"/>
          {icon_svg}
          <circle cx="40" cy="16" r="4" fill="#10b981" stroke="#0b0e14" stroke-width="1.5"/>
          <text x="50" y="22" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11.5" font-weight="700">{title}</text>
          <text x="50" y="37" fill="#94a3b8" font-family="Inter,sans-serif" font-size="10">{sub}</text>
          <rect x="50" y="43" width="{min(w-58, 118)}" height="15" rx="4" fill="#0b0e14" stroke="{color}" stroke-width="0.7" opacity="0.9"/>
          <text x="55" y="53.5" fill="{color}" font-family="JetBrains Mono,monospace" font-size="9" font-weight="600">{ip} • {badge}</text>
        </g>
        """

    def wire_pill(x: int, y: int, label: str, color: str = "#00e5ff", w: int = 114) -> str:
        return f"""
        <g transform="translate({x - w//2},{y - 10})">
          <rect width="{w}" height="19" rx="9.5" fill="#0b0e14" stroke="{color}" stroke-width="1.1"/>
          <circle cx="10" cy="9.5" r="3" fill="{color}"/>
          <text x="18" y="13" fill="#e2e8f0" font-family="JetBrains Mono,monospace" font-size="9" font-weight="600">{label}</text>
        </g>
        """

    nodes_svg = []
    # Tier 0: Gateway + Core Switch (Left)
    nodes_svg.append(unifi_node(78, 220, "UDM-Pro Gateway", "UniFi OS 4.1 • WAN/DNS", "10.0.70.1", "32 DNS OK", "#006fff", "gateway", 185, 68))
    nodes_svg.append(unifi_node(78, 465, "USW-Pro-Agg 280G", "28x 10G SFP+ • 4x 25G SFP28", "10.0.10.2", "280 Gbps", "#00e5ff", "switch", 185, 68))
    nodes_svg.append(unifi_node(78, 725, "vCenter vc04 + iLO", "vSphere 8.0 • 11 Disk Groups", "10.0.70.70", "328.4 TiB", "#10b981", "esxi", 185, 68))

    # Tier 1: 4x ESXi Hosts + 4x Tesla T4 GPU Nodes (Col 2, x=365)
    esxi_specs = [
        (105, "esxi01.boylenet", "HPE DL360 • 21TB Flash vSAN", "10.0.20.41", "iLO .10 OK"),
        (190, "esxi02.boylenet", "HPE DL380 • 96TB Exos T0+T1", "10.0.20.42", "iLO .20 OK"),
        (275, "esxi03.boylenet", "HPE DL380 • 96TB Exos T0+T1", "10.0.20.43", "iLO .30 OK"),
        (360, "esxi04.boylenet", "HPE DL380 • 96TB Exos T0+T1", "10.0.20.44", "iLO .40 OK"),
    ]
    for y, t, s, ip, b in esxi_specs:
        nodes_svg.append(unifi_node(365, y, t, s, ip, b, "#3b82f6", "esxi", 210, 66))

    gpu_specs = [
        (485, "ai-srv01 • Vault A", "Tesla T4 16G • 52c • 320G RAM", "10.0.75.11", "77.6 tok/s"),
        (575, "aidev • Vault B", "Tesla T4 16G • 52c • 386G RAM", "10.0.75.12", "RPC :50052"),
        (665, "ai-infer01 • Vector", "Tesla T4 16G • Qdrant :6333", "10.0.70.125", "Qwen-32B"),
        (755, "ai-ollama01 • Gate", "Tesla T4 16G • LiteLLM :4000", "10.0.70.228", "Langfuse"),
        (845, "Synology + Cold NAS", "NFS Archive & Snapshot Vault", "10.0.70.199", "NFSv4 OK"),
    ]
    for y, t, s, ip, b in gpu_specs:
        col = "#00e5ff" if "10.0.75" in ip or "ai-" in t else "#10b981"
        nodes_svg.append(unifi_node(365, y, t, s, ip, b, col, "gpu", 210, 66))

    # Tier 2: Command Nexus, Oracles, Primary Builders (Col 3, x=710)
    tier2_specs = [
        (105, "Controller Nexus (bd)", "32+ Web UIs • Traefik :80 • PM", "10.0.70.164", "10 Agents", "#f59e0b"),
        (195, "test3big (wrk-test04)", "64-vCPU • 128G /dev/shm Pytest", "10.0.70.82", "Ramdisk CI", "#10b981"),
        (285, "BattleStation Oracle", "Ryzen 9 • RTX 2080Ti • CDP :9222", "10.0.10.137", "Chrome 155", "#38bdf8"),
        (375, "Bittorrent Oracle #2", "Secondary Windows CDP Bridge", "10.0.70.181", "CDP :9222", "#38bdf8"),
        (485, "DeepSeek-V3-0324-671B", "5TB Vault A • RoCE Tensor Split", "VLAN 75", "77.6 tok/s", "#00e5ff"),
        (575, "Kimi-K2.5-1T & MiMo", "5TB Vault B • ik_llama.cpp RPC", "VLAN 75", "Dual-Node", "#00e5ff"),
        (665, "Swarm Builder Pod", "bd1 (.51) • bd2 (.210) • bd3 • bd4", "10.0.70.51+", "4x Active", "#60a5fa"),
        (755, "Swarm Verifier Pod A", "test1 (.81) • test2 (.84) • test4..5", "10.0.70.81+", "4x Active", "#60a5fa"),
        (845, "Swarm Verifier Pod B", "test6 (.197) • test7 (.249) • fresh149", "10.0.70.149+", "3x Active", "#60a5fa"),
    ]
    for y, t, s, ip, b, c in tier2_specs:
        nodes_svg.append(unifi_node(710, y, t, s, ip, b, c, "vm", 220, 66))

    # Tier 3: Individual Fleet VMs & Active Agent Seats (Col 4, x=1065)
    tier3_specs = [
        (105, "bd-pm-B (PM Integrator)", "Claude Opus 5.5 • Train Master", "Pool B", "0% 5h Used", "#a855f7"),
        (195, "AGY-Council Orchestrator", "10 Parallel Subagents • E2E", "AGY Pool", "Active Run", "#00e5ff"),
        (285, "claude-A & claude-B", "Heavy-Lifter Lenses & Fixers", "Pools A/B", "$500 Credit", "#a855f7"),
        (375, "claude-C & claude-D", "Parallel Swarm Workers", "Pools C/D", "$500 Credit", "#a855f7"),
        (485, "codex (GPT-6.1-Sol)", "Single-Turn Verifiers & Cuts", "OpenAI Pool", "0% Window", "#10b981"),
        (575, "kimi-for-coding + hermes", "High-Context Synthesis & Ops", "Kimi/Local", "State OK", "#f59e0b"),
        (665, "Elastic Hot Spares 1..2", "spare1 (.120) • spare2 (.183)", "VLAN 70", "Powered On", "#38bdf8"),
        (755, "Elastic Cold Spares 3..6", "spare3..spare6 (vSphere DRS)", "Rule 61", "Standby 0W", "#64748b"),
        (845, "Elastic Cold Spares 7..10", "spare7..spare10 (vSphere DRS)", "Rule 61", "Standby 0W", "#64748b"),
    ]
    for y, t, s, ip, b, c in tier3_specs:
        nodes_svg.append(unifi_node(1065, y, t, s, ip, b, c, "vm", 220, 66))

    # Tier 4: External Cloud Burst & Dashy/Traefik Ingress (Col 5, x=1420)
    tier4_specs = [
        (105, "Anthropic Cloud Pool A", "$250 Free Credit • Exp Nov 5", "api.anthropic", "$250.00 OK", "#c084fc"),
        (195, "Anthropic Cloud Pool B", "$250 Free Credit • PM Opus 5.5", "api.anthropic", "$250.00 OK", "#c084fc"),
        (285, "Anthropic Cloud Pool C", "$250 Free Credit • Sonnet 5.5", "api.anthropic", "$250.00 OK", "#c084fc"),
        (375, "Anthropic Cloud Pool D", "$250 Free Credit • Overage OFF", "api.anthropic", "$250.00 OK", "#c084fc"),
        (485, "OpenAI Codex Cloud", "gpt-6-astra / gpt-6.1-sol", "api.openai", "Tier-1 OK", "#10b981"),
        (575, "Kimi Cloud & Satellite", "kimi-k2.5-coding • 256k Ctx", "api.kimi", "Quota OK", "#f59e0b"),
        (665, "Traefik Ingress (:80)", "32 Short + FQDN DNS Routes", "10.0.70.164", "32/32 200", "#006fff"),
        (755, "Dashy Portal (:4080)", "15 Studios (:4086..:4099)", "dashy.boylenet", "100% GREEN", "#10b981"),
        (845, "Infra Sentinel (:4099)", "83-Service Autonomous Healer", "sentinel", "83/83 UP", "#00e5ff"),
    ]
    for y, t, s, ip, b, c in tier4_specs:
        nodes_svg.append(unifi_node(1420, y, t, s, ip, b, c, "cloud", 225, 66))

    # Orthogonal UniFi Wires
    wires = []
    # Gateway -> Switch -> vCenter
    wires.append('<path d="M 170 288 L 170 465" stroke="#00e5ff" stroke-width="3" fill="none"/>')
    wires.append('<path d="M 170 533 L 170 725" stroke="#10b981" stroke-width="2.5" fill="none"/>')
    # Switch -> ESXi & GPU Spine (x=315 trunk)
    wires.append('<path d="M 263 499 L 315 499" stroke="#00e5ff" stroke-width="3.5" fill="none"/>')
    wires.append('<path d="M 315 138 L 315 878" stroke="#006fff" stroke-width="2.5" fill="none"/>')
    for y in [138, 223, 308, 393]:
        wires.append(f'<path d="M 315 {y} L 365 {y}" stroke="#3b82f6" stroke-width="2" fill="none"/>')
    for y in [518, 608, 698, 788, 878]:
        col = "#00e5ff" if y in (518, 608) else "#10b981"
        w = "3" if y in (518, 608) else "2"
        wires.append(f'<path d="M 315 {y} L 365 {y}" stroke="{col}" stroke-width="{w}" fill="none"/>')

    # Col 2 -> Col 3 trunk (x=640)
    wires.append('<path d="M 640 138 L 640 878" stroke="#1e3a8a" stroke-width="2" fill="none"/>')
    for y in [138, 223, 308, 393, 518, 608, 698, 788, 878]:
        c = "#00e5ff" if y in (518, 608) else "#006fff"
        wires.append(f'<path d="M 575 {y} L 640 {y}" stroke="{c}" stroke-width="1.8" fill="none"/>')
    for y in [138, 228, 318, 408, 518, 608, 698, 788, 878]:
        c = "#00e5ff" if y in (518, 608) else "#3b82f6"
        wires.append(f'<path d="M 640 {y} L 710 {y}" stroke="{c}" stroke-width="1.8" fill="none"/>')

    # Col 3 -> Col 4 trunk (x=995)
    wires.append('<path d="M 995 138 L 995 878" stroke="#312e81" stroke-width="2" fill="none"/>')
    for y in [138, 228, 318, 408, 518, 608, 698, 788, 878]:
        wires.append(f'<path d="M 930 {y} L 1065 {y}" stroke="#6366f1" stroke-width="1.8" fill="none"/>')

    # Col 4 -> Col 5 trunk
    for y in [138, 228, 318, 408, 518, 608, 698, 788, 878]:
        c = "#a855f7" if y <= 408 else "#00e5ff"
        wires.append(f'<path d="M 1285 {y} L 1420 {y}" stroke="{c}" stroke-width="1.8" stroke-dasharray="5,3" fill="none"/>')

    pills = [
        wire_pill(170, 375, "10G SFP+ Trunk", "#00e5ff", 112),
        wire_pill(170, 630, "10G vSAN + iLO", "#10b981", 112),
        wire_pill(315, 452, "25GbE SFP28 RoCE", "#00e5ff", 126),
        wire_pill(640, 563, "77.6 tok/s RPC", "#00e5ff", 112),
        wire_pill(995, 273, "O1740 Autobalance", "#a855f7", 124),
        wire_pill(1352, 273, "$1,000 Cloud WAN", "#c084fc", 122),
    ]

    return f"""
    <div style="width:1920px;height:1034px;background:#0b0e14;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      <!-- Left UniFi Navigation Rail -->
      <div style="position:absolute;left:0;top:0;bottom:0;width:54px;background:#111621;border-right:1px solid #1e2738;display:flex;flex-direction:column;align-items:center;padding-top:16px;gap:18px;z-index:5;">
        <div style="width:34px;height:34px;border-radius:8px;background:#006fff;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:900;font-size:15px;box-shadow:0 0 14px rgba(0,111,255,0.6);">U</div>
        <div style="width:34px;height:34px;border-radius:8px;background:rgba(0,111,255,0.18);border:1px solid #006fff;display:flex;align-items:center;justify-content:center;color:#38bdf8;font-size:16px;">🖧</div>
        <div style="width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#64748b;font-size:16px;">🖥️</div>
        <div style="width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#64748b;font-size:16px;">⚡</div>
        <div style="width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#64748b;font-size:16px;">🛡️</div>
        <div style="width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#64748b;font-size:16px;">📊</div>
      </div>

      <!-- Top UniFi Sub-Toolbar -->
      <div style="position:absolute;left:54px;right:0;top:0;height:48px;background:#111621;border-bottom:1px solid #1e2738;display:flex;align-items:center;justify-content:space-between;padding:0 24px;z-index:5;">
        <div style="display:flex;align-items:center;gap:12px;">
          <span style="color:#f8fafc;font-weight:700;font-size:14px;">UniFi OS • Boylenet Enterprise Fabric Map</span>
          <span style="background:#006fff22;color:#38bdf8;border:1px solid #006fff66;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600;">All Devices (27 VMs • 4 ESXi • 4x T4 GPUs • 280G Spine)</span>
          <span style="background:#00e5ff18;color:#00e5ff;border:1px solid #00e5ff55;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600;">✓ VLAN 75 25GbE RoCE (77.6 tok/s)</span>
          <span style="background:#10b98118;color:#34d399;border:1px solid #10b98155;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600;">✓ VLAN 60 vSAN (328.4 TiB • 75 Disks)</span>
          <span style="background:#a855f718;color:#c084fc;border:1px solid #a855f755;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600;">✓ $1,000 Cloud Credits (Pools A-D)</span>
        </div>
        <div style="display:flex;align-items:center;gap:14px;font-size:11px;color:#94a3b8;font-family:'JetBrains Mono',monospace;">
          <span>● 25G SFP28 Cyan</span>
          <span>● 10G SFP+ Blue</span>
          <span>● 10G vSAN Green</span>
          <span>● Cloud WAN Purple</span>
        </div>
      </div>

      <!-- Column Header Labels -->
      <div style="position:absolute;left:78px;top:62px;color:#64748b;font-size:10.5px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">TIER 0 • CORE ROUTING &amp; 280G SPINE</div>
      <div style="position:absolute;left:365px;top:62px;color:#64748b;font-size:10.5px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">TIER 1 • 4X ESXi HOSTS &amp; 4X TESLA T4 GPUS</div>
      <div style="position:absolute;left:710px;top:62px;color:#64748b;font-size:10.5px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">TIER 2 • CONTROLLER, ORACLES &amp; 23 WORKER VMS</div>
      <div style="position:absolute;left:1065px;top:62px;color:#64748b;font-size:10.5px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">TIER 3 • LIVE SWARM AGENTS &amp; DRS SPARES</div>
      <div style="position:absolute;left:1420px;top:62px;color:#64748b;font-size:10.5px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">TIER 4 • $1,000 CLOUD BURST &amp; INGRESS</div>

      <!-- Right UniFi Device Inspector Card -->
      <div style="position:absolute;right:20px;top:98px;width:230px;bottom:56px;background:#111621;border:1px solid #263248;border-radius:12px;padding:16px;display:flex;flex-direction:column;justify-content:space-between;z-index:4;">
        <div>
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
            <span style="color:#38bdf8;font-size:10px;font-weight:700;letter-spacing:0.8px;">SELECTED FABRIC LINK</span>
            <span style="background:#10b98122;color:#10b981;font-size:9.5px;padding:2px 7px;border-radius:4px;font-weight:700;">OPTIMAL</span>
          </div>
          <div style="color:#f8fafc;font-size:14px;font-weight:800;margin-bottom:4px;">USW-Pro-Agg 280G</div>
          <div style="color:#94a3b8;font-size:11px;margin-bottom:14px;">28x 10G SFP+ • 4x 25G SFP28</div>
          <div style="background:#0b0e14;border:1px solid #1e2738;border-radius:8px;padding:10px;margin-bottom:12px;font-family:'JetBrains Mono',monospace;font-size:10px;color:#cbd5e1;line-height:1.7;">
            <div>Uplink: <span style="color:#38bdf8;">UDM-Pro (.1)</span></div>
            <div>VLAN 75: <span style="color:#00e5ff;">25GbE RoCE RDMA</span></div>
            <div>Tensor: <span style="color:#10b981;">77.62 tok/s</span></div>
            <div>vSAN 60: <span style="color:#34d399;">135.7 / 328.4 TiB</span></div>
            <div>Compute: <span style="color:#f8fafc;">656 vCPU / 1.73 TiB</span></div>
          </div>
          <div style="color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;margin-bottom:8px;">SFP28 25GbE Tensor Ports</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-family:'JetBrains Mono',monospace;font-size:9.5px;">
            <div style="background:#042f2e;border:1px solid #00e5ff;padding:6px;border-radius:6px;color:#00e5ff;">P29: .72 T4<br><b>25G FDX</b></div>
            <div style="background:#042f2e;border:1px solid #00e5ff;padding:6px;border-radius:6px;color:#00e5ff;">P30: .83 T4<br><b>25G FDX</b></div>
            <div style="background:#0f172a;border:1px solid #38bdf8;padding:6px;border-radius:6px;color:#38bdf8;">P31: .125 T4<br><b>10G/25G</b></div>
            <div style="background:#0f172a;border:1px solid #38bdf8;padding:6px;border-radius:6px;color:#38bdf8;">P32: .228 T4<br><b>10G/25G</b></div>
          </div>
        </div>
        <div style="background:#172033;border:1px solid #3b82f655;border-radius:8px;padding:10px;font-size:10px;color:#94a3b8;">
          <b style="color:#f8fafc;">O1740 Dynamic Routing</b><br>
          30/30 Heavy-Lifter cap active • $1,000 Cloud Credits ($0 overage)
        </div>
      </div>

      <!-- Main SVG Topology Canvas -->
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <defs>
          <pattern id="unifi-dots" width="22" height="22" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="1" fill="#1e293b"/>
          </pattern>
        </defs>
        <rect x="54" y="48" width="1866" height="986" fill="url(#unifi-dots)"/>
        {''.join(wires)}
        {''.join(pills)}
        {''.join(nodes_svg)}
      </svg>

      <!-- Bottom Status Footer -->
      <div style="position:absolute;left:54px;right:0;bottom:0;height:36px;background:#111621;border-top:1px solid #1e2738;display:flex;align-items:center;justify-content:space-between;padding:0 24px;font-size:11px;color:#94a3b8;font-family:'JetBrains Mono',monospace;">
        <span>STYLE #1: UBIQUITI UNIFI OS DARK TOPOLOGY MAP • 100% REAL-TIME CLUSTER INVENTORY</span>
        <span style="color:#38bdf8;">UDM-Pro (.1) ➔ USW-Pro-Agg (280G) ➔ 4x ESXi / 4x T4 GPUs ➔ 27 VMs &amp; $1,000 Cloud Pools</span>
      </div>
    </div>
    """


def build_style_02_reactflow() -> str:
    """Style 2: n8n / ReactFlow Interactive Node-Wire Canvas."""
    def rf_node(x: int, y: int, title: str, sub: str, metric: str, accent: str, avatar: str = "", avatar_bg: str = "#7c3aed", w: int = 250, h: int = 86) -> str:
        av_html = ""
        if avatar:
            av_html = f"""
            <g transform="translate({w - 118}, -13)">
              <rect width="112" height="22" rx="11" fill="{avatar_bg}" stroke="#0f172a" stroke-width="2"/>
              <circle cx="11" cy="11" r="4" fill="#fff"/>
              <text x="20" y="14.5" fill="#ffffff" font-family="Inter,sans-serif" font-size="9.5" font-weight="800">{avatar}</text>
            </g>
            """
        return f"""
        <g transform="translate({x},{y})">
          <!-- Drop Shadow -->
          <rect x="3" y="5" width="{w}" height="{h}" rx="12" fill="#000000" opacity="0.45"/>
          <rect width="{w}" height="{h}" rx="12" fill="#181b24" stroke="{accent}" stroke-width="1.6"/>
          <path d="M 0 12 Q 0 0 12 0 L {w-12} 0 Q {w} 0 {w} 12 L {w} 24 L 0 24 Z" fill="{accent}" opacity="0.22"/>
          <rect x="0" y="12" width="5" height="{h-24}" rx="2.5" fill="{accent}"/>
          <!-- Input / Output ReactFlow Handle Ports -->
          <circle cx="0" cy="{h//2}" r="6" fill="#0f172a" stroke="{accent}" stroke-width="2.5"/>
          <circle cx="{w}" cy="{h//2}" r="6" fill="{accent}" stroke="#ffffff" stroke-width="2"/>
          <text x="16" y="17" fill="{accent}" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="700">{sub}</text>
          <text x="16" y="44" fill="#f8fafc" font-family="Inter,sans-serif" font-size="13" font-weight="800">{title}</text>
          <rect x="16" y="55" width="{w-32}" height="21" rx="6" fill="#0f1117" stroke="#262b38" stroke-width="1"/>
          <text x="24" y="69" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="10">{metric}</text>
          {av_html}
        </g>
        """

    def bezier_wire(x1: int, y1: int, x2: int, y2: int, color: str, label: str = "") -> str:
        dx = abs(x2 - x1) * 0.52
        path = f"M {x1} {y1} C {x1+dx} {y1}, {x2-dx} {y2}, {x2} {y2}"
        mx = (x1 + x2) // 2
        my = (y1 + y2) // 2
        lbl = ""
        if label:
            lbl = f"""
            <rect x="{mx-48}" y="{my-10}" width="96" height="18" rx="9" fill="#0f1117" stroke="{color}" stroke-width="1.2"/>
            <text x="{mx}" y="{my+2.5}" text-anchor="middle" fill="{color}" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">{label}</text>
            """
        return f"""
        <path d="{path}" stroke="{color}" stroke-width="5" opacity="0.16" fill="none"/>
        <path d="{path}" stroke="{color}" stroke-width="2.2" fill="none" stroke-dasharray="7,4"/>
        <circle cx="{int(x1*0.65 + x2*0.35)}" cy="{int(y1*0.65 + y2*0.35)}" r="4.5" fill="#ffffff" stroke="{color}" stroke-width="2"/>
        <circle cx="{int(x1*0.3 + x2*0.7)}" cy="{int(y1*0.3 + y2*0.7)}" r="4" fill="{color}"/>
        {lbl}
        """

    cards = []
    # Stage 1 (x=60): Cloud Pools & Triggers
    s1 = [
        (95, "Claude Pool A ($250)", "TRIGGER • ANTHROPIC", "Opus 5.5 • 5h: 0% • Exp Nov 5", "#a855f7", "claude-A Opus", "#7c3aed"),
        (225, "Claude Pool B ($250 PM)", "TRIGGER • PM SEAT", "Opus 5.5 + Fable 5.1 • $250", "#c084fc", "bd-pm-B PM", "#9333ea"),
        (355, "Claude Pools C & D ($500)", "TRIGGER • PARALLEL", "Sonnet 5.5 • $250x2 • Cap 30", "#8b5cf6", "claude-C/D", "#6d28d9"),
        (485, "OpenAI Codex Cloud", "TRIGGER • VERIFIER", "gpt-6.1-sol • gpt-6-astra", "#10b981", "GPT-6.1-Sol", "#059669"),
        (615, "AGY Council & Kimi Code", "TRIGGER • MULTI-AGENT", "10 Subagents • Kimi 256k", "#06b6d4", "AGY-Council", "#0284c7"),
        (745, "Hermes-4 & Local Dispatch", "TRIGGER • SATELLITE", "Zero-Cost Local AI Router", "#f59e0b", "Hermes-4", "#d97706"),
    ]
    for y, t, s, m, c, av, abg in s1:
        cards.append(rf_node(60, y, t, s, m, c, av, abg))

    # Stage 2 (x=455): Orchestration, Gateway & Oracles
    s2 = [
        (130, "Controller Nexus (.164)", "ORCHESTRATOR • BD", "32 Web UIs • O1740 Router", "#f59e0b", "bd-pm-B Live", "#d97706"),
        (285, "LiteLLM & Langfuse (.228)", "AI GATEWAY • T4 #4", "Port :4000/:3000 • 280G RAM", "#00e5ff", "17 Models", "#0891b2"),
        (440, "BattleStation CDP (.137)", "ORACLE #1 • RYZEN 9", "Chrome :9222 + RTX 2080 Ti", "#38bdf8", "CDP Oracle 1", "#0284c7"),
        (595, "Bittorrent CDP (.181)", "ORACLE #2 • WINDOWS", "Parallel Browser Bridge :9222", "#38bdf8", "CDP Oracle 2", "#0369a1"),
        (745, "Qdrant Vector RAG (.125)", "EMBEDDING • T4 #3", "Port :6333 + Qwen2.5-32B", "#10b981", "RAG :6333", "#059669"),
    ]
    for y, t, s, m, c, av, abg in s2:
        cards.append(rf_node(455, y, t, s, m, c, av, abg))

    # Stage 3 (x=855): 25GbE RoCE GPU Tensor Vaults & 64c Ramdisk
    s3 = [
        (130, "AI Vault A • ai-srv01 (.72)", "VLAN 75 • TESLA T4 #1", "deepseek-v3-671b @ 77.6 tok/s", "#00e5ff", "Vault A 5TB", "#0891b2"),
        (285, "AI DEV Vault B • aidev (.83)", "VLAN 75 • TESLA T4 #2", "RoCE RPC :50052 • MiMo-1024B", "#00e5ff", "Vault B 5TB", "#0891b2"),
        (440, "CI Ramdisk • test3big (.82)", "64-vCPU • 128G RAMDISK", "/dev/shm Pytest Shards • 0 IO", "#10b981", "64c xdist", "#059669"),
        (595, "Builder Fleet (bd1..bd4)", "4X LINUX WORKER VMS", ".51, .210, .211, .212 • Git WT", "#60a5fa", "4x Builders", "#2563eb"),
        (745, "Verifier Fleet (test1..7)", "8X TEST + 10X SPARE VMS", "14 Active VMs • 8 DRS Standby", "#818cf8", "22 VMs OK", "#4f46e5"),
    ]
    for y, t, s, m, c, av, abg in s3:
        cards.append(rf_node(855, y, t, s, m, c, av, abg))

    # Stage 4 (x=1255): Physical Switch, ESXi Hypervisors & vSAN
    s4 = [
        (130, "USW-Pro-Aggregation 280G", "CORE SWITCH • .10.2", "28x 10G SFP+ • 4x 25G SFP28", "#38bdf8", "280G Spine", "#0284c7"),
        (285, "ESXi 01 & 02 Hypervisors", "HPE PROLIANT • vSAN", ".101 & .102 • iLO .10/.20 OK", "#3b82f6", "2x Hosts", "#1d4ed8"),
        (440, "ESXi 03 & 04 Hypervisors", "HPE PROLIANT • vSAN", ".103 & .104 • iLO .30/.40 OK", "#3b82f6", "2x Hosts", "#1d4ed8"),
        (595, "vSAN 328.4 TiB All-Flash/Exos", "VLAN 60 • 75 DISKS", "11 Disk Groups • 41.3% Used", "#10b981", "328.4 TiB", "#059669"),
        (745, "UDM-Pro + Traefik + Sentinel", "INGRESS & SELF-HEAL", "32 DNS • 83 Services Healed", "#f43f5e", "83/83 GREEN", "#e11d48"),
    ]
    for y, t, s, m, c, av, abg in s4:
        cards.append(rf_node(1255, y, t, s, m, c, av, abg))

    # Stage 5 (x=1610): Output Sinks / Live Cockpits
    s5 = [
        (160, "Dashy Nexus (:4080)", "OUTPUT • PORTAL", "15 Studios • 100% GREEN", "#10b981", "", "", 255, 86),
        (330, "3D Topology (:4088)", "OUTPUT • VISUALIZER", "Live Swarm Flow & Ping", "#00e5ff", "", "", 255, 86),
        (500, "Multi-Harness (:4098)", "OUTPUT • AI ARENA", "6-Way Prompt Fanout", "#a855f7", "", "", 255, 86),
        (670, "Cloud & Vault (:4090/:4087)", "OUTPUT • FINOPS/SSH", "$1,000 Credits • 38 SSH", "#f59e0b", "", "", 255, 86),
    ]
    for y, t, s, m, c, av, abg, w, h in s5:
        cards.append(rf_node(1610, y, t, s, m, c, av, abg, w, h))

    wires = [
        bezier_wire(310, 138, 455, 173, "#a855f7", "Opus 5.5"),
        bezier_wire(310, 268, 455, 173, "#c084fc", "PM Order"),
        bezier_wire(310, 398, 455, 328, "#8b5cf6", "$500 Burst"),
        bezier_wire(310, 528, 455, 328, "#10b981", "GPT-6.1-Sol"),
        bezier_wire(310, 658, 455, 483, "#06b6d4", "CDP Fanout"),
        bezier_wire(310, 788, 455, 788, "#f59e0b", "RAG Query"),
        # Stage 2 -> Stage 3
        bezier_wire(705, 173, 855, 173, "#00e5ff", "77.6 tok/s"),
        bezier_wire(705, 173, 855, 483, "#10b981", "Pytest xdist"),
        bezier_wire(705, 328, 855, 173, "#00e5ff", "RoCE Tensor"),
        bezier_wire(705, 328, 855, 328, "#00e5ff", "RPC :50052"),
        bezier_wire(705, 483, 855, 638, "#38bdf8", "E2E Verify"),
        bezier_wire(705, 788, 855, 788, "#10b981", "Vector Hits"),
        # Stage 3 -> Stage 4
        bezier_wire(1105, 173, 1255, 173, "#00e5ff", "25GbE SFP28"),
        bezier_wire(1105, 328, 1255, 173, "#00e5ff", "25GbE SFP28"),
        bezier_wire(1105, 483, 1255, 328, "#3b82f6", "vSphere VM"),
        bezier_wire(1105, 638, 1255, 483, "#3b82f6", "vSphere VM"),
        bezier_wire(1105, 788, 1255, 638, "#10b981", "10G vSAN IO"),
        # Stage 4 -> Stage 5
        bezier_wire(1505, 173, 1610, 203, "#10b981", ""),
        bezier_wire(1505, 328, 1610, 373, "#00e5ff", ""),
        bezier_wire(1505, 483, 1610, 543, "#a855f7", ""),
        bezier_wire(1505, 638, 1610, 713, "#f59e0b", ""),
    ]

    return f"""
    <div style="width:1920px;height:1034px;background:#111318;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      <!-- Top Floating n8n / ReactFlow Workflow Bar -->
      <div style="position:absolute;left:24px;top:16px;right:24px;height:50px;background:#181b24;border:1px solid #282e3d;border-radius:12px;display:flex;align-items:center;justify-content:space-between;padding:0 20px;z-index:5;box-shadow:0 10px 25px rgba(0,0,0,0.4);">
        <div style="display:flex;align-items:center;gap:14px;">
          <span style="background:linear-gradient(135deg,#ff6d5a,#ff4b4b);color:#fff;padding:5px 12px;border-radius:8px;font-weight:800;font-size:12px;">n8n / ReactFlow Canvas</span>
          <span style="color:#f8fafc;font-weight:800;font-size:14px;">Workflow: Boylenet Autonomous Swarm Pipeline (#O1789)</span>
          <span style="background:#10b98122;color:#34d399;border:1px solid #10b98155;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;">● EXECUTING LIVE (15 Agents • 27 VMs)</span>
        </div>
        <div style="display:flex;align-items:center;gap:10px;font-family:'JetBrains Mono',monospace;font-size:11px;">
          <span style="background:#0f1117;border:1px solid #282e3d;color:#cbd5e1;padding:5px 12px;border-radius:8px;">Nodes: <b style="color:#00e5ff;">36</b></span>
          <span style="background:#0f1117;border:1px solid #282e3d;color:#cbd5e1;padding:5px 12px;border-radius:8px;">Edges: <b style="color:#a855f7;">48 Bezier</b></span>
          <span style="background:#0f1117;border:1px solid #282e3d;color:#cbd5e1;padding:5px 12px;border-radius:8px;">RoCE Tensor: <b style="color:#10b981;">77.6 tok/s</b></span>
          <span style="background:#7c3aed;color:#fff;padding:5px 14px;border-radius:8px;font-weight:700;">⚡ Trigger Swarm Wave</span>
        </div>
      </div>

      <!-- Stage Column Pill Headers -->
      <div style="position:absolute;left:60px;top:74px;color:#a855f7;font-size:11px;font-weight:800;letter-spacing:0.8px;">STAGE 1 • AI HARNESSES &amp; $1,000 CLOUD POOLS</div>
      <div style="position:absolute;left:455px;top:74px;color:#f59e0b;font-size:11px;font-weight:800;letter-spacing:0.8px;">STAGE 2 • COMMAND NEXUS, GATEWAY &amp; ORACLES</div>
      <div style="position:absolute;left:855px;top:74px;color:#00e5ff;font-size:11px;font-weight:800;letter-spacing:0.8px;">STAGE 3 • 4X TESLA T4 ROCE VAULTS &amp; 23 WORKER VMS</div>
      <div style="position:absolute;left:1255px;top:74px;color:#3b82f6;font-size:11px;font-weight:800;letter-spacing:0.8px;">STAGE 4 • 280G SPINE, 4X ESXi &amp; 328TB vSAN</div>
      <div style="position:absolute;left:1610px;top:74px;color:#10b981;font-size:11px;font-weight:800;letter-spacing:0.8px;">STAGE 5 • LIVE COCKPITS</div>

      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <defs>
          <pattern id="rf-grid" width="28" height="28" patternUnits="userSpaceOnUse">
            <path d="M 14 11 L 14 17 M 11 14 L 17 14" stroke="#222634" stroke-width="1"/>
          </pattern>
        </defs>
        <rect width="1920" height="1034" fill="url(#rf-grid)"/>
        {''.join(wires)}
        {''.join(cards)}
      </svg>

      <!-- ReactFlow Bottom-Left Zoom Controls & Bottom-Right MiniMap -->
      <div style="position:absolute;left:24px;bottom:20px;display:flex;gap:8px;z-index:5;">
        <div style="background:#181b24;border:1px solid #282e3d;border-radius:8px;padding:8px 14px;color:#cbd5e1;font-size:12px;font-family:'JetBrains Mono',monospace;">🔍 100% • Fit View • Interactive Bezier Handles</div>
      </div>
      <div style="position:absolute;right:24px;bottom:20px;width:230px;height:110px;background:#181b24;border:1px solid #38bdf866;border-radius:10px;padding:10px;z-index:5;">
        <div style="font-size:9.5px;color:#94a3b8;font-weight:700;margin-bottom:6px;display:flex;justify-content:space-between;">
          <span>REACTFLOW MINIMAP</span><span style="color:#00e5ff;">1920×1080</span>
        </div>
        <svg width="208" height="75" style="background:#0f1117;border-radius:6px;">
          <rect x="8" y="8" width="28" height="58" rx="3" fill="#a855f744" stroke="#a855f7"/>
          <rect x="48" y="12" width="28" height="50" rx="3" fill="#f59e0b44" stroke="#f59e0b"/>
          <rect x="88" y="12" width="28" height="50" rx="3" fill="#00e5ff44" stroke="#00e5ff"/>
          <rect x="128" y="12" width="28" height="50" rx="3" fill="#3b82f644" stroke="#3b82f6"/>
          <rect x="168" y="16" width="28" height="42" rx="3" fill="#10b98144" stroke="#10b981"/>
          <rect x="2" y="2" width="204" height="71" fill="none" stroke="#ffffff66" stroke-width="1" stroke-dasharray="3,2"/>
        </svg>
      </div>
    </div>
    """


def build_style_03_palantir() -> str:
    """Style 3: Palantir Gotham / Tactical Defense HUD."""
    targets = [
        (960, 510, "TGT-164 // BD-CONTROLLER", "10.0.70.164 • 32 UIs • PM-B", "#ffb000", True),
        (760, 355, "TGT-072 // AI-SRV01 T4", "10.0.75.11 • 77.6 TOK/S ROCE", "#00f0ff", True),
        (1160, 355, "TGT-083 // AIDEV T4", "10.0.75.12 • RPC :50052 VAULT-B", "#00f0ff", True),
        (760, 665, "TGT-125 // AI-INFER01 T4", "10.0.70.125 • QDRANT :6333", "#00f0ff", False),
        (1160, 665, "TGT-228 // AI-OLLAMA01 T4", "10.0.70.228 • LITELLM :4000", "#00f0ff", False),
        (960, 240, "TGT-002 // USW-AGG-280G", "28x10G + 4x25G SFP28 SPINE", "#00f0ff", False),
        (960, 785, "TGT-070 // VCENTER + VSAN", "328.4 TiB • 75 DISKS • 4 ESXi", "#10b981", False),
        (615, 510, "TGT-082 // TEST3BIG 64C", "128G /DEV/SHM RAMDISK PYTEST", "#10b981", True),
        (1305, 510, "TGT-137 // BATTLESTATION", "CDP :9222 + RTX 2080Ti + .181", "#ffb000", True),
        (555, 250, "CLD-AB // ANTHROPIC $500", "POOLS A & B • OPUS 5.5 READY", "#c084fc", False),
        (1365, 250, "CLD-CD // ANTHROPIC $500", "POOLS C & D + CODEX SOL", "#c084fc", False),
        (555, 760, "POD-BD // BUILDERS BD1..4", ".51, .210, .211, .212 ACTIVE", "#00f0ff", False),
        (1365, 760, "POD-TST // TEST1..7 + SPARE", "14 ACTIVE VMS • 8 DRS STANDBY", "#00f0ff", False),
    ]

    reticles = []
    for x, y, code, sub, col, locked in targets:
        r = 34 if locked else 26
        reticles.append(f"""
        <g transform="translate({x},{y})">
          <line x1="0" y1="0" x2="{960-x}" y2="{510-y}" stroke="{col}" stroke-width="1.1" stroke-dasharray="4,4" opacity="0.45"/>
          <circle cx="0" cy="0" r="{r}" fill="{col}" fill-opacity="0.07" stroke="{col}" stroke-width="1" stroke-dasharray="6,3"/>
          <!-- Corner Targeting Brackets -->
          <path d="M {-r-6} {-r+8} L {-r-6} {-r-6} L {-r+8} {-r-6}" fill="none" stroke="{col}" stroke-width="2"/>
          <path d="M {r-8} {-r-6} L {r+6} {-r-6} L {r+6} {-r+8}" fill="none" stroke="{col}" stroke-width="2"/>
          <path d="M {-r-6} {r-8} L {-r-6} {r+6} L {-r+8} {r+6}" fill="none" stroke="{col}" stroke-width="2"/>
          <path d="M {r-8} {r+6} L {r+6} {r+6} L {r+6} {r-8}" fill="none" stroke="{col}" stroke-width="2"/>
          <circle cx="0" cy="0" r="4.5" fill="{col}"/>
          <rect x="{-92}" y="{r+10}" width="184" height="32" fill="#040a10" stroke="{col}" stroke-width="1"/>
          <text x="0" y="{r+23}" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="800">{code}</text>
          <text x="0" y="{r+36}" text-anchor="middle" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="8.5">{sub}</text>
        </g>
        """)

    # Degree ticks around radar
    ticks = []
    for deg in range(0, 360, 10):
        rad = math.radians(deg)
        r1 = 425
        r2 = 438 if deg % 30 == 0 else 431
        x1, y1 = 960 + r1 * math.cos(rad), 510 + r1 * math.sin(rad)
        x2, y2 = 960 + r2 * math.cos(rad), 510 + r2 * math.sin(rad)
        ticks.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#00f0ff" stroke-width="1" opacity="0.5"/>')
        if deg % 30 == 0:
            tx, ty = 960 + 452 * math.cos(rad), 510 + 452 * math.sin(rad)
            ticks.append(f'<text x="{tx:.1f}" y="{ty+3:.1f}" text-anchor="middle" fill="#00f0ff" font-family="JetBrains Mono,monospace" font-size="8.5" opacity="0.7">{deg:03d}°</text>')

    return f"""
    <div style="width:1920px;height:1034px;background:#03070b;position:relative;overflow:hidden;font-family:'JetBrains Mono',monospace;color:#00f0ff;">
      <!-- Top Classification Banner -->
      <div style="height:34px;background:#07131d;border-bottom:1px solid #00f0ff55;display:flex;align-items:center;justify-content:space-between;padding:0 20px;font-size:11px;letter-spacing:1.4px;">
        <span style="color:#ffb000;font-weight:800;">// PALANTIR GOTHAM C4ISR // BOYLENET SWARM TACTICAL COMMAND HUD //</span>
        <span>GRID: 10.0.70.0/24 + VLAN-75 ROCE • 27 VMS • 656 VCPU • 4X TESLA T4 • 328.4 TIB VSAN</span>
        <span style="color:#10b981;font-weight:800;">DEFCON-5 // ALL 83 SERVICES NOMINAL</span>
      </div>

      <!-- Left Tactical Panel -->
      <div style="position:absolute;left:18px;top:50px;width:410px;bottom:18px;border:1px solid #00f0ff44;background:rgba(5,14,22,0.88);padding:14px;display:flex;flex-direction:column;justify-content:space-between;">
        <div>
          <div style="border-bottom:1px solid #00f0ff44;padding-bottom:6px;margin-bottom:10px;display:flex;justify-content:space-between;font-size:11px;font-weight:800;">
            <span>01 // O1740 DYNAMIC CAPABILITY ROUTER</span>
            <span style="color:#ffb000;">CAP: 30/30</span>
          </div>
          <table style="width:100%;font-size:10px;border-collapse:collapse;color:#cbd5e1;">
            <tr style="color:#00f0ff;border-bottom:1px solid #00f0ff33;"><th align="left">POOL / HARNESS</th><th align="left">STATE</th><th align="right">5H%</th><th align="right">CREDIT</th></tr>
            <tr><td style="padding:5px 0;">CLAUDE-POOL-A (OPUS)</td><td style="color:#10b981;">OK</td><td align="right">0%</td><td align="right" style="color:#ffb000;">$250.00</td></tr>
            <tr><td style="padding:5px 0;">CLAUDE-POOL-B (PM-B)</td><td style="color:#10b981;">OK</td><td align="right">0%</td><td align="right" style="color:#ffb000;">$250.00</td></tr>
            <tr><td style="padding:5px 0;">CLAUDE-POOL-C (SONNET)</td><td style="color:#10b981;">OK</td><td align="right">5%</td><td align="right" style="color:#ffb000;">$250.00</td></tr>
            <tr><td style="padding:5px 0;">CLAUDE-POOL-D (SONNET)</td><td style="color:#10b981;">OK</td><td align="right">0%</td><td align="right" style="color:#ffb000;">$250.00</td></tr>
            <tr><td style="padding:5px 0;">CODEX (GPT-6.1-SOL)</td><td style="color:#10b981;">OK</td><td align="right">0%</td><td align="right" style="color:#00f0ff;">FLAT</td></tr>
            <tr><td style="padding:5px 0;">KIMI-CODE + AGY-SWARM</td><td style="color:#10b981;">OK</td><td align="right">19%</td><td align="right" style="color:#00f0ff;">ACTIVE</td></tr>
          </table>

          <div style="border-bottom:1px solid #00f0ff44;padding-bottom:6px;margin:16px 0 10px;display:flex;justify-content:space-between;font-size:11px;font-weight:800;">
            <span>02 // VLAN 75 25GBE ROCE TENSOR ARRAY</span>
            <span style="color:#10b981;">77.6 TOK/S</span>
          </div>
          <div style="font-size:10px;line-height:1.75;color:#94a3b8;">
            <div>[T4-01] <b style="color:#00f0ff;">10.0.70.72 (ai-srv01)</b> • 10.1/15.3GB • 71°C • 31.2W</div>
            <div>[T4-02] <b style="color:#00f0ff;">10.0.70.83 (aidev)</b> • 10.7/15.3GB • 74°C • 32.5W</div>
            <div>[T4-03] <b style="color:#00f0ff;">10.0.70.125 (ai-infer01)</b> • 11.9/15.3GB • 60°C • 30.1W</div>
            <div>[T4-04] <b style="color:#00f0ff;">10.0.70.228 (ai-ollama01)</b> • 12.4/15.3GB • 73°C • 31.1W</div>
          </div>

          <div style="border-bottom:1px solid #00f0ff44;padding-bottom:6px;margin:16px 0 10px;display:flex;justify-content:space-between;font-size:11px;font-weight:800;">
            <span>03 // 4X HPE ESXi &amp; ILO4 TELEMETRY</span>
            <span style="color:#00f0ff;">VLAN 10/20/60</span>
          </div>
          <div style="font-size:10px;line-height:1.75;color:#94a3b8;">
            <div>ESXI-01 (.101 / iLO .10) • 1x DG All-Flash • 246W • 23°C</div>
            <div>ESXI-02 (.102 / iLO .20) • 3x DG 96TB Exos • 312W • 24°C</div>
            <div>ESXI-03 (.103 / iLO .30) • 3x DG 96TB Exos • 298W • 24°C</div>
            <div>ESXI-04 (.104 / iLO .40) • 3x DG 96TB Exos • 324W • 25°C</div>
          </div>
        </div>

        <div style="border:1px solid #ffb00066;background:#ffb00012;padding:10px;font-size:10px;color:#ffb000;">
          <b>TACTICAL LOCK:</b> DEEPSEEK-V3-0324-671B + KIMI-K2.5-1T DUAL-VAULT STREAMING OVER 25GBE SFP28 ROCE (0.0% PACKET LOSS)
        </div>
      </div>

      <!-- Center Radar & Vector Map -->
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;pointer-events:none;">
        <!-- Radar Rings centered at (960,510) -->
        <circle cx="960" cy="510" r="120" fill="none" stroke="#00f0ff" stroke-width="0.8" opacity="0.3"/>
        <circle cx="960" cy="510" r="230" fill="none" stroke="#00f0ff" stroke-width="1" stroke-dasharray="8,4" opacity="0.4"/>
        <circle cx="960" cy="510" r="330" fill="none" stroke="#00f0ff" stroke-width="0.8" opacity="0.3"/>
        <circle cx="960" cy="510" r="425" fill="none" stroke="#00f0ff" stroke-width="1.4" opacity="0.5"/>
        <line x1="510" y1="510" x2="1410" y2="510" stroke="#00f0ff" stroke-width="0.7" opacity="0.3"/>
        <line x1="960" y1="60" x2="960" y2="960" stroke="#00f0ff" stroke-width="0.7" opacity="0.3"/>
        <!-- RoCE High-Intensity Diamond Link between .72 and .83 -->
        <line x1="760" y1="355" x2="1160" y2="355" stroke="#ffb000" stroke-width="2.8"/>
        <rect x="895" y="344" width="130" height="20" fill="#03070b" stroke="#ffb000" stroke-width="1.2"/>
        <text x="960" y="357" text-anchor="middle" fill="#ffb000" font-size="9.5" font-weight="800">25GBE ROCE :50052</text>
        {''.join(ticks)}
        {''.join(reticles)}
      </svg>

      <!-- Right Tactical Intercept & 27-VM Matrix Panel -->
      <div style="position:absolute;right:18px;top:50px;width:410px;bottom:18px;border:1px solid #00f0ff44;background:rgba(5,14,22,0.88);padding:14px;display:flex;flex-direction:column;justify-content:space-between;">
        <div>
          <div style="border-bottom:1px solid #00f0ff44;padding-bottom:6px;margin-bottom:10px;display:flex;justify-content:space-between;font-size:11px;font-weight:800;">
            <span>04 // 27-VM CLUSTER READINESS MATRIX</span>
            <span style="color:#10b981;">19 ON / 8 DRS</span>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;font-size:9px;">
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">bd (.164) ON</div>
            <div style="border:1px solid #00f0ff;padding:4px 6px;color:#00f0ff;">ai-srv01 (.72)</div>
            <div style="border:1px solid #00f0ff;padding:4px 6px;color:#00f0ff;">aidev (.83)</div>
            <div style="border:1px solid #00f0ff;padding:4px 6px;color:#00f0ff;">infer01 (.125)</div>
            <div style="border:1px solid #00f0ff;padding:4px 6px;color:#00f0ff;">ollama01 (.228)</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">test3big (.82)</div>
            <div style="border:1px solid #ffb000;padding:4px 6px;color:#ffb000;">BattleSt (.137)</div>
            <div style="border:1px solid #ffb000;padding:4px 6px;color:#ffb000;">Bittorrent (.181)</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">vc04 (.70) ON</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">bd1 (.51) ON</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">bd2 (.210) ON</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">bd3 (.211) ON</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">bd4 (.212) ON</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">test1 (.81) ON</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">test2 (.84) ON</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">test4 (.85) ON</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">test5 (.86) ON</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">test6 (.197) ON</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">test7 (.249) ON</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">fresh149 (.149)</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">spare1 (.120)</div>
            <div style="border:1px solid #10b981;padding:4px 6px;color:#10b981;">spare2 (.183)</div>
            <div style="border:1px solid #475569;padding:4px 6px;color:#64748b;">spare3..6 DRS</div>
            <div style="border:1px solid #475569;padding:4px 6px;color:#64748b;">spare7..10 DRS</div>
          </div>

          <div style="border-bottom:1px solid #00f0ff44;padding-bottom:6px;margin:16px 0 10px;display:flex;justify-content:space-between;font-size:11px;font-weight:800;">
            <span>05 // LIVE SWARM COMMAND INTERCEPT</span>
            <span style="color:#ffb000;">WAL STREAM</span>
          </div>
          <div style="font-size:9.5px;line-height:1.7;color:#94a3b8;">
            <div><span style="color:#00f0ff;">16:44:02Z</span> [AGY-COUNCIL] 15/15 Web UIs HTTP 200 verified</div>
            <div><span style="color:#ffb000;">16:44:08Z</span> [BD-PM-B] Opus-5.5 Pool B 0% 5h window active</div>
            <div><span style="color:#10b981;">16:44:15Z</span> [ROCE-75] .72 &lt;-&gt; .83:50052 tensor sync 77.6 tok/s</div>
            <div><span style="color:#00f0ff;">16:44:21Z</span> [ORACLE-137] Chrome/155 CDP 1920x1080 locked</div>
            <div><span style="color:#c084fc;">16:44:29Z</span> [CLOUD-BURST] $1,000 Credit Pool ($0 overage)</div>
            <div><span style="color:#10b981;">16:44:35Z</span> [SENTINEL] 83/83 cluster services self-healed</div>
          </div>
        </div>
        <div style="border-top:1px solid #00f0ff44;padding-top:10px;display:flex;justify-content:space-between;font-size:10px;color:#00f0ff;">
          <span>STYLE #3 // PALANTIR GOTHAM HUD</span>
          <span>LATENCY: 0.18ms</span>
        </div>
      </div>
    </div>
    """


def build_style_04_isometric() -> str:
    """Style 4: Isometric 2.5D / 3D Data-Center Floor (Cloudcraft / SimCity Style)."""
    def iso_pt(gx: float, gy: float, gz: float = 0.0) -> tuple[float, float]:
        # Center around (960, 540)
        sx = 960.0 + (gx - gy) * 0.88
        sy = 175.0 + (gx + gy) * 0.44 - gz
        return sx, sy

    def iso_platform(gx: float, gy: float, gw: float, gd: float, gh: float, top_fill: str, edge_col: str, label: str, sub: str) -> str:
        x0, y0 = iso_pt(gx, gy, 0)
        x1, y1 = iso_pt(gx + gw, gy, 0)
        x2, y2 = iso_pt(gx + gw, gy + gd, 0)
        x3, y3 = iso_pt(gx, gy + gd, 0)
        bx1, by1 = iso_pt(gx + gw, gy, -gh)
        bx2, by2 = iso_pt(gx + gw, gy + gd, -gh)
        bx3, by3 = iso_pt(gx, gy + gd, -gh)
        lx, ly = iso_pt(gx + gw * 0.5, gy + gd + 18, 0)
        return f"""
        <g>
          <!-- Platform Glow -->
          <polygon points="{x0:.1f},{y0:.1f} {x1:.1f},{y1:.1f} {x2:.1f},{y2:.1f} {x3:.1f},{y3:.1f}" fill="{edge_col}" opacity="0.12"/>
          <!-- Left Wall -->
          <polygon points="{x3:.1f},{y3:.1f} {x2:.1f},{y2:.1f} {bx2:.1f},{by2:.1f} {bx3:.1f},{by3:.1f}" fill="#0c1428" stroke="{edge_col}" stroke-width="1.2"/>
          <!-- Right Wall -->
          <polygon points="{x1:.1f},{y1:.1f} {x2:.1f},{y2:.1f} {bx2:.1f},{by2:.1f} {bx1:.1f},{by1:.1f}" fill="#070c1a" stroke="{edge_col}" stroke-width="1.2"/>
          <!-- Top Surface -->
          <polygon points="{x0:.1f},{y0:.1f} {x1:.1f},{y1:.1f} {x2:.1f},{y2:.1f} {x3:.1f},{y3:.1f}" fill="{top_fill}" stroke="{edge_col}" stroke-width="2"/>
          <!-- Zone Label Banner -->
          <rect x="{lx-135:.1f}" y="{ly-6:.1f}" width="270" height="32" rx="6" fill="#070b18" stroke="{edge_col}" stroke-width="1.3"/>
          <text x="{lx:.1f}" y="{ly+7:.1f}" text-anchor="middle" fill="{edge_col}" font-family="Inter,sans-serif" font-size="10.5" font-weight="800">{label}</text>
          <text x="{lx:.1f}" y="{ly+20:.1f}" text-anchor="middle" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="9">{sub}</text>
        </g>
        """

    def iso_tower(gx: float, gy: float, gw: float, gd: float, gh: float, col_top: str, col_left: str, col_right: str, stroke: str, tag: str, sub: str = "") -> str:
        # Base corners at z=0, top corners at z=gh
        b0x, b0y = iso_pt(gx, gy, 0)
        b1x, b1y = iso_pt(gx + gw, gy, 0)
        b2x, b2y = iso_pt(gx + gw, gy + gd, 0)
        b3x, b3y = iso_pt(gx, gy + gd, 0)
        t0x, t0y = iso_pt(gx, gy, gh)
        t1x, t1y = iso_pt(gx + gw, gy, gh)
        t2x, t2y = iso_pt(gx + gw, gy + gd, gh)
        t3x, t3y = iso_pt(gx, gy + gd, gh)
        cx, cy = (t0x + t2x) * 0.5, (t0y + t2y) * 0.5
        # LED stripes on front-left wall
        stripes = []
        for s in range(1, 4):
            fz = gh * (s / 4.2)
            s3x, s3y = iso_pt(gx, gy + gd, fz)
            s2x, s2y = iso_pt(gx + gw, gy + gd, fz)
            stripes.append(f'<line x1="{s3x+4:.1f}" y1="{s3y-2:.1f}" x2="{s2x-4:.1f}" y2="{s2y-2:.1f}" stroke="{stroke}" stroke-width="2" opacity="0.85"/>')

        tag_w = max(108, len(tag) * 6 + 18)
        sub_html = f'<text x="{cx:.1f}" y="{cy-16:.1f}" text-anchor="middle" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="8.5">{sub}</text>' if sub else ""
        box_h = 30 if sub else 19
        box_y = cy - 41 if sub else cy - 30
        txt_y = cy - 29 if sub else cy - 17
        return f"""
        <g>
          <!-- Left Front Face -->
          <polygon points="{t3x:.1f},{t3y:.1f} {t2x:.1f},{t2y:.1f} {b2x:.1f},{b2y:.1f} {b3x:.1f},{b3y:.1f}" fill="{col_left}" stroke="{stroke}" stroke-width="1.2"/>
          <!-- Right Front Face -->
          <polygon points="{t2x:.1f},{t2y:.1f} {t1x:.1f},{t1y:.1f} {b1x:.1f},{b1y:.1f} {b2x:.1f},{b2y:.1f}" fill="{col_right}" stroke="{stroke}" stroke-width="1.2"/>
          <!-- Top Roof Face -->
          <polygon points="{t0x:.1f},{t0y:.1f} {t1x:.1f},{t1y:.1f} {t2x:.1f},{t2y:.1f} {t3x:.1f},{t3y:.1f}" fill="{col_top}" stroke="{stroke}" stroke-width="1.5"/>
          {''.join(stripes)}
          <!-- Floating Isometric Callout Flag -->
          <line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx:.1f}" y2="{cy-12:.1f}" stroke="{stroke}" stroke-width="1.4"/>
          <rect x="{cx - tag_w/2:.1f}" y="{box_y:.1f}" width="{tag_w}" height="{box_h}" rx="5" fill="#060a15" stroke="{stroke}" stroke-width="1.1" opacity="0.95"/>
          <text x="{cx:.1f}" y="{txt_y:.1f}" text-anchor="middle" fill="#f8fafc" font-family="Inter,sans-serif" font-size="9.5" font-weight="800">{tag}</text>
          {sub_html}
        </g>
        """

    def iso_beam(gx1: float, gy1: float, gx2: float, gy2: float, col: str, label: str = "") -> str:
        x1, y1 = iso_pt(gx1, gy1, 8)
        x2, y2 = iso_pt(gx2, gy2, 8)
        mx, my = (x1 + x2) * 0.5, (y1 + y2) * 0.5
        lbl = ""
        if label:
            lbl = f"""
            <rect x="{mx-58:.1f}" y="{my-10:.1f}" width="116" height="18" rx="9" fill="#050814" stroke="{col}" stroke-width="1.2"/>
            <text x="{mx:.1f}" y="{my+2.5:.1f}" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="8.5" font-weight="700">{label}</text>
            """
        return f"""
        <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="6" opacity="0.2"/>
        <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="2.4" stroke-dasharray="8,4"/>
        {lbl}
        """

    # Background Isometric Floor Grid
    grid_lines = []
    for i in range(-180, 980, 60):
        x1, y1 = iso_pt(i, -120)
        x2, y2 = iso_pt(i, 920)
        grid_lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#131d38" stroke-width="1"/>')
        x3, y3 = iso_pt(-180, i)
        x4, y4 = iso_pt(980, i)
        grid_lines.append(f'<line x1="{x3:.1f}" y1="{y3:.1f}" x2="{x4:.1f}" y2="{y4:.1f}" stroke="#131d38" stroke-width="1"/>')

    platforms = [
        # Platform 1: Cloud Sky-Deck (Top-Left in iso)
        iso_platform(-120, 60, 250, 290, 14, "#1a103c", "#a855f7", "ZONE 01 • $1,000 CLOUD BURST SKY-DECK", "Pools A/B/C/D ($250x4) • Codex • Kimi • AGY"),
        # Platform 2: Network Core & 4x T4 GPU Island (Top-Right in iso)
        iso_platform(210, -60, 320, 290, 16, "#06283d", "#00e5ff", "ZONE 02 • 280G SPINE & 4X TESLA T4 ROCE VAULTS", "UDM-Pro • USW-Agg 280G • .72/.83/.125/.228 (77.6 tok/s)"),
        # Platform 3: 4x HPE ESXi & 328TiB vSAN (Bottom-Right in iso)
        iso_platform(590, 110, 290, 340, 16, "#0b2239", "#3b82f6", "ZONE 03 • 4X HPE DL380 ESXi & 328.4 TiB vSAN", "esxi01..04 (2x SFF + 2x 12-Bay LFF) • UPS + USW-Pro-Max Rear"),
        # Platform 4: 23-VM Compute Grid & Oracles (Center/Bottom-Left in iso)
        iso_platform(150, 350, 380, 380, 14, "#082924", "#10b981", "ZONE 04 • CONTROLLER, ORACLES & 23 WORKER VMS", "bd .164 • test3big .82 (64c) • .137/.181 CDP • bd1..4 • test1..7"),
    ]

    beams = [
        iso_beam(130, 190, 260, 350, "#a855f7", "$1,000 Cloud API"),
        iso_beam(350, 230, 340, 350, "#00e5ff", "25GbE RoCE 77.6t/s"),
        iso_beam(530, 120, 600, 220, "#38bdf8", "280G SFP28 Trunk"),
        iso_beam(530, 520, 620, 360, "#10b981", "10GbE vSAN 328TiB"),
    ]

    towers = [
        # Zone 1: Cloud Towers
        iso_tower(-85, 95, 65, 65, 95, "#c084fc", "#6b21a8", "#4c1d95", "#d8b4fe", "Pool A & B ($500)", "Opus 5.5 PM"),
        iso_tower(15, 95, 65, 65, 85, "#a855f7", "#581c87", "#3b0764", "#c084fc", "Pool C & D ($500)", "Sonnet 5.5"),
        iso_tower(-85, 210, 65, 65, 80, "#34d399", "#065f46", "#064e3b", "#10b981", "Codex GPT-6.1-Sol", "OpenAI Pool"),
        iso_tower(15, 210, 65, 65, 88, "#38bdf8", "#075985", "#0c4a6e", "#00e5ff", "AGY-Council + Kimi", "10 Subagents"),
        # Zone 2: Spine + 4x Tesla T4 GPU Towers
        iso_tower(240, -25, 75, 55, 62, "#e2e8f0", "#475569", "#334155", "#38bdf8", "UDM-Pro + 280G Agg", "4x1U UniFi Stack"),
        iso_tower(365, -25, 78, 68, 122, "#22d3ee", "#0e7490", "#155e75", "#00e5ff", "ai-srv01 (.72) T4", "5TB Vault A • 77.6t/s"),
        iso_tower(455, -25, 78, 68, 122, "#22d3ee", "#0e7490", "#155e75", "#00e5ff", "aidev (.83) T4", "5TB Vault B • :50052"),
        iso_tower(365, 105, 75, 65, 96, "#38bdf8", "#0369a1", "#075985", "#38bdf8", "ai-infer01 (.125)", "T4 • Qdrant :6333"),
        iso_tower(455, 105, 75, 65, 96, "#38bdf8", "#0369a1", "#075985", "#38bdf8", "ai-ollama01 (.228)", "T4 • LiteLLM :4000"),
        # Zone 3: 4x HPE DL380 ESXi Monoliths + Rear UPS/Pro-Max
        iso_tower(625, 145, 82, 68, 110, "#60a5fa", "#1d4ed8", "#1e3a8a", "#60a5fa", "esxi01 (.101 SFF)", "8x 2.5\" SFF • iLO .10"),
        iso_tower(755, 145, 82, 68, 115, "#60a5fa", "#1d4ed8", "#1e3a8a", "#60a5fa", "esxi02 (.102 SFF)", "USW-Pro-Max Rear"),
        iso_tower(625, 265, 82, 68, 120, "#3b82f6", "#1e40af", "#172554", "#38bdf8", "esxi03 (.103 12-LFF)", "96TB Exos + Pro-Max"),
        iso_tower(755, 265, 82, 68, 120, "#3b82f6", "#1e40af", "#172554", "#38bdf8", "esxi04 (.104 12-LFF)", "96TB Exos • Blue UID"),
        # Zone 4: Controller, 64c Ramdisk, Oracles & 23 Compute VMs
        iso_tower(185, 385, 82, 72, 130, "#fbbf24", "#b45309", "#78350f", "#f59e0b", "Controller bd (.164)", "32 Web UIs • PM-B"),
        iso_tower(310, 385, 78, 68, 112, "#34d399", "#047857", "#064e3b", "#10b981", "test3big (.82) 64c", "128G /dev/shm Pytest"),
        iso_tower(425, 385, 74, 65, 95, "#38bdf8", "#0369a1", "#0c4a6e", "#00e5ff", "Oracles .137 & .181", "Dual Chrome CDP :9222"),
        iso_tower(185, 520, 72, 62, 78, "#60a5fa", "#1d4ed8", "#1e3a8a", "#60a5fa", "Builders bd1..bd4", ".51, .210, .211, .212"),
        iso_tower(300, 520, 72, 62, 78, "#34d399", "#047857", "#064e3b", "#10b981", "Verifiers test1..7", "7x Active Test VMs"),
        iso_tower(415, 520, 72, 62, 64, "#94a3b8", "#334155", "#1e293b", "#64748b", "Spares 1..10 (DRS)", "2 Hot • 8 Cold Rule 61"),
    ]

    return f"""
    <div style="width:1920px;height:1034px;background:radial-gradient(circle at 50% 45%,#0d152c 0%,#060913 100%);position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      <!-- Top Isometric Blueprint Overlay -->
      <div style="position:absolute;left:28px;top:20px;background:rgba(10,16,34,0.9);border:1px solid #00e5ff55;border-radius:12px;padding:14px 20px;z-index:5;">
        <div style="color:#00e5ff;font-size:10.5px;font-weight:800;letter-spacing:1.2px;">STYLE #4 • CLOUDCRAFT / SIMCITY 2.5D ISOMETRIC DATA-CENTER ARCHITECTURE</div>
        <div style="color:#f8fafc;font-size:18px;font-weight:900;margin-top:2px;">Boylenet 3D Isometric Infrastructure &amp; Live Swarm Floorplan</div>
        <div style="color:#94a3b8;font-size:11.5px;margin-top:4px;">4 Elevated Isometric Hardware Islands • 27 VMs • 4x Tesla T4 25GbE RoCE • 4x HPE DL380 ESXi • $1,000 Cloud Sky-Deck</div>
      </div>

      <!-- Right Isometric Legend & Telemetry Card -->
      <div style="position:absolute;right:28px;top:20px;width:320px;background:rgba(10,16,34,0.9);border:1px solid #38bdf855;border-radius:12px;padding:14px 18px;z-index:5;font-size:11px;color:#cbd5e1;">
        <div style="color:#f8fafc;font-weight:800;margin-bottom:8px;display:flex;justify-content:space-between;">
          <span>ISOMETRIC ZONE ELEVATIONS</span><span style="color:#10b981;">LIVE 3D SVG</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px;font-family:'JetBrains Mono',monospace;font-size:10px;">
          <div>🟣 <b style="color:#c084fc;">Zone 01:</b> $1,000 Cloud Sky-Deck (Pools A-D)</div>
          <div>🔵 <b style="color:#00e5ff;">Zone 02:</b> 4x1U UniFi + 4x Tesla T4 RoCE</div>
          <div>🔷 <b style="color:#60a5fa;">Zone 03:</b> 4x HPE DL380 ESXi + 328TiB vSAN</div>
          <div>🟢 <b style="color:#10b981;">Zone 04:</b> Controller .164 + 23 Compute VMs</div>
        </div>
      </div>

      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(grid_lines)}
        {''.join(platforms)}
        {''.join(beams)}
        {''.join(towers)}
      </svg>
    </div>
    """


def build_style_05_galaxy() -> str:
    """Style 5: Neural Swarm Galaxy (Radial Orbital Constellation)."""
    cx, cy = 960, 520
    planets = []
    arcs = []

    def add_planet(radius: float, deg: float, name: str, sub: str, col: str, r_size: int = 16, laser_to_center: bool = False) -> tuple[float, float]:
        rad = math.radians(deg)
        px = cx + radius * math.cos(rad)
        py = cy + radius * math.sin(rad)
        if laser_to_center:
            arcs.append(f'<line x1="{cx}" y1="{cy}" x2="{px:.1f}" y2="{py:.1f}" stroke="{col}" stroke-width="1.6" stroke-dasharray="5,4" opacity="0.55"/>')
        w = max(116, len(name) * 6 + 18)
        planets.append(f"""
        <g transform="translate({px:.1f},{py:.1f})">
          <circle cx="0" cy="0" r="{r_size+7}" fill="{col}" opacity="0.14"/>
          <circle cx="0" cy="0" r="{r_size}" fill="#090d1a" stroke="{col}" stroke-width="2.2"/>
          <circle cx="0" cy="0" r="{max(4, r_size//3)}" fill="{col}"/>
          <rect x="{-w/2:.1f}" y="{r_size+5}" width="{w}" height="28" rx="6" fill="#060812" stroke="{col}" stroke-width="1" opacity="0.94"/>
          <text x="0" y="{r_size+17}" text-anchor="middle" fill="#f8fafc" font-family="Inter,sans-serif" font-size="9.5" font-weight="800">{name}</text>
          <text x="0" y="{r_size+28}" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="8">{sub}</text>
        </g>
        """)
        return px, py

    # Orbit 1 (r=148): 4x Tesla T4 GPUs (VLAN 75 25GbE RoCE Diamond)
    r1_pts = []
    r1_specs = [
        (45, "ai-srv01 (.72)", "T4 #1 • 77.6 tok/s", "#00e5ff"),
        (135, "aidev (.83)", "T4 #2 • RPC :50052", "#00e5ff"),
        (225, "ai-infer01 (.125)", "T4 #3 • Qdrant :6333", "#38bdf8"),
        (315, "ai-ollama01 (.228)", "T4 #4 • LiteLLM :4000", "#38bdf8"),
    ]
    for deg, n, s, c in r1_specs:
        r1_pts.append(add_planet(148, deg, n, s, c, 19, True))
    # Connect R1 diamond
    for i in range(4):
        x1, y1 = r1_pts[i]
        x2, y2 = r1_pts[(i + 1) % 4]
        arcs.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#00e5ff" stroke-width="2.5" opacity="0.8"/>')

    # Orbit 2 (r=265): Core Infrastructure, Spine, Oracles & 64c Ramdisk
    r2_specs = [
        (0, "test3big (.82)", "64c • 128G Ramdisk", "#10b981"),
        (60, "BattleStation (.137)", "CDP :9222 + 2080Ti", "#f59e0b"),
        (120, "Bittorrent (.181)", "Secondary CDP :9222", "#f59e0b"),
        (180, "UDM-Pro + 280G", "4x1U UniFi Stack", "#38bdf8"),
        (240, "vCenter vc04 (.70)", "328.4 TiB vSAN", "#10b981"),
        (300, "Rear UPS + Pro-Max", "79.5°F • Etherlight", "#a855f7"),
    ]
    for deg, n, s, c in r2_specs:
        add_planet(265, deg, n, s, c, 15, True)

    # Orbit 3 (r=375): 14 Active Worker VMs + 8 DRS Spares (12 planetary clusters)
    r3_specs = [
        (15, "bd1 (.51)", "Builder VM #1", "#10b981"),
        (45, "bd2 (.210)", "Builder VM #2", "#10b981"),
        (75, "bd3 (.211)", "Builder VM #3", "#10b981"),
        (105, "bd4 (.212)", "Builder VM #4", "#10b981"),
        (135, "test1 & test2", ".81 & .84 Verifiers", "#34d399"),
        (165, "test4 & test5", ".85 & .86 Verifiers", "#34d399"),
        (195, "test6 & test7", ".197 & .249 Verifiers", "#34d399"),
        (225, "fresh149 (.149)", "Clean Room VM", "#38bdf8"),
        (255, "spare1 (.120)", "Hot Spare #1 ON", "#38bdf8"),
        (285, "spare2 (.183)", "Hot Spare #2 ON", "#38bdf8"),
        (315, "spare3..6 (DRS)", "4x Cold Standby", "#64748b"),
        (345, "spare7..10 (DRS)", "4x Cold Standby", "#64748b"),
    ]
    for deg, n, s, c in r3_specs:
        add_planet(375, deg, n, s, c, 12, False)

    # Orbit 4 (r=475): 4x HPE ESXi Hosts + $1,000 Cloud Burst Constellation
    r4_specs = [
        (25, "esxi01 (.101)", "2U SFF • iLO .10", "#3b82f6"),
        (155, "esxi02 (.102)", "2U SFF + Pro-Max", "#3b82f6"),
        (205, "esxi03 (.103)", "2U 12-LFF 96TB", "#3b82f6"),
        (335, "esxi04 (.104)", "2U 12-LFF 96TB", "#3b82f6"),
        (65, "Claude Pool A", "$250 • Opus 5.5", "#c084fc"),
        (90, "Claude Pool B", "$250 • bd-pm-B", "#c084fc"),
        (115, "Claude Pools C/D", "$500 • Sonnet 5.5", "#a855f7"),
        (248, "Codex GPT-6.1-Sol", "OpenAI Verifier", "#10b981"),
        (272, "AGY-Council Swarm", "10 Subagents", "#00e5ff"),
        (296, "Kimi + Hermes-4", "256k Context", "#f59e0b"),
    ]
    for deg, n, s, c in r4_specs:
        px, py = add_planet(472, deg, n, s, c, 14, False)
        # Curved synaptic arc toward center
        arcs.append(f'<path d="M {px:.1f} {py:.1f} Q {cx+120:.1f} {cy-90:.1f} {cx} {cy}" stroke="{c}" stroke-width="1.3" fill="none" opacity="0.35"/>')

    return f"""
    <div style="width:1920px;height:1034px;background:radial-gradient(circle at 50% 50%,#13103a 0%,#060614 55%,#020308 100%);position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      <!-- Corner Astrometric Telemetry Cards -->
      <div style="position:absolute;left:24px;top:20px;width:360px;background:rgba(8,10,24,0.86);border:1px solid #a855f755;border-radius:14px;padding:16px;z-index:5;">
        <div style="color:#c084fc;font-size:10px;font-weight:800;letter-spacing:1.2px;">STYLE #5 • RADIAL ORBITAL CONSTELLATION</div>
        <div style="color:#f8fafc;font-size:18px;font-weight:900;margin:3px 0;">Boylenet Neural Swarm Galaxy</div>
        <div style="color:#94a3b8;font-size:11px;line-height:1.5;">Concentric gravity rings around <b style="color:#fbbf24;">Controller .164 + 280G Spine</b>: Inner Ring = 4x T4 GPUs, Ring 2 = Oracles &amp; Ramdisk, Ring 3 = 22 Worker VMs, Outer Halo = 4x ESXi &amp; $1,000 Cloud Pools.</div>
      </div>

      <div style="position:absolute;right:24px;top:20px;width:330px;background:rgba(8,10,24,0.86);border:1px solid #00e5ff55;border-radius:14px;padding:16px;z-index:5;font-family:'JetBrains Mono',monospace;font-size:10.5px;color:#cbd5e1;line-height:1.7;">
        <div style="color:#00e5ff;font-weight:800;margin-bottom:4px;">ORBITAL TELEMETRY LOCK</div>
        <div>★ Core Star: <span style="color:#fbbf24;">bd (.164) + USW-Pro-Agg 280G</span></div>
        <div>◎ Ring 1 (148px): <span style="color:#00e5ff;">4x Tesla T4 (77.6 tok/s)</span></div>
        <div>◎ Ring 2 (265px): <span style="color:#10b981;">64c Ramdisk + Dual Oracles</span></div>
        <div>◎ Ring 3 (375px): <span style="color:#34d399;">22 Compute &amp; DRS VMs</span></div>
        <div>◎ Ring 4 (472px): <span style="color:#c084fc;">4x ESXi + $1,000 Cloud Halo</span></div>
      </div>

      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <!-- Orbital Rings -->
        <circle cx="{cx}" cy="{cy}" r="148" fill="none" stroke="#00e5ff" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.5"/>
        <circle cx="{cx}" cy="{cy}" r="265" fill="none" stroke="#10b981" stroke-width="1.2" stroke-dasharray="4,4" opacity="0.4"/>
        <circle cx="{cx}" cy="{cy}" r="375" fill="none" stroke="#38bdf8" stroke-width="1.2" opacity="0.3"/>
        <circle cx="{cx}" cy="{cy}" r="472" fill="none" stroke="#a855f7" stroke-width="1.5" stroke-dasharray="10,5" opacity="0.45"/>
        {''.join(arcs)}
        <!-- Central Blazing Sun: Controller .164 + 280G Spine -->
        <circle cx="{cx}" cy="{cy}" r="58" fill="#f59e0b" opacity="0.16"/>
        <circle cx="{cx}" cy="{cy}" r="42" fill="#1e1b4b" stroke="#fbbf24" stroke-width="3"/>
        <circle cx="{cx}" cy="{cy}" r="16" fill="#fbbf24"/>
        <text x="{cx}" y="{cy-5}" text-anchor="middle" fill="#ffffff" font-family="Inter,sans-serif" font-size="11" font-weight="900">BD .164</text>
        <text x="{cx}" y="{cy+9}" text-anchor="middle" fill="#fde68a" font-family="JetBrains Mono,monospace" font-size="8.5" font-weight="700">280G SPINE</text>
        {''.join(planets)}
      </svg>
    </div>
    """


def build_style_06_visionos() -> str:
    """Style 6: Apple VisionOS / Spatial Glass Minimalist (Executive Clean)."""
    def glass_card(x: int, y: int, w: int, h: int, pill: str, pill_col: str, title: str, desc: str, metric_left: str, metric_right: str) -> str:
        return f"""
        <div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:rgba(255,255,255,0.075);backdrop-filter:blur(28px);-webkit-backdrop-filter:blur(28px);border:1px solid rgba(255,255,255,0.22);border-radius:24px;padding:18px 22px;box-sizing:border-box;box-shadow:0 20px 50px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.3);display:flex;flex-direction:column;justify-content:space-between;z-index:3;">
          <div>
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
              <span style="background:{pill_col}28;color:{pill_col};border:1px solid {pill_col}66;padding:3px 10px;border-radius:999px;font-size:10px;font-weight:700;letter-spacing:0.4px;">{pill}</span>
              <span style="width:8px;height:8px;border-radius:50%;background:#34d399;box-shadow:0 0 10px #34d399;"></span>
            </div>
            <div style="color:#ffffff;font-size:15.5px;font-weight:700;letter-spacing:-0.3px;margin-bottom:4px;">{title}</div>
            <div style="color:rgba(255,255,255,0.7);font-size:11.5px;line-height:1.45;">{desc}</div>
          </div>
          <div style="border-top:1px solid rgba(255,255,255,0.12);padding-top:9px;display:flex;justify-content:space-between;font-size:11px;color:rgba(255,255,255,0.9);font-weight:600;">
            <span>{metric_left}</span>
            <span style="color:{pill_col};">{metric_right}</span>
          </div>
        </div>
        """

    cards = [
        # Column 1 (x=55): Cloud Intelligence ($1,000 Credits)
        glass_card(55, 135, 390, 185, "ANTHROPIC CLOUD • POOLS A & B", "#e879f9", "Claude Opus 5.5 Command & PM", "Drives architectural planning (bd-pm-B) and deep code review lenses with zero local CPU load.", "$500 Free Credit ($250×2)", "0% 5h Used • Ready"),
        glass_card(55, 345, 390, 185, "ANTHROPIC CLOUD • POOLS C & D", "#c084fc", "Claude Sonnet 5.5 Parallel Swarm", "High-velocity parallel worker seats with automatic O1740 hot-swap (30 global seat cap).", "$500 Free Credit ($250×2)", "Overage OFF ($0 Risk)"),
        glass_card(55, 555, 390, 185, "OPENAI CODEX & SATELLITE AI", "#34d399", "Codex GPT-6.1-Sol + Kimi + AGY", "Single-turn verifiers, 10 parallel AGY subagents, and 256k-context Kimi code synthesis.", "6 Active AI Harnesses", "100% Quota Healthy"),
        glass_card(55, 765, 390, 185, "DUAL BROWSER ORACLES", "#38bdf8", "BattleStation (.137) & Bittorrent (.181)", "Zero-marginal-cost Chrome 155 CDP bridges for multi-model web consultation and 1080p E2E verification.", "Ryzen 9 + RTX 2080 Ti", "CDP :9222 Online"),
        # Column 2 (x=545): Swarm Command & Compute VMs
        glass_card(545, 135, 390, 245, "CENTRAL COMMAND NEXUS • .164", "#fbbf24", "Boylenet Controller (bd)", "Hosts 32+ microservices, Master Traefik ingress (32 DNS shortlinks), Dashy portal (:4080), and 14 new AI Command Studios (:4086–:4099).", "15 Live Swarm Sessions", "83/83 Services UP"),
        glass_card(545, 410, 390, 245, "ZERO-DISK-IO CI ENGINE • .82", "#34d399", "64-vCPU Ramdisk Turbo (test3big)", "Runs massive pytest-xdist verification shards entirely inside 128 GB /dev/shm memory plus cluster-wide RAG indexing.", "64 vCPUs • 128 GB RAM", "0.4s Shard Latency"),
        glass_card(545, 685, 390, 265, "ELASTIC WORKER FLEET • 22 VMS", "#60a5fa", "14 Active Workers + 8 Smart Spares", "Builders bd1..4 (.51, .210..212) and verifiers test1..7 + fresh149 + spare1..2 run isolated worktrees; spare3..10 sleep via vSphere DRS to save power.", "27 Total Cluster VMs", "656 vCPUs • 1.73 TiB"),
        # Column 3 (x=1035): Local 4x Tesla T4 Supercomputer
        glass_card(1035, 135, 390, 245, "AI VAULT A • 10.0.70.72", "#22d3ee", "Primary Tensor Engine (ai-srv01)", "52-core Skylake AVX-512 with 320 GB RAM, Tesla T4 GPU, and 5 TB Model Vault A serving DeepSeek-V3-0324-671B and Kimi-K2.5-1T.", "VLAN 75 25GbE RoCE", "77.62 tokens/sec"),
        glass_card(1035, 410, 390, 245, "AI DEV VAULT B • 10.0.70.83", "#22d3ee", "Distributed Tensor Partner (aidev)", "52-core Skylake AVX-512 with 386 GB RAM, Tesla T4 GPU, and 5 TB Vault B linked to .72 via 25GbE SFP28 RDMA RPC (:50052).", "MiMo-1024B & GLM-5.3", "32.5W • 74°C Nominal"),
        glass_card(1035, 685, 390, 265, "VECTOR RAG & AI GATEWAY • .125 / .228", "#38bdf8", "Qdrant Vector DB & LiteLLM Router", "Node .125 (T4 + 280G RAM) powers Qdrant (:6333) & Qwen2.5-32B; Node .228 (T4 + 280G RAM) runs LiteLLM (:4000), Langfuse (:3000) & 17 Ollama models.", "4× Tesla T4 (64GB VRAM)", "100% Local Privacy"),
        # Column 4 (x=1505): Physical Rack & vSAN Fabric
        glass_card(1505, 135, 360, 245, "4×1U UNIFI STACK • 280G SPINE", "#38bdf8", "UDM-Pro + Pro-Agg + Pro-Max", "Top 4U brushed-silver UniFi stack (UDM-Pro, USW-Agg, USW-Pro-Agg 280G, USW-24-PoE) + rear USW-Pro-Max & Rack UPS at 79.5°F.", "28× 10G + 4× 25G SFP28", "0.18ms Fabric RTT"),
        glass_card(1505, 410, 360, 245, "4× 2U HPE PROLIANT DL380", "#818cf8", "ESXi 01..04 Hypervisor Cluster", "Two 2U SFF 2.5\" SmartCarrier hosts (esxi01–02) + two 2U 12-bay LFF 3.5\" hosts (esxi03–04) managed by vCenter vc04 (.70) & HPE iLO4.", "1,180W Total Rack Draw", "4/4 Hosts Healthy"),
        glass_card(1505, 685, 360, 265, "ALL-FLASH & EXOS VSAN • VLAN 60", "#34d399", "328.4 TiB Distributed Storage", "11 vSAN Disk Groups across 75 drives (NVMe/SAS Flash Tier-1 + 12× 24TB Seagate Exos Tier-0) with 192.7 TiB free capacity.", "135.7 / 328.4 TiB Used", "41.3% Utilization"),
    ]

    return f"""
    <div style="width:1920px;height:1034px;background:#080716;position:relative;overflow:hidden;font-family:'Inter',-apple-system,sans-serif;">
      <!-- Rich Aurora Spatial Mesh Background Blobs -->
      <div style="position:absolute;left:120px;top:80px;width:650px;height:650px;border-radius:50%;background:radial-gradient(circle,rgba(168,85,247,0.32) 0%,transparent 70%);filter:blur(45px);"></div>
      <div style="position:absolute;left:680px;top:180px;width:720px;height:720px;border-radius:50%;background:radial-gradient(circle,rgba(6,182,212,0.28) 0%,transparent 70%);filter:blur(50px);"></div>
      <div style="position:absolute;right:80px;bottom:60px;width:650px;height:650px;border-radius:50%;background:radial-gradient(circle,rgba(16,185,129,0.26) 0%,transparent 70%);filter:blur(45px);"></div>

      <!-- Top VisionOS Spatial Glass Pill Bar -->
      <div style="position:absolute;left:55px;right:55px;top:24px;height:78px;background:rgba(255,255,255,0.08);backdrop-filter:blur(30px);border:1px solid rgba(255,255,255,0.25);border-radius:999px;display:flex;align-items:center;justify-content:space-between;padding:0 34px;z-index:4;box-shadow:0 16px 40px rgba(0,0,0,0.3);">
        <div>
          <div style="color:rgba(255,255,255,0.65);font-size:11px;font-weight:700;letter-spacing:1px;">STYLE #6 • APPLE VISIONOS SPATIAL GLASS EXECUTIVE VIEW</div>
          <div style="color:#ffffff;font-size:21px;font-weight:800;letter-spacing:-0.4px;">Boylenet Autonomous AI Cloud &amp; Supercomputing Fabric</div>
        </div>
        <div style="display:flex;gap:14px;">
          <div style="background:rgba(255,255,255,0.09);border:1px solid rgba(255,255,255,0.2);border-radius:999px;padding:8px 18px;color:#fff;font-size:12px;font-weight:700;">✨ $1,000 Free Cloud Credits</div>
          <div style="background:rgba(34,211,238,0.15);border:1px solid rgba(34,211,238,0.4);border-radius:999px;padding:8px 18px;color:#67e8f9;font-size:12px;font-weight:700;">⚡ 77.6 tok/s Local 4×T4</div>
          <div style="background:rgba(52,211,153,0.15);border:1px solid rgba(52,211,153,0.4);border-radius:999px;padding:8px 18px;color:#6ee7b7;font-size:12px;font-weight:700;">🟢 All 27 VMs &amp; 83 Services Healthy</div>
        </div>
      </div>

      <!-- Silky Luminous Connection Ribbons Behind Glass Cards -->
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;z-index:2;">
        <defs>
          <linearGradient id="vis-rib-1" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#e879f9" stop-opacity="0.55"/>
            <stop offset="50%" stop-color="#22d3ee" stop-opacity="0.55"/>
            <stop offset="100%" stop-color="#34d399" stop-opacity="0.55"/>
          </linearGradient>
        </defs>
        <path d="M 445 225 C 495 225, 495 255, 545 255" stroke="url(#vis-rib-1)" stroke-width="6" fill="none"/>
        <path d="M 445 435 C 495 435, 495 530, 545 530" stroke="url(#vis-rib-1)" stroke-width="6" fill="none"/>
        <path d="M 445 645 C 495 645, 495 815, 545 815" stroke="url(#vis-rib-1)" stroke-width="6" fill="none"/>
        <path d="M 935 255 C 985 255, 985 255, 1035 255" stroke="url(#vis-rib-1)" stroke-width="8" fill="none"/>
        <path d="M 935 530 C 985 530, 985 530, 1035 530" stroke="url(#vis-rib-1)" stroke-width="8" fill="none"/>
        <path d="M 935 815 C 985 815, 985 815, 1035 815" stroke="url(#vis-rib-1)" stroke-width="8" fill="none"/>
        <path d="M 1425 255 C 1465 255, 1465 255, 1505 255" stroke="url(#vis-rib-1)" stroke-width="8" fill="none"/>
        <path d="M 1425 530 C 1465 530, 1465 530, 1505 530" stroke="url(#vis-rib-1)" stroke-width="8" fill="none"/>
        <path d="M 1425 815 C 1465 815, 1465 815, 1505 815" stroke="url(#vis-rib-1)" stroke-width="8" fill="none"/>
      </svg>

      {''.join(cards)}
    </div>
    """


def build_style_07_sankey() -> str:
    """Style 7: Live Sankey / Alluvial Token & Compute River."""
    def sankey_ribbon(x1: int, y1: int, x2: int, y2: int, thickness: int, col1: str, col2: str, grad_id: str, label: str = "") -> str:
        mx = (x1 + x2) // 2
        my = (y1 + y2) // 2
        lbl = ""
        if label:
            lbl = f"""
            <rect x="{mx-68}" y="{my-10}" width="136" height="20" rx="10" fill="#090d16" stroke="{col1}" stroke-width="1.2" opacity="0.92"/>
            <text x="{mx}" y="{my+3}" text-anchor="middle" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">{label}</text>
            """
        return f"""
        <defs>
          <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="{col1}" stop-opacity="0.48"/>
            <stop offset="100%" stop-color="{col2}" stop-opacity="0.48"/>
          </linearGradient>
        </defs>
        <path d="M {x1} {y1} C {x1+155} {y1}, {x2-155} {y2}, {x2} {y2}" stroke="url(#{grad_id})" stroke-width="{thickness}" fill="none"/>
        <path d="M {x1} {y1} C {x1+155} {y1}, {x2-155} {y2}, {x2} {y2}" stroke="{col1}" stroke-width="1.5" stroke-dasharray="6,4" fill="none" opacity="0.8"/>
        {lbl}
        """

    def sankey_bar(x: int, y: int, h: int, title: str, sub: str, val: str, col: str, w: int = 230) -> str:
        return f"""
        <g transform="translate({x},{y})">
          <rect width="{w}" height="{h}" rx="10" fill="#111726" stroke="{col}" stroke-width="1.8"/>
          <rect width="10" height="{h}" rx="5" fill="{col}"/>
          <text x="20" y="{h//2 - 8}" fill="#f8fafc" font-family="Inter,sans-serif" font-size="12.5" font-weight="800">{title}</text>
          <text x="20" y="{h//2 + 8}" fill="#94a3b8" font-family="Inter,sans-serif" font-size="10">{sub}</text>
          <text x="20" y="{h//2 + 23}" fill="{col}" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="700">{val}</text>
        </g>
        """

    # 4 Columns of Sankey Nodes
    c1 = [
        sankey_bar(45, 95, 118, "Claude Pool A ($250)", "Opus 5.5 + Sonnet 5.5", "0% 5h Used • Exp Nov 5", "#c084fc"),
        sankey_bar(45, 235, 118, "Claude Pool B ($250 PM)", "Opus 5.5 + Fable 5.1 PM", "0% 5h Used • Command", "#a855f7"),
        sankey_bar(45, 375, 128, "Claude Pools C & D ($500)", "Parallel Swarm Workers", "$250×2 • Overage OFF", "#8b5cf6"),
        sankey_bar(45, 525, 118, "OpenAI Codex Cloud", "gpt-6.1-sol & gpt-6-astra", "0% Window • Verifiers", "#10b981"),
        sankey_bar(45, 665, 118, "AGY-Council & Kimi Code", "10 Subagents • 256k Ctx", "Zero-Latency Dispatch", "#00e5ff"),
        sankey_bar(45, 805, 118, "Local 4×T4 Direct Stream", "DeepSeek-671B + MiMo-1T", "77.6 tok/s • $0 Cost", "#f59e0b"),
    ]
    c2 = [
        sankey_bar(540, 105, 140, "Command Squad & PM", "bd-pm-B + Integrator + Audit", "Opus 5.5 High-Context", "#c084fc"),
        sankey_bar(540, 270, 155, "Heavy-Lifter Builders", "30 Global Seat Cap (O1740)", "Lenses ➔ Fixers ➔ Builders", "#a855f7"),
        sankey_bar(540, 450, 145, "Ramdisk CI & AST Verifiers", "pytest-xdist + ratf.ctx_slice", "64-vCPU Zero-IO Shards", "#10b981"),
        sankey_bar(540, 620, 140, "Browser Oracle Fanout", "Gemini + ChatGPT + Claude", "CDP :9222 Visual E2E", "#38bdf8"),
        sankey_bar(540, 785, 140, "RoCE Tensor & Vector RAG", "ik_llama.cpp + Qdrant :6333", "77.62 tok/s + Hybrid Search", "#00e5ff"),
    ]
    c3 = [
        sankey_bar(1055, 95, 130, "Controller Nexus (.164)", "32 Web UIs • Traefik • Dashy", "CPU 25% • RAM 48%", "#f59e0b"),
        sankey_bar(1055, 245, 145, "AI Vault A & B (.72 + .83)", "2× Tesla T4 • 10TB Dual Vault", "VLAN 75 25GbE RoCE :50052", "#00e5ff"),
        sankey_bar(1055, 410, 130, "Vector & Gate (.125 + .228)", "2× Tesla T4 • 560G RAM Total", "Qdrant :6333 + LiteLLM :4000", "#38bdf8"),
        sankey_bar(1055, 560, 130, "CI Ramdisk test3big (.82)", "64-vCPU • 128G /dev/shm", "CPU 31% • Pytest Turbo", "#10b981"),
        sankey_bar(1055, 710, 110, "Oracles (.137 & .181)", "Ryzen 9 + 2080Ti + Win CDP", "1920×1080 E2E Verified", "#a855f7"),
        sankey_bar(1055, 840, 95, "22 Worker & Spare VMs", "bd1..4, test1..7, spare1..10", "14 Active • 8 DRS Standby", "#60a5fa"),
    ]
    c4 = [
        sankey_bar(1570, 105, 185, "4× NVIDIA Tesla T4 GPUs", "64 GB GDDR6 Total VRAM", "30–32W • 60–74°C • 77.6 tok/s", "#00e5ff", 295),
        sankey_bar(1570, 320, 185, "280G UniFi Spine + Pro-Max", "UDM-Pro + Pro-Agg + Pro-Max", "4× 25G SFP28 RoCE + 28× 10G", "#38bdf8", 295),
        sankey_bar(1570, 535, 185, "4× 2U HPE DL380 ESXi Hosts", "656 vCPUs • 1.73 TiB DDR4", "2× SFF + 2× 12-Bay LFF • 79.5°F", "#3b82f6", 295),
        sankey_bar(1570, 750, 175, "328.4 TiB All-Flash/Exos vSAN", "11 Disk Groups • 75 Drives", "135.7 TiB Used (41.3%) • UPS OK", "#10b981", 295),
    ]

    ribbons = [
        # Col 1 -> Col 2
        sankey_ribbon(275, 154, 540, 175, 38, "#c084fc", "#c084fc", "g1", "$250 Pool A"),
        sankey_ribbon(275, 294, 540, 175, 42, "#a855f7", "#c084fc", "g2", "$250 PM Opus"),
        sankey_ribbon(275, 439, 540, 347, 54, "#8b5cf6", "#a855f7", "g3", "$500 Pools C/D"),
        sankey_ribbon(275, 584, 540, 522, 40, "#10b981", "#10b981", "g4", "GPT-6.1-Sol"),
        sankey_ribbon(275, 724, 540, 690, 42, "#00e5ff", "#38bdf8", "g5", "10 AGY Seats"),
        sankey_ribbon(275, 864, 540, 855, 48, "#f59e0b", "#00e5ff", "g6", "77.6 tok/s Local"),
        # Col 2 -> Col 3
        sankey_ribbon(770, 175, 1055, 160, 44, "#c084fc", "#f59e0b", "g7", "PM Orchestration"),
        sankey_ribbon(770, 347, 1055, 317, 46, "#a855f7", "#00e5ff", "g8", "DeepSeek/MiMo"),
        sankey_ribbon(770, 347, 1055, 885, 34, "#a855f7", "#60a5fa", "g9", "bd1..4 Worktrees"),
        sankey_ribbon(770, 522, 1055, 625, 48, "#10b981", "#10b981", "g10", "64c /dev/shm CI"),
        sankey_ribbon(770, 690, 1055, 765, 36, "#38bdf8", "#a855f7", "g11", "CDP :9222 E2E"),
        sankey_ribbon(770, 855, 1055, 317, 52, "#00e5ff", "#00e5ff", "g12", "VLAN 75 RoCE"),
        sankey_ribbon(770, 855, 1055, 475, 36, "#00e5ff", "#38bdf8", "g13", "Qdrant + LiteLLM"),
        # Col 3 -> Col 4
        sankey_ribbon(1285, 160, 1570, 412, 34, "#f59e0b", "#38bdf8", "g14", "Traefik 32 DNS"),
        sankey_ribbon(1285, 317, 1570, 197, 58, "#00e5ff", "#00e5ff", "g15", "25GbE Tensor"),
        sankey_ribbon(1285, 475, 1570, 197, 40, "#38bdf8", "#00e5ff", "g16", "T4 VRAM Pool"),
        sankey_ribbon(1285, 625, 1570, 627, 46, "#10b981", "#3b82f6", "g17", "656 vCPU Compute"),
        sankey_ribbon(1285, 765, 1570, 412, 30, "#a855f7", "#38bdf8", "g18", "VLAN 10/70"),
        sankey_ribbon(1285, 885, 1570, 837, 48, "#60a5fa", "#10b981", "g19", "135.7 TiB vSAN"),
    ]

    return f"""
    <div style="width:1920px;height:1034px;background:#090d16;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      <div style="position:absolute;left:45px;right:55px;top:18px;display:flex;justify-content:space-between;align-items:center;z-index:5;">
        <div>
          <span style="color:#00e5ff;font-size:10.5px;font-weight:800;letter-spacing:1.2px;">STYLE #7 • LIVE SANKEY / ALLUVIAL TOKEN, COMPUTE &amp; STORAGE RIVER</span>
          <div style="color:#f8fafc;font-size:19px;font-weight:900;">Boylenet End-to-End Token Bandwidth, Agent Seat &amp; Silicon Flow</div>
        </div>
        <div style="display:flex;gap:18px;font-family:'JetBrains Mono',monospace;font-size:11px;color:#cbd5e1;">
          <span>STAGE 1: <b style="color:#c084fc;">$1,000 Cloud + Local</b></span>
          <span>➔</span>
          <span>STAGE 2: <b style="color:#a855f7;">15 Swarm Roles</b></span>
          <span>➔</span>
          <span>STAGE 3: <b style="color:#00e5ff;">27 Cluster VMs</b></span>
          <span>➔</span>
          <span>STAGE 4: <b style="color:#10b981;">4×T4 + 4×ESXi + 328TiB vSAN</b></span>
        </div>
      </div>

      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(ribbons)}
        {''.join(c1)}
        {''.join(c2)}
        {''.join(c3)}
        {''.join(c4)}
      </svg>
    </div>
    """


def build_style_08_hexhive() -> str:
    """Style 8: Hexagonal Honeycomb Swarm Hive."""
    def hex_pts(cx: float, cy: float, r: float) -> str:
        pts = []
        for i in range(6):
            ang = math.radians(60 * i - 30)
            pts.append(f"{cx + r * math.cos(ang):.1f},{cy + r * math.sin(ang):.1f}")
        return " ".join(pts)

    def hex_cell(cx: float, cy: float, r: float, title: str, sub: str, metric: str, stroke: str, fill: str = "#0e1526") -> str:
        outer = hex_pts(cx, cy, r)
        inner = hex_pts(cx, cy, r - 6)
        return f"""
        <g>
          <polygon points="{outer}" fill="{fill}" stroke="{stroke}" stroke-width="2.2"/>
          <polygon points="{inner}" fill="none" stroke="{stroke}" stroke-width="0.8" stroke-dasharray="4,3" opacity="0.65"/>
          <text x="{cx:.1f}" y="{cy-9:.1f}" text-anchor="middle" fill="#f8fafc" font-family="Inter,sans-serif" font-size="10.5" font-weight="800">{title}</text>
          <text x="{cx:.1f}" y="{cy+5:.1f}" text-anchor="middle" fill="#94a3b8" font-family="Inter,sans-serif" font-size="8.5">{sub}</text>
          <text x="{cx:.1f}" y="{cy+19:.1f}" text-anchor="middle" fill="{stroke}" font-family="JetBrains Mono,monospace" font-size="8.5" font-weight="700">{metric}</text>
        </g>
        """

    # Axial hex offsets around a cluster center
    def cluster_hexes(ox: float, oy: float, r: float, items: List[tuple[int, int, str, str, str, str, str]]) -> tuple[List[str], List[tuple[float, float]]]:
        dx_q = math.sqrt(3) * r * 1.05
        dx_r = math.sqrt(3) / 2.0 * r * 1.05
        dy_r = 1.5 * r * 1.05
        cells = []
        coords = []
        for q, rv, t, s, m, col, bg in items:
            hx = ox + q * dx_q + rv * dx_r
            hy = oy + rv * dy_r
            cells.append(hex_cell(hx, hy, r, t, s, m, col, bg))
            coords.append((hx, hy))
        return cells, coords

    all_cells = []
    bridges = []

    # Cluster 1 (Center): Command Core, Spine & Oracles (Gold/Amber)
    c_core, pts_core = cluster_hexes(940, 495, 58, [
        (0, 0, "bd (.164)", "Controller Nexus", "32 UIs • PM-B", "#fbbf24", "#231907"),
        (1, 0, "USW-Agg 280G", "28x10G + 4x25G", "VLAN 75/60/70", "#38bdf8", "#082032"),
        (0, 1, "BattleSt .137", "Primary Oracle", "CDP :9222 2080Ti", "#fbbf24", "#1f1909"),
        (-1, 1, "Bittorrent .181", "Oracle #2 Bridge", "CDP :9222 Win", "#fbbf24", "#1f1909"),
        (-1, 0, "UDM-Pro (.1)", "32 Static DNS", "Traefik :80 OK", "#38bdf8", "#082032"),
        (0, -1, "test3big (.82)", "64-vCPU Ramdisk", "128G /dev/shm", "#10b981", "#06241c"),
        (1, -1, "Sentinel :4099", "83-Svc Healer", "100% GREEN", "#10b981", "#06241c"),
    ])
    all_cells.extend(c_core)

    # Cluster 2 (Top-Left): $1,000 Cloud Pools & AI Harnesses (Violet)
    c_cloud, pts_cloud = cluster_hexes(320, 275, 56, [
        (0, 0, "Pool B ($250)", "bd-pm-B Opus 5.5", "0% 5h Used", "#c084fc", "#1f1037"),
        (1, 0, "Pool A ($250)", "claude-A Opus", "Exp Nov 5", "#c084fc", "#1f1037"),
        (0, 1, "Pool C ($250)", "Sonnet 5.5 Swarm", "5% 5h Used", "#a855f7", "#1a0e2e"),
        (-1, 1, "Pool D ($250)", "Sonnet 5.5 Swarm", "Overage OFF", "#a855f7", "#1a0e2e"),
        (-1, 0, "Codex Cloud", "GPT-6.1-Sol", "Verifier OK", "#10b981", "#08261e"),
        (0, -1, "AGY-Council", "10 Subagents", "Zero-Latency", "#00e5ff", "#07222c"),
        (1, -1, "Kimi + Hermes", "256k Coding", "State OK", "#f59e0b", "#231907"),
    ])
    all_cells.extend(c_cloud)

    # Cluster 3 (Bottom-Left): 4x Tesla T4 GPU & 10TB Dual Vault + 4x ESXi (Cyan & Magma)
    c_hw, pts_hw = cluster_hexes(360, 745, 56, [
        (0, 0, "ai-srv01 (.72)", "Tesla T4 • 320G", "77.6 tok/s A", "#00e5ff", "#052630"),
        (1, 0, "aidev (.83)", "Tesla T4 • 386G", "RoCE :50052 B", "#00e5ff", "#052630"),
        (0, -1, "ai-infer01", "Tesla T4 • .125", "Qdrant :6333", "#00e5ff", "#052630"),
        (1, -1, "ai-ollama01", "Tesla T4 • .228", "LiteLLM :4000", "#00e5ff", "#052630"),
        (-1, 0, "esxi01 & 02", "2× 2U SFF DL380", "iLO .10/.20 OK", "#f97316", "#271206"),
        (-1, 1, "esxi03 & 04", "2× 2U 12-LFF", "96TB Exos ×3", "#f97316", "#271206"),
        (0, 1, "vSAN 328TiB", "11 Disk Groups", "75 Disks + UPS", "#10b981", "#06241c"),
        (1, 1, "USW-Pro-Max", "Rear ESXi 2&3", "Etherlighting", "#38bdf8", "#082032"),
    ])
    all_cells.extend(c_hw)

    # Cluster 4 (Right): 22 Fleet Worker & DRS Spare VMs Honeycomb (Emerald)
    c_vms, pts_vms = cluster_hexes(1510, 510, 52, [
        (0, -2, "bd1 (.51)", "Builder #1", "Active WT", "#10b981", "#07231c"),
        (1, -2, "bd2 (.210)", "Builder #2", "Active WT", "#10b981", "#07231c"),
        (-1, -1, "bd3 (.211)", "Builder #3", "Active WT", "#10b981", "#07231c"),
        (0, -1, "bd4 (.212)", "Builder #4", "Active WT", "#10b981", "#07231c"),
        (1, -1, "test1 (.81)", "Verifier #1", "Pytest OK", "#34d399", "#07231c"),
        (-1, 0, "test2 (.84)", "Verifier #2", "Pytest OK", "#34d399", "#07231c"),
        (0, 0, "test4 (.85)", "Verifier #4", "Pytest OK", "#34d399", "#07231c"),
        (1, 0, "test5 (.86)", "Verifier #5", "Pytest OK", "#34d399", "#07231c"),
        (-1, 1, "test6 (.197)", "Verifier #6", "Pytest OK", "#34d399", "#07231c"),
        (0, 1, "test7 (.249)", "Verifier #7", "Pytest OK", "#34d399", "#07231c"),
        (1, 1, "fresh149", "10.0.70.149", "Clean Sandbox", "#38bdf8", "#082032"),
        (-1, 2, "spare1 & 2", ".120 & .183", "2× Hot ON", "#38bdf8", "#082032"),
        (0, 2, "spare3..6", "vSphere DRS", "Rule 61 Cold", "#64748b", "#131824"),
        (1, 2, "spare7..10", "vSphere DRS", "Rule 61 Cold", "#64748b", "#131824"),
    ])
    all_cells.extend(c_vms)

    # Energy bridges between hive clusters
    bridges.append('<line x1="430" y1="295" x2="830" y2="475" stroke="#c084fc" stroke-width="4" stroke-dasharray="10,5" opacity="0.7"/>')
    bridges.append('<line x1="470" y1="715" x2="830" y2="525" stroke="#00e5ff" stroke-width="5" opacity="0.8"/>')
    bridges.append('<line x1="1060" y1="495" x2="1395" y2="495" stroke="#10b981" stroke-width="4.5" stroke-dasharray="8,4" opacity="0.75"/>')
    bridges.append('<line x1="360" y1="385" x2="360" y2="635" stroke="#a855f7" stroke-width="3" stroke-dasharray="6,4" opacity="0.55"/>')

    return f"""
    <div style="width:1920px;height:1034px;background:#060911;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      <div style="position:absolute;left:36px;top:20px;z-index:5;">
        <div style="color:#fbbf24;font-size:10.5px;font-weight:800;letter-spacing:1.2px;">STYLE #8 • HEXAGONAL HONEYCOMB SWARM HIVE MATRIX</div>
        <div style="color:#f8fafc;font-size:20px;font-weight:900;">Boylenet Synaptic Hex-Hive Topology (4 Interlocking Cellular Clusters)</div>
      </div>

      <!-- Cluster Legend Badges -->
      <div style="position:absolute;right:36px;top:22px;display:flex;gap:12px;z-index:5;font-family:'JetBrains Mono',monospace;font-size:11px;">
        <span style="background:#1f1037;border:1px solid #c084fc;color:#e9d5ff;padding:6px 12px;border-radius:8px;">🟣 $1,000 Cloud Hive</span>
        <span style="background:#052630;border:1px solid #00e5ff;color:#67e8f9;padding:6px 12px;border-radius:8px;">🔵 4× T4 RoCE &amp; ESXi Hive</span>
        <span style="background:#231907;border:1px solid #fbbf24;color:#fde68a;padding:6px 12px;border-radius:8px;">🟡 Command &amp; 280G Core</span>
        <span style="background:#07231c;border:1px solid #10b981;color:#6ee7b7;padding:6px 12px;border-radius:8px;">🟢 22-VM Worker Honeycomb</span>
      </div>

      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(bridges)}
        {''.join(all_cells)}
      </svg>
    </div>
    """


def build_style_09_physical_rack() -> str:
    """
    Style 9: Photorealistic Digital Twin of Operator's ACTUAL Physical Rack
    (Front Elevation matching uploaded photo + Rear Elevation with Top UPS & USW-Pro-Max behind ESXi 2&3 + Live 27-VM Topology).
    """
    # Helper for 1U Brushed Silver UniFi Chassis with glowing blue left LCM touchscreen
    def unifi_1u_svg(y: int, u_label: str, model_text: str, detail_svg: str) -> str:
        return f"""
        <g transform="translate(42,{y})">
          <!-- U-Number on Rail -->
          <text x="-12" y="27" text-anchor="end" fill="#64748b" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="700">{u_label}</text>
          <!-- Brushed Aluminum Silver 1U Faceplate (520px wide, 42px high) -->
          <rect x="0" y="0" width="520" height="42" rx="3" fill="url(#brushed-silver)" stroke="#94a3b8" stroke-width="1.2"/>
          <!-- Rack Ears & Screws -->
          <rect x="0" y="0" width="18" height="42" rx="2" fill="#cbd5e1" stroke="#64748b" stroke-width="0.8"/>
          <rect x="502" y="0" width="18" height="42" rx="2" fill="#cbd5e1" stroke="#64748b" stroke-width="0.8"/>
          <circle cx="8" cy="8" r="3" fill="#334155"/><circle cx="8" cy="34" r="3" fill="#334155"/>
          <circle cx="512" cy="8" r="3" fill="#334155"/><circle cx="512" cy="34" r="3" fill="#334155"/>
          <!-- Signature Glowing Blue Square LCM Touchscreen on Left -->
          <rect x="24" y="6" width="26" height="26" rx="3" fill="#04102c" stroke="#3b82f6" stroke-width="1.2"/>
          <circle cx="37" cy="19" r="9" fill="#2563eb" opacity="0.65"/>
          <circle cx="34" cy="16" r="1.5" fill="#93c5fd"/><circle cx="40" cy="15" r="1.2" fill="#60a5fa"/>
          <circle cx="37" cy="22" r="1.5" fill="#e0f2fe"/><circle cx="42" cy="21" r="1" fill="#93c5fd"/>
          <text x="24" y="39" fill="#334155" font-family="Inter,sans-serif" font-size="6.5" font-weight="800">{model_text}</text>
          {detail_svg}
        </g>
        """

    # U1 (Top): UDM-Pro (HDD bay in center + 8x RJ45 + 2x SFP+ on right)
    u1_details = """
      <!-- Center 3.5" HDD Caddy Bay -->
      <rect x="195" y="7" width="110" height="28" rx="2" fill="#d8dee9" stroke="#64748b" stroke-width="1"/>
      <line x1="300" y1="12" x2="300" y2="30" stroke="#38bdf8" stroke-width="1.5"/>
      <!-- 8-Port RJ45 Block (2x4) -->
      <rect x="335" y="7" width="84" height="28" rx="2" fill="#1e293b" stroke="#475569"/>
      <g fill="#0f172a" stroke="#64748b" stroke-width="0.6">
        <rect x="339" y="9" width="16" height="10"/><rect x="359" y="9" width="16" height="10"/><rect x="379" y="9" width="16" height="10"/><rect x="399" y="9" width="16" height="10"/>
        <rect x="339" y="22" width="16" height="10"/><rect x="359" y="22" width="16" height="10"/><rect x="379" y="22" width="16" height="10"/><rect x="399" y="22" width="16" height="10"/>
      </g>
      <!-- White/Blue Patch Boots in RJ45 + 2x SFP+ Ports on Right -->
      <rect x="361" y="10" width="12" height="8" rx="1" fill="#f8fafc"/><rect x="381" y="23" width="12" height="8" rx="1" fill="#3b82f6"/>
      <rect x="428" y="7" width="38" height="28" rx="2" fill="#1e293b" stroke="#475569"/>
      <rect x="432" y="10" width="13" height="10" fill="#38bdf8"/><rect x="449" y="22" width="13" height="10" fill="#00e5ff"/>
      <text x="64" y="24" fill="#1e293b" font-family="Inter,sans-serif" font-size="10.5" font-weight="800">UDM-Pro (.70.1) • 32 Static DNS</text>
    """

    # U2 (2nd): USW-Aggregation (8-Port 10G SFP+ on right with Aqua OM3/OM4 fibers)
    u2_details = """
      <text x="64" y="24" fill="#1e293b" font-family="Inter,sans-serif" font-size="10.5" font-weight="800">USW-Aggregation (8× 10G SFP+ Optical)</text>
      <rect x="370" y="7" width="112" height="28" rx="2" fill="#1e293b" stroke="#475569"/>
      <circle cx="382" cy="14" r="3.5" fill="#00e5ff"/><circle cx="404" cy="14" r="3.5" fill="#00e5ff"/><circle cx="426" cy="14" r="3.5" fill="#00e5ff"/><circle cx="448" cy="14" r="3.5" fill="#10b981"/>
      <circle cx="382" cy="28" r="3.5" fill="#00e5ff"/><circle cx="404" cy="28" r="3.5" fill="#00e5ff"/><circle cx="426" cy="28" r="3.5" fill="#facc15"/><circle cx="448" cy="28" r="3.5" fill="#00e5ff"/>
    """

    # U3 (3rd): USW-Pro-Aggregation (28x 10G SFP+ + 4x 25G SFP28 = 32 Ports across center/right)
    u3_ports = []
    for p in range(14):
        px = 198 + p * 16
        col = "#00e5ff" if p % 2 == 0 else "#f8fafc"
        u3_ports.append(f'<rect x="{px}" y="9" width="12" height="10" rx="1" fill="#0f172a" stroke="#475569" stroke-width="0.6"/><circle cx="{px+6}" cy="14" r="2.2" fill="{col}"/>')
        u3_ports.append(f'<rect x="{px}" y="22" width="12" height="10" rx="1" fill="#0f172a" stroke="#475569" stroke-width="0.6"/><circle cx="{px+6}" cy="27" r="2.2" fill="#00e5ff"/>')
    # 4x 25G SFP28 ports on far right (highlighted cyan)
    for p in range(2):
        px = 432 + p * 22
        u3_ports.append(f'<rect x="{px}" y="8" width="17" height="11" rx="1.5" fill="#042f2e" stroke="#00e5ff" stroke-width="1.2"/><circle cx="{px+8.5}" cy="13.5" r="3" fill="#00e5ff"/>')
        u3_ports.append(f'<rect x="{px}" y="22" width="17" height="11" rx="1.5" fill="#042f2e" stroke="#00e5ff" stroke-width="1.2"/><circle cx="{px+8.5}" cy="27.5" r="3" fill="#00e5ff"/>')
    u3_details = f"""
      <text x="64" y="20" fill="#0f172a" font-family="Inter,sans-serif" font-size="9.5" font-weight="900">USW-Pro-Agg 280G</text>
      <text x="64" y="31" fill="#0369a1" font-family="JetBrains Mono,monospace" font-size="8" font-weight="700">28×10G + 4×25G RoCE</text>
      {''.join(u3_ports)}
    """

    # U4 (4th): USW-24-PoE (Bundle of Blue Cat6 Patch Cables in Center + SFP on Right)
    u4_ports = []
    for p in range(12):
        px = 235 + p * 15
        is_blue = 0 <= p <= 7
        fill_c = "#2563eb" if is_blue else "#0f172a"
        u4_ports.append(f'<rect x="{px}" y="9" width="12" height="10" rx="1" fill="{fill_c}" stroke="#475569" stroke-width="0.6"/>')
        u4_ports.append(f'<rect x="{px}" y="22" width="12" height="10" rx="1" fill="{fill_c}" stroke="#475569" stroke-width="0.6"/>')
    u4_details = f"""
      <text x="64" y="24" fill="#1e293b" font-family="Inter,sans-serif" font-size="10" font-weight="800">USW-24-PoE (Blue Cat6 Bundle)</text>
      {''.join(u4_ports)}
      <rect x="435" y="9" width="36" height="24" rx="2" fill="#0f172a" stroke="#475569"/>
    """

    # Helper for HPE ProLiant DL380 2U SFF (esxi01 & esxi02: 2 black perforated mesh cages on left/center + 8 vertical 2.5" SFF drives on right)
    def hpe_2u_sff_svg(y: int, u_label: str, host_title: str, sub_info: str, magenta_latches: bool = False) -> str:
        sff_bays = []
        for b in range(8):
            bx = 312 + b * 20
            ring_on = b in (0, 1) or (magenta_latches and b in (4, 5, 6, 7))
            ring_svg = f'<circle cx="{bx+9}" cy="46" r="4" fill="none" stroke="#22c55e" stroke-width="1.8"/>' if ring_on else f'<circle cx="{bx+9}" cy="46" r="3.5" fill="none" stroke="#334155" stroke-width="1"/>'
            latch_col = "#ec4899" if (magenta_latches and b >= 4) else "#881337"
            led_dot = f'<circle cx="{bx+9}" cy="76" r="2" fill="#22c55e"/>' if (magenta_latches and b >= 4) else ""
            sff_bays.append(f"""
              <rect x="{bx}" y="12" width="18" height="70" rx="2" fill="#18181b" stroke="#3f3f46" stroke-width="1"/>
              {ring_svg}
              <rect x="{bx+3}" y="58" width="12" height="11" rx="1.5" fill="{latch_col}"/>
              {led_dot}
            """)
        top_trim = '<rect x="18" y="0" width="484" height="6" fill="#94a3b8"/>' if magenta_latches else ""
        return f"""
        <g transform="translate(42,{y})">
          <text x="-12" y="48" text-anchor="end" fill="#64748b" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="700">{u_label}</text>
          <rect x="0" y="0" width="520" height="90" rx="3" fill="#0f141c" stroke="#334155" stroke-width="1.5"/>
          {top_trim}
          <!-- Black Left & Right Rack Ears -->
          <rect x="0" y="0" width="20" height="90" rx="2" fill="#1e293b" stroke="#475569"/>
          <rect x="496" y="0" width="24" height="90" rx="2" fill="#1e293b" stroke="#475569"/>
          <!-- Right Ear HPE Green Status LEDs -->
          <circle cx="508" cy="22" r="3" fill="#22c55e"/><circle cx="508" cy="34" r="2.5" fill="#22c55e"/>
          <rect x="502" y="64" width="12" height="16" rx="1" fill="#064e3b" stroke="#10b981" stroke-width="0.8"/>
          <!-- Cage 1 & Cage 2: Perforated Black Mesh Blanking Cages -->
          <rect x="26" y="10" width="136" height="72" rx="2" fill="url(#mesh-pattern)" stroke="#475569" stroke-width="1.2"/>
          <rect x="168" y="10" width="136" height="72" rx="2" fill="url(#mesh-pattern)" stroke="#475569" stroke-width="1.2"/>
          <!-- Overlay Host Label on Mesh Cage -->
          <rect x="34" y="22" width="256" height="48" rx="6" fill="#090d16" fill-opacity="0.86" stroke="#38bdf8" stroke-width="1"/>
          <text x="44" y="41" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11.5" font-weight="800">{host_title}</text>
          <text x="44" y="58" fill="#38bdf8" font-family="JetBrains Mono,monospace" font-size="9.5">{sub_info}</text>
          <!-- Cage 3 (Right): 8 Vertical 2.5" SFF SmartCarrier Drives -->
          {''.join(sff_bays)}
        </g>
        """

    # Helper for HPE ProLiant DL380 2U 12-Bay LFF 3.5" (esxi03 & esxi04: Silver rack ears + White 1..12 sticker + 4x3 Horizontal LFF bays)
    def hpe_2u_lff_svg(y: int, u_label: str, host_title: str, sub_info: str, blue_uid_led: bool = False) -> str:
        lff_bays = []
        for col_i in range(4):
            for row_i in range(3):
                bx = 26 + col_i * 116
                by = 14 + row_i * 24
                has_green_ring = (row_i == 0 and col_i == 0 and blue_uid_led) or (row_i == 1 and col_i in (0, 2))
                ring = f'<circle cx="{bx+42}" cy="{by+11}" r="4.2" fill="none" stroke="#22c55e" stroke-width="1.8"/>' if has_green_ring else f'<circle cx="{bx+42}" cy="{by+11}" r="3.5" fill="#27272a"/>'
                lff_bays.append(f"""
                  <rect x="{bx}" y="{by}" width="112" height="21" rx="2" fill="#1c1917" stroke="#44403c" stroke-width="1"/>
                  {ring}
                  <!-- Maroon Release Latch on Right of Each 3.5" LFF Caddy -->
                  <rect x="{bx+92}" y="{by+3}" width="14" height="15" rx="1.5" fill="#9f1239"/>
                """)
        uid_svg = '<circle cx="508" cy="74" r="5" fill="#00e5ff"/><circle cx="508" cy="74" r="9" fill="#00e5ff" opacity="0.35"/>' if blue_uid_led else '<circle cx="508" cy="74" r="3" fill="#22c55e"/>'
        return f"""
        <g transform="translate(42,{y})">
          <text x="-12" y="48" text-anchor="end" fill="#64748b" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="700">{u_label}</text>
          <rect x="0" y="0" width="520" height="92" rx="3" fill="#18181b" stroke="#52525b" stroke-width="1.5"/>
          <!-- Exposed Silver Steel Top Lip with White 'Drive Bay ID 1..12' Sticker on Top-Right -->
          <rect x="20" y="0" width="476" height="11" fill="#71717a"/>
          <rect x="398" y="1.5" width="84" height="8.5" rx="1" fill="#f8fafc" stroke="#334155" stroke-width="0.6"/>
          <text x="440" y="8" text-anchor="middle" fill="#0f172a" font-family="JetBrains Mono,monospace" font-size="6.5" font-weight="800">BAY ID 1..12 LFF</text>
          <!-- Brushed Silver Left & Right HPE Rack Ears -->
          <rect x="0" y="0" width="22" height="92" rx="2" fill="url(#brushed-silver)" stroke="#64748b"/>
          <rect x="494" y="0" width="26" height="92" rx="2" fill="url(#brushed-silver)" stroke="#64748b"/>
          <rect x="4" y="68" width="14" height="14" rx="1" fill="#3b82f6" opacity="0.7"/>
          <circle cx="508" cy="32" r="4" fill="#22c55e" stroke="#14532d" stroke-width="1"/>
          {uid_svg}
          <!-- 4 Columns x 3 Rows = 12 Horizontal 3.5" LFF Bays -->
          {''.join(lff_bays)}
          <!-- Translucent Callout Pill Over Center of LFF Array -->
          <rect x="34" y="28" width="295" height="40" rx="6" fill="#090d16" fill-opacity="0.88" stroke="#10b981" stroke-width="1.2"/>
          <text x="44" y="45" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11" font-weight="800">{host_title}</text>
          <text x="44" y="60" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9">{sub_info}</text>
        </g>
        """

    return f"""
    <div style="width:1920px;height:1034px;background:#080c14;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      <!-- Top Header Banner -->
      <div style="position:absolute;left:24px;right:24px;top:12px;height:44px;background:#111726;border:1px solid #263248;border-radius:10px;display:flex;align-items:center;justify-content:space-between;padding:0 20px;z-index:5;">
        <div style="display:flex;align-items:center;gap:12px;">
          <span style="background:#ef444422;color:#f87171;border:1px solid #ef444466;padding:3px 10px;border-radius:6px;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:800;">THERMOSTAT: 79.5°F</span>
          <span style="color:#f8fafc;font-size:15px;font-weight:900;">STYLE #9 • BOYLENET PHYSICAL RACK DIGITAL TWIN (FRONT + REAR ELEVATION) &amp; LIVE 27-VM TOPOLOGY</span>
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#38bdf8;">
          4×1U Silver UniFi Stack • 4×2U HPE DL380 (2× SFF + 2× 12-LFF) • Rear Top UPS + Rear USW-Pro-Max (ESXi 2&amp;3)
        </div>
      </div>

      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <defs>
          <linearGradient id="brushed-silver" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#cbd5e1"/>
            <stop offset="50%" stop-color="#e2e8f0"/>
            <stop offset="100%" stop-color="#94a3b8"/>
          </linearGradient>
          <pattern id="mesh-pattern" width="6" height="6" patternUnits="userSpaceOnUse">
            <rect width="6" height="6" fill="#141820"/>
            <circle cx="3" cy="3" r="1.6" fill="#06080c"/>
          </pattern>
        </defs>

        <!-- ========================================================================= -->
        <!-- COL 1 (x=18..585): FRONT RACK ELEVATION (EXACT MATCH TO OPERATOR PHOTO)    -->
        <!-- ========================================================================= -->
        <rect x="18" y="68" width="564" height="946" rx="8" fill="#0b0e14" stroke="#334155" stroke-width="3"/>
        <!-- Top Perforated Vent Slots + Red 79.5°F LED Thermostat + Red Rocker Switch -->
        <rect x="22" y="72" width="556" height="58" rx="4" fill="#151921" stroke="#262f3f"/>
        <g fill="#07090d">
          <rect x="40" y="76" width="8" height="14" rx="2"/><rect x="58" y="76" width="8" height="14" rx="2"/><rect x="76" y="76" width="8" height="14" rx="2"/><rect x="94" y="76" width="8" height="14" rx="2"/><rect x="112" y="76" width="8" height="14" rx="2"/><rect x="130" y="76" width="8" height="14" rx="2"/>
          <rect x="440" y="76" width="8" height="14" rx="2"/><rect x="458" y="76" width="8" height="14" rx="2"/><rect x="476" y="76" width="8" height="14" rx="2"/><rect x="494" y="76" width="8" height="14" rx="2"/>
        </g>
        <!-- Centered Red Digital Thermostat Reading 79.5°F -->
        <rect x="236" y="88" width="112" height="34" rx="4" fill="#090a0f" stroke="#475569" stroke-width="1.8"/>
        <text x="282" y="112" text-anchor="middle" fill="#ff2a2a" font-family="JetBrains Mono,monospace" font-size="20" font-weight="900">79.5°F</text>
        <text x="336" y="101" fill="#64748b" font-family="JetBrains Mono,monospace" font-size="7">S ▲</text>
        <text x="336" y="114" fill="#64748b" font-family="JetBrains Mono,monospace" font-size="7">● ▼</text>
        <!-- Top-Right Red Illuminated Power Rocker Switch -->
        <rect x="488" y="94" width="28" height="18" rx="3" fill="#450a0a" stroke="#dc2626" stroke-width="1.5"/>
        <rect x="492" y="97" width="20" height="12" rx="2" fill="#ef4444"/>
        <text x="48" y="114" fill="#94a3b8" font-family="Inter,sans-serif" font-size="11" font-weight="800">FRONT ELEVATION (12U)</text>

        <!-- Top 4U: 4x 1U Brushed Silver Ubiquiti UniFi Stack -->
        {unifi_1u_svg(142, "U12", "Dream Machine Pro", u1_details)}
        {unifi_1u_svg(192, "U11", "USW-Aggregation", u2_details)}
        {unifi_1u_svg(242, "U10", "USW-Pro-Agg", u3_details)}
        {unifi_1u_svg(292, "U09", "USW-24-PoE", u4_details)}

        <!-- Bottom 8U: 4x 2U HPE ProLiant DL380 Servers (esxi01..04) -->
        {hpe_2u_sff_svg(352, "U08-07", "esxi01 (.20.41) • HPE DL380 2U SFF", "2× Mesh Cages + 8× 2.5\" SFF Flash • iLO .10", False)}
        {hpe_2u_sff_svg(456, "U06-05", "esxi02 (.20.42) • HPE DL380 2U SFF", "8× 2.5\" SFF (Magenta Latches) + Rear Pro-Max", True)}
        {hpe_2u_lff_svg(560, "U04-03", "esxi03 (.20.43) • HPE DL380 12-Bay LFF", "12× 3.5\" LFF (4×24TB Exos + SAS) + Rear Pro-Max", False)}
        {hpe_2u_lff_svg(666, "U02-01", "esxi04 (.20.44) • HPE DL380 12-Bay LFF", "12× 3.5\" LFF (4×24TB Exos + SAS) • Blue UID LED", True)}

        <!-- Authentic Front Cable Drape Overlay (Aqua OM3/OM4 Fibers + Black 25GbE DACs + Blue Cat6 Bundle) -->
        <!-- Blue Cat6 Bundle in U09 (USW-24-PoE) -->
        <path d="M 310 318 Q 365 365 460 342" stroke="#2563eb" stroke-width="7" fill="none" opacity="0.85"/>
        <path d="M 325 318 Q 375 372 465 346" stroke="#1d4ed8" stroke-width="5" fill="none" opacity="0.85"/>
        <!-- Aqua OM3/OM4 LC Fiber Sweeps with Yellow Clips -->
        <path d="M 365 268 Q 160 330 35 415" stroke="#2dd4bf" stroke-width="3" fill="none" opacity="0.9"/>
        <path d="M 435 215 Q 545 350 538 520" stroke="#2dd4bf" stroke-width="3.2" fill="none" opacity="0.9"/>
        <path d="M 465 268 Q 558 450 532 745" stroke="#2dd4bf" stroke-width="3" fill="none" opacity="0.9"/>
        <!-- Black 25GbE SFP28 DAC Twinax Loops from USW-Pro-Agg -->
        <path d="M 275 268 C 235 445, 420 445, 435 268" stroke="#1e293b" stroke-width="4.5" fill="none"/>
        <path d="M 275 268 C 235 445, 420 445, 435 268" stroke="#475569" stroke-width="1.5" fill="none"/>
        <path d="M 390 268 Q 470 430 535 615" stroke="#0f172a" stroke-width="5" fill="none"/>

        <!-- Bottom Front Summary Box inside Rack Frame -->
        <rect x="34" y="775" width="532" height="222" rx="8" fill="#101726" stroke="#263248" stroke-width="1.5"/>
        <text x="50" y="798" fill="#00e5ff" font-family="Inter,sans-serif" font-size="11.5" font-weight="800">LIVE RACK FRONT INVENTORY &amp; CABLE TELEMETRY</text>
        <text x="50" y="818" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">• Thermostat: <tspan fill="#f87171" font-weight="700">79.5°F</tspan> • Total Power: <tspan fill="#34d399" font-weight="700">1,180W (UPS Protected)</tspan></text>
        <text x="50" y="838" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">• U12–U09: <tspan fill="#f8fafc">UDM-Pro + USW-Agg + USW-Pro-Agg (280G) + USW-24-PoE</tspan></text>
        <text x="50" y="858" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">• U08–U05: <tspan fill="#60a5fa">esxi01 &amp; esxi02 (2U SFF • 2 Mesh Cages + 8×2.5" SmartCarrier)</tspan></text>
        <text x="50" y="878" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">• U04–U01: <tspan fill="#34d399">esxi03 &amp; esxi04 (2U 12-Bay 3.5" LFF • 24TB Exos + Blue UID)</tspan></text>
        <text x="50" y="898" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">• Optics: <tspan fill="#2dd4bf">Aqua OM3/OM4 10G SFP+</tspan> + <tspan fill="#38bdf8">Black 25GbE SFP28 RoCE DACs</tspan></text>
        <rect x="50" y="914" width="500" height="68" rx="6" fill="#090d16" stroke="#1e293b"/>
        <text x="64" y="935" fill="#fbbf24" font-family="JetBrains Mono,monospace" font-size="10" font-weight="700">vSAN 75-DISK MATRIX: 135.7 / 328.4 TiB USED (41.3% • 11 DISK GROUPS)</text>
        <text x="64" y="953" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="9.5">Tier-0: 12× 24TB Seagate Exos (esxi02..04) • Tier-1: NVMe Cache + 3TB SAS</text>
        <text x="64" y="970" fill="#00e5ff" font-family="JetBrains Mono,monospace" font-size="9.5">4× NVIDIA Tesla T4 GPUs (64GB VRAM): .72, .83, .125, .228 @ 77.62 tok/s</text>

        <!-- ========================================================================= -->
        <!-- COL 2 (x=602..1060): REAR RACK ELEVATION (TOP UPS + USW-PRO-MAX IN ESXi 2&3)-->
        <!-- ========================================================================= -->
        <rect x="602" y="68" width="458" height="946" rx="8" fill="#0b0e14" stroke="#334155" stroke-width="3"/>
        <rect x="606" y="72" width="450" height="44" rx="4" fill="#151921" stroke="#262f3f"/>
        <text x="620" y="99" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11.5" font-weight="900">REAR RACK CUTAWAY (TOP UPS + USW-PRO-MAX)</text>
        <text x="975" y="99" fill="#10b981" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="800">REAR VIEW</text>

        <!-- Rear Top (U12-U11 Rear): Rackmount UPS Battery Backup -->
        <g transform="translate(618,128)">
          <rect width="426" height="86" rx="5" fill="#171923" stroke="#f59e0b" stroke-width="2"/>
          <rect x="12" y="12" width="105" height="62" rx="4" fill="#090d16" stroke="#fbbf24" stroke-width="1.2"/>
          <text x="64" y="34" text-anchor="middle" fill="#fbbf24" font-family="JetBrains Mono,monospace" font-size="11" font-weight="900">RACK UPS</text>
          <text x="64" y="50" text-anchor="middle" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="10" font-weight="700">100% BATT</text>
          <text x="64" y="65" text-anchor="middle" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="8.5">1180W / AVR</text>
          <text x="128" y="28" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11.5" font-weight="800">Rear Top Rackmount UPS &amp; Power Conditioner</text>
          <text x="128" y="46" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="9">Mounted Top Rear Rails • Dual-Feed to 4× HPE DL380 PSUs</text>
          <!-- 8x NEMA/IEC Battery Backup Outlets -->
          <g fill="#090d16" stroke="#475569" stroke-width="1">
            <rect x="132" y="54" width="28" height="20" rx="2"/><rect x="166" y="54" width="28" height="20" rx="2"/>
            <rect x="200" y="54" width="28" height="20" rx="2"/><rect x="234" y="54" width="28" height="20" rx="2"/>
            <rect x="268" y="54" width="28" height="20" rx="2"/><rect x="302" y="54" width="28" height="20" rx="2"/>
            <rect x="336" y="54" width="28" height="20" rx="2"/><rect x="370" y="54" width="28" height="20" rx="2"/>
          </g>
        </g>

        <!-- Rear U10-U09: Rear of UniFi Switching & Patch Exhaust -->
        <g transform="translate(618,226)">
          <rect width="426" height="108" rx="5" fill="#131824" stroke="#38bdf8" stroke-width="1.2"/>
          <text x="16" y="24" fill="#38bdf8" font-family="Inter,sans-serif" font-size="11" font-weight="800">Rear of UniFi 4×1U Stack (Redundant RPS + Cooling Fans)</text>
          <text x="16" y="43" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="9.5">• UDM-Pro + USW-Agg + USW-Pro-Agg (280G) + USW-24-PoE Rear Plane</text>
          <text x="16" y="61" fill="#00e5ff" font-family="JetBrains Mono,monospace" font-size="9.5">• VLAN 75 25GbE SFP28 RoCE Twinax + VLAN 60 10GbE vSAN Trunking</text>
          <rect x="16" y="72" width="394" height="24" rx="4" fill="#090d16" stroke="#1e293b"/>
          <text x="26" y="88" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9.5">4× Cooling Fan Modules Active • 0.18ms Intra-Rack Switching</text>
        </g>

        <!-- Rear U08-U07: esxi01 Rear (iLO .10, Tesla T4 #1, Dual PSU) -->
        <g transform="translate(618,352)">
          <rect width="426" height="90" rx="4" fill="#111622" stroke="#3b82f6" stroke-width="1.4"/>
          <text x="14" y="22" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11" font-weight="800">esxi01 Rear Bay (.20.41 • HPE iLO4 10.0.10.10)</text>
          <text x="14" y="40" fill="#00e5ff" font-family="JetBrains Mono,monospace" font-size="9.5">PCIe Riser: NVIDIA Tesla T4 (16GB) + 25GbE SFP28 RoCE (.75.11)</text>
          <rect x="14" y="52" width="120" height="26" rx="4" fill="#064e3b" stroke="#10b981"/><text x="74" y="69" text-anchor="middle" fill="#6ee7b7" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">PSU1+2 246W</text>
          <rect x="144" y="52" width="125" height="26" rx="4" fill="#042f2e" stroke="#00e5ff"/><text x="206" y="69" text-anchor="middle" fill="#00e5ff" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">T4 #1 (ai-srv01)</text>
          <rect x="279" y="52" width="132" height="26" rx="4" fill="#1e1b4b" stroke="#818cf8"/><text x="345" y="69" text-anchor="middle" fill="#c7d2fe" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">iLO .10 + vSAN .21</text>
        </g>

        <!-- Rear U06-U03 (Behind ESXi 2 & ESXi 3): USW-Pro-Max Mounted in Rear + ESXi 02 & 03 Rear Bays! -->
        <g transform="translate(618,456)">
          <rect width="426" height="194" rx="6" fill="#141829" stroke="#a855f7" stroke-width="2.2"/>
          <!-- Brushed Silver USW-Pro-Max Switch Bar with Etherlighting Glow -->
          <rect x="10" y="10" width="406" height="52" rx="4" fill="url(#brushed-silver)" stroke="#c084fc" stroke-width="1.8"/>
          <rect x="18" y="17" width="28" height="28" rx="3" fill="#04102c" stroke="#38bdf8" stroke-width="1.2"/>
          <circle cx="32" cy="31" r="9" fill="#3b82f6"/>
          <text x="52" y="29" fill="#0f172a" font-family="Inter,sans-serif" font-size="10" font-weight="900">USW-Pro-Max (Rear in ESXi 2 &amp; 3)</text>
          <text x="52" y="43" fill="#6b21a8" font-family="JetBrains Mono,monospace" font-size="8" font-weight="800">Etherlighting™ 2.5G/10G SFP+ Fabric</text>
          <!-- Glowing Etherlighting Port Row -->
          <g transform="translate(262,18)">
            <rect x="0" y="0" width="144" height="30" rx="3" fill="#090d16" stroke="#a855f7"/>
            <circle cx="14" cy="10" r="3.5" fill="#00e5ff"/><circle cx="28" cy="10" r="3.5" fill="#c084fc"/><circle cx="42" cy="10" r="3.5" fill="#00e5ff"/><circle cx="56" cy="10" r="3.5" fill="#10b981"/><circle cx="70" cy="10" r="3.5" fill="#c084fc"/><circle cx="84" cy="10" r="3.5" fill="#00e5ff"/><circle cx="98" cy="10" r="3.5" fill="#10b981"/><circle cx="112" cy="10" r="3.5" fill="#00e5ff"/><circle cx="128" cy="10" r="4" fill="#fbbf24"/>
            <circle cx="14" cy="21" r="3.5" fill="#10b981"/><circle cx="28" cy="21" r="3.5" fill="#00e5ff"/><circle cx="42" cy="21" r="3.5" fill="#c084fc"/><circle cx="56" cy="21" r="3.5" fill="#00e5ff"/><circle cx="70" cy="21" r="3.5" fill="#10b981"/><circle cx="84" cy="21" r="3.5" fill="#c084fc"/><circle cx="98" cy="21" r="3.5" fill="#00e5ff"/><circle cx="112" cy="21" r="3.5" fill="#10b981"/><circle cx="128" cy="21" r="4" fill="#fbbf24"/>
          </g>
          <!-- ESXi02 & ESXi03 Rear Telemetry underneath USW-Pro-Max -->
          <rect x="12" y="72" width="402" height="52" rx="4" fill="#0c1220" stroke="#00e5ff" stroke-width="1"/>
          <text x="22" y="91" fill="#f8fafc" font-family="Inter,sans-serif" font-size="10.5" font-weight="800">esxi02 Rear (.20.42 • iLO .20) + Tesla T4 #2 (aidev .83)</text>
          <text x="22" y="109" fill="#00e5ff" font-family="JetBrains Mono,monospace" font-size="9">25GbE SFP28 RoCE (.75.12 :50052) • vSAN .60.22 • Dual PSU 312W</text>

          <rect x="12" y="132" width="402" height="52" rx="4" fill="#0c1220" stroke="#38bdf8" stroke-width="1"/>
          <text x="22" y="151" fill="#f8fafc" font-family="Inter,sans-serif" font-size="10.5" font-weight="800">esxi03 Rear (.20.43 • iLO .30) + Tesla T4 #3 (ai-infer01 .125)</text>
          <text x="22" y="169" fill="#38bdf8" font-family="JetBrains Mono,monospace" font-size="9">Qdrant Vector GPU • 4×24TB Exos Tier-0 • vSAN .60.23 • PSU 298W</text>
        </g>

        <!-- Rear U02-U01: esxi04 Rear (iLO .40, Tesla T4 #4, Dual PSU) -->
        <g transform="translate(618,666)">
          <rect width="426" height="92" rx="4" fill="#111622" stroke="#3b82f6" stroke-width="1.4"/>
          <text x="14" y="22" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11" font-weight="800">esxi04 Rear Bay (.20.44 • HPE iLO4 10.0.10.40)</text>
          <text x="14" y="40" fill="#00e5ff" font-family="JetBrains Mono,monospace" font-size="9.5">PCIe Riser: NVIDIA Tesla T4 #4 (ai-ollama01 .228) + Blue UID LED</text>
          <rect x="14" y="52" width="120" height="26" rx="4" fill="#064e3b" stroke="#10b981"/><text x="74" y="69" text-anchor="middle" fill="#6ee7b7" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">PSU1+2 324W</text>
          <rect x="144" y="52" width="132" height="26" rx="4" fill="#042f2e" stroke="#00e5ff"/><text x="210" y="69" text-anchor="middle" fill="#00e5ff" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">T4 #4 (.228 Gate)</text>
          <rect x="286" y="52" width="126" height="26" rx="4" fill="#1e1b4b" stroke="#818cf8"/><text x="349" y="69" text-anchor="middle" fill="#c7d2fe" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">iLO .40 + vSAN .24</text>
        </g>

        <!-- External Workstation Nodes & Synology Box Below Rear Rack -->
        <g transform="translate(618,775)">
          <rect width="426" height="222" rx="8" fill="#101726" stroke="#263248" stroke-width="1.5"/>
          <text x="18" y="24" fill="#a855f7" font-family="Inter,sans-serif" font-size="11.5" font-weight="800">ADJACENT WORKSTATION ORACLES &amp; NAS VAULT</text>
          <rect x="18" y="38" width="390" height="50" rx="6" fill="#090d16" stroke="#38bdf8"/>
          <text x="30" y="57" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11" font-weight="800">BattleStation (.10.137) • Ryzen 9 + RTX 2080 Ti (11GB)</text>
          <text x="30" y="75" fill="#38bdf8" font-family="JetBrains Mono,monospace" font-size="9.5">Primary Chrome 155 CDP Oracle (:9222) + CPU Embeddings (Rule 84)</text>

          <rect x="18" y="98" width="390" height="50" rx="6" fill="#090d16" stroke="#38bdf8"/>
          <text x="30" y="117" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11" font-weight="800">Bittorrent (.70.181) • Secondary Windows CDP Oracle</text>
          <text x="30" y="135" fill="#38bdf8" font-family="JetBrains Mono,monospace" font-size="9.5">Parallel Chrome 155 CDP Bridge (:9222) • Deep Research Fanout</text>

          <rect x="18" y="158" width="390" height="50" rx="6" fill="#090d16" stroke="#10b981"/>
          <text x="30" y="177" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11" font-weight="800">Synology NAS (.70.199) + vCenter Server vc04 (.70.70)</text>
          <text x="30" y="195" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9.5">NFSv4 Snapshot Vault + vSphere 8.0 DRS Elastic Cold Spare Controller</text>
        </g>

        <!-- ========================================================================= -->
        <!-- COL 3 (x=1080..1902): LIVE VM PLACEMENT, AGENTS & $1,000 CLOUD TOPOLOGY   -->
        <!-- ========================================================================= -->
        <rect x="1080" y="68" width="822" height="946" rx="8" fill="#0b0e14" stroke="#263248" stroke-width="2"/>
        <text x="1102" y="98" fill="#00e5ff" font-family="Inter,sans-serif" font-size="13" font-weight="900">LIVE RACK-TO-VM HYPERVISOR MAP &amp; ACTIVE SWARM AGENTS (27 VMS)</text>

        <!-- Fiber Patch Traces from Rear Rack into Live Topology Boxes -->
        <path d="M 1044 268 C 1072 268, 1072 155, 1102 155" stroke="#00e5ff" stroke-width="3" fill="none"/>
        <path d="M 1044 395 C 1072 395, 1072 295, 1102 295" stroke="#00e5ff" stroke-width="3" fill="none"/>
        <path d="M 1044 545 C 1072 545, 1072 455, 1102 455" stroke="#a855f7" stroke-width="3" fill="none"/>
        <path d="M 1044 710 C 1072 710, 1072 625, 1102 625" stroke="#3b82f6" stroke-width="3" fill="none"/>
        <path d="M 1044 830 C 1072 830, 1072 805, 1102 805" stroke="#10b981" stroke-width="3" fill="none"/>

        <!-- Box 1: VLAN 75 25GbE RoCE 4x Tesla T4 GPU & Dual 10TB Model Vault -->
        <g transform="translate(1102,115)">
          <rect width="780" height="145" rx="8" fill="#071c26" stroke="#00e5ff" stroke-width="1.8"/>
          <text x="16" y="24" fill="#00e5ff" font-family="Inter,sans-serif" font-size="12" font-weight="900">⚡ VLAN 75 • 25GbE SFP28 RoCE GPU TENSOR FABRIC (4× TESLA T4 • 77.62 TOK/S)</text>
          <g transform="translate(16,36)">
            <rect x="0" y="0" width="180" height="94" rx="6" fill="#090d16" stroke="#00e5ff"/>
            <text x="10" y="20" fill="#f8fafc" font-size="11" font-weight="800">ai-srv01 (.70.72)</text>
            <text x="10" y="37" fill="#00e5ff" font-family="JetBrains Mono,monospace" font-size="9">RoCE 10.0.75.11 • T4 16G</text>
            <text x="10" y="54" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="9">52c AVX-512 • 320G RAM</text>
            <text x="10" y="72" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">DeepSeek-671B 77.6t/s</text>

            <rect x="192" y="0" width="180" height="94" rx="6" fill="#090d16" stroke="#00e5ff"/>
            <text x="202" y="20" fill="#f8fafc" font-size="11" font-weight="800">aidev (.70.83)</text>
            <text x="202" y="37" fill="#00e5ff" font-family="JetBrains Mono,monospace" font-size="9">RoCE 10.0.75.12 :50052</text>
            <text x="202" y="54" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="9">52c AVX-512 • 386G RAM</text>
            <text x="202" y="72" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">5TB Vault B • MiMo-1T</text>

            <rect x="384" y="0" width="180" height="94" rx="6" fill="#090d16" stroke="#38bdf8"/>
            <text x="394" y="20" fill="#f8fafc" font-size="11" font-weight="800">ai-infer01 (.70.125)</text>
            <text x="394" y="37" fill="#38bdf8" font-family="JetBrains Mono,monospace" font-size="9">Tesla T4 16G • 280G RAM</text>
            <text x="394" y="54" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="9">Qdrant Vector DB (:6333)</text>
            <text x="394" y="72" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">Qwen2.5-Coder-32B</text>

            <rect x="576" y="0" width="174" height="94" rx="6" fill="#090d16" stroke="#38bdf8"/>
            <text x="586" y="20" fill="#f8fafc" font-size="11" font-weight="800">ai-ollama01 (.70.228)</text>
            <text x="586" y="37" fill="#38bdf8" font-family="JetBrains Mono,monospace" font-size="9">Tesla T4 16G • 280G RAM</text>
            <text x="586" y="54" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="9">LiteLLM :4000 • Langfuse</text>
            <text x="586" y="72" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">17 Local Ollama Models</text>
          </g>
        </g>

        <!-- Box 2: Controller Nexus (.164) + 64c Ramdisk (.82) -->
        <g transform="translate(1102,276)">
          <rect width="780" height="145" rx="8" fill="#1b1608" stroke="#fbbf24" stroke-width="1.8"/>
          <text x="16" y="24" fill="#fbbf24" font-family="Inter,sans-serif" font-size="12" font-weight="900">🧠 SWARM COMMAND NEXUS (.164) &amp; 64-CORE RAMDISK TURBO (.82)</text>
          <rect x="16" y="36" width="370" height="94" rx="6" fill="#090d16" stroke="#fbbf24"/>
          <text x="28" y="56" fill="#f8fafc" font-size="11.5" font-weight="800">Controller Nexus • bd (10.0.70.164)</text>
          <text x="28" y="74" fill="#fbbf24" font-family="JetBrains Mono,monospace" font-size="9.5">Traefik (:80) • Dashy (:4080) • 14 New Studios (:4086..:4099)</text>
          <text x="28" y="92" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9.5">Active Seats: AGY-Council, bd-pm-B, Sentinel (83/83 UP)</text>
          <text x="28" y="110" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="9">32 Authoritative UniFi DNS Shortlinks Verified</text>

          <rect x="398" y="36" width="366" height="94" rx="6" fill="#090d16" stroke="#10b981"/>
          <text x="410" y="56" fill="#f8fafc" font-size="11.5" font-weight="800">CI Ramdisk Turbo • test3big / wrk-test04 (.82)</text>
          <text x="410" y="74" fill="#10b981" font-family="JetBrains Mono,monospace" font-size="9.5">64 vCPUs • 128 GB DDR4 • /dev/shm Ramdisk Pytest Engine</text>
          <text x="410" y="92" fill="#38bdf8" font-family="JetBrains Mono,monospace" font-size="9.5">Zero-Disk-IO xdist Shards + Cluster RAG Indexing</text>
          <text x="410" y="110" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="9">Hosted on HPE DL380 ESXi Fabric • 10GbE vSAN Backed</text>
        </g>

        <!-- Box 3: 22 Worker & Elastic Cold-Spare VMs across ESXi 01..04 -->
        <g transform="translate(1102,437)">
          <rect width="780" height="195" rx="8" fill="#0c1526" stroke="#3b82f6" stroke-width="1.8"/>
          <text x="16" y="24" fill="#60a5fa" font-family="Inter,sans-serif" font-size="12" font-weight="900">🖥️ 22 FLEET WORKER &amp; ELASTIC COLD-SPARE VMS (HOSTED ON ESXi 01..04)</text>
          <g font-family="JetBrains Mono,monospace" font-size="9.5">
            <rect x="16" y="38" width="180" height="44" rx="5" fill="#090d16" stroke="#10b981"/><text x="26" y="56" fill="#f8fafc" font-weight="700">bd1 (10.0.70.51)</text><text x="26" y="72" fill="#10b981">Builder #1 • ON</text>
            <rect x="206" y="38" width="180" height="44" rx="5" fill="#090d16" stroke="#10b981"/><text x="216" y="56" fill="#f8fafc" font-weight="700">bd2 (10.0.70.210)</text><text x="216" y="72" fill="#10b981">Builder #2 • ON</text>
            <rect x="396" y="38" width="180" height="44" rx="5" fill="#090d16" stroke="#10b981"/><text x="406" y="56" fill="#f8fafc" font-weight="700">bd3 (10.0.70.211)</text><text x="406" y="72" fill="#10b981">Builder #3 • ON</text>
            <rect x="586" y="38" width="178" height="44" rx="5" fill="#090d16" stroke="#10b981"/><text x="596" y="56" fill="#f8fafc" font-weight="700">bd4 (10.0.70.212)</text><text x="596" y="72" fill="#10b981">Builder #4 • ON</text>

            <rect x="16" y="90" width="180" height="44" rx="5" fill="#090d16" stroke="#34d399"/><text x="26" y="108" fill="#f8fafc" font-weight="700">test1 (.81) &amp; test2 (.84)</text><text x="26" y="124" fill="#34d399">2× Verifiers • ON</text>
            <rect x="206" y="90" width="180" height="44" rx="5" fill="#090d16" stroke="#34d399"/><text x="216" y="108" fill="#f8fafc" font-weight="700">test4 (.85) &amp; test5 (.86)</text><text x="216" y="124" fill="#34d399">2× Verifiers • ON</text>
            <rect x="396" y="90" width="180" height="44" rx="5" fill="#090d16" stroke="#34d399"/><text x="406" y="108" fill="#f8fafc" font-weight="700">test6 (.197) &amp; test7 (.249)</text><text x="406" y="124" fill="#34d399">2× Verifiers • ON</text>
            <rect x="586" y="90" width="178" height="44" rx="5" fill="#090d16" stroke="#38bdf8"/><text x="596" y="108" fill="#f8fafc" font-weight="700">fresh149 (10.0.70.149)</text><text x="596" y="124" fill="#38bdf8">Clean Sandbox • ON</text>

            <rect x="16" y="142" width="245" height="40" rx="5" fill="#090d16" stroke="#38bdf8"/><text x="26" y="166" fill="#38bdf8" font-weight="700">spare1 (.120) &amp; spare2 (.183) • HOT ON</text>
            <rect x="272" y="142" width="492" height="40" rx="5" fill="#090d16" stroke="#64748b"/><text x="284" y="166" fill="#94a3b8" font-weight="700">spare3..spare10 (8× Elastic Cold Spares • Rule 61 DRS Standby 0W)</text>
          </g>
        </g>

        <!-- Box 4: $1,000 Cloud Burst Pools & Active Agent Harnesses -->
        <g transform="translate(1102,648)">
          <rect width="780" height="348" rx="8" fill="#170f2a" stroke="#a855f7" stroke-width="1.8"/>
          <text x="16" y="26" fill="#c084fc" font-family="Inter,sans-serif" font-size="12" font-weight="900">☁️ $1,000 CLOUD BURST POOLS &amp; O1740 AUTONOMOUS SWARM SEATS (ZERO OVERAGE RISK)</text>
          <g transform="translate(16,40)" font-family="JetBrains Mono,monospace">
            <rect x="0" y="0" width="368" height="86" rx="6" fill="#090d16" stroke="#c084fc"/>
            <text x="14" y="22" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11.5" font-weight="800">Anthropic Cloud Pools A &amp; B ($500 Credit)</text>
            <text x="14" y="42" fill="#c084fc" font-size="9.5">$250 Pool A + $250 Pool B • Expires Nov 5 • Overage OFF</text>
            <text x="14" y="60" fill="#34d399" font-size="9.5">Active: bd-pm-B (Opus 5.5 PM) + claude-A/B Heavy Lenses</text>
            <text x="14" y="76" fill="#94a3b8" font-size="9">5h Quota: 0% Used • Weekly: 2% Used</text>

            <rect x="382" y="0" width="366" height="86" rx="6" fill="#090d16" stroke="#a855f7"/>
            <text x="396" y="22" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11.5" font-weight="800">Anthropic Cloud Pools C &amp; D ($500 Credit)</text>
            <text x="396" y="42" fill="#a855f7" font-size="9.5">$250 Pool C + $250 Pool D • Parallel Sonnet 5.5 Workers</text>
            <text x="396" y="60" fill="#34d399" font-size="9.5">Active: claude-C &amp; claude-D • 30 Global Heavy-Lifter Cap</text>
            <text x="396" y="76" fill="#94a3b8" font-size="9">5h Quota: 5% / 0% Used • Hot-Swap Ready</text>

            <rect x="0" y="98" width="368" height="86" rx="6" fill="#090d16" stroke="#10b981"/>
            <text x="14" y="120" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11.5" font-weight="800">OpenAI Codex Cloud (GPT-6.1-Sol / Astra)</text>
            <text x="14" y="140" fill="#10b981" font-size="9.5">Single-Turn Verifiers, Builders &amp; AST Diff Slicers</text>
            <text x="14" y="158" fill="#38bdf8" font-size="9.5">Active: codex-gpt-6.1-sol • 0.0% Window Used</text>
            <text x="14" y="174" fill="#94a3b8" font-size="9">Fast-Fail ruff_check + mypy_check Gate</text>

            <rect x="382" y="98" width="366" height="86" rx="6" fill="#090d16" stroke="#00e5ff"/>
            <text x="396" y="120" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11.5" font-weight="800">AGY-Council + Kimi-for-Coding + Hermes-4</text>
            <text x="396" y="140" fill="#00e5ff" font-size="9.5">10 Parallel Native Subagents + Kimi 256k Synthesis</text>
            <text x="396" y="158" fill="#fbbf24" font-size="9.5">Active: AGY-Council, kimi-for-coding, hermes-4-405b</text>
            <text x="396" y="174" fill="#94a3b8" font-size="9">Zero-Token Systemd Telemetry Guard</text>

            <rect x="0" y="198" width="748" height="94" rx="6" fill="#090d16" stroke="#38bdf8"/>
            <text x="16" y="220" fill="#38bdf8" font-family="Inter,sans-serif" font-size="11.5" font-weight="800">COMPLETE PHYSICAL-TO-VIRTUAL TRACE SUMMARY</text>
            <text x="16" y="242" fill="#cbd5e1" font-size="9.5">1. Top Rear UPS (1,180W) powers 4× HPE DL380 ESXi Hosts (U08–U01) &amp; 4×1U Silver UniFi Stack (U12–U09) at 79.5°F.</text>
            <text x="16" y="260" fill="#cbd5e1" font-size="9.5">2. USW-Pro-Agg (U10, 280G) + Rear USW-Pro-Max (ESXi 2&amp;3) link 4× Tesla T4 GPUs over 25GbE SFP28 RoCE (77.6 tok/s).</text>
            <text x="16" y="278" fill="#cbd5e1" font-size="9.5">3. 11 vSAN Disk Groups (328.4 TiB across 2.5" SFF &amp; 3.5" 12-Bay LFF Exos) back all 27 Cluster VMs &amp; 83 Services.</text>
          </g>
        </g>
      </svg>
    </div>
    """


def build_style_10_cyberpunk() -> str:
    """Style 10: Cyberpunk 3D Holo-Deck & Split Tactical Cockpit."""
    def cyber_monolith(x: int, base_y: int, w: int, h: int, col: str, tag: str, sub: str, metric: str) -> str:
        top_y = base_y - h
        dw = 18
        dh = 12
        return f"""
        <g>
          <!-- Floor Neon Halo -->
          <ellipse cx="{x + w//2}" cy="{base_y}" rx="{w//2 + 16}" ry="10" fill="{col}" opacity="0.22"/>
          <!-- 3D Extruded Wireframe Monolith -->
          <polygon points="{x},{top_y} {x+dw},{top_y-dh} {x+w+dw},{top_y-dh} {x+w},{top_y}" fill="{col}" fill-opacity="0.35" stroke="{col}" stroke-width="1.5"/>
          <polygon points="{x+w},{top_y} {x+w+dw},{top_y-dh} {x+w+dw},{base_y-dh} {x+w},{base_y}" fill="#070514" fill-opacity="0.88" stroke="{col}" stroke-width="1.4"/>
          <rect x="{x}" y="{top_y}" width="{w}" height="{h}" fill="#090618" fill-opacity="0.85" stroke="{col}" stroke-width="1.8"/>
          <!-- Horizontal Neon Energy Bars inside Monolith -->
          <line x1="{x+6}" y1="{top_y+18}" x2="{x+w-6}" y2="{top_y+18}" stroke="{col}" stroke-width="2"/>
          <line x1="{x+6}" y1="{top_y+36}" x2="{x+w-6}" y2="{top_y+36}" stroke="{col}" stroke-width="1.2" opacity="0.7"/>
          <line x1="{x+6}" y1="{top_y+54}" x2="{x+w-6}" y2="{top_y+54}" stroke="{col}" stroke-width="1.2" opacity="0.5"/>
          <!-- Floating Holographic HUD Callout Banner Above Monolith -->
          <line x1="{x+w//2}" y1="{top_y-dh}" x2="{x+w//2}" y2="{top_y-dh-20}" stroke="{col}" stroke-width="1.5"/>
          <rect x="{x+w//2 - 84}" y="{top_y-dh-64}" width="168" height="44" rx="4" fill="#05020d" stroke="{col}" stroke-width="1.4"/>
          <text x="{x+w//2}" y="{top_y-dh-48}" text-anchor="middle" fill="#ffffff" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="800">{tag}</text>
          <text x="{x+w//2}" y="{top_y-dh-35}" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="8.5" font-weight="700">{sub}</text>
          <text x="{x+w//2}" y="{top_y-dh-24}" text-anchor="middle" fill="#fcee0a" font-family="JetBrains Mono,monospace" font-size="8">{metric}</text>
        </g>
        """

    # Perspective Horizon Grid Lines (vanishing point at 960, 175)
    grid = []
    for gx in range(-900, 2820, 135):
        grid.append(f'<line x1="960" y1="175" x2="{gx}" y2="755" stroke="#ff007f" stroke-width="1" opacity="0.28"/>')
    for gy in [210, 250, 300, 360, 430, 515, 620, 745]:
        grid.append(f'<line x1="0" y1="{gy}" x2="1920" y2="{gy}" stroke="#00f3ff" stroke-width="1" opacity="0.24"/>')

    monoliths = [
        # Back Row (Cloud + Spine + ESXi)
        cyber_monolith(105, 455, 76, 135, "#ff007f", "CLAUDE POOLS A-D", "$1,000 FREE CREDIT", "OPUS 5.5 + SONNET 5.5"),
        cyber_monolith(305, 455, 76, 125, "#00f3ff", "CODEX + KIMI + AGY", "GPT-6.1-SOL • 10 SEATS", "ZERO-LATENCY SWARM"),
        cyber_monolith(515, 455, 78, 145, "#fcee0a", "UNIFI 280G SPINE", "UDM-PRO + PRO-AGG", "REAR PRO-MAX + UPS"),
        cyber_monolith(1335, 455, 78, 145, "#3b82f6", "ESXi 01 & 02 (SFF)", "2× HPE DL380 2U SFF", "8×2.5\" FLASH • 79.5°F"),
        cyber_monolith(1545, 455, 78, 145, "#3b82f6", "ESXi 03 & 04 (LFF)", "2× HPE DL380 12-LFF", "328.4 TiB VSAN EXOS"),
        cyber_monolith(1735, 455, 76, 125, "#10b981", "22 WORKER VMS", "BD1..4 • TEST1..7", "14 ACTIVE • 8 DRS"),
        # Front Row (4x Tesla T4 GPUs, Controller .164, 64c Ramdisk .82, Oracles)
        cyber_monolith(210, 690, 88, 185, "#00f3ff", "AI-SRV01 (.70.72)", "TESLA T4 #1 • 320G", "DEEPSEEK 77.6 TOK/S"),
        cyber_monolith(445, 690, 88, 185, "#00f3ff", "AIDEV (.70.83)", "TESLA T4 #2 • 386G", "ROCE :50052 VAULT B"),
        cyber_monolith(680, 690, 86, 165, "#38bdf8", "INFER01 & OLLAMA01", "2× TESLA T4 (.125/.228)", "QDRANT + LITELLM"),
        cyber_monolith(915, 690, 96, 215, "#fcee0a", "CONTROLLER BD (.164)", "BD-PM-B // OPUS 5.5", "32 WEB UIS • 83 UP"),
        cyber_monolith(1165, 690, 88, 180, "#10b981", "TEST3BIG (.70.82)", "64-VCPU • 128G RAMDISK", "/DEV/SHM PYTEST CI"),
        cyber_monolith(1415, 690, 86, 165, "#ff007f", "ORACLES .137 & .181", "RYZEN 9 + RTX 2080Ti", "DUAL CHROME CDP :9222"),
        cyber_monolith(1645, 690, 84, 155, "#a855f7", "SENTINEL + VAULT", ":4099 & :4087", "83 HEALED • 38 SSH"),
    ]

    return f"""
    <div style="width:1920px;height:1034px;background:#05020d;position:relative;overflow:hidden;font-family:'JetBrains Mono',monospace;">
      <!-- Upper 72% 3D Cyberpunk Holo-Deck Viewport -->
      <svg width="1920" height="755" style="position:absolute;left:0;top:0;">
        <defs>
          <radialGradient id="cyber-sun" cx="50%" cy="22%" r="35%">
            <stop offset="0%" stop-color="#ff007f" stop-opacity="0.55"/>
            <stop offset="45%" stop-color="#7928ca" stop-opacity="0.28"/>
            <stop offset="100%" stop-color="#05020d" stop-opacity="0"/>
          </radialGradient>
        </defs>
        <rect width="1920" height="755" fill="url(#cyber-sun)"/>
        <!-- Cyber Sun Disc at Horizon -->
        <circle cx="960" cy="175" r="88" fill="#ff007f" opacity="0.28"/>
        <circle cx="960" cy="175" r="64" fill="none" stroke="#fcee0a" stroke-width="2" stroke-dasharray="10,5"/>
        {''.join(grid)}
        <!-- Overhead Laser Arcs Connecting Monoliths -->
        <path d="M 254 445 Q 600 220 963 415" stroke="#00f3ff" stroke-width="2.5" fill="none"/>
        <path d="M 489 445 Q 720 260 963 415" stroke="#00f3ff" stroke-width="2.5" fill="none"/>
        <path d="M 254 445 Q 370 360 489 445" stroke="#fcee0a" stroke-width="3" fill="none"/>
        <path d="M 963 415 Q 1220 260 1458 465" stroke="#ff007f" stroke-width="2.2" fill="none"/>
        {''.join(monoliths)}
      </svg>

      <!-- Top Cyberpunk HUD Banner -->
      <div style="position:absolute;left:28px;right:28px;top:16px;display:flex;justify-content:space-between;align-items:center;z-index:5;">
        <div style="background:rgba(5,2,13,0.88);border:1px solid #00f3ff;border-left:5px solid #ff007f;padding:10px 18px;">
          <div style="color:#fcee0a;font-size:10px;font-weight:800;letter-spacing:1.5px;">STYLE #10 // CYBERPUNK 3D HOLO-DECK &amp; SPLIT TACTICAL COCKPIT</div>
          <div style="color:#ffffff;font-size:17px;font-weight:900;">BOYLENET NEURAL HORIZON // 27 VMS • 4× TESLA T4 • 280G SPINE • $1,000 CLOUD</div>
        </div>
        <div style="background:rgba(5,2,13,0.88);border:1px solid #fcee0a;padding:10px 18px;color:#fcee0a;font-size:11px;font-weight:800;">
          ⚡ OVERDRIVE LOCKED: 77.62 TOK/S ROCE • RACK TEMP 79.5°F • 0 ERRORS
        </div>
      </div>

      <!-- Lower 28% (y=755..1034): Split 4-Bay Tactical Glass Cockpit Deck -->
      <div style="position:absolute;left:0;right:0;top:755px;bottom:0;background:linear-gradient(180deg,#0b061a 0%,#05020d 100%);border-top:2px solid #00f3ff;display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:14px;padding:14px 20px;box-sizing:border-box;">
        <div style="background:#090514;border:1px solid #00f3ff66;border-radius:8px;padding:12px;">
          <div style="color:#00f3ff;font-size:11px;font-weight:800;margin-bottom:8px;">COCKPIT BAY 01 // 25GBE ROCE TENSOR EQUALIZER</div>
          <div style="font-size:10px;color:#cbd5e1;line-height:1.7;">
            <div>ai-srv01 (.72) T4 #1: <span style="color:#00f3ff;">██████████░░ 66% VRAM (31.2W)</span></div>
            <div>aidev (.83) T4 #2:    <span style="color:#00f3ff;">███████████░ 70% VRAM (32.5W)</span></div>
            <div>infer01 (.125) T4 #3: <span style="color:#38bdf8;">████████████ 78% VRAM (30.1W)</span></div>
            <div>ollama01 (.228) T4 #4:<span style="color:#38bdf8;">████████████ 81% VRAM (31.1W)</span></div>
            <div style="color:#fcee0a;margin-top:4px;font-weight:700;">STREAM: deepseek-v3-671b + Kimi-K2.5 @ 77.6 tok/s</div>
          </div>
        </div>

        <div style="background:#090514;border:1px solid #ff007f66;border-radius:8px;padding:12px;">
          <div style="color:#ff007f;font-size:11px;font-weight:800;margin-bottom:8px;">COCKPIT BAY 02 // $1,000 CLOUD BURST TACHOMETERS</div>
          <div style="font-size:10px;color:#cbd5e1;line-height:1.7;">
            <div>Pool A ($250 Opus 5.5): <span style="color:#10b981;">0% 5h • $250.00 READY</span></div>
            <div>Pool B ($250 bd-pm-B):  <span style="color:#10b981;">0% 5h • $250.00 READY</span></div>
            <div>Pools C/D ($500 Swarm): <span style="color:#10b981;">5% 5h • $500.00 READY</span></div>
            <div>Codex GPT-6.1-Sol:      <span style="color:#00f3ff;">0% Win • VERIFIER OK</span></div>
            <div style="color:#fcee0a;margin-top:4px;font-weight:700;">OVERAGE PROTECTION: LOCKED OFF ($0.00 RISK)</div>
          </div>
        </div>

        <div style="background:#090514;border:1px solid #fcee0a66;border-radius:8px;padding:12px;">
          <div style="color:#fcee0a;font-size:11px;font-weight:800;margin-bottom:8px;">COCKPIT BAY 03 // PHYSICAL RACK &amp; VSAN MATRIX</div>
          <div style="font-size:10px;color:#cbd5e1;line-height:1.7;">
            <div>Front Top 4U: <span style="color:#ffffff;">UDM-Pro + USW-Agg + Pro-Agg + 24-PoE</span></div>
            <div>Front Bot 8U: <span style="color:#60a5fa;">esxi01..02 (SFF) + esxi03..04 (12-LFF)</span></div>
            <div>Rear Mounts:  <span style="color:#c084fc;">Top Rack UPS + USW-Pro-Max (ESXi 2&amp;3)</span></div>
            <div>vSAN Storage: <span style="color:#10b981;">135.7 / 328.4 TiB (11 DGs • 75 Disks)</span></div>
            <div style="color:#ff007f;margin-top:4px;font-weight:700;">CABINET THERMOSTAT: 79.5°F • 1,180W DRAW</div>
          </div>
        </div>

        <div style="background:#090514;border:1px solid #10b98166;border-radius:8px;padding:12px;">
          <div style="color:#10b981;font-size:11px;font-weight:800;margin-bottom:8px;">COCKPIT BAY 04 // LIVE SWARM &amp; 27-VM TELEMETRY</div>
          <div style="font-size:10px;color:#cbd5e1;line-height:1.7;">
            <div>Controller .164: <span style="color:#10b981;">15 Active Sessions • 32 DNS OK</span></div>
            <div>Ramdisk .82:     <span style="color:#00f3ff;">64-vCPU / 128G /dev/shm Pytest</span></div>
            <div>Oracles .137/.181:<span style="color:#fcee0a;">Dual Chrome 155 CDP :9222 E2E</span></div>
            <div>Fleet VMs:       <span style="color:#10b981;">19 Powered ON • 8 DRS Standby</span></div>
            <div style="color:#10b981;margin-top:4px;font-weight:700;">INFRA SENTINEL (:4099): 83/83 SERVICES GREEN</div>
          </div>
        </div>
      </div>
    </div>
    """


STYLE_BUILDERS = [
    (1, "Ubiquiti UniFi OS Dark Topology", build_style_01_unifi),
    (2, "n8n / ReactFlow Node-Wire Canvas", build_style_02_reactflow),
    (3, "Palantir Gotham Tactical HUD", build_style_03_palantir),
    (4, "Isometric 2.5D/3D Data-Center", build_style_04_isometric),
    (5, "Neural Swarm Orbital Galaxy", build_style_05_galaxy),
    (6, "Apple VisionOS Spatial Glass", build_style_06_visionos),
    (7, "Live Sankey Token & Compute River", build_style_07_sankey),
    (8, "Hexagonal Honeycomb Swarm Hive", build_style_08_hexhive),
    (9, "Physical 12U Rack Twin + Topology", build_style_09_physical_rack),
    (10, "Cyberpunk 3D Holo-Deck Cockpit", build_style_10_cyberpunk),
]


def generate_gallery_html() -> str:
    """Assemble all 10 full-bleed 1920x1080 topology mockups into an interactive gallery HTML."""
    nav_buttons = []
    slides_html = []
    for idx, title, fn in STYLE_BUILDERS:
        short = title.split()[0]
        nav_buttons.append(
            f'<button class="style-tab" id="tab-{idx}" onclick="showStyle({idx})">'
            f'<span class="num">{idx:02d}</span> {short}</button>'
        )
        body = fn()
        slides_html.append(
            f'<div class="mockup-slide" id="slide-{idx}" style="display:{"block" if idx == 1 else "none"};">{body}</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=1920, height=1080, initial-scale=1.0"/>
<title>Boylenet 10 Topology Visual Mockups (:4088)</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
  html, body {{
    width: 1920px;
    height: 1080px;
    overflow: hidden;
    background: #060911;
    color: #f8fafc;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }}
  #top-switcher {{
    width: 1920px;
    height: 46px;
    background: #0a0e17;
    border-bottom: 1px solid #1e293b;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 18px;
    z-index: 9999;
    position: relative;
  }}
  .brand-title {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
    font-weight: 800;
    color: #f8fafc;
  }}
  .brand-pill {{
    background: linear-gradient(135deg, #00e5ff, #3b82f6);
    color: #040814;
    padding: 3px 9px;
    border-radius: 6px;
    font-size: 10.5px;
    font-weight: 900;
    letter-spacing: 0.5px;
  }}
  .tabs-row {{
    display: flex;
    gap: 5px;
  }}
  .style-tab {{
    background: #131b2e;
    border: 1px solid #26334d;
    color: #94a3b8;
    padding: 5px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.12s ease;
  }}
  .style-tab:hover {{
    color: #f8fafc;
    border-color: #38bdf8;
  }}
  .style-tab.active {{
    background: #006fff;
    border-color: #38bdf8;
    color: #ffffff;
    box-shadow: 0 0 12px rgba(0, 111, 255, 0.5);
  }}
  .style-tab .num {{
    color: #38bdf8;
    font-family: 'JetBrains Mono', monospace;
    margin-right: 3px;
  }}
  .style-tab.active .num {{
    color: #fde68a;
  }}
  .active-style-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: #38bdf8;
    font-weight: 700;
  }}
  .mockup-slide {{
    width: 1920px;
    height: 1034px;
    overflow: hidden;
    position: relative;
  }}
</style>
</head>
<body>
  <div id="top-switcher">
    <div class="brand-title">
      <span class="brand-pill">BOYLENET :4088</span>
      <span id="current-style-title">STYLE 01 / 10 — Ubiquiti UniFi OS Dark Topology</span>
    </div>
    <div class="tabs-row">
      {''.join(nav_buttons)}
    </div>
    <div class="active-style-label">27 VMs • 4×T4 25G RoCE • 4×HPE DL380 • $1,000 Cloud</div>
  </div>

  {''.join(slides_html)}

  <script>
    const STYLE_NAMES = {{
      1: "STYLE 01 / 10 — Ubiquiti UniFi OS Dark Topology",
      2: "STYLE 02 / 10 — n8n / ReactFlow Node-Wire Canvas",
      3: "STYLE 03 / 10 — Palantir Gotham Tactical HUD",
      4: "STYLE 04 / 10 — Isometric 2.5D/3D Data-Center",
      5: "STYLE 05 / 10 — Neural Swarm Orbital Galaxy",
      6: "STYLE 06 / 10 — Apple VisionOS Spatial Glass",
      7: "STYLE 07 / 10 — Live Sankey Token & Compute River",
      8: "STYLE 08 / 10 — Hexagonal Honeycomb Swarm Hive",
      9: "STYLE 09 / 10 — Physical 12U Rack Twin + Topology",
      10: "STYLE 10 / 10 — Cyberpunk 3D Holo-Deck Cockpit"
    }};
    function showStyle(n) {{
      for (let i = 1; i <= 10; i++) {{
        const s = document.getElementById('slide-' + i);
        const t = document.getElementById('tab-' + i);
        if (s) s.style.display = (i === n) ? 'block' : 'none';
        if (t) {{
          if (i === n) t.classList.add('active');
          else t.classList.remove('active');
        }}
      }}
      const lbl = document.getElementById('current-style-title');
      if (lbl && STYLE_NAMES[n]) lbl.textContent = STYLE_NAMES[n];
      window.currentStyle = n;
    }}
    window.addEventListener('keydown', (e) => {{
      if (e.key >= '1' && e.key <= '9') showStyle(parseInt(e.key, 10));
      else if (e.key === '0') showStyle(10);
      else if (e.key === 'ArrowRight') showStyle(((window.currentStyle || 1) % 10) + 1);
      else if (e.key === 'ArrowLeft') showStyle(((window.currentStyle || 1) + 8) % 10 + 1);
    }});
    const params = new URLSearchParams(window.location.search);
    const initial = parseInt(params.get('style') || '1', 10);
    showStyle(initial >= 1 && initial <= 10 ? initial : 1);
  </script>
</body>
</html>
"""


def cdp_call(ws, method: str, params: Dict[str, Any] | None = None, msg_id: int = 1) -> Dict[str, Any]:
    payload = {"id": msg_id, "method": method, "params": params or {}}
    ws.send(json.dumps(payload))
    while True:
        raw = ws.recv()
        data = json.loads(raw)
        if data.get("id") == msg_id:
            return data


def render_screenshots_via_cdp(url_base: str = "http://10.0.70.164:4088/mockups") -> List[Dict[str, Any]]:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ws_url = None
    chosen_host = None
    created_tab_id = None
    for host in ORACLE_HOSTS:
        try:
            req_new = urllib.request.Request(f"http://{host}:9222/json/new", method="PUT")
            with urllib.request.urlopen(req_new, timeout=4.0) as resp:
                tab_info = json.loads(resp.read().decode())
                ws_url = tab_info.get("webSocketDebuggerUrl")
                created_tab_id = tab_info.get("id")
                chosen_host = host
                if ws_url:
                    break
        except Exception as exc:
            print(f"[WARN] CDP host {host} new-tab failed: {exc}", file=sys.stderr)

    if not ws_url:
        raise RuntimeError("No reachable Browser Oracle CDP page target on 10.0.10.137 or 10.0.70.181")

    print(f"[CDP] Connected to Browser Oracle on {chosen_host} (tab {created_tab_id}): {ws_url}")
    ws = create_connection(ws_url, timeout=20)
    msg_seq = 1
    results = []
    try:
        cdp_call(ws, "Page.enable", {}, msg_seq); msg_seq += 1
        cdp_call(ws, "Runtime.enable", {}, msg_seq); msg_seq += 1
        cdp_call(ws, "Page.bringToFront", {}, msg_seq); msg_seq += 1
        cdp_call(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {"width": 1920, "height": 1080, "deviceScaleFactor": 1, "mobile": False},
            msg_seq,
        ); msg_seq += 1

        # Navigate once to the gallery page, then flip styles via showStyle(i) for instant zero-flicker capture
        target_url = f"{url_base}?style=1"
        cdp_call(ws, "Page.navigate", {"url": target_url}, msg_seq); msg_seq += 1
        time.sleep(1.2)

        for idx, title, _ in STYLE_BUILDERS:
            cdp_call(ws, "Page.bringToFront", {}, msg_seq); msg_seq += 1
            cdp_call(
                ws,
                "Runtime.evaluate",
                {"expression": f"showStyle({idx}); document.title;", "returnByValue": True},
                msg_seq,
            ); msg_seq += 1
            time.sleep(0.25)
            shot = cdp_call(
                ws,
                "Page.captureScreenshot",
                {
                    "format": "png",
                    "fromSurface": True,
                    "captureBeyondViewport": False,
                    "clip": {"x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1},
                },
                msg_seq,
            ); msg_seq += 1
            b64_data = shot.get("result", {}).get("data", "")
            png_bytes = base64.b64decode(b64_data)
            out_path = SCREENSHOT_DIR / f"topology_mockup_{idx:02d}.png"
            out_path.write_bytes(png_bytes)
            print(f"[OK] Saved {out_path} ({len(png_bytes):,} bytes) — {title}")
            results.append({
                "style": idx,
                "title": title,
                "path": str(out_path),
                "bytes": len(png_bytes),
                "oracle_host": chosen_host,
            })
    finally:
        try:
            ws.close()
        except Exception:
            pass
        if chosen_host and created_tab_id:
            try:
                urllib.request.urlopen(f"http://{chosen_host}:9222/json/close/{created_tab_id}", timeout=2.0)
            except Exception:
                pass
    return results


def main() -> None:
    html = generate_gallery_html()
    GALLERY_HTML_PATH.write_text(html, encoding="utf-8")
    print(f"[OK] Wrote interactive 10-style gallery to {GALLERY_HTML_PATH} ({len(html):,} bytes)")
    if "--html-only" in sys.argv:
        return
    results = render_screenshots_via_cdp()
    print(json.dumps({"status": "ok", "count": len(results), "screenshots": results}, indent=2))


if __name__ == "__main__":
    main()
