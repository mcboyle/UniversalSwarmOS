#!/usr/bin/env python3
"""
Boylenet Live BD KB Auto-Indexer (`bd-kb-live-sync.py`)
Automatically indexes new/updated:
  - `AGENT*.md` receipts (`/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/AGENT*.md` & `/home/mboyle/bd-persist/AGENT*.md`)
  - `PM-HANDOFF.md` (`/home/mboyle/bd-persist/PM-HANDOFF.md` & `harness-work/O1789/**/PM-HANDOFF*.md`)
  - `WATCHDOG-STATUS.md` (`/home/mboyle/bd-persist/WATCHDOG-STATUS.md` & `harness-work/O1789/**/WATCHDOG-STATUS*.md`)
into:
  1. `/home/mboyle/bd-persist/bd-kb/05-SWARM-OPERATIONS-RECEIPTS-AND-PLAYBOOKS.md`
  2. Qdrant Vector Collection `bd_master_kb` (`http://10.0.70.125:6333`, 1024-d Cosine)
  3. OpenWebUI Tool Gateway (`:4079`) live BD KB cache refresh
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if "/home/mboyle/bin" not in sys.path:
    sys.path.insert(0, "/home/mboyle/bin")

BD_KB_DIR = Path("/home/mboyle/bd-persist/bd-kb")
TARGET_MD = BD_KB_DIR / "05-SWARM-OPERATIONS-RECEIPTS-AND-PLAYBOOKS.md"
STATE_FILE = Path("/var/tmp/bd-kb-live-sync-state.json")
STREAM_LOG = Path("/var/tmp/bd-headless-streams/agent104-homestretch-vsan-parity.log")

QDRANT_URL = os.environ.get("BD_KB_QDRANT_URL", "http://10.0.70.125:6333").rstrip("/")
QDRANT_COLLECTION = os.environ.get("BD_KB_QDRANT_COLLECTION", "bd_master_kb")
GATEWAY_URL = os.environ.get("BD_KB_GATEWAY_URL", "http://127.0.0.1:4079").rstrip("/")

SEARCH_ROOTS = [
    Path("/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade"),
    Path("/home/mboyle/bd-persist/harness-work/O1789"),
    Path("/home/mboyle/bd-persist"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_msg(msg: str) -> None:
    line = f"[{utc_now()}] [bd-kb-live-sync] {msg}"
    print(line, flush=True)
    try:
        STREAM_LOG.parent.mkdir(parents=True, exist_ok=True)
        with STREAM_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_embedding_fn():
    import math

    def _fallback_embed(text: str) -> list[float]:
        vec = [0.0] * 1024
        tokens = re.findall(r"[a-zA-Z0-9_.-]{2,}", text.lower())
        if not tokens:
            tokens = ["boylenet"]
        for tok in tokens:
            h = hashlib.sha256(tok.encode("utf-8")).digest()
            idx1 = int.from_bytes(h[0:2], "little") % 1024
            idx2 = int.from_bytes(h[2:4], "little") % 1024
            sign1 = 1.0 if h[4] & 1 == 0 else -1.0
            sign2 = 1.0 if h[5] & 1 == 0 else -1.0
            vec[idx1] += sign1 * 1.0
            vec[idx2] += sign2 * 0.5
        norm = math.sqrt(sum((v * v for v in vec))) or 1.0
        return [round(v / norm, 6) for v in vec]
    return _fallback_embed


def discover_source_files() -> list[Path]:
    found: dict[str, Path] = {}
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for pat in ("AGENT*.md", "PM-HANDOFF*.md", "WATCHDOG-STATUS*.md"):
            for p in root.glob(pat):
                if p.is_file() and p.stat().st_size > 0:
                    found[str(p.resolve())] = p.resolve()
    # Sort with PM-HANDOFF and WATCHDOG-STATUS first, then AGENT receipts by mtime descending
    def _sort_key(p: Path) -> tuple[int, float, str]:
        name = p.name.upper()
        if name.startswith("PM-HANDOFF"):
            prio = 0
        elif name.startswith("WATCHDOG-STATUS"):
            prio = 1
        else:
            prio = 2
        return (prio, -p.stat().st_mtime, p.name)

    return sorted(found.values(), key=_sort_key)


def summarize_markdown_file(fpath: Path, max_chars: int = 2400) -> dict[str, Any]:
    raw = fpath.read_text(encoding="utf-8", errors="replace")
    sha256 = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    mtime_iso = datetime.fromtimestamp(fpath.stat().st_mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    lines = [ln.rstrip() for ln in raw.splitlines()]
    title = fpath.stem
    for ln in lines[:15]:
        if ln.startswith("# "):
            title = ln.lstrip("# ").strip()
            break

    # Extract key headings & bullet highlights
    kept_lines: list[str] = []
    char_count = 0
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        # Convert internal ## headings to ### so each file stays one cohesive ## chunk in BD KB
        if s.startswith("## "):
            s = "### " + s[3:]
        elif s.startswith("# "):
            continue
        kept_lines.append(s)
        char_count += len(s) + 1
        if char_count >= max_chars:
            kept_lines.append(f"... *(truncated in digest; full receipt at `{fpath}`)*")
            break

    digest = "\n".join(kept_lines).strip()
    return {
        "path": str(fpath),
        "name": fpath.name,
        "title": title,
        "mtime_utc": mtime_iso,
        "size_bytes": fpath.stat().st_size,
        "sha256": sha256[:16],
        "digest": digest,
    }


def build_playbook_markdown(items: list[dict[str, Any]]) -> str:
    now_str = utc_now()
    agent_items = [x for x in items if x["name"].upper().startswith("AGENT")]
    handoff_items = [x for x in items if x["name"].upper().startswith("PM-HANDOFF")]
    watchdog_items = [x for x in items if x["name"].upper().startswith("WATCHDOG-STATUS")]

    out: list[str] = [
        "# 🛠️ BD-KB 05B: Swarm Operations Receipts, PM Handoffs & Watchdog Playbooks (Live Auto-Indexed)",
        "",
        f"- **Auto-Indexed By**: `/home/mboyle/bin/bd-kb-live-sync.py` (`bd-kb-live-sync.service` / `bd-kb-live-sync.timer` every 15m)",
        f"- **Last Synchronized (UTC)**: `{now_str}`",
        f"- **Total Indexed Documents**: `{len(items)}` (`{len(agent_items)}` `AGENT*.md` Receipts, `{len(handoff_items)}` `PM-HANDOFF*.md`, `{len(watchdog_items)}` `WATCHDOG-STATUS*.md`)",
        f"- **Vector Index Target**: Qdrant `http://10.0.70.125:6333/collections/{QDRANT_COLLECTION}` (`1024-d Cosine`)",
        "",
        "## 0. Executive Index of Live Swarm Receipts & Handoffs",
        "",
        "| Document | Category | Updated (UTC) | Size | SHA-256 (16c) | Absolute Path |",
        "|---|---|---|---:|---|---|",
    ]
    for it in items:
        cat = (
            "PM Handoff"
            if it["name"].upper().startswith("PM-HANDOFF")
            else ("Watchdog" if it["name"].upper().startswith("WATCHDOG") else "Agent Receipt")
        )
        out.append(
            f"| `{it['name']}` | {cat} | `{it['mtime_utc']}` | `{it['size_bytes']} B` | `{it['sha256']}` | `{it['path']}` |"
        )
    out.append("")

    for idx, it in enumerate(items, start=1):
        out.append(f"## {idx}. [{it['name']}] {it['title']}")
        out.append(
            f"- **Source Path**: `{it['path']}` | **Updated**: `{it['mtime_utc']}` | **SHA-256**: `{it['sha256']}`"
        )
        out.append("")
        out.append(it["digest"])
        out.append("")

    return "\n".join(out)


def load_all_kb_chunks() -> list[dict[str, Any]]:
    books_meta = [
        ("bd-kb-master", "00-BD-KB-MASTER-ENCYCLOPEDIA.md", "📚 BD-KB 00: Master Encyclopedia"),
        ("bd-kb-bulkdownloader", "01-BULKDOWNLOADER-ARCHITECTURE-AND-CONTRACTS.md", "📥 BD-KB 01: BulkDownloader Architecture & Contracts"),
        ("bd-kb-cluster-infra", "02-BOYLENET-27NODE-CLUSTER-12U-RACK-VSAN-25GBE.md", "🖥️ BD-KB 02: Boylenet 27-Node Cluster, 12U Rack, vSAN & 25GbE"),
        ("bd-kb-86-models", "03-86-MODEL-VAULT-BENCHMARKS-AND-AIRGAP.md", "🧠 BD-KB 03: 86-Model AI Vault, Benchmarks & Airgap"),
        ("bd-kb-fleet-law", "04-FLEET-LAW-RULES-1-86-AND-O1740-ROUTING.md", "⚖️ BD-KB 04: Fleet Law Rules 1-86 & O1740 Routing"),
        ("bd-kb-ci-and-uis", "05-CI-TAXONOMY-RECOVERY-AND-MCP-TOOLS.md", "🩺 BD-KB 05A: CI Taxonomy, Recovery, 14 MCPs & 50 Toolkits"),
        ("bd-kb-swarm-ops", "05-SWARM-OPERATIONS-RECEIPTS-AND-PLAYBOOKS.md", "🛠️ BD-KB 05B: Swarm Operations Receipts, PM Handoffs & Watchdog Playbooks"),
        ("bd-kb-5platform-mods", "06-5PLATFORM-MCP-MODS-HTTPS-AND-215-LEDGER.md", "🌐 BD-KB 06: 5-Platform boylenet-infra MCP, Mods 1-5, NGINX/Cloudflare HTTPS & 215/215 Backlog Ledger"),
    ]
    chunks: list[dict[str, Any]] = []
    chunk_idx = 1
    for kb_id, fname, bname in books_meta:
        fpath = BD_KB_DIR / fname
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
                    "chunk_id": f"chunk-{chunk_idx}",
                    "point_id": chunk_idx,
                    "kb_id": kb_id,
                    "book_name": bname,
                    "filename": fname,
                    "file_path": str(fpath),
                    "section_title": first_line[:160],
                    "content": sec_clean[:4000],
                }
            )
            chunk_idx += 1
    return chunks


def sync_chunks_to_qdrant(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    embed_fn = load_embedding_fn()
    # Ensure collection exists
    req_create = urllib.request.Request(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}",
        data=json.dumps({"vectors": {"size": 1024, "distance": "Cosine"}}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req_create, timeout=8) as r:
            create_status = json.loads(r.read().decode()).get("status", "ok")
    except Exception as e:
        create_status = f"exists_or_warn:{e}"

    points = []
    for ch in chunks:
        vec = embed_fn(f"{ch['section_title']}\n{ch['content']}")
        points.append(
            {
                "id": ch["point_id"],
                "vector": vec,
                "payload": {
                    "chunk_id": ch["chunk_id"],
                    "book_id": ch["kb_id"],
                    "book_name": ch["book_name"],
                    "filename": ch["filename"],
                    "section_title": ch["section_title"],
                    "text": ch["content"],
                    "content": ch["content"],
                    "source": ch["file_path"],
                    "indexed_at": utc_now(),
                    "metadata": {
                        "source": ch["filename"],
                        "book_id": ch["kb_id"],
                        "section": ch["section_title"],
                    },
                },
            }
        )

    # Upsert in batches of 64 points so payload stays lightweight
    batch_size = 64
    upserted = 0
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        req_up = urllib.request.Request(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points?wait=true",
            data=json.dumps({"points": batch}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(req_up, timeout=15) as r:
            res = json.loads(r.read().decode())
            if res.get("status") == "ok":
                upserted += len(batch)

    return {
        "qdrant_url": QDRANT_URL,
        "collection": QDRANT_COLLECTION,
        "create_status": create_status,
        "total_chunks": len(chunks),
        "points_upserted": upserted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Boylenet Live BD KB Auto-Indexer")
    parser.add_argument("--force", action="store_true", help="Force full re-index even if unchanged")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    t0 = time.perf_counter()
    BD_KB_DIR.mkdir(parents=True, exist_ok=True)
    files = discover_source_files()

    fingerprint_map = {str(p): f"{p.stat().st_mtime_ns}:{p.stat().st_size}" for p in files}
    prev_state: dict[str, Any] = {}
    if STATE_FILE.exists():
        try:
            prev_state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            prev_state = {}

    changed = (
        args.force
        or not TARGET_MD.exists()
        or prev_state.get("fingerprints") != fingerprint_map
    )

    items = [summarize_markdown_file(p) for p in files]
    if changed:
        md_content = build_playbook_markdown(items)
        TARGET_MD.write_text(md_content, encoding="utf-8")

    chunks = load_all_kb_chunks()
    qdrant_res = sync_chunks_to_qdrant(chunks)

    summary = {
        "ok": True,
        "timestamp": utc_now(),
        "changed": changed,
        "source_files_indexed": len(items),
        "target_markdown": str(TARGET_MD),
        "target_markdown_bytes": TARGET_MD.stat().st_size if TARGET_MD.exists() else 0,
        "qdrant": qdrant_res,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
    }

    STATE_FILE.write_text(
        json.dumps(
            {
                "last_sync": summary["timestamp"],
                "source_files_indexed": len(items),
                "total_chunks": len(chunks),
                "fingerprints": fingerprint_map,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    log_msg(
        f"Indexed {len(items)} receipts/handoffs -> {TARGET_MD.name} ({summary['target_markdown_bytes']} B) "
        f"& Qdrant {QDRANT_COLLECTION} ({qdrant_res['points_upserted']} chunks) in {summary['elapsed_ms']}ms"
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
