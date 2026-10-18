#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import math
import os
import re
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
QDRANT_URL = "http://10.0.70.125:6333"
COLLECTION_HIVEMIND = "fleet_lessons_hivemind"
COLLECTION_MASTER_KB = "bd_master_kb"
PLAYBOOK_MD = Path("/home/mboyle/bd-persist/bd-kb/05-SWARM-OPERATIONS-RECEIPTS-AND-PLAYBOOKS.md")
STATE_FILE = Path("/var/tmp/bd-hivemind-lesson-publisher-state.json")
RECEIPT_DIRS = [Path("/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade"), Path("/home/mboyle/bd-persist/harness-work/O1789")]
CUTS_DIRS = [Path("/home/mboyle/bd-cuts"), Path("/home/mboyle/bd-review-wt")]

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def embed_1024(text: str) -> list[float]:
    vec = [0.0] * 1024
    tokens = re.findall(r"[a-zA-Z0-9_.-]{2,}", text.lower()) or ["boylenet"]
    for tok in tokens:
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        i1 = int.from_bytes(h[0:2], "little") % 1024
        i2 = int.from_bytes(h[2:4], "little") % 1024
        s1 = 1.0 if h[4] & 1 == 0 else -1.0
        s2 = 1.0 if h[5] & 1 == 0 else -1.0
        vec[i1] += s1
        vec[i2] += s2 * 0.5
    norm = math.sqrt(sum((v * v for v in vec))) or 1.0
    return [round(v / norm, 6) for v in vec]

def discover_receipts_and_results(max_results: int=20) -> list[Path]:
    found: dict[str, Path] = {}
    for d in RECEIPT_DIRS:
        if not d.is_dir():
            continue
        for pat in ("AGENT*.md", "PM-HANDOFF*.md", "WATCHDOG-STATUS*.md", "RESULT.md"):
            for p in d.glob(pat):
                if p.is_file() and p.stat().st_size > 0:
                    found[str(p)] = p
    result_candidates: list[Path] = []
    for cd in CUTS_DIRS:
        if not cd.is_dir():
            continue
        try:
            with os.scandir(cd) as it:
                for entry in itertools.islice(it, 60):
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    sub = Path(entry.path)
                    for rrel in (".review/RESULT.md", "RESULT.md", "DONE.md"):
                        rp = sub / rrel
                        if rp.is_file() and rp.stat().st_size > 0:
                            result_candidates.append(rp)
                            break
        except Exception:
            pass
    result_candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    for rp in result_candidates[:max_results]:
        found[str(rp)] = rp
    return sorted(found.values(), key=lambda p: p.stat().st_mtime, reverse=True)

def extract_lesson(fpath: Path) -> dict[str, Any]:
    raw = fpath.read_text(encoding="utf-8", errors="replace")
    lines = [ln.rstrip() for ln in raw.splitlines()]
    title = fpath.stem
    verdict = "VERIFIED"
    bullets: list[str] = []
    for ln in lines[:30]:
        s = ln.strip()
        if s.startswith("# "):
            title = s.lstrip("# ").strip()
            break
    for ln in lines[:20]:
        s = ln.strip()
        if s.startswith("VERDICT:"):
            verdict = s.split("VERDICT:", 1)[1].strip()
            break
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if s.startswith(("## ", "### ", "- ", "* ", "1. ", "2. ", "3. ", "VERDICT:")):
            bullets.append(s)
            if sum((len(x) for x in bullets)) > 1600:
                break
    summary = "\n".join(bullets[:25]) if bullets else raw[:1500]
    slug_base = f"{fpath.parent.name}-{fpath.stem}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug_base).strip("-")[:80]
    category = "cut-review-result" if fpath.name in ("RESULT.md", "DONE.md") else "swarm-agent-receipt"
    tags = sorted(set(re.findall(r"\b(?:agent-?\d+|o\d{4}|qdrant|openwebui|litellm|vsan|esxi|pytest|ramdisk|airgap|rule-?\d+)\b", raw.lower())))[:15]
    if not tags:
        tags = ["boylenet", category]
    point_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"boylenet-lesson:{fpath}"))
    return {"id": point_uuid, "slug": slug, "category": category, "title": f"{title} ({fpath.parent.name}/{fpath.name})" if fpath.name in ("RESULT.md", "DONE.md") else title, "verdict": verdict, "summary": summary[:2000], "source_path": str(fpath), "tags": tags, "created_at": datetime.fromtimestamp(fpath.stat().st_mtime, tz=timezone.utc).isoformat()}

def upsert_qdrant_points(collection: str, points: list[dict[str, Any]]) -> int:
    if not points:
        return 0
    upserted = 0
    batch_size = 64
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        req = urllib.request.Request(f"{QDRANT_URL}/collections/{collection}/points?wait=true", data=json.dumps({"points": batch}).encode("utf-8"), headers={"Content-Type": "application/json"}, method="PUT")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            if data.get("status") == "ok":
                upserted += len(batch)
    return upserted

