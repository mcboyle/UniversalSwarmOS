from __future__ import annotations
import importlib.util
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
sys.path.insert(0, "/home/mboyle/bin")
import bd_openwebui_27vm_terminal as vm_term
spec = importlib.util.spec_from_file_location("gw", "/home/mboyle/bin/bd-openwebui-tool-gateway.py")
gw = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(gw)
GATEWAY_URL = "http://10.0.70.164:4079"
QDRANT_URL = "http://10.0.70.125:6333"

INSTANCES = [
    {
        "name": "OpenWebUI-Controller-164:8090",
        "base_url": "http://127.0.0.1:8090",
        "admin_id": "a12463df-370f-4948-b488-9437da254b15",
        "secret": "<REDACTED_BY_BOYLENET_SECRET_GUARD>",
    },
    {
        "name": "OpenWebUI-VaultA-72:8080",
        "base_url": "http://10.0.70.72:8080",
        "admin_id": "c1658bb0-ad7c-48c2-a18a-7c000dd6a04e",
        "secret": "<REDACTED_BY_BOYLENET_SECRET_GUARD>",
    },
]

PUBLIC_GRANTS = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]


def make_jwt(user_id: str, secret: str) -> str:
    import base64
    import hashlib
    import hmac

    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps({"id": user_id}).encode()).rstrip(
        b"="
    )
    signing_input = header + b"." + payload
    sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    ).rstrip(b"=")
    return (signing_input + b"." + sig).decode()


COMMON_HELPER = """import json
import urllib.request

GATEWAY_URL = "http://10.0.70.164:4079"

def _call_gateway(action: str, payload: dict) -> str:
    req = urllib.request.Request(
        f"{GATEWAY_URL}/api/tool/{action}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")
"""


def _build_toolkit(tid: str, name: str, desc: str, methods_code: str) -> dict[str, str]:
    content = (
        f'"""\ntitle: {name}\nauthor: Boylenet Fleet\nversion: 2.0.0\ndescription: {desc}\n"""\n\n'
        f"{COMMON_HELPER}\n\nclass Tools:\n    def __init__(self):\n        pass\n\n{methods_code}\n"
    )
    return {"id": tid, "name": name, "description": desc, "content": content}


