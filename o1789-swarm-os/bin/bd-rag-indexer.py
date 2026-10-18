#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import glob
import hashlib
import http.client
import json
import math
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

QDRANT_URL = os.environ.get("BD_QDRANT_URL", "http://10.0.70.125:6333").rstrip("/")
TEI_EMBED_URL = os.environ.get("BD_TEI_EMBED_URL", "http://10.0.70.164:8081").rstrip(
    "/"
)
TEI_RERANK_URL = os.environ.get("BD_TEI_RERANK_URL", "http://10.0.70.164:8082").rstrip(
    "/"
)
COLLECTION_NAME = "boylenet_fleet_rag"
VECTOR_DIM = 1024
DENSE_WEIGHT = math.sqrt(0.6)
LEXICAL_WEIGHT = math.sqrt(0.4)
STOPWORDS = {
    "a",
    "an",
    "the",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "and",
    "or",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "how",
    "what",
    "do",
    "we",
    "where",
    "when",
    "who",
    "which",
    "why",
    "it",
    "this",
    "that",
    "as",
    "into",
    "can",
}
_tls = threading.local()


def _l2_normalize(vec: list[float]) -> list[float]:
    norm_sq = sum(x * x for x in vec)
    if norm_sq > 1e-12:
        inv = 1.0 / math.sqrt(norm_sq)
        return [x * inv for x in vec]
    return vec


def extract_lexical_tokens(text: str) -> list[tuple[str, float]]:
    low = text.lower()
    raw_tokens = re.findall(r"[a-z0-9_.\-]+", low)
    weighted: list[tuple[str, float]] = []
    clean_seq: list[str] = []
    for tok in raw_tokens:
        t = tok.strip("._-")
        if not t or t in STOPWORDS or len(t) < 2:
            continue
        has_digit = any(c.isdigit() for c in t)
        has_sep = any(c in t for c in "._-")
        w = 2.4 if has_digit or has_sep else 1.0
        weighted.append((t, w))
        clean_seq.append(t)
        if has_sep:
            for sub in re.split(r"[._\-]+", t):
                if len(sub) >= 2 and sub not in STOPWORDS:
                    sub_w = 2.2 if any(c.isdigit() for c in sub) else 1.1
                    weighted.append((sub, sub_w))
    for i in range(len(clean_seq) - 1):
        bg = f"{clean_seq[i]}_{clean_seq[i + 1]}"
        weighted.append((bg, 1.3))
    return weighted


def build_hybrid_1024_vector(tei_vec: list[float], text: str) -> list[float]:
    d_norm = _l2_normalize([float(x) for x in tei_vec])
    if len(d_norm) >= VECTOR_DIM:
        return _l2_normalize(d_norm[:VECTOR_DIM])
    dense_dim = len(d_norm)
    lex_dim = VECTOR_DIM - dense_dim
    lex_vec = [0.0] * lex_dim
    for tok, weight in extract_lexical_tokens(text):
        digest = hashlib.md5(tok.encode("utf-8")).digest()
        h1 = int.from_bytes(digest[:4], "little")
        h2 = int.from_bytes(digest[4:8], "little")
        idx = h1 % lex_dim
        sign = 1.0 if h2 & 1 == 0 else -1.0
        lex_vec[idx] += sign * weight
    l_norm = _l2_normalize(lex_vec)
    combined = [DENSE_WEIGHT * x for x in d_norm] + [LEXICAL_WEIGHT * y for y in l_norm]
    return _l2_normalize(combined)


def call_tei_embed_batch(texts: list[str]) -> list[list[float]]:
    parsed = urllib.parse.urlparse(TEI_EMBED_URL)
    host = parsed.hostname or "10.0.70.164"
    port = parsed.port or 8081
    truncated = [t[:480] if t.strip() else "empty" for t in texts]
    body = json.dumps({"inputs": truncated}).encode("utf-8")
    for attempt in range(3):
        try:
            conn = getattr(_tls, "tei_conn", None)
            if conn is None:
                conn = http.client.HTTPConnection(host, port, timeout=30.0)
                _tls.tei_conn = conn
            conn.request(
                "POST",
                "/embed",
                body=body,
                headers={
                    "Content-Type": "application/json",
                    "Connection": "keep-alive",
                },
            )
            resp = conn.getresponse()
            raw = resp.read()
            if resp.status == 200:
                return json.loads(raw.decode("utf-8"))
            _tls.tei_conn = None
        except Exception:
            _tls.tei_conn = None
            if attempt == 2:
                raise
            time.sleep(0.1)
    raise RuntimeError("TEI embed batch failed")


