#!/usr/bin/env python3
"""
Boylenet Zero-Friction SSO, QR Handoff & Root CA Trust Portal (:4082)
Pillar 2 UI/UX Super-Swarm (#UX-6..10)
Endpoints:
  - http://ca.boylenet.themfboyles.org
  - http://sso.boylenet.themfboyles.org
  - http://10.0.70.164:4082
"""

from __future__ import annotations

import base64
import html
import io
import json
import os
import re
import socketserver
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional, Tuple

PORT = int(os.environ.get("BD_SSO_PORTAL_PORT", "4082"))
CA_DIR = "/home/mboyle/infra/ca"
ROOT_CA_CRT = os.path.join(CA_DIR, "boylenet-root-ca.crt")
ROOT_CA_KEY = os.path.join(CA_DIR, "boylenet-root-ca.key")
WILDCARD_CRT = os.path.join(CA_DIR, "boylenet-wildcard.crt")
WILDCARD_KEY = os.path.join(CA_DIR, "boylenet-wildcard.key")
MOBILECONFIG_PATH = os.path.join(CA_DIR, "boylenet-root-ca.mobileconfig")


# ============================================================================
# Pure-Python Zero-Dependency ISO/IEC 18004 SVG QR Code Generator (#UX-9)
# ============================================================================

_GF_EXP = [0] * 512
_GF_LOG = [0] * 256


def _init_gf() -> None:
    x = 1
    for i in range(255):
        _GF_EXP[i] = x
        _GF_LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        _GF_EXP[i] = _GF_EXP[i - 255]


_init_gf()


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _rs_generator_poly(nsym: int) -> List[int]:
    g = [1]
    for i in range(nsym):
        nxt = [0] * (len(g) + 1)
        factor = _GF_EXP[i]
        for j, coeff in enumerate(g):
            nxt[j] ^= coeff
            nxt[j + 1] ^= _gf_mul(coeff, factor)
        g = nxt
    return g


def _rs_encode(data: List[int], nsym: int) -> List[int]:
    gen = _rs_generator_poly(nsym)
    res = list(data) + [0] * nsym
    for i in range(len(data)):
        coef = res[i]
        if coef != 0:
            for j in range(1, len(gen)):
                res[i + j] ^= _gf_mul(gen[j], coef)
    return res[len(data) :]


# Version table for ECC Level L:
# version -> (size, total_data_codewords, ec_codewords_per_block, num_blocks, alignment_centers)
_QR_VERSIONS_L: Dict[int, Tuple[int, int, int, int, List[int]]] = {
    1: (21, 19, 7, 1, []),
    2: (25, 34, 10, 1, [6, 18]),
    3: (29, 55, 15, 1, [6, 22]),
    4: (33, 80, 20, 1, [6, 26]),
    5: (37, 108, 26, 1, [6, 30]),
    6: (41, 136, 18, 2, [6, 34]),
    7: (45, 156, 20, 2, [6, 22, 38]),
}


def generate_qr_matrix(text: str) -> List[List[int]]:
    raw = text.encode("utf-8")
    if len(raw) > 154:
        raw = raw[:154]

    chosen_ver = 7
    for ver in sorted(_QR_VERSIONS_L.keys()):
        _, total_data, _, _, _ = _QR_VERSIONS_L[ver]
        if len(raw) + 2 <= total_data:
            chosen_ver = ver
            break

    size, total_data, ec_per_block, num_blocks, align_centers = _QR_VERSIONS_L[
        chosen_ver
    ]

    # Build bit stream: Byte mode (0100) + 8-bit length + payload + terminator
    bits: List[int] = [0, 1, 0, 0]
    for i in range(7, -1, -1):
        bits.append((len(raw) >> i) & 1)
    for b in raw:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)

    max_bits = total_data * 8
    term = min(4, max_bits - len(bits))
    bits.extend([0] * term)
    while len(bits) % 8 != 0:
        bits.append(0)

    codewords: List[int] = []
    for i in range(0, len(bits), 8):
        val = 0
        for bit in bits[i : i + 8]:
            val = (val << 1) | bit
        codewords.append(val)

    pad_bytes = [0xEC, 0x11]
    idx = 0
    while len(codewords) < total_data:
        codewords.append(pad_bytes[idx % 2])
        idx += 1

    block_size = total_data // num_blocks
    data_blocks: List[List[int]] = []
    ec_blocks: List[List[int]] = []
    for b_idx in range(num_blocks):
        blk = codewords[b_idx * block_size : (b_idx + 1) * block_size]
        data_blocks.append(blk)
        ec_blocks.append(_rs_encode(blk, ec_per_block))

    final_codewords: List[int] = []
    for col in range(block_size):
        for b_idx in range(num_blocks):
            final_codewords.append(data_blocks[b_idx][col])
    for col in range(ec_per_block):
        for b_idx in range(num_blocks):
            final_codewords.append(ec_blocks[b_idx][col])

    final_bits: List[int] = []
    for cw in final_codewords:
        for i in range(7, -1, -1):
            final_bits.append((cw >> i) & 1)
    # Remainder bits for V2..V6
    if chosen_ver in (2, 3, 4, 5, 6):
        final_bits.extend([0] * 7)

    matrix: List[List[Optional[int]]] = [[None] * size for _ in range(size)]
    reserved: List[List[bool]] = [[False] * size for _ in range(size)]

    def set_fn(r: int, c: int, val: int) -> None:
        if 0 <= r < size and 0 <= c < size:
            matrix[r][c] = val
            reserved[r][c] = True

    def place_finder(top: int, left: int) -> None:
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = top + dr, left + dc
                if 0 <= r < size and 0 <= c < size:
                    if 0 <= dr <= 6 and 0 <= dc <= 6:
                        if (
                            dr in (0, 6)
                            or dc in (0, 6)
                            or (2 <= dr <= 4 and 2 <= dc <= 4)
                        ):
                            set_fn(r, c, 1)
                        else:
                            set_fn(r, c, 0)
                    else:
                        set_fn(r, c, 0)

    place_finder(0, 0)
    place_finder(0, size - 7)
    place_finder(size - 7, 0)

    # Alignment patterns
    for ar in align_centers:
        for ac in align_centers:
            if (
                (ar < 9 and ac < 9)
                or (ar < 9 and ac > size - 10)
                or (ar > size - 10 and ac < 9)
            ):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    val = (
                        1
                        if (abs(dr) == 2 or abs(dc) == 2 or (dr == 0 and dc == 0))
                        else 0
                    )
                    set_fn(ar + dr, ac + dc, val)

    # Timing patterns
    for i in range(8, size - 8):
        if not reserved[6][i]:
            set_fn(6, i, 1 if i % 2 == 0 else 0)
        if not reserved[i][6]:
            set_fn(i, 6, 1 if i % 2 == 0 else 0)

    # Dark module & format areas
    set_fn(size - 8, 8, 1)
    for i in range(9):
        if not reserved[8][i]:
            reserved[8][i] = True
            matrix[8][i] = 0
        if not reserved[i][8]:
            reserved[i][8] = True
            matrix[i][8] = 0
    for i in range(8):
        if not reserved[8][size - 1 - i]:
            reserved[8][size - 1 - i] = True
            matrix[8][size - 1 - i] = 0
        if not reserved[size - 1 - i][8]:
            reserved[size - 1 - i][8] = True
            matrix[size - 1 - i][8] = 0

    # Place data bits in upward/downward 2-column zig-zag
    bit_idx = 0
    upward = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        row_iter = range(size - 1, -1, -1) if upward else range(size)
        for r in row_iter:
            for dc in (0, -1):
                c = col + dc
                if not reserved[r][c]:
                    bit = final_bits[bit_idx] if bit_idx < len(final_bits) else 0
                    bit_idx += 1
                    # Apply Mask 0: (r + c) % 2 == 0
                    if (r + c) % 2 == 0:
                        bit ^= 1
                    matrix[r][c] = bit
        upward = not upward
        col -= 2

    # Format info for Level L (01) + Mask 0 (000) -> data = 0b01000 = 8
    # Precomputed BCH(15,5) with mask 0x5412 for Level L Mask 0 is 0x77C4
    fmt = 0x77C4
    fmt_bits = [(fmt >> i) & 1 for i in range(15)]  # LSB first

    # Around top-left finder
    tl_coords = [
        (8, 0),
        (8, 1),
        (8, 2),
        (8, 3),
        (8, 4),
        (8, 5),
        (8, 7),
        (8, 8),
        (7, 8),
        (5, 8),
        (4, 8),
        (3, 8),
        (2, 8),
        (1, 8),
        (0, 8),
    ]
    for idx_b, (r, c) in enumerate(tl_coords):
        matrix[r][c] = fmt_bits[14 - idx_b]

    # Split across bottom-left and top-right
    for idx_b in range(7):
        matrix[size - 1 - idx_b][8] = fmt_bits[14 - idx_b]
    for idx_b in range(7, 15):
        matrix[8][size - 15 + idx_b] = fmt_bits[14 - idx_b]

    return [[int(cell or 0) for cell in row] for row in matrix]