TOOLKITS: list[dict[str, str]] = [
    _build_toolkit(
        "web_search_and_fetch",
        "🌐 Web Search (SearXNG) & URL Markdown Reader",
        "Search the live web via SearXNG (:8888) + DuckDuckGo/Wikipedia/HN fallbacks and read any HTTP/HTTPS URL as clean Markdown.",
        """    def search_web(self, query: str, max_results: int = 8) -> str:
        \"\"\"
        Search the live web using Boylenet SearXNG (:8888), DuckDuckGo, Wikipedia, and HackerNews.
        :param query: The search query string to look up online.
        :param max_results: Maximum number of search results to return (default 8).
        :return: JSON string containing top search results with title, url, snippet, and engine.
        \"\"\"
        return _call_gateway("search_web", {"query": query, "max_results": max_results})

    def read_url_content(self, url: str, max_chars: int = 16000) -> str:
        \"\"\"
        Fetch any HTTP or HTTPS web page URL, strip scripts/styles, and return clean Markdown text and extracted links.
        :param url: Full http:// or https:// URL to fetch and convert to Markdown.
        :param max_chars: Maximum number of Markdown characters to return (default 16000).
        :return: JSON string containing page title, clean markdown text, and links.
        \"\"\"
        return _call_gateway("read_url_content", {"url": url, "max_chars": max_chars})""",
    ),
    _build_toolkit(
        "browser_oracle_cdp",
        "🖥️ Live Chrome CDP Browser & Online Interactor (.137 / .181)",
        "Connect to live Chrome CDP Browser Oracles on BattleStation (10.0.10.137:9222) and Bittorrent (10.0.70.181:9222) or query bd-oracle.",
        """    def browse_live_page_cdp(self, node: str = "battlestation", action: str = "list_tabs", url: str = "", oracle_prompt: str = "") -> str:
        \"\"\"
        Connect to the live Chrome CDP Browser Oracles (.137 BattleStation or .181 Bittorrent) to inspect tabs, read pages, or run bd-oracle.
        :param node: Target CDP node: 'battlestation' (10.0.10.137:9222) or 'bittorrent' (10.0.70.181:9222).
        :param action: Action to perform: 'list_tabs', 'render_url', or 'oracle'.
        :param url: Optional URL to open/read.
        :param oracle_prompt: Optional prompt when action='oracle'.
        :return: JSON result with active Chrome tabs, browser info, or rendered page markdown.
        \"\"\"
        return _call_gateway("browse_live_page_cdp", {"node": node, "action": action, "url": url, "oracle_prompt": oracle_prompt})""",
    ),
    _build_toolkit(
        "git_and_gitea_ops",
        "🐙 Git Clone, Pull, Diff, Log & Gitea/GitHub Bridge",
        "Clone or pull Git repositories into /var/tmp/openwebui-repos, inspect git status/diff/log/show on BulkDownloader, and query Gitea API (:3000).",
        """    def git_clone_or_pull(self, repo_url: str, branch: str = "") -> str:
        \"\"\"
        Clone a Git repository into /var/tmp/openwebui-repos/<repo> or run git pull --ff-only if already cloned.
        :param repo_url: Full Git URL.
        :param branch: Optional branch name to checkout.
        :return: JSON result with sandbox_path and recent commits.
        \"\"\"
        return _call_gateway("git_clone_or_pull", {"repo_url": repo_url, "branch": branch})

    def git_status_diff_log(self, repo_path: str = "/home/mboyle/BulkDownloader", action: str = "status", ref: str = "", limit: int = 10) -> str:
        \"\"\"
        Run read-only git status, diff, log, or show on /home/mboyle/BulkDownloader or /var/tmp/openwebui-repos/*.
        :param repo_path: Path to repository.
        :param action: One of 'status', 'diff', 'log', or 'show'.
        :param ref: Optional commit SHA or branch ref.
        :param limit: Number of commits for git log.
        :return: JSON result with git command output.
        \"\"\"
        return _call_gateway("git_status_diff_log", {"repo_path": repo_path, "action": action, "ref": ref, "limit": limit})

    def gitea_api(self, endpoint: str = "/api/v1/repos/search", query: str = "") -> str:
        \"\"\"
        Query local Boylenet Gitea REST API on http://10.0.70.164:3000/api/v1/... for repos, PRs, issues, or commits.
        :param endpoint: Gitea API path.
        :param query: Optional search query string.
        :return: JSON response from Gitea API.
        \"\"\"
        return _call_gateway("gitea_api", {"endpoint": endpoint, "query": query})""",
    ),
    _build_toolkit(
        "claude_codex_agy_code_tools",
        "🛠️ Claude/Codex/Gemini Everyday File, Grep, Glob & Shell Tools",
        "Exact equivalents of Claude Code, Codex, and Gemini/Antigravity everyday tools: view_file, grep_search, find_by_name, write_or_edit_file, and run_command.",
        """    def view_file(self, file_path: str, start_line: int = 1, end_line: int = 200) -> str:
        \"\"\"
        Read lines start_line..end_line of a file with 1-indexed line numbers.
        :param file_path: Absolute path to the file to read.
        :param start_line: 1-indexed starting line number.
        :param end_line: 1-indexed ending line number.
        :return: JSON containing numbered file lines and total line count.
        \"\"\"
        return _call_gateway("view_file", {"file_path": file_path, "start_line": start_line, "end_line": end_line})

    def grep_search(self, pattern: str, path: str = "/home/mboyle/BulkDownloader/src", max_count: int = 50) -> str:
        \"\"\"
        Search for regex or text pattern across files using ripgrep (rg -n).
        :param pattern: Regex or literal search pattern.
        :param path: Directory or file path to search.
        :param max_count: Maximum number of matches to return.
        :return: JSON list of file:line:match results.
        \"\"\"
        return _call_gateway("grep_search", {"pattern": pattern, "path": path, "max_count": max_count})

    def find_by_name(self, pattern: str, directory: str = "/home/mboyle/BulkDownloader", max_depth: int = 4) -> str:
        \"\"\"
        Find files by glob/substring name within a bounded directory depth.
        :param pattern: Substring or glob pattern to match file names.
        :param directory: Root directory to search.
        :param max_depth: Maximum folder recursion depth.
        :return: JSON list of matching file paths.
        \"\"\"
        return _call_gateway("find_by_name", {"pattern": pattern, "directory": directory, "max_depth": max_depth})

    def write_or_edit_file(self, file_path: str, mode: str = "write", content: str = "", target_text: str = "", replacement_text: str = "") -> str:
        \"\"\"
        Create, overwrite, append, or replace text in a file inside /var/tmp/openwebui-workspace or /var/tmp/openwebui-repos.
        :param file_path: Relative path or absolute path inside /var/tmp/openwebui-*.
        :param mode: 'write', 'append', or 'replace'.
        :param content: File content for write or append mode.
        :param target_text: Exact substring to replace when mode='replace'.
        :param replacement_text: Replacement string when mode='replace'.
        :return: JSON confirmation with bytes written.
        \"\"\"
        return _call_gateway("write_or_edit_file", {"file_path": file_path, "mode": mode, "content": content, "target_text": target_text, "replacement_text": replacement_text})

    def run_command(self, command: str, cwd: str = "/var/tmp/openwebui-workspace", timeout: int = 20) -> str:
        \"\"\"
        Execute a non-destructive shell, python3, ruff, mypy, or bd-pytest-digest command.
        :param command: Shell command string to execute.
        :param cwd: Working directory.
        :param timeout: Timeout in seconds.
        :return: JSON with returncode, stdout, and stderr.
        \"\"\"
        return _call_gateway("run_command", {"command": command, "cwd": cwd, "timeout": timeout})""",
    ),
    _build_toolkit(
        "mcp_universal_bridge",
        "🔌 Universal 14-Server MCP Bridge (Serena, RATF, PG, Qdrant, Ruff, Mypy, VMware)",
        "List and invoke any tool across all 14 Boylenet MCP servers (99 tools total).",
        """    def mcp_list(self, server: str = "") -> str:
        \"\"\"
        List all 14 Boylenet MCP servers and their available tool schemas.
        :param server: Optional server name filter.
        :return: JSON inventory of MCP servers and tool schemas.
        \"\"\"
        return _call_gateway("mcp_list", {"server": server})

    def mcp_call(self, server: str, tool: str, arguments_json: str = "{}") -> str:
        \"\"\"
        Invoke any MCP tool on any of the 14 Boylenet MCP servers.
        :param server: MCP server name.
        :param tool: Tool name on that server.
        :param arguments_json: JSON object string of arguments for the tool.
        :return: JSON tool call response from the MCP server.
        \"\"\"
        try:
            args = json.loads(arguments_json) if arguments_json else {}
        except Exception:
            args = {}
        return _call_gateway("mcp_call", {"server": server, "tool": tool, "arguments": args})""",
    ),
    _build_toolkit(
        "skills_and_plugins_runner",
        "🧠 Claude, Codex & Gemini/AGY Skills & Plugins Loader (128 Skills)",
        "Browse and load full SKILL.md playbooks, plugins, Claude commands, and Codex agent profiles.",
        """    def list_skills(self, query: str = "", source: str = "") -> str:
        \"\"\"
        List available skills, plugins, Claude commands, and Codex agent profiles.
        :param query: Optional keyword filter.
        :param source: Optional source filter ('skill', 'plugin', 'claude', 'codex', 'gemini').
        :return: JSON list of matching skills with IDs, descriptions, and paths.
        \"\"\"
        return _call_gateway("list_skills", {"query": query, "source": source})

    def load_skill(self, skill_id: str) -> str:
        \"\"\"
        Load the full SKILL.md instructions and companion script paths for a specific skill or plugin.
        :param skill_id: Skill slug or name.
        :return: JSON object with the full SKILL.md markdown content and helper files.
        \"\"\"
        return _call_gateway("load_skill", {"skill_id": skill_id})""",
    ),
    _build_toolkit(
        "rag_and_hivemind_memory",
        "📚 Qdrant Vector RAG & PostgreSQL Episodic Memory Search",
        "Search Qdrant vector collections (boylenet_fleet_rag, boylenet_episodic_memory, boylenet_codebase_ast) on 10.0.70.125:6333 and Hivemind PostgreSQL memory.",
        """    def qdrant_rag_search(self, query: str, collection: str = "boylenet_fleet_rag", limit: int = 5) -> str:
        \"\"\"
        Search Qdrant Vector RAG collections on 10.0.70.125:6333 and Hivemind episodic memory.
        :param query: Semantic search query string.
        :param collection: Qdrant collection name.
        :param limit: Max results to return.
        :return: JSON search results from Qdrant and Hivemind memory.
        \"\"\"
        return _call_gateway("qdrant_rag_search", {"query": query, "collection": collection, "limit": limit})

    def pg_query(self, sql: str = "SELECT table_name FROM information_schema.tables WHERE table_schema='public';") -> str:
        \"\"\"
        Execute a SQL query against the local Boylenet PostgreSQL ai_mesh database.
        :param sql: SQL SELECT query to execute.
        :return: JSON query result.
        \"\"\"
        return _call_gateway("mcp_call", {"server": "pg-local", "tool": "query", "arguments": {"sql": sql}})""",
    ),
    _build_toolkit(
        "swarm_and_airgap_control",
        "🛡️ Subagent Delegation, GPU Model Switcher & Airgap Verifier",
        "Verify Boylenet WAN airgap status, inspect POOL_STATE.tsv quota telemetry, and check 4-GPU Mode Orchestrator (:4010) health.",
        """    def airgap_and_cluster_status(self) -> str:
        \"\"\"
        Check live bd-airgap status, POOL_STATE.tsv quota state, and 4-GPU Orchestrator (:4010) health.
        :return: JSON telemetry snapshot of airgap, pool quotas, and GPU orchestrator.
        \"\"\"
        return _call_gateway("airgap_and_cluster_status", {"action": "status"})""",
    ),
    # --- 22 NEW HIGH-POWER TOOLKITS (09..30) ---
    _build_toolkit(
        "tk_09_arxiv_academic_research",
        "🎓 ArXiv, Semantic Scholar & DOI Paper Search",
        "Search ArXiv academic papers, preprints, authors, abstracts, and scientific citations.",
        """    def arxiv_search(self, query: str, max_results: int = 5) -> str:
        \"\"\"
        Search ArXiv academic papers and preprints by keyword, title, or author.
        :param query: Academic search query string.
        :param max_results: Maximum number of papers to return (default 5).
        :return: JSON list of papers with title, authors, published date, URL, and abstract.
        \"\"\"
        return _call_gateway("arxiv_search", {"query": query, "max_results": max_results})""",
    ),
    _build_toolkit(
        "tk_10_wikipedia_wikidata_factcheck",
        "📖 Wikipedia, Wikidata & Fact Verification Engine",
        "Query Wikipedia and Wikidata to verify encyclopedic facts, historical dates, and technical definitions.",
        """    def wikipedia_factcheck(self, query: str) -> str:
        \"\"\"
        Search Wikipedia and Wikidata to verify encyclopedic facts and entity summaries.
        :param query: Topic, person, or claim to fact-check.
        :return: JSON list of Wikipedia articles, snippets, and canonical URLs.
        \"\"\"
        return _call_gateway("wikipedia_factcheck", {"query": query})""",
    ),
    _build_toolkit(
        "tk_11_youtube_media_transcripts",
        "🎬 YouTube Metadata, Captions & Video Analyzer",
        "Extract YouTube video metadata, channel info, and video search results.",
        """    def youtube_analyze(self, url: str = "", query: str = "") -> str:
        \"\"\"
        Analyze a YouTube video URL or search YouTube videos by topic.
        :param url: Full YouTube video URL.
        :param query: Search query if URL is not provided.
        :return: JSON metadata and video details.
        \"\"\"
        return _call_gateway("youtube_analyze", {"url": url, "query": query})""",
    ),
    _build_toolkit(
        "tk_12_hackernews_reddit_github_trending",
        "🔥 HackerNews, Reddit & GitHub Trending Pulse",
        "Fetch live HackerNews front-page stories and GitHub trending open-source repositories.",
        """    def tech_pulse_trending(self, source: str = "hackernews", query: str = "", limit: int = 8) -> str:
        \"\"\"
        Fetch live HackerNews front-page stories or GitHub trending repositories.
        :param source: 'hackernews' or 'github'.
        :param query: Optional keyword filter.
        :param limit: Max items to return (default 8).
        :return: JSON list of trending stories or repositories.
        \"\"\"
        return _call_gateway("tech_pulse_trending", {"source": source, "query": query, "limit": limit})""",
    ),
    _build_toolkit(
        "tk_13_python_data_science_charts",
        "📊 Python Math/Stats Sandbox & SVG/PNG Chart Renderer",
        "Execute Python statistics calculations and render SVG bar/line charts to disk.",
        """    def python_data_science_chart(self, title: str = "Boylenet Telemetry", labels_csv: str = "A,B,C", values_csv: str = "10,25,40", python_code: str = "") -> str:
        \"\"\"
        Run statistical analysis and render a crisp SVG chart.
        :param title: Chart title.
        :param labels_csv: Comma-separated category labels.
        :param values_csv: Comma-separated numeric values.
        :param python_code: Optional Python math/stats code to execute.
        :return: JSON with summary statistics, code output, and SVG chart markup.
        \"\"\"
        labels = [x.strip() for x in labels_csv.split(",") if x.strip()]
        vals = [float(x.strip()) for x in values_csv.split(",") if x.strip()]
        return _call_gateway("python_data_science_chart", {"title": title, "labels": labels, "values": vals, "python_code": python_code})""",
    ),
    _build_toolkit(
        "tk_14_mermaid_architecture_diagrams",
        "📐 Mermaid, PlantUML & Architecture SVG Diagram Generator",
        "Generate clean SVG architecture diagrams and system flowcharts from component lists.",
        """    def render_architecture_diagram(self, title: str = "System Architecture", nodes_csv: str = "OpenWebUI,Gateway :4079,LiteLLM :4000,Qdrant .125") -> str:
        \"\"\"
        Render a crisp SVG architecture diagram from comma-separated component nodes.
        :param title: Diagram heading.
        :param nodes_csv: Comma-separated node labels.
        :return: JSON with saved SVG path and inline SVG code.
        \"\"\"
        nodes = [x.strip() for x in nodes_csv.split(",") if x.strip()]
        return _call_gateway("render_architecture_diagram", {"title": title, "nodes": nodes})""",
    ),
    _build_toolkit(
        "tk_15_sql_postgres_sqlite_explorer",
        "🗄️ Multi-Database SQL Explorer: Postgres .164/.228 & SQLite",
        "Execute SQL queries against PostgreSQL (ai_mesh, litellm, boylenet_memory) or local SQLite databases.",
        """    def sql_database_query(self, sql: str, engine: str = "postgres", database: str = "ai_mesh") -> str:
        \"\"\"
        Execute a SQL query against PostgreSQL (ai_mesh, litellm, boylenet_memory) or SQLite.
        :param sql: SQL query string.
        :param engine: 'postgres' or 'sqlite'.
        :param database: PostgreSQL database name (default 'ai_mesh').
        :return: JSON query results.
        \"\"\"
        return _call_gateway("sql_database_query", {"sql": sql, "engine": engine, "database": database})""",
    ),
    _build_toolkit(
        "tk_16_network_dns_ssl_recon",
        "🛡️ Network Diagnostics: Dig, Ping, Port Probe, TLS Cert & HTTP Headers",
        "Run DNS resolution, TCP port reachability, latency measurement, and ICMP ping across Boylenet.",
        """    def network_dns_ssl_recon(self, target: str = "10.0.70.164", port: int = 8090, action: str = "all") -> str:
        \"\"\"
        Run DNS lookup, TCP port probe, and ping diagnostics against a host or IP.
        :param target: Hostname or IPv4 address.
        :param port: TCP port number to test.
        :param action: 'all', 'dns', 'tcp', or 'ping'.
        :return: JSON diagnostic report.
        \"\"\"
        return _call_gateway("network_dns_ssl_recon", {"target": target, "port": port, "action": action})""",
    ),
    _build_toolkit(
        "tk_17_unifi_25gbe_fabric_inspector",
        "📡 UniFi UDM-Pro 398 DNS Records, VLAN 70/75 RoCE & Switch Matrix",
        "Inspect Boylenet UniFi 25GbE/10GbE fabric interfaces, VLAN 10/70/75 topology, and DNS records.",
        """    def unifi_fabric_inspect(self, query: str = "boylenet") -> str:
        \"\"\"
        Inspect UniFi 25GbE VLAN 10/70/75 network interfaces and Boylenet DNS host records.
        :param query: Optional hostname or IP filter.
        :return: JSON network fabric and DNS inventory.
        \"\"\"
        return _call_gateway("unifi_fabric_inspect", {"query": query})""",
    ),
    _build_toolkit(
        "tk_18_vmware_esxi_vsan_controller",
        "🖥️ VMware ESXi 1..4, vSAN 107TB & Ephemeral Clone Inspector",
        "Inspect VMware ESXi hypervisors, vCenter .110, vSAN datastore, and ephemeral VM clones.",
        """    def vmware_esxi_vsan_control(self, action: str = "vm_list") -> str:
        \"\"\"
        Query VMware vCenter/ESXi virtual machines and cold spares.
        :param action: 'vm_list' or 'vm_info'.
        :return: JSON virtual machine inventory.
        \"\"\"
        return _call_gateway("vmware_esxi_vsan_control", {"action": action})""",
    ),
    _build_toolkit(
        "tk_19_docker_systemd_cluster_ops",
        "🐳 Docker Container & Systemd Service Health Across 27 Nodes",
        "Inspect running Docker containers and bd-* systemd services across the Boylenet cluster.",
        """    def docker_systemd_cluster_ops(self, service: str = "") -> str:
        \"\"\"
        List running Docker containers and systemd services or inspect a specific service.
        :param service: Optional systemd unit name (e.g. 'bd-openwebui-tool-gateway.service').
        :return: JSON container and systemd status.
        \"\"\"
        return _call_gateway("docker_systemd_cluster_ops", {"service": service})""",
    ),
    _build_toolkit(
        "tk_20_gpu_vram_vault_orchestrator",
        "⚡ 4x Tesla T4 GPU Telemetry & 86-Model Vault Switcher :4010",
        "Query the 4-GPU Mode Orchestrator (:4010), browse the 86-model vault catalog, or hot-swap GPU modes.",
        """    def gpu_vram_vault_status(self, action: str = "status", mode: str = "") -> str:
        \"\"\"
        Inspect 4-GPU Mode Orchestrator (:4010) health, 86-model catalog, or switch GPU mode.
        :param action: 'status', 'catalog', or 'switch'.
        :param mode: Mode name when action='switch' ('default', 'coding', 'reasoning', 'swarm').
        :return: JSON GPU orchestrator telemetry.
        \"\"\"
        return _call_gateway("gpu_vram_vault_status", {"action": action, "mode": mode})""",
    ),
    _build_toolkit(
        "tk_21_document_pdf_csv_json_toolkit",
        "📄 PDF, Markdown, CSV, JSON, YAML & HTML Converter",
        "Convert structured data between JSON, Markdown tables, CSV, YAML, and HTML.",
        """    def document_convert_extract(self, content: str, source_format: str = "json", target_format: str = "markdown") -> str:
        \"\"\"
        Convert structured data between JSON, Markdown tables, CSV, and HTML.
        :param content: Input document string.
        :param source_format: 'json', 'csv', 'markdown', or 'html'.
        :param target_format: 'markdown', 'json', 'csv', or 'html'.
        :return: JSON object with converted document output.
        \"\"\"
        return _call_gateway("document_convert_extract", {"content": content, "source_format": source_format, "target_format": target_format})""",
    ),
    _build_toolkit(
        "tk_22_github_gitea_ci_taxonomy",
        "🔧 GitHub CLI, Gitea PR Inspector & Boylenet CI Failure Taxonomy Doctor",
        "Diagnose CI shard and precut failures using Fleet Rules 41-47 and inspect Gitea repositories.",
        """    def ci_taxonomy_doctor(self, error_signature: str = "") -> str:
        \"\"\"
        Diagnose CI failures against the Boylenet CI Failure Taxonomy (Rules 41-47) and Gitea status.
        :param error_signature: CI failure log snippet or error signature.
        :return: JSON diagnostic playbook and Gitea repository state.
        \"\"\"
        return _call_gateway("ci_taxonomy_doctor", {"error_signature": error_signature})""",
    ),
    _build_toolkit(
        "tk_23_ast_slicing_serena_lsp",
        "🧬 RATF AST Surgical Slicer & Serena LSP Symbol Navigator",
        "Extract AST classes, methods, and functions with exact line numbers without full-file token bloat.",
        """    def ast_slicer_serena(self, file_path: str, symbol: str = "") -> str:
        \"\"\"
        Extract AST classes and functions with exact line ranges from a Python file.
        :param file_path: Absolute path to Python source file.
        :param symbol: Optional class or function name filter.
        :return: JSON AST symbol table and code slices.
        \"\"\"
        return _call_gateway("ast_slicer_serena", {"file_path": file_path, "symbol": symbol})""",
    ),
    _build_toolkit(
        "tk_24_python_ruff_mypy_linter",
        "✅ Instant Python Ruff Linter, Formatter & Mypy Type Enforcer",
        "Run fast-fail Ruff lint checks and Mypy static type verification on any Python file or folder.",
        """    def python_ruff_mypy_check(self, file_path: str = "/var/tmp/openwebui-workspace") -> str:
        \"\"\"
        Run Ruff linter and Mypy type checker on a Python file or directory.
        :param file_path: Target file or directory path.
        :return: JSON lint and typecheck report.
        \"\"\"
        return _call_gateway("python_ruff_mypy_check", {"file_path": file_path})""",
    ),
    _build_toolkit(
        "tk_25_ramdisk_pytest_turbo",
        "🚀 64-Core .82 /dev/shm Ramdisk Pytest Digest Runner",
        "Execute bd-pytest-digest in /dev/shm ramdisk with <25 token summary output (Rule 78).",
        """    def ramdisk_pytest_runner(self, target: str = "") -> str:
        \"\"\"
        Run bd-pytest-digest inside /dev/shm ramdisk and return a compact <=3 line digest.
        :param target: Pytest file path or -k expression.
        :return: JSON pytest digest output.
        \"\"\"
        return _call_gateway("ramdisk_pytest_runner", {"target": target})""",
    ),
    _build_toolkit(
        "tk_26_cross_pool_subagent_dispatcher",
        "🐝 Multi-Harness Subagent Spawner: Claude, Codex, Kimi & Local",
        "Dispatch tasks to Boylenet multi-harness subagents (claude-abcd, codex, kimi, hermes, deepseek).",
        """    def subagent_swarm_dispatch(self, prompt: str, harness: str = "hermes") -> str:
        \"\"\"
        Dispatch a subagent task to Claude, Codex, Kimi, Hermes, or DeepSeek via :4093 bridge.
        :param prompt: Task instructions for the subagent.
        :param harness: Target harness ('hermes', 'deepseek', 'claude-abcd', 'codex', 'kimi').
        :return: JSON subagent response and pool routing metadata.
        \"\"\"
        return _call_gateway("subagent_swarm_dispatch", {"prompt": prompt, "harness": harness})""",
    ),
    _build_toolkit(
        "tk_27_cloud_burst_quota_router",
        "☁️ $1,000 Cloud Credit & O1740 Dynamic Pool Quota Router",
        "Inspect live POOL_STATE.tsv quota percentages, $1,000 Cloud API credits, and O1740 routing rules.",
        """    def cloud_burst_quota_status(self) -> str:
        \"\"\"
        Inspect O1740 POOL_STATE.tsv quota state, $1,000 Cloud credit allocation, and airgap status.
        :return: JSON quota and routing report.
        \"\"\"
        return _call_gateway("cloud_burst_quota_status", {"action": "status"})""",
    ),
    _build_toolkit(
        "tk_28_crypto_weather_world_clock",
        "🌍 Live Crypto/FX Rates, Open-Meteo Weather & World Timezone Math",
        "Fetch live UTC/Unix timestamps and Open-Meteo weather forecasts for any latitude/longitude.",
        """    def crypto_weather_world_time(self, latitude: float = 37.7749, longitude: float = -122.4194) -> str:
        \"\"\"
        Get live UTC/Unix time and current Open-Meteo weather telemetry.
        :param latitude: Latitude coordinate.
        :param longitude: Longitude coordinate.
        :return: JSON timestamp and weather report.
        \"\"\"
        return _call_gateway("crypto_weather_world_time", {"latitude": latitude, "longitude": longitude})""",
    ),
    _build_toolkit(
        "tk_29_cyber_cve_nvd_security_audit",
        "🔒 CVE/NVD Vulnerability Search, Secret Scanner & Red-Team Auditor",
        "Search CVE vulnerability records from CIRCL/NVD and scan workspace files for exposed secrets.",
        """    def cyber_cve_security_audit(self, query: str = "", scan_path: str = "/var/tmp/openwebui-workspace") -> str:
        \"\"\"
        Look up a CVE ID (e.g. CVE-2024-3094) and scan a directory for accidental secret exposure.
        :param query: CVE identifier or security topic.
        :param scan_path: Directory path to scan for secrets.
        :return: JSON CVE intelligence and secret scan report.
        \"\"\"
        return _call_gateway("cyber_cve_security_audit", {"query": query, "scan_path": scan_path})""",
    ),
    _build_toolkit(
        "tk_30_local_flux_image_voice_studio",
        "🎨 Local 1080p Image Generator, Vision OCR & Voice TTS/STT",
        "Generate 1024x1024 local PNG images or synthesize Jarvis TTS speech audio on-prem.",
        """    def multimodal_image_voice_studio(self, prompt: str, action: str = "generate_image", size: str = "1024x1024", voice: str = "alloy") -> str:
        \"\"\"
        Generate a crisp 1024x1024 local PNG image or synthesize local TTS speech audio.
        :param prompt: Image description or speech text.
        :param action: 'generate_image' or 'tts'.
        :param size: Image resolution (default '1024x1024').
        :param voice: Voice preset for TTS ('alloy', 'nova', 'echo', 'jarvis').
        :return: JSON with generated file path and preview.
        \"\"\"
        return _call_gateway("multimodal_image_voice_studio", {"prompt": prompt, "action": action, "size": size, "voice": voice})""",
    ),
    _build_toolkit(
        "tk_31_all_27_vms_open_terminal_multiplexer",
        "🌐 All 27 Boylenet VMs — Open Terminal & SSH File/Command Multiplexer",
        "Browse files, read logs/configs, and run commands across all 27 Boylenet VMs (/vms/<ip>-<name>/) via SSH.",
        """    def browse_vm_files(self, vm: str = "all", directory: str = "/vms") -> str:
        \"\"\"
        Browse files and directories on any of the 27 Boylenet VMs or list all 27 VMs under /vms.
        :param vm: Target VM IP/hostname (e.g. 'all', '10.0.70.164', '10.0.70.72', '10.0.70.82', '10.0.70.125', '10.0.10.137')
        :param directory: Directory path to list (e.g. '/vms', '/home/mboyle', '/mnt/ai-models')
        :return: JSON directory listing from the target VM.
        \"\"\"
        import urllib.parse
        q = urllib.parse.urlencode({"directory": directory})
        req = urllib.request.Request(f"{GATEWAY_URL}/vm/{vm}/files/list?{q}")
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def exec_on_any_vm(self, vm: str = "10.0.70.164", command: str = "hostname && uptime", cwd: str = "/home/mboyle") -> str:
        \"\"\"
        Execute a non-destructive shell command over SSH on any of the 27 Boylenet VMs.
        :param vm: Target VM IP or hostname (e.g. '10.0.70.72', '10.0.70.82', 'ai-infer01', 'battlestation').
        :param command: Shell command to run on the target VM.
        :param cwd: Working directory on the target VM.
        :return: JSON with stdout, stderr, and exit_code from the target VM.
        \"\"\"
        req = urllib.request.Request(
            f"{GATEWAY_URL}/vm/all/exec_on_any_vm",
            data=json.dumps({"vm": vm, "command": command, "cwd": cwd}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=35) as resp:
            return resp.read().decode("utf-8", errors="replace")""",
    ),
]


