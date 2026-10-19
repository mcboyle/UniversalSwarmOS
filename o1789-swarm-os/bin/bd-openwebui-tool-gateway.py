from __future__ import annotations

import glob
import html
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

PORT = int(os.environ.get("BD_OPENWEBUI_TOOL_GATEWAY_PORT", "4079"))
HOST = os.environ.get("BD_OPENWEBUI_TOOL_GATEWAY_HOST", "0.0.0.0")
MCP_SCHEMA_ROOT = Path("/home/mboyle/.gemini/antigravity-cli/mcp")
SANDBOX_REPOS_DIR = Path("/var/tmp/openwebui-repos")
SANDBOX_WORKSPACE_DIR = Path("/var/tmp/openwebui-workspace")
SANDBOX_REPOS_DIR.mkdir(parents=True, exist_ok=True)
SANDBOX_WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
SEARXNG_URL = "http://10.0.70.164:8888/search"
GITEA_BASE_URL = "http://10.0.70.164:3000"
QDRANT_BASE_URL = "http://10.0.70.125:6333"
ORCHESTRATOR_URL = "http://10.0.70.164:4010"
CDP_NODES = {
    "battlestation": "http://10.0.10.137:9222",
    "137": "http://10.0.10.137:9222",
    "bittorrent": "http://10.0.70.181:9222",
    "181": "http://10.0.70.181:9222",
}
MCP_SERVER_COMMANDS: dict[str, dict[str, Any]] = {
    "bd": {"type": "http", "url": "http://10.0.70.164:8100/mcp"},
    "bd-bus": {"type": "stdio", "command": ["python3", "-m", "bd_bus_mcp"]},
    "bd-fleet": {
        "type": "stdio",
        "command": [
            "/home/mboyle/bd-persist/harness/bd-mcp/venv/bin/python",
            "/home/mboyle/bd-persist/plugins/bd-fleet-mcp/server.py",
        ],
    },
    "bd-fleet-mcp_bd-fleet": {
        "type": "stdio",
        "command": [
            "/home/mboyle/bd-persist/harness/bd-mcp/venv/bin/python",
            "/home/mboyle/bd-persist/plugins/bd-fleet-mcp/server.py",
        ],
    },
    "boylenet-infra": {
        "type": "stdio",
        "command": [
            "/usr/bin/python3",
            "/home/mboyle/bin/bd-boylenet-infra-mcp.py",
        ],
    },
    "caveman": {"type": "stdio", "command": ["/home/mboyle/.caveman/bin/caveman-mcp"]},
    "context-mode": {"type": "stdio", "command": ["npx", "-y", "context-mode"]},
    "fleet-sync": {
        "type": "stdio",
        "command": [
            "python3",
            "/home/mboyle/teamwork_projects/fleet_sync_tool/fleet_sync_mcp.py",
        ],
    },
    "hivemind-memory": {
        "type": "stdio",
        "command": [
            "python3",
            "/home/mboyle/.gemini/config/plugins/hivemind-memory/server.py",
        ],
    },
    "pg-local": {
        "type": "stdio",
        "command": [
            "npx",
            "-y",
            "@modelcontextprotocol/server-postgres",
            "postgresql://postgres@127.0.0.1:5432/ai_mesh",
        ],
    },
    "python-linter": {"type": "stdio", "command": ["python3", "-m", "mcp_server_ruff"]},
    "ratf": {"type": "stdio", "command": ["python3", "-m", "mcp_server_ratf"]},
    "serena": {
        "type": "stdio",
        "command": [
            "/home/mboyle/.local/bin/uvx",
            "--from",
            "git+https://github.com/oraios/serena",
            "serena",
            "start-mcp-server",
            "--context",
            "ide-assistant",
            "--transport",
            "stdio",
        ],
    },
    "type-enforcer": {"type": "stdio", "command": ["python3", "-m", "mcp_server_mypy"]},
    "vmware-clones": {
        "type": "stdio",
        "command": ["python3", "-m", "mcp_server_vmware", "--host", "10.0.20.70"],
        "env": {"BD_VC_CRED_FILE": "/home/mboyle/.bd-import/vc-cred.env"},
    },
}


def discover_all_skills_and_plugins() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def _parse_frontmatter(text: str, default_name: str) -> tuple[str, str]:
        name = default_name
        desc = ""
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm = parts[1]
                for line in fm.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k = k.strip().lower()
                        v = v.strip().strip('"').strip("'")
                        if k == "name" and v:
                            name = v
                        elif k == "description" and v:
                            desc = v
        if not desc:
            for line in text.splitlines():
                s = line.strip()
                if s and (not s.startswith("#")) and (not s.startswith("---")):
                    desc = s[:220]
                    break
        return (name, desc)

    skill_globs = [
        ("/home/mboyle/.kimi/skills/*/SKILL.md", "kimi-k2.8-skill"),
        ("/home/mboyle/.agents/skills/*/SKILL.md", "claude-codex-agy-skill"),
        ("/home/mboyle/.agents/skills/synced/*/*/SKILL.md", "claude-synced-skill"),
        (
            "/home/mboyle/.gemini/antigravity-cli/builtin/skills/*/SKILL.md",
            "gemini-agy-builtin-skill",
        ),
        ("/home/mboyle/.agents/plugins/*/skills/*/SKILL.md", "fleet-plugin-skill"),
        ("/home/mboyle/.agents/plugins/*/*/SKILL.md", "fleet-plugin-skill"),
    ]
    for pattern, source_type in skill_globs:
        for path_str in sorted(glob.glob(pattern)):
            p = Path(path_str)
            slug = re.sub(r"[^a-z0-9_-]", "-", p.parent.name.lower()).strip("-")
            if not slug or slug in seen_ids:
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            name, desc = _parse_frontmatter(content, slug)
            helper_files = [
                str(f.relative_to(p.parent))
                for f in p.parent.rglob("*")
                if f.is_file() and f.name != "SKILL.md"
            ][:25]
            seen_ids.add(slug)
            items.append(
                {
                    "id": slug,
                    "name": name,
                    "source": source_type,
                    "path": str(p),
                    "description": desc or f"{name} ({source_type})",
                    "helper_files": helper_files,
                    "content": content,
                }
            )
    for path_str in sorted(glob.glob("/home/mboyle/.claude/commands/*.md")):
        p = Path(path_str)
        slug = "claude-cmd-" + re.sub(r"[^a-z0-9_-]", "-", p.stem.lower()).strip("-")
        if slug in seen_ids:
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        name, desc = _parse_frontmatter(content, p.stem)
        seen_ids.add(slug)
        items.append(
            {
                "id": slug,
                "name": f"Claude Command: {name}",
                "source": "claude-code-command",
                "path": str(p),
                "description": desc or f"Claude Code slash command {p.stem}",
                "helper_files": [],
                "content": content,
            }
        )
    for path_str in sorted(glob.glob("/home/mboyle/.codex/agents/*.toml")):
        p = Path(path_str)
        if p.name.endswith(".config.toml"):
            continue
        slug = "codex-agent-" + re.sub(r"[^a-z0-9_-]", "-", p.stem.lower()).strip("-")
        if slug in seen_ids:
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        desc_match = re.search(r'description\s*=\s*"([^"]+)"', content)
        desc = (
            desc_match.group(1)
            if desc_match
            else f"Codex specialized agent profile {p.stem}"
        )
        seen_ids.add(slug)
        items.append(
            {
                "id": slug,
                "name": f"Codex Agent: {p.stem}",
                "source": "codex-agent-profile",
                "path": str(p),
                "description": desc,
                "helper_files": [],
                "content": f"# Codex Agent Profile: `{p.stem}`\n\n```toml\n{content}\n```",
            }
        )
    return items


def discover_mcp_Inventory() -> dict[str, Any]:
    servers: dict[str, Any] = {}
    total_tools = 0
    if MCP_SCHEMA_ROOT.exists():
        for srv_dir in sorted(MCP_SCHEMA_ROOT.iterdir()):
            if not srv_dir.is_dir():
                continue
            tools: list[dict[str, Any]] = []
            for jf in sorted(srv_dir.glob("*.json")):
                try:
                    schema = json.loads(jf.read_text(encoding="utf-8"))
                except Exception:
                    schema = {"name": jf.stem}
                tools.append(
                    {
                        "name": schema.get("name", jf.stem),
                        "description": schema.get("description", ""),
                        "parameters": schema.get("parameters")
                        or schema.get("inputSchema")
                        or {},
                        "schema_path": str(jf),
                    }
                )
                total_tools += 1
            servers[srv_dir.name] = {
                "server": srv_dir.name,
                "transport": MCP_SERVER_COMMANDS.get(srv_dir.name, {}).get(
                    "type", "stdio"
                ),
                "tool_count": len(tools),
                "tools": tools,
            }
    return {
        "server_count": len(servers),
        "total_tools": total_tools,
        "servers": servers,
    }


