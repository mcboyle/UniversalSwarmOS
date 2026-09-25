import warnings

warnings.filterwarnings("ignore")

import contextlib
import http.client
import json
import threading
import urllib.error
import urllib.request
from typing import Any

import redis
from mcp.server.fastmcp import FastMCP
from redis.cluster import RedisCluster, RedisClusterException

mcp = FastMCP("ratf", log_level="ERROR")

_REDIS_CLIENT: Any = None
_REDIS_LOCK = threading.Lock()


def _get_redis_client() -> Any:
    global _REDIS_CLIENT
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT

    with _REDIS_LOCK:
        if _REDIS_CLIENT is not None:
            return _REDIS_CLIENT

        r = None
        try:
            r = redis.Redis(
                host="127.0.0.1",
                port=6379,
                decode_responses=True,
                encoding_errors="replace",
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            cluster_info = r.info("cluster")
            if cluster_info.get("cluster_enabled") in (1, "1", True):
                with contextlib.suppress(redis.RedisError, OSError):
                    r.close()
                r = None

                _REDIS_CLIENT = RedisCluster(
                    host="127.0.0.1",
                    port=6379,
                    decode_responses=True,
                    encoding_errors="replace",
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                )
            else:
                _REDIS_CLIENT = r
                r = None
        except (redis.RedisError, RedisClusterException, TimeoutError, OSError):
            if r is not None:
                with contextlib.suppress(redis.RedisError, OSError):
                    r.close()
            _REDIS_CLIENT = redis.Redis(
                host="127.0.0.1",
                port=6379,
                decode_responses=True,
                encoding_errors="replace",
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
        return _REDIS_CLIENT


def _reset_redis_client() -> None:
    global _REDIS_CLIENT
    with _REDIS_LOCK:
        if _REDIS_CLIENT is not None:
            with contextlib.suppress(redis.RedisError, RedisClusterException, OSError):
                _REDIS_CLIENT.close()
            _REDIS_CLIENT = None


@mcp.tool()
def ctx_slice(
    code: str | None = "",
    pattern: str | None = "",
    lang: str | None = "python",
    endpoint: str | None = "",
    timeout: float | None = 15,
    skeleton: bool | None = False,
    symbol: str | None = "",
    file_path: str | None = "",
) -> str:
    """Query or parse code using the Tree-sitter AST server at 127.0.0.1:8095.

    Args:
        code: Source code string to parse or query.
        pattern: AST pattern to match (ast-grep query). If provided, sends a query request.
        lang: Target language for pattern query (default: python).
        endpoint: Specific endpoint override ('parse', 'query', 'health', 'skeleton', 'symbol'). If empty, determined automatically.
        timeout: Request timeout in seconds (default: 15).
        skeleton: If True, request AST skeleton projection (bodies folded to ...).
        symbol: If provided, extract the definition of this symbol.
        file_path: Path to source file on disk (optional).
    """
    if endpoint is not None and not isinstance(endpoint, str):
        return f"Error: Unsupported endpoint '{endpoint}'. Supported endpoints: 'parse', 'query', 'health', 'skeleton', 'symbol'."

    ep = endpoint.strip().lower() if endpoint else ""
    if ep and ep not in ("parse", "query", "health", "skeleton", "symbol"):
        return f"Error: Unsupported endpoint '{endpoint}'. Supported endpoints: 'parse', 'query', 'health', 'skeleton', 'symbol'."

    if timeout is None:
        timeout = 15
    elif (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or timeout <= 0
    ):
        return f"Error: timeout must be a positive number, got {timeout}."

    code_str = "" if code is None else str(code)
    pattern_str = "" if pattern is None else str(pattern)
    lang_str = "python" if not lang else str(lang)
    symbol_str = "" if symbol is None else str(symbol).strip()
    file_path_str = "" if file_path is None else str(file_path).strip()
    is_skeleton = bool(skeleton) or (ep == "skeleton")

    base_url = "http://127.0.0.1:8095"

    try:
        if ep == "health" or (not ep and not code_str and not pattern_str and not is_skeleton and not symbol_str and not file_path_str):
            req = urllib.request.Request(f"{base_url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")

        if is_skeleton:
            payload_dict = {}
            if code_str:
                payload_dict["code"] = code_str
            if file_path_str:
                payload_dict["file_path"] = file_path_str
            payload = json.dumps(payload_dict).encode("utf-8")
            target = f"{base_url}/skeleton"
        elif symbol_str or ep == "symbol":
            payload_dict = {"symbol": symbol_str}
            if code_str:
                payload_dict["code"] = code_str
            if file_path_str:
                payload_dict["file_path"] = file_path_str
            payload = json.dumps(payload_dict).encode("utf-8")
            target = f"{base_url}/symbol"
        elif ep == "query" or (not ep and pattern_str):
            payload = json.dumps(
                {"pattern": pattern_str, "code": code_str, "lang": lang_str}
            ).encode("utf-8")
            target = f"{base_url}/query"
        else:
            payload = json.dumps({"code": code_str}).encode("utf-8")
            target = f"{base_url}/parse"

        req = urllib.request.Request(
            target,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            return f"Error connecting to AST server: HTTP {exc.code} - {body}"
        except (OSError, UnicodeError, http.client.HTTPException):
            return f"Error connecting to AST server: {exc}"
    except (
        urllib.error.URLError,
        http.client.HTTPException,
        TimeoutError,
        OSError,
        ValueError,
    ) as exc:
        return f"Error connecting to AST server: {exc}"



@mcp.tool()
def ctx_deref(
    key: str | None,
    value: str | None = "",
    op: str | None = "get",
) -> str:
    """Read or write pointer handles in the Redis cluster at 127.0.0.1:6379.

    Args:
        key: The pointer handle key to read, write, or delete.
        value: The string value/payload to associate with the key (used when op='set').
        op: Operation to perform: 'get' (default), 'set', or 'del'.
    """
    if not isinstance(key, str) or not key.strip():
        return "Error: Key parameter cannot be empty."

    if op is not None and not isinstance(op, str):
        return f"Error: Unsupported operation '{op}'. Supported operations: 'get', 'set', 'del'."

    operation = op.strip().lower() if (op and op.strip()) else "get"
    if operation not in ("get", "set", "del", "delete"):
        return f"Error: Unsupported operation '{op}'. Supported operations: 'get', 'set', 'del'."

    val_to_set = "" if value is None else str(value)

    try:
        r = _get_redis_client()
        if operation == "set":
            r.set(key, val_to_set)
            return f"Handle '{key}' written successfully."
        elif operation in ("del", "delete"):
            deleted = r.delete(key)
            return f"Handle '{key}' deleted ({deleted} keys removed)."
        else:
            val = r.get(key)
            if val is None:
                return f"Handle '{key}' not found."
            return str(val)
    except (
        redis.RedisError,
        RedisClusterException,
        TimeoutError,
        OSError,
        ValueError,
        UnicodeError,
    ) as exc:
        if isinstance(
            exc,
            (
                redis.ConnectionError,
                redis.TimeoutError,
                RedisClusterException,
                TimeoutError,
                OSError,
            ),
        ):
            _reset_redis_client()
        return f"Error communicating with Redis: {exc}"


@mcp.tool()
def ctx_resolve(
    query: str | None,
    top_k: int | None = 5,
) -> str:
    """Perform hybrid lexical and vector retrieval across the indexed knowledge base.
    
    Args:
        query: Search query or symbol name.
        top_k: Number of nearest document matches to retrieve (default: 5).
    """
    if not isinstance(query, str) or not query.strip():
        return "Error: query parameter cannot be empty."
    k = top_k if (isinstance(top_k, int) and top_k > 0) else 5

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect("postgresql://postgres:postgres@127.0.0.1:5432/ai_mesh")
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = """
                SELECT doc_id, title, substring(content from 1 for 300) as snippet,
                       ts_rank_cd(tsv, plainto_tsquery('english', %s)) as rank
                FROM public.documents
                WHERE tsv @@ plainto_tsquery('english', %s)
                ORDER BY rank DESC
                LIMIT %s;
            """
            cur.execute(sql, (query, query, k))
            rows = cur.fetchall()

        conn.close()
        if not rows:
            return f"No matching documents found in ai_mesh for '{query}'."

        results = [f"[{r['doc_id']}] {r['title']} (score: {r['rank']:.4f})\n{r['snippet']}..." for r in rows]
        return "\n\n".join(results)
    except (psycopg2.Error, OSError, ValueError, KeyError) as exc:
        return f"Error executing retrieval in ai_mesh: {exc}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