def chunk_markdown_by_heading(
    file_path: str, source_type: str, max_chunk_lines: int = 45
) -> list[dict[str, Any]]:
    if not os.path.isfile(file_path):
        return []
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    if not lines:
        return []
    sections: list[tuple[str, int, int, list[str]]] = []
    cur_heading = os.path.basename(file_path)
    cur_start = 1
    cur_lines: list[str] = []
    for idx, line in enumerate(lines, start=1):
        m = re.match(r"^(#{1,3})\s+(.+?)\s*$", line)
        if m and cur_lines:
            sections.append((cur_heading, cur_start, idx - 1, cur_lines))
            cur_heading = m.group(2).strip()
            cur_start = idx
            cur_lines = [line]
        else:
            if m and (not cur_lines):
                cur_heading = m.group(2).strip()
                cur_start = idx
            cur_lines.append(line)
    if cur_lines:
        sections.append((cur_heading, cur_start, len(lines), cur_lines))
    chunks: list[dict[str, Any]] = []
    bname = os.path.basename(file_path)
    for heading, s_line, e_line, sec_lines in sections:
        if len(sec_lines) <= max_chunk_lines:
            text_body = "".join(sec_lines).strip()
            if not text_body:
                continue
            chunks.append(
                {
                    "file_path": file_path,
                    "start_line": s_line,
                    "end_line": e_line,
                    "line_range": f"L{s_line}-L{e_line}",
                    "source_type": source_type,
                    "symbol": heading,
                    "snippet": text_body[:1200],
                    "embed_text": f"File: {bname} ({file_path}) | Heading: {heading} | {text_body[:900]}",
                }
            )
        else:
            step = max(20, max_chunk_lines - 5)
            for offset in range(0, len(sec_lines), step):
                sub = sec_lines[offset : offset + max_chunk_lines]
                sub_s = s_line + offset
                sub_e = min(e_line, sub_s + len(sub) - 1)
                text_body = "".join(sub).strip()
                if not text_body:
                    continue
                sub_sym = (
                    heading if offset == 0 else f"{heading} (part {offset // step + 1})"
                )
                chunks.append(
                    {
                        "file_path": file_path,
                        "start_line": sub_s,
                        "end_line": sub_e,
                        "line_range": f"L{sub_s}-L{sub_e}",
                        "source_type": source_type,
                        "symbol": sub_sym,
                        "snippet": text_body[:1200],
                        "embed_text": f"File: {bname} ({file_path}) | Heading: {sub_sym} | {text_body[:900]}",
                    }
                )
    return chunks


def chunk_role_prompt(file_path: str) -> list[dict[str, Any]]:
    if not os.path.isfile(file_path):
        return []
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    if not lines:
        return []
    bname = os.path.basename(file_path)
    role_name = bname.replace(".prompt", "")
    full_text = "".join(lines).strip()
    return [
        {
            "file_path": file_path,
            "start_line": 1,
            "end_line": len(lines),
            "line_range": f"L1-L{len(lines)}",
            "source_type": "role_prompt",
            "symbol": f"role:{role_name}",
            "snippet": full_text[:1200],
            "embed_text": f"Role Prompt: {role_name} ({file_path}) | {full_text[:900]}",
        }
    ]