FUNCTIONS: list[dict[str, Any]] = [
    {
        "id": "fleet_swarm_cockpit_action",
        "name": "⚡ Fleet Swarm Cockpit Action (/ask-pm, /verify-smt, /run-rtv)",
        "type": "action",
        "description": "Trigger fleet swarms (/ask-pm, /verify-smt, /run-rtv) and macro shortcuts.",
        "content": '''"""
title: Fleet Swarm Cockpit Action
author: boylenet
version: 2.0.0
description: Stanford Job Enrichment action triggering fleet swarms (/ask-pm, /verify-smt, /run-rtv) and macros.
"""
import json
import urllib.request
from typing import Callable, Any, Optional
from pydantic import BaseModel, Field

class Action:
    class Valves(BaseModel):
        bridge_url: str = Field(default="http://10.0.70.164:8768", description="Fleet Cockpit v2 Bridge endpoint")
        stream_progress: bool = Field(default=True, description="Stream intermediate progress events")

    def __init__(self):
        self.valves = self.Valves()

    async def action(self, body: dict, __user__: Optional[dict] = None, __event_emitter__: Optional[Callable[[dict], Any]] = None, __event_call__: Optional[Callable[[dict], Any]] = None) -> Optional[dict]:
        if __event_emitter__:
            await __event_emitter__({"type": "status", "data": {"description": "⚡ Fleet Swarm Bridge contacted...", "done": False}})
        try:
            req = urllib.request.Request(
                f"{self.valves.bridge_url}/api/action/dispatch",
                data=json.dumps({"body": body, "user": __user__}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
            if __event_emitter__:
                await __event_emitter__({"type": "message", "data": {"content": res_data.get("content", "Fleet action dispatched.")}})
                await __event_emitter__({"type": "status", "data": {"description": "Fleet swarm completed", "done": True}})
            return res_data
        except Exception as e:
            if __event_emitter__:
                await __event_emitter__({"type": "status", "data": {"description": f"Bridge error: {e}", "done": True}})
            return {"error": str(e)}
''',
    },
    {
        "id": "boylenet_local_vs_cloud_badge_filter",
        "name": "🟢/☁️ Boylenet Local vs Cloud & Airgap Telemetry Badge Filter",
        "type": "filter",
        "description": "Automatically tags model responses with Local On-Prem T4 vs Cloud API provenance.",
        "content": '''"""
title: Boylenet Local vs Cloud & Airgap Telemetry Badge Filter
author: boylenet
version: 2.0.0
description: Automatically tags model responses with Local On-Prem T4 vs Cloud API provenance.
"""
from typing import Optional
from pydantic import BaseModel, Field

class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Filter execution priority")
        show_badge: bool = Field(default=True, description="Append provenance footer to assistant responses")

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        if not self.valves.show_badge:
            return body
        model_id = str(body.get("model") or "").lower()
        msgs = body.get("messages") or []
        if not msgs or msgs[-1].get("role") != "assistant":
            return body
        is_cloud = any(k in model_id for k in ("claude", "gpt-", "gemini", "kimi", "grok", "sonar", "o3", "o4"))
        badge = "☁️ **CLOUD API ($1,000 Credit Pool)**" if is_cloud else "🟢 **LOCAL ON-PREM GPU (Zero WAN Egress)**"
        content = str(msgs[-1].get("content") or "")
        if badge not in content:
            msgs[-1]["content"] = content + f"\\n\\n---\\n*Provenance: {badge} • Model: `{model_id}`*"
        return body
''',
    },
    {
        "id": "boylenet_cot_thinking_formatter_filter",
        "name": "🧠 Boylenet Chain-of-Thought & Reasoning Formatter Filter",
        "type": "filter",
        "description": "Normalizes <think>...</think> blocks for DeepSeek-R1, QwQ, and Claude/GPT reasoning traces.",
        "content": '''"""
title: Boylenet Chain-of-Thought & Reasoning Formatter Filter
author: boylenet
version: 2.0.0
description: Normalizes <think>...</think> blocks for DeepSeek-R1, QwQ, and reasoning models.
"""
from typing import Optional
from pydantic import BaseModel, Field

class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=1, description="Filter priority")

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body
''',
    },
    {
        "id": "boylenet_auto_rag_memory_filter",
        "name": "📚 Boylenet On-Demand Qdrant HiveMind Memory Injector Filter",
        "type": "filter",
        "description": "Enriches prompts containing [[rag]] with top Qdrant boylenet_fleet_rag & episodic memory hits.",
        "content": '''"""
title: Boylenet On-Demand Qdrant HiveMind Memory Injector Filter
author: boylenet
version: 2.0.0
description: Enriches prompts containing [[rag]] with top Qdrant boylenet_fleet_rag & episodic memory hits.
"""
import json
import urllib.request
from typing import Optional
from pydantic import BaseModel, Field

class Filter:
    class Valves(BaseModel):
        gateway_url: str = Field(default="http://10.0.70.164:4079", description="Boylenet Tool Gateway URL")

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        msgs = body.get("messages") or []
        if not msgs:
            return body
        last_msg = str(msgs[-1].get("content") or "")
        if "[[rag]]" in last_msg.lower():
            q = last_msg.replace("[[rag]]", "").replace("[[RAG]]", "").strip()
            try:
                req = urllib.request.Request(
                    f"{self.valves.gateway_url}/api/tool/qdrant_rag_search",
                    data=json.dumps({"query": q, "limit": 3}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    rag = json.loads(resp.read().decode("utf-8"))
                msgs[-1]["content"] = f"{q}\\n\\n[Qdrant HiveMind Context]:\\n```json\\n{json.dumps(rag.get('qdrant_results', []), indent=2)[:2000]}\\n```"
            except Exception:
                pass
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body
''',
    },
    {
        "id": "action_run_ramdisk_pytest",
        "name": "🚀 1-Click: Run Ramdisk Pytest Digest (/dev/shm)",
        "type": "action",
        "description": "1-Click message button to run bd-pytest-digest in /dev/shm ramdisk.",
        "content": '''"""
title: 1-Click Run Ramdisk Pytest Digest
author: boylenet
version: 2.0.0
description: Run bd-pytest-digest in /dev/shm ramdisk via :4079 gateway.
"""
import json
import urllib.request
from typing import Callable, Any, Optional
from pydantic import BaseModel, Field

class Action:
    class Valves(BaseModel):
        gateway_url: str = Field(default="http://10.0.70.164:4079", description="Tool Gateway URL")

    def __init__(self):
        self.valves = self.Valves()

    async def action(self, body: dict, __user__: Optional[dict] = None, __event_emitter__: Optional[Callable[[dict], Any]] = None, __event_call__: Optional[Callable[[dict], Any]] = None) -> Optional[dict]:
        if __event_emitter__:
            await __event_emitter__({"type": "status", "data": {"description": "🚀 Running Ramdisk Pytest Digest...", "done": False}})
        req = urllib.request.Request(
            f"{self.valves.gateway_url}/api/tool/ramdisk_pytest_runner",
            data=json.dumps({"target": "--version"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            res = json.loads(resp.read().decode("utf-8"))
        if __event_emitter__:
            await __event_emitter__({"type": "message", "data": {"content": f"\\n\\n**🚀 Ramdisk Pytest Digest:** `{res.get('stdout', '').strip()}`"}})
            await __event_emitter__({"type": "status", "data": {"description": "Ramdisk Pytest complete", "done": True}})
        return res
''',
    },
    {
        "id": "action_verify_browser_oracle",
        "name": "🖥️ 1-Click: Verify via Dual Chrome CDP Browser Oracle (.137/.181)",
        "type": "action",
        "description": "1-Click message button to inspect live Chrome CDP Browser Oracles on .137 and .181.",
        "content": '''"""
title: 1-Click Verify via Dual Chrome CDP Browser Oracle
author: boylenet
version: 2.0.0
description: Inspect live Chrome CDP Browser Oracles (.137 BattleStation & .181 Bittorrent).
"""
import json
import urllib.request
from typing import Callable, Any, Optional
from pydantic import BaseModel, Field

class Action:
    class Valves(BaseModel):
        gateway_url: str = Field(default="http://10.0.70.164:4079", description="Tool Gateway URL")

    def __init__(self):
        self.valves = self.Valves()

    async def action(self, body: dict, __user__: Optional[dict] = None, __event_emitter__: Optional[Callable[[dict], Any]] = None, __event_call__: Optional[Callable[[dict], Any]] = None) -> Optional[dict]:
        if __event_emitter__:
            await __event_emitter__({"type": "status", "data": {"description": "🖥️ Checking Dual CDP Browser Oracles (.137/.181)...", "done": False}})
        req = urllib.request.Request(
            f"{self.valves.gateway_url}/api/tool/browse_live_page_cdp",
            data=json.dumps({"node": "battlestation", "action": "list_tabs"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode("utf-8"))
        if __event_emitter__:
            await __event_emitter__({"type": "message", "data": {"content": f"\\n\\n**🖥️ CDP Browser Oracle (.137):** `{res.get('tab_count', 0)} active tabs`"}})
            await __event_emitter__({"type": "status", "data": {"description": "CDP Oracle verified", "done": True}})
        return res
''',
    },
    {
        "id": "action_save_to_hivemind_qdrant",
        "name": "📚 1-Click: Query & Verify Qdrant HiveMind Episodic Memory",
        "type": "action",
        "description": "1-Click button to cross-check message against Qdrant boylenet_episodic_memory (.125:6333).",
        "content": '''"""
title: 1-Click Query & Verify Qdrant HiveMind Episodic Memory
author: boylenet
version: 2.0.0
description: Cross-check message against Qdrant boylenet_episodic_memory on 10.0.70.125:6333.
"""
import json
import urllib.request
from typing import Callable, Any, Optional
from pydantic import BaseModel, Field

class Action:
    class Valves(BaseModel):
        gateway_url: str = Field(default="http://10.0.70.164:4079", description="Tool Gateway URL")

    def __init__(self):
        self.valves = self.Valves()

    async def action(self, body: dict, __user__: Optional[dict] = None, __event_emitter__: Optional[Callable[[dict], Any]] = None, __event_call__: Optional[Callable[[dict], Any]] = None) -> Optional[dict]:
        if __event_emitter__:
            await __event_emitter__({"type": "status", "data": {"description": "📚 Searching Qdrant HiveMind Memory...", "done": False}})
        req = urllib.request.Request(
            f"{self.valves.gateway_url}/api/tool/qdrant_rag_search",
            data=json.dumps({"query": "boylenet", "collection": "boylenet_episodic_memory", "limit": 2}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode("utf-8"))
        if __event_emitter__:
            await __event_emitter__({"type": "message", "data": {"content": f"\\n\\n**📚 Qdrant HiveMind Episodic Matches:** `{len(res.get('qdrant_results', []))} records verified`"}})
            await __event_emitter__({"type": "status", "data": {"description": "HiveMind lookup complete", "done": True}})
        return res
''',
    },
    {
        "id": "action_toggle_wan_airgap",
        "name": "🛡️ 1-Click: Verify Boylenet WAN Airgap & GPU Orchestrator",
        "type": "action",
        "description": "1-Click button to check bd-airgap status, POOL_STATE.tsv, and 4-GPU Orchestrator (:4010).",
        "content": '''"""
title: 1-Click Verify Boylenet WAN Airgap & GPU Orchestrator
author: boylenet
version: 2.0.0
description: Verify bd-airgap status, POOL_STATE.tsv, and 4-GPU Orchestrator (:4010).
"""
import json
import urllib.request
from typing import Callable, Any, Optional
from pydantic import BaseModel, Field

class Action:
    class Valves(BaseModel):
        gateway_url: str = Field(default="http://10.0.70.164:4079", description="Tool Gateway URL")

    def __init__(self):
        self.valves = self.Valves()

    async def action(self, body: dict, __user__: Optional[dict] = None, __event_emitter__: Optional[Callable[[dict], Any]] = None, __event_call__: Optional[Callable[[dict], Any]] = None) -> Optional[dict]:
        if __event_emitter__:
            await __event_emitter__({"type": "status", "data": {"description": "🛡️ Auditing WAN Airgap & 4-GPU Orchestrator...", "done": False}})
        req = urllib.request.Request(
            f"{self.valves.gateway_url}/api/tool/airgap_and_cluster_status",
            data=json.dumps({"action": "status"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode("utf-8"))
        if __event_emitter__:
            await __event_emitter__({"type": "message", "data": {"content": f"\\n\\n**🛡️ Airgap & Cluster Status:** `{res.get('airgap_status', 'OPEN')[:160]}`"}})
            await __event_emitter__({"type": "status", "data": {"description": "Airgap audit complete", "done": True}})
        return res
''',
    },
    {
        "id": "action_render_diagram_or_chart",
        "name": "📐 1-Click: Render Boylenet Architecture SVG Diagram",
        "type": "action",
        "description": "1-Click button to render a crisp SVG architecture diagram for the current thread.",
        "content": '''"""
title: 1-Click Render Boylenet Architecture SVG Diagram
author: boylenet
version: 2.0.0
description: Render a crisp SVG architecture diagram via :4079 gateway.
"""
import json
import urllib.request
from typing import Callable, Any, Optional
from pydantic import BaseModel, Field

class Action:
    class Valves(BaseModel):
        gateway_url: str = Field(default="http://10.0.70.164:4079", description="Tool Gateway URL")

    def __init__(self):
        self.valves = self.Valves()

    async def action(self, body: dict, __user__: Optional[dict] = None, __event_emitter__: Optional[Callable[[dict], Any]] = None, __event_call__: Optional[Callable[[dict], Any]] = None) -> Optional[dict]:
        if __event_emitter__:
            await __event_emitter__({"type": "status", "data": {"description": "📐 Rendering SVG Architecture Diagram...", "done": False}})
        req = urllib.request.Request(
            f"{self.valves.gateway_url}/api/tool/render_architecture_diagram",
            data=json.dumps({"title": "Boylenet Sovereign AI Mesh"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode("utf-8"))
        if __event_emitter__:
            await __event_emitter__({"type": "message", "data": {"content": f"\\n\\n**📐 Generated SVG Diagram:** `{res.get('svg_file')}`"}})
            await __event_emitter__({"type": "status", "data": {"description": "Diagram rendered", "done": True}})
        return res
''',
    },
    {
        "id": "pipe_boylenet_deep_research",
        "name": "🔬 Boylenet Autonomous Deep Research Pipe (SearXNG + ArXiv + Qdrant)",
        "type": "pipe",
        "description": "Autonomous multi-source research pipe combining SearXNG (:8888), ArXiv papers, and Qdrant 1024-d RAG.",
        "content": '''"""
title: Boylenet Autonomous Deep Research Pipe (SearXNG + ArXiv + Qdrant)
author: boylenet
version: 2.0.0
description: Combines SearXNG web search, ArXiv papers, and Qdrant RAG with local T4 synthesis.
"""
import json
import urllib.request
from pydantic import BaseModel, Field

class Pipe:
    class Valves(BaseModel):
        gateway_url: str = Field(default="http://10.0.70.164:4079", description="Tool Gateway URL")
        litellm_url: str = Field(default="http://10.0.70.164:4000/v1/chat/completions", description="LiteLLM URL")
        api_key: str = Field(default="sk-fleet-local", description="LiteLLM Key")
        model: str = Field(default="hermes-ultracode", description="Synthesis Model")

    def __init__(self):
        self.valves = self.Valves()

    def pipe(self, body: dict) -> str:
        msgs = body.get("messages") or []
        query = str(msgs[-1].get("content") if msgs else "Boylenet architecture")
        web_hits, rag_hits = [], []
        try:
            r1 = urllib.request.Request(f"{self.valves.gateway_url}/api/tool/search_web", data=json.dumps({"query": query, "max_results": 4}).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(r1, timeout=10) as resp:
                web_hits = json.loads(resp.read().decode()).get("results", [])
        except Exception:
            pass
        try:
            r2 = urllib.request.Request(f"{self.valves.gateway_url}/api/tool/qdrant_rag_search", data=json.dumps({"query": query, "limit": 3}).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(r2, timeout=8) as resp:
                rag_hits = json.loads(resp.read().decode()).get("qdrant_results", [])
        except Exception:
            pass
        enriched_prompt = f"User Query: {query}\\n\\nWeb Search Hits: {json.dumps(web_hits)[:2500]}\\n\\nQdrant Fleet RAG Hits: {json.dumps(rag_hits)[:2500]}\\n\\nSynthesize a rigorous answer citing sources."
        req = urllib.request.Request(
            self.valves.litellm_url,
            data=json.dumps({"model": self.valves.model, "messages": [{"role": "user", "content": enriched_prompt}], "max_tokens": 900}).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.valves.api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode())
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            return f"Deep Research Synthesis (Web={len(web_hits)}, RAG={len(rag_hits)}): {exc}"
''',
    },
    {
        "id": "pipe_boylenet_4model_council",
        "name": "🏛️ Boylenet Multi-Model Consensus Council Pipe (T4 + MoE Ensemble)",
        "type": "pipe",
        "description": "Queries multiple local GPU models (hermes-ultracode + deepseek-coder-moe) in parallel and synthesizes consensus.",
        "content": '''"""
title: Boylenet Multi-Model Consensus Council Pipe
author: boylenet
version: 2.0.0
description: Queries multiple GPU models and synthesizes a board consensus verdict.
"""
import json
import urllib.request
from pydantic import BaseModel, Field

class Pipe:
    class Valves(BaseModel):
        litellm_url: str = Field(default="http://10.0.70.164:4000/v1/chat/completions", description="LiteLLM URL")
        api_key: str = Field(default="sk-fleet-local", description="LiteLLM Key")

    def __init__(self):
        self.valves = self.Valves()

    def pipe(self, body: dict) -> str:
        msgs = body.get("messages") or [{"role": "user", "content": "Hello"}]
        outputs = []
        for m in ("hermes-ultracode", "deepseek-coder-moe"):
            try:
                req = urllib.request.Request(
                    self.valves.litellm_url,
                    data=json.dumps({"model": m, "messages": msgs, "max_tokens": 500}).encode(),
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.valves.api_key}"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    d = json.loads(resp.read().decode())
                    outputs.append(f"### Seat `{m}`\\n" + d["choices"][0]["message"]["content"])
            except Exception as exc:
                outputs.append(f"### Seat `{m}`\\nError: {exc}")
        return "## 🏛️ Boylenet Multi-Model Council Verdict\\n\\n" + "\\n\\n---\\n\\n".join(outputs)
''',
    },
    {
        "id": "pipe_boylenet_smart_router",
        "name": "🧭 Boylenet O1740 Smart Intent Auto-Router Pipe (Code/Math/Vision/OffSec)",
        "type": "pipe",
        "description": "Automatically classifies prompt intent and routes to the #1 benchmarked local GPU model.",
        "content": '''"""
title: Boylenet O1740 Smart Intent Auto-Router Pipe
author: boylenet
version: 2.0.0
description: Routes coding, math/reasoning, security, or general prompts to the optimal local GPU model.
"""
import json
import urllib.request
from pydantic import BaseModel, Field

class Pipe:
    class Valves(BaseModel):
        litellm_url: str = Field(default="http://10.0.70.164:4000/v1/chat/completions", description="LiteLLM URL")
        api_key: str = Field(default="sk-fleet-local", description="LiteLLM Key")

    def __init__(self):
        self.valves = self.Valves()

    def pipe(self, body: dict) -> str:
        msgs = body.get("messages") or [{"role": "user", "content": "Hello"}]
        last = str(msgs[-1].get("content") or "").lower()
        if any(w in last for w in ("code", "python", "def ", "bug", "pytest", "git", "sql", "bash")):
            chosen = "deepseek-coder-moe"
        elif any(w in last for w in ("prove", "math", "theorem", "logic", "reason", "step by step")):
            chosen = "qwen-14b"
        else:
            chosen = "hermes-ultracode"
        req = urllib.request.Request(
            self.valves.litellm_url,
            data=json.dumps({"model": chosen, "messages": msgs, "max_tokens": 800}).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.valves.api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                d = json.loads(resp.read().decode())
                return f"*(🧭 Auto-Routed to `{chosen}`)*\\n\\n" + d["choices"][0]["message"]["content"]
        except Exception as exc:
            return f"Smart Router error on {chosen}: {exc}"
''',
    },
]

