import warnings
warnings.filterwarnings("ignore")
import argparse
import os
import shutil
import subprocess
import sys
from mcp.server.fastmcp import FastMCP

parser = argparse.ArgumentParser(description="VMware Clones & vCenter MCP Server", add_help=False)
parser.add_argument("--host", default="10.0.20.70", help="vCenter / ESXi Host IP")
known, remaining = parser.parse_known_args()
sys.argv = [sys.argv[0]] + remaining

host = known.host or "10.0.20.70"
if host in ("10.0.70.1", "10.0.20.70"):
    # vCenter Server Appliance (VCSA)
    govc_url = "https://Administrator%40boylenet.themfboyles.com:Matt99%21%21@10.0.20.70/sdk"
else:
    # Direct ESXi HostAgent
    govc_url = f"https://root:Matt99%21%21@{host}/sdk"

os.environ["GOVC_INSECURE"] = "1"
os.environ["GOVC_URL"] = govc_url
os.environ["GOVC_DATASTORE"] = "vsanDatastore"
os.environ["GOVC_RESOURCE_POOL"] = "/Boylenet Datacenter/host/Boylenet Cluster/Resources"

GOVC_BIN = shutil.which("govc") or "/usr/local/bin/govc"

mcp = FastMCP("vmware-clones")

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
def vm_list() -> str:
    """List virtual machines registered across the cluster in vCenter/ESXi."""
    cmd = [GOVC_BIN, "find", "/", "-type", "m"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = (res.stdout + "\n" + res.stderr).strip()
    return out or "No VMs found or query returned empty."

@mcp.tool()
def vm_info(vm_name: str) -> str:
    """Get detailed information about a specific VM."""
    cmd = [GOVC_BIN, "vm.info", vm_name]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return (res.stdout + "\n" + res.stderr).strip()

@mcp.tool()
def vm_clone(clone_name: str, template_or_vm: str = "", snapshot: str = "") -> str:
    """Clone an instant VM from a snapshot or template."""
    import random
    if not template_or_vm:
        template_or_vm = random.choice(["spare2", "Test", "spare12", "spare5"])
    cmd = [GOVC_BIN, "vm.clone"]
    if snapshot:
        cmd.extend(["-snapshot", snapshot])
    cmd.extend(["-vm", template_or_vm, clone_name])
    res = subprocess.run(cmd, capture_output=True, text=True)
    return (res.stdout + "\n" + res.stderr).strip() or f"Successfully cloned {clone_name} from {template_or_vm}"

@mcp.tool()
def vm_destroy(vm_name: str) -> str:
    """Destroy an ephemeral instant clone VM."""
    cmd = [GOVC_BIN, "vm.destroy", vm_name]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return (res.stdout + "\n" + res.stderr).strip() or f"Successfully destroyed {vm_name}"

if __name__ == "__main__":
    if "--canonical-schemas" in sys.argv or "--tools" in sys.argv:
        print(serialize_tools_canonical())
        sys.exit(0)
    mcp.run(transport="stdio")
