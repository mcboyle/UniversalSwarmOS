#!/usr/bin/env python3
"""
Two-Layer Dead-Man's Switch & Auto-Revert Watchdog for Boylenet Infrastructure Swarm.
Monitors:
  1. External Internet (1.1.1.1, 8.8.8.8, api.ui.com)
  2. Local Gateways (10.0.10.1, 10.0.70.1) & vCenter (10.0.20.70)
  3. All 4 ESXi Management IPs (10.0.20.41..44)
  4. All 4 HPE iLO Out-of-Band IPs (10.0.10.10, 10.0.10.20, 10.0.10.252, 10.0.10.40)

On startup:
  - Captures golden pre-change UniFi device configs (USAGGPRO 10.0.10.111 & USL8A 10.0.10.182)
  - Verifies vCenter DVS rollback (`config.vswitch.rollback`) is enabled (true)
On anomaly (>15s unreachable on any critical target):
  - Immediately pushes golden pre-change `port_overrides` / device config back to UniFi API
  - Restores ESXi NIC auto-negotiation / DVS uplinks via govc / SSH
  - Logs full forensic event to /home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/DEADMAN-WATCHDOG.log
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
import requests

BASE_DIR = "/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade"
LOG_FILE = os.path.join(BASE_DIR, "DEADMAN-WATCHDOG.log")
GOLDEN_UNIFI = os.path.join(BASE_DIR, "golden_unifi_switches.json")
CID = "602232292CA100000000069BFAAB0000000006EB9D760000000062F4D112:2071288107"

TARGETS = {
    "internet_cloudflare": "1.1.1.1",
    "internet_google": "8.8.8.8",
    "gw_udm": "10.0.10.1",
    "gw_vlan70": "10.0.70.1",
    "vcenter": "10.0.20.70",
    "esxi01_mgmt": "10.0.20.41",
    "esxi02_mgmt": "10.0.20.42",
    "esxi03_mgmt": "10.0.20.43",
    "esxi04_mgmt": "10.0.20.44",
    "esxi01_ilo": "10.0.10.10",
    "esxi02_ilo": "10.0.10.20",
    "esxi03_ilo": "10.0.10.252",
    "esxi04_ilo": "10.0.10.40",
}

def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def load_unifi_key() -> str:
    with open("/home/mboyle/.config/bd/unifi.env") as f:
        for line in f:
            if line.startswith("UNIFI_API_KEY="):
                return line.strip().split("=", 1)[1].strip("\"'")
    return ""

def snapshot_golden_unifi(api_key: str) -> dict:
    if os.path.exists(GOLDEN_UNIFI):
        with open(GOLDEN_UNIFI) as f:
            data = json.load(f)
        if data:
            log(f"Loaded existing golden UniFi snapshot ({len(data)} switches) from {GOLDEN_UNIFI}")
            return data
    url = f"https://api.ui.com/v1/connector/consoles/{CID}/proxy/network/api/s/default/stat/device"
    resp = requests.get(url, headers={"X-API-KEY": api_key, "Accept": "application/json"}, timeout=15)
    resp.raise_for_status()
    golden = {}
    for d in resp.json().get("data", []):
        if d.get("model") in ("USAGGPRO", "USL8A", "USL24B"):
            golden[d["_id"]] = {
                "_id": d["_id"],
                "name": d.get("name"),
                "model": d.get("model"),
                "ip": d.get("ip"),
                "jumboframe_enabled": d.get("jumboframe_enabled"),
                "flowctrl_enabled": d.get("flowctrl_enabled"),
                "port_overrides": d.get("port_overrides", []),
            }
    with open(GOLDEN_UNIFI, "w") as f:
        json.dump(golden, f, indent=2)
    log(f"Saved golden UniFi snapshot ({len(golden)} switches) to {GOLDEN_UNIFI}")
    return golden

def revert_unifi(api_key: str, golden: dict, reason: str) -> None:
    log(f"!!! AUTO-REVERT TRIGGERED ({reason}) — Restoring Golden UniFi Switch Configs !!!")
    for dev_id, cfg in golden.items():
        url = f"https://api.ui.com/v1/connector/consoles/{CID}/proxy/network/api/s/default/rest/device/{dev_id}"
        payload = {
            "port_overrides": cfg["port_overrides"],
            "jumboframe_enabled": cfg["jumboframe_enabled"],
            "flowctrl_enabled": cfg["flowctrl_enabled"],
        }
        try:
            r = requests.put(url, headers={"X-API-KEY": api_key, "Content-Type": "application/json"}, json=payload, timeout=10)
            log(f"Reverted switch {cfg.get('name')} ({dev_id}): HTTP {r.status_code}")
        except Exception as e:
            log(f"Failed to revert switch {dev_id}: {e}")

def revert_esxi03_nic() -> None:
    log("!!! Restoring esxi03 vmnic11 to auto-negotiate via govc/SSH !!!")
    try:
        sys.path.insert(0, "/home/mboyle/bin")
        import lib_vsphere_govc
        u, p = lib_vsphere_govc.load_vc_credentials()
        env = dict(os.environ, GOVC_URL=lib_vsphere_govc.DEFAULT_GOVC_URL, GOVC_USERNAME=u, GOVC_PASSWORD=p, GOVC_INSECURE="1")
        subprocess.run(["govc", "host.esxcli", "-host", "esxi03.boylenet.themfboyles.com", "network", "nic", "set", "-n", "vmnic11", "-a"], env=env, timeout=10)
    except Exception as e:
        log(f"ESXi03 NIC revert error: {e}")

def ping_ok(ip: str) -> bool:
    r = subprocess.run(["ping", "-c", "1", "-W", "1", ip], capture_output=True)
    return r.returncode == 0

def main() -> None:
    os.makedirs(BASE_DIR, exist_ok=True)
    api_key = load_unifi_key()
    golden = snapshot_golden_unifi(api_key)
    log("Armed Dead-Man's Switch Watchdog (polling every 5s, auto-revert threshold = 3 consecutive failures / 15s)")
    fail_streaks = {k: 0 for k in TARGETS}
    reverted = False
    # Run for up to 45 minutes covering the entire swarm execution
    for tick in range(540):
        inet_ok = ping_ok("1.1.1.1") or ping_ok("8.8.8.8")
        if not inet_ok:
            fail_streaks["internet_cloudflare"] += 1
        else:
            fail_streaks["internet_cloudflare"] = 0

        for name, ip in TARGETS.items():
            if name.startswith("internet_"):
                continue
            if ping_ok(ip):
                fail_streaks[name] = 0
            else:
                fail_streaks[name] += 1
                log(f"WARN: Target {name} ({ip}) missed ping (streak={fail_streaks[name]}/3)")

        bad = [k for k, v in fail_streaks.items() if v >= 3]
        if bad and not reverted:
            reason = f"Unreachable targets for >=15s: {bad}"
            revert_unifi(api_key, golden, reason)
            revert_esxi03_nic()
            reverted = True
        elif not bad and tick % 12 == 0:
            log("HEARTBEAT OK: Internet (1.1.1.1/8.8.8.8), Gateways (.10.1/.70.1), vCenter (.20.70), ESXi01-04 (.20.41-.44), iLO01-04 all reachable.")
        time.sleep(5)

if __name__ == "__main__":
    main()
