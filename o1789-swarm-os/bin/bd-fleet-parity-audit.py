import concurrent.futures
import json
import subprocess
HOSTS = [("10.0.70.164", "hub-mesh01 (controller)"), ("10.0.70.25", "ops-mcp01"), ("10.0.70.162", "ops-cicd01"), ("10.0.70.107", "ops-test01"), ("10.0.70.182", "stg-cache01"), ("10.0.70.72", "ai-srv01"), ("10.0.70.125", "ai-infer01"), ("10.0.70.228", "ai-ollama01"), ("10.0.70.83", "aidev / wrk-test01"), ("10.0.70.50", "wrk-bd01"), ("10.0.70.51", "wrk-bd02"), ("10.0.70.52", "wrk-bd03"), ("10.0.70.53", "wrk-bd04"), ("10.0.70.54", "wrk-bd05"), ("10.0.70.194", "wrk-test01"), ("10.0.70.95", "wrk-test02"), ("10.0.70.80", "wrk-test03"), ("10.0.70.82", "wrk-test04"), ("10.0.70.85", "wrk-test05"), ("10.0.70.249", "wrk-test06"), ("10.0.70.84", "wrk-test07"), ("10.0.70.120", "spr-pool01"), ("10.0.70.183", "spr-pool02"), ("10.0.70.149", "spr-pool05"), ("10.0.70.197", "spare1"), ("10.0.70.193", "node1 (spare2)"), ("10.0.70.81", "spare4"), ("10.0.70.185", "spare5"), ("10.0.70.186", "spare6"), ("10.0.70.187", "node2 (spare9)"), ("10.0.70.184", "spare8"), ("10.0.70.196", "spare10"), ("10.0.70.195", "spare11"), ("10.0.70.35", "seatc1"), ("10.0.70.171", "seatc2"), ("10.0.70.121", "cir1"), ("10.0.70.86", "cir2"), ("10.0.70.122", "spare3"), ("10.0.70.224", "spare"), ("10.0.70.198", "kvcache-cx1")]
PROBE_SCRIPT = r'''
export PATH=/home/mboyle/.local/bin:/usr/local/bin:/home/mboyle/bin:/usr/bin:/bin:$PATH
export GEMINI_CLI_TRUSTED_FOLDERS_PATH=/home/mboyle/.gemini/direct_gemini_trustedFolders.json
python3 -c "
import subprocess, os, json, hashlib, concurrent.futures

CMDS = {
    'claude': 'claude --version',
    'codex': 'codex --version',
    'grok': 'grok --version',
    'kimi': 'kimi --version',
    'gemini': 'gemini --version',
    'opencode': 'opencode --version',
    'agy': 'agy --version',
    'caveman': 'caveman --version',
    'codeburn': 'codeburn --version',
    'firecrawl': 'firecrawl --version',
}

def get_out(item):
    k, cmd = item
    try:
        return k, subprocess.check_output(shlex.split(cmd), shell=False, text=True, stderr=subprocess.DEVNULL, timeout=15).strip()
    except Exception:
        return k, 'absent'

def file_sha(p):
    if not os.path.isfile(p): return 'absent'
    try:
        with open(p, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        return 'unreadable'

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    ver_map = dict(ex.map(get_out, CMDS.items()))

skills_dir = '/home/mboyle/.agents/skills'
skills = sorted(os.listdir(skills_dir)) if os.path.isdir(skills_dir) else []

plugins_dir = '/home/mboyle/.agents/plugins'
plugins = sorted(os.listdir(plugins_dir)) if os.path.isdir(plugins_dir) else []

claude_skills = sorted(os.listdir('/home/mboyle/.claude/skills')) if os.path.isdir('/home/mboyle/.claude/skills') else []
codex_skills = sorted(os.listdir('/home/mboyle/.codex/skills')) if os.path.isdir('/home/mboyle/.codex/skills') else []

res = {
    **ver_map,
    'gemini_hooks_sha': file_sha('/home/mboyle/.gemini/config/hooks.json'),
    'claude_settings_sha': file_sha('/home/mboyle/.claude/settings.json'),
    'codex_hooks_sha': file_sha('/home/mboyle/.codex/hooks.json'),
    'skills_count': len(skills),
    'skills': skills,
    'plugins_count': len(plugins),
    'plugins': plugins,
    'claude_skills_count': len(claude_skills),
    'codex_skills_count': len(codex_skills),
    'has_bd_repo': os.path.isdir('/home/mboyle/BulkDownloader'),
    'has_venv': os.path.isdir('/home/mboyle/BulkDownloader/venv'),
    'has_bd_local': os.path.exists('/home/mboyle/bin/bd-claude-local') and os.path.exists('/home/mboyle/bin/bd-ai-harness'),
}
print(json.dumps(res))
"
'''

def audit_host(host_info):
    ip, name = host_info
    if ip == "10.0.70.164":
        cmd = ["bash", "-c", PROBE_SCRIPT]
    else:
        cmd = ["ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no", "-o", "ControlMaster=no", "-o", "ControlPath=none", f"mboyle@{ip}", PROBE_SCRIPT]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE, timeout=35).strip()
        lines = [l for l in out.splitlines() if l.startswith("{") and l.endswith("}")]
        if lines:
            data = json.loads(lines[-1])
            data["status"] = "OK"
            return (ip, name, data)
        else:
            return (ip, name, {"status": "PARSE_ERROR", "raw": out[:100]})
    except Exception as e:
        return (ip, name, {"status": "UNREACHABLE", "error": str(e)[:60]})

def main():
    print(f"Auditing {len(HOSTS)} fleet hosts in parallel...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(audit_host, HOSTS))
    output = {}
    for ip, name, data in results:
        output[ip] = {"name": name, "audit": data}
    with open("/home/mboyle/bd-persist/FLEET_PARITY_AUDIT.json", "w") as f:
        json.dump(output, f, indent=2)
    ok_hosts = [ip for ip, _, d in results if d.get("status") == "OK"]
    print(f"Audit completed ({len(ok_hosts)}/{len(HOSTS)} reachable). Saved to /home/mboyle/bd-persist/FLEET_PARITY_AUDIT.json")
if __name__ == "__main__":
    main()
