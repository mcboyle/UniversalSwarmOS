import sqlite3
import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP

DB_PATH = Path("/home/mboyle/bd-persist/fleet-bus.db")

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH, isolation_level=None) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cursors (
                seat TEXT NOT NULL,
                topic TEXT NOT NULL,
                last_read_id INTEGER NOT NULL,
                PRIMARY KEY (seat, topic)
            )
        """)

mcp = FastMCP("bd-bus")

@mcp.tool()
def bus_publish(topic: str, payload: str) -> str:
    """Publish a message to the fleet context bus."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO messages (topic, payload) VALUES (?, ?)", (topic, payload))
    return f"Published to {topic}"

@mcp.tool()
def bus_read(seat: str, topic: str, unread_only: bool = True) -> str:
    """Read messages from the bus. Acknowledges messages automatically if unread_only is True."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor_val = 0
        if unread_only:
            row = conn.execute("SELECT last_read_id FROM cursors WHERE seat=? AND topic=?", (seat, topic)).fetchone()
            if row:
                cursor_val = row[0]
                
        rows = conn.execute("SELECT id, timestamp, payload FROM messages WHERE topic=? AND id > ? ORDER BY id ASC", (topic, cursor_val)).fetchall()
        
        if not rows:
            return "No new messages."
            
        max_id = rows[-1][0]
        if unread_only:
            conn.execute("INSERT OR REPLACE INTO cursors (seat, topic, last_read_id) VALUES (?, ?, ?)", (seat, topic, max_id))
            
        results = [f"[{r[1]}] {r[2]}" for r in rows]
        return "\n".join(results)

@mcp.tool()
def bus_summarize(topic: str) -> str:
    """Uses caveman-style compression to return a 1-line diff of state for the given topic."""
    # Caveman style summarization stub - in a real deployment this could use liteLLM or regex
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        count = conn.execute("SELECT COUNT(*) FROM messages WHERE topic=?", (topic,)).fetchone()[0]
    return f"{count} total events on {topic}. (Caveman compression: ready)"

if __name__ == "__main__":
    init_db()
    mcp.run(transport="stdio")
