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

def sort_keys_recursive(val):
    if isinstance(val, dict):
        return {k: sort_keys_recursive(v) for k, v in sorted(val.items())}
    if isinstance(val, list):
        return [sort_keys_recursive(x) for x in val]
    return val

def serialize_tools_canonical(tools: list | None = None) -> str:
    """Canonicalize and serialize tool schemas with sorted keys and alphabetical ordering."""
    if tools is None:
        raw_tools = mcp._tool_manager.list_tools()
        tools_data = []
        for t in raw_tools:
            item = {
                "name": t.name,
                "description": t.description or "",
                "inputSchema": t.parameters if isinstance(t.parameters, dict) else {},
            }
            if hasattr(t, "output_schema") and t.output_schema:
                item["outputSchema"] = t.output_schema
            tools_data.append(item)
    else:
        tools_data = tools

    sorted_tools = sorted([sort_keys_recursive(t) for t in tools_data], key=lambda x: x.get("name", ""))
    return json.dumps(sorted_tools, sort_keys=True, separators=(',', ':'), ensure_ascii=True)

def _apply_mcp_canonicalization(mcp_server: FastMCP):
    orig_list = mcp_server._tool_manager.list_tools
    def sorted_list():
        items = orig_list()
        for t in items:
            if hasattr(t, "parameters") and isinstance(t.parameters, dict):
                t.parameters = sort_keys_recursive(t.parameters)
            if hasattr(t, "output_schema") and isinstance(t.output_schema, dict):
                t.output_schema = sort_keys_recursive(t.output_schema)
        return sorted(items, key=lambda t: t.name)
    mcp_server._tool_manager.list_tools = sorted_list

    if hasattr(mcp_server, "_mcp_server") and hasattr(mcp_server._mcp_server, "request_handlers"):
        import mcp.types as types
        orig_handler = mcp_server._mcp_server.request_handlers.get(types.ListToolsRequest)
        if orig_handler:
            async def sorted_list_tools_handler(req: types.ListToolsRequest):
                result = await orig_handler(req)
                if hasattr(result, "root") and hasattr(result.root, "tools"):
                    result.root.tools.sort(key=lambda t: t.name)
                    for t in result.root.tools:
                        if hasattr(t, "inputSchema") and isinstance(t.inputSchema, dict):
                            t.inputSchema = sort_keys_recursive(t.inputSchema)
                return result
            mcp_server._mcp_server.request_handlers[types.ListToolsRequest] = sorted_list_tools_handler

    import mcp.types as types
    def deterministic_model_dump_json(self, *args, **kwargs):
        d = self.model_dump(by_alias=True, exclude_none=True)
        return json.dumps(sort_keys_recursive(d), sort_keys=True, separators=(',', ':'), ensure_ascii=True)

    types.JSONRPCResponse.model_dump_json = deterministic_model_dump_json
    types.JSONRPCNotification.model_dump_json = deterministic_model_dump_json

_apply_mcp_canonicalization(mcp)


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
    import sys
    if "--canonical-schemas" in sys.argv or "--tools" in sys.argv:
        print(serialize_tools_canonical())
        sys.exit(0)
    init_db()
    mcp.run(transport="stdio")