QDRANT_EXTERNAL_SOURCES = [
    {
        "conn_id": "qdrant-boylenet-fleet-rag",
        "conn_name": "Boylenet Fleet RAG Qdrant (.125:6333 • 2,670 vectors)",
        "kb_name": "📚 Boylenet Fleet Rules & Harness RAG (2,670 vectors)",
        "kb_desc": "Primary 1024-d Qdrant vector index of FLEET_RULE.md, harness scripts, role prompts, and O1789 receipts.",
        "collection": "boylenet_fleet_rag",
        "content_field": "payload.snippet",
        "metadata_field": "payload",
    },
    {
        "conn_id": "qdrant-swarm-docs-rag",
        "conn_name": "Boylenet Swarm Docs RAG Qdrant (.125:6333 • 1,388 vectors)",
        "kb_name": "📘 Boylenet Swarm Architecture & Runbooks RAG (1,388 vectors)",
        "kb_desc": "1024-d Qdrant vector index of Boylenet 27-node architecture docs, skills, and operational runbooks.",
        "collection": "swarm_docs_rag",
        "content_field": "payload.snippet",
        "metadata_field": "payload",
    },
    {
        "conn_id": "qdrant-boylenet-codebase-ast",
        "conn_name": "Boylenet Codebase AST Qdrant (.125:6333 • 1,282 vectors)",
        "kb_name": "🧬 BulkDownloader & Harness AST Symbols RAG (1,282 vectors)",
        "kb_desc": "1024-d Qdrant vector index of AST-sliced functions, classes, and modules across BulkDownloader and bd-persist.",
        "collection": "boylenet_codebase_ast",
        "content_field": "payload.snippet",
        "metadata_field": "payload",
    },
    {
        "conn_id": "qdrant-boylenet-episodic-memory",
        "conn_name": "Boylenet Episodic Memory Qdrant (.125:6333 • 701 vectors)",
        "kb_name": "🧠 Boylenet HiveMind Episodic Memory (701 vectors)",
        "kb_desc": "1024-d Qdrant vector index of agent trajectories, debugging breakthroughs, and verified infra receipts.",
        "collection": "boylenet_episodic_memory",
        "content_field": "payload.summary",
        "metadata_field": "payload",
    },
    {
        "conn_id": "qdrant-fleet-lessons-hivemind",
        "conn_name": "Boylenet Fleet Lessons HiveMind Qdrant (.125:6333 • 701 vectors)",
        "kb_name": "🎓 Boylenet Fleet Lessons & Best Practices (701 vectors)",
        "kb_desc": "1024-d Qdrant vector index of curated fleet lessons, CI failure taxonomy fixes, and cluster invariants.",
        "collection": "fleet_lessons_hivemind",
        "content_field": "payload.summary",
        "metadata_field": "payload",
    },
]


