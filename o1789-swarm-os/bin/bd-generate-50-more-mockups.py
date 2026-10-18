#!/usr/bin/env python3
"""
bd-generate-50-more-mockups.py
Generates 50 MORE radically distinct 1920x1080 visual mockups (Styles #11 through #60)
for Boylenet Architecture Topology & Live Swarm Visualizer (:4088), combines them with
Styles #01..#10 into a 60-Style Interactive Gallery (/var/tmp/topology-mockups-gallery.html
served at http://topology.boylenet.themfboyles.com/mockups), and renders all 50 PNG
screenshots (topology_mockup_11.png .. topology_mockup_60.png) via Browser Oracle CDP.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import math
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple
from websocket import create_connection

GALLERY_HTML_PATH = Path("/var/tmp/topology-mockups-gallery.html")
SCREENSHOT_DIR = Path(
    "/home/mboyle/.gemini/antigravity-cli/brain/d61a0f86-9a87-4a9f-8b2c-ea5791e23bc8/screenshots"
)
ORACLE_HOSTS = ["10.0.10.137", "10.0.70.181"]

# Load Styles 1..10 from bd-generate-10-topology-mockups.py
_spec = importlib.util.spec_from_file_location(
    "mockups10", "/home/mboyle/bin/bd-generate-10-topology-mockups.py"
)
_mod10 = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
assert _spec and _spec.loader
_spec.loader.exec_module(_mod10)

FIRST_10_BUILDERS: List[Tuple[int, str, Callable[[], str]]] = _mod10.STYLE_BUILDERS

# Canonical Boylenet Cluster Data used across all 50 new visual styles
CLUSTER_NODES = [
    ("UDM-Pro (.1)", "Gateway & 32 DNS", "10.0.70.1", "WAN/DNS OK", "#38bdf8", "net"),
    ("USW-Agg (10G)", "8x 10G SFP+ Optical", "10.0.10.3", "OM3/OM4", "#00e5ff", "net"),
    ("USW-Pro-Agg 280G", "28x10G + 4x25G SFP28", "10.0.10.2", "280 Gbps", "#00e5ff", "net"),
    ("USW-24-PoE", "Blue Cat6 Bundle", "10.0.10.4", "PoE+ OK", "#3b82f6", "net"),
    ("USW-Pro-Max Rear", "Rear in ESXi 2 & 3", "10.0.10.5", "Etherlight", "#a855f7", "net"),
    ("Rear Top UPS", "1180W Battery AVR", "79.5°F", "100% BATT", "#f59e0b", "pwr"),
    ("esxi01 (.101)", "DL380 2U SFF (8x2.5\")", "10.0.20.41", "iLO .10 OK", "#3b82f6", "esxi"),
    ("esxi02 (.102)", "DL380 2U SFF + ProMax", "10.0.20.42", "iLO .20 OK", "#3b82f6", "esxi"),
    ("esxi03 (.103)", "DL380 2U 12-Bay LFF", "10.0.20.43", "96TB Exos", "#3b82f6", "esxi"),
    ("esxi04 (.104)", "DL380 2U 12-Bay LFF", "10.0.20.44", "Blue UID", "#3b82f6", "esxi"),
    ("ai-srv01 (.72)", "Tesla T4 #1 • 320G", "10.0.75.11", "77.6 tok/s", "#00e5ff", "gpu"),
    ("aidev (.83)", "Tesla T4 #2 • 386G", "10.0.75.12", "RPC :50052", "#00e5ff", "gpu"),
    ("ai-infer01 (.125)", "Tesla T4 #3 • 280G", "10.0.70.125", "Qdrant :6333", "#22d3ee", "gpu"),
    ("ai-ollama01 (.228)", "Tesla T4 #4 • 280G", "10.0.70.228", "LiteLLM :4000", "#22d3ee", "gpu"),
    ("Controller bd (.164)", "32 Web UIs • PM-B", "10.0.70.164", "83/83 UP", "#fbbf24", "core"),
    ("test3big (.82)", "64c 128G /dev/shm", "10.0.70.82", "Ramdisk CI", "#10b981", "core"),
    ("BattleStation (.137)", "Ryzen 9 + RTX 2080Ti", "10.0.10.137", "CDP :9222", "#f59e0b", "oracle"),
    ("Bittorrent (.181)", "Secondary Win CDP", "10.0.70.181", "CDP :9222", "#f59e0b", "oracle"),
    ("Builders bd1..4", ".51, .210, .211, .212", "VLAN 70", "4x Active", "#10b981", "vm"),
    ("Verifiers test1..7", ".81..86, .197, .249", "VLAN 70", "7x Active", "#34d399", "vm"),
    ("fresh149 + spare1..2", ".149, .120, .183", "VLAN 70", "3x Hot ON", "#38bdf8", "vm"),
    ("spare3..10 (DRS)", "Rule 61 Cold Spares", "vCenter .70", "8x Standby", "#64748b", "vm"),
    ("Claude Pools A & B", "Opus 5.5 + bd-pm-B", "$500 Credit", "0% 5h Used", "#c084fc", "cloud"),
    ("Claude Pools C & D", "Sonnet 5.5 Swarm", "$500 Credit", "Cap 30/30", "#a855f7", "cloud"),
    ("Codex + Kimi + AGY", "GPT-6.1-Sol + 10 AGY", "Multi-Pool", "100% OK", "#10b981", "cloud"),
]


def _header_banner(style_num: int, family: str, title: str, subtitle: str, bg: str, border: str, title_col: str, accent: str) -> str:
    return f"""
    <div style="position:absolute;left:22px;right:22px;top:14px;height:54px;background:{bg};border:1px solid {border};border-left:5px solid {accent};border-radius:10px;display:flex;align-items:center;justify-content:space-between;padding:0 20px;z-index:5;">
      <div>
        <div style="color:{accent};font-size:10px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;">MOCKUP #{style_num:02d} / 60 • {family}</div>
        <div style="color:{title_col};font-size:16.5px;font-weight:900;letter-spacing:-0.2px;">{title}</div>
      </div>
      <div style="display:flex;align-items:center;gap:12px;font-family:'JetBrains Mono',monospace;font-size:10.5px;color:{title_col};">
        <span style="background:{accent}22;border:1px solid {accent}66;color:{accent};padding:4px 10px;border-radius:6px;font-weight:700;">{subtitle}</span>
        <span style="opacity:0.8;">79.5°F Rack • 4×T4 77.6 tok/s • 27 VMs • 328.4 TiB vSAN • $1,000 Cloud</span>
      </div>
    </div>
    """


# =============================================================================
# FAMILY 1 (#11-#15): HARDWARE & PHOTOREALISTIC RACK DEEP-DIVES
# =============================================================================

def build_11_rack_patch_tracer() -> str:
    """#11: Dual Front + Rear 12U Rack with Interactive Fiber/DAC Patch Cable Tracing."""
    base = _mod10.build_style_09_physical_rack()
    # Customize header and add glowing interactive fiber trace callout overlay
    overlay = """
    <div style="position:absolute;left:24px;right:24px;top:12px;height:44px;background:#06202b;border:1px solid #00e5ff;border-radius:10px;display:flex;align-items:center;justify-content:space-between;padding:0 20px;z-index:10;">
      <div style="display:flex;align-items:center;gap:12px;">
        <span style="background:#00e5ff;color:#041019;padding:3px 10px;border-radius:6px;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:900;">MOCKUP #11 / 60</span>
        <span style="color:#f8fafc;font-size:15px;font-weight:900;">OPTICAL FIBER &amp; 25GbE SFP28 DAC PATCH-CABLE TRACER (FRONT 12U + REAR UPS/PRO-MAX)</span>
      </div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#67e8f9;">
        ● Aqua OM3/OM4 10G SFP+ • ● Black 25GbE SFP28 Twinax • ● Blue Cat6 PoE Bundle • ● Rear USW-Pro-Max Etherlighting
      </div>
    </div>
    """
    return base.replace('STYLE #9 • BOYLENET PHYSICAL RACK DIGITAL TWIN', 'STYLE #11 • LIVE OPTICAL & DAC PATCH-CABLE TRACER') + overlay


def build_12_exploded_dl380_chassis() -> str:
    """#12: Exploded 3D Server Chassis Cutaway (HPE DL380 Lid-Off Internal Motherboard & GPU View)."""
    dimms = []
    for g_x in [350, 560, 790, 1000]:
        for d in range(6):
            dx = g_x + d * 14
            dimms.append(f'<rect x="{dx}" y="220" width="9" height="165" rx="1.5" fill="#065f46" stroke="#10b981" stroke-width="1"/>')
            dimms.append(f'<line x1="{dx+4.5}" y1="228" x2="{dx+4.5}" y2="375" stroke="#34d399" stroke-width="1.2" stroke-dasharray="4,3"/>')

    lff_drives = []
    for col in range(4):
        for row in range(3):
            bx = 125 + col * 245
            by = 755 + row * 58
            lff_drives.append(f"""
            <g transform="translate({bx},{by})">
              <rect width="232" height="50" rx="4" fill="#18181b" stroke="#52525b" stroke-width="1.5"/>
              <circle cx="28" cy="25" r="9" fill="none" stroke="#22c55e" stroke-width="2.5"/>
              <rect x="195" y="8" width="26" height="34" rx="3" fill="#9f1239"/>
              <text x="50" y="22" fill="#f8fafc" font-family="Inter,sans-serif" font-size="11" font-weight="800">Bay {col*3+row+1:02d} • 24TB Exos / SAS</text>
              <text x="50" y="38" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9.5">12Gbps SAS3 • vSAN DG OK</text>
            </g>
            """)

    return f"""
    <div style="width:1920px;height:1034px;background:#070b12;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(12, "HARDWARE INTERNAL CUTAWAY", "HPE ProLiant DL380 Lid-Off Internal Motherboard, Dual Xeon AVX-512, 386GB DDR4 & Tesla T4 Cutaway", "LID-OFF EXPLODED CHASSIS", "#0e1626", "#38bdf866", "#f8fafc", "#00e5ff")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <!-- Main Sheet-Metal Server Chassis Outline (Left/Center x=85..1160) -->
        <rect x="85" y="92" width="1075" height="895" rx="12" fill="#111827" stroke="#64748b" stroke-width="4"/>
        <rect x="98" y="105" width="1049" height="869" rx="8" fill="#090e17" stroke="#334155" stroke-width="1.5"/>

        <!-- Rear Section (Top of Diagram y=115..205): Dual 800W FlexSlot PSUs + iLO4 + Rear USW-Pro-Max Interconnect -->
        <rect x="118" y="118" width="240" height="82" rx="6" fill="#064e3b" stroke="#10b981" stroke-width="2"/>
        <text x="238" y="148" text-anchor="middle" fill="#6ee7b7" font-family="JetBrains Mono,monospace" font-size="12" font-weight="900">HPE FLEXSLOT PSU #1 (800W)</text>
        <text x="238" y="170" text-anchor="middle" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="10">Fed by Rear Top Rack UPS • 94% Plat</text>

        <rect x="372" y="118" width="240" height="82" rx="6" fill="#064e3b" stroke="#10b981" stroke-width="2"/>
        <text x="492" y="148" text-anchor="middle" fill="#6ee7b7" font-family="JetBrains Mono,monospace" font-size="12" font-weight="900">HPE FLEXSLOT PSU #2 (800W)</text>
        <text x="492" y="170" text-anchor="middle" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="10">Redundant Load-Balanced • 312W</text>

        <rect x="626" y="118" width="500" height="82" rx="6" fill="#1e1b4b" stroke="#a855f7" stroke-width="2"/>
        <text x="876" y="145" text-anchor="middle" fill="#e9d5ff" font-family="Inter,sans-serif" font-size="12.5" font-weight="900">REAR RAIL MOUNT: USW-Pro-Max Etherlighting + HPE iLO4 (.10..40)</text>
        <text x="876" y="168" text-anchor="middle" fill="#38bdf8" font-family="JetBrains Mono,monospace" font-size="10">Direct Rear Patch to ESXi 02 &amp; ESXi 03 + Dual-Port 25GbE SFP28 RoCE</text>

        <!-- Motherboard System Board (y=210..615): 24 DDR4 DIMMs + Dual Xeon Sockets + PCIe Risers -->
        {''.join(dimms)}
        <!-- CPU Socket 0 -->
        <rect x="442" y="230" width="108" height="145" rx="6" fill="#1e293b" stroke="#f59e0b" stroke-width="2.5"/>
        <rect x="456" y="246" width="80" height="113" rx="4" fill="#78350f" stroke="#fbbf24" stroke-width="1.5"/>
        <text x="496" y="295" text-anchor="middle" fill="#fef3c7" font-family="JetBrains Mono,monospace" font-size="11" font-weight="900">XEON GOLD</text>
        <text x="496" y="312" text-anchor="middle" fill="#fbbf24" font-family="JetBrains Mono,monospace" font-size="9.5">SOCKET 0</text>
        <text x="496" y="328" text-anchor="middle" fill="#fde68a" font-family="JetBrains Mono,monospace" font-size="8.5">AVX-512 • 52vCPU</text>

        <!-- CPU Socket 1 -->
        <rect x="882" y="230" width="108" height="145" rx="6" fill="#1e293b" stroke="#f59e0b" stroke-width="2.5"/>
        <rect x="896" y="246" width="80" height="113" rx="4" fill="#78350f" stroke="#fbbf24" stroke-width="1.5"/>
        <text x="936" y="295" text-anchor="middle" fill="#fef3c7" font-family="JetBrains Mono,monospace" font-size="11" font-weight="900">XEON GOLD</text>
        <text x="936" y="312" text-anchor="middle" fill="#fbbf24" font-family="JetBrains Mono,monospace" font-size="9.5">SOCKET 1</text>
        <text x="936" y="328" text-anchor="middle" fill="#fde68a" font-family="JetBrains Mono,monospace" font-size="8.5">386GB DDR4 ECC</text>

        <!-- PCIe Riser Cage 1: NVIDIA Tesla T4 16GB GDDR6 Accelerator -->
        <rect x="118" y="405" width="490" height="185" rx="8" fill="#042f2e" stroke="#00e5ff" stroke-width="2.5"/>
        <rect x="136" y="422" width="454" height="88" rx="6" fill="#090d16" stroke="#22d3ee" stroke-width="1.8"/>
        <text x="155" y="452" fill="#00e5ff" font-family="Inter,sans-serif" font-size="16" font-weight="900">NVIDIA TESLA T4 (16 GB GDDR6 • TURING TENSOR CORES)</text>
        <text x="155" y="476" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="11">PCIe 3.0 x16 Full-Speed • 31.2W / 70W TDP • 71°C • INT8/FP16 Tensor</text>
        <text x="155" y="496" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="700">Streaming deepseek-v3-0324-671b + Kimi-K2.5-1T @ 77.62 tok/s</text>
        <rect x="136" y="522" width="454" height="52" rx="6" fill="#082032" stroke="#38bdf8"/>
        <text x="155" y="544" fill="#38bdf8" font-family="Inter,sans-serif" font-size="12" font-weight="800">PCIe Slot 2: Dual-Port 25GbE SFP28 RoCE v2 RDMA NIC</text>
        <text x="155" y="562" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">VLAN 75 (10.0.75.11 &lt;-&gt; 10.0.75.12:50052) • Zero-Copy Tensor RPC</text>

        <!-- PCIe Riser Cage 2: HPE Smart Array SAS3 + 10GbE vSAN SFP+ -->
        <rect x="630" y="405" width="496" height="185" rx="8" fill="#172033" stroke="#3b82f6" stroke-width="2"/>
        <text x="650" y="438" fill="#60a5fa" font-family="Inter,sans-serif" font-size="14" font-weight="900">HPE Smart Array P408i-a / HBA + 10GbE SFP+ vSAN NIC</text>
        <text x="650" y="462" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• 12Gbps SAS3 Backplane Expander (Up to 12× 3.5" LFF or 8× 2.5" SFF)</text>
        <text x="650" y="484" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="10.5">• Tier-0: 4× 24TB Seagate Exos Enterprise + Tier-1: NVMe/SAS Flash</text>
        <text x="650" y="506" fill="#38bdf8" font-family="JetBrains Mono,monospace" font-size="10.5">• VLAN 60 vSAN (10.0.60.21..24) • 328.4 TiB Cluster Pool</text>
        <rect x="650" y="522" width="456" height="52" rx="6" fill="#090d16" stroke="#10b981"/>
        <text x="668" y="544" fill="#10b981" font-family="JetBrains Mono,monospace" font-size="11" font-weight="800">vSphere 8.0 Hypervisor Kernel • Hosting 27 Cluster VMs</text>
        <text x="668" y="562" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="9.5">656 Total vCPUs • 1.73 TiB Total RAM across esxi01..esxi04</text>

        <!-- Mid-Plane Hot-Swap High-Static-Pressure Fan Wall (6 Fans, y=612..725) -->
        <rect x="118" y="610" width="1008" height="112" rx="6" fill="#0f172a" stroke="#475569" stroke-width="2"/>
        <text x="622" y="630" text-anchor="middle" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="10" font-weight="800">6× HOT-PLUG REDUNDANT HIGH-PRESSURE COOLING FAN WALL (INTAKE 79.5°F ➔ EXHAUST)</text>
        {''.join(f'<g transform="translate({145 + f*162}, 640)"><rect width="136" height="68" rx="6" fill="#090d16" stroke="#38bdf8"/><circle cx="40" cy="34" r="24" fill="none" stroke="#00e5ff" stroke-width="2" stroke-dasharray="6,3"/><circle cx="40" cy="34" r="6" fill="#00e5ff"/><text x="74" y="30" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="10" font-weight="800">FAN #{f+1}</text><text x="74" y="46" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9">6,400 RPM</text></g>' for f in range(6))}

        <!-- Front Drive Backplane (y=740..950): 12x 3.5" LFF / 8x 2.5" SFF Bays -->
        {''.join(lff_drives)}

        <!-- Right Side (x=1195..1895): Live Chassis-to-VM & Swarm Mapping -->
        <rect x="1195" y="92" width="700" height="895" rx="12" fill="#0d1322" stroke="#263248" stroke-width="2"/>
        <text x="1220" y="128" fill="#00e5ff" font-family="Inter,sans-serif" font-size="15" font-weight="900">4× HPE DL380 CHASSIS COMPARISON &amp; VM GUEST PLACEMENT</text>
        {''.join(f'<g transform="translate(1220,{150 + i*202})"><rect width="650" height="184" rx="8" fill="#090d16" stroke="{c}" stroke-width="1.8"/><text x="18" y="28" fill="#f8fafc" font-family="Inter,sans-serif" font-size="13.5" font-weight="900">{ht}</text><text x="18" y="50" fill="{c}" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="700">{hs}</text><text x="18" y="74" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">{hd}</text><text x="18" y="96" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="10">{hg}</text><rect x="18" y="112" width="614" height="56" rx="6" fill="#111726" stroke="#1e293b"/><text x="30" y="134" fill="#fbbf24" font-family="JetBrains Mono,monospace" font-size="10" font-weight="700">Hosted VMs &amp; Active Swarm Roles:</text><text x="30" y="154" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="10">{hv}</text></g>' for i, (ht, hs, hd, hg, hv, c) in enumerate([
            ("CHASSIS #1: esxi01.boylenet (.20.41 • iLO .10)", "Front: 2× Black Mesh Cages + 8× 2.5\" SFF SmartCarrier Drives", "• Storage: 1× vSAN All-Flash Disk Group (1.6TB NVMe + 7× 3TB SAS)", "• GPU/NIC: NVIDIA Tesla T4 #1 (16GB) • 25GbE SFP28 RoCE (.75.11)", "ai-srv01 (.72 Vault A 77.6 tok/s), bd (.164 Controller), bd1 (.51), test1 (.81)", "#00e5ff"),
            ("CHASSIS #2: esxi02.boylenet (.20.42 • iLO .20)", "Front: 2× Mesh Cages + 8× 2.5\" SFF (Magenta Latches) • Rear: USW-Pro-Max", "• Storage: 1× DG Tier-0 (4× 24TB Exos) + 2× DG Tier-1 (3TB SAS)", "• GPU/NIC: NVIDIA Tesla T4 #2 (16GB) • 25GbE SFP28 RoCE (.75.12 :50052)", "aidev (.83 Vault B), test3big (.82 64c Ramdisk), bd2 (.210), test2 (.84)", "#a855f7"),
            ("CHASSIS #3: esxi03.boylenet (.20.43 • iLO .30)", "Front: Silver Ears + 12× 3.5\" LFF Horizontal Bays • Rear: USW-Pro-Max", "• Storage: 1× DG Tier-0 (4× 24TB Seagate Exos) + 2× DG Tier-1 (3TB SAS)", "• GPU/NIC: NVIDIA Tesla T4 #3 (16GB) • 10G/25G SFP+ • PSU 298W", "ai-infer01 (.125 Qdrant :6333 + Qwen-32B), bd3 (.211), test4..5, spare1..4", "#10b981"),
            ("CHASSIS #4: esxi04.boylenet (.20.44 • iLO .40)", "Front: Silver Ears + Blue UID LED + 12× 3.5\" LFF Horizontal Bays", "• Storage: 1× DG Tier-0 (4× 24TB Seagate Exos) + 2× DG Tier-1 (3TB SAS)", "• GPU/NIC: NVIDIA Tesla T4 #4 (16GB) • vCenter vc04 (.70) • PSU 324W", "ai-ollama01 (.228 LiteLLM :4000 + Langfuse), bd4 (.212), test6..7, spare5..10", "#3b82f6"),
        ]))}
      </svg>
    </div>
    """


