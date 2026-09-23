#!/usr/bin/env python3
"""hybrid_search.py -- Hybrid Lexical + Dense Semantic Search Pipeline.

Uses TEI (Text Embeddings Inference) on localhost:8081 for 384-d dense vectors
and PGvector on localhost:5432 (database ai_mesh) for hybrid retrieval with
Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

TEI_EMBED_URL = "http://localhost:8081/embed"
PG_DSN = "postgresql://postgres:postgres@localhost:5432/ai_mesh"


def get_embedding(text: str) -> List[float]:
    """Retrieve dense embedding from TEI."""
    # MiniLM model token window is 512 tokens (~1500 chars). Truncate to avoid 413.
    truncated = text[:1200]
    req = urllib.request.Request(
        TEI_EMBED_URL,
        data=json.dumps({"inputs": truncated}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res[0]


def init_schema(conn) -> None:
    """Initialize hybrid search schema and indices in PostgreSQL."""
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                doc_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', title || ' ' || content)) STORED,
                embedding vector(384),
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_docs_tsv ON documents USING gin(tsv);
            CREATE INDEX IF NOT EXISTS idx_docs_embedding ON documents USING hnsw (embedding vector_cosine_ops);
            """
        )
        conn.commit()


def index_document(
    conn, doc_id: str, title: str, content: str, metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Index or update a document with dense embedding and full-text vector."""
    emb = get_embedding(f"{title}\n{content}")
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (doc_id, title, content, embedding, metadata)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (doc_id) DO UPDATE SET
                title = EXCLUDED.title,
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata;
            """,
            (doc_id, title, content, emb, json.dumps(metadata or {})),
        )
        conn.commit()


def hybrid_search(conn, query: str, limit: int = 5, rrf_k: int = 60) -> List[Dict[str, Any]]:
    """Execute hybrid search combining FTS and dense vector search via RRF."""
    emb = get_embedding(query)
    emb_str = f"[{','.join(str(x) for x in emb)}]"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Reciprocal Rank Fusion (RRF) combining lexical (FTS) and vector cosine similarity
        cur.execute(
            """
            WITH lexical AS (
                SELECT id, doc_id, title, content, metadata,
                       ROW_NUMBER() OVER (ORDER BY ts_rank_cd(tsv, plainto_tsquery('english', %s)) DESC) AS rank
                FROM documents
                WHERE tsv @@ plainto_tsquery('english', %s)
                LIMIT 50
            ),
            semantic AS (
                SELECT id, doc_id, title, content, metadata,
                       ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS rank
                FROM documents
                LIMIT 50
            )
            SELECT 
                COALESCE(l.id, s.id) AS id,
                COALESCE(l.doc_id, s.doc_id) AS doc_id,
                COALESCE(l.title, s.title) AS title,
                COALESCE(l.content, s.content) AS content,
                COALESCE(l.metadata, s.metadata) AS metadata,
                COALESCE(1.0 / (%s + l.rank), 0.0) + COALESCE(1.0 / (%s + s.rank), 0.0) AS rrf_score
            FROM lexical l
            FULL OUTER JOIN semantic s ON l.id = s.id
            ORDER BY rrf_score DESC
            LIMIT %s;
            """,
            (query, query, emb_str, rrf_k, rrf_k, limit),
        )
        return list(cur.fetchall())


def main():
    parser = argparse.ArgumentParser(description="Hybrid search pipeline CLI")
    parser.add_argument("--init", action="store_true", help="Initialize schema and indices")
    parser.add_argument("--index", nargs=3, metavar=("ID", "TITLE", "FILE"), help="Index a document from a file")
    parser.add_argument("--search", metavar="QUERY", help="Search query")
    parser.add_argument("--limit", type=int, default=5, help="Result limit")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    if psycopg2 is None:
        print("psycopg2 not installed in current python environment", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(PG_DSN)

    if args.init:
        init_schema(conn)
        print("Initialized hybrid search schema (PGvector + FTS GIN index) in ai_mesh.")

    if args.index:
        doc_id, title, fpath = args.index
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        index_document(conn, doc_id, title, content)
        print(f"Indexed document '{doc_id}': {title}")

    if args.search:
        results = hybrid_search(conn, args.search, limit=args.limit)
        if args.json:
            clean = [
                {
                    "doc_id": r["doc_id"],
                    "title": r["title"],
                    "score": round(float(r["rrf_score"]), 5),
                    "snippet": r["content"][:300].replace("\n", " "),
                    "metadata": r.get("metadata", {}),
                }
                for r in results
            ]
            print(json.dumps(clean))
        else:
            print(f"Hybrid search results for: '{args.search}'")
            for i, res in enumerate(results, 1):
                print(f"{i}. [{res['doc_id']}] {res['title']} (score: {res['rrf_score']:.4f})")
                snippet = res['content'][:120].replace('\n', ' ')
                print(f"   \"{snippet}...\"\n")

    conn.close()


if __name__ == "__main__":
    main()
