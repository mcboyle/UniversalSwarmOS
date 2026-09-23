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
    mcp.run(transport="stdio")