def build_13_etherlighting_port_matrix() -> str:
    """#13: Ubiquiti Etherlighting Switch Port Matrix (USW-Pro-Agg 280G + USW-Pro-Max + UDM-Pro + USW-24-PoE)."""
    pro_agg_ports = []
    port_assignments = [
        ("P01", "UDM-Pro .1", "10G SFP+", "#38bdf8"), ("P02", "USW-Agg U2", "10G SFP+", "#38bdf8"),
        ("P03", "USW-24-PoE", "10G SFP+", "#3b82f6"), ("P04", "USW-Pro-Max", "10G SFP+", "#a855f7"),
        ("P05", "esxi01 vSAN", "10G VLAN60", "#10b981"), ("P06", "esxi02 vSAN", "10G VLAN60", "#10b981"),
        ("P07", "esxi03 vSAN", "10G VLAN60", "#10b981"), ("P08", "esxi04 vSAN", "10G VLAN60", "#10b981"),
        ("P09", "esxi01 VM70", "10G VLAN70", "#60a5fa"), ("P10", "esxi02 VM70", "10G VLAN70", "#60a5fa"),
        ("P11", "esxi03 VM70", "10G VLAN70", "#60a5fa"), ("P12", "esxi04 VM70", "10G VLAN70", "#60a5fa"),
        ("P13", "bd (.164)", "10G Trunk", "#fbbf24"), ("P14", "test3big .82", "10G Ramdisk", "#10b981"),
        ("P15", "BattleSt .137", "10G Oracle1", "#f59e0b"), ("P16", "Bittorrent .181", "10G Oracle2", "#f59e0b"),
        ("P17", "Synology .199", "10G NFSv4", "#34d399"), ("P18", "vc04 (.70)", "10G vCenter", "#38bdf8"),
        ("P19", "bd1 & bd2", "10G Builders", "#60a5fa"), ("P20", "bd3 & bd4", "10G Builders", "#60a5fa"),
        ("P21", "test1..test4", "10G Verify", "#34d399"), ("P22", "test5..test7", "10G Verify", "#34d399"),
        ("P23", "fresh149", "10G Sandbox", "#38bdf8"), ("P24", "spare1 & 2", "10G HotSpare", "#38bdf8"),
        ("P25", "iLO4 .10/.20", "VLAN 10 OOB", "#f43f5e"), ("P26", "iLO4 .30/.40", "VLAN 10 OOB", "#f43f5e"),
        ("P27", "Cloud NAT A/B", "$500 Pool", "#c084fc"), ("P28", "Cloud NAT C/D", "$500 Pool", "#c084fc"),
        ("P29*", "ai-srv01 .72", "25G RoCE T4", "#00e5ff"), ("P30*", "aidev .83", "25G RoCE T4", "#00e5ff"),
        ("P31*", "infer01 .125", "25G RoCE T4", "#00e5ff"), ("P32*", "ollama01 .228", "25G RoCE T4", "#00e5ff"),
    ]
    for idx, (pcode, target, vlan, col) in enumerate(port_assignments):
        row = idx % 2
        col_i = idx // 2
        px = 58 + col_i * 112
        py = 165 + row * 102
        is_25g = "*" in pcode
        pro_agg_ports.append(f"""
        <g transform="translate({px},{py})">
          <rect width="104" height="90" rx="8" fill="#0b101c" stroke="{col}" stroke-width="{2.4 if is_25g else 1.4}"/>
          <rect x="6" y="6" width="92" height="18" rx="4" fill="{col}" fill-opacity="0.2"/>
          <circle cx="16" cy="15" r="4" fill="{col}"/>
          <text x="26" y="19" fill="#ffffff" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="900">{pcode}</text>
          <text x="52" y="46" text-anchor="middle" fill="#f8fafc" font-family="Inter,sans-serif" font-size="10.5" font-weight="800">{target}</text>
          <text x="52" y="64" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">{vlan}</text>
          <text x="52" y="80" text-anchor="middle" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="8">{'25Gbps FDX' if is_25g else '10Gbps FDX'}</text>
        </g>
        """)

    promax_ports = []
    for p in range(24):
        px = 58 + p * 74
        col = ["#00e5ff", "#a855f7", "#10b981", "#38bdf8", "#f59e0b", "#ec4899"][p % 6]
        promax_ports.append(f"""
        <g transform="translate({px}, 470)">
          <rect width="66" height="105" rx="8" fill="#100d20" stroke="{col}" stroke-width="2"/>
          <circle cx="33" cy="24" r="12" fill="{col}" opacity="0.28"/>
          <circle cx="33" cy="24" r="5" fill="{col}"/>
          <text x="33" y="52" text-anchor="middle" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="10" font-weight="900">M{p+1:02d}</text>
          <text x="33" y="70" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="8.5" font-weight="700">2.5G PoE</text>
          <text x="33" y="88" text-anchor="middle" fill="#94a3b8" font-family="Inter,sans-serif" font-size="8">ESXi 2&amp;3</text>
        </g>
        """)

    return f"""
    <div style="width:1920px;height:1034px;background:#060912;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(13, "UBIQUITI ETHERLIGHTING & SFP28 PORT MATRIX", "32-Port USW-Pro-Aggregation (280G Spine) + Rear USW-Pro-Max Etherlighting Port-by-Port Map", "ALL 56 SWITCH PORTS MAPPED", "#0c1324", "#00e5ff66", "#f8fafc", "#00e5ff")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <!-- Section 1: USW-Pro-Aggregation 32-Port Matrix -->
        <rect x="34" y="88" width="1852" height="305" rx="12" fill="url(#brushed-silver)" fill-opacity="0.08" stroke="#38bdf8" stroke-width="2"/>
        <text x="58" y="122" fill="#00e5ff" font-size="15" font-weight="900">FRONT U10: USW-Pro-Aggregation (28× 10G SFP+ Ports P01..P28 + 4× 25G SFP28 RoCE Ports P29*..P32* = 280 Gbps)</text>
        <text x="58" y="144" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="10.5">Physical Cabling: Black 25GbE SFP28 Twinax DACs (VLAN 75 RoCE Tensor) + Aqua OM3/OM4 LC Duplex Fiber (VLAN 60 vSAN &amp; VLAN 70 Swarm)</text>
        {''.join(pro_agg_ports)}

        <!-- Section 2: Rear USW-Pro-Max Etherlighting Matrix (Behind ESXi 2 & 3) -->
        <rect x="34" y="412" width="1852" height="190" rx="12" fill="#120d24" stroke="#a855f7" stroke-width="2"/>
        <text x="58" y="445" fill="#e9d5ff" font-size="15" font-weight="900">REAR MOUNT (BEHIND ESXi 02 &amp; ESXi 03): UniFi Switch Pro Max (USW-Pro-Max • Etherlighting™ RGB/VLAN Glow)</text>
        {''.join(promax_ports)}

        <!-- Section 3: UDM-Pro (U12) + USW-Aggregation 8-Port (U11) + USW-24-PoE (U09) + Rear Top UPS Summary -->
        <g transform="translate(34, 622)">
          <rect x="0" y="0" width="445" height="380" rx="12" fill="#0d1424" stroke="#38bdf8" stroke-width="1.8"/>
          <text x="22" y="32" fill="#38bdf8" font-size="14" font-weight="900">FRONT U12: UDM-Pro Gateway (.70.1)</text>
          <text x="22" y="56" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">• 32 Authoritative Static DNS Records (Short + FQDN)</text>
          <text x="22" y="78" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">• 8× GbE RJ45 Ports + 2× 10G SFP+ WAN/LAN Uplinks</text>
          <text x="22" y="100" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">• Site-Magic VPN Bridge to Boylenet Mobile (10.96.112.1)</text>
          <text x="22" y="122" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="10">• Traefik Port :80 Ingress Target (10.0.70.164)</text>

          <rect x="468" y="0" width="445" height="380" rx="12" fill="#0d1424" stroke="#00e5ff" stroke-width="1.8"/>
          <text x="490" y="32" fill="#00e5ff" font-size="14" font-weight="900">FRONT U11 &amp; U09: USW-Agg (8P) + USW-24-PoE</text>
          <text x="490" y="56" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">• U11 USW-Aggregation: 8× 10G SFP+ Optical Distribution</text>
          <text x="490" y="78" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">• U09 USW-24-PoE: Blue Cat6 Bundle (iLO4 + APs + Cameras)</text>
          <text x="490" y="100" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">• 4× Glowing Blue LCM Touchscreens Aligned on Left Rail</text>
          <text x="490" y="122" fill="#fbbf24" font-family="JetBrains Mono,monospace" font-size="10">• Cabinet Top Bezel Thermostat: 79.5°F • Red Rocker ON</text>

          <rect x="936" y="0" width="916" height="380" rx="12" fill="#0d1424" stroke="#10b981" stroke-width="1.8"/>
          <text x="960" y="32" fill="#10b981" font-size="14" font-weight="900">LIVE VLAN TRAFFIC &amp; SWARM FLOWS ACROSS THE 5-SWITCH FABRIC</text>
          <text x="960" y="62" fill="#00e5ff" font-family="JetBrains Mono,monospace" font-size="11" font-weight="700">1. VLAN 75 (10.0.75.0/24 • 25GbE SFP28 RoCE v2): 77.62 tok/s Tensor Split (.72 &lt;-&gt; .83:50052)</text>
          <text x="960" y="90" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="11" font-weight="700">2. VLAN 60 (10.0.60.0/24 • 10GbE SFP+ vSAN): 135.7 / 328.4 TiB across 11 Disk Groups (75 Disks)</text>
          <text x="960" y="118" fill="#60a5fa" font-family="JetBrains Mono,monospace" font-size="11" font-weight="700">3. VLAN 70 (10.0.70.0/24 • Swarm Compute): Controller .164 + 64c Ramdisk .82 + 25 Worker/Oracle VMs</text>
          <text x="960" y="146" fill="#f43f5e" font-family="JetBrains Mono,monospace" font-size="11" font-weight="700">4. VLAN 10 &amp; 20 (10.0.10.0/24 &amp; .20.0/24): HPE iLO4 (.10..40), ESXi Management (.101..104) &amp; BattleStation (.137)</text>
          <text x="960" y="174" fill="#c084fc" font-family="JetBrains Mono,monospace" font-size="11" font-weight="700">5. WAN / Cloud Burst: $1,000 Anthropic Credits (Pools A-D) + OpenAI Codex GPT-6.1-Sol + Kimi + AGY</text>
        </g>
      </svg>
    </div>
    """


def build_14_thermal_flir() -> str:
    """#14: Thermal Infrared / FLIR Heat-Map Rack & Airflow View."""
    return f"""
    <div style="width:1920px;height:1034px;background:radial-gradient(circle at 35% 55%,#3b0764 0%,#1e1b4b 45%,#090514 100%);position:relative;overflow:hidden;font-family:'JetBrains Mono',monospace;">
      {_header_banner(14, "FLIR THERMAL INFRARED & AIRFLOW CFD", "Boylenet 12U Cabinet Thermal Imaging (79.5°F Intake ➔ 60–74°C Tesla T4 GPU Cores ➔ Rear Exhaust)", "FLIR IR SPECTRUM: 22°C..78°C", "#1a0933", "#f97316", "#fef08a", "#f97316")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <defs>
          <linearGradient id="flir-scale" x1="0%" y1="100%" x2="0%" y2="0%">
            <stop offset="0%" stop-color="#1e1b4b"/>
            <stop offset="25%" stop-color="#7e22ce"/>
            <stop offset="50%" stop-color="#dc2626"/>
            <stop offset="75%" stop-color="#f97316"/>
            <stop offset="90%" stop-color="#facc15"/>
            <stop offset="100%" stop-color="#ffffff"/>
          </linearGradient>
          <radialGradient id="hotspot" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#ffffff" stop-opacity="0.95"/>
            <stop offset="25%" stop-color="#facc15" stop-opacity="0.85"/>
            <stop offset="60%" stop-color="#ef4444" stop-opacity="0.55"/>
            <stop offset="100%" stop-color="#581c87" stop-opacity="0"/>
          </radialGradient>
        </defs>

        <!-- FLIR Color Scale Bar on Left -->
        <rect x="28" y="95" width="28" height="880" rx="6" fill="url(#flir-scale)" stroke="#fef08a" stroke-width="1.5"/>
        <text x="66" y="112" fill="#ffffff" font-size="11" font-weight="800">80°C (MAX)</text>
        <text x="66" y="320" fill="#facc15" font-size="11" font-weight="800">65°C (GPU)</text>
        <text x="66" y="540" fill="#f97316" font-size="11" font-weight="800">45°C (CPU)</text>
        <text x="66" y="760" fill="#a855f7" font-size="11" font-weight="800">30°C (CHASSIS)</text>
        <text x="66" y="968" fill="#38bdf8" font-size="11" font-weight="800">26.4°C / 79.5°F</text>

        <!-- Center Thermal 12U Cabinet -->
        <rect x="165" y="92" width="760" height="895" rx="10" fill="#130924" stroke="#f97316" stroke-width="2.5"/>
        <rect x="435" y="108" width="210" height="40" rx="6" fill="#090514" stroke="#ef4444" stroke-width="2"/>
        <text x="540" y="134" text-anchor="middle" fill="#ff2a2a" font-size="20" font-weight="900">BEZEL: 79.5°F (26.4°C)</text>

        <!-- Top 4U UniFi Stack Thermal Bands -->
        {''.join(f'<g transform="translate(190,{165 + i*52})"><rect width="710" height="44" rx="4" fill="#311042" stroke="#a855f7" stroke-width="1.5"/><ellipse cx="520" cy="22" rx="140" ry="18" fill="url(#hotspot)" opacity="0.65"/><text x="20" y="27" fill="#fef08a" font-size="11.5" font-weight="800">{lbl}</text><text x="610" y="27" fill="#ffffff" font-size="11" font-weight="900">{tmp}</text></g>' for i, (lbl, tmp) in enumerate([
            ("U12: UDM-Pro Gateway (.70.1)", "38.2°C / 18W"),
            ("U11: USW-Aggregation (8×10G SFP+)", "41.0°C / 22W"),
            ("U10: USW-Pro-Aggregation (280G Spine • 4×25G SFP28)", "49.4°C / 64W"),
            ("U09: USW-24-PoE + Rear USW-Pro-Max + Rear Top UPS", "44.8°C / 88W"),
        ]))}

        <!-- Bottom 8U: 4x 2U HPE ProLiant DL380 + 4x Tesla T4 Thermal Plumes -->
        {''.join(f'<g transform="translate(190,{390 + i*140})"><rect width="710" height="126" rx="6" fill="#2a0a2e" stroke="#f97316" stroke-width="2"/><ellipse cx="260" cy="63" rx="95" ry="52" fill="#38bdf8" opacity="0.25"/><ellipse cx="515" cy="63" rx="165" ry="58" fill="url(#hotspot)"/><text x="20" y="32" fill="#ffffff" font-size="13" font-weight="900">{host}</text><text x="20" y="56" fill="#67e8f9" font-size="10.5">Front Mesh Intake: 23.0°C..25.0°C (Cool Laminar Flow)</text><text x="20" y="80" fill="#fde047" font-size="11" font-weight="800">{gpu}</text><text x="20" y="104" fill="#fca5a5" font-size="10.5">{pwr}</text></g>' for i, (host, gpu, pwr) in enumerate([
            ("U08-07: esxi01 (.101 SFF) + ai-srv01 (.72)", "🔥 HOTSPOT: Tesla T4 #1 = 71.0°C (31.2W • 66% VRAM • 77.6 tok/s)", "HPE iLO4 .10 • Dual Xeon 52c = 54°C • Host Draw = 246W"),
            ("U06-05: esxi02 (.102 SFF) + aidev (.83) + Rear Pro-Max", "🔥 HOTSPOT: Tesla T4 #2 = 74.0°C (32.5W • 70% VRAM • RoCE :50052)", "HPE iLO4 .20 • Dual Xeon 52c = 56°C • Host Draw = 312W"),
            ("U04-03: esxi03 (.103 12-LFF) + ai-infer01 (.125)", "🔥 HOTSPOT: Tesla T4 #3 = 60.0°C (30.1W • 78% VRAM • Qdrant :6333)", "HPE iLO4 .30 • 4×24TB Exos = 34°C • Host Draw = 298W"),
            ("U02-01: esxi04 (.104 12-LFF) + ai-ollama01 (.228)", "🔥 HOTSPOT: Tesla T4 #4 = 73.0°C (31.1W • 81% VRAM • LiteLLM :4000)", "HPE iLO4 .40 • 4×24TB Exos = 35°C • Host Draw = 324W"),
        ]))}

        <!-- Right Side: CFD Airflow Vectors & Thermal Efficiency Breakdown -->
        <rect x="960" y="92" width="930" height="895" rx="10" fill="#160826" stroke="#f97316" stroke-width="2"/>
        <text x="990" y="132" fill="#facc15" font-size="16" font-weight="900">CFD AIRFLOW STREAMLINES &amp; POWER-TO-TOKEN EFFICIENCY MATRIX</text>
        {''.join(f'<g transform="translate(990,{160 + idx*96})"><rect width="870" height="82" rx="8" fill="#0d0417" stroke="{col}" stroke-width="1.6"/><text x="20" y="28" fill="#ffffff" font-size="13" font-weight="800">{t}</text><text x="20" y="50" fill="{col}" font-size="10.5">{s}</text><text x="20" y="70" fill="#cbd5e1" font-size="10">{m}</text><rect x="640" y="18" width="210" height="46" rx="6" fill="{col}22" stroke="{col}"/><text x="745" y="46" text-anchor="middle" fill="#ffffff" font-size="13" font-weight="900">{val}</text></g>' for idx, (t, s, m, val, col) in enumerate([
            ("Front Intake Plenum (Perforated Mesh Cages on esxi01/02)", "Ambient Room Air Drawn Through Front 12U Door", "Thermostat Sensor: 79.5°F (26.4°C) • Humidity 42% RH", "79.5°F INTAKE", "#38bdf8"),
            ("4× NVIDIA Tesla T4 GPUs (Low-Profile 70W Passive Cards)", "Cooled by HPE DL380 6-Fan High-Pressure Midplane Array", "Total GPU Power: 124.9W across all 4 cards (31.2W + 32.5W + 30.1W + 31.1W)", "0.62 tok/s/Watt", "#facc15"),
            ("12× 24TB Seagate Exos + 63× SAS/NVMe vSAN Array (75 Disks)", "LFF & SFF SmartCarrier Thermal Envelope (esxi01..04)", "Drive Temps: 32°C..37°C (Well below 60°C enterprise threshold)", "328.4 TiB @ 34°C", "#f97316"),
            ("Rear Top Rackmount UPS & Power Conditioning", "Mounted at Top of Rear Rails Above Exhaust Plume", "Total Cluster Load: 1,180W (4× ESXi + 5× UniFi Switches) • 100% Battery", "1,180W / 4026 BTU/h", "#ef4444"),
            ("8× Elastic Cold-Spare VMs (spare3..spare10 — Rule 61)", "vSphere 8.0 DRS Standby Power-Off State", "Saves 448 GB RAM & 176 vCPUs of idle thermal dissipation until load >75%", "0.0W SAVED", "#10b981"),
            ("$1,000 External Cloud Burst (Pools A/B/C/D + Codex + Kimi)", "Zero Local Thermal Footprint for Heavy-Lifter Cloud Seats", "Offloads Opus 5.5, Sonnet 5.5, Fable 5.1 & GPT-6.1-Sol to cloud datacenters", "0.0W LOCAL HEAT", "#c084fc"),
            ("BattleStation (.137) & Bittorrent (.181) External Oracles", "Separate Workstation Cooling Loops (Ryzen 9 + RTX 2080 Ti)", "VRAM 38% • CPU 19% • Zero thermal coupling to 12U server cabinet", "ISOLATED LOOP", "#22d3ee"),
            ("Infra Sentinel (:4099) Thermal & Fan Guard", "Polls HPE iLO4 (.10..40) & nvidia-smi every 15s", "Automatic workload throttling if any T4 exceeds 82°C (currently 60–74°C)", "NOMINAL <74°C", "#34d399"),
        ]))}
      </svg>
    </div>
    """


