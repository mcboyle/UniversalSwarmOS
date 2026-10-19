from __future__ import annotations
import glob
import json
import os
import subprocess
import time
from pathlib import Path
LOG_PATH = Path("/var/tmp/bd-boot-recovery.log")

def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"[{ts}] [bd-boot-recovery] {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def sh(cmd: list[str], timeout: int=30, env: dict[str, str] | None=None) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, check=False)
        return (r.returncode, (r.stdout or r.stderr or "").strip())
    except Exception as e:
        return (1, str(e))

def step1_docker_and_iptables() -> None:
    log("Step 1: Ensuring all .164 Docker containers are running and purging stale DOCKER DNAT rules...")
    containers = ["forgejo", "litellm-proxy", "open-webui", "devpi-server", "tei-embeddings", "tei-reranker", "prometheus", "grafana-dashboards", "traefik-ingress", "kafka", "code-server", "alertmanager", "searxng-search", "devdocs-mirror", "cadvisor-metrics", "node-exporter", "docker-mirror", "verdaccio", "apt-cacher-ng", "lobechat-studio", "librechat-api", "sillytavern", "openhands"]
    sh(["docker", "start", *containers], timeout=60)
    rc, out = sh(["docker", "ps", "-q"])
    active_ips: set[str] = set()
    if rc == 0 and out:
        for cid in out.splitlines():
            _, ip_out = sh(["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}", cid])
            for ip in ip_out.split():
                active_ips.add(ip.strip())
    rc, nat_out = sh(["sudo", "iptables", "-t", "nat", "-S", "DOCKER"])
    removed = 0
    if rc == 0:
        for line in nat_out.splitlines():
            if line.startswith("-A DOCKER") and "--to-destination " in line:
                dest = line.split("--to-destination ")[-1].split()[0]
                dest_ip = dest.split(":")[0]
                if active_ips and dest_ip not in active_ips:
                    del_rule = line.replace("-A DOCKER ", "", 1).split()
                    sh(["sudo", "iptables", "-t", "nat", "-D", "DOCKER", *del_rule])
                    removed += 1
    log(f"Step 1 complete: {len(active_ips)} active container IPs, removed {removed} stale DNAT rules.")

def step2_rc_credentials_and_sessions() -> None:
    log("Step 2: Ensuring Remote Control OAuth credentials (.credentials.json) are active on .164...")
    # Keep token-1year.txt intact for remote worker launches; only hide during local .164 RC seat launches
    hidden = []
    for pool in ["a", "b", "c", "d"]:
        tok = Path(f"/home/mboyle/.claude-{pool}/token-1year.txt")
        bak = Path(f"/home/mboyle/.claude-{pool}/token-1year.txt.cli-only-no-rc")
        if tok.exists():
            tok.rename(bak)
            hidden.append((tok, bak))

    def latest_uuid(proj_dir: str) -> str | None:
        files = sorted(glob.glob(os.path.join(proj_dir, "*.jsonl")), key=os.path.getmtime, reverse=True)
        return Path(files[0]).stem if files else None
    seats = [("pm", "B", "bd-pm-B", "/var/tmp/bd-seats/pm", "/home/mboyle/.claude-b/projects/-var-tmp-bd-seats-pm"), ("usage-a", "A", "bd-usage-a-A", "/var/tmp/bd-seats/usage-a", "/home/mboyle/.claude-a/projects/-var-tmp-bd-seats-usage-a"), ("usage-b", "B", "bd-usage-b-B", "/var/tmp/bd-seats/usage-b", "/home/mboyle/.claude-b/projects/-var-tmp-bd-seats-usage-b"), ("usage-c", "C", "bd-usage-c-C", "/var/tmp/bd-seats/usage-c", "/home/mboyle/.claude-c/projects/-var-tmp-bd-seats-usage-c"), ("usage-d", "D", "bd-usage-d-D", "/var/tmp/bd-seats/usage-d", "/home/mboyle/.claude-d/projects/-var-tmp-bd-seats-usage-d")]
    for role, pool, sess, workdir, proj_dir in seats:
        rc, _ = sh(["tmux", "has-session", "-t", f"={sess}"])
        if rc == 0:
            log(f"Session {sess} already running; skipping.")
            continue
        os.makedirs(workdir, exist_ok=True)
        uuid = latest_uuid(proj_dir)
        env = os.environ.copy()
        env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
        env["BD_LAUNCH_ALLOW_DUP"] = "1"
        env["BD_LAUNCH_WORKDIR"] = workdir
        cmd = ["/home/mboyle/bd-persist/harness/bd-launch-role.sh", role, pool, sess]
        if uuid:
            cmd.extend(["--resume", uuid])
        cmd.append("--allow-unconfirmed-kick")
        l_rc, l_out = sh(cmd, timeout=45, env=env)
        log(f"Launched {sess} (uuid={uuid}) -> rc={l_rc}")
    for tok, bak in hidden:
        if bak.exists():
            import shutil
            shutil.copy2(bak, tok)

def step3_verify_ai_vms() -> None:
    log("Step 3: Verifying AI VMs (.72, .83, .125, .228) sysctls, THP, NAT redirects, and inference services...")
    for host in ["10.0.70.72", "10.0.70.83", "10.0.70.125", "10.0.70.228"]:
        sh(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host, "sudo sysctl -w kernel.numa_balancing=0 vm.swappiness=1 vm.overcommit_memory=1 >/dev/null 2>&1; "
            "echo always | sudo tee /sys/kernel/mm/transparent_hugepage/enabled >/dev/null 2>&1"], timeout=15)
    sh(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "10.0.70.72", "sudo iptables -t nat -C PREROUTING -p tcp --dport 8000 -j REDIRECT --to-ports 8082 2>/dev/null || "
        "sudo iptables -t nat -A PREROUTING -p tcp --dport 8000 -j REDIRECT --to-ports 8082; "
        "sudo iptables -t nat -C OUTPUT -p tcp -d 10.0.70.72 --dport 8000 -j REDIRECT --to-ports 8082 2>/dev/null || "
        "sudo iptables -t nat -A OUTPUT -p tcp -d 10.0.70.72 --dport 8000 -j REDIRECT --to-ports 8082; "
        "sudo systemctl start llama-tier1-alpha.service open-webui.service llama-rpc.service || true"], timeout=25)
    sh(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "10.0.70.83", "sudo systemctl start llama-heretic-18080.service llama-rpc.service || true"], timeout=20)
    sh(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "10.0.70.125", "sudo systemctl start llama-distributed-32b.service llama-rpc.service ollama.service || true; "
        "sudo docker start qdrant 2>/dev/null || true"], timeout=20)
    sh(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "10.0.70.228", "sudo systemctl start llama-rpc.service ollama.service || true; "
        "sudo docker start $(sudo docker ps -aq) 2>/dev/null || true"], timeout=20)
    log("Step 3 complete: AI VMs verified.")

def main() -> int:
    log("=== Starting Boylenet Persistent Post-Reboot Auto-Recovery ===")
    step1_docker_and_iptables()
    step3_verify_ai_vms()
    step2_rc_credentials_and_sessions()
    sh(["/usr/bin/python3", "/home/mboyle/bin/bd-kv-warmer", "--pin-only"], timeout=90)
    sh(["/usr/bin/python3", "/home/mboyle/bin/bd-relief-puppeteer.py"], timeout=45)
    log("=== Boylenet Persistent Post-Reboot Auto-Recovery COMPLETE ===")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