def chunk_python_ast(
    file_path: str, source_type: str, max_chunks_per_file: int = 3
) -> list[dict[str, Any]]:
    if not os.path.isfile(file_path):
        return []
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()
    lines = source.splitlines(keepends=True)
    if not lines:
        return []
    bname = os.path.basename(file_path)
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        text_body = "".join(lines[:80]).strip()
        return [
            {
                "file_path": file_path,
                "start_line": 1,
                "end_line": min(len(lines), 80),
                "line_range": f"L1-L{min(len(lines), 80)}",
                "source_type": source_type,
                "symbol": bname,
                "snippet": text_body[:1200],
                "embed_text": f"Python Module: {bname} ({file_path}) | {text_body[:800]}",
            }
        ]
    mod_doc = ast.get_docstring(tree) or ""
    defs: list[tuple[str, int, int, str]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else "def"
            s_ln = getattr(node, "lineno", 1)
            e_ln = getattr(node, "end_lineno", min(len(lines), s_ln + 30))
            doc = ast.get_docstring(node) or ""
            defs.append((f"{kind} {node.name}", s_ln, e_ln, doc))
    if not defs or max_chunks_per_file == 1:
        sym_list = ", ".join(d[0] for d in defs[:20]) if defs else bname
        s_ln = 1
        e_ln = len(lines)
        snippet_lines = "".join(lines[:75]).strip()
        return [
            {
                "file_path": file_path,
                "start_line": s_ln,
                "end_line": e_ln,
                "line_range": f"L{s_ln}-L{e_ln}",
                "source_type": source_type,
                "symbol": f"{bname}: {sym_list[:120]}",
                "snippet": snippet_lines[:1200],
                "embed_text": f"Python AST: {bname} ({file_path}) | Symbols: {sym_list} | Doc: {mod_doc[:250]} | {snippet_lines[:600]}",
            }
        ]
    chunks: list[dict[str, Any]] = []
    group_size = max(1, math.ceil(len(defs) / max_chunks_per_file))
    for i in range(0, len(defs), group_size):
        grp = defs[i : i + group_size]
        s_ln = grp[0][1] if i > 0 else 1
        e_ln = grp[-1][2]
        sym_names = ", ".join(g[0] for g in grp)
        docs = " | ".join(g[3][:120] for g in grp if g[3])
        code_slice = "".join(lines[s_ln - 1 : min(e_ln, s_ln + 65)]).strip()
        chunks.append(
            {
                "file_path": file_path,
                "start_line": s_ln,
                "end_line": e_ln,
                "line_range": f"L{s_ln}-L{e_ln}",
                "source_type": source_type,
                "symbol": sym_names[:140],
                "snippet": code_slice[:1200],
                "embed_text": f"Python AST: {bname} ({file_path}) | Symbols: {sym_names} | Doc: {mod_doc[:150]} {docs[:200]} | {code_slice[:600]}",
            }
        )
    return chunks


def chunk_shell_script(
    file_path: str, source_type: str = "harness_sh"
) -> list[dict[str, Any]]:
    if not os.path.isfile(file_path):
        return []
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    if not lines:
        return []
    bname = os.path.basename(file_path)
    funcs = []
    for line in lines:
        m = re.match(r"^\s*(?:function\s+)?([a-zA-Z0-9_]+)\s*\(\)\s*\{", line)
        if m:
            funcs.append(m.group(1))
    sym = f"{bname} ({', '.join(funcs[:10])})" if funcs else bname
    snippet = "".join(lines[:75]).strip()
    return [
        {
            "file_path": file_path,
            "start_line": 1,
            "end_line": len(lines),
            "line_range": f"L1-L{len(lines)}",
            "source_type": source_type,
            "symbol": sym,
            "snippet": snippet[:1200],
            "embed_text": f"Harness Script: {sym} ({file_path}) | {snippet[:850]}",
        }
    ]


def collect_all_corpus_chunks() -> tuple[list[dict[str, Any]], dict[str, int]]:
    chunks: list[dict[str, Any]] = []
    counts: dict[str, int] = {
        "fleet_rules": 0,
        "role_prompts": 0,
        "harness_scripts": 0,
        "o1789_infra_receipts": 0,
        "bulkdownloader_code_and_contract": 0,
    }
    for rule_fp in (
        "/home/mboyle/bd-persist/FLEET_RULE-FLOOR.md",
        "/home/mboyle/bd-persist/FLEET_RULE.md",
    ):
        c = chunk_markdown_by_heading(
            rule_fp, source_type="fleet_rule", max_chunk_lines=35
        )
        chunks.extend(c)
        counts["fleet_rules"] += len(c)
    for p_fp in sorted(glob.glob("/home/mboyle/bd-persist/role-prompts/*.prompt")):
        c = chunk_role_prompt(p_fp)
        chunks.extend(c)
        counts["role_prompts"] += len(c)
    for sh_fp in sorted(glob.glob("/home/mboyle/bd-persist/harness/*.sh")):
        c = chunk_shell_script(sh_fp, source_type="harness_sh")
        chunks.extend(c)
        counts["harness_scripts"] += len(c)
    for py_fp in sorted(glob.glob("/home/mboyle/bd-persist/harness/*.py")):
        c = chunk_python_ast(py_fp, source_type="harness_py", max_chunks_per_file=1)
        chunks.extend(c)
        counts["harness_scripts"] += len(c)
    for md_fp in sorted(
        glob.glob("/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/*.md")
    ):
        c = chunk_markdown_by_heading(
            md_fp, source_type="infra_receipt", max_chunk_lines=40
        )
        chunks.extend(c)
        counts["o1789_infra_receipts"] += len(c)
    bd_claude = "/home/mboyle/BulkDownloader/CLAUDE.md"
    if os.path.isfile(bd_claude):
        c = chunk_markdown_by_heading(
            bd_claude, source_type="repo_contract", max_chunk_lines=40
        )
        chunks.extend(c)
        counts["bulkdownloader_code_and_contract"] += len(c)
    py_patterns = [
        "/home/mboyle/BulkDownloader/downloader/*.py",
        "/home/mboyle/BulkDownloader/bulk_downloader/*.py",
    ]
    seen_py = set()
    for pat in py_patterns:
        for py_fp in sorted(glob.glob(pat)):
            if py_fp in seen_py:
                continue
            seen_py.add(py_fp)
            c = chunk_python_ast(
                py_fp, source_type="codebase_ast", max_chunks_per_file=1
            )
            chunks.extend(c)
            counts["bulkdownloader_code_and_contract"] += len(c)
    return (chunks, counts)


def qdrant_request(
    method: str, path: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    url = f"{QDRANT_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method=method
    )
    with urllib.request.urlopen(req, timeout=60.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Boylenet Fleet Hybrid RAG + AST Indexer"
    )
    parser.add_argument(
        "--collection", default=COLLECTION_NAME, help="Target Qdrant collection name"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="TEI embedding batch size (default 32)",
    )
    parser.add_argument(
        "--workers", type=int, default=8, help="Concurrent TEI batch workers"
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate Qdrant collection from scratch",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON summary")
    args = parser.parse_args()
    t_start = time.perf_counter()
    create_res = qdrant_request(
        "PUT",
        f"/collections/{args.collection}",
        {
            "vectors": {"size": VECTOR_DIM, "distance": "Cosine"},
            "recreate": args.recreate,
        },
    )
    t_chunk0 = time.perf_counter()
    chunks, source_counts = collect_all_corpus_chunks()
    chunk_elapsed_s = time.perf_counter() - t_chunk0
    bs = max(1, min(32, int(args.batch_size)))
    batches: list[list[tuple[int, dict[str, Any]]]] = []
    for i in range(0, len(chunks), bs):
        batches.append(
            [(idx, chunks[idx]) for idx in range(i, min(i + bs, len(chunks)))]
        )
    t_emb0 = time.perf_counter()

    def process_batch(
        batch_items: list[tuple[int, dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        texts = [item[1]["embed_text"] for item in batch_items]
        raw_vecs = call_tei_embed_batch(texts)
        points: list[dict[str, Any]] = []
        for (pt_idx, ch), t_vec in zip(batch_items, raw_vecs):
            vec_1024 = build_hybrid_1024_vector(t_vec, ch["embed_text"])
            payload = {
                "file_path": ch["file_path"],
                "start_line": ch["start_line"],
                "end_line": ch["end_line"],
                "line_range": ch["line_range"],
                "source_type": ch["source_type"],
                "symbol": ch["symbol"],
                "snippet": ch["snippet"],
            }
            points.append({"id": pt_idx + 1, "vector": vec_1024, "payload": payload})
        return points

    all_points: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for batch_pts in pool.map(process_batch, batches):
            all_points.extend(batch_pts)
    embed_elapsed_s = time.perf_counter() - t_emb0
    t_up0 = time.perf_counter()
    upsert_batch_size = 256
    total_upserted = 0
    for i in range(0, len(all_points), upsert_batch_size):
        sub_pts = all_points[i : i + upsert_batch_size]
        up_res = qdrant_request(
            "PUT", f"/collections/{args.collection}/points", {"points": sub_pts}
        )
        total_upserted += int(
            (up_res.get("result") or {}).get("upserted", len(sub_pts))
        )
    ast_pts = [
        p
        for p in all_points
        if p["payload"]["source_type"] in ("codebase_ast", "harness_py", "harness_sh")
    ]
    doc_pts = [
        p
        for p in all_points
        if p["payload"]["source_type"]
        in ("fleet_rule", "infra_receipt", "role_prompt", "repo_contract")
    ]
    for sub_col, sub_list in (
        ("boylenet_codebase_ast", ast_pts),
        ("swarm_docs_rag", doc_pts),
    ):
        for i in range(0, len(sub_list), upsert_batch_size):
            qdrant_request(
                "PUT",
                f"/collections/{sub_col}/points",
                {"points": sub_list[i : i + upsert_batch_size]},
            )
    upsert_elapsed_s = time.perf_counter() - t_up0
    col_info = qdrant_request("GET", f"/collections/{args.collection}")
    total_elapsed_s = time.perf_counter() - t_start
    summary = {
        "rc": 0,
        "status": "INDEXED",
        "qdrant_url": QDRANT_URL,
        "tei_embed_url": f"{TEI_EMBED_URL}/embed",
        "collection": args.collection,
        "vector_size": VECTOR_DIM,
        "distance": "Cosine",
        "batch_size": bs,
        "total_chunks_indexed": total_upserted,
        "source_breakdown": source_counts,
        "timings_sec": {
            "chunking_s": round(chunk_elapsed_s, 3),
            "embedding_s": round(embed_elapsed_s, 3),
            "qdrant_upsert_s": round(upsert_elapsed_s, 3),
            "total_s": round(total_elapsed_s, 3),
            "chunks_per_sec": round(total_upserted / max(embed_elapsed_s, 0.001), 1),
        },
        "collection_info": col_info.get("result", {}),
        "collection_created": create_res.get("status") == "ok",
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"[bd-rag-indexer] Indexed {total_upserted} chunks into {QDRANT_URL}/collections/{args.collection} "
            f"(dim={VECTOR_DIM}, distance=Cosine) in {total_elapsed_s:.2f}s "
            f"({summary['timings_sec']['chunks_per_sec']} chunks/s)"
        )
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