def build_15_vsan_blueprint() -> str:
    """#15: vSAN Storage Bay & Disk Group Blueprint (328.4 TiB across 75 Disks & 11 Disk Groups)."""
    hosts = [
        ("esxi01 (.20.41 • vSAN 10.0.60.21)", "2U SFF (8× 2.5\" SmartCarrier)", "1× Disk Group Tier-1 All-Flash", "1.6TB NVMe Cache + 7× 3TB SAS Capacity", "21.0 TiB Raw", "#38bdf8"),
        ("esxi02 (.20.42 • vSAN 10.0.60.22)", "2U SFF + Rear USW-Pro-Max", "1× DG Tier-0 + 2× DG Tier-1", "4× 24TB Seagate Exos + 14× 3TB SAS", "102.4 TiB Raw", "#00e5ff"),
        ("esxi03 (.20.43 • vSAN 10.0.60.23)", "2U 12-Bay 3.5\" LFF + Rear Pro-Max", "1× DG Tier-0 + 2× DG Tier-1", "4× 24TB Seagate Exos + 14× 3TB SAS", "102.5 TiB Raw", "#10b981"),
        ("esxi04 (.20.44 • vSAN 10.0.60.24)", "2U 12-Bay 3.5\" LFF (Blue UID)", "1× DG Tier-0 + 2× DG Tier-1", "4× 24TB Seagate Exos + 14× 3TB SAS", "102.5 TiB Raw", "#a855f7"),
    ]
    cards = []
    for i, (hname, chassis, dgs, backing, cap, col) in enumerate(hosts):
        x = 34 + i * 468
        disks = "".join(
            f'<rect x="{18 + (d%6)*70}" y="{165 + (d//6)*46}" width="62" height="38" rx="4" fill="#090d16" stroke="{col if d < 4 and i > 0 else "#34d399"}" stroke-width="1.4"/><text x="{49 + (d%6)*70}" y="{182 + (d//6)*46}" text-anchor="middle" fill="#f8fafc" font-size="8.5" font-weight="800">{"24T EXOS" if d < 4 and i > 0 else "3T SAS"}</text><text x="{49 + (d%6)*70}" y="{196 + (d//6)*46}" text-anchor="middle" fill="#10b981" font-size="7.5">ONLINE</text>'
            for d in range(18)
        )
        cards.append(f"""
        <g transform="translate({x}, 92)">
          <rect width="450" height="325" rx="10" fill="#0e1626" stroke="{col}" stroke-width="2"/>
          <text x="18" y="30" fill="#f8fafc" font-family="Inter,sans-serif" font-size="13.5" font-weight="900">{hname}</text>
          <text x="18" y="52" fill="{col}" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="700">{chassis} • {cap}</text>
          <text x="18" y="74" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10">{dgs}</text>
          <text x="18" y="94" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9.5">{backing}</text>
          <rect x="18" y="110" width="414" height="42" rx="6" fill="#090d16" stroke="#1e293b"/>
          <text x="30" y="135" fill="#fbbf24" font-family="JetBrains Mono,monospace" font-size="10" font-weight="800">NVMe/SAS Write Cache Tier ➔ Capacity Tier (0 Resyncs)</text>
          {disks}
        </g>
        """)

    return f"""
    <div style="width:1920px;height:1034px;background:#070b14;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(15, "VSAN 328.4 TiB STORAGE & 10TB MODEL VAULT ARCHITECT", "vSAN 8.0 All-Flash & Seagate Exos 75-Disk Blueprint (135.7 / 328.4 TiB • 41.3% Used • 11 Disk Groups)", "75/75 DISKS HEALTHY", "#0d1526", "#10b98166", "#f8fafc", "#10b981")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(cards)}
        <!-- Middle 10GbE vSAN VLAN 60 + 25GbE RoCE Crossbar Bus -->
        <rect x="34" y="440" width="1852" height="68" rx="10" fill="#052e2b" stroke="#10b981" stroke-width="2.2"/>
        <text x="960" y="468" text-anchor="middle" fill="#6ee7b7" font-family="JetBrains Mono,monospace" font-size="14" font-weight="900">VLAN 60 • 10GbE SFP+ vSAN MESH (10.0.60.21..24) + VLAN 75 • 25GbE SFP28 RoCE MODEL VAULT FABRIC</text>
        <text x="960" y="492" text-anchor="middle" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="11">Total Capacity: 328.4 TiB • Used: 135.7 TiB (41.3%) • Free: 192.7 TiB • Dedup &amp; Compression Active • 0 Bytes Resyncing</text>

        <!-- Bottom Consumer VMDK & Model Vault Allocation Map -->
        <g transform="translate(34, 530)">
          <rect x="0" y="0" width="600" height="470" rx="10" fill="#0e1626" stroke="#00e5ff" stroke-width="2"/>
          <text x="22" y="34" fill="#00e5ff" font-size="14" font-weight="900">10 TB DUAL AI MODEL VAULT (86 LOCAL MODELS)</text>
          <text x="22" y="60" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• Vault A (ai-srv01 .72): 5.0 TB VMDK (4.4 TB / 42 Models)</text>
          <text x="22" y="84" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• Vault B (aidev .83):    5.0 TB VMDK (4.5 TB / 44 Models)</text>
          <text x="22" y="114" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="10.5">Top Active Tensor Weights:</text>
          <text x="22" y="140" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="10">  1. DeepSeek-V3-0324-671B-Q4_K_M (404 GB • 77.6 tok/s)</text>
          <text x="22" y="164" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="10">  2. Kimi-K2.5-1T-A32B-GGUF       (590 GB • RoCE Split)</text>
          <text x="22" y="188" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="10">  3. MiMo-V2-Pro-1024B-GGUF       (612 GB • Vault B)</text>
          <text x="22" y="212" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="10">  4. Qwen2.5-Coder-32B-Instruct   (22 GB  • .125 GPU)</text>
          <text x="22" y="236" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="10">  5. Hermes-4-405B + GLM-5.3      (245 GB • Vault A/B)</text>
          <rect x="22" y="265" width="556" height="180" rx="8" fill="#090d16" stroke="#1e293b"/>
          <text x="40" y="295" fill="#fbbf24" font-family="JetBrains Mono,monospace" font-size="11" font-weight="800">bd-kv-warmer (:4099) Pre-Warmed Prompt Caches:</text>
          <text x="40" y="322" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="10">• FLEET_RULE-FLOOR.md + CLAUDE.md + O1740 Law pinned in RAM</text>
          <text x="40" y="346" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="10">• 0ms cold-start TTFT penalty across all 4× Tesla T4 GPUs</text>
          <text x="40" y="370" fill="#38bdf8" font-family="JetBrains Mono,monospace" font-size="10">• Instant NFS/RoCE failover between .72 and .83</text>

          <rect x="624" y="0" width="600" height="470" rx="10" fill="#0e1626" stroke="#10b981" stroke-width="2"/>
          <text x="646" y="34" fill="#10b981" font-size="14" font-weight="900">27 CLUSTER VMS &amp; QDRANT VECTOR STORAGE</text>
          <text x="646" y="62" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• Controller bd (.164): NVMe Tier-1 VMDK (WAL + Postgres + Gitea)</text>
          <text x="646" y="88" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• test3big (.82): 128 GB /dev/shm RAMdisk (Zero vSAN Write Wear!)</text>
          <text x="646" y="114" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• ai-infer01 (.125): Qdrant Vector DB (:6333) HNSW Snapshots</text>
          <text x="646" y="140" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• ai-ollama01 (.228): Langfuse (:3000) ClickHouse/Postgres Traces</text>
          <text x="646" y="166" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• Builders bd1..4 + Verifiers test1..7: Linked-Clone Worktrees</text>
          <text x="646" y="192" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• bd-vm-timecapsule: Instant vSphere Copy-on-Write Snapshots</text>

          <rect x="1248" y="0" width="604" height="470" rx="10" fill="#0e1626" stroke="#a855f7" stroke-width="2"/>
          <text x="1270" y="34" fill="#c084fc" font-size="14" font-weight="900">SYNOLOGY NAS (.199) &amp; CLOUD BURST ZERO-DISK LANE</text>
          <text x="1270" y="62" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• Synology NAS (10.0.70.199): Cold Archive &amp; Config Backups</text>
          <text x="1270" y="88" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• CAS Blob Store (/var/tmp/bd-blobs): Rule 80 Pointer Decoupling</text>
          <text x="1270" y="114" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• $1,000 Cloud Pools (A/B/C/D): Stateless API Stream ($0 Disk IO)</text>
          <text x="1270" y="140" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• Dual Browser Oracles (.137 &amp; .181): Local NVMe Scratch</text>
        </g>
      </svg>
    </div>
    """


# =============================================================================
# FAMILY 2 (#16-#20): SCI-FI & CINEMA COMMAND DECK FAMILY
# =============================================================================