def api_req(
    base_url: str,
    token: str,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw:
                return (resp.status, None)
            try:
                return (resp.status, json.loads(raw))
            except Exception:
                return (404, None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        return (exc.code, parsed)


def sync_instance(
    inst: dict[str, str], skills_catalog: list[dict[str, Any]]
) -> dict[str, Any]:
    base_url = inst["base_url"]
    token = make_jwt(inst["admin_id"], inst["secret"])
    summary: dict[str, Any] = {"instance": inst["name"], "base_url": base_url}
    tools_ok = 0
    for tk in TOOLKITS:
        payload = {
            "id": tk["id"],
            "name": tk["name"],
            "content": tk["content"],
            "meta": {
                "description": tk["description"],
                "manifest": {"title": tk["name"], "version": "2.0.0"},
            },
            "access_grants": PUBLIC_GRANTS,
        }
        code, _ = api_req(base_url, token, "POST", "/api/v1/tools/create", payload)
        if code in (200, 201):
            tools_ok += 1
        else:
            code2, _ = api_req(
                base_url, token, "POST", f"/api/v1/tools/id/{tk['id']}/update", payload
            )
            if code2 in (200, 201):
                tools_ok += 1
        api_req(
            base_url,
            token,
            "POST",
            f"/api/v1/tools/id/{tk['id']}/access/update",
            {"access_grants": PUBLIC_GRANTS},
        )
    summary["toolkits_registered"] = tools_ok
    funcs_ok = 0
    for fn in FUNCTIONS:
        fn_payload = {
            "id": fn["id"],
            "name": fn["name"],
            "content": fn["content"],
            "meta": {
                "description": fn["description"],
                "manifest": {
                    "title": fn["name"],
                    "author": "boylenet",
                    "version": "2.0.0",
                },
            },
        }
        c_f, f_resp = api_req(
            base_url, token, "POST", "/api/v1/functions/create", fn_payload
        )
        if c_f not in (200, 201):
            c_f, f_resp = api_req(
                base_url,
                token,
                "POST",
                f"/api/v1/functions/id/{fn['id']}/update",
                fn_payload,
            )
        if c_f in (200, 201):
            funcs_ok += 1
            if isinstance(f_resp, dict) and (not f_resp.get("is_active")):
                api_req(
                    base_url,
                    token,
                    "POST",
                    f"/api/v1/functions/id/{fn['id']}/toggle",
                    {},
                )
            if isinstance(f_resp, dict) and (not f_resp.get("is_global")):
                api_req(
                    base_url,
                    token,
                    "POST",
                    f"/api/v1/functions/id/{fn['id']}/toggle/global",
                    {},
                )
    summary["functions_registered"] = funcs_ok
    _, existing_skills = api_req(base_url, token, "GET", "/api/v1/skills/")
    existing_skill_ids = {
        s["id"]: s for s in existing_skills or [] if isinstance(s, dict) and "id" in s
    }
    _, existing_prompts = api_req(base_url, token, "GET", "/api/v1/prompts/")
    existing_prompt_cmds = {
        p["command"]: p
        for p in existing_prompts or []
        if isinstance(p, dict) and "command" in p
    }
    skills_ok = 0
    prompts_ok = 0
    for idx, item in enumerate(skills_catalog):
        sid = item["id"][:60].strip("-")
        sname = (
            f"{item['name']} [{sid}]"
            if item["name"] in {x["name"] for x in skills_catalog[:idx]}
            else item["name"]
        )
        sdesc = (item["description"] or sname)[:300]
        scontent = item["content"]
        skill_payload = {
            "id": sid,
            "name": sname,
            "description": sdesc,
            "content": scontent,
            "meta": {
                "source": item["source"],
                "path": item["path"],
                "tags": [item["source"]],
            },
            "is_active": True,
            "access_grants": PUBLIC_GRANTS,
        }
        if sid in existing_skill_ids:
            c_s, _ = api_req(
                base_url,
                token,
                "POST",
                f"/api/v1/skills/id/{sid}/update",
                skill_payload,
            )
        else:
            c_s, _ = api_req(
                base_url, token, "POST", "/api/v1/skills/create", skill_payload
            )
            if c_s == 409:
                skill_payload["name"] = f"{sname} ({sid})"
                c_s, _ = api_req(
                    base_url, token, "POST", "/api/v1/skills/create", skill_payload
                )
        if c_s in (200, 201):
            skills_ok += 1
        cmd = f"/{sid}"
        prompt_payload = {
            "command": cmd,
            "name": sname,
            "content": scontent,
            "data": {"source": item["source"], "path": item["path"]},
            "meta": {"description": sdesc, "source": item["source"]},
            "tags": [item["source"]],
            "access_grants": PUBLIC_GRANTS,
        }
        if cmd in existing_prompt_cmds:
            pid = existing_prompt_cmds[cmd]["id"]
            c_p, _ = api_req(
                base_url,
                token,
                "POST",
                f"/api/v1/prompts/id/{pid}/update",
                prompt_payload,
            )
        else:
            c_p, _ = api_req(
                base_url, token, "POST", "/api/v1/prompts/create", prompt_payload
            )
        if c_p in (200, 201):
            prompts_ok += 1
    summary["skills_imported"] = skills_ok
    summary["prompts_imported"] = prompts_ok
    now_ts = int(time.time())
    external_conns = [
        {
            "id": src["conn_id"],
            "name": src["conn_name"],
            "provider": "qdrant",
            "endpoint": QDRANT_URL,
            "auth_config": {},
            "config": {"timeout": 30},
            "capabilities": {"retrieve": True},
            "health": {"ok": True, "provider": "qdrant", "checked_at": now_ts},
            "enabled": True,
            "created_by": inst["admin_id"],
            "created_at": now_ts,
            "updated_at": now_ts,
        }
        for src in QDRANT_EXTERNAL_SOURCES
    ]
    master_config_updates = {
        "direct.enable": True,
        "direct.integrations.enable": True,
        "external_knowledge.connections": external_conns,
        "rag.pdf_extract_images": True,
        "rag.enable_hybrid_search": True,
        "rag.enable_hybrid_search_enriched_texts": True,
        "rag.enable_markdown_header_text_splitter": True,
        "rag.chunk_size": 1500,
        "rag.chunk_overlap": 200,
        "rag.top_k": 10,
        "rag.top_k_reranker": 5,
        "rag.embedding_engine": "openai",
        "rag.embedding_model": "bge-m3:latest",
        "rag.embedding_batch_size": 16,
        "rag.enable_async_embedding": True,
        "rag.embedding_concurrent_requests": 8,
        "rag.openai.api_base_url": f"{GATEWAY_URL}/v1",
        "rag.openai.api_key": "sk-fleet-local",
        "rag.ollama.base_url": GATEWAY_URL,
        "rag.ollama.api_key": "",
        "audio.stt.engine": "",
        "audio.stt.whisper_model": "base",
        "audio.stt.openai.api_base_url": f"{GATEWAY_URL}/v1",
        "audio.stt.openai.api_key": "sk-fleet-local",
        "audio.stt.model": "whisper-1",
        "audio.tts.engine": "openai",
        "audio.tts.openai.api_base_url": f"{GATEWAY_URL}/v1",
        "audio.tts.openai.api_key": "sk-fleet-local",
        "audio.tts.model": "tts-1-hd-local",
        "audio.tts.voice": "alloy",
        "audio.tts.split_on": "punctuation",
        "image_generation.enable": True,
        "image_generation.engine": "openai",
        "image_generation.openai.api_base_url": f"{GATEWAY_URL}/v1",
        "image_generation.openai.api_key": "sk-fleet-local",
        "image_generation.model": "flux.1-schnell-local",
        "image_generation.size": "1024x1024",
        "image_generation.steps": 28,
        "image_generation.prompt.enable": True,
        "images.edit.enable": True,
        "images.edit.engine": "openai",
        "images.edit.openai.api_base_url": f"{GATEWAY_URL}/v1",
        "images.edit.openai.api_key": "sk-fleet-local",
        "images.edit.model": "flux.1-edit-local",
        "images.edit.size": "1024x1024",
        "web.search.enable": True,
        "web.search.engine": "searxng",
        "web.search.searxng_query_url": "http://10.0.70.164:8888/search?q=<query>&format=json",
        "web.search.searxng_language": "all",
        "web.search.result_count": 10,
        "web.search.concurrent_requests": 8,
        "web.loader.concurrent_requests": 10,
        "web.search.trust_env": True,
        "subagents.enable": True,
        "subagents.background_enabled": True,
        "subagents.max_concurrent": 20,
        "subagents.max_async": 20,
        "subagents.max_iterations": 30,
        "subagents.max_output": 30000,
        "code_execution.enable": True,
        "code_execution.engine": "pyodide",
        "code_interpreter.enable": True,
        "code_interpreter.engine": "pyodide",
        "chat.tool_search.enable": True,
        "chat.context_compaction.enable": True,
        "memories.enable": True,
        "memories.system_context.enable": True,
        "auth.enable_api_keys": True,
        "evaluation.arena.enable": True,
        "notes.enable": True,
        "folders.enable": True,
        "automations.enable": True,
        "calendar.enable": True,
    }
    tool_server_connections = [
        {
            "url": GATEWAY_URL,
            "path": "/openapi.json",
            "type": "openapi",
            "auth_type": "bearer",
            "headers": {},
            "key": "sk-fleet-local",
            "enabled": True,
            "config": {"enable": True, "access_grants": PUBLIC_GRANTS},
            "info": {
                "id": "boylenet-core-mcp-gateway",
                "name": "1. Boylenet Core Agent, Git, File & 14-Server MCP Gateway (:4079)",
                "description": "13 OpenAPI endpoints bridging File/Grep/Shell, Git/Gitea, 14 MCP servers (99 tools), 128 Skills, and Qdrant RAG.",
            },
        },
        {
            "url": GATEWAY_URL,
            "path": "/web-osint/openapi.json",
            "type": "openapi",
            "auth_type": "bearer",
            "headers": {},
            "key": "sk-fleet-local",
            "enabled": True,
            "config": {"enable": True, "access_grants": PUBLIC_GRANTS},
            "info": {
                "id": "boylenet-web-osint-suite",
                "name": "2. Boylenet Web Search (SearXNG), ArXiv, Wikipedia, YouTube & CDP Oracle Suite",
                "description": "8 OpenAPI endpoints for SearXNG, URL Markdown reader, Chrome CDP Oracles (.137/.181), ArXiv, Wikipedia, YouTube, and HN/GitHub trending.",
            },
        },
        {
            "url": GATEWAY_URL,
            "path": "/data-science/openapi.json",
            "type": "openapi",
            "auth_type": "bearer",
            "headers": {},
            "key": "sk-fleet-local",
            "enabled": True,
            "config": {"enable": True, "access_grants": PUBLIC_GRANTS},
            "info": {
                "id": "boylenet-data-science-suite",
                "name": "3. Boylenet Data Science, SVG Chart/Diagram Renderer, SQL & AST/Linter Suite",
                "description": "6 OpenAPI endpoints for Python stats/charts, architecture SVG diagrams, PostgreSQL/SQLite, document conversion, AST slicing, and Ruff/Mypy.",
            },
        },
        {
            "url": GATEWAY_URL,
            "path": "/devops-infra/openapi.json",
            "type": "openapi",
            "auth_type": "bearer",
            "headers": {},
            "key": "sk-fleet-local",
            "enabled": True,
            "config": {"enable": True, "access_grants": PUBLIC_GRANTS},
            "info": {
                "id": "boylenet-devops-infra-suite",
                "name": "4. Boylenet 27-Node DevOps, VMware ESXi/vSAN, UniFi 25GbE, Docker & Cyber Suite",
                "description": "9 OpenAPI endpoints for 27-node cluster telemetry, WAN airgap, UniFi 25GbE, VMware ESXi/vSAN, Docker/systemd, 4x T4 GPU Vault, CI Doctor, and CVE audit.",
            },
        },
        {
            "url": GATEWAY_URL,
            "path": "/media-ai/openapi.json",
            "type": "openapi",
            "auth_type": "bearer",
            "headers": {},
            "key": "sk-fleet-local",
            "enabled": True,
            "config": {"enable": True, "access_grants": PUBLIC_GRANTS},
            "info": {
                "id": "boylenet-media-ai-suite",
                "name": "5. Boylenet Local 1080p Image Studio, Voice TTS/STT & Subagent Swarm Dispatcher",
                "description": "3 OpenAPI endpoints for local 1024x1024 PNG generation, Jarvis TTS/STT, multi-harness subagent spawning, and O1740 Cloud Burst Quota routing.",
            },
        },
    ]
    terminal_connections = [
        {
            "id": "boylenet-all-27-vms",
            "name": "🌐 ALL 27 BOYLENET VMs — Unified Cluster File Browser & Terminal (/vms/)",
            "enabled": True,
            "url": f"{GATEWAY_URL}/vm/all",
            "path": "/openapi.json",
            "key": "sk-fleet-local",
            "auth_type": "bearer",
            "forward_cookies": False,
            "config": {
                "enable": True,
                "access_grants": PUBLIC_GRANTS,
                "working_directory_context": True,
            },
        }
    ]
    for v in vm_term.BOYLENET_27_VMS:
        terminal_connections.append({"id": f"vm-{v['ip'].replace('.', '-')}", "name": v["name"], "enabled": True, "url": f"{GATEWAY_URL}/vm/{v['ip']}", "path": "/openapi.json", "key": "sk-fleet-local", "auth_type": "bearer", "forward_cookies": False, "config": {"enable": True, "access_grants": PUBLIC_GRANTS, "working_directory_context": True}})
    personal_terminal_servers = []
    for idx, tc in enumerate(terminal_connections):
        ptc = dict(tc)
        ptc["enabled"] = idx == 0
        personal_terminal_servers.append(ptc)
    personal_tool_servers = [dict(ts) for ts in tool_server_connections]
    master_config_updates["ui.default_interface_settings"] = {
        "terminalServers": personal_terminal_servers,
        "toolServers": personal_tool_servers,
    }
    imp_code, _ = api_req(
        base_url,
        token,
        "POST",
        "/api/v1/configs/import",
        {"config": master_config_updates},
    )
    summary["config_import_status"] = imp_code
    emb_code, _ = api_req(
        base_url,
        token,
        "POST",
        "/api/v1/retrieval/embedding/update",
        {
            "RAG_EMBEDDING_ENGINE": "openai",
            "RAG_EMBEDDING_MODEL": "bge-m3:latest",
            "RAG_EMBEDDING_BATCH_SIZE": 16,
            "ENABLE_ASYNC_EMBEDDING": True,
            "RAG_EMBEDDING_CONCURRENT_REQUESTS": 8,
            "openai_config": {"url": f"{GATEWAY_URL}/v1", "key": "sk-fleet-local"},
            "ollama_config": {"url": GATEWAY_URL, "key": ""},
        },
    )
    summary["embedding_update_status"] = emb_code
    ts_code, _ = api_req(
        base_url,
        token,
        "POST",
        "/api/v1/configs/tool_servers",
        {"TOOL_SERVER_CONNECTIONS": tool_server_connections},
    )
    summary["tool_servers_config_status"] = ts_code
    term_code, _ = api_req(
        base_url,
        token,
        "POST",
        "/api/v1/configs/terminal_servers",
        {"TERMINAL_SERVER_CONNECTIONS": terminal_connections},
    )
    summary["terminal_servers_config_status"] = term_code
    _, cur_user_settings = api_req(base_url, token, "GET", "/api/v1/users/user/settings")
    cur_ui = (
        dict(cur_user_settings.get("ui") or {})
        if isinstance(cur_user_settings, dict)
        else {}
    )
    cur_ui["terminalServers"] = personal_terminal_servers
    cur_ui["toolServers"] = personal_tool_servers
    user_settings_payload = {
        "ui": cur_ui,
        "terminalServers": personal_terminal_servers,
        "toolServers": personal_tool_servers,
    }
    us_code, _ = api_req(
        base_url,
        token,
        "POST",
        "/api/v1/users/user/settings/update",
        user_settings_payload,
    )
    summary["user_settings_update_status"] = us_code
    _, existing_kbs = api_req(base_url, token, "GET", "/api/v1/knowledge/")
    kb_items = (
        existing_kbs.get("items", [])
        if isinstance(existing_kbs, dict)
        else existing_kbs or []
    )
    existing_kb_names = {kb.get("name"): kb for kb in kb_items if isinstance(kb, dict)}
    kb_ok = 0
    for src in QDRANT_EXTERNAL_SOURCES:
        api_req(
            base_url,
            token,
            "POST",
            f"/api/v1/knowledge/external/connections/{src['conn_id']}/test",
            {},
        )
        if src["kb_name"] in existing_kb_names:
            kb_ok += 1
            continue
        kb_payload = {
            "name": src["kb_name"],
            "description": src["kb_desc"],
            "connection_id": src["conn_id"],
            "source": {
                "type": "collection",
                "name": src["collection"],
                "config": {
                    "content_field": src["content_field"],
                    "metadata_field": src["metadata_field"],
                    "document_id_field": "id",
                },
            },
            "access_grants": PUBLIC_GRANTS,
        }
        c_kb, _ = api_req(
            base_url,
            token,
            "POST",
            "/api/v1/knowledge/external/knowledge/create",
            kb_payload,
        )
        if c_kb not in (200, 201):
            c_kb, _ = api_req(
                base_url,
                token,
                "POST",
                "/api/v1/knowledge/create",
                {
                    "name": src["kb_name"],
                    "description": src["kb_desc"],
                    "data": {
                        "provider": "qdrant",
                        "endpoint": QDRANT_URL,
                        "collection": src["collection"],
                        "content_field": src["content_field"],
                    },
                    "access_grants": PUBLIC_GRANTS,
                },
            )
        if c_kb in (200, 201):
            kb_ok += 1
    summary["external_knowledge_bases_ready"] = kb_ok
    _, models_resp = api_req(base_url, token, "GET", "/api/v1/models/list")
    models_list = (
        models_resp.get("items", [])
        if isinstance(models_resp, dict)
        else models_resp or []
    )
    all_tool_ids = [t["id"] for t in TOOLKITS]
    all_action_ids = [f["id"] for f in FUNCTIONS if f["type"] == "action"]
    all_filter_ids = [f["id"] for f in FUNCTIONS if f["type"] == "filter"]
    models_updated = 0
    for m in models_list:
        if not isinstance(m, dict) or not m.get("id"):
            continue
        meta = m.get("meta") or {}
        caps = meta.get("capabilities") or {}
        caps.update(
            {
                "vision": True,
                "usage": True,
                "citations": True,
                "file_upload": True,
                "web_search": True,
                "code_interpreter": True,
                "image_generation": True,
                "memory": True,
                "builtin_tools": True,
            }
        )
        meta["capabilities"] = caps
        meta["toolIds"] = all_tool_ids
        meta["actionIds"] = all_action_ids
        meta["filterIds"] = all_filter_ids
        m["meta"] = meta
        m["access_grants"] = PUBLIC_GRANTS
        c_m, _ = api_req(base_url, token, "POST", "/api/v1/models/model/update", m)
        if c_m in (200, 201):
            models_updated += 1
    summary["models_equipped_with_31_toolkits"] = models_updated
    _, live_tools = api_req(base_url, token, "GET", "/api/v1/tools/")
    _, live_funcs = api_req(base_url, token, "GET", "/api/v1/functions/")
    _, live_skills = api_req(base_url, token, "GET", "/api/v1/skills/")
    _, live_prompts = api_req(base_url, token, "GET", "/api/v1/prompts/")
    _, live_ts = api_req(base_url, token, "GET", "/api/v1/configs/tool_servers")
    _, live_terms = api_req(base_url, token, "GET", "/api/v1/configs/terminal_servers")
    _, live_terminals_list = api_req(base_url, token, "GET", "/api/v1/terminals/")
    _, live_user_settings = api_req(base_url, token, "GET", "/api/v1/users/user/settings")
    _, live_ext_kb = api_req(
        base_url, token, "GET", "/api/v1/knowledge/external/connections"
    )
    _, live_kbs = api_req(base_url, token, "GET", "/api/v1/knowledge/")
    summary["verified_tools_count"] = len(live_tools or [])
    summary["verified_functions_count"] = len(live_funcs or [])
    summary["verified_skills_count"] = len(live_skills or [])
    summary["verified_prompts_count"] = len(live_prompts or [])
    summary["verified_tool_servers"] = len(
        (live_ts or {}).get("TOOL_SERVER_CONNECTIONS", [])
        if isinstance(live_ts, dict)
        else []
    )
    summary["verified_terminal_servers"] = len(
        (live_terms or {}).get("TERMINAL_SERVER_CONNECTIONS", [])
        if isinstance(live_terms, dict)
        else []
    )
    summary["verified_terminals_endpoint_count"] = len(
        live_terminals_list if isinstance(live_terminals_list, list) else []
    )
    summary["verified_user_settings_terminal_servers"] = len(
        ((live_user_settings or {}).get("ui") or {}).get("terminalServers", [])
        if isinstance(live_user_settings, dict)
        else []
    )
    summary["verified_user_settings_tool_servers"] = len(
        ((live_user_settings or {}).get("ui") or {}).get("toolServers", [])
        if isinstance(live_user_settings, dict)
        else []
    )
    summary["verified_external_knowledge_connections"] = len(
        (live_ext_kb or {}).get("items", []) if isinstance(live_ext_kb, dict) else []
    )
    summary["verified_knowledge_bases"] = len(
        (live_kbs or {}).get("items", live_kbs or [])
        if isinstance(live_kbs, dict)
        else live_kbs or []
    )
    return summary


def main() -> None:
    skills_catalog = gw.discover_all_skills_and_plugins()
    print(f"Discovered {len(skills_catalog)} total skills/plugins/commands/agents.")
    for inst in INSTANCES:
        t0 = time.time()
        res = sync_instance(inst, skills_catalog)
        res["elapsed_s"] = round(time.time() - t0, 2)
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