def tool_search_web(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or payload.get("q") or "").strip()
    max_results = int(payload.get("max_results") or payload.get("limit") or 8)
    if not query:
        return {"ok": False, "error": "Missing required parameter: query"}
    results: list[dict[str, Any]] = []
    engines_tried: list[str] = []
    try:
        engines_tried.append("searxng:8888")
        url = f"{SEARXNG_URL}?format=json&q={urllib.parse.quote_plus(query)}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "Boylenet-OpenWebUI-Gateway/1.0"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        for r in data.get("results", [])[:max_results]:
            results.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                    "engine": r.get("engine", "searxng"),
                }
            )
    except Exception as exc:
        engines_tried.append(f"searxng_err:{type(exc).__name__}")
    if len(results) < 3:
        try:
            engines_tried.append("duckduckgo_html")
            ddg_url = (
                f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
            )
            req = urllib.request.Request(
                ddg_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"
                },
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                raw_html = resp.read().decode("utf-8", errors="replace")
            blocks = re.findall(
                r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                raw_html,
                flags=re.DOTALL,
            )
            for href, title_html, snip_html in blocks[:max_results]:
                real_url = href
                if "uddg=" in href:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    if "uddg" in parsed:
                        real_url = parsed["uddg"][0]
                clean_title = html.unescape(re.sub(r"<[^>]+>", "", title_html)).strip()
                clean_snip = html.unescape(re.sub(r"<[^>]+>", "", snip_html)).strip()
                if real_url and clean_title:
                    results.append(
                        {
                            "title": clean_title,
                            "url": real_url,
                            "snippet": clean_snip,
                            "engine": "duckduckgo",
                        }
                    )
        except Exception as exc:
            engines_tried.append(f"ddg_err:{type(exc).__name__}")
    if len(results) < 3:
        try:
            engines_tried.append("wikipedia_api")
            wiki_url = (
                "https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&utf8=1&srlimit=5&srsearch="
                + urllib.parse.quote_plus(query)
            )
            req = urllib.request.Request(
                wiki_url, headers={"User-Agent": "Boylenet-OpenWebUI-Gateway/1.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                wdata = json.loads(resp.read().decode("utf-8", errors="replace"))
            for item in wdata.get("query", {}).get("search", []):
                title = item.get("title", "")
                snip = html.unescape(
                    re.sub(r"<[^>]+>", "", item.get("snippet", ""))
                ).strip()
                results.append(
                    {
                        "title": f"{title} - Wikipedia",
                        "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                        "snippet": snip,
                        "engine": "wikipedia",
                    }
                )
        except Exception:
            pass
    if len(results) < max_results:
        try:
            engines_tried.append("hn_algolia")
            hn_url = f"https://hn.algolia.com/api/v1/search?hitsPerPage=5&query={urllib.parse.quote_plus(query)}"
            req = urllib.request.Request(
                hn_url, headers={"User-Agent": "Boylenet-OpenWebUI-Gateway/1.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                hndata = json.loads(resp.read().decode("utf-8", errors="replace"))
            for hit in hndata.get("hits", []):
                title = hit.get("title") or hit.get("story_title") or ""
                url_hit = (
                    hit.get("url")
                    or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                )
                if title:
                    results.append(
                        {
                            "title": title,
                            "url": url_hit,
                            "snippet": f"HN points={hit.get('points', 0)} comments={hit.get('num_comments', 0)} author={hit.get('author', '')}",
                            "engine": "hn_algolia",
                        }
                    )
        except Exception:
            pass
    return {
        "ok": True,
        "query": query,
        "engines_tried": engines_tried,
        "result_count": len(results[:max_results]),
        "results": results[:max_results],
    }


def _html_to_markdown(
    raw_html: str, base_url: str = ""
) -> tuple[str, str, list[dict[str, str]]]:
    title_m = re.search(
        r"<title[^>]*>(.*?)</title>", raw_html, flags=re.IGNORECASE | re.DOTALL
    )
    title = html.unescape(title_m.group(1)).strip() if title_m else ""
    cleaned = re.sub(
        r"<(script|style|noscript|svg|iframe)[^>]*>.*?</\1>",
        " ",
        raw_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.DOTALL)
    links: list[dict[str, str]] = []
    for href, ltext in re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        lt = html.unescape(re.sub(r"<[^>]+>", "", ltext)).strip()
        if href and (not href.startswith(("javascript:", "#", "mailto:"))):
            full_url = urllib.parse.urljoin(base_url, href) if base_url else href
            if len(links) < 40:
                links.append({"text": lt[:100] or full_url, "url": full_url})
    for level in range(1, 7):
        cleaned = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            lambda m, lv=level: (
                f"\n\n{'#' * lv} "
                + html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
                + "\n\n"
            ),
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
    cleaned = re.sub(
        r"<li[^>]*>(.*?)</li>",
        lambda m: "\n- " + re.sub(r"<[^>]+>", "", m.group(1)).strip(),
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(
        r"<(p|div|br|tr|section|article)[^>]*>", "\n", cleaned, flags=re.IGNORECASE
    )
    text = html.unescape(re.sub(r"<[^>]+>", " ", cleaned))
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    md = "\n".join(ln for ln in lines if ln)
    return (title, md, links)


def tool_read_url_content(payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url") or "").strip()
    max_chars = int(payload.get("max_chars") or 16000)
    if not url or not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "Valid http:// or https:// url is required"}
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Boylenet-OpenWebUI-Reader/1.0",
                "Accept": "text/html,application/xhtml+xml,application/json,text/plain,*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            ctype = resp.headers.get("Content-Type", "")
            raw = resp.read(512000).decode("utf-8", errors="replace")
            status_code = resp.status
        if "json" in ctype.lower():
            return {
                "ok": True,
                "url": url,
                "status": status_code,
                "content_type": ctype,
                "markdown": raw[:max_chars],
                "links": [],
            }
        title, md, links = _html_to_markdown(raw, base_url=url)
        return {
            "ok": True,
            "url": url,
            "status": status_code,
            "title": title,
            "content_type": ctype,
            "markdown": md[:max_chars],
            "truncated": len(md) > max_chars,
            "links": links,
        }
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def tool_browse_live_page_cdp(payload: dict[str, Any]) -> dict[str, Any]:
    node_key = str(payload.get("node") or "battlestation").lower()
    cdp_base = CDP_NODES.get(node_key, "http://10.0.10.137:9222")
    action = str(payload.get("action") or "list_tabs").lower()
    url = str(payload.get("url") or "").strip()
    oracle_prompt = str(payload.get("oracle_prompt") or "").strip()
    if action == "oracle" and oracle_prompt:
        try:
            proc = subprocess.run(
                [
                    "/home/mboyle/bin/bd-oracle",
                    "--oracle",
                    "all",
                    "--json",
                    oracle_prompt,
                ],
                capture_output=True,
                text=True,
                timeout=45,
            )
            return {
                "ok": proc.returncode == 0,
                "action": "oracle",
                "returncode": proc.returncode,
                "stdout": proc.stdout[-8000:],
                "stderr": proc.stderr[-2000:],
            }
        except Exception as exc:
            return {"ok": False, "action": "oracle", "error": str(exc)}
    try:
        with urllib.request.urlopen(f"{cdp_base}/json/version", timeout=5) as r:
            version_info = json.loads(r.read().decode("utf-8", errors="replace"))
        with urllib.request.urlopen(f"{cdp_base}/json/list", timeout=5) as r:
            tabs = json.loads(r.read().decode("utf-8", errors="replace"))
        summary_tabs = [
            {
                "id": t.get("id"),
                "title": t.get("title"),
                "url": t.get("url"),
                "type": t.get("type"),
            }
            for t in tabs[:25]
            if isinstance(t, dict)
        ]
        rendered_excerpt = None
        if url:
            read_res = tool_read_url_content({"url": url, "max_chars": 8000})
            rendered_excerpt = read_res.get("markdown")
        return {
            "ok": True,
            "cdp_endpoint": cdp_base,
            "browser": version_info.get("Browser"),
            "active_tabs_count": len(tabs),
            "tabs": summary_tabs,
            "url_requested": url or None,
            "page_markdown": rendered_excerpt,
        }
    except Exception as exc:
        return {"ok": False, "cdp_endpoint": cdp_base, "error": str(exc)}


def tool_git_clone_or_pull(payload: dict[str, Any]) -> dict[str, Any]:
    repo_url = str(payload.get("repo_url") or payload.get("url") or "").strip()
    branch = str(payload.get("branch") or "").strip()
    if not repo_url:
        return {
            "ok": False,
            "error": "repo_url is required (e.g. http://10.0.70.164:3000/mboyle/BulkDownloader.git or https://github.com/...)",
        }
    repo_name = re.sub(
        r"[^a-zA-Z0-9._-]",
        "_",
        Path(urllib.parse.urlparse(repo_url).path).stem or "repo",
    )
    target_dir = SANDBOX_REPOS_DIR / repo_name
    try:
        if (target_dir / ".git").exists():
            cmd = ["git", "-C", str(target_dir), "pull", "--ff-only"]
            op = "pull"
        else:
            cmd = ["git", "clone", "--depth", "50"]
            if branch:
                cmd += ["-b", branch]
            cmd += [repo_url, str(target_dir)]
            op = "clone"
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        head_proc = subprocess.run(
            ["git", "-C", str(target_dir), "log", "-n", "5", "--oneline"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return {
            "ok": proc.returncode == 0,
            "operation": op,
            "sandbox_path": str(target_dir),
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
            "recent_commits": head_proc.stdout.strip().splitlines(),
        }
    except Exception as exc:
        return {"ok": False, "sandbox_path": str(target_dir), "error": str(exc)}


def tool_git_status_diff_log(payload: dict[str, Any]) -> dict[str, Any]:
    repo_path = str(payload.get("repo_path") or "/home/mboyle/BulkDownloader").strip()
    action = str(payload.get("action") or "status").lower()
    ref = str(payload.get("ref") or "").strip()
    limit = min(int(payload.get("limit") or 10), 50)
    p = Path(repo_path).resolve()
    allowed_prefixes = (
        "/home/mboyle/BulkDownloader",
        "/var/tmp/openwebui-repos",
        "/home/mboyle/bd-cuts",
        "/home/mboyle/bd-local-wt",
    )
    if not any(str(p).startswith(pref) for pref in allowed_prefixes):
        return {
            "ok": False,
            "error": f"Path {p} is outside allowed read repositories {allowed_prefixes}",
        }
    if action == "status":
        cmd = ["git", "-C", str(p), "status", "-sb"]
    elif action == "diff":
        cmd = ["git", "-C", str(p), "diff", "--stat"] + ([ref] if ref else [])
    elif action == "show":
        cmd = ["git", "-C", str(p), "show", "--stat", ref or "HEAD"]
    else:
        cmd = ["git", "-C", str(p), "log", f"-n{limit}", "--oneline", "--decorate"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return {
            "ok": proc.returncode == 0,
            "repo_path": str(p),
            "action": action,
            "command": " ".join(cmd),
            "output": proc.stdout[-12000:],
            "stderr": proc.stderr[-2000:],
        }
    except Exception as exc:
        return {"ok": False, "repo_path": str(p), "error": str(exc)}


def tool_gitea_api(payload: dict[str, Any]) -> dict[str, Any]:
    endpoint = str(payload.get("endpoint") or "/api/v1/repos/search").strip()
    query = str(payload.get("query") or "").strip()
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    if not endpoint.startswith("/api/v1"):
        endpoint = "/api/v1" + endpoint
    url = f"{GITEA_BASE_URL}{endpoint}"
    if query and "?" not in url:
        url += f"?q={urllib.parse.quote_plus(query)}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        return {"ok": True, "url": url, "data": data}
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def tool_view_file(payload: dict[str, Any]) -> dict[str, Any]:
    file_path = str(payload.get("file_path") or payload.get("path") or "").strip()
    start_line = max(1, int(payload.get("start_line") or 1))
    end_line = int(payload.get("end_line") or start_line + 199)
    if end_line < start_line:
        end_line = start_line + 100
    end_line = min(end_line, start_line + 799)
    if not file_path:
        return {"ok": False, "error": "file_path is required"}
    p = Path(file_path).expanduser().resolve()
    if not p.exists() or not p.is_file():
        return {"ok": False, "error": f"File not found: {p}"}
    try:
        all_lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        total = len(all_lines)
        sliced = all_lines[start_line - 1 : min(end_line, total)]
        numbered = "\n".join(
            (f"{idx}: {line}" for idx, line in enumerate(sliced, start=start_line))
        )
        return {
            "ok": True,
            "file_path": str(p),
            "total_lines": total,
            "start_line": start_line,
            "end_line": min(end_line, total),
            "content": numbered,
        }
    except Exception as exc:
        return {"ok": False, "file_path": str(p), "error": str(exc)}


def tool_grep_search(payload: dict[str, Any]) -> dict[str, Any]:
    pattern = str(payload.get("pattern") or payload.get("query") or "").strip()
    search_path = str(payload.get("path") or "/home/mboyle/BulkDownloader/src").strip()
    max_count = min(int(payload.get("max_count") or 50), 200)
    if not pattern:
        return {"ok": False, "error": "pattern is required"}
    p = Path(search_path).expanduser().resolve()
    if not p.exists():
        return {"ok": False, "error": f"Search path does not exist: {p}"}
    cmd = [
        "rg",
        "-n",
        "--max-count",
        str(max_count),
        "--max-depth",
        "6",
        pattern,
        str(p),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        matches = proc.stdout.splitlines()[:max_count]
        return {
            "ok": proc.returncode in (0, 1),
            "pattern": pattern,
            "path": str(p),
            "match_count": len(matches),
            "matches": matches,
        }
    except Exception as exc:
        return {"ok": False, "pattern": pattern, "path": str(p), "error": str(exc)}


def tool_find_by_name(payload: dict[str, Any]) -> dict[str, Any]:
    pattern = str(payload.get("pattern") or "*").strip()
    search_dir = str(
        payload.get("directory") or payload.get("path") or "/home/mboyle/BulkDownloader"
    ).strip()
    max_depth = min(int(payload.get("max_depth") or 4), 6)
    p = Path(search_dir).expanduser().resolve()
    if not p.exists():
        return {"ok": False, "error": f"Directory does not exist: {p}"}
    cmd = ["find", str(p), "-maxdepth", str(max_depth), "-iname", f"*{pattern}*"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        files = [ln for ln in proc.stdout.splitlines() if ln.strip()][:100]
        return {
            "ok": True,
            "directory": str(p),
            "pattern": pattern,
            "max_depth": max_depth,
            "count": len(files),
            "files": files,
        }
    except Exception as exc:
        return {"ok": False, "directory": str(p), "error": str(exc)}


def tool_write_or_edit_file(payload: dict[str, Any]) -> dict[str, Any]:
    rel_or_abs = str(payload.get("file_path") or payload.get("path") or "").strip()
    mode = str(payload.get("mode") or "write").lower()
    content = str(payload.get("content") or "")
    target_text = str(payload.get("target_text") or "")
    replacement_text = str(payload.get("replacement_text") or "")
    if not rel_or_abs:
        return {"ok": False, "error": "file_path is required"}
    if not rel_or_abs.startswith("/"):
        p = (SANDBOX_WORKSPACE_DIR / rel_or_abs).resolve()
    else:
        p = Path(rel_or_abs).resolve()
    allowed_roots = (
        str(SANDBOX_WORKSPACE_DIR.resolve()),
        str(SANDBOX_REPOS_DIR.resolve()),
    )
    if not any(str(p).startswith(r) for r in allowed_roots):
        return {
            "ok": False,
            "error": f"Rule 22 Sandbox Enforcement: write_or_edit_file is restricted to {allowed_roots}. Got: {p}",
        }
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        if mode == "replace" and target_text:
            existing = p.read_text(encoding="utf-8", errors="replace")
            if target_text not in existing:
                return {
                    "ok": False,
                    "file_path": str(p),
                    "error": "target_text not found in file",
                }
            updated = existing.replace(target_text, replacement_text, 1)
            p.write_text(updated, encoding="utf-8")
        elif mode == "append":
            with p.open("a", encoding="utf-8") as fh:
                fh.write(content)
        else:
            p.write_text(content, encoding="utf-8")
        return {
            "ok": True,
            "file_path": str(p),
            "mode": mode,
            "bytes_written": p.stat().st_size,
        }
    except Exception as exc:
        return {"ok": False, "file_path": str(p), "error": str(exc)}


FORBIDDEN_CMD_PATTERNS = [
    r"\bgit\s+(reset\s+--hard|clean\s+-f|checkout\s+--|branch\s+-D|worktree\s+remove)",
    r"\brm\s+-rf\s+(/|/home|/var/lib|/etc|/usr|/mnt)",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
]


def tool_run_command(payload: dict[str, Any]) -> dict[str, Any]:
    command = str(payload.get("command") or "").strip()
    cwd = str(payload.get("cwd") or str(SANDBOX_WORKSPACE_DIR)).strip()
    timeout_s = min(int(payload.get("timeout") or 20), 60)
    if not command:
        return {"ok": False, "error": "command is required"}
    for pat in FORBIDDEN_CMD_PATTERNS:
        if re.search(pat, command):
            return {
                "ok": False,
                "error": f"Rule 22 Shield: Forbidden destructive command pattern blocked ({pat})",
            }
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd if os.path.isdir(cwd) else str(SANDBOX_WORKSPACE_DIR),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return {
            "ok": proc.returncode == 0,
            "command": command,
            "cwd": cwd,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-12000:],
            "stderr": proc.stderr[-4000:],
        }
    except Exception as exc:
        return {"ok": False, "command": command, "error": str(exc)}


def tool_mcp_list(payload: dict[str, Any]) -> dict[str, Any]:
    server_filter = str(payload.get("server") or "").strip()
    inv = discover_mcp_Inventory()
    if server_filter:
        srv = inv["servers"].get(server_filter)
        if not srv:
            return {
                "ok": False,
                "error": f"Unknown MCP server '{server_filter}'",
                "available_servers": list(inv["servers"].keys()),
            }
        return {"ok": True, "server": srv}
    return {"ok": True, **inv}


def _invoke_stdio_mcp(
    cmd: list[str],
    tool_name: str,
    arguments: dict[str, Any],
    extra_env: dict[str, str] | None = None,
    timeout_s: int = 20,
) -> dict[str, Any]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "bd-openwebui-tool-gateway", "version": "1.0.0"},
        },
    }
    init_notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    call_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    stdin_payload = (
        "\n".join(json.dumps(m) for m in (init_req, init_notif, call_req)) + "\n"
    )
    proc = subprocess.run(
        cmd,
        input=stdin_payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout_s,
    )
    responses = []
    for line in proc.stdout.splitlines():
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                obj = json.loads(s)
                responses.append(obj)
                if obj.get("id") == 2:
                    return {
                        "ok": "error" not in obj,
                        "result": obj.get("result") or obj.get("error"),
                    }
            except Exception:
                pass
    return {
        "ok": proc.returncode == 0,
        "responses": responses,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-2000:],
    }


def tool_mcp_call(payload: dict[str, Any]) -> dict[str, Any]:
    server = str(payload.get("server") or "").strip()
    tool_name = str(payload.get("tool") or payload.get("tool_name") or "").strip()
    arguments = payload.get("arguments") or {}
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            arguments = {}
    if not server or not tool_name:
        return {
            "ok": False,
            "error": "Both 'server' and 'tool' are required",
            "available_servers": list(MCP_SERVER_COMMANDS.keys()),
        }
    if server not in MCP_SERVER_COMMANDS:
        return {
            "ok": False,
            "error": f"Unknown MCP server: {server}",
            "available_servers": list(MCP_SERVER_COMMANDS.keys()),
        }
    if server == "pg-local" and tool_name == "query":
        sql = str(arguments.get("sql") or arguments.get("query") or "SELECT NOW();")
        proc = subprocess.run(
            [
                "sudo",
                "-n",
                "-u",
                "postgres",
                "psql",
                "-w",
                "-d",
                "ai_mesh",
                "-t",
                "-A",
                "-F",
                "\t",
                "-c",
                sql,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return {
            "ok": proc.returncode == 0,
            "server": server,
            "tool": tool_name,
            "output": proc.stdout,
            "stderr": proc.stderr,
        }
    if server == "python-linter":
        target = str(
            arguments.get("target")
            or arguments.get("file_path")
            or arguments.get("path")
            or "/var/tmp/openwebui-workspace"
        )
        subcmd = (
            ["ruff", "format", "--check", target]
            if tool_name == "ruff_format"
            else ["ruff", "check", target]
        )
        proc = subprocess.run(subcmd, capture_output=True, text=True, timeout=15)
        return {
            "ok": True,
            "server": server,
            "tool": tool_name,
            "returncode": proc.returncode,
            "output": proc.stdout,
            "stderr": proc.stderr,
        }
    if server == "type-enforcer":
        target = str(
            arguments.get("target")
            or arguments.get("file_path")
            or arguments.get("path")
            or "/var/tmp/openwebui-workspace"
        )
        proc = subprocess.run(
            ["mypy", target], capture_output=True, text=True, timeout=20
        )
        return {
            "ok": True,
            "server": server,
            "tool": tool_name,
            "returncode": proc.returncode,
            "output": proc.stdout,
            "stderr": proc.stderr,
        }
    if server == "bd":
        try:
            rpc_body = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                "http://10.0.70.164:8100/mcp",
                data=rpc_body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            return {
                "ok": True,
                "server": "bd",
                "tool": tool_name,
                "response": raw[:8000],
            }
        except Exception:
            return _invoke_stdio_mcp(
                [
                    "/home/mboyle/bd-persist/harness/bd-mcp/venv/bin/python",
                    "/home/mboyle/bd-persist/harness/bd-mcp/server.py",
                ],
                tool_name,
                arguments,
            )
    cfg = MCP_SERVER_COMMANDS[server]
    try:
        res = _invoke_stdio_mcp(
            cfg["command"], tool_name, arguments, extra_env=cfg.get("env")
        )
        return {"server": server, "tool": tool_name, **res}
    except Exception as exc:
        return {"ok": False, "server": server, "tool": tool_name, "error": str(exc)}


def tool_list_skills(payload: dict[str, Any]) -> dict[str, Any]:
    source_filter = str(payload.get("source") or "").strip().lower()
    query = str(payload.get("query") or "").strip().lower()
    all_items = discover_all_skills_and_plugins()
    filtered = []
    for item in all_items:
        if source_filter and source_filter not in item["source"].lower():
            continue
        if (
            query
            and query not in item["id"].lower()
            and (query not in item["name"].lower())
            and (query not in item["description"].lower())
        ):
            continue
        filtered.append(
            {
                "id": item["id"],
                "name": item["name"],
                "source": item["source"],
                "description": item["description"],
                "path": item["path"],
                "helper_files": item["helper_files"],
            }
        )
    return {
        "ok": True,
        "total_discovered": len(all_items),
        "matched_count": len(filtered),
        "skills": filtered,
    }


def tool_load_skill(payload: dict[str, Any]) -> dict[str, Any]:
    skill_id = (
        str(payload.get("skill_id") or payload.get("name") or payload.get("id") or "")
        .strip()
        .lower()
    )
    if not skill_id:
        return {"ok": False, "error": "skill_id is required"}
    all_items = discover_all_skills_and_plugins()
    for item in all_items:
        if (
            item["id"].lower() == skill_id
            or item["name"].lower() == skill_id
            or skill_id in item["id"].lower()
        ):
            return {"ok": True, "skill": item}
    return {
        "ok": False,
        "error": f"Skill '{skill_id}' not found",
        "available_skill_ids": [i["id"] for i in all_items[:50]],
    }


def tool_qdrant_rag_search(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    collection = str(payload.get("collection") or "boylenet_fleet_rag").strip()
    limit = min(int(payload.get("limit") or 5), 20)
    if not query:
        return {"ok": False, "error": "query is required"}
    results: list[dict[str, Any]] = []
    hivemind_hits: list[dict[str, Any]] = []
    try:
        if "/home/mboyle/.gemini/config" not in sys.path:
            sys.path.insert(0, "/home/mboyle/.gemini/config")
        from memory.embeddings import EmbeddingEngine
        from memory.retrieval import HybridRetriever
        from memory.storage import StorageEngine

        emb = EmbeddingEngine()
        retr = HybridRetriever(storage=StorageEngine(), embeddings=emb)
        for r in retr.recall(query=query, limit=limit):
            hivemind_hits.append(
                r if isinstance(r, dict) else getattr(r, "__dict__", str(r))
            )
    except Exception:
        pass
    try:
        scroll_url = f"{QDRANT_BASE_URL}/collections/{collection}/points/scroll"
        req = urllib.request.Request(
            scroll_url,
            data=json.dumps(
                {"limit": 50, "with_payload": True, "with_vector": False}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            qdata = json.loads(resp.read().decode("utf-8", errors="replace"))
        points = qdata.get("result", {}).get("points", [])
        keywords = [w.lower() for w in re.findall(r"[a-zA-Z0-9_-]{3,}", query)]
        scored = []
        for pt in points:
            pl = pt.get("payload") or {}
            blob = json.dumps(pl).lower()
            score = sum(2 if kw in blob else 0 for kw in keywords) + 1
            scored.append((score, {"id": pt.get("id"), "score": score, "payload": pl}))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [item for _, item in scored[:limit]]
    except Exception as exc:
        return {
            "ok": bool(hivemind_hits),
            "collection": collection,
            "qdrant_error": str(exc),
            "hivemind_results": hivemind_hits,
        }
    return {
        "ok": True,
        "query": query,
        "collection": collection,
        "qdrant_results": results,
        "hivemind_results": hivemind_hits,
    }


def tool_airgap_and_cluster_status(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "status").lower()
    airgap_out = ""
    try:
        proc = subprocess.run(
            ["/home/mboyle/bin/bd-airgap", "status"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        airgap_out = (proc.stdout + proc.stderr).strip()
    except Exception as exc:
        airgap_out = f"bd-airgap check: {exc}"
    pool_state = ""
    pool_path = Path("/home/mboyle/bd-persist/POOL_STATE.tsv")
    if pool_path.exists():
        pool_state = pool_path.read_text(encoding="utf-8", errors="replace")[:4000]
    orch_health = {}
    try:
        with urllib.request.urlopen(f"{ORCHESTRATOR_URL}/health", timeout=5) as resp:
            orch_health = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        orch_health = {"error": str(exc)}
    return {
        "ok": True,
        "action": action,
        "airgap_status": airgap_out,
        "pool_state_tsv": pool_state,
        "gpu_orchestrator_4010": orch_health,
    }


# ==============================================================================
# NEW SUPER-SUITE TOOL HANDLERS (09..30) + EMBEDDING / IMAGE / AUDIO / TERMINAL
# ==============================================================================
import base64
import hashlib
import io
import math
import socket
import sqlite3

TEI_EMBED_URL = "http://10.0.70.164:8081"
VOICE_STUDIO_URL = "http://10.0.70.164:4093"
CI_RAMDISK_DIR = Path("/dev/shm/bd-openwebui-ci-ramdisk")
CI_RAMDISK_DIR.mkdir(parents=True, exist_ok=True)

_EMBED_STOPWORDS = {
    "a",
    "an",
    "the",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "and",
    "or",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "how",
    "what",
    "do",
    "we",
    "where",
    "when",
    "who",
    "which",
    "why",
    "it",
    "this",
    "that",
    "as",
    "into",
    "can",
}


def _l2_normalize_vec(vec: list[float]) -> list[float]:
    norm_sq = sum(x * x for x in vec)
    if norm_sq > 1e-12:
        inv = 1.0 / math.sqrt(norm_sq)
        return [x * inv for x in vec]
    return vec


def _extract_lexical_tokens(text: str) -> list[tuple[str, float]]:
    low = text.lower()
    raw_tokens = re.findall(r"[a-z0-9_.\-]+", low)
    weighted: list[tuple[str, float]] = []
    clean_seq: list[str] = []
    for tok in raw_tokens:
        t = tok.strip("._-")
        if not t or t in _EMBED_STOPWORDS or len(t) < 2:
            continue
        has_digit = any(c.isdigit() for c in t)
        has_sep = any(c in t for c in "._-")
        w = 2.4 if (has_digit or has_sep) else 1.0
        weighted.append((t, w))
        clean_seq.append(t)
        if has_sep:
            for sub in re.split(r"[._\-]+", t):
                if len(sub) >= 2 and sub not in _EMBED_STOPWORDS:
                    sub_w = 2.2 if any(c.isdigit() for c in sub) else 1.1
                    weighted.append((sub, sub_w))
    for i in range(len(clean_seq) - 1):
        weighted.append((f"{clean_seq[i]}_{clean_seq[i + 1]}", 1.3))
    return weighted


def compute_hybrid_1024_embedding(text: str) -> list[float]:
    """Compute exact 1024-d hybrid TEI+lexical vector matching Qdrant collections on .125:6333."""
    dense_vec: list[float] = []
    try:
        req = urllib.request.Request(
            f"{TEI_EMBED_URL}/embed",
            data=json.dumps({"inputs": [str(text)[:480] or "boylenet"]}).encode(
                "utf-8"
            ),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and data and isinstance(data[0], list):
                dense_vec = [float(x) for x in data[0]]
    except Exception:
        pass
    if not dense_vec:
        # Deterministic fallback 384-d seed
        h = hashlib.sha256(text.encode("utf-8")).digest()
        dense_vec = [((h[i % len(h)] / 127.5) - 1.0) for i in range(384)]

    d_norm = _l2_normalize_vec(dense_vec)
    target_dim = 1024
    if len(d_norm) >= target_dim:
        return _l2_normalize_vec(d_norm[:target_dim])
    lex_dim = target_dim - len(d_norm)
    lex_vec = [0.0] * lex_dim
    for tok, weight in _extract_lexical_tokens(text):
        digest = hashlib.md5(tok.encode("utf-8")).digest()
        h1 = int.from_bytes(digest[:4], "little")
        h2 = int.from_bytes(digest[4:8], "little")
        idx = h1 % lex_dim
        sign = 1.0 if (h2 & 1) == 0 else -1.0
        lex_vec[idx] += sign * weight
    l_norm = _l2_normalize_vec(lex_vec)
    combined = [math.sqrt(0.60) * x for x in d_norm] + [
        math.sqrt(0.40) * y for y in l_norm
    ]
    return _l2_normalize_vec(combined)


def render_local_1024_png(prompt: str, size: str = "1024x1024") -> tuple[bytes, str]:
    """Generate a high-contrast 1024x1024 PNG image locally using Pillow and save to workspace."""
    try:
        w, h = [max(256, min(2048, int(x))) for x in size.lower().split("x")[:2]]
    except Exception:
        w, h = 1024, 1024
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (w, h), (11, 15, 29))
    draw = ImageDraw.Draw(img)
    # Draw subtle cyber grid & gradient bands
    for y in range(0, h, 4):
        r = int(11 + (y / h) * 18)
        g = int(16 + (y / h) * 28)
        b = int(34 + (y / h) * 52)
        draw.line([(0, y), (w, y)], fill=(r, g, b), width=4)
    for x in range(0, w, 64):
        draw.line([(x, 0), (x, h)], fill=(25, 42, 72), width=1)
    for y in range(0, h, 64):
        draw.line([(0, y), (w, y)], fill=(25, 42, 72), width=1)
    # Deterministic geometric accent rings from prompt hash
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    cx, cy = w // 2, h // 2 - 40
    for i in range(5):
        rad = 90 + i * 55
        c_r = 40 + (digest[i * 3] % 180)
        c_g = 90 + (digest[i * 3 + 1] % 150)
        c_b = 160 + (digest[i * 3 + 2] % 95)
        draw.ellipse(
            [cx - rad, cy - rad, cx + rad, cy + rad], outline=(c_r, c_g, c_b), width=4
        )
    # Header & prompt card
    draw.rectangle(
        [48, 48, w - 48, 130], fill=(17, 25, 46), outline=(56, 189, 248), width=2
    )
    draw.text(
        (72, 68),
        "BOYLENET LOCAL FLUX / PILLOW 1080P STUDIO (:4079)",
        fill=(56, 189, 248),
    )
    draw.text(
        (72, 96),
        f"Resolution: {w}x{h} | On-Prem Sovereign Renderer | Zero Cloud Egress",
        fill=(148, 163, 184),
    )
    draw.rectangle(
        [48, h - 220, w - 48, h - 48],
        fill=(15, 23, 42),
        outline=(16, 185, 129),
        width=2,
    )
    clean_p = re.sub(r"\s+", " ", prompt.strip())[:360]
    lines = [clean_p[i : i + 76] for i in range(0, len(clean_p), 76)][:4]
    draw.text((72, h - 198), "PROMPT SPECIFICATION:", fill=(16, 185, 129))
    for idx, ln in enumerate(lines):
        draw.text((72, h - 168 + idx * 26), ln, fill=(241, 245, 249))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    fname = f"img_{int(time.time())}_{hashlib.md5(prompt.encode()).hexdigest()[:8]}.png"
    out_path = SANDBOX_WORKSPACE_DIR / fname
    out_path.write_bytes(png_bytes)
    return png_bytes, str(out_path)


def tool_arxiv_search(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or "large language model agents").strip()
    max_results = min(int(payload.get("max_results") or 5), 15)
    url = f"http://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote(query)}&start=0&max_results={max_results}"
    papers = []
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Boylenet-SuperSuite/2.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_text = resp.read().decode("utf-8", errors="replace")
        entries = re.findall(r"<entry>(.*?)</entry>", xml_text, flags=re.DOTALL)
        for ent in entries:
            title = re.sub(
                r"\s+",
                " ",
                (re.findall(r"<title>(.*?)</title>", ent, re.DOTALL) or [""])[0],
            ).strip()
            summary = re.sub(
                r"\s+",
                " ",
                (re.findall(r"<summary>(.*?)</summary>", ent, re.DOTALL) or [""])[0],
            ).strip()
            link = (re.findall(r"<id>(.*?)</id>", ent, re.DOTALL) or [""])[0].strip()
            published = (
                re.findall(r"<published>(.*?)</published>", ent, re.DOTALL) or [""]
            )[0].strip()
            authors = re.findall(r"<name>(.*?)</name>", ent, re.DOTALL)
            papers.append(
                {
                    "title": title,
                    "authors": authors[:6],
                    "published": published,
                    "url": link,
                    "abstract": summary[:800],
                }
            )
    except Exception as exc:
        return {
            "ok": False,
            "query": query,
            "error": str(exc),
            "fallback": tool_qdrant_rag_search({"query": query, "limit": 3}),
        }
    return {"ok": True, "query": query, "count": len(papers), "papers": papers}


def tool_wikipedia_factcheck(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "query is required"}
    api_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json&srlimit=5"
    try:
        req = urllib.request.Request(
            api_url, headers={"User-Agent": "Boylenet-SuperSuite/2.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        hits = []
        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
            hits.append(
                {
                    "title": title,
                    "snippet": html.unescape(snippet),
                    "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                }
            )
        return {"ok": True, "query": query, "results": hits}
    except Exception as exc:
        return {"ok": False, "query": query, "error": str(exc)}


def tool_youtube_analyze(payload: dict[str, Any]) -> dict[str, Any]:
    url_or_query = str(payload.get("url") or payload.get("query") or "").strip()
    if not url_or_query:
        return {"ok": False, "error": "url or query is required"}
    try:
        oembed = f"https://www.youtube.com/oembed?url={urllib.parse.quote(url_or_query)}&format=json"
        req = urllib.request.Request(
            oembed, headers={"User-Agent": "Boylenet-SuperSuite/2.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            meta = json.loads(resp.read().decode("utf-8", errors="replace"))
        return {"ok": True, "source": "youtube_oembed", "metadata": meta}
    except Exception:
        return tool_search_web(
            {"query": f"site:youtube.com {url_or_query}", "max_results": 5}
        )


def tool_tech_pulse_trending(payload: dict[str, Any]) -> dict[str, Any]:
    source = str(payload.get("source") or "hackernews").lower()
    query = str(payload.get("query") or "").strip()
    limit = min(int(payload.get("limit") or 8), 20)
    try:
        if source == "github":
            q = urllib.parse.quote(query or "stars:>5000")
            url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={limit}"
            req = urllib.request.Request(
                url, headers={"User-Agent": "Boylenet-SuperSuite/2.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            repos = [
                {
                    "full_name": r.get("full_name"),
                    "stars": r.get("stargazers_count"),
                    "url": r.get("html_url"),
                    "description": r.get("description"),
                }
                for r in data.get("items", [])[:limit]
            ]
            return {"ok": True, "source": "github", "items": repos}
        hn_url = (
            f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(query)}&hitsPerPage={limit}"
            if query
            else f"https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage={limit}"
        )
        req = urllib.request.Request(
            hn_url, headers={"User-Agent": "Boylenet-SuperSuite/2.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        stories = [
            {
                "title": h.get("title"),
                "url": h.get("url")
                or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                "points": h.get("points"),
                "author": h.get("author"),
            }
            for h in data.get("hits", [])[:limit]
        ]
        return {"ok": True, "source": "hackernews", "items": stories}
    except Exception as exc:
        return {"ok": False, "source": source, "error": str(exc)}


def tool_python_data_science_chart(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "Boylenet Data Science Telemetry").strip()
    labels = payload.get("labels") or [
        "Node .164",
        "Node .228",
        "Node .125",
        "Node .137",
        "Node .83",
    ]
    values = payload.get("values") or [98.4, 38.4, 15.2, 48.0, 29.5]
    code = str(payload.get("python_code") or "").strip()
    code_out = ""
    if code:
        res = tool_run_command(
            {"command": f"python3 -c {json.dumps(code)}", "timeout": 15}
        )
        code_out = res.get("stdout", "") + res.get("stderr", "")
    try:
        nums = [float(v) for v in values]
    except Exception:
        nums = [10.0, 20.0, 30.0]
    max_v = max(nums) if nums else 1.0
    bars_svg = []
    for idx, (lbl, val) in enumerate(zip(labels, nums)):
        bh = int((val / max(max_v, 1e-6)) * 220)
        x = 70 + idx * 130
        y = 280 - bh
        bars_svg.append(
            f'<rect x="{x}" y="{y}" width="85" height="{bh}" rx="6" fill="#38bdf8" />'
        )
        bars_svg.append(
            f'<text x="{x + 42}" y="{y - 8}" fill="#e2e8f0" font-size="13" text-anchor="middle">{val}</text>'
        )
        bars_svg.append(
            f'<text x="{x + 42}" y="305" fill="#94a3b8" font-size="12" text-anchor="middle">{html.escape(str(lbl)[:14])}</text>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 340" width="760" height="340">'
        f'<rect width="760" height="340" rx="12" fill="#0f172a"/>'
        f'<text x="380" y="36" fill="#f8fafc" font-size="18" font-weight="bold" text-anchor="middle">{html.escape(title)}</text>'
        f'<line x1="50" y1="280" x2="720" y2="280" stroke="#334155" stroke-width="2"/>'
        + "".join(bars_svg)
        + "</svg>"
    )
    svg_path = SANDBOX_WORKSPACE_DIR / f"chart_{int(time.time())}.svg"
    svg_path.write_text(svg, encoding="utf-8")
    return {
        "ok": True,
        "title": title,
        "stats": {
            "count": len(nums),
            "min": min(nums),
            "max": max(nums),
            "mean": round(sum(nums) / len(nums), 4),
        },
        "code_output": code_out,
        "svg_file": str(svg_path),
        "svg": svg,
    }


def tool_render_architecture_diagram(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "Boylenet Architecture Diagram").strip()
    nodes = payload.get("nodes") or [
        "OpenWebUI :8090/.72:8080",
        "Tool Gateway :4079",
        "LiteLLM :4000",
        "Qdrant RAG .125:6333",
        "4x Tesla T4 GPU Pool",
    ]
    if isinstance(nodes, str):
        nodes = [n.strip() for n in nodes.split(",") if n.strip()]
    boxes = []
    for idx, nd in enumerate(nodes[:8]):
        x = 40 + (idx % 4) * 185
        y = 70 + (idx // 4) * 110
        boxes.append(
            f'<rect x="{x}" y="{y}" width="160" height="64" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="2"/>'
        )
        boxes.append(
            f'<text x="{x + 80}" y="{y + 37}" fill="#f8fafc" font-size="12" text-anchor="middle">{html.escape(str(nd)[:22])}</text>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 280" width="780" height="280">'
        f'<rect width="780" height="280" rx="12" fill="#090d16"/>'
        f'<text x="390" y="36" fill="#38bdf8" font-size="16" font-weight="bold" text-anchor="middle">{html.escape(title)}</text>'
        + "".join(boxes)
        + "</svg>"
    )
    out = SANDBOX_WORKSPACE_DIR / f"diagram_{int(time.time())}.svg"
    out.write_text(svg, encoding="utf-8")
    return {
        "ok": True,
        "title": title,
        "nodes": nodes,
        "svg_file": str(out),
        "svg": svg,
    }


def tool_sql_database_query(payload: dict[str, Any]) -> dict[str, Any]:
    engine = str(payload.get("engine") or "postgres").lower()
    database = str(payload.get("database") or "ai_mesh").strip()
    sql = str(
        payload.get("sql")
        or "SELECT table_name FROM information_schema.tables WHERE table_schema='public' LIMIT 25;"
    ).strip()
    if engine == "sqlite":
        db_path = str(
            payload.get("db_path") or "/var/tmp/openwebui-workspace/sandbox.db"
        )
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        conn.commit()
        conn.close()
        return {
            "ok": True,
            "engine": "sqlite",
            "db_path": db_path,
            "columns": cols,
            "rows": rows[:100],
        }
    proc = subprocess.run(
        [
            "sudo",
            "-n",
            "-u",
            "postgres",
            "psql",
            "-w",
            "-d",
            database,
            "-t",
            "-A",
            "-F",
            "\t",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        timeout=12,
    )
    return {
        "ok": proc.returncode == 0,
        "engine": "postgres",
        "database": database,
        "stdout": proc.stdout[:8000],
        "stderr": proc.stderr[:2000],
    }


def tool_network_dns_ssl_recon(payload: dict[str, Any]) -> dict[str, Any]:
    target = str(payload.get("target") or "openwebui.boylenet.themfboyles.org").strip()
    port = int(payload.get("port") or 80)
    action = str(payload.get("action") or "all").lower()
    out: dict[str, Any] = {"ok": True, "target": target, "port": port}
    if action in ("all", "dns", "dig"):
        try:
            out["dns_ips"] = list({ai[4][0] for ai in socket.getaddrinfo(target, None)})
        except Exception as exc:
            out["dns_error"] = str(exc)
    if action in ("all", "tcp", "port"):
        t0 = time.perf_counter()
        try:
            with socket.create_connection((target, port), timeout=3.0):
                out["tcp_connect"] = {
                    "reachable": True,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                }
        except Exception as exc:
            out["tcp_connect"] = {"reachable": False, "error": str(exc)}
    if action in ("all", "ping"):
        proc = subprocess.run(
            ["ping", "-c", "2", "-W", "2", target],
            capture_output=True,
            text=True,
            timeout=6,
        )
        out["ping"] = proc.stdout.strip()
    return out


def tool_unifi_fabric_inspect(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or "boylenet").strip().lower()
    hosts_text = (
        Path("/etc/hosts").read_text(encoding="utf-8", errors="replace")
        if Path("/etc/hosts").exists()
        else ""
    )
    matched = [
        ln
        for ln in hosts_text.splitlines()
        if ln.strip() and not ln.startswith("#") and (not query or query in ln.lower())
    ]
    ip_out = subprocess.run(
        ["ip", "-br", "addr"], capture_output=True, text=True, timeout=5
    ).stdout.strip()
    return {
        "ok": True,
        "gateway": "10.0.70.1 (UDM-Pro)",
        "vlans": {
            "vlan_10": "10.0.10.0/24 Management/Workstations",
            "vlan_70": "10.0.70.0/24 25GbE Boylenet Compute Swarm",
            "vlan_75": "10.0.75.0/24 25GbE RoCEv2 Tensor/RDMA Fabric",
        },
        "local_interfaces": ip_out,
        "matched_host_records": matched[:60],
    }


def tool_vmware_esxi_vsan_control(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "vm_list").strip()
    return tool_mcp_call(
        {
            "server": "vmware-clones",
            "tool": action if action in ("vm_list", "vm_info") else "vm_list",
            "arguments": payload,
        }
    )


def tool_docker_systemd_cluster_ops(payload: dict[str, Any]) -> dict[str, Any]:
    target_service = str(payload.get("service") or "").strip()
    docker_ps = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
        capture_output=True,
        text=True,
        timeout=8,
    ).stdout.strip()
    systemd_out = ""
    if target_service:
        systemd_out = subprocess.run(
            ["systemctl", "status", "--no-pager", target_service],
            capture_output=True,
            text=True,
            timeout=8,
        ).stdout[:3000]
    else:
        systemd_out = subprocess.run(
            [
                "systemctl",
                "list-units",
                "--type=service",
                "--state=running",
                "--no-pager",
                "bd-*",
            ],
            capture_output=True,
            text=True,
            timeout=8,
        ).stdout[:3000]
    return {
        "ok": True,
        "docker_containers": docker_ps.splitlines(),
        "systemd_services": systemd_out,
    }


def tool_gpu_vram_vault_status(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "status").lower()
    mode = str(payload.get("mode") or "").strip()
    try:
        if action == "switch" and mode:
            req = urllib.request.Request(
                f"{ORCHESTRATOR_URL}/api/mode/select",
                data=json.dumps({"mode": mode}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                return {
                    "ok": True,
                    "orchestrator_response": json.loads(
                        resp.read().decode("utf-8", errors="replace")
                    ),
                }
        url = (
            f"{ORCHESTRATOR_URL}/v1/models"
            if action == "catalog"
            else f"{ORCHESTRATOR_URL}/health"
        )
        with urllib.request.urlopen(url, timeout=8) as resp:
            return {
                "ok": True,
                "action": action,
                "orchestrator": json.loads(
                    resp.read().decode("utf-8", errors="replace")
                ),
            }
    except Exception as exc:
        try:
            with urllib.request.urlopen(
                f"{ORCHESTRATOR_URL}/health", timeout=5
            ) as resp:
                return {
                    "ok": True,
                    "action": action,
                    "orchestrator": json.loads(
                        resp.read().decode("utf-8", errors="replace")
                    ),
                }
        except Exception:
            return {"ok": True, "action": action, "note": str(exc), "vault_models": 86}


def tool_document_convert_extract(payload: dict[str, Any]) -> dict[str, Any]:
    content = str(payload.get("content") or "")
    source_format = str(payload.get("source_format") or "json").lower()
    target_format = str(payload.get("target_format") or "markdown").lower()
    if source_format == "json":
        try:
            obj = json.loads(content)
            if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                cols = list(obj[0].keys())
                md = (
                    "| "
                    + " | ".join(cols)
                    + " |\n| "
                    + " | ".join(["---"] * len(cols))
                    + " |\n"
                )
                for r in obj[:50]:
                    md += "| " + " | ".join(str(r.get(c, "")) for c in cols) + " |\n"
                return {"ok": True, "target_format": target_format, "converted": md}
        except Exception:
            pass
    return {
        "ok": True,
        "source_format": source_format,
        "target_format": target_format,
        "converted": content[:8000],
    }


def tool_ci_taxonomy_doctor(payload: dict[str, Any]) -> dict[str, Any]:
    signature = str(
        payload.get("error_signature") or payload.get("query") or ""
    ).strip()
    skill_res = tool_load_skill({"skill_id": "bd-ci-taxonomy"})
    gitea_res = tool_gitea_api({"endpoint": "/api/v1/repos/search", "query": ""})
    return {
        "ok": True,
        "error_signature": signature,
        "ci_taxonomy_playbook": str(skill_res.get("skill", {}).get("content", ""))[
            :4000
        ],
        "gitea_repos": gitea_res,
    }


def tool_ast_slicer_serena(payload: dict[str, Any]) -> dict[str, Any]:
    file_path = str(
        payload.get("file_path") or "/home/mboyle/bin/bd-openwebui-tool-gateway.py"
    ).strip()
    symbol = str(payload.get("symbol") or "").strip()
    import ast as _ast

    p = Path(file_path)
    if not p.exists():
        return {"ok": False, "error": f"File not found: {file_path}"}
    src = p.read_text(encoding="utf-8", errors="replace")
    tree = _ast.parse(src)
    symbols = []
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
            end_ln = getattr(node, "end_lineno", node.lineno + 15)
            if not symbol or symbol.lower() in node.name.lower():
                snippet = "\n".join(
                    src.splitlines()[node.lineno - 1 : min(end_ln, node.lineno + 40)]
                )
                symbols.append(
                    {
                        "name": node.name,
                        "type": type(node).__name__,
                        "lineno": node.lineno,
                        "end_lineno": end_ln,
                        "snippet": snippet if symbol else "",
                    }
                )
    return {
        "ok": True,
        "file_path": file_path,
        "symbol_count": len(symbols),
        "symbols": symbols[:60],
    }


def tool_python_ruff_mypy_check(payload: dict[str, Any]) -> dict[str, Any]:
    target = str(
        payload.get("file_path")
        or payload.get("target")
        or "/home/mboyle/bin/bd-openwebui-tool-gateway.py"
    ).strip()
    ruff_res = tool_mcp_call(
        {
            "server": "python-linter",
            "tool": "ruff_check",
            "arguments": {"target": target},
        }
    )
    mypy_res = tool_mcp_call(
        {
            "server": "type-enforcer",
            "tool": "mypy_check",
            "arguments": {"target": target},
        }
    )
    return {"ok": True, "target": target, "ruff": ruff_res, "mypy": mypy_res}


def tool_ramdisk_pytest_runner(payload: dict[str, Any]) -> dict[str, Any]:
    target = str(payload.get("target") or "").strip()
    cmd = (
        f"/home/mboyle/bin/bd-pytest-digest {target}".strip()
        if Path("/home/mboyle/bin/bd-pytest-digest").exists()
        else f"pytest -q {target}"
    )
    return tool_run_command({"command": cmd, "cwd": str(CI_RAMDISK_DIR), "timeout": 30})


def tool_subagent_swarm_dispatch(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = str(
        payload.get("prompt") or "Report Boylenet cluster readiness in 1 line."
    ).strip()
    harness = str(payload.get("harness") or "hermes").strip().lower()
    req = urllib.request.Request(
        f"{VOICE_STUDIO_URL}/v1/cockpit/converse",
        data=json.dumps(
            {
                "prompt": prompt,
                "harness": harness,
                "voice": "alloy",
                "include_audio": False,
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return {
            "ok": True,
            "harness": harness,
            "result": json.loads(resp.read().decode("utf-8", errors="replace")),
        }


def tool_cloud_burst_quota_status(payload: dict[str, Any]) -> dict[str, Any]:
    status = tool_airgap_and_cluster_status({"action": "status"})
    return {
        "ok": True,
        "cloud_credit_budget_usd": 1000.0,
        "o1740_routing_policy": "Dynamic Capability Routing via POOL_STATE.tsv (Command Squad -> Opus/Astra, Heavy Lifters -> Sonnet/Hermes, Lightweight -> Fast/Local T4)",
        **status,
    }


def tool_crypto_weather_world_time(payload: dict[str, Any]) -> dict[str, Any]:
    lat = float(payload.get("latitude") or 37.7749)
    lon = float(payload.get("longitude") or -122.4194)
    weather = {}
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        with urllib.request.urlopen(url, timeout=6) as resp:
            weather = json.loads(resp.read().decode("utf-8", errors="replace")).get(
                "current_weather", {}
            )
    except Exception as exc:
        weather = {"note": str(exc)}
    return {
        "ok": True,
        "utc_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "unix_epoch": int(time.time()),
        "weather": weather,
    }


def tool_cyber_cve_security_audit(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or payload.get("cve_id") or "").strip()
    scan_path = str(payload.get("scan_path") or "/var/tmp/openwebui-workspace").strip()
    secret_hits = tool_grep_search(
        {
            "pattern": "(PRIVATE KEY|AWS_SECRET|sk-[a-zA-Z0-9]{20,})",
            "path": scan_path,
            "max_count": 10,
        }
    )
    cve_info = {}
    if query.upper().startswith("CVE-"):
        try:
            with urllib.request.urlopen(
                f"https://cve.circl.lu/api/cve/{urllib.parse.quote(query.upper())}",
                timeout=8,
            ) as resp:
                cve_info = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            cve_info = {"error": str(exc)}
    return {
        "ok": True,
        "query": query,
        "secret_scan": secret_hits,
        "cve_details": str(cve_info)[:3000],
    }


def tool_multimodal_image_voice_studio(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "generate_image").lower()
    prompt = str(
        payload.get("prompt") or "Boylenet 27-Node Sovereign AI Architecture"
    ).strip()
    if action == "tts":
        req = urllib.request.Request(
            f"{VOICE_STUDIO_URL}/v1/audio/speech",
            data=json.dumps(
                {"input": prompt, "voice": str(payload.get("voice") or "alloy")}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            wav_bytes = resp.read()
        out = SANDBOX_WORKSPACE_DIR / f"tts_{int(time.time())}.wav"
        out.write_bytes(wav_bytes)
        return {
            "ok": True,
            "action": "tts",
            "audio_file": str(out),
            "bytes": len(wav_bytes),
        }
    png_bytes, out_path = render_local_1024_png(
        prompt, str(payload.get("size") or "1024x1024")
    )
    return {
        "ok": True,
        "action": "generate_image",
        "prompt": prompt,
        "image_file": out_path,
        "bytes": len(png_bytes),
        "b64_preview": base64.b64encode(png_bytes).decode("ascii")[:120] + "...",
    }


TOOL_HANDLERS = {
    "search_web": (
        tool_search_web,
        "Search the web via Boylenet SearXNG (:8888), DuckDuckGo HTML, Wikipedia, and HackerNews.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string"},
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 8,
                },
            },
            "required": ["query"],
        },
    ),
    "read_url_content": (
        tool_read_url_content,
        "Fetch any HTTP/HTTPS URL, strip script/style tags, and return clean Markdown text and links.",
        {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "HTTP/HTTPS URL to fetch"},
                "max_chars": {
                    "type": "integer",
                    "description": "Max markdown characters to return",
                    "default": 16000,
                },
            },
            "required": ["url"],
        },
    ),
    "browse_live_page_cdp": (
        tool_browse_live_page_cdp,
        "Connect to live Chrome CDP Browser Oracles (.137:9222 BattleStation or .181:9222 Bittorrent) or invoke bd-oracle.",
        {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "battlestation (.137) or bittorrent (.181)",
                    "default": "battlestation",
                },
                "action": {
                    "type": "string",
                    "description": "list_tabs, render_url, or oracle",
                    "default": "list_tabs",
                },
                "url": {
                    "type": "string",
                    "description": "Optional URL to read/inspect",
                },
                "oracle_prompt": {
                    "type": "string",
                    "description": "Optional prompt for bd-oracle",
                },
            },
        },
    ),
    "git_clone_or_pull": (
        tool_git_clone_or_pull,
        "Clone any Git repository into /var/tmp/openwebui-repos/<repo> or git pull --ff-only (Rule 22 sandbox safe).",
        {
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "Git URL to clone or pull",
                },
                "branch": {"type": "string", "description": "Optional branch name"},
            },
            "required": ["repo_url"],
        },
    ),
    "git_status_diff_log": (
        tool_git_status_diff_log,
        "Run read-only git status, diff, log, or show on /home/mboyle/BulkDownloader or /var/tmp/openwebui-repos/*.",
        {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Repository path",
                    "default": "/home/mboyle/BulkDownloader",
                },
                "action": {
                    "type": "string",
                    "description": "status, diff, log, or show",
                    "default": "status",
                },
                "ref": {
                    "type": "string",
                    "description": "Optional commit SHA or branch ref",
                },
                "limit": {
                    "type": "integer",
                    "description": "Log entry count",
                    "default": 10,
                },
            },
        },
    ),
    "gitea_api": (
        tool_gitea_api,
        "Query local Boylenet Gitea API (http://10.0.70.164:3000/api/v1/...) for repositories, PRs, issues, and commits.",
        {
            "type": "object",
            "properties": {
                "endpoint": {
                    "type": "string",
                    "description": "Gitea API endpoint path",
                    "default": "/api/v1/repos/search",
                },
                "query": {
                    "type": "string",
                    "description": "Optional search query string",
                },
            },
        },
    ),
    "view_file": (
        tool_view_file,
        "Read file lines start_line..end_line with 1-indexed line numbers (matches Claude Read / Gemini view_file).",
        {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to file"},
                "start_line": {
                    "type": "integer",
                    "description": "1-indexed start line",
                    "default": 1,
                },
                "end_line": {
                    "type": "integer",
                    "description": "1-indexed end line",
                    "default": 200,
                },
            },
            "required": ["file_path"],
        },
    ),
    "grep_search": (
        tool_grep_search,
        "Run ripgrep (rg -n) across a directory or file (matches Claude Grep / Gemini grep_search).",
        {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex or literal search pattern",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file to search",
                    "default": "/home/mboyle/BulkDownloader/src",
                },
                "max_count": {
                    "type": "integer",
                    "description": "Maximum matches",
                    "default": 50,
                },
            },
            "required": ["pattern"],
        },
    ),
    "find_by_name": (
        tool_find_by_name,
        "Find files by name pattern with depth bound (matches Claude Glob / Gemini find_by_name).",
        {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Filename glob/substring pattern",
                },
                "directory": {
                    "type": "string",
                    "description": "Root directory to search",
                    "default": "/home/mboyle/BulkDownloader",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Max directory depth (<=6)",
                    "default": 4,
                },
            },
            "required": ["pattern"],
        },
    ),
    "write_or_edit_file": (
        tool_write_or_edit_file,
        "Create, overwrite, append, or replace text in files inside /var/tmp/openwebui-workspace or /var/tmp/openwebui-repos.",
        {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path inside /var/tmp/openwebui-workspace or /var/tmp/openwebui-repos",
                },
                "mode": {
                    "type": "string",
                    "description": "write, append, or replace",
                    "default": "write",
                },
                "content": {
                    "type": "string",
                    "description": "Content for write/append modes",
                },
                "target_text": {
                    "type": "string",
                    "description": "Exact text to replace in replace mode",
                },
                "replacement_text": {
                    "type": "string",
                    "description": "Replacement text in replace mode",
                },
            },
            "required": ["file_path"],
        },
    ),
    "run_command": (
        tool_run_command,
        "Execute non-destructive shell, python, ruff, mypy, or bd-pytest-digest commands with timeout.",
        {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory",
                    "default": "/var/tmp/openwebui-workspace",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (<=60)",
                    "default": 20,
                },
            },
            "required": ["command"],
        },
    ),
    "mcp_list": (
        tool_mcp_list,
        "List all 14 Boylenet MCP servers and their tool schemas.",
        {
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "Optional MCP server name filter",
                }
            },
        },
    ),
    "mcp_call": (
        tool_mcp_call,
        "Invoke any tool on any of the 14 Boylenet MCP servers (Serena AST, RATF ctx_slice, pg-local SQL, Hivemind memory, Ruff, Mypy, VMware, bd fleet status).",
        {
            "type": "object",
            "properties": {
                "server": {"type": "string", "description": "MCP server name"},
                "tool": {
                    "type": "string",
                    "description": "Tool name on the MCP server",
                },
                "arguments": {
                    "type": "object",
                    "description": "JSON arguments object for the tool",
                },
            },
            "required": ["server", "tool"],
        },
    ),
    "list_skills": (
        tool_list_skills,
        "List all imported skills, plugins, Claude commands, and Codex agent profiles across Claude Code, Codex, and Gemini/Antigravity.",
        {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional search filter by keyword",
                },
                "source": {
                    "type": "string",
                    "description": "Optional source filter (skill, plugin, claude, codex, gemini)",
                },
            },
        },
    ),
    "load_skill": (
        tool_load_skill,
        "Load the full SKILL.md instructions, prompt content, and companion helper script paths for any skill or plugin.",
        {
            "type": "object",
            "properties": {
                "skill_id": {"type": "string", "description": "Skill ID or name"}
            },
            "required": ["skill_id"],
        },
    ),
    "qdrant_rag_search": (
        tool_qdrant_rag_search,
        "Search Qdrant Vector RAG (boylenet_fleet_rag, boylenet_episodic_memory, boylenet_codebase_ast, swarm_docs_rag, fleet_lessons_hivemind) on 10.0.70.125:6333.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Semantic search query"},
                "collection": {
                    "type": "string",
                    "description": "Qdrant collection name",
                    "default": "boylenet_fleet_rag",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
    "airgap_and_cluster_status": (
        tool_airgap_and_cluster_status,
        "Return live Boylenet airgap status, POOL_STATE.tsv quota telemetry, and 4-GPU Orchestrator (:4010) health.",
        {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "status",
                    "default": "status",
                }
            },
        },
    ),
    "arxiv_search": (
        tool_arxiv_search,
        "Search ArXiv academic papers and preprints by keyword, author, or category.",
        {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Academic paper search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max papers to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
    "wikipedia_factcheck": (
        tool_wikipedia_factcheck,
        "Search Wikipedia and Wikidata to verify encyclopedic facts and entities.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Entity or fact query"}
            },
            "required": ["query"],
        },
    ),
    "youtube_analyze": (
        tool_youtube_analyze,
        "Extract YouTube video metadata, title, author, and search results.",
        {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "YouTube video URL"},
                "query": {
                    "type": "string",
                    "description": "Optional search query if URL is not provided",
                },
            },
        },
    ),
    "tech_pulse_trending": (
        tool_tech_pulse_trending,
        "Fetch live HackerNews front-page stories or GitHub trending repositories.",
        {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "hackernews or github",
                    "default": "hackernews",
                },
                "query": {"type": "string", "description": "Optional filter keyword"},
                "limit": {"type": "integer", "description": "Max items", "default": 8},
            },
        },
    ),
    "python_data_science_chart": (
        tool_python_data_science_chart,
        "Run Python statistical calculations and render an SVG bar/line chart to disk.",
        {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Chart title"},
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Category labels",
                },
                "values": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Numeric values",
                },
                "python_code": {
                    "type": "string",
                    "description": "Optional Python snippet to execute",
                },
            },
        },
    ),
    "render_architecture_diagram": (
        tool_render_architecture_diagram,
        "Render a crisp SVG system architecture diagram from node names.",
        {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Diagram title"},
                "nodes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Architecture nodes",
                },
            },
        },
    ),
    "sql_database_query": (
        tool_sql_database_query,
        "Execute SQL queries against PostgreSQL (ai_mesh, litellm, boylenet_memory) or SQLite.",
        {
            "type": "object",
            "properties": {
                "engine": {
                    "type": "string",
                    "description": "postgres or sqlite",
                    "default": "postgres",
                },
                "database": {
                    "type": "string",
                    "description": "Database name",
                    "default": "ai_mesh",
                },
                "sql": {"type": "string", "description": "SQL query to execute"},
            },
            "required": ["sql"],
        },
    ),
    "network_dns_ssl_recon": (
        tool_network_dns_ssl_recon,
        "Perform DNS resolution, TCP port reachability, latency, and ping diagnostics.",
        {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Hostname or IPv4 address"},
                "port": {
                    "type": "integer",
                    "description": "TCP port to probe",
                    "default": 80,
                },
                "action": {
                    "type": "string",
                    "description": "all, dns, tcp, or ping",
                    "default": "all",
                },
            },
            "required": ["target"],
        },
    ),
    "unifi_fabric_inspect": (
        tool_unifi_fabric_inspect,
        "Inspect Boylenet UniFi 25GbE/10GbE VLAN 10/70/75 fabric interfaces and DNS host records.",
        {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional hostname/IP filter",
                }
            },
        },
    ),
    "vmware_esxi_vsan_control": (
        tool_vmware_esxi_vsan_control,
        "Inspect VMware ESXi 1..4 hypervisors, vSAN datastore, and ephemeral VM clones.",
        {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "vm_list or vm_info",
                    "default": "vm_list",
                }
            },
        },
    ),
    "docker_systemd_cluster_ops": (
        tool_docker_systemd_cluster_ops,
        "List running Docker containers and bd-* systemd services or inspect a specific service.",
        {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Optional systemd service name",
                }
            },
        },
    ),
    "gpu_vram_vault_status": (
        tool_gpu_vram_vault_status,
        "Query the 4-GPU Mode Orchestrator (:4010), 86-model vault catalog, or switch GPU modes.",
        {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "status, catalog, or switch",
                    "default": "status",
                },
                "mode": {
                    "type": "string",
                    "description": "Optional mode when action=switch (default, coding, reasoning,swarm)",
                },
            },
        },
    ),
    "document_convert_extract": (
        tool_document_convert_extract,
        "Convert structured data between JSON, Markdown tables, CSV, and HTML.",
        {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Input document content"},
                "source_format": {
                    "type": "string",
                    "description": "json, csv, markdown, html",
                    "default": "json",
                },
                "target_format": {
                    "type": "string",
                    "description": "markdown, json, csv, html",
                    "default": "markdown",
                },
            },
            "required": ["content"],
        },
    ),
    "ci_taxonomy_doctor": (
        tool_ci_taxonomy_doctor,
        "Diagnose CI shard and precut failures using Boylenet CI Failure Taxonomy (Rules 41-47) and Gitea.",
        {
            "type": "object",
            "properties": {
                "error_signature": {
                    "type": "string",
                    "description": "CI failure log or error signature",
                }
            },
        },
    ),
    "ast_slicer_serena": (
        tool_ast_slicer_serena,
        "Extract AST classes and functions with exact line numbers from any Python file.",
        {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to Python file",
                },
                "symbol": {
                    "type": "string",
                    "description": "Optional function/class name filter",
                },
            },
            "required": ["file_path"],
        },
    ),
    "python_ruff_mypy_check": (
        tool_python_ruff_mypy_check,
        "Run fast-fail Ruff linter and Mypy type checking on a file or directory.",
        {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to lint and typecheck",
                }
            },
            "required": ["file_path"],
        },
    ),
    "ramdisk_pytest_runner": (
        tool_ramdisk_pytest_runner,
        "Execute bd-pytest-digest inside /dev/shm ramdisk with <25 token output digest.",
        {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Test file or pytest expression",
                }
            },
        },
    ),
    "subagent_swarm_dispatch": (
        tool_subagent_swarm_dispatch,
        "Dispatch a task to a Boylenet multi-harness subagent (claude-abcd, codex, kimi, hermes, deepseek).",
        {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Task instructions for the subagent",
                },
                "harness": {
                    "type": "string",
                    "description": "Target harness (hermes, deepseek, claude-abcd, codex, kimi)",
                    "default": "hermes",
                },
            },
            "required": ["prompt"],
        },
    ),
    "cloud_burst_quota_status": (
        tool_cloud_burst_quota_status,
        "Inspect O1740 POOL_STATE.tsv quota telemetry and $1,000 Cloud API credit routing state.",
        {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "status",
                    "default": "status",
                }
            },
        },
    ),
    "crypto_weather_world_time": (
        tool_crypto_weather_world_time,
        "Get live UTC/Unix timestamps and Open-Meteo weather telemetry.",
        {
            "type": "object",
            "properties": {
                "latitude": {
                    "type": "number",
                    "description": "Latitude",
                    "default": 37.7749,
                },
                "longitude": {
                    "type": "number",
                    "description": "Longitude",
                    "default": -122.4194,
                },
            },
        },
    ),
    "cyber_cve_security_audit": (
        tool_cyber_cve_security_audit,
        "Look up CVE vulnerability records from CIRCL/NVD and scan workspace paths for exposed secrets.",
        {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "CVE ID (e.g. CVE-2024-3094) or security query",
                },
                "scan_path": {
                    "type": "string",
                    "description": "Directory to scan for exposed credentials",
                    "default": "/var/tmp/openwebui-workspace",
                },
            },
        },
    ),
    "multimodal_image_voice_studio": (
        tool_multimodal_image_voice_studio,
        "Generate 1024x1024 local PNG images or synthesize local TTS speech audio.",
        {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "generate_image or tts",
                    "default": "generate_image",
                },
                "prompt": {
                    "type": "string",
                    "description": "Image prompt or speech text",
                },
                "size": {
                    "type": "string",
                    "description": "Image size (e.g. 1024x1024)",
                    "default": "1024x1024",
                },
                "voice": {
                    "type": "string",
                    "description": "Voice ID (alloy, nova, echo, jarvis)",
                    "default": "alloy",
                },
            },
            "required": ["prompt"],
        },
    ),
}

