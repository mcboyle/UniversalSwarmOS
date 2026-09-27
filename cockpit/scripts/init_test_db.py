#!/usr/bin/env python3
"""
scripts/init_test_db.py
Creates and initializes an isolated SQLite WAL database fixture with usage_responses schema.
"""
import json
import sqlite3
import sys

def init_db(db_path, num_rows=50):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_responses (
            provider TEXT,
            response_id TEXT,
            timestamp TEXT,
            model TEXT,
            usage TEXT,
            fingerprint TEXT,
            quarantined INTEGER,
            PRIMARY KEY(provider, response_id)
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_diagnostics (
            kind TEXT PRIMARY KEY,
            count INTEGER
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_occurrences (
            provider TEXT,
            response_id TEXT,
            host TEXT,
            thread TEXT,
            source TEXT,
            PRIMARY KEY(provider, response_id, host, thread, source)
        );
    """)
    sample_models = [
        ("anthropic", "claude-opus-5-5", 1000, 920, 150, 80),
        ("xai", "grok-2", 1200, 960, 180, 100),
        ("moonshot", "kimi-k1.5", 1500, 1200, 220, 150),
    ]
    for i in range(num_rows):
        provider, model, inp, cache_read, out, cache_create = sample_models[i % len(sample_models)]
        total = inp + out
        ts = f"2026-09-22T22:{i%60:02d}:00Z"
        usage_payload = {
            "input_tokens": inp,
            "cached_input_tokens": cache_read,
            "output_tokens": out,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_create,
            "total_tokens": total
        }
        usage_json = json.dumps(usage_payload)
        conn.execute("""
            INSERT OR REPLACE INTO usage_responses VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (provider, f"resp_{i}", ts, model, usage_json, f"fp_{provider}_{i}", 0))
        conn.execute("""
            INSERT OR REPLACE INTO usage_occurrences VALUES (?, ?, ?, ?, ?);
        """, (provider, f"resp_{i}", f"host_{i%4}", f"thread_{i%5}", f"/path/to/log_{provider}_{i}.jsonl"))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test_usage.sqlite"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    init_db(path, count)
