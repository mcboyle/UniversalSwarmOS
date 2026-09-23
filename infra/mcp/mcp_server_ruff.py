import warnings
warnings.filterwarnings("ignore")
import subprocess
import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("python-linter")

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
    mcp.run(transport="stdio")