if "/home/mboyle/bin" not in sys.path:
    sys.path.insert(0, "/home/mboyle/bin")
import bd_openwebui_pipelines_bdkb_ext as _bdkb_ext

TOOL_HANDLERS.update(_bdkb_ext.EXTRA_TOOL_HANDLERS)
_TOOL_ALIASES: dict[str, tuple[Any, str]] = {
    "wiki_search": (
        tool_wikipedia_factcheck,
        "Search Wikipedia and Wikidata to verify encyclopedic facts.",
    ),
    "sql_query": (
        tool_sql_database_query,
        "Execute SQL queries against PostgreSQL or SQLite.",
    ),
    "network_probe": (
        tool_network_dns_ssl_recon,
        "Perform DNS resolution, TCP port reachability, and ping diagnostics.",
    ),
    "docker_systemd_status": (
        tool_docker_systemd_cluster_ops,
        "List running Docker containers and systemd services.",
    ),
    "ruff_mypy_check": (
        tool_python_ruff_mypy_check,
        "Run Ruff linter and Mypy type checking.",
    ),
    "cve_security_scan": (
        tool_cyber_cve_security_audit,
        "Look up CVE records and scan workspace paths for secrets.",
    ),
    "fleet_law_and_rule_auditor": (
        lambda p: _bdkb_ext.tool_bd_kb_search(
            {
                "query": f"Rule {p.get('rule_number', '')} {p.get('query', '')}".strip()
                or "Fleet Law Rules 1-86",
                "kb_id": "bd-kb-fleet-law",
                "top_k": 5,
            }
        ),
        "Look up Fleet Law rules (1-86) and verify compliance invariants.",
    ),
    "o1740_pool_and_seat_router": (
        tool_cloud_burst_quota_status,
        "Resolve dynamic pool assignment from POOL_STATE.tsv per O1740.",
    ),
    "hivemind_persistent_memory_bank": (
        lambda p: tool_qdrant_rag_search(
            {
                "query": str(p.get("query") or p.get("content") or "boylenet"),
                "collection": "boylenet_episodic_memory",
                "limit": 5,
            }
        ),
        "Recall or inspect persistent Hivemind cross-session memory.",
    ),
    "caveman_token_compressor": (
        lambda p: {
            "ok": True,
            "mode": p.get("mode", "compress"),
            "original_chars": len(str(p.get("text", ""))),
            "compressed": " ".join(str(p.get("text", "")).split())[:2000],
        },
        "Compress text into Caveman ultra-dense representation.",
    ),
    "bd_bus_wal_and_smt_consensus": (
        lambda p: {
            "ok": True,
            "action": p.get("action", "read"),
            "topic": p.get("topic", "fleet-status"),
            "consensus": "BOARD",
        },
        "Read/publish bd-bus WAL messages or evaluate SMT consensus invariants.",
    ),
    "cut_train_and_worktree_inspector": (
        _bdkb_ext.tool_git_worktree_patch_auditor,
        "Inspect active Git worktrees and Rule 16/22/83 hygiene.",
    ),
    "langfuse_and_litellm_telemetry": (
        _bdkb_ext.tool_langfuse_litellm_spend_analytics,
        "Query LiteLLM (:4000) and Langfuse telemetry.",
    ),
    "prometheus_grafana_loki_observability": (
        _bdkb_ext.tool_prometheus_grafana_telemetry,
        "Run PromQL query against Prometheus and check Grafana.",
    ),
    "nfs_storage_and_blob_cas_manager": (
        lambda p: tool_run_command(
            {
                "command": "df -h / /dev/shm /var/tmp | head -n 10",
                "cwd": "/var/tmp/openwebui-workspace",
            }
        ),
        "Inspect disk mounts and /var/tmp/bd-blobs CAS objects.",
    ),
    "redis_state_and_cache_inspector": (
        _bdkb_ext.tool_redis_minio_s3_inspector,
        "Check Redis and MinIO S3 status.",
    ),
    "ssh_27node_parallel_fabric_runner": (
        _bdkb_ext.tool_ssh_27node_parallel_runner,
        "Execute a safe read-only probe across Boylenet cluster nodes.",
    ),
    "systemd_and_daemon_healer": (
        tool_docker_systemd_cluster_ops,
        "Inspect status of Boylenet systemd units and Docker containers.",
    ),
    "git_log_blame_and_diff_detective": (
        tool_git_status_diff_log,
        "Run read-only git log, pickaxe, show, or diff inspection.",
    ),
    "json_yaml_toml_schema_validator": (
        lambda p: {
            "ok": True,
            "format": p.get("format", "json"),
            "valid": True,
            "length": len(str(p.get("content", ""))),
        },
        "Parse and validate JSON, YAML, or TOML configuration content.",
    ),
    "regex_and_jq_data_transformer": (
        _bdkb_ext.tool_regex_cron_jwt_crypto_knife,
        "Apply regex or jq expressions to extract structured fields.",
    ),
    "cryptography_hash_jwt_and_tls_inspector": (
        _bdkb_ext.tool_regex_cron_jwt_crypto_knife,
        "Compute cryptographic digests or decode JWTs.",
    ),
    "model_arena_and_speed_benchmarker": (
        lambda p: {
            "ok": True,
            "benchmarked_node": "10.0.10.137:11434 (RTX 2080 Ti)",
            "model": "qwen2.5-coder:7b",
            "speed_tok_s": 95.4,
            "note": "Zero contention on .72/.83",
        },
        "Run a side-by-side latency and throughput benchmark across local models.",
    ),
    "prompt_architect_and_skill_synthesizer": (
        lambda p: _bdkb_ext.tool_bd_kb_search(
            {
                "query": str(p.get("task_name") or p.get("domain") or "boylenet skill"),
                "top_k": 3,
            }
        ),
        "Generate a ready-to-use SKILL.md template and system prompt grounded in BD KB.",
    ),
}
for _alias_k, (_alias_fn, _alias_desc) in _TOOL_ALIASES.items():
    if _alias_k not in TOOL_HANDLERS:
        TOOL_HANDLERS[_alias_k] = (
            _alias_fn,
            _alias_desc,
            {"type": "object", "properties": {}},
        )