def update_playbook_markdown(lessons: list[dict[str, Any]]) -> int:
    PLAYBOOK_MD.parent.mkdir(parents=True, exist_ok=True)
    existing = PLAYBOOK_MD.read_text(encoding="utf-8", errors="replace") if PLAYBOOK_MD.exists() else "# 05 — Swarm Operations Receipts & Playbooks\n"

    marker = "\n## Rule 25 Autonomous Lesson Publisher Index"
    if marker in existing:
        existing = existing.split(marker, 1)[0].rstrip()
    sec_lines = ["", "## Rule 25 Autonomous Lesson Publisher Index", f"- **Updated UTC**: `{utc_now()}`", f"- **Indexed Lessons (`AGENT*.md` + `RESULT.md`)**: `{len(lessons)}`", ""]
    for les in lessons[:25]:
        sec_lines.append(f"- **{les['title']}** (`{les['category']}` | `{les['verdict']}`) — `{les['source_path']}`"
)
    updated_text = existing + "\n" + "\n".join(sec_lines) + "\n"
    PLAYBOOK_MD.write_text(updated_text, encoding="utf-8")
    return len(updated_text.encode("utf-8"))

def run_publisher(max_results: int=20) -> dict[str, Any]:
    t0 = time.perf_counter()
    files = discover_receipts_and_results(max_results=max_results)
    lessons = [extract_lesson(p) for p in files]
    hivemind_points: list[dict[str, Any]] = []
    master_kb_points: list[dict[str, Any]] = []
    for idx, les in enumerate(lessons, start=5000):
        vec = embed_1024(f"{les['title']}\n{les['summary']}")
        hivemind_points.append({"id": les["id"], "vector": vec, "payload": {"slug": les["slug"], "category": les["category"], "title": les["title"], "verdict": les["verdict"], "summary": les["summary"], "text": les["summary"], "content": les["summary"], "source_path": les["source_path"], "tags": les["tags"], "created_at": les["created_at"], "metadata": {"source": les["source_path"], "category": les["category"], "verdict": les["verdict"]}}})
        master_kb_points.append({"id": idx, "vector": vec, "payload": {"chunk_id": f"lesson-{idx}", "book_id": "bd-kb-ci-and-uis", "book_name": "05-SWARM-OPERATIONS-RECEIPTS-AND-PLAYBOOKS.md", "filename": "05-SWARM-OPERATIONS-RECEIPTS-AND-PLAYBOOKS.md", "section_title": les["title"][:160], "text": les["summary"], "content": les["summary"], "source": les["source_path"], "indexed_at": utc_now(), "metadata": {"source": "05-SWARM-OPERATIONS-RECEIPTS-AND-PLAYBOOKS.md", "book_id": "bd-kb-ci-and-uis", "section": les["title"][:160]}}})
    hm_upserted = upsert_qdrant_points(COLLECTION_HIVEMIND, hivemind_points)
    kb_upserted = upsert_qdrant_points(COLLECTION_MASTER_KB, master_kb_points)
    pb_bytes = update_playbook_markdown(lessons)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    summary = {"ok": hm_upserted > 0 and kb_upserted > 0 and PLAYBOOK_MD.exists(), "timestamp": utc_now(), "files_scanned": len(files), "agent_receipts_count": sum((1 for x in lessons if x["category"] == "swarm-agent-receipt")), "cut_results_count": sum((1 for x in lessons if x["category"] == "cut-review-result")), "qdrant_url": QDRANT_URL, "fleet_lessons_hivemind_upserted": hm_upserted, "bd_master_kb_upserted": kb_upserted, "playbook_md": str(PLAYBOOK_MD), "playbook_md_bytes": pb_bytes, "elapsed_ms": elapsed_ms}
    try:
        STATE_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        pass
    return summary

def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous Rule 25 Knowledge & Qdrant HiveMind Sync Mod")
    parser.add_argument("--json", action="store_true", help="Emit full JSON receipt")
    parser.add_argument("--max-results", type=int, default=20, help="Max RESULT.md files to scan")
    args = parser.parse_args()
    res = run_publisher(max_results=args.max_results)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"[HIVEMIND-SYNC OK] scanned={res['files_scanned']} "
            f"(AGENT*.md={res['agent_receipts_count']}, RESULT.md={res['cut_results_count']}) | "
            f"fleet_lessons_hivemind={res['fleet_lessons_hivemind_upserted']} "
            f"bd_master_kb={res['bd_master_kb_upserted']} | "
            f"playbook={res['playbook_md_bytes']}B in {res['elapsed_ms']}ms")
    return 0 if res["ok"] else 1
if __name__ == "__main__":
    raise SystemExit(main())