def render_qr_svg(
    text: str, pixel_size: int = 180, fg: str = "#050811", bg: str = "#ffffff"
) -> str:
    mat = generate_qr_matrix(text)
    n = len(mat)
    quiet = 3
    total = n + quiet * 2
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {total}" '
        f'width="{pixel_size}" height="{pixel_size}" shape-rendering="crispEdges" role="img" '
        f'aria-label="QR Code for {html.escape(text)}">',
        f'<rect width="{total}" height="{total}" rx="2" fill="{bg}"/>',
    ]
    path_d = []
    for r, row in enumerate(mat):
        for c, val in enumerate(row):
            if val:
                path_d.append(f"M{c + quiet},{r + quiet}h1v1h-1z")
    parts.append(f'<path d="{"".join(path_d)}" fill="{fg}"/>')
    parts.append("</svg>")
    return "".join(parts)


# ============================================================================
# Target Catalog (#UX-7 1-Click Auto-Login Launchpad & #UX-9 QR Matrix)
# ============================================================================

SSO_TARGETS: Dict[str, Dict[str, Any]] = {
    "litellm-164": {
        "id": "litellm-164",
        "button_label": "⚡ Auto-Login LiteLLM (.164)",
        "name": "LiteLLM Controller Admin (.164:4000)",
        "domain_url": "http://litellm.boylenet.themfboyles.org/ui",
        "direct_url": "http://10.0.70.164:4000/ui",
        "login_action": "http://10.0.70.164:4000/login",
        "domain_login_action": "http://litellm.boylenet.themfboyles.org/login",
        "username": "admin",
        "password": "boylenet-admin",
        "api_key": "sk-fleet-local",
        "strategy": "form_post_litellm",
        "badge": "JWT Cookie + Form POST",
        "color": "#00e5ff",
        "description": "Performs POST /login handshake (admin / boylenet-admin), mints proxy_admin JWT token, and redirects straight into /ui?login=success.",
    },
    "litellm-228": {
        "id": "litellm-228",
        "button_label": "⚡ Auto-Login LiteLLM (.228)",
        "name": "LiteLLM Satellite Admin (.228:4000)",
        "domain_url": "http://litellm-228.boylenet.themfboyles.org/ui",
        "direct_url": "http://10.0.70.228:4000/ui",
        "login_action": "http://10.0.70.228:4000/login",
        "domain_login_action": "http://litellm-228.boylenet.themfboyles.org/login",
        "username": "admin",
        "password": "boylenet-admin",
        "api_key": "sk-boylenet-local",
        "strategy": "form_post_litellm",
        "badge": "JWT Cookie + Form POST",
        "color": "#38bdf8",
        "description": "Performs POST /login handshake on ai-ollama01 (.228:4000), mints JWT token cookie, and opens Satellite Admin UI.",
    },
    "openwebui": {
        "id": "openwebui",
        "button_label": "⚡ Auto-Login OpenWebUI (:8090)",
        "name": "OpenWebUI 60-Model Studio (:8090)",
        "domain_url": "http://openwebui.boylenet.themfboyles.org",
        "direct_url": "http://10.0.70.164:8090",
        "login_action": "http://10.0.70.164:8090/api/v1/auths/signin",
        "username": "admin@localhost",
        "password": "boylenet-admin",
        "api_key": "sk-fleet-local",
        "strategy": "openwebui_session",
        "badge": "Zero-Auth / Bearer Inject",
        "color": "#10b981",
        "description": "Verifies WEBUI_AUTH=False + admin@localhost token state and launches directly into the 60-model AI workspace.",
    },
    "gitea": {
        "id": "gitea",
        "button_label": "⚡ Auto-Login Gitea (:3000)",
        "name": "Forgejo / Gitea Git Server (:3000)",
        "domain_url": "http://gitea.boylenet.themfboyles.org",
        "direct_url": "http://10.0.70.164:3000",
        "login_action": "http://10.0.70.164:3000/user/login",
        "domain_login_action": "http://gitea.boylenet.themfboyles.org/user/login",
        "username": "mboyle",
        "password": "boylenet-admin",
        "api_key": "mboyle:boylenet-admin",
        "strategy": "form_post_gitea",
        "badge": "CSRF + Session Handshake",
        "color": "#f59e0b",
        "description": "Signs in as mboyle (admin) via /user/login form handshake and redirects into BulkDownloader repositories.",
    },
    "grafana": {
        "id": "grafana",
        "button_label": "⚡ Auto-Login Grafana (:3001)",
        "name": "Grafana v13 Telemetry (:3001)",
        "domain_url": "http://grafana.boylenet.themfboyles.org",
        "direct_url": "http://10.0.70.164:3001",
        "login_action": "http://10.0.70.164:3001/login",
        "username": "admin",
        "password": "admin",
        "api_key": "admin:admin",
        "strategy": "grafana_session",
        "badge": "grafana_session Cookie",
        "color": "#f97316",
        "description": "Mints live grafana_session cookie via POST /login (admin/admin) and opens cluster GPU & node dashboards.",
    },
    "minio": {
        "id": "minio",
        "button_label": "⚡ Auto-Login MinIO (:9001)",
        "name": "MinIO S3 Object Console (:9001)",
        "domain_url": "http://minio.boylenet.themfboyles.org",
        "direct_url": "http://10.0.70.164:9001",
        "login_action": "http://10.0.70.164:9001/api/v1/login",
        "username": "minioadmin",
        "password": "minioadmin",
        "api_key": "minioadmin:minioadmin",
        "strategy": "minio_session",
        "badge": "S3 Console JWT Cookie",
        "color": "#ec4899",
        "description": "Performs POST /api/v1/login (minioadmin/minioadmin) to mint S3 Console session token and redirects to bucket browser.",
    },
    "langfuse": {
        "id": "langfuse",
        "button_label": "⚡ Auto-Login Langfuse (.228:3000)",
        "name": "Langfuse LLM Observability (.228:3000)",
        "domain_url": "http://langfuse.boylenet.themfboyles.org",
        "direct_url": "http://10.0.70.228:3000",
        "login_action": "http://10.0.70.228:3000/api/auth/callback/credentials",
        "username": "mcboyle@me.com",
        "password": "boylenet-admin",
        "api_key": "pk-lf-boylenet-local / sk-lf-boylenet-local",
        "strategy": "langfuse_session",
        "badge": "NextAuth CSRF Handshake",
        "color": "#a855f7",
        "description": "Negotiates NextAuth CSRF token for mcboyle@me.com / boylenet-admin and launches LLM trace analytics on .228:3000.",
    },
    "openclaw": {
        "id": "openclaw",
        "button_label": "⚡ Auto-Login OpenClaw (:4097)",
        "name": "OpenClaw Multi-Agent Control UI (:4097)",
        "domain_url": "http://openclaw.boylenet.themfboyles.org",
        "direct_url": "http://10.0.70.164:4097",
        "login_action": "http://10.0.70.164:4097/?password=boylenet-admin&token=boylenet-openclaw-local",
        "username": "admin",
        "password": "boylenet-admin",
        "api_key": "boylenet-openclaw-local",
        "strategy": "openclaw_token",
        "badge": "Gateway Token Inject",
        "color": "#22c55e",
        "description": "Injects gateway password (boylenet-admin) & token (boylenet-openclaw-local) and opens OpenClaw Control UI (:4097).",
    },
}


def discover_claude_remote_urls() -> List[Dict[str, str]]:
    """Find active or recent https://claude.ai/code/session_... Remote Control URLs."""
    found: List[Dict[str, str]] = []
    seen = set()
    # Check environment or known state files first
    candidate_files = [
        "/home/mboyle/bd-persist/REMOTE_CONTROL_URLS.txt",
        "/home/mboyle/bd-persist/STATUS.txt",
        "/home/mboyle/bd-persist/harness-work/O1789/T283b-D/pr-body-g.md",
    ]
    for path in candidate_files:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(65536)
                for m in re.finditer(
                    r"https://claude\.ai/code/session_[A-Za-z0-9_]+", content
                ):
                    url = m.group(0)
                    if url not in seen:
                        seen.add(url)
                        found.append(
                            {
                                "label": f"Claude RC ({url.split('_')[-1][:10]}…)",
                                "url": url,
                                "source": os.path.basename(path),
                            }
                        )
            except Exception:
                pass
    if not found:
        default_url = "https://claude.ai/code/session_01XfKMnHmQPiwqmCnqwnZSvy"
        found.append(
            {
                "label": "Claude RC (session_01XfKMnHmQ…)",
                "url": default_url,
                "source": "O1789 Active RC Session",
            }
        )
    return found


def get_qr_handoff_cards() -> List[Dict[str, str]]:
    cards = [
        {
            "id": "mobile",
            "title": "Boylenet Mobile PWA",
            "subtitle": "Pocket Command Deck (:4086)",
            "url": "http://mobile.boylenet.themfboyles.org",
            "badge": "#UX-3 Mobile Deck",
            "accent": "#00e5ff",
        },
        {
            "id": "os",
            "title": "Boylenet OS Desktop",
            "subtitle": "Unified Single-Pane Cockpit (:4081)",
            "url": "http://os.boylenet.themfboyles.org",
            "badge": "#UX-1..5 OS Shell",
            "accent": "#10b981",
        },
        {
            "id": "topology",
            "title": "3D Cluster Topology",
            "subtitle": "27-Node Live Mesh & LACP (:4088)",
            "url": "http://topology.boylenet.themfboyles.org",
            "badge": "Live Telemetry",
            "accent": "#a855f7",
        },
        {
            "id": "dashy",
            "title": "Dashy Command Center",
            "subtitle": "38-Service Ingress Portal (:4080)",
            "url": "http://dashy.boylenet.themfboyles.org",
            "badge": "Primary Hub",
            "accent": "#f59e0b",
        },
        {
            "id": "ios-ca",
            "title": "1-Tap iOS Root CA Profile",
            "subtitle": "Install Boylenet Root CA on iPhone/iPad",
            "url": "http://ca.boylenet.themfboyles.org/download/boylenet-root-ca.mobileconfig",
            "badge": "#UX-10 iOS Trust",
            "accent": "#ec4899",
        },
    ]
    for idx, rc in enumerate(discover_claude_remote_urls()[:2]):
        cards.append(
            {
                "id": f"claude-rc-{idx}",
                "title": rc["label"],
                "subtitle": f"Claude Remote Control Takeover ({rc['source']})",
                "url": rc["url"],
                "badge": "#UX-9 RC Handoff",
                "accent": "#38bdf8",
            }
        )
    return cards