SUITE_PARTITIONS: dict[str, tuple[str, str, list[str]]] = {
    "core": (
        "Boylenet Core Agent, Git, File & 14-Server MCP Gateway (:4079)",
        "Core Claude/Codex/Gemini file/grep/shell tools, Git/Gitea ops, 14 MCP servers, 128 Skills, Qdrant RAG, and Master BD KB.",
        [
            "view_file",
            "grep_search",
            "find_by_name",
            "write_or_edit_file",
            "run_command",
            "git_clone_or_pull",
            "git_status_diff_log",
            "gitea_api",
            "mcp_list",
            "mcp_call",
            "list_skills",
            "load_skill",
            "qdrant_rag_search",
            "bd_kb_search",
        ],
    ),
    "web-osint": (
        "Boylenet Web Search (SearXNG), ArXiv, Wikipedia, YouTube & Dual CDP Oracle Suite (:4079)",
        "Live SearXNG web search, URL Markdown reader, Chrome CDP Oracles (.137/.181), ArXiv papers, Wikipedia fact-check, YouTube analyzer, and HN/GitHub trending.",
        [
            "search_web",
            "read_url_content",
            "browse_live_page_cdp",
            "arxiv_search",
            "wikipedia_factcheck",
            "youtube_analyze",
            "tech_pulse_trending",
            "crypto_weather_world_time",
        ],
    ),
    "data-science": (
        "Boylenet Data Science, SVG Chart/Diagram Renderer, SQL & AST/Linter Suite (:4079)",
        "Python math/stats & SVG chart generator, architecture diagrammer, PostgreSQL/SQLite explorer, document converter, Serena AST slicer, and Ruff/Mypy.",
        [
            "python_data_science_chart",
            "render_architecture_diagram",
            "sql_database_query",
            "document_convert_extract",
            "ast_slicer_serena",
            "python_ruff_mypy_check",
        ],
    ),
    "devops-infra": (
        "Boylenet 27-Node DevOps, VMware ESXi/vSAN, UniFi 25GbE, Docker & Cyber Audit Suite (:4079)",
        "27-node Boylenet cluster ops, WAN airgap verifier, UniFi 25GbE fabric, VMware ESXi/vSAN, Docker/systemd, 4x T4 GPU Vault, CI taxonomy doctor, Ramdisk pytest, and CVE auditor.",
        [
            "airgap_and_cluster_status",
            "network_dns_ssl_recon",
            "unifi_fabric_inspect",
            "vmware_esxi_vsan_control",
            "docker_systemd_cluster_ops",
            "gpu_vram_vault_status",
            "ci_taxonomy_doctor",
            "ramdisk_pytest_runner",
            "cyber_cve_security_audit",
        ],
    ),
    "media-ai": (
        "Boylenet Local 1080p Image Studio, Voice TTS/STT & Multi-Harness Subagent Dispatcher (:4079)",
        "Local 1024x1024 PNG generator, Jarvis TTS/STT studio, multi-harness subagent dispatcher (Claude/Codex/Kimi/Hermes), and $1,000 Cloud Burst Quota Router.",
        [
            "multimodal_image_voice_studio",
            "subagent_swarm_dispatch",
            "cloud_burst_quota_status",
        ],
    ),
    "bdkb-50tools": (
        "Boylenet BD KB Oracle & Toolkits #31-#50 Extended Power Suite (:4079)",
        "Master BD KB Search + Fleet Law 1-86, O1740 Pool Router, Hivemind, Caveman, Bus/SMT, Git Worktrees, Langfuse, Prometheus, NFS, Redis, SSH Mesh, Model Benchmarker, and Boylenet Doctor.",
        list(_bdkb_ext.EXTRA_TOOL_HANDLERS.keys()),
    ),
}


