import warnings
warnings.filterwarnings("ignore")
import subprocess
import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("python-linter")

def sort_keys_recursive(val):
    if isinstance(val, dict):
        return {k: sort_keys_recursive(v) for k, v in sorted(val.items())}
    if isinstance(val, list):
        return [sort_keys_recursive(x) for x in val]
    return val

def serialize_tools_canonical(tools: list | None = None) -> str:
    """Canonicalize and serialize tool schemas with sorted keys and alphabetical ordering."""
    import json
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

    import json
    import mcp.types as types
    def deterministic_model_dump_json(self, *args, **kwargs):
        d = self.model_dump(by_alias=True, exclude_none=True)
        return json.dumps(sort_keys_recursive(d), sort_keys=True, separators=(',', ':'), ensure_ascii=True)

    types.JSONRPCResponse.model_dump_json = deterministic_model_dump_json
    types.JSONRPCNotification.model_dump_json = deterministic_model_dump_json

_apply_mcp_canonicalization(mcp)

@mcp.tool()
def ruff_check(path: str = ".", fix: bool = False) -> str:
    """Run ruff check on a file or directory. Optionally apply safe auto-fixes."""
    cmd = ["ruff", "check"]
    if fix:
        cmd.append("--fix")
    cmd.append(path)
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = (res.stdout + "\n" + res.stderr).strip()
    return out or "All checks passed! No issues found."

@mcp.tool()
def ruff_format(path: str = ".", check_only: bool = True) -> str:
    """Run ruff format on a file or directory."""
    cmd = ["ruff", "format"]
    if check_only:
        cmd.append("--check")
    cmd.append(path)
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = (res.stdout + "\n" + res.stderr).strip()
    return out or "Formatting is clean!"

if __name__ == "__main__":
    if "--canonical-schemas" in sys.argv or "--tools" in sys.argv:
        print(serialize_tools_canonical())
        sys.exit(0)
    mcp.run(transport="stdio")
