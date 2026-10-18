import json
import ssl
import subprocess
import sys
import time
import urllib.request
sys.path.insert(0, "/home/mboyle/bin")
import lib_vsphere_govc
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
u, p = lib_vsphere_govc.load_vc_credentials()
ctx = ssl._create_unverified_context()
si = SmartConnect(host="10.0.20.70", user=u, pwd=p, sslContext=ctx)
content = si.RetrieveContent()
dvs = next((d for d in content.viewManager.CreateContainerView(content.rootFolder, [vim.DistributedVirtualSwitch], True).view if d.name == "25GB"))
uplink_pg_key = "dvportgroup-10"
env = {}
with open("/home/mboyle/.config/bd/unifi.env") as f:
    for line in f:
        if "=" in line and (not line.startswith("#")):
            k, v = line.strip().split("=", 1)
            env[k] = v.strip("'\"")
cid = "602232292CA100000000069BFAAB0000000006EB9D760000000062F4D112:2071288107"
sw_id = "c4b8bfa2-f496-46a8-bb31-cda8baf247fb"
stat_url = f"https://api.ui.com/v1/connector/consoles/{cid}/proxy/network/api/s/default/stat/device"
rest_url = f"https://api.ui.com/v1/connector/consoles/{cid}/proxy/network/api/s/default/rest/device/{sw_id}"

def reconfig_host_pnics(host_name, target_pairs):
    for attempt in range(3):
        hm = next((h for h in dvs.config.host if h.config.host.name == host_name))
        current = sorted(((ps.pnicDevice, ps.uplinkPortKey) for ps in hm.config.backing.pnicSpec))
        desired = sorted(((dev, str(pk)) for dev, pk in target_pairs))
        if current == desired:
            return
        spec = vim.dvs.VmwareDistributedVirtualSwitch.ConfigSpec()
        spec.configVersion = dvs.config.configVersion
        hspec = vim.dvs.HostMember.ConfigSpec(operation="edit", host=hm.config.host)
        backing = vim.dvs.HostMember.PnicBacking()
        for dev, pk in target_pairs:
            backing.pnicSpec.append(vim.dvs.HostMember.PnicSpec(pnicDevice=dev, uplinkPortKey=str(pk), uplinkPortgroupKey=uplink_pg_key))
        hspec.backing = backing
        spec.host = [hspec]
        task = dvs.ReconfigureDvs_Task(spec)
        while task.info.state in ("queued", "running"):
            time.sleep(0.5)
        if task.info.state != "success":
            raise RuntimeError(f"ReconfigureDvs_Task failed on {host_name}: {task.info.error}")
        time.sleep(1.5)
    hm = next((h for h in dvs.config.host if h.config.host.name == host_name))
    print(f"  [{host_name}] Verified pnicSpec:", [(ps.pnicDevice, ps.uplinkPortKey) for ps in hm.config.backing.pnicSpec])

def apply_unifi_agg(master_port, members, lag_idx, label):
    req = urllib.request.Request(stat_url, headers={"X-API-KEY": env["UNIFI_API_KEY"], "Accept": "application/json"})
    data = json.loads(urllib.request.urlopen(req, context=ctx, timeout=15).read().decode())
    sw = next((d for d in data["data"] if d["_id"] == sw_id))
    new_overrides = [o for o in sw.get("port_overrides", []) if o.get("port_idx") not in members]
    new_overrides.append({"port_idx": master_port, "setting_preference": "manual", "name": label, "op_mode": "aggregate", "aggregate_members": members, "lag_idx": lag_idx, "speed": 10000, "full_duplex": True, "autoneg": False, "forward": "customize", "tagged_vlan_mgmt": "custom", "native_networkconf_id": "", "excluded_networkconf_ids": ["0ed17ee4-576a-482b-82ef-28ac69fdf370", "735a4415-51cf-43b3-a23d-f1cc4f051d38"], "stp_port_mode": True, "stp_edge_state": "auto", "dot1x_ctrl": "force_authorized", "dot1x_idle_timeout": 300, "lldpmed_enabled": True})
    new_overrides.sort(key=lambda x: x.get("port_idx", 0))
    put_req = urllib.request.Request(rest_url, data=json.dumps({"port_overrides": new_overrides}).encode(), headers={"X-API-KEY": env["UNIFI_API_KEY"], "Content-Type": "application/json", "Accept": "application/json"}, method="PUT")
    put_resp = json.loads(urllib.request.urlopen(put_req, context=ctx, timeout=15).read().decode())
    print(f"  [UniFi P{members[0]}-P{members[-1]} lag_idx={lag_idx}] meta:", put_resp.get("meta"))
    time.sleep(5)
HOSTS = [{"name": "esxi03.boylenet.themfboyles.com", "ip": "10.0.20.43", "keep_pnics": [("vmnic10", "177"), ("vmnic5", "180"), ("vmnic4", "181")], "lag_pnics": [("vmnic9", "383"), ("vmnic11", "384"), ("vmnic8", "385")], "master_port": 10, "members": [10, 11, 12], "lag_idx": 5, "label": "esxi03 - 30G LACP (vmnic9/11/8)"}, {"name": "esxi04.boylenet.themfboyles.com", "ip": "10.0.20.44", "keep_pnics": [("vmnic6", "144")], "lag_pnics": [("vmnic4", "368"), ("vmnic7", "369"), ("vmnic8", "370"), ("vmnic5", "371"), ("vmnic9", "372")], "master_port": 4, "members": [4, 5, 6, 7, 8], "lag_idx": 6, "label": "esxi04 - 50G LACP (vmnic4/7/8/5/9)"}, {"name": "esxi01.boylenet.themfboyles.com", "ip": "10.0.20.41", "keep_pnics": [("vmnic7", "242")], "lag_pnics": [("vmnic4", "378"), ("vmnic5", "379"), ("vmnic9", "380"), ("vmnic8", "381"), ("vmnic6", "382")], "master_port": 13, "members": [13, 14, 15, 16, 17], "lag_idx": 7, "label": "esxi01 - 50G LACP (vmnic4/5/9/8/6)"}]
for h in HOSTS:
    print(f"\n=== Processing {h['name']} ({h['label']}) ===")
    print("  1. Detaching 10G pnics from standalone uplinks (isolating onto 25G uplink)...")
    reconfig_host_pnics(h["name"], h["keep_pnics"])
    print("  2. Setting op_mode=aggregate on USAGGPRO BEFORE teaming...")
    apply_unifi_agg(h["master_port"], h["members"], h["lag_idx"], h["label"])
    print("  3. Attaching 10G pnics to VDS 25GB LAG1...")
    reconfig_host_pnics(h["name"], h["keep_pnics"] + h["lag_pnics"])
    time.sleep(5)
    out = subprocess.check_output(["govc", "host.esxcli", "-u", f"https://root:{p}@{h['ip']}/sdk", "-k", "network", "vswitch", "dvs", "vmware", "lacp", "status", "get"], text=True)
    print(out)
Disconnect(si)