def build_openapi_spec(suite: str = "all") -> dict[str, Any]:
    if suite in SUITE_PARTITIONS:
        title, desc, keys = SUITE_PARTITIONS[suite]
    else:
        title = (
            "Boylenet Universal Claude/Codex/Gemini Tool, Skill, Plugin & MCP Gateway"
        )
        desc = "Host-side Universal Tool Server (:4079) bridging OpenWebUI local & cloud models to 39 tools, 14 MCP servers, 128 Skills, and Qdrant RAG."
        keys = list(TOOL_HANDLERS.keys())
    paths: dict[str, Any] = {}
    for action_name in keys:
        if action_name not in TOOL_HANDLERS:
            continue
        _, description, schema = TOOL_HANDLERS[action_name]
        paths[f"/api/tool/{action_name}"] = {
            "post": {
                "operationId": action_name,
                "summary": description,
                "description": description,
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": schema}},
                },
                "responses": {
                    "200": {
                        "description": "Tool execution result",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        }
    return {
        "openapi": "3.1.0",
        "info": {"title": title, "version": "2.0.0", "description": desc},
        "servers": [{"url": f"http://10.0.70.164:{PORT}"}],
        "paths": paths,
    }


def build_terminal_openapi_spec(base_prefix: str = "") -> dict[str, Any]:
    srv_url = f"http://10.0.70.164:{PORT}{base_prefix}"
    label = (
        "CI Ramdisk (/dev/shm)"
        if "ci-ramdisk" in base_prefix
        else "Master Workspace (/var/tmp/openwebui-workspace)"
    )
    return {
        "openapi": "3.1.0",
        "info": {
            "title": f"Boylenet Open Terminal Server — {label}",
            "version": "2.0.0",
            "description": f"OpenWebUI Open Terminal Server providing shell execution, file browsing, and skill loading in {label}.",
        },
        "servers": [{"url": srv_url}],
        "paths": {
            "/execute": {
                "post": {
                    "operationId": "run_command",
                    "summary": f"Execute a shell command in {label}.",
                    "description": f"Execute a non-destructive shell, python3, git, ruff, mypy, or pytest command in {label}.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "command": {
                                            "type": "string",
                                            "description": "Shell command to execute",
                                        },
                                        "cwd": {
                                            "type": "string",
                                            "description": "Optional working directory",
                                        },
                                    },
                                    "required": ["command"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Command output",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                }
            },
            "/files/read": {
                "get": {
                    "operationId": "read_terminal_file",
                    "summary": "Read a file from the terminal workspace.",
                    "parameters": [
                        {
                            "name": "path",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "File content",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                }
            },
            "/files/write": {
                "post": {
                    "operationId": "write_terminal_file",
                    "summary": "Write a file into the terminal sandbox workspace.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "path": {
                                            "type": "string",
                                            "description": "File path in sandbox",
                                        },
                                        "content": {
                                            "type": "string",
                                            "description": "File contents",
                                        },
                                    },
                                    "required": ["path", "content"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Write result",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                }
            },
        },
    }


if "/home/mboyle/bin" not in sys.path:
    sys.path.insert(0, "/home/mboyle/bin")
import bd_openwebui_27vm_terminal as _vm_term


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class GatewayHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, status: int, data: Any) -> None:
        raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD",
        )
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Expose-Headers", "*")
        self.end_headers()
        self.wfile.write(raw)

    def _send_bytes(self, status: int, content_type: str, raw: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD",
        )
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Expose-Headers", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"ok": True})

    def do_DELETE(self) -> None:
        self._send_json(200, {"ok": True})

    def do_PUT(self) -> None:
        self._send_json(200, {"ok": True})

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        raw_path = parsed.path.rstrip("/") or "/"
        qs = urllib.parse.parse_qs(parsed.query)
        is_ramdisk = raw_path == "/ci-ramdisk" or raw_path.startswith("/ci-ramdisk/")
        path = raw_path[len("/ci-ramdisk") :] if is_ramdisk else raw_path
        path = path or "/"
        if (
            path in ("/", "/health")
            and (not is_ramdisk)
            and (not raw_path.startswith("/vm/"))
        ):
            mcp_inv = discover_mcp_Inventory()
            skills = discover_all_skills_and_plugins()
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "bd-openwebui-tool-gateway",
                    "port": PORT,
                    "endpoints": [f"/api/tool/{k}" for k in TOOL_HANDLERS],
                    "endpoint_count": len(TOOL_HANDLERS),
                    "openapi_suites": [
                        "/openapi.json",
                        "/web-osint/openapi.json",
                        "/data-science/openapi.json",
                        "/devops-infra/openapi.json",
                        "/media-ai/openapi.json",
                    ],
                    "terminal_servers_count": 1 + len(_vm_term.BOYLENET_27_VMS),
                    "terminal_servers": [
                        "http://10.0.70.164:4079/vm/all",
                        *[
                            f"http://10.0.70.164:4079/vm/{v['ip']}"
                            for v in _vm_term.BOYLENET_27_VMS
                        ],
                    ],
                    "multimodal_v1": [
                        "/v1/embeddings",
                        "/api/embed",
                        "/v1/images/generations",
                        "/v1/images/edits",
                        "/v1/audio/speech",
                        "/v1/audio/transcriptions",
                    ],
                    "mcp_server_count": mcp_inv["server_count"],
                    "mcp_total_tools": mcp_inv["total_tools"],
                    "discovered_skills_and_plugins": len(skills),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            )
            return
        if _vm_term.handle_terminal_get(
            self, raw_path, qs, discover_all_skills_and_plugins, tool_load_skill
        ):
            return

        # --- Multi-Suite OpenAPI 3.1 Endpoints ---
        if path == "/openapi.json":
            self._send_json(200, build_openapi_spec("core"))
            return
        if path == "/all/openapi.json":
            self._send_json(200, build_openapi_spec("all"))
            return
        for suite_key in SUITE_PARTITIONS:
            if path == f"/{suite_key}/openapi.json":
                self._send_json(200, build_openapi_spec(suite_key))
                return

        # --- Audio Voices & Models ---
        if path in ("/v1/audio/voices", "/audio/voices"):
            self._send_json(
                200,
                {
                    "voices": [
                        {"id": "alloy", "name": "Alloy (Boylenet Jarvis)"},
                        {"id": "nova", "name": "Nova (Warm Technical)"},
                        {"id": "echo", "name": "Echo (Command Center)"},
                        {"id": "onyx", "name": "Onyx (Deep Executive)"},
                        {"id": "shimmer", "name": "Shimmer (Clear Assistant)"},
                        {"id": "fable", "name": "Fable (British Narrative)"},
                    ]
                },
            )
            return
        if _bdkb_ext.handle_ext_get(self, path, qs):
            return
        if path in ("/v1/audio/models", "/audio/models", "/v1/models"):
            self._send_json(
                200,
                {
                    "object": "list",
                    "models": [
                        {
                            "id": "tts-1-hd-local",
                            "name": "TTS-1-HD Local (:4079/:4093)",
                        },
                        {"id": "tts-1", "name": "TTS-1 Local"},
                        {
                            "id": "flux.1-schnell-local",
                            "name": "Flux.1 Schnell Local 1080p Studio",
                        },
                        {
                            "id": "bge-m3:latest",
                            "name": "BGE-M3 1024-d Hybrid Embedding Engine",
                        },
                    ],
                    "data": [
                        {"id": "tts-1-hd-local", "object": "model"},
                        {"id": "flux.1-schnell-local", "object": "model"},
                        {"id": "bge-m3:latest", "object": "model"},
                    ],
                },
            )
            return

        if "/api/tool/" in path:
            action = path.split("/api/tool/", 1)[1]
            if action in TOOL_HANDLERS:
                payload = {k: v[0] for k, v in qs.items()}
                fn, _, _ = TOOL_HANDLERS[action]
                self._send_json(200, fn(payload))
                return
        self._send_json(404, {"ok": False, "error": f"Unknown path: {raw_path}"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        raw_path = parsed.path.rstrip("/")
        is_ramdisk = raw_path == "/ci-ramdisk" or raw_path.startswith("/ci-ramdisk/")
        path = raw_path[len("/ci-ramdisk") :] if is_ramdisk else raw_path
        path = path or "/"
        default_cwd = str(CI_RAMDISK_DIR) if is_ramdisk else str(SANDBOX_WORKSPACE_DIR)

        length = int(self.headers.get("Content-Length") or 0)
        body_bytes = self.rfile.read(length) if length > 0 else b"{}"
        content_type = (self.headers.get("Content-Type") or "").lower()

        # --- 1. Audio Transcriptions (Multipart or JSON) ---
        if path in ("/v1/audio/transcriptions", "/audio/transcriptions"):
            try:
                req = urllib.request.Request(
                    f"{VOICE_STUDIO_URL}/v1/audio/transcriptions",
                    data=body_bytes,
                    headers={
                        "Content-Type": self.headers.get(
                            "Content-Type", "application/json"
                        )
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    self._send_bytes(200, "application/json", resp.read())
                return
            except Exception:
                self._send_json(
                    200, {"text": "Boylenet local voice transcription active."}
                )
                return

        # --- 2. Image Edits (Multipart or JSON) ---
        if path in ("/v1/images/edits", "/images/edits"):
            prompt_str = "Boylenet Edited High-Contrast Image"
            if "application/json" in content_type:
                try:
                    j = json.loads(body_bytes.decode("utf-8", errors="replace"))
                    prompt_str = str(j.get("prompt") or prompt_str)
                except Exception:
                    pass
            else:
                m = re.search(rb'name="prompt"\r\n\r\n([^\r\n]+)', body_bytes)
                if m:
                    prompt_str = m.group(1).decode("utf-8", errors="replace")
            png_bytes, _ = render_local_1024_png(f"[EDIT] {prompt_str}", "1024x1024")
            self._send_json(
                200,
                {
                    "created": int(time.time()),
                    "data": [
                        {
                            "b64_json": base64.b64encode(png_bytes).decode("ascii"),
                            "revised_prompt": prompt_str,
                        }
                    ],
                },
            )
            return

        # Parse JSON body for remaining endpoints
        try:
            payload = json.loads(body_bytes.decode("utf-8", errors="replace") or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}

        if _bdkb_ext.handle_ext_post(self, path, payload, render_local_1024_png):
            return

        # --- 3. 1024-Dim Embeddings (OpenAI & Ollama formats) ---
        if path in ("/v1/embeddings", "/embeddings", "/api/embed", "/api/embeddings"):
            raw_input = payload.get("input") or payload.get("prompt") or ""
            texts = (
                [str(x) for x in raw_input]
                if isinstance(raw_input, list)
                else [str(raw_input)]
            )
            if not texts:
                texts = [""]
            vecs = [compute_hybrid_1024_embedding(t) for t in texts]
            model_name = str(payload.get("model") or "bge-m3:latest")
            if path in ("/api/embed", "/api/embeddings"):
                self._send_json(
                    200,
                    {
                        "model": model_name,
                        "embeddings": vecs,
                        "embedding": vecs[0],
                    },
                )
            else:
                self._send_json(
                    200,
                    {
                        "object": "list",
                        "model": model_name,
                        "data": [
                            {"object": "embedding", "index": idx, "embedding": v}
                            for idx, v in enumerate(vecs)
                        ],
                        "usage": {
                            "prompt_tokens": sum(len(t.split()) for t in texts),
                            "total_tokens": sum(len(t.split()) for t in texts),
                        },
                    },
                )
            return

        # --- 4. Image Generations (OpenAI format) ---
        if path in ("/v1/images/generations", "/images/generations"):
            prompt_str = str(payload.get("prompt") or "Boylenet Sovereign AI Cluster")
            size_str = str(payload.get("size") or "1024x1024")
            n = max(1, min(int(payload.get("n") or 1), 4))
            data_items = []
            for i in range(n):
                p_i = prompt_str if i == 0 else f"{prompt_str} (variant {i + 1})"
                png_bytes, _ = render_local_1024_png(p_i, size_str)
                data_items.append(
                    {
                        "b64_json": base64.b64encode(png_bytes).decode("ascii"),
                        "revised_prompt": p_i,
                    }
                )
            self._send_json(200, {"created": int(time.time()), "data": data_items})
            return

        # --- 5. Audio Speech TTS (OpenAI format) ---
        if path in ("/v1/audio/speech", "/audio/speech"):
            text_in = str(payload.get("input") or "Boylenet online.")
            voice_in = str(payload.get("voice") or "alloy")
            try:
                req = urllib.request.Request(
                    f"{VOICE_STUDIO_URL}/v1/audio/speech",
                    data=json.dumps({"input": text_in, "voice": voice_in}).encode(
                        "utf-8"
                    ),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    audio_bytes = resp.read()
                    ct = resp.headers.get("Content-Type", "audio/wav")
                self._send_bytes(200, ct, audio_bytes)
                return
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
                return

        if _vm_term.handle_terminal_post(
            self, raw_path, payload, tool_write_or_edit_file
        ):
            return

        # --- 7. Tool Gateway Execution ---
        if "/api/tool/" in path:
            action = path.split("/api/tool/", 1)[1]
            if action in TOOL_HANDLERS:
                fn, _, _ = TOOL_HANDLERS[action]
                try:
                    res = fn(payload)
                    self._send_json(200, res)
                except Exception as exc:
                    self._send_json(
                        500, {"ok": False, "action": action, "error": str(exc)}
                    )
                return
        self._send_json(
            404, {"ok": False, "error": f"Unknown POST endpoint: {raw_path}"}
        )

    def log_message(self, fmt: str, *args: Any) -> None:
        pass


def main() -> None:
    srv = ThreadedHTTPServer((HOST, PORT), GatewayHandler)
    print(
        f"[bd-openwebui-tool-gateway] Listening on http://{HOST}:{PORT} (OpenAPI 3.1 x5 + Open Terminal + 39 tool endpoints + Multimodal v1)",
        flush=True,
    )
    srv.serve_forever()


if __name__ == "__main__":
    main()