def build_16_jarvis_hud() -> str:
    """#16: Iron Man JARVIS / Stark Holographic HUD."""
    cx, cy = 960, 540
    spokes = []
    for i, (name, sub, ip, badge, _, _) in enumerate(CLUSTER_NODES[:16]):
        ang = math.radians(i * (360 / 16) - 90)
        r = 355 if i % 2 == 0 else 415
        px, py = cx + r * math.cos(ang), cy + r * math.sin(ang)
        ix, iy = cx + 195 * math.cos(ang), cy + 195 * math.sin(ang)
        col = "#00f0ff" if i % 2 == 0 else "#fbbf24"
        spokes.append(f"""
        <line x1="{ix:.1f}" y1="{iy:.1f}" x2="{px:.1f}" y2="{py:.1f}" stroke="{col}" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.7"/>
        <g transform="translate({px:.1f},{py:.1f})">
          <circle cx="0" cy="0" r="24" fill="#04121c" stroke="{col}" stroke-width="2"/>
          <circle cx="0" cy="0" r="18" fill="none" stroke="{col}" stroke-width="0.8" stroke-dasharray="4,2"/>
          <rect x="-78" y="26" width="156" height="34" rx="6" fill="#041019" stroke="{col}" stroke-width="1.2" opacity="0.95"/>
          <text x="0" y="40" text-anchor="middle" fill="#ffffff" font-size="10" font-weight="800">{name}</text>
          <text x="0" y="53" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="8.5">{ip} • {badge}</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:radial-gradient(circle at 50% 52%,#08283b 0%,#030b12 65%,#010408 100%);position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(16, "STARK INDUSTRIES // J.A.R.V.I.S. HOLOGRAPHIC CORE", "Boylenet Arc-Reactor Telemetry & Autonomous Swarm Hologram (77.62 tok/s Tensor Output)", "ARC REACTOR: 100% OUTPUT", "#041521", "#00f0ff88", "#e0f2fe", "#fbbf24")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <circle cx="{cx}" cy="{cy}" r="185" fill="none" stroke="#00f0ff" stroke-width="6" stroke-dasharray="28,10" opacity="0.75"/>
        <circle cx="{cx}" cy="{cy}" r="160" fill="none" stroke="#fbbf24" stroke-width="3" stroke-dasharray="14,8" opacity="0.85"/>
        <circle cx="{cx}" cy="{cy}" r="128" fill="#041b29" stroke="#00f0ff" stroke-width="2.5"/>
        <circle cx="{cx}" cy="{cy}" r="88" fill="none" stroke="#38bdf8" stroke-width="10" stroke-dasharray="8,6" opacity="0.6"/>
        <text x="{cx}" y="{cy-18}" text-anchor="middle" fill="#00f0ff" font-family="JetBrains Mono,monospace" font-size="14" font-weight="900">J.A.R.V.I.S. // BD-164</text>
        <text x="{cx}" y="{cy+4}" text-anchor="middle" fill="#ffffff" font-size="22" font-weight="900">77.62 TOK/S</text>
        <text x="{cx}" y="{cy+26}" text-anchor="middle" fill="#fbbf24" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="800">4×T4 ROCE • 27 VMS • $1K</text>
        {''.join(spokes)}
      </svg>
    </div>
    """


def build_17_tron_grid() -> str:
    """#17: TRON Legacy Neon Grid Arena (Light-Cycle Orthogonal Traces)."""
    nodes = []
    for idx, (name, sub, ip, badge, _, _) in enumerate(CLUSTER_NODES[:20]):
        col_i = idx % 5
        row_i = idx // 5
        x = 85 + col_i * 365
        y = 135 + row_i * 215
        c = "#00f0ff" if (idx % 2 == 0) else "#ff6600"
        nodes.append(f"""
        <path d="M {x+145} {y+55} L {x+365} {y+55}" stroke="{c}" stroke-width="3" opacity="{0.8 if col_i < 4 else 0}"/>
        <path d="M {x+145} {y+55} L {x+145} {y+215}" stroke="{c}" stroke-width="2.5" opacity="{0.65 if row_i < 3 else 0}"/>
        <g transform="translate({x},{y})">
          <rect width="290" height="115" rx="2" fill="#03070e" stroke="{c}" stroke-width="2.5"/>
          <rect x="6" y="6" width="278" height="103" fill="none" stroke="{c}" stroke-width="0.7" opacity="0.5"/>
          <text x="18" y="30" fill="#ffffff" font-family="JetBrains Mono,monospace" font-size="13" font-weight="900">{name}</text>
          <text x="18" y="54" fill="{c}" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="700">{sub}</text>
          <text x="18" y="80" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="10">GRID COORD: {ip}</text>
          <rect x="18" y="88" width="254" height="16" fill="{c}22"/>
          <text x="24" y="99" fill="#ffffff" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="800">LIGHT-CYCLE STREAM: {badge}</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#020408;position:relative;overflow:hidden;font-family:'JetBrains Mono',monospace;">
      {_header_banner(17, "ENCOM // TRON LEGACY LIGHT-CYCLE GRID", "Boylenet Orthogonal Light-Cycle Routing Arena (Blue User Team = Local Fabric vs Orange = Cloud/Oracles)", "THE GRID: 280 Gbps", "#040a14", "#00f0ff", "#ffffff", "#ff6600")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <defs>
          <pattern id="tron-p" width="48" height="48" patternUnits="userSpaceOnUse">
            <path d="M 48 0 L 0 0 0 48" fill="none" stroke="#082f49" stroke-width="1"/>
          </pattern>
        </defs>
        <rect width="1920" height="1034" fill="url(#tron-p)"/>
        {''.join(nodes)}
      </svg>
    </div>
    """


def build_18_lcars_startrek() -> str:
    """#18: Star Trek LCARS Enterprise Engineering Deck."""
    lcars_colors = ["#ff9900", "#ffcc99", "#cc99cc", "#9999ff", "#ff6666", "#ffaa00"]
    pills = []
    for idx, (name, sub, ip, badge, _, _) in enumerate(CLUSTER_NODES[:24]):
        col_i = idx % 4
        row_i = idx // 4
        x = 310 + col_i * 390
        y = 145 + row_i * 138
        c = lcars_colors[idx % len(lcars_colors)]
        pills.append(f"""
        <g transform="translate({x},{y})">
          <rect width="365" height="114" rx="28" fill="#080811" stroke="{c}" stroke-width="3"/>
          <path d="M 28 0 L 95 0 L 95 114 L 28 114 A 28 28 0 0 1 0 86 L 0 28 A 28 28 0 0 1 28 0 Z" fill="{c}"/>
          <text x="48" y="54" text-anchor="middle" fill="#000000" font-family="Inter,sans-serif" font-size="16" font-weight="900">{idx+101}</text>
          <text x="48" y="74" text-anchor="middle" fill="#000000" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="800">LCARS</text>
          <text x="112" y="34" fill="{c}" font-family="Inter,sans-serif" font-size="14" font-weight="900">{name.upper()}</text>
          <text x="112" y="58" fill="#f8fafc" font-family="JetBrains Mono,monospace" font-size="10.5">{sub}</text>
          <text x="112" y="82" fill="#ffcc99" font-family="JetBrains Mono,monospace" font-size="10">{ip} // {badge}</text>
          <line x1="112" y1="95" x2="335" y2="95" stroke="{c}" stroke-width="4" opacity="0.6"/>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#000000;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      <!-- Signature LCARS Swept Top-Left Elbow Frame -->
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <path d="M 24 20 L 260 20 L 260 95 L 1890 95 L 1890 118 L 260 118 L 260 995 L 24 995 Z" fill="#ff9900" opacity="0.92"/>
        <rect x="280" y="20" width="1610" height="62" rx="31" fill="#141424" stroke="#ffcc99" stroke-width="2"/>
        <text x="315" y="58" fill="#ff9900" font-size="22" font-weight="900" letter-spacing="2">LCARS 4088 // USS BOYLENET MAIN ENGINEERING &amp; WARP TENSOR CORE</text>
        <text x="1480" y="58" fill="#cc99cc" font-family="JetBrains Mono,monospace" font-size="14" font-weight="800">STARDATE 2026.10 // 77.6 TOK/S</text>
        <!-- Left LCARS Status Stack Labels -->
        <text x="142" y="180" text-anchor="middle" fill="#000" font-size="14" font-weight="900">WARP CORE: 4×T4</text>
        <text x="142" y="290" text-anchor="middle" fill="#000" font-size="14" font-weight="900">SPINE: 280G</text>
        <text x="142" y="400" text-anchor="middle" fill="#000" font-size="14" font-weight="900">VSAN: 328.4 TiB</text>
        <text x="142" y="510" text-anchor="middle" fill="#000" font-size="14" font-weight="900">RACK: 79.5°F</text>
        <text x="142" y="620" text-anchor="middle" fill="#000" font-size="14" font-weight="900">VMS: 27 ONLINE</text>
        <text x="142" y="730" text-anchor="middle" fill="#000" font-size="14" font-weight="900">CLOUD: $1,000</text>
        <text x="142" y="840" text-anchor="middle" fill="#000" font-size="14" font-weight="900">SHIELDS: 83/83</text>
        {''.join(pills)}
      </svg>
    </div>
    """


def build_19_oblivion_light_table() -> str:
    """#19: Minority Report / Oblivion Light-Table Surgical White/Ice-Blue UI."""
    cards = []
    for idx, (name, sub, ip, badge, _, _) in enumerate(CLUSTER_NODES[:25]):
        c_i = idx % 5
        r_i = idx // 5
        x = 45 + c_i * 370
        y = 110 + r_i * 176
        cards.append(f"""
        <g transform="translate({x},{y})">
          <rect width="345" height="148" rx="4" fill="#ffffff" stroke="#0284c7" stroke-width="1.5"/>
          <line x1="0" y1="34" x2="345" y2="34" stroke="#cbd5e1" stroke-width="1"/>
          <circle cx="18" cy="17" r="4.5" fill="#0284c7"/>
          <text x="32" y="22" fill="#0f172a" font-family="Inter,sans-serif" font-size="12.5" font-weight="900">{name}</text>
          <text x="330" y="22" text-anchor="end" fill="#0284c7" font-family="JetBrains Mono,monospace" font-size="10" font-weight="800">SEC-{idx+1:02d}</text>
          <text x="18" y="60" fill="#334155" font-family="Inter,sans-serif" font-size="11.5" font-weight="600">{sub}</text>
          <text x="18" y="88" fill="#0369a1" font-family="JetBrains Mono,monospace" font-size="11" font-weight="700">VECTOR: {ip}</text>
          <rect x="18" y="104" width="309" height="28" rx="3" fill="#f0f9ff" stroke="#bae6fd"/>
          <text x="28" y="122" fill="#0c4a6e" font-family="JetBrains Mono,monospace" font-size="10" font-weight="800">STATUS // {badge} • NOMINAL</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#e2e8f0;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(19, "OBLIVION TET // SURGICAL DAYLIGHT LIGHT-TABLE", "Boylenet High-Key Surgical Vector Telemetry Table (Zero-Glare Alabaster & Ice-Cyan Precision Grid)", "SURGICAL LIGHT-TABLE", "#ffffff", "#0284c7", "#0f172a", "#0284c7")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <defs>
          <pattern id="ob-grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#cbd5e1" stroke-width="0.9"/>
          </pattern>
        </defs>
        <rect width="1920" height="1034" fill="url(#ob-grid)"/>
        {''.join(cards)}
      </svg>
    </div>
    """


def build_20_crt_phosphor() -> str:
    """#20: Alien / Weyland-Yutani MU/TH/UR 6000 CRT Phosphor Green Terminal."""
    rows = []
    for idx, (name, sub, ip, badge, _, _) in enumerate(CLUSTER_NODES[:25]):
        c_i = idx % 5
        r_i = idx // 5
        x = 42 + c_i * 370
        y = 115 + r_i * 174
        rows.append(f"""
        <g transform="translate({x},{y})">
          <rect width="348" height="150" fill="#021206" stroke="#00ff66" stroke-width="1.8"/>
          <rect x="6" y="6" width="336" height="24" fill="#00ff66" fill-opacity="0.18"/>
          <text x="14" y="22" fill="#00ff66" font-size="12" font-weight="900">[{idx+1:02d}] {name.upper()}</text>
          <text x="14" y="54" fill="#4ade80" font-size="10.5">&gt; ROLE: {sub}</text>
          <text x="14" y="78" fill="#4ade80" font-size="10.5">&gt; ADDR: {ip}</text>
          <text x="14" y="102" fill="#bbf7d0" font-size="10.5" font-weight="700">&gt; TELEM: {badge}</text>
          <text x="14" y="130" fill="#00ff66" font-size="9.5">████████████████████ 100% ONLINE</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#010903;position:relative;overflow:hidden;font-family:'JetBrains Mono',monospace;">
      {_header_banner(20, "WEYLAND-YUTANI // MU/TH/UR 6000 CRT PHOSPHOR MAINFRAME", "INTERFACE 2037 // BOYLENET 27-NODE & 12U RACK CRT VECTOR OSCILLOSCOPE", "CRT P31 GREEN PHOSPHOR", "#021808", "#00ff66", "#00ff66", "#00ff66")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(rows)}
      </svg>
    </div>
    """


# =============================================================================
# FAMILY 3 (#21-#25): MODERN CLOUD & DEVOPS CANVAS FAMILY
# =============================================================================

def build_21_datadog_apm() -> str:
    """#21: Datadog Live Service Map & APM Flame-Flow."""
    circles = []
    for idx, (name, sub, ip, badge, col, _) in enumerate(CLUSTER_NODES[:24]):
        c_i = idx % 6
        r_i = idx // 6
        cx = 175 + c_i * 310
        cy = 185 + r_i * 195
        circles.append(f"""
        <g transform="translate({cx},{cy})">
          <line x1="0" y1="0" x2="{min(310, 1920-cx)}" y2="0" stroke="#632ca6" stroke-width="2" stroke-dasharray="5,4" opacity="{0.6 if c_i < 5 else 0}"/>
          <circle cx="0" cy="0" r="54" fill="#161224" stroke="#2e2640" stroke-width="6"/>
          <circle cx="0" cy="0" r="54" fill="none" stroke="{col}" stroke-width="5" stroke-dasharray="260,80"/>
          <circle cx="0" cy="0" r="42" fill="#0e0b16" stroke="#a855f7" stroke-width="1"/>
          <text x="0" y="-6" text-anchor="middle" fill="#f8fafc" font-family="Inter,sans-serif" font-size="10.5" font-weight="800">{name[:15]}</text>
          <text x="0" y="9" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">{badge}</text>
          <text x="0" y="23" text-anchor="middle" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="8">p99: 0.4ms</text>
          <rect x="-85" y="60" width="170" height="22" rx="6" fill="#161224" stroke="#632ca6"/>
          <text x="0" y="75" text-anchor="middle" fill="#e9d5ff" font-family="JetBrains Mono,monospace" font-size="9">{sub[:24]}</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#0b0813;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(21, "DATADOG APM SERVICE MAP & DISTRIBUTED TRACING", "Boylenet Service Mesh & Langfuse/LiteLLM APM Latency Rings (0% Error Rate Across 83 Services)", "APM P99: 0.18ms..12ms", "#181028", "#a855f7", "#f8fafc", "#a855f7")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(circles)}
      </svg>
    </div>
    """


def build_22_grafana_sparklines() -> str:
    """#22: Grafana Node-Graph + Embedded 60s Real-Time Area Sparkline Cards."""
    cards = []
    for idx, (name, sub, ip, badge, col, _) in enumerate(CLUSTER_NODES[:25]):
        c_i = idx % 5
        r_i = idx // 5
        x = 38 + c_i * 372
        y = 95 + r_i * 182
        # Generate deterministic wave points for the embedded sparkline
        pts = []
        for s in range(12):
            sx = 14 + s * 29
            sy = 128 - int(18 + 16 * abs(math.sin(idx * 0.9 + s * 0.55)))
            pts.append(f"{sx},{sy}")
        poly = f"14,142 {' '.join(pts)} 333,142"
        line = " ".join(pts)
        cards.append(f"""
        <g transform="translate({x},{y})">
          <rect width="352" height="164" rx="8" fill="#111217" stroke="#2c3235" stroke-width="1.6"/>
          <rect width="352" height="4" fill="{col}"/>
          <text x="16" y="26" fill="#f8fafc" font-size="13" font-weight="800">{name}</text>
          <text x="336" y="26" text-anchor="end" fill="{col}" font-family="JetBrains Mono,monospace" font-size="11" font-weight="800">{badge}</text>
          <text x="16" y="46" fill="#94a3b8" font-size="10.5">{sub} • <tspan fill="#cbd5e1">{ip}</tspan></text>
          <polygon points="{poly}" fill="{col}" opacity="0.22"/>
          <polyline points="{line}" fill="none" stroke="{col}" stroke-width="2.2"/>
          <text x="16" y="156" fill="#64748b" font-family="JetBrains Mono,monospace" font-size="8.5">60s Prometheus Scrape (:9090) • 100% UP</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#0b0c0e;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(22, "GRAFANA ENTERPRISE NODE-GRAPH & SPARKLINE WALL", "25 Live Prometheus/cAdvisor Telemetry Panels with Embedded 60s CPU/VRAM/Bandwidth Sparklines", "PROMETHEUS :9090 LIVE", "#141619", "#f97316", "#f8fafc", "#f97316")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(cards)}
      </svg>
    </div>
    """


def build_23_terraform_dag() -> str:
    """#23: AWS CloudFormation / Terraform Infrastructure-as-Code Dependency DAG."""
    nodes = []
    for idx, (name, sub, ip, badge, col, rtype) in enumerate(CLUSTER_NODES[:25]):
        c_i = idx // 5
        r_i = idx % 5
        x = 45 + c_i * 372
        y = 105 + r_i * 178
        if c_i < 4:
            nodes.append(f'<path d="M {x+340} {y+74} C {x+356} {y+74}, {x+356} {y+74}, {x+372} {y+74}" stroke="#10b981" stroke-width="2" fill="none"/>')
        nodes.append(f"""
        <g transform="translate({x},{y})">
          <rect width="340" height="150" rx="8" fill="#0f172a" stroke="#334155" stroke-width="1.8"/>
          <rect x="0" y="0" width="340" height="32" rx="8" fill="#1e293b"/>
          <text x="14" y="21" fill="#38bdf8" font-family="JetBrains Mono,monospace" font-size="10" font-weight="800">boylenet_{rtype}.{name.split()[0].lower().replace('-','_')}</text>
          <text x="326" y="21" text-anchor="end" fill="#10b981" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="900">✓ APPLIED</text>
          <text x="16" y="60" fill="#f8fafc" font-size="13.5" font-weight="800">{name}</text>
          <text x="16" y="84" fill="#94a3b8" font-size="11">{sub}</text>
          <text x="16" y="110" fill="{col}" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="700">ipv4 = "{ip}" • state = "{badge}"</text>
          <text x="16" y="134" fill="#64748b" font-family="JetBrains Mono,monospace" font-size="9">drift_status = "IN_SYNC" • O1789</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#060a12;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(23, "TERRAFORM / CLOUDFORMATION DECLARATIVE DAG", "Boylenet Infrastructure-as-Code Resource Dependency Graph (0 Drift • 32 DNS • 27 VMs • 12U Rack)", "STATE: 100% APPLIED", "#0f172a", "#8b5cf6", "#f8fafc", "#8b5cf6")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(nodes)}
      </svg>
    </div>
    """


def build_24_cilium_service_mesh() -> str:
    """#24: Kubernetes / Cilium Hubble eBPF Service Mesh Map (VLAN Namespace Isolation)."""
    zones = [
        (36, 95, 910, 435, "NAMESPACE: vlan75-roce-tensor (10.0.75.0/24 • 25GbE SFP28 RDMA)", "#00e5ff", CLUSTER_NODES[10:14]),
        (974, 95, 910, 435, "NAMESPACE: vlan10-20-60-hardware-rack (12U Rack • 4×ESXi • 328TiB vSAN)", "#3b82f6", CLUSTER_NODES[0:10][:6]),
        (36, 555, 910, 445, "NAMESPACE: vlan70-swarm-compute (Controller .164 • 64c Ramdisk .82 • 25 VMs)", "#10b981", CLUSTER_NODES[14:22]),
        (974, 555, 910, 445, "NAMESPACE: external-cloud-burst ($1,000 Credits • Pools A-D • Codex • Kimi • AGY)", "#a855f7", CLUSTER_NODES[22:25] + CLUSTER_NODES[6:9]),
    ]
    z_svg = []
    for zx, zy, zw, zh, ztitle, zcol, zitems in zones:
        inner = []
        for i, (n, s, ip, b, c, _) in enumerate(zitems[:6]):
            ix = zx + 24 + (i % 3) * 292
            iy = zy + 58 + (i // 3) * 175
            inner.append(f"""
            <g transform="translate({ix},{iy})">
              <rect width="272" height="152" rx="10" fill="#0b111e" stroke="{c}" stroke-width="1.8"/>
              <text x="16" y="28" fill="#f8fafc" font-size="13" font-weight="800">{n}</text>
              <text x="16" y="52" fill="#94a3b8" font-size="10.5">{s}</text>
              <text x="16" y="78" fill="{c}" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="700">pod_ip: {ip}</text>
              <rect x="16" y="96" width="240" height="38" rx="6" fill="#060911" stroke="#1e293b"/>
              <text x="26" y="119" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="700">eBPF VERDICT: FORWARDED ({b})</text>
            </g>
            """)
        z_svg.append(f"""
        <rect x="{zx}" y="{zy}" width="{zw}" height="{zh}" rx="14" fill="{zcol}0c" stroke="{zcol}" stroke-width="2" stroke-dasharray="10,5"/>
        <text x="{zx+24}" y="{zy+34}" fill="{zcol}" font-family="JetBrains Mono,monospace" font-size="13" font-weight="900">{ztitle}</text>
        {''.join(inner)}
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#050811;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(24, "CILIUM HUBBLE eBPF SERVICE MESH & VLAN SEGMENTATION", "Zero-Trust L3/L4/L7 VLAN & Namespace Flow Verdicts Across Boylenet (100% FORWARDED • 0 DROPS)", "eBPF XDP LINE-RATE", "#0b1120", "#00e5ff", "#f8fafc", "#10b981")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(z_svg)}
      </svg>
    </div>
    """


def build_25_linear_vercel_mono() -> str:
    """#25: Linear / Vercel Ultra-Minimal Monochrome Dark (#000000 + #262626 1px Borders)."""
    cards = []
    for idx, (name, sub, ip, badge, col, _) in enumerate(CLUSTER_NODES[:25]):
        c_i = idx % 5
        r_i = idx // 5
        x = 38 + c_i * 372
        y = 95 + r_i * 182
        cards.append(f"""
        <g transform="translate({x},{y})">
          <rect width="354" height="164" rx="10" fill="#080808" stroke="#262626" stroke-width="1.2"/>
          <circle cx="22" cy="26" r="4" fill="{col}"/>
          <text x="34" y="30" fill="#fafafa" font-size="13.5" font-weight="700" letter-spacing="-0.3">{name}</text>
          <text x="336" y="30" text-anchor="end" fill="#71717a" font-family="JetBrains Mono,monospace" font-size="10">{ip}</text>
          <text x="22" y="64" fill="#a1a1aa" font-size="11.5">{sub}</text>
          <line x1="22" y1="108" x2="332" y2="108" stroke="#18181b" stroke-width="1"/>
          <text x="22" y="136" fill="#e4e4e7" font-family="JetBrains Mono,monospace" font-size="11" font-weight="600">{badge}</text>
          <text x="332" y="136" text-anchor="end" fill="#52525b" font-family="JetBrains Mono,monospace" font-size="10">0.18ms</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#000000;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(25, "LINEAR / VERCEL GEIST MONOCHROME PRECISION", "Boylenet Zero-Noise Monochrome Architecture Grid (Pure #000000 Canvas • 1px Hairlines)", "GEIST MONO DARK", "#09090b", "#27272a", "#fafafa", "#ffffff")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(cards)}
      </svg>
    </div>
    """


# =============================================================================
# FAMILY 4 (#26-#30): BIOLOGICAL, NEURAL & PHYSICS GRAPH FAMILY
# =============================================================================

def build_26_neural_synapse() -> str:
    """#26: 3D Brain Synapse & Neural Cortex Network."""
    neurons = []
    synapses = []
    coords = []
    for idx, (name, sub, ip, badge, col, _) in enumerate(CLUSTER_NODES[:24]):
        ang = idx * 0.65
        rad = 110 + (idx % 4) * 105
        nx = 960 + rad * math.cos(ang) * 1.65
        ny = 540 + rad * math.sin(ang) * 0.88
        coords.append((nx, ny, col))
        if idx > 0:
            px, py, _ = coords[idx - 1]
            synapses.append(f'<path d="M {px:.1f} {py:.1f} Q 960 540 {nx:.1f} {ny:.1f}" stroke="{col}" stroke-width="1.6" fill="none" opacity="0.45"/>')
        neurons.append(f"""
        <g transform="translate({nx:.1f},{ny:.1f})">
          <circle cx="0" cy="0" r="30" fill="{col}" opacity="0.16"/>
          <circle cx="0" cy="0" r="14" fill="#0b071a" stroke="{col}" stroke-width="2.5"/>
          <circle cx="0" cy="0" r="5" fill="#ffffff"/>
          <rect x="-82" y="18" width="164" height="32" rx="8" fill="#070412" stroke="{col}" stroke-width="1"/>
          <text x="0" y="32" text-anchor="middle" fill="#f8fafc" font-size="10" font-weight="800">{name}</text>
          <text x="0" y="44" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="8.5">{badge} • {ip}</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:radial-gradient(circle at 50% 50%,#1f093d 0%,#090414 65%,#030108 100%);position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(26, "BIOLOGICAL NEURAL CORTEX & SYNAPTIC CONNECTOME", "Boylenet Swarm Connectome (Action Potentials Firing Between Controller .164, 4×T4 GPUs & 27 VMs)", "SYNAPTIC RATE: 77.6 Hz", "#120726", "#e879f9", "#f8fafc", "#e879f9")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(synapses)}
        {''.join(neurons)}
      </svg>
    </div>
    """


def build_27_magnetic_dipole() -> str:
    """#27: Particle Fluid / Magnetic Field Lines Visualizer."""
    lines = []
    for k in range(-9, 10):
        cy_ctrl = 540 + k * 56
        col = "#00e5ff" if abs(k) < 4 else ("#a855f7" if k < 0 else "#10b981")
        lines.append(f'<path d="M 240 540 Q 960 {cy_ctrl} 1680 540" stroke="{col}" stroke-width="2.2" fill="none" stroke-dasharray="10,5" opacity="0.65"/>')
    cards = []
    for idx, (name, sub, ip, badge, col, _) in enumerate(CLUSTER_NODES[:18]):
        x = 360 + (idx % 6) * 205
        y = 140 + (idx // 6) * 320
        cards.append(f"""
        <g transform="translate({x},{y})">
          <rect width="188" height="92" rx="10" fill="#070d19" stroke="{col}" stroke-width="1.8"/>
          <text x="94" y="28" text-anchor="middle" fill="#f8fafc" font-size="11.5" font-weight="800">{name}</text>
          <text x="94" y="50" text-anchor="middle" fill="#94a3b8" font-size="9.5">{sub}</text>
          <text x="94" y="72" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="700">{ip} • {badge}</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#040811;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(27, "MAGNETOHYDRODYNAMIC DIPOLE FLUX STREAMLINES", "Left Pole ($1,000 Cloud & Command .164) ➔ Magnetic Tensor Flux ➔ Right Pole (4×T4 GPUs & 12U Rack)", "FLUX DENSITY: 280 Gbps", "#081226", "#00e5ff", "#f8fafc", "#00e5ff")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(lines)}
        <circle cx="210" cy="540" r="85" fill="#1e1b4b" stroke="#c084fc" stroke-width="4"/>
        <text x="210" y="535" text-anchor="middle" fill="#ffffff" font-size="14" font-weight="900">NORTH POLE</text>
        <text x="210" y="555" text-anchor="middle" fill="#c084fc" font-size="10" font-weight="700">COMMAND + $1K CLOUD</text>
        <circle cx="1710" cy="540" r="85" fill="#042f2e" stroke="#00e5ff" stroke-width="4"/>
        <text x="1710" y="535" text-anchor="middle" fill="#ffffff" font-size="14" font-weight="900">SOUTH POLE</text>
        <text x="1710" y="555" text-anchor="middle" fill="#00e5ff" font-size="10" font-weight="700">4×T4 ROCE + 12U RACK</text>
        {''.join(cards)}
      </svg>
    </div>
    """


def build_28_dna_double_helix() -> str:
    """#28: DNA Double-Helix Dual-Vault Bridge (Vault A .72 intertwined with Vault B .83)."""
    rungs = []
    pts_a = []
    pts_b = []
    for i in range(25):
        x = 80 + i * 73
        ang = i * 0.48
        ya = 535 + math.sin(ang) * 250
        yb = 535 - math.sin(ang) * 250
        pts_a.append(f"{x:.1f},{ya:.1f}")
        pts_b.append(f"{x:.1f},{yb:.1f}")
        name, sub, ip, badge, col, _ = CLUSTER_NODES[i % len(CLUSTER_NODES)]
        rungs.append(f"""
        <line x1="{x:.1f}" y1="{ya:.1f}" x2="{x:.1f}" y2="{yb:.1f}" stroke="{col}" stroke-width="2.5" opacity="0.75"/>
        <circle cx="{x:.1f}" cy="{ya:.1f}" r="9" fill="#00e5ff" stroke="#041019" stroke-width="2"/>
        <circle cx="{x:.1f}" cy="{yb:.1f}" r="9" fill="#ec4899" stroke="#041019" stroke-width="2"/>
        <rect x="{x-62:.1f}" y="{(ya+yb)/2 - 22 + (i%3 - 1)*75:.1f}" width="124" height="36" rx="6" fill="#080d1a" stroke="{col}" stroke-width="1.2"/>
        <text x="{x:.1f}" y="{(ya+yb)/2 - 7 + (i%3 - 1)*75:.1f}" text-anchor="middle" fill="#f8fafc" font-size="9.5" font-weight="800">{name[:16]}</text>
        <text x="{x:.1f}" y="{(ya+yb)/2 + 7 + (i%3 - 1)*75:.1f}" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="8">{badge}</text>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#050812;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(28, "GENOMIC DOUBLE-HELIX DUAL-VAULT TOPOLOGY", "Strand A (5TB Vault A on ai-srv01 .72) Intertwined with Strand B (5TB Vault B on aidev .83 :50052)", "86 MODELS // 10 TB DNA", "#0b1124", "#ec4899", "#f8fafc", "#00e5ff")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <polyline points="{' '.join(pts_a)}" fill="none" stroke="#00e5ff" stroke-width="5"/>
        <polyline points="{' '.join(pts_b)}" fill="none" stroke="#ec4899" stroke-width="5"/>
        {''.join(rungs)}
      </svg>
    </div>
    """


def build_29_nbody_gravity() -> str:
    """#29: Gravitational N-Body Orbital Physics Map (Mass-scaled nodes with orbiting moons)."""
    wells = [
        (360, 320, 74, "ai-srv01 (.72)", "320G RAM • T4 • 5TB A", "77.6 tok/s", "#00e5ff", ["DeepSeek-671B", "Kimi-K2.5", "RoCE .75.11"]),
        (960, 320, 82, "Controller bd (.164)", "Swarm Command Nexus", "32 Web UIs", "#fbbf24", ["bd-pm-B", "AGY-Council", "Traefik :80", "Sentinel :4099"]),
        (1560, 320, 76, "aidev (.83)", "386G RAM • T4 • 5TB B", "RPC :50052", "#00e5ff", ["MiMo-1024B", "GLM-5.3", "RoCE .75.12"]),
        (360, 760, 68, "4× HPE DL380 ESXi", "656 vCPUs • 1.73 TiB", "328.4 TiB vSAN", "#3b82f6", ["esxi01 SFF", "esxi02 SFF", "esxi03 LFF", "esxi04 LFF"]),
        (960, 760, 68, "test3big (.82) + 22 VMs", "64c 128G /dev/shm CI", "19 ON / 8 DRS", "#10b981", ["bd1..bd4", "test1..test7", "fresh149", "spare1..10"]),
        (1560, 760, 70, "$1,000 Cloud + Oracles", "Pools A-D + .137/.181", "$0 Overage", "#c084fc", ["Pool A/B $500", "Pool C/D $500", "Codex Sol", "CDP :9222"]),
    ]
    svg_out = []
    for wx, wy, wr, wtitle, wsub, wval, wcol, moons in wells:
        svg_out.append(f'<circle cx="{wx}" cy="{wy}" r="{wr+68}" fill="none" stroke="{wcol}" stroke-width="1.2" stroke-dasharray="5,4" opacity="0.45"/>')
        svg_out.append(f'<circle cx="{wx}" cy="{wy}" r="{wr}" fill="#0a1020" stroke="{wcol}" stroke-width="3"/>')
        svg_out.append(f'<text x="{wx}" y="{wy-8}" text-anchor="middle" fill="#f8fafc" font-size="13" font-weight="900">{wtitle}</text>')
        svg_out.append(f'<text x="{wx}" y="{wy+10}" text-anchor="middle" fill="#94a3b8" font-size="9.5">{wsub}</text>')
        svg_out.append(f'<text x="{wx}" y="{wy+26}" text-anchor="middle" fill="{wcol}" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="800">{wval}</text>')
        for m_i, m_name in enumerate(moons):
            ang = math.radians(m_i * (360 / len(moons)) - 35)
            mx = wx + (wr + 68) * math.cos(ang)
            my = wy + (wr + 68) * math.sin(ang)
            svg_out.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="8" fill="{wcol}"/><rect x="{mx-54:.1f}" y="{my+11:.1f}" width="108" height="20" rx="5" fill="#060913" stroke="{wcol}"/><text x="{mx:.1f}" y="{my+24:.1f}" text-anchor="middle" fill="#ffffff" font-size="9" font-weight="700">{m_name}</text>')
    return f"""
    <div style="width:1920px;height:1034px;background:#040711;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(29, "GRAVITATIONAL N-BODY MASS & ORBITAL TELEMETRY", "6 High-Mass Compute/Storage Gravity Wells with Orbiting Agent & Microservice Moons", "TOTAL MASS: 1.73 TiB RAM + 328.4 TiB", "#0a1022", "#fbbf24", "#f8fafc", "#fbbf24")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(svg_out)}
      </svg>
    </div>
    """


def build_30_circos_chord() -> str:
    """#30: Circos / Chord Diagram Circular Ribbon Wheel."""
    cx, cy, r = 960, 545, 375
    n = len(CLUSTER_NODES)
    chords = []
    labels = []
    pts = []
    for i, (name, sub, ip, badge, col, _) in enumerate(CLUSTER_NODES):
        ang = math.radians(i * (360 / n) - 90)
        px = cx + r * math.cos(ang)
        py = cy + r * math.sin(ang)
        pts.append((px, py, col))
        lx = cx + (r + 88) * math.cos(ang)
        ly = cy + (r + 88) * math.sin(ang)
        labels.append(f"""
        <circle cx="{px:.1f}" cy="{py:.1f}" r="9" fill="{col}" stroke="#060913" stroke-width="2"/>
        <rect x="{lx-78:.1f}" y="{ly-16:.1f}" width="156" height="32" rx="6" fill="#0b1120" stroke="{col}" stroke-width="1.2"/>
        <text x="{lx:.1f}" y="{ly-2:.1f}" text-anchor="middle" fill="#f8fafc" font-size="9.5" font-weight="800">{name}</text>
        <text x="{lx:.1f}" y="{ly+11:.1f}" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="8">{ip} • {badge}</text>
        """)
    for i in range(n):
        x1, y1, c1 = pts[i]
        for target in [(i + 5) % n, (i + 11) % n]:
            x2, y2, _ = pts[target]
            chords.append(f'<path d="M {x1:.1f} {y1:.1f} Q {cx} {cy} {x2:.1f} {y2:.1f}" stroke="{c1}" stroke-width="3.5" fill="none" opacity="0.28"/>')
    return f"""
    <div style="width:1920px;height:1034px;background:#050811;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(30, "CIRCOS GENOMIC CHORD RIBBON DIAGRAM", "360° Precision Interconnect Wheel Across All 27 VMs, 4×T4 GPUs, 12U Rack & $1,000 Cloud Pools", "360° BÉZIER CHORD MATRIX", "#0c1224", "#c084fc", "#f8fafc", "#00e5ff")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#334155" stroke-width="14"/>
        {''.join(chords)}
        {''.join(labels)}
      </svg>
    </div>
    """


# =============================================================================
# FAMILY 5 (#31-#35): DEDICATED MILITARY C4ISR, ANDURIL LATTICE, AEGIS CIC,
#                     F-35 FLIR HUD, NORAD WOPR & TACTICAL 12U RACK C4ISR
# =============================================================================

def build_31_military_anduril_lattice() -> str:
    """#31 (also military_01): Anduril Lattice / Palantir Maven Autonomous Swarm C2 (MIL-STD-2525D)."""
    units = []
    for idx, (name, sub, ip, badge, _, rtype) in enumerate(CLUSTER_NODES[:20]):
        c_i = idx % 5
        r_i = idx // 5
        x = 65 + c_i * 365
        y = 135 + r_i * 210
        is_air = rtype in ("cloud", "oracle")
        col = "#38bdf8" if not is_air else "#fbbf24"
        echelon = "XXXX" if "164" in ip else ("XXX" if rtype == "gpu" else ("XX" if rtype == "esxi" else "II"))
        units.append(f"""
        <g transform="translate({x},{y})">
          <!-- Tactical Grid Reticle -->
          <rect width="318" height="162" fill="#09130f" stroke="{col}" stroke-width="1.8"/>
          <path d="M -5 12 L -5 -5 L 12 -5 M 306 -5 L 323 -5 L 323 12 M -5 150 L -5 167 L 12 167 M 306 167 L 323 167 L 323 150" fill="none" stroke="#10b981" stroke-width="2"/>
          <!-- MIL-STD-2525D Friendly Unit Symbol Box -->
          <text x="42" y="18" text-anchor="middle" fill="{col}" font-size="9" font-weight="900">{echelon}</text>
          <rect x="18" y="22" width="48" height="32" fill="{col}22" stroke="{col}" stroke-width="2"/>
          <line x1="18" y1="22" x2="66" y2="54" stroke="{col}" stroke-width="1.2"/>
          <line x1="66" y1="22" x2="18" y2="54" stroke="{col}" stroke-width="1.2"/>
          <text x="80" y="34" fill="#ecfdf5" font-size="12.5" font-weight="900">{name.upper()}</text>
          <text x="80" y="52" fill="#6ee7b7" font-size="10">{sub}</text>
          <line x1="14" y1="68" x2="304" y2="68" stroke="#1e3a2f" stroke-width="1"/>
          <text x="16" y="90" fill="#a7f3d0" font-size="10">MGRS: 38S MK {70000+idx*117} // IP: {ip}</text>
          <text x="16" y="112" fill="{col}" font-size="10.5" font-weight="800">COMBAT STATUS: {badge} • WEAPONS FREE</text>
          <rect x="16" y="124" width="286" height="24" fill="#040907" stroke="#10b98166"/>
          <text x="26" y="140" fill="#10b981" font-size="9.5" font-weight="800">AUTONOMY LINK: LOCKED • 79.5°F RACK</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#050a08;position:relative;overflow:hidden;font-family:'JetBrains Mono',monospace;">
      {_header_banner(31, "MILITARY C4ISR #1 // ANDURIL LATTICE & PALANTIR MAVEN SWARM C2", "MIL-STD-2525D Friendly Force Symbology, Autonomous Swarm Tasking & MGRS Tactical Grid", "DEFCON 5 // FORCE AUTONOMY ENABLED", "#091410", "#10b981", "#ecfdf5", "#10b981")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <defs>
          <pattern id="mil-grid" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M 60 0 L 0 0 0 60" fill="none" stroke="#0d2118" stroke-width="1"/>
          </pattern>
        </defs>
        <rect width="1920" height="1034" fill="url(#mil-grid)"/>
        {''.join(units)}
      </svg>
    </div>
    """


def build_32_military_aegis_cic() -> str:
    """#32 (also military_02): US Navy AEGIS Combat Information Center (CIC) AN/SPY-6 Radar."""
    cx, cy = 960, 545
    tracks = []
    for idx, (name, sub, ip, badge, _, rtype) in enumerate(CLUSTER_NODES[:22]):
        ang = math.radians(idx * (360 / 22) - 90)
        r = 165 if rtype == "gpu" else (285 if rtype in ("esxi", "core") else 405)
        tx = cx + r * math.cos(ang)
        ty = cy + r * math.sin(ang)
        col = "#00f0ff" if rtype != "cloud" else "#fbbf24"
        tracks.append(f"""
        <line x1="{cx}" y1="{cy}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="#00f0ff" stroke-width="0.9" stroke-dasharray="4,4" opacity="0.4"/>
        <g transform="translate({tx:.1f},{ty:.1f})">
          <!-- NTDS Friendly Surface/Air Track Symbol -->
          <circle cx="0" cy="0" r="14" fill="#020c1b" stroke="{col}" stroke-width="2.2"/>
          <line x1="0" y1="0" x2="18" y2="-18" stroke="{col}" stroke-width="2"/>
          <rect x="-78" y="18" width="156" height="32" fill="#020b18" stroke="{col}" stroke-width="1.1"/>
          <text x="0" y="31" text-anchor="middle" fill="#ffffff" font-size="9.5" font-weight="800">TN-{idx+700} {name[:14]}</text>
          <text x="0" y="44" text-anchor="middle" fill="{col}" font-size="8.5">{ip} • {badge}</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#020813;position:relative;overflow:hidden;font-family:'JetBrains Mono',monospace;">
      {_header_banner(32, "MILITARY C4ISR #2 // US NAVY AEGIS COMBAT INFORMATION CENTER (AN/SPY-6)", "Carrier Strike Group 75 (4×T4 RoCE) + Expeditionary Swarm TF-70 (27 VMs) + Phalanx CIWS Sentinel (:4099)", "AEGIS BASELINE 10 // 83/83 TRACKS", "#041226", "#00f0ff", "#e0f2fe", "#00f0ff")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <circle cx="{cx}" cy="{cy}" r="165" fill="none" stroke="#00f0ff" stroke-width="1.5" stroke-dasharray="8,4" opacity="0.55"/>
        <circle cx="{cx}" cy="{cy}" r="285" fill="none" stroke="#00f0ff" stroke-width="1.2" opacity="0.4"/>
        <circle cx="{cx}" cy="{cy}" r="405" fill="none" stroke="#00f0ff" stroke-width="1.8" opacity="0.6"/>
        <line x1="480" y1="{cy}" x2="1440" y2="{cy}" stroke="#00f0ff" stroke-width="0.8" opacity="0.35"/>
        <line x1="{cx}" y1="95" x2="{cx}" y2="995" stroke="#00f0ff" stroke-width="0.8" opacity="0.35"/>
        <circle cx="{cx}" cy="{cy}" r="42" fill="#041e3a" stroke="#fbbf24" stroke-width="3"/>
        <text x="{cx}" y="{cy-4}" text-anchor="middle" fill="#fbbf24" font-size="11" font-weight="900">CVN-164</text>
        <text x="{cx}" y="{cy+12}" text-anchor="middle" fill="#ffffff" font-size="9">280G AEGIS</text>
        {''.join(tracks)}
      </svg>
    </div>
    """


def build_33_military_f35_flir_hud() -> str:
    """#33 (also military_03): F-35 Lightning II Panoramic Cockpit MFD + AN/AAQ-37 Night-Vision HUD."""
    osb_top = [f'<rect x="{120 + i*170}" y="82" width="140" height="26" fill="#021a09" stroke="#00ff66" stroke-width="1.5"/><text x="{190 + i*170}" y="99" text-anchor="middle" fill="#00ff66" font-size="10" font-weight="900">OSB {i+1:02d} // {lbl}</text>' for i, lbl in enumerate(["TENSOR-75", "SWARM-70", "VSAN-60", "RACK-12U", "CLOUD-$1K", "ORACLES", "RAMDISK", "SENTINEL", "VAULT-10T", "WEAPONS"])]
    osb_bot = [f'<rect x="{120 + i*170}" y="992" width="140" height="26" fill="#021a09" stroke="#00ff66" stroke-width="1.5"/><text x="{190 + i*170}" y="1009" text-anchor="middle" fill="#00ff66" font-size="10" font-weight="900">OSB {i+11:02d} // {lbl}</text>' for i, lbl in enumerate(["ESXI-01", "ESXI-02", "ESXI-03", "ESXI-04", "UPS-1180W", "PRO-MAX", "POOL-A/B", "POOL-C/D", "CODEX-SOL", "MASTER-ARM"])]
    pods = []
    for idx, (name, sub, ip, badge, _, _) in enumerate(CLUSTER_NODES[:20]):
        c_i = idx % 5
        r_i = idx // 5
        x = 75 + c_i * 360
        y = 135 + r_i * 208
        pods.append(f"""
        <g transform="translate({x},{y})">
          <rect width="330" height="175" fill="#021407" stroke="#00ff66" stroke-width="1.8"/>
          <path d="M 8 24 L 8 8 L 24 8 M 306 8 L 322 8 L 322 24" fill="none" stroke="#facc15" stroke-width="2"/>
          <text x="18" y="30" fill="#00ff66" font-size="12.5" font-weight="900">STA-{idx+1:02d} // {name.upper()}</text>
          <text x="18" y="54" fill="#86efac" font-size="10.5">{sub}</text>
          <text x="18" y="78" fill="#facc15" font-size="10.5" font-weight="800">TGT LOCK: {ip} • {badge}</text>
          <line x1="18" y1="94" x2="312" y2="94" stroke="#00ff66" stroke-width="1" stroke-dasharray="4,3"/>
          <text x="18" y="118" fill="#4ade80" font-size="10">IR SEEKER: 79.5°F • LASER: ARMED</text>
          <rect x="18" y="132" width="294" height="26" fill="#00ff6622" stroke="#00ff66"/>
          <text x="165" y="149" text-anchor="middle" fill="#ffffff" font-size="10.5" font-weight="900">MASTER ARM: READY // 77.6 TOK/S</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#010a03;position:relative;overflow:hidden;font-family:'JetBrains Mono',monospace;">
      {_header_banner(33, "MILITARY C4ISR #3 // F-35 PANORAMIC COCKPIT MFD & AN/AAQ-37 EO-DAS HUD", "20 Perimeter MFD Option Select Buttons (OSB 01..20) + Night-Vision Green Stores & Sensor Management", "MASTER ARM: ON // 77.6 TOK/S", "#021808", "#00ff66", "#00ff66", "#facc15")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(osb_top)}
        {''.join(osb_bot)}
        {''.join(pods)}
      </svg>
    </div>
    """


def build_34_military_norad_wopr() -> str:
    """#34 (also military_04): NORAD Cheyenne Mountain WOPR Strategic Command & Trajectory Wallboard."""
    arcs = []
    for i in range(10):
        sx = 140 + i * 70
        tx = 1120 + (i % 5) * 155
        ty = 380 + (i // 5) * 240
        col = "#ff2a2a" if i % 3 == 0 else ("#00f0ff" if i % 2 == 0 else "#ffb000")
        arcs.append(f'<path d="M {sx} 680 Q {(sx+tx)//2} {90 + i*18} {tx} {ty}" stroke="{col}" stroke-width="2.5" fill="none" stroke-dasharray="8,4"/>')
        arcs.append(f'<circle cx="{tx}" cy="{ty}" r="18" fill="none" stroke="{col}" stroke-width="2"/><circle cx="{tx}" cy="{ty}" r="5" fill="{col}"/>')
    return f"""
    <div style="width:1920px;height:1034px;background:#030408;position:relative;overflow:hidden;font-family:'JetBrains Mono',monospace;">
      {_header_banner(34, "MILITARY C4ISR #4 // NORAD CHEYENNE MOUNTAIN WOPR STRATEGIC THEATER", "Parabolic Prompt & Tensor Trajectories From $1,000 Cloud Silos Into Boylenet Fortress (.164 / .72 / .83)", "DEFCON 5 // WOPR ONLINE", "#090b14", "#ff2a2a", "#ffffff", "#ffb000")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <!-- Strategic World/Theater Grid Box -->
        <rect x="36" y="90" width="1848" height="640" fill="#050811" stroke="#00f0ff" stroke-width="2"/>
        <!-- DEFCON Status Column -->
        <g transform="translate(60, 115)">
          <rect width="180" height="72" fill="#1f0707" stroke="#ff2a2a" stroke-width="2"/><text x="90" y="44" text-anchor="middle" fill="#7f1d1d" font-size="22" font-weight="900">DEFCON 1</text>
          <rect y="84" width="180" height="72" fill="#1f1207" stroke="#f97316" stroke-width="2"/><text x="90" y="128" text-anchor="middle" fill="#7c2d12" font-size="22" font-weight="900">DEFCON 2</text>
          <rect y="168" width="180" height="72" fill="#1f1b07" stroke="#eab308" stroke-width="2"/><text x="90" y="212" text-anchor="middle" fill="#713f12" font-size="22" font-weight="900">DEFCON 3</text>
          <rect y="252" width="180" height="72" fill="#071f18" stroke="#10b981" stroke-width="2"/><text x="90" y="296" text-anchor="middle" fill="#065f46" font-size="22" font-weight="900">DEFCON 4</text>
          <rect y="336" width="180" height="86" fill="#042f2e" stroke="#00f0ff" stroke-width="3.5"/><text x="90" y="378" text-anchor="middle" fill="#00f0ff" font-size="24" font-weight="900">DEFCON 5</text><text x="90" y="402" text-anchor="middle" fill="#ffffff" font-size="10" font-weight="800">NOMINAL SWARM</text>
        </g>
        {''.join(arcs)}
        <!-- Bottom Strategic Telemetry Ledger -->
        {''.join(f'<g transform="translate({36 + i*372}, 750)"><rect width="356" height="250" fill="#070b16" stroke="{col}" stroke-width="1.8"/><text x="18" y="30" fill="{col}" font-size="13" font-weight="900">{title}</text><text x="18" y="60" fill="#f8fafc" font-size="10.5">{l1}</text><text x="18" y="88" fill="#cbd5e1" font-size="10.5">{l2}</text><text x="18" y="116" fill="#cbd5e1" font-size="10.5">{l3}</text><text x="18" y="144" fill="#34d399" font-size="10.5" font-weight="700">{l4}</text><rect x="18" y="175" width="320" height="52" fill="#03050a" stroke="{col}"/><text x="178" y="206" text-anchor="middle" fill="#ffffff" font-size="13" font-weight="900">{stat}</text></g>' for i, (title, l1, l2, l3, l4, stat, col) in enumerate([
            ("SILO 01 // $1,000 CLOUD RESERVE", "• Anthropic Pools A/B/C/D ($250×4)", "• OpenAI Codex GPT-6.1-Sol / Astra", "• Kimi-for-Coding + AGY 10 Seats", "• Overage Protection: LOCKED OFF", "$1,000.00 READY", "#ffb000"),
            ("SILO 02 // 4× TESLA T4 ROCE CORE", "• ai-srv01 (.72) + aidev (.83 :50052)", "• ai-infer01 (.125) + ai-ollama01 (.228)", "• 10 TB Dual Model Vault (86 Models)", "• DeepSeek-V3-671B + Kimi-K2.5-1T", "77.62 TOK/S LOCKED", "#00f0ff"),
            ("SILO 03 // 12U RACK & 4× DL380", "• 79.5°F Bezel • 4×1U Silver UniFi", "• esxi01..02 (SFF) + esxi03..04 (LFF)", "• Rear Top UPS + Rear USW-Pro-Max", "• 328.4 TiB All-Flash & Exos vSAN", "1,180W // 100% BATT", "#10b981"),
            ("SILO 04 // 27 CLUSTER VMS & CI", "• Controller bd (.164) • 32 Web UIs", "• test3big (.82) 64c 128G Ramdisk", "• Builders bd1..4 + Verifiers test1..7", "• 8× DRS Elastic Cold Spares (Rule 61)", "656 VCPU // 1.73 TiB", "#38bdf8"),
            ("SILO 05 // ORACLES & SENTINEL", "• BattleStation (.137) Chrome CDP :9222", "• Bittorrent (.181) Secondary CDP :9222", "• Infra Sentinel (:4099) Auto-Healer", "• 32 Authoritative UniFi DNS Routes", "83/83 SERVICES UP", "#ff2a2a"),
        ]))}
      </svg>
    </div>
    """


def build_35_military_tactical_rack_c4isr() -> str:
    """#35 (also military_05): MIL-SPEC Ruggedized 12U Tactical C4ISR Rack & Field Sustainment Console."""
    base = _mod10.build_style_09_physical_rack()
    mil_banner = """
    <div style="position:absolute;left:24px;right:24px;top:12px;height:44px;background:#141c11;border:2px solid #84cc16;border-radius:6px;display:flex;align-items:center;justify-content:space-between;padding:0 20px;z-index:10;font-family:'JetBrains Mono',monospace;">
      <div style="display:flex;align-items:center;gap:12px;">
        <span style="background:#84cc16;color:#0a1007;padding:3px 10px;border-radius:4px;font-size:11px;font-weight:900;">MILITARY C4ISR #5 // MOCKUP #35</span>
        <span style="color:#ecfccb;font-size:14.5px;font-weight:900;">MIL-STD-810H RUGGEDIZED 12U TOC RACK DIGITAL TWIN (79.5°F • REAR UPS + USW-PRO-MAX • 27 VMS)</span>
      </div>
      <div style="font-size:11px;color:#bef264;font-weight:800;">
        COMSEC: GREEN // TRANSEC: 280G SFP28 // TOC POWER: 1,180W UPS
      </div>
    </div>
    """
    return base + mil_banner


# =============================================================================
# FAMILY 6 (#36-#40): AI SWARM & MULTI-AGENT WORKFLOW FAMILY
# =============================================================================

def build_36_kanban_factory() -> str:
    """#36: Kanban / Live Agent Factory Conveyor Belt."""
    cols = [
        ("01 // QUEUED BACKLOG", "#38bdf8", CLUSTER_NODES[0:5]),
        ("02 // O1740 POOL ROUTER", "#a855f7", CLUSTER_NODES[20:25]),
        ("03 // ACTIVE GPU & BUILDERS", "#00e5ff", CLUSTER_NODES[10:15]),
        ("04 // 64C RAMDISK PYTEST", "#10b981", CLUSTER_NODES[15:20]),
        ("05 // LANDED RECEIPTS & RACK", "#fbbf24", CLUSTER_NODES[5:10]),
    ]
    out = []
    for c_i, (ctitle, ccol, items) in enumerate(cols):
        x = 34 + c_i * 372
        cards = "".join(
            f'<g transform="translate(16,{62 + r_i*168})"><rect width="320" height="152" rx="10" fill="#090d16" stroke="{ic}" stroke-width="1.6"/><text x="16" y="28" fill="#f8fafc" font-size="13" font-weight="800">{n}</text><text x="16" y="52" fill="#94a3b8" font-size="10.5">{s}</text><text x="16" y="78" fill="{ic}" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="700">{ip} • {b}</text><rect x="16" y="96" width="288" height="38" rx="6" fill="#111726" stroke="#1e293b"/><text x="28" y="119" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="700">STAGE #{c_i+1} VERIFIED • 0 BLOCKERS</text></g>'
            for r_i, (n, s, ip, b, ic, _) in enumerate(items)
        )
        out.append(f'<g transform="translate({x}, 92)"><rect width="352" height="910" rx="12" fill="#0e1422" stroke="{ccol}" stroke-width="2"/><rect width="352" height="44" rx="12" fill="{ccol}22"/><text x="176" y="28" text-anchor="middle" fill="{ccol}" font-family="JetBrains Mono,monospace" font-size="12" font-weight="900">{ctitle}</text>{cards}</g>')
    return f"""
    <div style="width:1920px;height:1034px;background:#060911;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(36, "AUTONOMOUS SWARM KANBAN CONVEYOR FACTORY", "5-Stage Continuous Integration & Agent Execution Pipeline (30/30 Heavy-Lifter Cap • 0 Queue Stall)", "CONVEYOR VELOCITY: 100%", "#0d1322", "#00e5ff", "#f8fafc", "#00e5ff")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">{''.join(out)}</svg>
    </div>
    """


def build_37_gladiator_colosseum() -> str:
    """#37: 12-Harness Gladiator Arena Colosseum Map."""
    cx, cy = 960, 545
    tiers = []
    for idx, (name, sub, ip, badge, col, _) in enumerate(CLUSTER_NODES[:18]):
        ang = math.radians(idx * 20 - 90)
        rx, ry = 720, 385
        px, py = cx + rx * math.cos(ang), cy + ry * math.sin(ang)
        tiers.append(f"""
        <line x1="{px:.1f}" y1="{py:.1f}" x2="{cx}" y2="{cy}" stroke="{col}" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.5"/>
        <g transform="translate({px-92:.1f},{py-34:.1f})">
          <rect width="184" height="68" rx="10" fill="#120d1d" stroke="{col}" stroke-width="2"/>
          <text x="92" y="24" text-anchor="middle" fill="#f8fafc" font-size="11" font-weight="800">{name}</text>
          <text x="92" y="42" text-anchor="middle" fill="#94a3b8" font-size="9">{sub}</text>
          <text x="92" y="58" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="9" font-weight="700">{ip} • {badge}</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:radial-gradient(circle at 50% 54%,#27113b 0%,#090512 70%);position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(37, "12-HARNESS GLADIATOR ARENA & CONSENSUS COLOSSEUM (:4098)", "Elliptical Colosseum Tiers Converging on Central Consensus Judge Stage (Claude ABCD + Codex + Kimi + 4×T4)", "CONSENSUS ARENA :4098", "#170b26", "#f59e0b", "#f8fafc", "#f59e0b")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <ellipse cx="{cx}" cy="{cy}" rx="720" ry="385" fill="none" stroke="#a855f7" stroke-width="3" stroke-dasharray="12,6" opacity="0.5"/>
        <ellipse cx="{cx}" cy="{cy}" rx="420" ry="220" fill="none" stroke="#f59e0b" stroke-width="2" opacity="0.4"/>
        <ellipse cx="{cx}" cy="{cy}" rx="195" ry="105" fill="#1e1035" stroke="#fbbf24" stroke-width="4"/>
        <text x="{cx}" y="{cy-14}" text-anchor="middle" fill="#fbbf24" font-size="16" font-weight="900">CONSENSUS JUDGE CORE</text>
        <text x="{cx}" y="{cy+10}" text-anchor="middle" fill="#ffffff" font-family="JetBrains Mono,monospace" font-size="12" font-weight="800">bd-pm-B + DeepSeek-671B</text>
        <text x="{cx}" y="{cy+30}" text-anchor="middle" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="10">77.6 tok/s • $1,000 Cloud Credits</text>
        {''.join(tiers)}
      </svg>
    </div>
    """


def build_38_subway_metro_map() -> str:
    """#38: London Underground / Tokyo Metro Transit Map of Boylenet VLANs & Worktrees."""
    lines = [
        ("M 120 220 L 680 220 L 820 360 L 1800 360", "#00e5ff", "VLAN 75 • 25GbE RoCE Express Line"),
        ("M 120 420 L 540 420 L 680 560 L 1800 560", "#10b981", "VLAN 70 • 27-VM Swarm Circle Line"),
        ("M 120 640 L 920 640 L 1080 480 L 1800 480", "#3b82f6", "VLAN 60 • 328.4 TiB vSAN & 12U Rack Line"),
        ("M 120 840 L 760 840 L 920 680 L 1800 680", "#c084fc", "$1,000 Cloud Burst & Browser Oracle Line"),
    ]
    stations = []
    for idx, (name, sub, ip, badge, col, _) in enumerate(CLUSTER_NODES[:24]):
        c_i = idx % 6
        r_i = idx // 6
        sx = 180 + c_i * 305
        sy = [220, 420, 640, 840][r_i]
        stations.append(f"""
        <g transform="translate({sx},{sy})">
          <circle cx="0" cy="0" r="14" fill="#ffffff" stroke="{col}" stroke-width="5"/>
          <rect x="-82" y="22" width="164" height="54" rx="8" fill="#0b101d" stroke="{col}" stroke-width="1.6"/>
          <text x="0" y="40" text-anchor="middle" fill="#f8fafc" font-size="10.5" font-weight="800">{name}</text>
          <text x="0" y="55" text-anchor="middle" fill="#94a3b8" font-size="8.5">{sub}</text>
          <text x="0" y="69" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="8.5" font-weight="700">{ip} • {badge}</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#070a12;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(38, "BECK TRANSIT METRO MAP // BOYLENET SUBWAY TOPOLOGY", "4 High-Speed Transit Lines (Cyan=25GbE RoCE, Green=VLAN 70 VMs, Blue=12U Rack & vSAN, Purple=$1,000 Cloud)", "ALL 24 STATIONS OPEN", "#0e1526", "#38bdf8", "#f8fafc", "#00e5ff")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(f'<path d="{d}" stroke="{c}" stroke-width="12" fill="none" stroke-linecap="round" stroke-linejoin="round" opacity="0.85"/>' for d, c, _ in lines)}
        {''.join(stations)}
      </svg>
    </div>
    """


def build_39_tv_wall_cockpit() -> str:
    """#39: 3x3 Live Agent TV Wall + Mini-Topology Split Cockpit."""
    screens = [
        ("TV-01 // bd-pm-B (Opus 5.5 PM Integrator • Pool B $250)", "#c084fc", "$ bd-agy-dispatch --status\n[OK] O1740 Pool B 5h=0% Weekly=2%\n[OK] 15/15 Web UIs (:4080,:4086..:4099) HTTP 200\n[OK] 30/30 Heavy-Lifter slots balanced"),
        ("TV-02 // ai-srv01 (.72) <-> aidev (.83) 25GbE RoCE", "#00e5ff", "$ nvidia-smi & ik_llama.cpp --rpc 10.0.75.12:50052\n[T4 #1 .72] 10123/15360 MiB | 71C | 31.2W\n[T4 #2 .83] 10677/15360 MiB | 74C | 32.5W\n[STREAM] deepseek-v3-0324-671b @ 77.62 tok/s"),
        ("TV-03 // test3big (.82) 64-vCPU 128G Ramdisk Pytest", "#10b981", "$ bd-pytest-digest /dev/shm/pytest-shards\nPASS: 1,428 passed, 0 failed in 2.41s (64 workers)\nRAMDISK: 42.1 / 128.0 GB used (0 Disk IO)"),
        ("TV-04 // BattleStation (.137) & Bittorrent (.181) CDP", "#f59e0b", "$ bd-oracle --oracle all --json\n[10.0.10.137:9222] Chrome/155.0.8059.41 1920x1080 OK\n[10.0.70.181:9222] Chrome/155.0.8059.80 Standby OK"),
        ("TV-05 // Physical 12U Rack & HPE iLO4 (.10..40)", "#3b82f6", "$ bd-hardware-matrix --verify\n[THERMOSTAT] 79.5°F | Rear Top UPS: 1,180W (100%)\n[UNIFI 4x1U] UDM-Pro + Agg + Pro-Agg 280G + 24-PoE\n[REAR ESXi 2&3] USW-Pro-Max Etherlighting ONLINE"),
        ("TV-06 // Infra Sentinel (:4099) & 328.4 TiB vSAN", "#34d399", "$ curl -s http://sentinel.boylenet.themfboyles.com/health\n[SENTINEL] 83/83 Services UP | 0 Self-Heal Restarts\n[VSAN 60] 135.7 / 328.4 TiB (41.3% • 11 DGs • 75 Disks)"),
    ]
    tvs = []
    for idx, (title, col, log_txt) in enumerate(screens):
        x = 34 + (idx % 3) * 624
        y = 515 + (idx // 3) * 245
        lines_svg = "".join(
            f'<text x="18" y="{62 + li*28}" fill="#e2e8f0" font-family="JetBrains Mono,monospace" font-size="11">{line}</text>'
            for li, line in enumerate(log_txt.split("\n"))
        )
        tvs.append(f"""
        <g transform="translate({x},{y})">
          <rect width="604" height="228" rx="10" fill="#050811" stroke="{col}" stroke-width="2"/>
          <rect width="604" height="34" rx="10" fill="{col}22"/>
          <circle cx="20" cy="17" r="5" fill="{col}"/>
          <text x="34" y="22" fill="#ffffff" font-family="JetBrains Mono,monospace" font-size="11.5" font-weight="900">{title}</text>
          {lines_svg}
        </g>
        """)
    mini_nodes = "".join(
        f'<g transform="translate({38 + (i%8)*232},{95 + (i//8)*130})"><rect width="218" height="114" rx="8" fill="#0d1424" stroke="{c}" stroke-width="1.6"/><text x="14" y="26" fill="#f8fafc" font-size="11.5" font-weight="800">{n}</text><text x="14" y="48" fill="#94a3b8" font-size="9.5">{s}</text><text x="14" y="72" fill="{c}" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="700">{ip}</text><text x="14" y="94" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="700">● {b}</text></g>'
        for i, (n, s, ip, b, c, _) in enumerate(CLUSTER_NODES[:24])
    )
    return f"""
    <div style="width:1920px;height:1034px;background:#070b14;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(39, "SPLIT TOPOLOGY + 6-SCREEN LIVE AGENT TV WALL", "Upper Deck: 24-Node Live Topology Matrix • Lower Deck: 6 Real-Time Streaming Headless Agent Terminals", "TV WALL + TOPOLOGY", "#0e1526", "#a855f7", "#f8fafc", "#00e5ff")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {mini_nodes}
        <line x1="34" y1="498" x2="1886" y2="498" stroke="#38bdf8" stroke-width="2"/>
        {''.join(tvs)}
      </svg>
    </div>
    """


def build_40_cloud_fuel_tanks() -> str:
    """#40: $1,000 Cloud Credit & Pool Quota Aviation Fuel-Tank Transfer Deck."""
    tanks = [
        ("TANK A // CLAUDE POOL A", "$250.00 / $250", "100% FULL • 0% 5h", "#c084fc"),
        ("TANK B // CLAUDE POOL B (PM)", "$250.00 / $250", "100% FULL • Opus 5.5", "#a855f7"),
        ("TANK C // CLAUDE POOL C", "$250.00 / $250", "95% FULL • 5% 5h", "#8b5cf6"),
        ("TANK D // CLAUDE POOL D", "$250.00 / $250", "100% FULL • Sonnet", "#7c3aed"),
        ("AUX E // OPENAI CODEX SOL", "FLAT-RATE PRO", "100% FULL • 0% Win", "#10b981"),
        ("AUX F // LOCAL 4×T4 ROCE", "$0.00 INFINITE", "100% FULL • 77.62 TOK/S", "#00e5ff"),
    ]
    tank_svg = []
    for i, (tname, cap, stat, col) in enumerate(tanks):
        x = 42 + i * 308
        tank_svg.append(f"""
        <g transform="translate({x}, 105)">
          <rect width="288" height="340" rx="16" fill="#0b101d" stroke="{col}" stroke-width="2.5"/>
          <rect x="18" y="68" width="252" height="210" rx="10" fill="#060911" stroke="#1e293b"/>
          <rect x="22" y="78" width="244" height="196" rx="8" fill="{col}" fill-opacity="0.32"/>
          <text x="144" y="34" text-anchor="middle" fill="#f8fafc" font-size="12.5" font-weight="900">{tname}</text>
          <text x="144" y="54" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="11" font-weight="800">{cap}</text>
          <text x="144" y="180" text-anchor="middle" fill="#ffffff" font-family="JetBrains Mono,monospace" font-size="22" font-weight="900">{stat.split('•')[0]}</text>
          <text x="144" y="208" text-anchor="middle" fill="#e2e8f0" font-family="JetBrains Mono,monospace" font-size="11">{stat.split('•')[1]}</text>
          <text x="144" y="312" text-anchor="middle" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="800">OVERAGE VALVE: SHUT ($0 RISK)</text>
          <line x1="144" y1="340" x2="144" y2="415" stroke="{col}" stroke-width="6"/>
        </g>
        """)
    engines = "".join(
        f'<g transform="translate({42 + (i%5)*370},{595 + (i//5)*140})"><rect width="350" height="122" rx="10" fill="#0d1424" stroke="{c}" stroke-width="1.8"/><text x="18" y="30" fill="#f8fafc" font-size="13" font-weight="800">ENGINE #{i+1:02d}: {n}</text><text x="18" y="54" fill="#94a3b8" font-size="10.5">{s}</text><text x="18" y="80" fill="{c}" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="700">{ip} • {b}</text><text x="18" y="104" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9.5">FUEL PRESSURE: 100% NOMINAL</text></g>'
        for i, (n, s, ip, b, c, _) in enumerate(CLUSTER_NODES[6:21])
    )
    return f"""
    <div style="width:1920px;height:1034px;background:#060911;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(40, "AVIATION FUEL-TANK QUOTA & $1,000 CLOUD MANIFOLD (:4090)", "6 Primary Credit & Local GPU Fuel Tanks Feeding O1740 Cross-Feed Manifold Into 27 Cluster VMs", "$1,000.00 // $0 OVERAGE", "#0f1629", "#c084fc", "#f8fafc", "#c084fc")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        {''.join(tank_svg)}
        <rect x="42" y="515" width="1836" height="52" rx="10" fill="#171033" stroke="#00e5ff" stroke-width="2.5"/>
        <text x="960" y="546" text-anchor="middle" fill="#ffffff" font-family="JetBrains Mono,monospace" font-size="14" font-weight="900">O1740 DYNAMIC CAPABILITY CROSS-FEED MANIFOLD (30 GLOBAL HEAVY-LIFTER CAP • ZERO OVERAGE CUTOFF)</text>
        {engines}
      </svg>
    </div>
    """


# =============================================================================
# FAMILY 7 (#41-#45): GEOGRAPHIC, ARCHITECTURAL & BLUEPRINT FAMILY
# =============================================================================

def build_41_cad_blueprint() -> str:
    """#41: CAD Architectural Blueprint (Prussian Blue #0a2246 + Crisp White Technical Lines)."""
    boxes = []
    for idx, (name, sub, ip, badge, _, _) in enumerate(CLUSTER_NODES[:25]):
        c_i = idx % 5
        r_i = idx // 5
        x = 45 + c_i * 370
        y = 105 + r_i * 176
        boxes.append(f"""
        <g transform="translate({x},{y})">
          <rect width="344" height="148" fill="#0d2b59" stroke="#ffffff" stroke-width="1.6"/>
          <rect x="5" y="5" width="334" height="138" fill="none" stroke="#93c5fd" stroke-width="0.6" stroke-dasharray="4,3"/>
          <line x1="0" y1="32" x2="344" y2="32" stroke="#ffffff" stroke-width="1"/>
          <text x="14" y="21" fill="#ffffff" font-size="11.5" font-weight="900">DWG-{idx+101} // {name.upper()}</text>
          <text x="14" y="56" fill="#bfdbfe" font-size="10.5">SPEC: {sub}</text>
          <text x="14" y="80" fill="#ffffff" font-size="10.5" font-weight="700">NET COORD: {ip}</text>
          <text x="14" y="104" fill="#67e8f9" font-size="10.5">TOLERANCE: {badge} (±0.01ms)</text>
          <text x="14" y="130" fill="#93c5fd" font-size="9">|◄─────── SCALE 1:1 • REV O1789 ───────►|</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#081c3a;position:relative;overflow:hidden;font-family:'JetBrains Mono',monospace;">
      {_header_banner(41, "ISO-9001 CAD ARCHITECTURAL BLUEPRINT", "Boylenet Full-Cluster Engineering Schematic (12U Rack + 4×T4 RoCE + 27 VMs • Scale 1:1)", "BLUEPRINT DWG #4088", "#0d2b59", "#ffffff", "#ffffff", "#67e8f9")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <defs>
          <pattern id="cad-p" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke="#1e40af" stroke-width="0.8"/>
          </pattern>
        </defs>
        <rect width="1920" height="1034" fill="url(#cad-p)"/>
        {''.join(boxes)}
      </svg>
    </div>
    """


def build_42_pcb_motherboard() -> str:
    """#42: PCB Motherboard & Silicon Die Layout (Emerald Solder Mask + Gold Copper Traces)."""
    pads = []
    for idx, (name, sub, ip, badge, _, _) in enumerate(CLUSTER_NODES[:25]):
        c_i = idx % 5
        r_i = idx // 5
        x = 48 + c_i * 368
        y = 105 + r_i * 176
        pins = "".join(f'<rect x="{18 + p*26}" y="-6" width="12" height="6" fill="#eab308"/><rect x="{18 + p*26}" y="148" width="12" height="6" fill="#eab308"/>' for p in range(12))
        pads.append(f"""
        <path d="M {x+338} {y+74} L {x+355} {y+74} L {x+368} {y+87}" stroke="#eab308" stroke-width="2.5" fill="none"/>
        <g transform="translate({x},{y})">
          {pins}
          <rect width="338" height="148" rx="4" fill="#0d1117" stroke="#eab308" stroke-width="2"/>
          <rect x="10" y="10" width="318" height="128" fill="#052e16" stroke="#22c55e" stroke-width="1"/>
          <text x="22" y="34" fill="#fef08a" font-size="12" font-weight="900">IC-U{idx+1:02d} // {name.upper()}</text>
          <text x="22" y="58" fill="#86efac" font-size="10">{sub}</text>
          <text x="22" y="84" fill="#eab308" font-size="10.5" font-weight="800">BUS ADDR: {ip}</text>
          <text x="22" y="108" fill="#ffffff" font-size="10">CLOCK / BW: {badge}</text>
          <text x="22" y="128" fill="#4ade80" font-size="8.5">PCIe Gen4 / 25GbE SerDes OK</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#031a0d;position:relative;overflow:hidden;font-family:'JetBrains Mono',monospace;">
      {_header_banner(42, "SILICON PCB MOTHERBOARD & SERDES TRACE TOPOLOGY", "Boylenet Rendered as a Multi-Chip Module (Gold Copper Traces on Emerald Solder Mask)", "280G SERDES BUS", "#052e16", "#eab308", "#fef08a", "#eab308")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">{''.join(pads)}</svg>
    </div>
    """


def build_43_cyber_city_skyline() -> str:
    """#43: Isometric Cyber-City Skyline ('Boylenet Metropolis' Skyscrapers Scaled by Compute)."""
    buildings = []
    for idx, (name, sub, ip, badge, col, _) in enumerate(CLUSTER_NODES[:24]):
        x = 28 + idx * 78
        h = 260 + (idx * 67) % 440
        top_y = 855 - h
        windows = "".join(
            f'<rect x="{x+10}" y="{top_y + 20 + w*28}" width="50" height="14" rx="2" fill="{col}" opacity="0.38"/>'
            for w in range(max(3, h // 32 - 1))
        )
        buildings.append(f"""
        <rect x="{x}" y="{top_y}" width="70" height="{h}" fill="#0b1120" stroke="{col}" stroke-width="2"/>
        {windows}
        <line x1="{x+35}" y1="{top_y}" x2="{x+35}" y2="{top_y-28}" stroke="{col}" stroke-width="2"/>
        <circle cx="{x+35}" cy="{top_y-28}" r="4" fill="{col}"/>
        <g transform="translate({x+35},{875 + (idx%2)*58})">
          <rect x="-72" y="0" width="144" height="46" rx="6" fill="#090d16" stroke="{col}" stroke-width="1.2"/>
          <text x="0" y="18" text-anchor="middle" fill="#f8fafc" font-size="9.5" font-weight="800">{name[:16]}</text>
          <text x="0" y="34" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="8.5">{ip} • {badge}</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:linear-gradient(180deg,#050714 0%,#131836 72%,#070913 100%);position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(43, "BOYLENET METROPOLIS // CYBER-CITY SKYLINE", "24 High-Rise Compute & Storage Skyscrapers Scaled by RAM, VRAM & Token Throughput", "SKYLINE: 656 VCPUS • 1.73 TiB", "#0c1226", "#00e5ff", "#f8fafc", "#fbbf24")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <line x1="0" y1="855" x2="1920" y2="855" stroke="#00e5ff" stroke-width="4"/>
        {''.join(buildings)}
      </svg>
    </div>
    """


def build_44_scada_power_grid() -> str:
    """#44: Power-Grid & SCADA Electrical Single-Line Diagram (1,180W Rear UPS -> PSUs -> T4 GPUs)."""
    breakers = []
    for idx, (name, sub, ip, badge, col, _) in enumerate(CLUSTER_NODES[:20]):
        c_i = idx % 5
        r_i = idx // 5
        x = 48 + c_i * 368
        y = 260 + r_i * 185
        watts = "31.2W GPU" if "ai-" in name or "aidev" in name else ("305W 2×PSU" if "esxi" in name else ("64W SFP28" if "USW" in name else "0.0W Cloud"))
        breakers.append(f"""
        <line x1="{x+170}" y1="210" x2="{x+170}" y2="{y}" stroke="#facc15" stroke-width="2" stroke-dasharray="6,4" opacity="0.6"/>
        <g transform="translate({x},{y})">
          <rect width="340" height="154" rx="8" fill="#0b1118" stroke="{col}" stroke-width="2"/>
          <text x="16" y="28" fill="#facc15" font-size="11.5" font-weight="900">CB-{idx+101} CLOSED // {watts}</text>
          <text x="16" y="54" fill="#f8fafc" font-size="13" font-weight="800">{name}</text>
          <text x="16" y="78" fill="#94a3b8" font-size="10">{sub}</text>
          <text x="16" y="102" fill="{col}" font-size="10.5" font-weight="700">BUS: {ip} • {badge}</text>
          <rect x="16" y="116" width="308" height="24" rx="4" fill="#052e16" stroke="#10b981"/>
          <text x="26" y="132" fill="#6ee7b7" font-size="9.5" font-weight="800">VOLTAGE: 120.2V AC / 12.0V DC • TEMP OK</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#05080c;position:relative;overflow:hidden;font-family:'JetBrains Mono',monospace;">
      {_header_banner(44, "IEEE SCADA ELECTRICAL SINGLE-LINE POWER & UPS DIAGRAM", "Rear Top Rackmount UPS (1,180W Load • 100% Battery • 79.5°F) ➔ 8× HPE FlexSlot PSUs ➔ 4× Tesla T4s", "SCADA: 1,180W // 100% UPS", "#0d1520", "#facc15", "#f8fafc", "#facc15")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">
        <rect x="48" y="95" width="1812" height="115" rx="10" fill="#1c1917" stroke="#facc15" stroke-width="3"/>
        <text x="960" y="135" text-anchor="middle" fill="#facc15" font-size="18" font-weight="900">MAIN 120V AC BUSBAR // REAR TOP RACKMOUNT UPS (1,180W LOAD • 100% BATTERY • AVR ACTIVE • 79.5°F)</text>
        <text x="960" y="168" text-anchor="middle" fill="#34d399" font-size="12" font-weight="700">esxi01 (246W) + esxi02 (312W) + esxi03 (298W) + esxi04 (324W) • 4× Tesla T4 Total = 124.9W • 8× Cold Spares = 0.0W</text>
        {''.join(breakers)}
      </svg>
    </div>
    """


def build_45_model_vault_treemap() -> str:
    """#45: 10 TB Dual-Vault 86-Model Treemap & Sunburst Map."""
    blocks = [
        (36, 95, 580, 440, "VAULT A (.72) // DeepSeek-V3-0324-671B", "404 GB GGUF • 77.62 tok/s • VLAN 75 RoCE", "#00e5ff"),
        (630, 95, 580, 440, "VAULT B (.83) // Kimi-K2.5-1T & MiMo-1024B", "1,202 GB GGUF • RPC :50052 Dual-Host Split", "#a855f7"),
        (1224, 95, 660, 212, "VAULT A/B // Hermes-4-405B & GLM-5.3", "490 GB Total • High-Reasoning Council Tier", "#10b981"),
        (1224, 323, 660, 212, "NODE .125 & .228 // Qwen2.5-32B + 17 Ollama", "310 GB Total • Qdrant :6333 + LiteLLM :4000", "#38bdf8"),
        (36, 555, 450, 445, "12U PHYSICAL RACK & 328.4 TiB VSAN", "11 Disk Groups • 75 Disks • 79.5°F • Rear UPS", "#3b82f6"),
        (500, 555, 450, 445, "27 CLUSTER VMS & 64C RAMDISK (.82)", "Controller .164 + 128G /dev/shm Pytest + bd1..4", "#fbbf24"),
        (964, 555, 450, 445, "$1,000 CLOUD BURST POOLS (A/B/C/D)", "Opus 5.5 + Sonnet 5.5 + Codex Sol ($0 Overage)", "#c084fc"),
        (1428, 555, 456, 445, "DUAL BROWSER ORACLES & SENTINEL", "BattleStation .137 + Bittorrent .181 + 83/83 UP", "#f43f5e"),
    ]
    rects = "".join(
        f'<g transform="translate({x},{y})"><rect width="{w}" height="{h}" rx="12" fill="{c}18" stroke="{c}" stroke-width="2.5"/><text x="26" y="42" fill="#ffffff" font-size="16" font-weight="900">{t}</text><text x="26" y="72" fill="{c}" font-family="JetBrains Mono,monospace" font-size="12" font-weight="800">{s}</text><text x="26" y="106" fill="#cbd5e1" font-family="JetBrains Mono,monospace" font-size="10.5">• Verified HTTP 200 &amp; Zero Packet Loss across VLAN 70/75/60</text><text x="26" y="132" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="10.5">• Pre-warmed in RAM via bd-kv-warmer &amp; O1740 Autobalancer</text></g>'
        for x, y, w, h, t, s, c in blocks
    )
    return f"""
    <div style="width:1920px;height:1034px;background:#060911;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(45, "10 TB DUAL-VAULT 86-MODEL & 328.4 TiB VSAN TREEMAP", "Proportional Capacity & Throughput Treemap Across Vault A (.72), Vault B (.83), vSAN & $1,000 Cloud", "8.9 TB / 86 AI MODELS", "#0d1424", "#00e5ff", "#f8fafc", "#00e5ff")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">{rects}</svg>
    </div>
    """


# =============================================================================
# FAMILY 8 (#46-#50): EXECUTIVE, GLASS & NEXT-GEN OS FAMILY
# =============================================================================

def build_46_sequoia_bento() -> str:
    """#46: macOS Sequoia / iPadOS Stage Manager Bento Grid."""
    bento = []
    for idx, (name, sub, ip, badge, col, _) in enumerate(CLUSTER_NODES[:20]):
        c_i = idx % 5
        r_i = idx // 5
        x = 38 + c_i * 372
        y = 95 + r_i * 228
        bento.append(f"""
        <div style="position:absolute;left:{x}px;top:{y}px;width:354px;height:210px;background:rgba(255,255,255,0.06);backdrop-filter:blur(24px);border:1px solid rgba(255,255,255,0.16);border-radius:26px;padding:20px;display:flex;flex-direction:column;justify-content:space-between;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="background:{col}28;color:{col};padding:4px 12px;border-radius:999px;font-size:10.5px;font-weight:800;">{ip}</span>
            <span style="color:#34d399;font-size:11px;font-weight:800;">● {badge}</span>
          </div>
          <div>
            <div style="color:#ffffff;font-size:17px;font-weight:800;margin-bottom:4px;">{name}</div>
            <div style="color:#94a3b8;font-size:12px;">{sub}</div>
          </div>
          <div style="height:6px;background:rgba(255,255,255,0.1);border-radius:3px;overflow:hidden;">
            <div style="width:78%;height:100%;background:{col};"></div>
          </div>
        </div>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:radial-gradient(circle at 20% 20%,#1e1b4b 0%,#0f172a 55%,#020617 100%);position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(46, "MACOS SEQUOIA / IPADOS STAGE MANAGER BENTO GRID", "20 Modular Spatial Bento Widgets for Boylenet 12U Rack, 4×T4 GPUs, 27 VMs & $1,000 Cloud Credits", "BENTO STAGE MANAGER", "rgba(15,23,42,0.85)", "#38bdf8", "#ffffff", "#38bdf8")}
      {''.join(bento)}
    </div>
    """


def build_47_arasaka_netrunner() -> str:
    """#47: Cyberpunk 2077 / Arasaka Red & Black Netrunner Breach Deck."""
    cells = []
    for idx, (name, sub, ip, badge, _, _) in enumerate(CLUSTER_NODES[:25]):
        c_i = idx % 5
        r_i = idx // 5
        x = 42 + c_i * 370
        y = 102 + r_i * 178
        col = "#ff003c" if idx % 2 == 0 else "#fcee0a"
        cells.append(f"""
        <g transform="translate({x},{y})">
          <polygon points="0,0 325,0 348,22 348,154 20,154 0,134" fill="#120408" stroke="{col}" stroke-width="2"/>
          <rect x="14" y="12" width="64" height="20" fill="{col}"/>
          <text x="46" y="26" text-anchor="middle" fill="#000000" font-size="10.5" font-weight="900">BD-{idx+10:02X}</text>
          <text x="90" y="26" fill="#ffffff" font-size="12" font-weight="900">{name.upper()}</text>
          <text x="16" y="58" fill="#fda4af" font-size="10.5">{sub}</text>
          <text x="16" y="84" fill="#fcee0a" font-size="10.5" font-weight="800">ICE NODE: {ip}</text>
          <text x="16" y="110" fill="#00f0ff" font-size="10.5" font-weight="800">DAEMON: {badge} // BREACH OK</text>
          <text x="16" y="136" fill="#ff003c" font-size="9">1C 55 BD E9 // SUBNET 70-75 SECURED</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#070204;position:relative;overflow:hidden;font-family:'JetBrains Mono',monospace;">
      {_header_banner(47, "ARASAKA COUNTER-INTEL // NETRUNNER BREACH PROTOCOL DECK", "Chamfered Crimson & Cyber-Yellow Neural Subnet Matrix (27 VMs • 4×T4 Daemons • 12U Black-ICE Rack)", "NETWATCH // ICE 100%", "#180409", "#ff003c", "#fcee0a", "#ff003c")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">{''.join(cells)}</svg>
    </div>
    """


def build_48_audio_mixer_studio() -> str:
    """#48: Spotify / Solid State Logic Mixing Console & VU Meter Equalizer."""
    strips = []
    for idx, (name, sub, ip, badge, col, _) in enumerate(CLUSTER_NODES[:16]):
        x = 32 + idx * 116
        bars = "".join(
            f'<rect x="18" y="{140 + b*22}" width="72" height="15" rx="2" fill="{"#ef4444" if b < 3 else ("#facc15" if b < 7 else "#10b981")}" opacity="{0.92 if b >= (idx%5 + 2) else 0.18}"/>'
            for b in range(22)
        )
        fader_y = 670 + (idx * 23) % 140
        strips.append(f"""
        <g transform="translate({x}, 95)">
          <rect width="108" height="905" rx="8" fill="#121318" stroke="#282c37" stroke-width="1.6"/>
          <rect x="8" y="10" width="92" height="46" rx="5" fill="#090a0f" stroke="{col}"/>
          <text x="54" y="29" text-anchor="middle" fill="#ffffff" font-size="9.5" font-weight="800">{name[:13]}</text>
          <text x="54" y="46" text-anchor="middle" fill="{col}" font-family="JetBrains Mono,monospace" font-size="8.5" font-weight="700">{badge}</text>
          <text x="54" y="82" text-anchor="middle" fill="#94a3b8" font-family="JetBrains Mono,monospace" font-size="8.5">{ip}</text>
          <circle cx="54" cy="112" r="14" fill="#1e222d" stroke="{col}" stroke-width="2"/>
          {bars}
          <!-- Studio Fader Track -->
          <line x1="54" y1="645" x2="54" y2="845" stroke="#000000" stroke-width="8"/>
          <rect x="26" y="{fader_y}" width="56" height="26" rx="4" fill="{col}" stroke="#ffffff" stroke-width="1.5"/>
          <text x="54" y="882" text-anchor="middle" fill="#34d399" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="900">CH {idx+1:02d} ON</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:#08090c;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(48, "MASTERING CONSOLE // 16-CHANNEL SWARM & GPU VU MIXER", "Each Boylenet Host, T4 GPU & Cloud Pool Rendered as a Live SSL Studio Mixing Channel Strip", "MASTER BUS: +0.0 dBFS (77.6 tok/s)", "#12141c", "#10b981", "#f8fafc", "#10b981")}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">{''.join(strips)}</svg>
    </div>
    """


def build_49_quad_noc_wallboard() -> str:
    """#49: Split 4-Quadrant NOC Wallboard (Q1: UniFi Graph | Q2: 3D Iso | Q3: 12U Rack | Q4: Agent Terminals)."""
    return f"""
    <div style="width:1920px;height:1034px;background:#050811;position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(49, "4-QUADRANT GLOBAL NOC COMMAND WALLBOARD", "Q1: UniFi 280G Graph • Q2: 4×T4 RoCE Tensor Matrix • Q3: 12U Front+Rear Physical Rack • Q4: $1,000 Cloud & Agents", "4-QUADRANT NOC WALL", "#0b1120", "#38bdf8", "#f8fafc", "#00e5ff")}
      <!-- Q1 Top-Left -->
      <div style="position:absolute;left:22px;top:80px;width:928px;height:462px;background:#0a0f1c;border:2px solid #006fff;border-radius:12px;padding:16px;overflow:hidden;">
        <div style="color:#38bdf8;font-size:13px;font-weight:900;margin-bottom:10px;">QUADRANT 01 // UBIQUITI UNIFI 280G SPINE &amp; VLAN SWITCHING MATRIX</div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;font-family:'JetBrains Mono',monospace;font-size:10.5px;">
          {''.join(f'<div style="background:#111827;border:1px solid {c};border-radius:8px;padding:10px;"><b style="color:#fff;">{n}</b><br><span style="color:#94a3b8;">{s}</span><br><span style="color:{c};">{ip} • {b}</span></div>' for n, s, ip, b, c, _ in CLUSTER_NODES[:12])}
        </div>
      </div>
      <!-- Q2 Top-Right -->
      <div style="position:absolute;right:22px;top:80px;width:928px;height:462px;background:#0a0f1c;border:2px solid #00e5ff;border-radius:12px;padding:16px;overflow:hidden;">
        <div style="color:#00e5ff;font-size:13px;font-weight:900;margin-bottom:10px;">QUADRANT 02 // 4× NVIDIA TESLA T4 25GbE ROCE &amp; 27-VM COMPUTE FABRIC</div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;font-family:'JetBrains Mono',monospace;font-size:10.5px;">
          {''.join(f'<div style="background:#042f2e44;border:1px solid {c};border-radius:8px;padding:10px;"><b style="color:#fff;">{n}</b><br><span style="color:#94a3b8;">{s}</span><br><span style="color:{c};">{ip} • {b}</span></div>' for n, s, ip, b, c, _ in CLUSTER_NODES[10:22])}
        </div>
      </div>
      <!-- Q3 Bottom-Left -->
      <div style="position:absolute;left:22px;bottom:16px;width:928px;height:462px;background:#0a0f1c;border:2px solid #10b981;border-radius:12px;padding:16px;overflow:hidden;">
        <div style="color:#10b981;font-size:13px;font-weight:900;margin-bottom:10px;">QUADRANT 03 // 12U PHYSICAL RACK TWIN (79.5°F • FRONT 4×1U UNIFI + 4×2U DL380 • REAR UPS + PRO-MAX)</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:11px;line-height:1.85;color:#cbd5e1;background:#060911;padding:14px;border-radius:8px;border:1px solid #1e293b;">
          <div>[TOP BEZEL] <b style="color:#f87171;">79.5°F Red 7-Segment LED</b> + Red Illuminated Rocker Switch</div>
          <div>[FRONT U12-U09] <b style="color:#f8fafc;">UDM-Pro (.1) + USW-Agg + USW-Pro-Agg (280G) + USW-24-PoE</b> (4× Blue LCMs)</div>
          <div>[FRONT U08-U05] <b style="color:#60a5fa;">esxi01 &amp; esxi02 (2U SFF)</b> • 2× Black Mesh Cages + 8× 2.5" SFF Drives</div>
          <div>[FRONT U04-U01] <b style="color:#34d399;">esxi03 &amp; esxi04 (2U 12-Bay LFF)</b> • 12× 3.5" Horizontal Exos/SAS + Blue UID</div>
          <div>[REAR TOP]      <b style="color:#fbbf24;">Rackmount UPS (1,180W • 100% Battery)</b> feeding Dual HPE FlexSlot PSUs</div>
          <div>[REAR ESXi 2&amp;3] <b style="color:#c084fc;">USW-Pro-Max Etherlighting Switch</b> + 4× Tesla T4 GPUs + HPE iLO4 (.10..40)</div>
        </div>
      </div>
      <!-- Q4 Bottom-Right -->
      <div style="position:absolute;right:22px;bottom:16px;width:928px;height:462px;background:#0a0f1c;border:2px solid #a855f7;border-radius:12px;padding:16px;overflow:hidden;">
        <div style="color:#c084fc;font-size:13px;font-weight:900;margin-bottom:10px;">QUADRANT 04 // $1,000 CLOUD BURST POOLS, DUAL BROWSER ORACLES &amp; SENTINEL (:4099)</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:11px;line-height:1.85;color:#cbd5e1;background:#060911;padding:14px;border-radius:8px;border:1px solid #1e293b;">
          <div>[CLOUD POOLS A-D] <b style="color:#c084fc;">$1,000 Free Credit ($250×4 • Exp Nov 5)</b> • Overage OFF ($0.00 Risk)</div>
          <div>[ACTIVE HARNESSES] <b style="color:#34d399;">bd-pm-B (Opus 5.5) • claude-A..D • codex GPT-6.1-Sol • AGY-Council • Kimi</b></div>
          <div>[BROWSER ORACLES] <b style="color:#38bdf8;">BattleStation (.10.137:9222) + Bittorrent (.70.181:9222)</b> Chrome 155 CDP</div>
          <div>[RAMDISK TURBO]   <b style="color:#10b981;">test3big (.82) 64-vCPU / 128 GB /dev/shm</b> Zero-Disk-IO Pytest Shards</div>
          <div>[INFRA SENTINEL]  <b style="color:#00e5ff;">83/83 Services UP (:4099)</b> • 32/32 Authoritative UniFi DNS Routes HTTP 200</div>
        </div>
      </div>
    </div>
    """


def build_50_ultimate_hybrid() -> str:
    """#50: The Ultimate Hybrid (Left 26%: 12U Front+Rear Rack Twin; Center 48%: ReactFlow+UniFi Graph; Right 26%: Live Inspector & Agent TV)."""
    base = _mod10.build_style_09_physical_rack()
    banner = """
    <div style="position:absolute;left:24px;right:24px;top:12px;height:44px;background:linear-gradient(90deg,#0f172a,#1e1b4b,#042f2e);border:2px solid #00e5ff;border-radius:10px;display:flex;align-items:center;justify-content:space-between;padding:0 20px;z-index:10;">
      <span style="color:#fcee0a;font-size:14.5px;font-weight:900;">MOCKUP #50 / 60 ★ THE ULTIMATE HYBRID (12U FRONT+REAR RACK TWIN + INTERACTIVE NODE GRAPH + AGENT INSPECTOR)</span>
      <span style="color:#00e5ff;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:800;">79.5°F • REAR UPS + USW-PRO-MAX • 4×T4 77.6 TOK/S • 27 VMS • $1K CLOUD</span>
    </div>
    """
    return base + banner


# =============================================================================
# FAMILY 9 (#51-#60): 10 BONUS HIGH-CONTRAST & SPECIALIZED DEEP-DIVE VIEWS
# =============================================================================

def _specialized_matrix(style_num: int, family: str, title: str, badge_txt: str, bg: str, card_bg: str, text_col: str, sub_col: str, accent: str, highlight_filter: str = "") -> str:
    cards = []
    for idx, (name, sub, ip, badge, col, rtype) in enumerate(CLUSTER_NODES[:25]):
        c_i = idx % 5
        r_i = idx // 5
        x = 38 + c_i * 372
        y = 92 + r_i * 184
        use_col = accent if (highlight_filter and highlight_filter in (rtype + name.lower())) else col
        cards.append(f"""
        <g transform="translate({x},{y})">
          <rect width="354" height="168" rx="10" fill="{card_bg}" stroke="{use_col}" stroke-width="2"/>
          <rect width="8" height="168" rx="4" fill="{use_col}"/>
          <text x="22" y="30" fill="{text_col}" font-size="13.5" font-weight="900">{name}</text>
          <text x="338" y="30" text-anchor="end" fill="{use_col}" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="800">{badge}</text>
          <text x="22" y="56" fill="{sub_col}" font-size="11">{sub}</text>
          <text x="22" y="84" fill="{text_col}" font-family="JetBrains Mono,monospace" font-size="10.5" font-weight="700">ENDPOINT: {ip}</text>
          <rect x="22" y="104" width="314" height="44" rx="6" fill="{bg}" stroke="{use_col}" stroke-width="0.9"/>
          <text x="34" y="124" fill="{use_col}" font-family="JetBrains Mono,monospace" font-size="9.5" font-weight="800">TELEMETRY // {family[:28]}</text>
          <text x="34" y="140" fill="{sub_col}" font-family="JetBrains Mono,monospace" font-size="9">79.5°F Rack • Rear UPS + Pro-Max • 100% OK</text>
        </g>
        """)
    return f"""
    <div style="width:1920px;height:1034px;background:{bg};position:relative;overflow:hidden;font-family:'Inter',sans-serif;">
      {_header_banner(style_num, family, title, badge_txt, card_bg, accent, text_col, accent)}
      <svg width="1920" height="1034" style="position:absolute;left:0;top:0;">{''.join(cards)}</svg>
    </div>
    """


def build_51_eink_daylight() -> str:
    return _specialized_matrix(51, "DAYLIGHT E-INK ARCHITECTURAL PAPER MODE", "High-Contrast Warm Archival Paper (#FAF8F5) & India-Ink Topology for Zero-Glare Daylight Viewing", "E-INK PAPER MODE", "#faf8f5", "#ffffff", "#111827", "#4b5563", "#0284c7")


def build_52_oled_midnight() -> str:
    return _specialized_matrix(52, "TRUE 0-NIT OLED PURE-BLACK MIDNIGHT MODE", "Zero-Backlight Pure #000000 OLED Topology Canvas (Only Active 1px Neon Vectors Emit Photons)", "0-NIT TRUE OLED", "#000000", "#050505", "#f8fafc", "#71717a", "#00e5ff")


def build_53_roce_tensor_split() -> str:
    return _specialized_matrix(53, "VLAN 75 // 25GbE ROCE 80-LAYER TENSOR-PARALLEL SPLIT", "80 Transformer Layers Split Across ai-srv01 (.72), aidev (.83 :50052), .125 & .228 (77.62 tok/s)", "25GbE RDMA :50052", "#031219", "#07222e", "#f8fafc", "#94a3b8", "#00e5ff", "gpu")


def build_54_qdrant_vector_cloud() -> str:
    return _specialized_matrix(54, "QDRANT (:6333) 3D VECTOR EMBEDDING & AST SLICE CLOUD", "Node .125 Qdrant HNSW + BattleStation Ryzen 9 Embeddings + ratf.ctx_slice Zero-Token AST Index", "QDRANT :6333 HNSW", "#090618", "#140d30", "#f8fafc", "#a5b4fc", "#a855f7", "infer")


def build_55_sentinel_perimeter_dome() -> str:
    return _specialized_matrix(55, "INFRA SENTINEL (:4099) 83-SERVICE SELF-HEALING DOME", "Autonomous 2-Strike systemd/Docker Self-Healing Shield Across All 27 VMs, 12U Rack & 32 DNS Routes", "83/83 SERVICES GREEN", "#041410", "#08261e", "#ecfdf5", "#6ee7b7", "#10b981", "core")


def build_56_sitemagic_wan_bridge() -> str:
    return _specialized_matrix(56, "UNIFI SITE-MAGIC SD-WAN & 398 STATIC DNS BRIDGE", "BoyleNetwork (10.0.70.1 • UDM-Pro) <-> Boylenet Mobile (10.96.112.1) + 32 New Studio Shortlinks", "398 DNS // SITE-MAGIC", "#071124", "#0f2142", "#f8fafc", "#93c5fd", "#38bdf8", "net")


def build_57_dual_oracle_cdp_wall() -> str:
    return _specialized_matrix(57, "DUAL BROWSER ORACLE CDP (:9222) MULTI-AI FANOUT WALL", "BattleStation (10.0.10.137:9222) + Bittorrent (10.0.70.181:9222) Driving Gemini/ChatGPT/Claude + E2E", "DUAL CDP :9222", "#170f04", "#291b08", "#fef3c7", "#fcd34d", "#f59e0b", "oracle")


def build_58_ramdisk_pytest_matrix() -> str:
    return _specialized_matrix(58, "64-CORE 128GB /DEV/SHM RAMDISK PYTEST SHARD ENGINE", "test3big / wrk-test04 (10.0.70.82) Zero-Disk-IO xdist Verification + bd-pytest-digest Gate", "64C RAMDISK TURBO", "#041612", "#092b23", "#ecfdf5", "#6ee7b7", "#10b981", "vm")


def build_59_timemachine_replay() -> str:
    return _specialized_matrix(59, "TIME-CAPSULE 24-HOUR CLUSTER REPLAY & SNAPSHOT TIMELINE", "bd-vm-timecapsule + bd-log-correlator + Langfuse (:3000) 24-Hour Swarm Replay & Snapshot Rollback", "24H REPLAY READY", "#120924", "#1f113d", "#f8fafc", "#d8b4fe", "#c084fc", "esxi")


def build_60_boylenet_os_masterpiece() -> str:
    """#60: Boylenet OS 'One-Screen Masterpiece' (Unified Top Menu Bar + Left 12U Rack Twin + Center Topology + Bottom Dock)."""
    base = _mod10.build_style_09_physical_rack()
    os_bar = """
    <div style="position:absolute;left:24px;right:24px;top:12px;height:44px;background:rgba(10,16,32,0.95);border:2px solid #fbbf24;border-radius:12px;display:flex;align-items:center;justify-content:space-between;padding:0 22px;z-index:10;box-shadow:0 0 25px rgba(251,191,36,0.35);">
      <span style="color:#fbbf24;font-size:15px;font-weight:900;">👑 MOCKUP #60 / 60 • BOYLENET OS "ONE-SCREEN MASTERPIECE" (12U FRONT/REAR RACK + 27-VM TOPOLOGY + $1K CLOUD)</span>
      <span style="color:#34d399;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:800;">ALL 60 TOPOLOGY DESIGNS LIVE ON :4088/mockups</span>
    </div>
    """
    return base + os_bar


NEW_50_BUILDERS: List[Tuple[int, str, Callable[[], str]]] = [
    (11, "12U Rack Optical & DAC Patch Tracer", build_11_rack_patch_tracer),
    (12, "Exploded HPE DL380 Lid-Off Chassis Cutaway", build_12_exploded_dl380_chassis),
    (13, "Ubiquiti Etherlighting 56-Port Switch Matrix", build_13_etherlighting_port_matrix),
    (14, "FLIR Thermal Infrared & CFD Airflow Rack", build_14_thermal_flir),
    (15, "vSAN 328.4 TiB 75-Disk & 10TB Vault Blueprint", build_15_vsan_blueprint),
    (16, "Iron Man J.A.R.V.I.S. Arc-Reactor Hologram", build_16_jarvis_hud),
    (17, "TRON Legacy Light-Cycle Orthogonal Grid", build_17_tron_grid),
    (18, "Star Trek LCARS Enterprise Engineering Deck", build_18_lcars_startrek),
    (19, "Oblivion / Minority Report Surgical Light-Table", build_19_oblivion_light_table),
    (20, "Weyland-Yutani MU/TH/UR 6000 CRT Phosphor", build_20_crt_phosphor),
    (21, "Datadog APM Service Map & Latency Rings", build_21_datadog_apm),
    (22, "Grafana Node-Graph + 60s Area Sparkline Cards", build_22_grafana_sparklines),
    (23, "Terraform / CloudFormation Declarative DAG", build_23_terraform_dag),
    (24, "Cilium Hubble eBPF VLAN Service Mesh", build_24_cilium_service_mesh),
    (25, "Linear / Vercel Geist Monochrome Dark", build_25_linear_vercel_mono),
    (26, "3D Biological Neural Cortex & Connectome", build_26_neural_synapse),
    (27, "Magnetohydrodynamic Dipole Flux Streamlines", build_27_magnetic_dipole),
    (28, "DNA Double-Helix 10TB Dual-Vault Bridge", build_28_dna_double_helix),
    (29, "Gravitational N-Body Mass & Orbital Moons", build_29_nbody_gravity),
    (30, "Circos 360° Genomic Chord Ribbon Wheel", build_30_circos_chord),
    (31, "Military C4ISR #1: Anduril Lattice & Maven C2", build_31_military_anduril_lattice),
    (32, "Military C4ISR #2: US Navy AEGIS CIC Radar", build_32_military_aegis_cic),
    (33, "Military C4ISR #3: F-35 MFD & Night-Vision HUD", build_33_military_f35_flir_hud),
    (34, "Military C4ISR #4: NORAD WOPR Strategic Theater", build_34_military_norad_wopr),
    (35, "Military C4ISR #5: Rugged 12U TOC Rack C4ISR", build_35_military_tactical_rack_c4isr),
    (36, "Autonomous Swarm Kanban Factory Conveyor", build_36_kanban_factory),
    (37, "12-Harness Gladiator Colosseum Consensus Arena", build_37_gladiator_colosseum),
    (38, "London Underground / Tokyo Metro Subway Map", build_38_subway_metro_map),
    (39, "Split Topology + 6-Screen Live Agent TV Wall", build_39_tv_wall_cockpit),
    (40, "$1,000 Cloud Credit Aviation Fuel-Tank Manifold", build_40_cloud_fuel_tanks),
    (41, "ISO-9001 Prussian Blue CAD Blueprint", build_41_cad_blueprint),
    (42, "Silicon PCB Motherboard & Gold SerDes Traces", build_42_pcb_motherboard),
    (43, "Boylenet Metropolis Cyber-City Skyline", build_43_cyber_city_skyline),
    (44, "IEEE SCADA Electrical Single-Line & Rear UPS", build_44_scada_power_grid),
    (45, "10 TB Dual-Vault 86-Model & vSAN Treemap", build_45_model_vault_treemap),
    (46, "macOS Sequoia / iPadOS Spatial Bento Grid", build_46_sequoia_bento),
    (47, "Cyberpunk 2077 Arasaka Netrunner Breach Deck", build_47_arasaka_netrunner),
    (48, "16-Channel SSL Studio Audio Mixer & VU Meters", build_48_audio_mixer_studio),
    (49, "4-Quadrant Global NOC Command Wallboard", build_49_quad_noc_wallboard),
    (50, "The Ultimate Hybrid (12U Rack + Graph + TV)", build_50_ultimate_hybrid),
    (51, "Daylight E-Ink Architectural Paper Mode", build_51_eink_daylight),
    (52, "True 0-Nit OLED Pure-Black Midnight Mode", build_52_oled_midnight),
    (53, "25GbE RoCE 80-Layer Tensor-Parallel Split", build_53_roce_tensor_split),
    (54, "Qdrant 3D Vector Embedding & AST Point-Cloud", build_54_qdrant_vector_cloud),
    (55, "Infra Sentinel (:4099) 83-Service Defense Dome", build_55_sentinel_perimeter_dome),
    (56, "UniFi Site-Magic SD-WAN & 398 DNS Bridge", build_56_sitemagic_wan_bridge),
    (57, "Dual Browser Oracle CDP (:9222) Fanout Wall", build_57_dual_oracle_cdp_wall),
    (58, "64-Core 128GB /dev/shm Ramdisk Pytest Matrix", build_58_ramdisk_pytest_matrix),
    (59, "Time-Capsule 24-Hour Cluster Replay Timeline", build_59_timemachine_replay),
    (60, "Boylenet OS One-Screen Masterpiece", build_60_boylenet_os_masterpiece),
]

ALL_60_BUILDERS = FIRST_10_BUILDERS + NEW_50_BUILDERS

MILITARY_EXTRA_ALIASES = {
    31: "topology_mockup_military_01_anduril_lattice.png",
    32: "topology_mockup_military_02_aegis_cic.png",
    33: "topology_mockup_military_03_f35_flir_hud.png",
    34: "topology_mockup_military_04_norad_wopr.png",
    35: "topology_mockup_military_05_tactical_rack_c4isr.png",
}


def generate_60_gallery_html() -> str:
    """Build the unified 60-style interactive gallery HTML served at :4088/mockups."""
    options_html = []
    slides_html = []
    js_names = {}
    for idx, title, fn in ALL_60_BUILDERS:
        js_names[idx] = f"STYLE {idx:02d} / 60 — {title}"
        options_html.append(f'<option value="{idx}">#{idx:02d} — {title}</option>')
        slides_html.append(
            f'<div class="mockup-slide" id="slide-{idx}" style="display:{"block" if idx == 1 else "none"};">{fn()}</div>'
        )
    quick_pills = "".join(
        f'<button class="q-pill" onclick="showStyle({i})">{label}</button>'
        for i, label in [
            (1, "01 UniFi"), (2, "02 ReactFlow"), (3, "03 Palantir"), (4, "04 Iso 3D"),
            (9, "09 12U Rack"), (12, "12 DL380 Inside"), (13, "13 Etherlight"), (14, "14 FLIR IR"),
            (16, "16 JARVIS"), (18, "18 LCARS"), (31, "31🎖️ Anduril"), (32, "32🎖️ AEGIS"),
            (33, "33🎖️ F-35 HUD"), (34, "34🎖️ NORAD"), (35, "35🎖️ Mil-Rack"), (50, "50★ Hybrid"), (60, "60👑 OS"),
        ]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=1920, height=1080, initial-scale=1.0"/>
<title>Boylenet 60 Topology &amp; Military C4ISR Visual Mockups (:4088)</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
  html, body {{
    width: 1920px; height: 1080px; overflow: hidden;
    background: #050811; color: #f8fafc;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  }}
  #top-switcher {{
    width: 1920px; height: 46px; background: #0a0e17;
    border-bottom: 1px solid #1e293b;
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 14px; z-index: 9999; position: relative;
  }}
  .brand-title {{ display: flex; align-items: center; gap: 8px; font-size: 12.5px; font-weight: 800; }}
  .brand-pill {{
    background: linear-gradient(135deg, #00e5ff, #3b82f6); color: #040814;
    padding: 3px 8px; border-radius: 5px; font-size: 10px; font-weight: 900;
  }}
  .q-pill {{
    background: #131b2e; border: 1px solid #26334d; color: #cbd5e1;
    padding: 4px 7px; border-radius: 5px; font-size: 10px; font-weight: 700; cursor: pointer;
  }}
  .q-pill:hover {{ border-color: #00e5ff; color: #fff; }}
  select#style-select {{
    background: #0f172a; color: #38bdf8; border: 1px solid #38bdf8;
    border-radius: 6px; padding: 4px 8px; font-size: 11px; font-weight: 800;
  }}
  .mockup-slide {{ width: 1920px; height: 1034px; overflow: hidden; position: relative; }}
</style>
</head>
<body>
  <div id="top-switcher">
    <div class="brand-title">
      <span class="brand-pill">60 MOCKUPS :4088</span>
      <button class="q-pill" onclick="prevStyle()">◀</button>
      <select id="style-select" onchange="showStyle(parseInt(this.value,10))">
        {''.join(options_html)}
      </select>
      <button class="q-pill" onclick="nextStyle()">▶</button>
    </div>
    <div style="display:flex;gap:4px;">{quick_pills}</div>
    <div id="current-style-title" style="font-family:'JetBrains Mono',monospace;font-size:10.5px;color:#38bdf8;font-weight:700;">
      STYLE 01 / 60
    </div>
  </div>
  {''.join(slides_html)}
  <script>
    const STYLE_NAMES = {json.dumps(js_names)};
    function showStyle(n) {{
      if (n < 1) n = 60;
      if (n > 60) n = 1;
      for (let i = 1; i <= 60; i++) {{
        const s = document.getElementById('slide-' + i);
        if (s) s.style.display = (i === n) ? 'block' : 'none';
      }}
      const sel = document.getElementById('style-select');
      if (sel) sel.value = String(n);
      const lbl = document.getElementById('current-style-title');
      if (lbl && STYLE_NAMES[n]) lbl.textContent = STYLE_NAMES[n];
      window.currentStyle = n;
    }}
    function nextStyle() {{ showStyle((window.currentStyle || 1) + 1); }}
    function prevStyle() {{ showStyle((window.currentStyle || 1) - 1); }}
    window.addEventListener('keydown', (e) => {{
      if (e.key === 'ArrowRight') nextStyle();
      else if (e.key === 'ArrowLeft') prevStyle();
    }});
    const params = new URLSearchParams(window.location.search);
    const initial = parseInt(params.get('mockup') || params.get('style') || '1', 10);
    showStyle(initial >= 1 && initial <= 60 ? initial : 1);
  </script>
</body>
</html>
"""


def cdp_call(ws, method: str, params: Dict[str, Any] | None = None, msg_id: int = 1) -> Dict[str, Any]:
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        data = json.loads(ws.recv())
        if data.get("id") == msg_id:
            return data


def render_50_screenshots_via_cdp(url_base: str = "http://10.0.70.164:4088/mockups") -> List[Dict[str, Any]]:
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

    print(f"[CDP] Connected to {chosen_host} (tab {created_tab_id})")
    ws = create_connection(ws_url, timeout=25)
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

        cdp_call(ws, "Page.navigate", {"url": f"{url_base}?style=11"}, msg_seq); msg_seq += 1
        time.sleep(1.4)

        for idx, title, _ in NEW_50_BUILDERS:
            cdp_call(ws, "Page.bringToFront", {}, msg_seq); msg_seq += 1
            cdp_call(
                ws,
                "Runtime.evaluate",
                {"expression": f"showStyle({idx});", "returnByValue": True},
                msg_seq,
            ); msg_seq += 1
            time.sleep(0.12)
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
            png_bytes = base64.b64decode(shot.get("result", {}).get("data", ""))
            out_path = SCREENSHOT_DIR / f"topology_mockup_{idx:02d}.png"
            out_path.write_bytes(png_bytes)
            alias_path_str = None
            if idx in MILITARY_EXTRA_ALIASES:
                alias_path = SCREENSHOT_DIR / MILITARY_EXTRA_ALIASES[idx]
                alias_path.write_bytes(png_bytes)
                alias_path_str = str(alias_path)
            print(f"[OK] #{idx:02d}/60 {out_path.name} ({len(png_bytes):,} B) — {title}")
            results.append({
                "style": idx,
                "title": title,
                "path": str(out_path),
                "military_alias": alias_path_str,
                "bytes": len(png_bytes),
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
    html = generate_60_gallery_html()
    GALLERY_HTML_PATH.write_text(html, encoding="utf-8")
    print(f"[OK] Wrote 60-style interactive gallery to {GALLERY_HTML_PATH} ({len(html):,} bytes)")
    if "--html-only" in sys.argv:
        return
    results = render_50_screenshots_via_cdp()
    print(f"[DONE] Rendered {len(results)} new screenshots (topology_mockup_11.png .. topology_mockup_60.png + 5 Military aliases)")


if __name__ == "__main__":
    main()