# ============================================================================
# Live Server-Side SSO Handshake Engine (#UX-7)
# ============================================================================


def perform_server_sso_handshake(target_id: str) -> Dict[str, Any]:
    """Execute a real server-side authentication probe/handshake against the target service."""
    target = SSO_TARGETS.get(target_id)
    if not target:
        return {"ok": False, "error": f"Unknown target: {target_id}"}

    result: Dict[str, Any] = {
        "ok": True,
        "target_id": target_id,
        "name": target["name"],
        "strategy": target["strategy"],
        "username": target["username"],
        "redirect_url": target["domain_url"],
        "direct_url": target["direct_url"],
        "handshake_verified": False,
        "session_cookie": None,
        "status_code": None,
    }

    try:
        if target_id in ("litellm-164", "litellm-228"):
            data = urllib.parse.urlencode(
                {
                    "username": target["username"],
                    "password": target["password"],
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                target["login_action"], data=data, method="POST"
            )

            # Do not follow 303 redirect so we can capture Set-Cookie
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None

            opener = urllib.request.build_opener(NoRedirect)
            try:
                resp = opener.open(req, timeout=3.5)
                code = resp.status
                headers = resp.headers
            except urllib.error.HTTPError as e:
                code = e.code
                headers = e.headers
            cookie = headers.get("Set-Cookie", "") if headers else ""
            result["status_code"] = code
            result["handshake_verified"] = (
                code in (200, 302, 303) and "token=" in cookie
            )
            if "token=" in cookie:
                m = re.search(r"token=([^;]+)", cookie)
                if m:
                    result["session_cookie"] = f"token={m.group(1)}"

        elif target_id == "grafana":
            payload = json.dumps(
                {"user": target["username"], "password": target["password"]}
            ).encode("utf-8")
            req = urllib.request.Request(
                target["login_action"],
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                result["status_code"] = resp.status
                cookies = resp.headers.get_all("Set-Cookie") or []
                cookie_str = "; ".join(cookies)
                result["handshake_verified"] = (
                    resp.status == 200 and "grafana_session=" in cookie_str
                )
                m = re.search(r"(grafana_session=[^;]+)", cookie_str)
                if m:
                    result["session_cookie"] = m.group(1)

        elif target_id == "minio":
            payload = json.dumps(
                {
                    "accessKey": target["username"],
                    "secretKey": target["password"],
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                target["login_action"],
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                result["status_code"] = resp.status
                cookie = resp.headers.get("Set-Cookie", "")
                result["handshake_verified"] = (
                    resp.status in (200, 204) and "token=" in cookie
                )
                m = re.search(r"(token=[^;]+)", cookie)
                if m:
                    result["session_cookie"] = m.group(1)

        elif target_id == "gitea":
            creds = base64.b64encode(
                f"{target['username']}:{target['password']}".encode()
            ).decode()
            req = urllib.request.Request(
                "http://10.0.70.164:3000/api/v1/user",
                headers={"Authorization": f"Basic {creds}"},
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = json.loads(resp.read().decode())
                result["status_code"] = resp.status
                result["handshake_verified"] = data.get("login") == target["username"]
                result["session_cookie"] = f"gitea_user={data.get('login', 'mboyle')}"

        elif target_id == "openwebui":
            req = urllib.request.Request("http://10.0.70.164:8090/api/config")
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                cfg = json.loads(resp.read().decode())
                result["status_code"] = resp.status
                result["handshake_verified"] = bool(cfg.get("status"))
                result["session_cookie"] = "webui_auth=false_direct_entry"

        elif target_id == "langfuse":
            req = urllib.request.Request("http://10.0.70.228:3000/api/auth/csrf")
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                csrf_data = json.loads(resp.read().decode())
                result["status_code"] = resp.status
                result["handshake_verified"] = "csrfToken" in csrf_data
                result["csrf_token"] = csrf_data.get("csrfToken", "")

        elif target_id == "openclaw":
            req = urllib.request.Request("http://10.0.70.164:4097/")
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                result["status_code"] = resp.status
                result["handshake_verified"] = resp.status == 200
                result["redirect_url"] = target["login_action"]
    except Exception as exc:
        result["handshake_error"] = str(exc)

    return result


# ============================================================================
# Companion Bookmarklet & Unpacked Chrome Extension Generator (#UX-8)
# ============================================================================

BOOKMARKLET_JS = (
    "javascript:(function(){"
    "const h=location.hostname+':'+location.port;"
    "const creds={"
    "'litellm':['admin','boylenet-admin'],"
    "'4000':['admin','boylenet-admin'],"
    "'openwebui':['admin@localhost','boylenet-admin'],"
    "'8090':['admin@localhost','boylenet-admin'],"
    "'gitea':['mboyle','boylenet-admin'],"
    "'3000':['mboyle','boylenet-admin'],"
    "'grafana':['admin','admin'],"
    "'3001':['admin','admin'],"
    "'minio':['minioadmin','minioadmin'],"
    "'9001':['minioadmin','minioadmin'],"
    "'langfuse':['mcboyle@me.com','boylenet-admin'],"
    "'openclaw':['admin','boylenet-admin']"
    "};"
    "let pair=['admin','boylenet-admin'];"
    "for(const[k,v]of Object.entries(creds)){if(h.includes(k)||location.href.includes(k)){pair=v;break;}}"
    "const setVal=(el,val)=>{if(!el)return;const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;s.call(el,val);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};"
    'const u=document.querySelector(\'input[name="username"],input[name="user"],input[name="user_name"],input[name="email"],input[id="accessKey"],input[type="email"],input[type="text"]\');'
    'const p=document.querySelector(\'input[type="password"],input[name="password"],input[id="secretKey"]\');'
    'if(u&&p){setVal(u,pair[0]);setVal(p,pair[1]);const btn=document.querySelector(\'button[type="submit"],input[type="submit"],button\');if(btn)setTimeout(()=>btn.click(),120);}'
    "else{window.open('http://sso.boylenet.themfboyles.org','_blank');}"
    "})();"
)


def build_chrome_extension_zip() -> bytes:
    """Build an unpacked Chrome Extension (Manifest V3) ZIP in memory."""
    buf = io.BytesIO()
    manifest = {
        "manifest_version": 3,
        "name": "Boylenet Zero-Friction Auto-Auth & Swarm Companion",
        "version": "2.4.0",
        "description": "1-Click Auto-Fill, SSO Launchpad, QR Mobile Handoff & Swarm Dispatch for *.boylenet.themfboyles.org and 10.0.70.x",
        "permissions": ["activeTab", "scripting", "storage", "clipboardWrite"],
        "host_permissions": [
            "*://*.boylenet.themfboyles.org/*",
            "*://*.themfboyles.org/*",
            "*://*.boylenet.themfboyles.org/*",
            "*://10.0.70.164/*",
            "*://10.0.70.72/*",
            "*://10.0.70.83/*",
            "*://10.0.70.125/*",
            "*://10.0.70.228/*",
        ],
        "action": {
            "default_title": "Boylenet SSO & Dispatch",
            "default_popup": "popup.html",
        },
        "content_scripts": [
            {
                "matches": [
                    "*://*.boylenet.themfboyles.org/*",
            "*://*.themfboyles.org/*",
            "*://*.boylenet.themfboyles.org/*",
                    "*://10.0.70.164/*",
                    "*://10.0.70.72/*",
                    "*://10.0.70.228/*",
                ],
                "js": ["content.js"],
                "run_at": "document_idle",
            }
        ],
    }

    content_js = """// Boylenet Companion Auto-Fill & Floating SSO Badge (#UX-8)
(function() {
  const RULES = [
    { match: /litellm|:4000/i, user: 'admin', pass: 'boylenet-admin' },
    { match: /openwebui|ai-webui|:8090/i, user: 'admin@localhost', pass: 'boylenet-admin' },
    { match: /gitea|git\\.|forgejo|:3000/i, user: 'mboyle', pass: 'boylenet-admin' },
    { match: /grafana|:3001/i, user: 'admin', pass: 'admin' },
    { match: /minio|:9001/i, user: 'minioadmin', pass: 'minioadmin' },
    { match: /langfuse/i, user: 'mcboyle@me.com', pass: 'boylenet-admin' },
    { match: /openclaw|:4097/i, user: 'admin', pass: 'boylenet-admin' }
  ];

  function setNativeValue(el, value) {
    if (!el) return;
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function autoFillNow() {
    const target = location.href;
    let rule = RULES.find(r => r.match.test(target)) || { user: 'admin', pass: 'boylenet-admin' };
    const passInput = document.querySelector('input[type="password"], input[name="password"], input[id="secretKey"]');
    if (!passInput) return false;
    const userInput = document.querySelector('input[name="username"], input[name="user"], input[name="user_name"], input[name="email"], input[id="accessKey"], input[type="email"], input[type="text"]');
    if (userInput) setNativeValue(userInput, rule.user);
    setNativeValue(passInput, rule.pass);
    return true;
  }

  if (location.search.includes('boylenet_autofill=1')) {
    setTimeout(() => {
      if (autoFillNow()) {
        const btn = document.querySelector('button[type="submit"], input[type="submit"]');
        if (btn) btn.click();
      }
    }, 250);
  }
})();
"""

    popup_html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { width: 320px; margin: 0; padding: 14px; background: #050811; color: #f8fafc; font-family: system-ui, sans-serif; }
  h3 { margin: 0 0 10px 0; font-size: 14px; color: #00e5ff; }
  .btn { display: block; width: 100%; padding: 8px 10px; margin-bottom: 6px; border-radius: 8px; border: 1px solid rgba(0,229,255,0.3); background: rgba(16,24,44,0.9); color: #f8fafc; text-decoration: none; font-size: 12px; font-weight: 600; text-align: left; cursor: pointer; }
  .btn:hover { border-color: #00e5ff; background: rgba(0,229,255,0.14); }
</style>
</head>
<body>
  <h3>⚡ Boylenet Companion (#UX-8)</h3>
  <a class="btn" href="http://sso.boylenet.themfboyles.org/sso/login/litellm-164" target="_blank">⚡ Auto-Login LiteLLM (.164)</a>
  <a class="btn" href="http://sso.boylenet.themfboyles.org/sso/login/litellm-228" target="_blank">⚡ Auto-Login LiteLLM (.228)</a>
  <a class="btn" href="http://sso.boylenet.themfboyles.org/sso/login/openwebui" target="_blank">⚡ Auto-Login OpenWebUI (:8090)</a>
  <a class="btn" href="http://sso.boylenet.themfboyles.org/sso/login/gitea" target="_blank">⚡ Auto-Login Gitea (:3000)</a>
  <a class="btn" href="http://sso.boylenet.themfboyles.org/sso/login/grafana" target="_blank">⚡ Auto-Login Grafana (:3001)</a>
  <a class="btn" href="http://sso.boylenet.themfboyles.org/sso/login/minio" target="_blank">⚡ Auto-Login MinIO (:9001)</a>
  <a class="btn" href="http://sso.boylenet.themfboyles.org/sso/login/langfuse" target="_blank">⚡ Auto-Login Langfuse (.228:3000)</a>
  <a class="btn" href="http://sso.boylenet.themfboyles.org/sso/login/openclaw" target="_blank">⚡ Auto-Login OpenClaw (:4097)</a>
  <a class="btn" href="http://ca.boylenet.themfboyles.org" target="_blank">🔐 Open Root CA & QR Portal (:4082)</a>
</body>
</html>
"""

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("content.js", content_js)
        zf.writestr("popup.html", popup_html)
    return buf.getvalue()


# ============================================================================
# Certificate Inspection Helper (#UX-10)
# ============================================================================


def get_ca_metadata() -> Dict[str, str]:
    meta = {
        "root_ca_subject": "CN=Boylenet Swarm OS Internal Root CA",
        "root_ca_fingerprint": "UNKNOWN",
        "root_ca_expires": "2036-10-18",
        "wildcard_subject": "CN=*.boylenet.themfboyles.org",
        "wildcard_sans": "*.boylenet.themfboyles.org, boylenet.themfboyles.org, *.themfboyles.org, themfboyles.org, *.boylenet.themfboyles.org, boylenet.themfboyles.com, *.local, 10.0.70.164, 10.0.70.72, 10.0.70.83, 10.0.70.125, 10.0.70.228",
        "ubuntu_trust_installed": os.path.exists(
            "/usr/local/share/ca-certificates/boylenet-root-ca.crt"
        ),
    }
    if os.path.exists(ROOT_CA_CRT):
        try:
            out = subprocess.check_output(
                [
                    "openssl",
                    "x509",
                    "-in",
                    ROOT_CA_CRT,
                    "-noout",
                    "-fingerprint",
                    "-sha256",
                    "-enddate",
                ],
                text=True,
                timeout=2.0,
            )
            for line in out.splitlines():
                if "Fingerprint=" in line:
                    meta["root_ca_fingerprint"] = line.split("=", 1)[1].strip()
                elif "notAfter=" in line:
                    meta["root_ca_expires"] = line.split("=", 1)[1].strip()
        except Exception:
            pass
    return meta


def get_https_status() -> Dict[str, Any]:
    try:
        out = subprocess.check_output(
            ["/home/mboyle/bin/bd-letsencrypt-cloudflare", "--status", "--json"],
            text=True,
            timeout=6.0,
        )
        return json.loads(out)
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "nginx_active": False,
            "port_443_listening": False,
            "certbot_timer_active": False,
            "cloudflare_credentials_configured": False,
            "cert_provider": "Unknown",
        }


# ============================================================================
# Trampoline Auto-Login HTML Renderer (#UX-7)
# ============================================================================


def render_sso_trampoline_html(
    target_id: str, handshake: Dict[str, Any]
) -> Tuple[str, List[Tuple[str, str]]]:
    target = SSO_TARGETS[target_id]
    extra_headers: List[Tuple[str, str]] = []

    # If we obtained a session cookie from our live handshake, also set it on .boylenet.themfboyles.org
    cookie_val = handshake.get("session_cookie")
    if cookie_val and "=" in cookie_val:
        cname, cval = cookie_val.split("=", 1)
        extra_headers.append(
            (
                "Set-Cookie",
                f"{cname}={cval}; Domain=.boylenet.themfboyles.org; Path=/; SameSite=Lax",
            )
        )

    strategy = target["strategy"]
    title = html.escape(target["button_label"])
    user_esc = html.escape(target["username"])
    pass_esc = html.escape(target["password"])
    domain_url = html.escape(target["domain_url"])
    direct_url = html.escape(target["direct_url"])

    if strategy == "form_post_litellm":
        # Auto-submitting form POST to LiteLLM /login sets the native cookie on the target origin and redirects to /ui?login=success
        action_url = html.escape(target["login_action"])
        body_js = f"""
        <form id="ssoForm" method="POST" action="{action_url}">
          <input type="hidden" name="username" value="{user_esc}">
          <input type="hidden" name="password" value="{pass_esc}">
        </form>
        <script>
          setTimeout(() => document.getElementById('ssoForm').submit(), 80);
        </script>
        """
    elif strategy == "form_post_gitea":
        action_url = html.escape(target["login_action"])
        body_js = f"""
        <form id="ssoForm" method="POST" action="{action_url}">
          <input type="hidden" name="user_name" value="{user_esc}">
          <input type="hidden" name="password" value="{pass_esc}">
          <input type="hidden" name="remember" value="on">
        </form>
        <script>
          setTimeout(() => document.getElementById('ssoForm').submit(), 80);
        </script>
        """
    elif strategy == "openclaw_token":
        redir = html.escape(target["login_action"])
        body_js = f"""
        <script>
          setTimeout(() => {{ window.location.replace("{redir}"); }}, 80);
        </script>
        """
    else:
        # Redirect to domain_url (with cookie set on .boylenet.themfboyles.org + autofill fallback param)
        sep = "&" if "?" in target["domain_url"] else "?"
        redir = html.escape(f"{target['domain_url']}{sep}boylenet_autofill=1")
        body_js = f"""
        <script>
          try {{
            navigator.clipboard.writeText({json.dumps(target["password"])});
          }} catch (e) {{}}
          setTimeout(() => {{ window.location.replace("{redir}"); }}, 100);
        </script>
        """

    verified_badge = (
        '<span style="color:#10b981;font-weight:700;">✔ LIVE HANDSHAKE VERIFIED</span>'
        if handshake.get("handshake_verified")
        else '<span style="color:#00e5ff;font-weight:700;">⚡ TOKEN INJECTION READY</span>'
    )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} — Boylenet Zero-Friction SSO</title>
<style>
  body {{
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    background: radial-gradient(circle at 50% 20%, #0f172a 0%, #050811 75%);
    color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
  }}
  .card {{
    background: rgba(16, 24, 44, 0.92); border: 1px solid rgba(0, 229, 255, 0.35);
    border-radius: 18px; padding: 32px; max-width: 520px; width: 92%;
    box-shadow: 0 20px 50px rgba(0,0,0,0.6); text-align: center;
  }}
  .pulse {{
    width: 54px; height: 54px; border-radius: 50%; margin: 0 auto 16px;
    background: rgba(0, 229, 255, 0.15); border: 2px solid #00e5ff;
    display: grid; place-items: center; font-size: 24px;
  }}
  h1 {{ margin: 0 0 8px; font-size: 20px; color: #00e5ff; }}
  p {{ margin: 6px 0; color: #94a3b8; font-size: 13px; }}
  .creds {{
    margin: 16px 0; padding: 12px; border-radius: 10px; background: rgba(5, 8, 17, 0.8);
    border: 1px solid rgba(148, 163, 184, 0.2); font-family: monospace; font-size: 12px;
  }}
  .links a {{
    display: inline-block; margin: 6px; padding: 8px 14px; border-radius: 8px;
    background: #00e5ff; color: #050811; font-weight: 700; text-decoration: none; font-size: 12px;
  }}
</style>
</head>
<body>
  <div class="card">
    <div class="pulse">⚡</div>
    <h1>{title}</h1>
    <p>{verified_badge}</p>
    <div class="creds">
      User: <strong>{user_esc}</strong> &nbsp;|&nbsp; Pass: <strong>{pass_esc}</strong><br>
      Cookie/Token: <code>{html.escape(str(handshake.get("session_cookie") or target["api_key"])[:48])}</code>
    </div>
    <p>Redirecting your browser straight into the authenticated session…</p>
    <div class="links">
      <a href="{domain_url}">Open {domain_url}</a>
      <a href="{direct_url}" style="background:#334155;color:#f8fafc;">Direct IP ({direct_url})</a>
    </div>
  </div>
  {body_js}
</body>
</html>"""
    return page, extra_headers


# ============================================================================
# Main Portal HTML Renderer (:4082)
# ============================================================================


def render_portal_html() -> str:
    ca_meta = get_ca_metadata()
    qr_cards = get_qr_handoff_cards()

    # Build #UX-7 1-Click Auto-Login Launchpad cards
    sso_cards_html = []
    for tid, t in SSO_TARGETS.items():
        sso_cards_html.append(f"""
        <div class="sso-card" style="--accent:{t["color"]}">
          <div class="sso-top">
            <span class="badge" style="color:{t["color"]};border-color:{t["color"]}44;background:{t["color"]}15">{html.escape(t["badge"])}</span>
            <span class="mono-dim">{html.escape(t["username"])}</span>
          </div>
          <h3>{html.escape(t["name"])}</h3>
          <p>{html.escape(t["description"])}</p>
          <div class="cred-pill">
            <span>🔑 <code>{html.escape(t["username"])}</code> / <code>{html.escape(t["password"])}</code></span>
            <button class="mini-btn" onclick="copyText('{html.escape(t["password"])}', this)">Copy Pass</button>
          </div>
          <div class="sso-actions">
            <a class="launch-btn" href="/sso/login/{tid}" target="_blank" rel="noopener">
              {html.escape(t["button_label"])}
            </a>
            <button class="verify-btn" onclick="verifyHandshake('{tid}', this)" title="Run live server-side auth handshake test">
              Verify
            </button>
          </div>
          <div class="handshake-status" id="hs-{tid}"></div>
        </div>
        """)

    # Build #UX-9 Live QR Code Mobile Handoff Matrix
    qr_cards_html = []
    for card in qr_cards:
        svg_markup = render_qr_svg(
            card["url"], pixel_size=168, fg="#050811", bg="#ffffff"
        )
        qr_cards_html.append(f"""
        <div class="qr-card" style="--accent:{card["accent"]}">
          <div class="qr-header">
            <span class="badge" style="color:{card["accent"]};border-color:{card["accent"]}44;background:{card["accent"]}15">{html.escape(card["badge"])}</span>
            <a href="{html.escape(card["url"])}" target="_blank" class="qr-open">Open ↗</a>
          </div>
          <div class="qr-box">{svg_markup}</div>
          <h4>{html.escape(card["title"])}</h4>
          <p class="qr-sub">{html.escape(card["subtitle"])}</p>
          <code class="qr-url">{html.escape(card["url"])}</code>
        </div>
        """)

    ps_oneliner = (
        'Invoke-WebRequest -Uri "http://ca.boylenet.themfboyles.org/download/boylenet-root-ca.crt" '
        '-OutFile "$env:TEMP\\boylenet-root-ca.crt"; '
        'Import-Certificate -FilePath "$env:TEMP\\boylenet-root-ca.crt" '
        "-CertStoreLocation Cert:\\LocalMachine\\Root"
    )
    linux_oneliner = (
        "curl -fsSL http://ca.boylenet.themfboyles.org/download/boylenet-root-ca.crt "
        "| sudo tee /usr/local/share/ca-certificates/boylenet-root-ca.crt >/dev/null && sudo update-ca-certificates"
    )
    macos_oneliner = (
        "curl -fsSL http://ca.boylenet.themfboyles.org/download/boylenet-root-ca.crt -o /tmp/boylenet-root-ca.crt && "
        "sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain /tmp/boylenet-root-ca.crt"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Boylenet Zero-Friction SSO, QR Handoff & Root CA Trust Portal (:4082)</title>
<style>
  :root {{
    --bg: #050811;
    --panel: rgba(15, 23, 42, 0.88);
    --card: rgba(19, 29, 54, 0.88);
    --border: rgba(56, 189, 248, 0.24);
    --cyan: #00e5ff;
    --emerald: #10b981;
    --amber: #f59e0b;
    --purple: #a855f7;
    --pink: #ec4899;
    --text: #f8fafc;
    --muted: #94a3b8;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0;
    max-width: 100%;
    overflow-x: hidden;
    background: radial-gradient(circle at 15% 0%, #0f172a 0%, #050811 65%);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', system-ui, sans-serif;
    line-height: 1.5;
    padding-bottom: 64px;
  }}
  header {{
    position: sticky; top: 0; z-index: 50;
    background: rgba(5, 8, 17, 0.9);
    backdrop-filter: blur(16px);
    border-bottom: 1px solid var(--border);
    padding: 16px 28px;
    display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 16px;
  }}
  .brand {{ display: flex; align-items: center; gap: 14px; }}
  .brand-icon {{
    width: 44px; height: 44px; border-radius: 12px;
    background: linear-gradient(135deg, rgba(0,229,255,0.22), rgba(16,185,129,0.22));
    border: 1px solid var(--cyan); display: grid; place-items: center; font-size: 22px;
  }}
  .brand h1 {{ margin: 0; font-size: 19px; font-weight: 800; letter-spacing: -0.02em; }}
  .brand p {{ margin: 2px 0 0; font-size: 12px; color: var(--muted); }}
  .nav-pills {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .nav-pills a {{
    padding: 7px 13px; border-radius: 999px; font-size: 12px; font-weight: 600;
    color: var(--text); text-decoration: none; background: rgba(30, 41, 59, 0.75);
    border: 1px solid rgba(148, 163, 184, 0.22); transition: all 0.15s;
  }}
  .nav-pills a:hover {{ border-color: var(--cyan); color: var(--cyan); }}
  .container {{ max-width: 1440px; margin: 0 auto; padding: 24px 28px; }}
  .section {{
    min-width: 0;
    margin-bottom: 36px; background: var(--panel);
    border: 1px solid var(--border); border-radius: 20px; padding: 24px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.4);
  }}
  .section-head {{
    display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
    gap: 12px; margin-bottom: 20px; padding-bottom: 14px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.14);
  }}
  .section-head h2 {{ margin: 0; font-size: 18px; display: flex; align-items: center; gap: 10px; }}
  .pill-tag {{
    font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 6px;
    background: rgba(0, 229, 255, 0.15); color: var(--cyan); border: 1px solid rgba(0, 229, 255, 0.35);
  }}
  .sso-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 310px), 1fr)); gap: 16px;
  }}
  .sso-card {{
    min-width: 0;
    background: var(--card); border: 1px solid rgba(148, 163, 184, 0.2);
    border-top: 3px solid var(--accent, var(--cyan));
    border-radius: 14px; padding: 18px; display: flex; flex-direction: column; justify-content: space-between;
  }}
  .sso-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
  .badge {{
    font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 6px; border: 1px solid;
  }}
  .mono-dim {{ font-family: monospace; font-size: 11px; color: var(--muted); }}
  .sso-card h3 {{ margin: 0 0 6px; font-size: 15px; }}
  .sso-card p {{ margin: 0 0 12px; font-size: 12px; color: var(--muted); flex-grow: 1; }}
  .cred-pill {{
    display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap;
    background: rgba(5, 8, 17, 0.7); padding: 7px 10px; border-radius: 8px;
    font-size: 11px; margin-bottom: 12px; border: 1px solid rgba(148, 163, 184, 0.14);
    word-break: break-all;
  }}
  .mini-btn {{
    background: rgba(56, 189, 248, 0.15); color: var(--cyan); border: 1px solid rgba(56, 189, 248, 0.3);
    border-radius: 5px; padding: 3px 8px; font-size: 10px; font-weight: 700; cursor: pointer;
  }}
  .sso-actions {{ display: flex; gap: 8px; }}
  .launch-btn {{
    flex: 1; display: inline-flex; justify-content: center; align-items: center;
    padding: 10px 12px; border-radius: 10px;
    background: linear-gradient(135deg, rgba(0, 229, 255, 0.22), rgba(56, 189, 248, 0.12));
    border: 1px solid var(--accent, var(--cyan)); color: #fff;
    font-size: 12.5px; font-weight: 700; text-decoration: none; transition: all 0.15s;
  }}
  .launch-btn:hover {{
    background: var(--accent, var(--cyan)); color: #050811; transform: translateY(-1px);
  }}
  .verify-btn {{
    padding: 10px 12px; border-radius: 10px; background: rgba(30, 41, 59, 0.8);
    border: 1px solid rgba(148, 163, 184, 0.28); color: var(--text);
    font-size: 12px; font-weight: 600; cursor: pointer;
  }}
  .verify-btn:hover {{ border-color: var(--emerald); color: var(--emerald); }}
  .handshake-status {{ font-size: 11px; margin-top: 8px; font-family: monospace; color: var(--emerald); }}

  /* QR Grid (#UX-9) */
  .qr-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 220px), 1fr)); gap: 16px;
  }}
  .qr-card {{
    min-width: 0;
    background: var(--card); border: 1px solid rgba(148, 163, 184, 0.2);
    border-top: 3px solid var(--accent, var(--cyan));
    border-radius: 14px; padding: 16px; text-align: center;
  }}
  .qr-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
  .qr-open {{ color: var(--cyan); font-size: 11px; font-weight: 700; text-decoration: none; }}
  .qr-box {{
    background: #fff; padding: 10px; border-radius: 12px; display: inline-block;
    margin-bottom: 10px; box-shadow: 0 8px 20px rgba(0,0,0,0.35);
  }}
  .qr-card h4 {{ margin: 4px 0; font-size: 14px; }}
  .qr-sub {{ margin: 0 0 8px; font-size: 11.5px; color: var(--muted); }}
  .qr-url {{
    display: block; font-size: 10px; padding: 5px 8px; border-radius: 6px;
    background: rgba(5, 8, 17, 0.75); color: #cbd5e1; word-break: break-all;
  }}
  .custom-qr-bar {{
    margin-top: 18px; padding: 14px; border-radius: 12px;
    background: rgba(5, 8, 17, 0.65); border: 1px solid rgba(56, 189, 248, 0.2);
    display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
  }}
  .custom-qr-bar input {{
    flex: 1; min-width: 220px; padding: 10px 14px; border-radius: 8px;
    background: #0f172a; border: 1px solid rgba(148, 163, 184, 0.3); color: #fff; font-size: 13px;
  }}
  .custom-qr-bar button {{
    padding: 10px 18px; border-radius: 8px; background: var(--cyan); color: #050811;
    border: 0; font-weight: 700; cursor: pointer;
  }}

  /* Root CA & Bookmarklet (#UX-8 & #UX-10) */
  .two-col {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 400px), 1fr)); gap: 20px; }}
  .dl-btn {{
    display: inline-flex; align-items: center; gap: 8px; padding: 12px 18px;
    border-radius: 12px; font-size: 13px; font-weight: 700; text-decoration: none;
    margin-right: 10px; margin-bottom: 10px; border: 1px solid;
  }}
  .dl-primary {{ background: var(--cyan); color: #050811; border-color: var(--cyan); }}
  .dl-ios {{ background: rgba(236, 72, 153, 0.18); color: #f472b6; border-color: #ec4899; }}
  .dl-ext {{ background: rgba(16, 185, 129, 0.18); color: #34d399; border-color: #10b981; }}
  .bookmarklet-drag {{
    display: inline-flex; align-items: center; gap: 8px; padding: 12px 20px;
    border-radius: 999px; background: linear-gradient(135deg, #f59e0b, #ec4899);
    color: #050811; font-weight: 800; font-size: 13.5px; text-decoration: none;
    box-shadow: 0 8px 25px rgba(245, 158, 11, 0.35); cursor: grab;
  }}
  pre.cmd-box {{
    max-width: 100%;
    background: #050811; border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 10px; padding: 12px; font-size: 11.5px; color: #38bdf8;
    overflow-x: auto; white-space: pre-wrap; word-break: break-all; margin: 8px 0 14px;
  }}
</style>
</head>
<body>

<header>
  <div class="brand">
    <div class="brand-icon">🔐</div>
    <div>
      <h1>Boylenet Zero-Friction SSO, QR Handoff & Root CA Trust Portal</h1>
      <p>Pillar 2 (#UX-6..10) • <code>ca.boylenet.themfboyles.org</code> • <code>sso.boylenet.themfboyles.org</code> • Port <code>:4082</code></p>
    </div>
  </div>
  <nav class="nav-pills">
    <a href="#ux7-launchpad">⚡ #UX-7 Auto-Login Launchpad</a>
    <a href="#ux9-qr-matrix">📱 #UX-9 QR Mobile Handoff</a>
    <a href="#ux8-bookmarklet">🧩 #UX-8 Bookmarklet & Chrome Ext</a>
    <a href="#ux10-root-ca">🛡️ #UX-10 Root CA & iOS Profile</a>
    <a href="http://vault.boylenet.themfboyles.org" target="_blank">🗄️ Credentials Vault (:4087)</a>
  </nav>
</header>

<div class="container">

  <!-- #UX-7: 1-Click Auto-Login Launchpad -->
  <section class="section" id="ux7-launchpad">
    <div class="section-head">
      <h2><span class="pill-tag">#UX-6 / #UX-7</span> 1-Click Auto-Login Launchpad (Zero-Friction Session Handshake)</h2>
      <button class="verify-btn" onclick="verifyAllHandshakes()">⚡ Verify All 8 Live Auth Handshakes</button>
    </div>
    <div class="sso-grid">
      {"".join(sso_cards_html)}
    </div>
  </section>

  <!-- #UX-9: Live QR Code Mobile Handoff Matrix -->
  <section class="section" id="ux9-qr-matrix">
    <div class="section-head">
      <h2><span class="pill-tag">#UX-9</span> Live SVG QR Code Mobile Handoff Matrix (iPhone / iPad 1-Second Takeover)</h2>
      <span class="mono-dim">Pure Python/JS Zero-Dependency ISO/IEC 18004 SVG Generator</span>
    </div>
    <div class="qr-grid" id="qrGrid">
      {"".join(qr_cards_html)}
    </div>
    <div class="custom-qr-bar">
      <strong>⚡ Instant Custom / Claude RC Session QR:</strong>
      <input type="text" id="customQrInput" placeholder="Paste any https://claude.ai/code/session_... or http://*.boylenet.themfboyles.org URL" value="https://claude.ai/code/session_01XfKMnHmQPiwqmCnqwnZSvy">
      <button onclick="renderCustomQr()">Generate Live QR</button>
      <div id="customQrPreview" style="display:flex;align-items:center;gap:12px;"></div>
    </div>
  </section>

  <div class="two-col">
    <!-- #UX-10: 1-Click Root CA & Wildcard TLS Trust -->
    <section class="section" id="ux10-root-ca">
      <div class="section-head">
        <h2><span class="pill-tag">#UX-10</span> Boylenet Internal Root CA & Wildcard TLS</h2>
      </div>
      <p style="font-size:13px;color:var(--muted);margin-top:0;">
        Eliminates browser TLS warnings across <code>*.boylenet.themfboyles.org</code>, <code>*.local</code>, and cluster nodes (<code>.164</code>, <code>.72</code>, <code>.83</code>, <code>.125</code>, <code>.228</code>).
      </p>
      <div style="margin:14px 0;display:flex;flex-wrap:wrap;gap:8px;">
        <a class="dl-btn dl-primary" id="dl-ca-crt" href="/ca.crt">⬇️ Download Root CA (/ca.crt)</a>
        <a class="dl-btn dl-ios" id="dl-mobileconfig" href="/boylenet-ca.mobileconfig">📱 1-Tap iOS/iPadOS Profile (/boylenet-ca.mobileconfig)</a>
        <a class="dl-btn dl-ext" id="dl-wildcard-crt" href="/download/boylenet-wildcard.crt">🌐 Wildcard Cert (.crt)</a>
      </div>
      <div class="cred-pill">
        <span>SHA-256 Fingerprint: <code>{html.escape(ca_meta["root_ca_fingerprint"][:47])}…</code></span>
        <span style="color:var(--emerald);font-weight:700;">Ubuntu .164 Trust: {"INSTALLED ✔" if ca_meta["ubuntu_trust_installed"] else "PENDING"}</span>
      </div>

      <div class="ca-platform-tabs" style="display:flex;gap:6px;flex-wrap:wrap;margin:14px 0 10px;">
        <button type="button" class="mini-btn ca-tab-btn active" id="ca-tab-ios" data-platform="ios" onclick="switchCaTab('ios')" style="background:rgba(56,189,248,0.22);border-color:#38bdf8;color:#fff;">📱 iOS/iPadOS</button>
        <button type="button" class="mini-btn ca-tab-btn" id="ca-tab-macos" data-platform="macos" onclick="switchCaTab('macos')">🍎 macOS</button>
        <button type="button" class="mini-btn ca-tab-btn" id="ca-tab-windows" data-platform="windows" onclick="switchCaTab('windows')">🪟 Windows</button>
        <button type="button" class="mini-btn ca-tab-btn" id="ca-tab-linux" data-platform="linux" onclick="switchCaTab('linux')">🐧 Linux</button>
        <button type="button" class="mini-btn ca-tab-btn" id="ca-tab-android" data-platform="android" onclick="switchCaTab('android')">🤖 Android</button>
      </div>

      <div id="ca-panel-ios" class="ca-platform-panel" style="display:block;">
        <div style="font-size:12px;font-weight:700;display:flex;justify-content:space-between;align-items:center;">
          <span>📱 iOS / iPadOS 1-Tap Configuration Profile (<code>/boylenet-ca.mobileconfig</code>):</span>
          <a class="mini-btn" href="/boylenet-ca.mobileconfig" style="text-decoration:none;">Install Profile</a>
        </div>
        <pre class="cmd-box">1. Tap /boylenet-ca.mobileconfig above in Safari on iPhone or iPad.
2. Open Settings → Profile Downloaded → Install "Boylenet Swarm OS Root CA".
3. Go to Settings → General → About → Certificate Trust Settings → Enable Full Trust for Root Certificates.</pre>
      </div>

      <div id="ca-panel-macos" class="ca-platform-panel" style="display:none;">
        <div style="font-size:12px;font-weight:700;display:flex;justify-content:space-between;">
          <span>🍎 macOS System Keychain 1-Liner:</span>
          <button class="mini-btn" onclick="copyText({html.escape(json.dumps(macos_oneliner))}, this)">Copy macOS</button>
        </div>
        <pre class="cmd-box">{html.escape(macos_oneliner)}</pre>
      </div>

      <div id="ca-panel-windows" class="ca-platform-panel" style="display:none;">
        <div style="font-size:12px;font-weight:700;display:flex;justify-content:space-between;">
          <span>🪟 Windows PowerShell 1-Liner (BattleStation .137 &amp; Bittorrent .181):</span>
          <button class="mini-btn" onclick="copyText({html.escape(json.dumps(ps_oneliner))}, this)">Copy PowerShell</button>
        </div>
        <pre class="cmd-box">{html.escape(ps_oneliner)}</pre>
      </div>

      <div id="ca-panel-linux" class="ca-platform-panel" style="display:none;">
        <div style="font-size:12px;font-weight:700;display:flex;justify-content:space-between;">
          <span>🐧 Ubuntu / Debian / Arch 1-Liner:</span>
          <button class="mini-btn" onclick="copyText({html.escape(json.dumps(linux_oneliner))}, this)">Copy Linux</button>
        </div>
        <pre class="cmd-box">{html.escape(linux_oneliner)}</pre>
      </div>

      <div id="ca-panel-android" class="ca-platform-panel" style="display:none;">
        <div style="font-size:12px;font-weight:700;display:flex;justify-content:space-between;align-items:center;">
          <span>🤖 Android Wi-Fi &amp; Browser Root CA Trust (<code>/ca.crt</code>):</span>
          <a class="mini-btn" href="/ca.crt" style="text-decoration:none;">Download /ca.crt</a>
        </div>
        <pre class="cmd-box">1. Download http://10.0.70.164:4082/ca.crt on your Android device.
2. Open Settings → Security &amp; Privacy → More Security Settings → Encryption &amp; Credentials.
3. Tap "Install a certificate" → "CA certificate" → "Install anyway" and select boylenet-root-ca.crt.</pre>
      </div>

      <!-- Cloudflare DNS-01 Let's Encrypt Wildcard Provisioner (:443) -->
      <div id="letsencrypt-card" style="margin-top:18px;padding:14px;border-radius:12px;background:rgba(5,8,17,0.78);border:1px solid rgba(16,185,129,0.35);">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:8px;">
          <strong style="font-size:13px;color:var(--emerald);">🔒 NGINX :443 Wildcard HTTPS &amp; Cloudflare Let's Encrypt DNS-01</strong>
          <span id="httpsStatusBadge" class="badge" style="color:var(--emerald);border-color:rgba(16,185,129,0.4);background:rgba(16,185,129,0.12);">NGINX :443 ACTIVE</span>
        </div>
        <div id="httpsStatusMeta" style="font-size:11.5px;color:var(--muted);margin-bottom:10px;font-family:monospace;">
          Primary: <code>*.boylenet.themfboyles.org</code> &amp; <code>*.themfboyles.org</code> • Alias: <code>*.boylenet.themfboyles.org</code> • Loading live TLS status...
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
          <input type="password" id="cfApiTokenInput" placeholder="Paste Cloudflare DNS API Token (Zone:DNS:Edit)" style="flex:1;min-width:210px;padding:8px 12px;border-radius:8px;background:#0f172a;border:1px solid rgba(56,189,248,0.35);color:#fff;font-size:12px;">
          <select id="cfDomainSelect" style="padding:8px 10px;border-radius:8px;background:#0f172a;border:1px solid rgba(56,189,248,0.35);color:#fff;font-size:12px;">
            <option value="themfboyles.org" selected>themfboyles.org (Primary)</option>
            <option value="themfboyles.com">themfboyles.com (Legacy)</option>
          </select>
          <button type="button" class="mini-btn" style="padding:8px 14px;font-size:12px;background:var(--emerald);color:#050811;border-color:var(--emerald);" onclick="provisionLetsEncrypt()">⚡ Swap to Let's Encrypt DNS-01</button>
        </div>
        <div id="leResultMsg" style="font-size:11.5px;margin-top:8px;font-family:monospace;color:var(--cyan);"></div>
      </div>
    </section>

    <!-- #UX-8: Boylenet Companion Bookmarklet & Chrome Extension -->
    <section class="section" id="ux8-bookmarklet">
      <div class="section-head">
        <h2><span class="pill-tag">#UX-8</span> Companion Bookmarklet & Chrome Extension</h2>
      </div>
      <p style="font-size:13px;color:var(--muted);margin-top:0;">
        Drag the button below to your browser Bookmarks Bar for 1-click credential injection on any Boylenet service, or download the unpacked Manifest V3 Chrome Extension.
      </p>
      <div style="margin:18px 0;display:flex;flex-wrap:wrap;gap:14px;align-items:center;">
        <a class="bookmarklet-drag" href="{html.escape(BOOKMARKLET_JS)}" title="Drag me to your Bookmarks Bar!">
          ⚡ Boylenet Auto-Fill & Dispatch
        </a>
        <a class="dl-btn dl-ext" style="margin:0;" href="/download/boylenet-chrome-ext.zip">
          📦 Download Chrome Extension (/download/boylenet-chrome-ext.zip)
        </a>
      </div>
      <div style="font-size:12px;font-weight:700;margin-top:14px;display:flex;justify-content:space-between;">
        <span>Bookmarklet Source (Auto-detects LiteLLM, OpenWebUI, Gitea, Grafana, MinIO, Langfuse, OpenClaw):</span>
        <button class="mini-btn" onclick="copyText({html.escape(json.dumps(BOOKMARKLET_JS))}, this)">Copy Bookmarklet</button>
      </div>
      <pre class="cmd-box">{html.escape(BOOKMARKLET_JS)}</pre>
      <div style="font-size:12px;color:var(--muted);background:rgba(5,8,17,0.65);padding:12px;border-radius:10px;border:1px solid rgba(148,163,184,0.15);">
        <strong>Chrome Extension Installation (BattleStation / Bittorrent / Laptop):</strong><br>
        1. Download <code>/download/boylenet-chrome-ext.zip</code> and unzip to a folder.<br>
        2. Open <code>chrome://extensions</code> → Enable <strong>Developer mode</strong> → Click <strong>Load unpacked</strong>.<br>
        3. Includes popup SSO launcher + automatic form fill on all <code>*.boylenet.themfboyles.org</code> & <code>10.0.70.x</code> pages!
      </div>
    </section>
  </div>

</div>

<script>
function switchCaTab(platform) {{
  const platforms = ['ios', 'macos', 'windows', 'linux', 'android'];
  platforms.forEach(p => {{
    const panel = document.getElementById('ca-panel-' + p);
    const btn = document.getElementById('ca-tab-' + p);
    if (panel) panel.style.display = (p === platform) ? 'block' : 'none';
    if (btn) {{
      btn.classList.toggle('active', p === platform);
      btn.style.background = (p === platform) ? 'rgba(56,189,248,0.22)' : '';
      btn.style.borderColor = (p === platform) ? '#38bdf8' : '';
      btn.style.color = (p === platform) ? '#fff' : '';
    }}
  }});
}}

function copyText(txt, btn) {{
  try {{
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(txt).catch(() => {{}});
    }} else {{
      const ta = document.createElement('textarea');
      ta.value = txt;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }}
  }} catch (e) {{}}
  if (btn) {{
    const old = btn.textContent;
    btn.textContent = 'Copied ✔';
    setTimeout(() => btn.textContent = old, 1400);
  }}
}}

async function verifyHandshake(tid, btn) {{
  const statusEl = document.getElementById('hs-' + tid);
  statusEl.textContent = '⏳ Negotiating live auth handshake...';
  try {{
    const r = await fetch('/sso/login/' + tid + '?mode=json');
    const d = await r.json();
    if (d.handshake_verified) {{
      statusEl.innerHTML = '✔ Handshake OK (HTTP ' + d.status_code + ') • ' + (d.session_cookie || 'Ready');
    }} else {{
      statusEl.innerHTML = '⚡ Trampoline Ready • ' + (d.redirect_url || '');
    }}
  }} catch (e) {{
    statusEl.textContent = '⚠️ ' + e;
  }}
}}

async function verifyAllHandshakes() {{
  const ids = {json.dumps(list(SSO_TARGETS.keys()))};
  await Promise.all(ids.map(id => verifyHandshake(id)));
}}

async function renderCustomQr() {{
  const val = document.getElementById('customQrInput').value.trim();
  if (!val) return;
  const box = document.getElementById('customQrPreview');
  box.innerHTML = '<img src="/api/qr?url=' + encodeURIComponent(val) + '" width="96" height="96" style="background:#fff;padding:4px;border-radius:8px;"> <code style="font-size:11px;color:#00e5ff;">' + val + '</code>';
}}

async function loadHttpsStatus() {{
  try {{
    const r = await fetch('/api/https-status');
    const d = await r.json();
    const badge = document.getElementById('httpsStatusBadge');
    const meta = document.getElementById('httpsStatusMeta');
    if (badge) {{
      badge.textContent = (d.nginx_active && d.port_443_listening ? 'NGINX :443 ACTIVE • ' : 'NGINX :443 • ') + (d.cert_provider || 'Active');
    }}
    if (meta) {{
      meta.innerHTML = 'Subject: <code>' + (d.subject || '') + '</code> • Expires: <code>' + (d.expires || '') + '</code> • Certbot Timer: <code>' + (d.certbot_timer_active ? 'ENABLED' : 'OFF') + '</code> • CF INI: <code>' + (d.cloudflare_credentials_configured ? 'CONFIGURED' : 'READY') + '</code>';
    }}
  }} catch (e) {{}}
}}

async function provisionLetsEncrypt() {{
  const token = document.getElementById('cfApiTokenInput').value.trim();
  const domain = document.getElementById('cfDomainSelect').value;
  const msg = document.getElementById('leResultMsg');
  if (!token) {{
    msg.textContent = '⚠️ Please paste your Cloudflare DNS API token first.';
    return;
  }}
  msg.textContent = '⏳ Running certbot DNS-01 challenge for *.' + domain + ' and *.boylenet.' + domain + ' (approx 20-30s)...';
  try {{
    const r = await fetch('/api/letsencrypt-cloudflare', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{token: token, domain: domain}})
    }});
    const d = await r.json();
    if (d.ok) {{
      msg.textContent = '✔ Let\\'s Encrypt wildcard certificate issued and NGINX :443 reloaded!';
    }} else {{
      msg.textContent = '⚠️ Certbot response: ' + (d.error || 'Zero-downtime Root CA wildcard remains active on :443');
    }}
    loadHttpsStatus();
  }} catch (e) {{
    msg.textContent = '⚠️ ' + e;
  }}
}}

window.addEventListener('DOMContentLoaded', () => {{
  loadHttpsStatus();
}});
</script>
</body>
</html>"""


# ============================================================================
# Threaded HTTP Server & Request Handler
# ============================================================================


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class TrustAndSSOPortalHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _send_bytes(
        self,
        data: bytes,
        content_type: str,
        status: int = 200,
        extra_headers: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self._send_bytes(raw, "application/json; charset=utf-8", status=status)

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            body = json.loads(raw_body or "{}")
        except Exception:
            body = {}

        if path == "/api/letsencrypt-cloudflare":
            token = str(body.get("token") or body.get("cf_api_token") or "").strip()
            domain = str(body.get("domain") or "themfboyles.org").strip()
            email = str(body.get("email") or "").strip()
            global_key = str(body.get("global_key") or "").strip()
            if not token and not global_key:
                self._send_json(
                    {"ok": False, "error": "Missing token or global_key"},
                    status=400,
                )
                return
            cmd = [
                "/home/mboyle/bin/bd-letsencrypt-cloudflare",
                "--domain",
                domain,
                "--json",
            ]
            if token:
                cmd.extend(["--set-token", token])
            if email:
                cmd.extend(["--email", email])
            if global_key:
                cmd.extend(["--global-key", global_key])
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
                res = json.loads(proc.stdout)
            except Exception as e:
                res = {"ok": False, "error": str(e), "status": get_https_status()}
            self._send_json(res)
            return

        self._send_json({"ok": False, "error": f"Unknown POST endpoint: {path}"}, status=404)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/api/https-status":
            self._send_json(get_https_status())
            return

        if path == "/health":
            ca_meta = get_ca_metadata()
            self._send_json(
                {
                    "status": "ok",
                    "service": "bd-trust-and-sso-portal",
                    "port": PORT,
                    "ux_items": ["#UX-6", "#UX-7", "#UX-8", "#UX-9", "#UX-10"],
                    "hosts": [
                        "ca.boylenet.themfboyles.org",
                        "sso.boylenet.themfboyles.org",
                        "ca.boylenet.themfboyles.org",
                        "sso.boylenet.themfboyles.org",
                    ],
                    "ca": ca_meta,
                    "https": get_https_status(),
                    "sso_targets": list(SSO_TARGETS.keys()),
                    "qr_endpoints": [c["url"] for c in get_qr_handoff_cards()],
                    "downloads": [
                        "/ca.crt",
                        "/boylenet-ca.mobileconfig",
                        "/download/boylenet-root-ca.crt",
                        "/download/boylenet-root-ca.mobileconfig",
                        "/download/boylenet-wildcard.crt",
                        "/download/boylenet-chrome-ext.zip",
                        "/download/install-ca-windows.ps1",
                    ],
                }
            )
            return

        if path == "/api/status":
            self._send_json(
                {
                    "status": "ok",
                    "targets": SSO_TARGETS,
                    "qr_cards": get_qr_handoff_cards(),
                    "ca": get_ca_metadata(),
                    "https": get_https_status(),
                }
            )
            return

        if path == "/api/qr":
            url_param = qs.get("url", ["http://mobile.boylenet.themfboyles.org"])[0]
            svg = render_qr_svg(url_param, pixel_size=220)
            self._send_bytes(svg.encode("utf-8"), "image/svg+xml; charset=utf-8")
            return

        if path.startswith("/sso/login/"):
            target_id = path.split("/sso/login/", 1)[1].strip("/")
            if target_id not in SSO_TARGETS:
                self._send_json(
                    {"ok": False, "error": f"Unknown SSO target: {target_id}"},
                    status=404,
                )
                return
            handshake = perform_server_sso_handshake(target_id)
            if qs.get("mode", [""])[0] == "json":
                self._send_json(handshake)
                return
            page, headers = render_sso_trampoline_html(target_id, handshake)
            self._send_bytes(
                page.encode("utf-8"), "text/html; charset=utf-8", extra_headers=headers
            )
            return

        if path in ("/download/boylenet-root-ca.crt", "/ca.crt"):
            if os.path.exists(ROOT_CA_CRT):
                with open(ROOT_CA_CRT, "rb") as f:
                    data = f.read()
                self._send_bytes(
                    data,
                    "application/x-x509-ca-cert",
                    extra_headers=[
                        (
                            "Content-Disposition",
                            'attachment; filename="boylenet-root-ca.crt"',
                        )
                    ],
                )
            else:
                self._send_json({"error": "Root CA not found"}, status=404)
            return

        if path == "/download/boylenet-wildcard.crt":
            if os.path.exists(WILDCARD_CRT):
                with open(WILDCARD_CRT, "rb") as f:
                    data = f.read()
                self._send_bytes(
                    data,
                    "application/x-x509-ca-cert",
                    extra_headers=[
                        (
                            "Content-Disposition",
                            'attachment; filename="boylenet-wildcard.crt"',
                        )
                    ],
                )
            else:
                self._send_json({"error": "Wildcard certificate not found"}, status=404)
            return

        if path in ("/download/boylenet-root-ca.mobileconfig", "/boylenet-ca.mobileconfig"):
            if os.path.exists(MOBILECONFIG_PATH):
                with open(MOBILECONFIG_PATH, "rb") as f:
                    data = f.read()
                self._send_bytes(
                    data,
                    "application/x-apple-aspen-config",
                    extra_headers=[
                        (
                            "Content-Disposition",
                            'attachment; filename="boylenet-root-ca.mobileconfig"',
                        )
                    ],
                )
            else:
                self._send_json({"error": "iOS mobileconfig not found"}, status=404)
            return

        if path == "/download/boylenet-chrome-ext.zip":
            zbytes = build_chrome_extension_zip()
            self._send_bytes(
                zbytes,
                "application/zip",
                extra_headers=[
                    (
                        "Content-Disposition",
                        'attachment; filename="boylenet-chrome-ext.zip"',
                    )
                ],
            )
            return

        if path == "/download/install-ca-windows.ps1":
            ps1 = (
                "# Boylenet Internal Root CA 1-Click Installer for Windows (BattleStation & Bittorrent)\r\n"
                '$CaUrl = "http://ca.boylenet.themfboyles.org/download/boylenet-root-ca.crt"\r\n'
                '$OutPath = "$env:TEMP\\boylenet-root-ca.crt"\r\n'
                "Invoke-WebRequest -Uri $CaUrl -OutFile $OutPath\r\n"
                "Import-Certificate -FilePath $OutPath -CertStoreLocation Cert:\\LocalMachine\\Root\r\n"
                'Write-Host "Boylenet Swarm OS Internal Root CA installed successfully!" -ForegroundColor Green\r\n'
            ).encode("utf-8")
            self._send_bytes(
                ps1,
                "text/plain; charset=utf-8",
                extra_headers=[
                    (
                        "Content-Disposition",
                        'attachment; filename="install-ca-windows.ps1"',
                    )
                ],
            )
            return

        # Default: serve main portal UI
        html_doc = render_portal_html().encode("utf-8")
        self._send_bytes(html_doc, "text/html; charset=utf-8")


def main() -> None:
    server = ThreadedHTTPServer(("0.0.0.0", PORT), TrustAndSSOPortalHandler)
    print(
        f"Boylenet Zero-Friction SSO, QR Handoff & Root CA Portal listening on 0.0.0.0:{PORT}",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
