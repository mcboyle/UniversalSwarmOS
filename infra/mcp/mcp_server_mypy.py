import warnings
warnings.filterwarnings("ignore")
import subprocess
import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("type-enforcer")

@mcp.tool()
def mypy_check(path: str = ".", strict: bool = False) -> str:
    """Run mypy type checking on a file or directory."""
    cmd = ["mypy"]
    if strict:
        cmd.append("--strict")
    cmd.append(path)
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = (res.stdout + "\n" + res.stderr).strip()
    return out or "Success: no issues found."

if __name__ == "__main__":
    mcp.run(transport="stdio")
