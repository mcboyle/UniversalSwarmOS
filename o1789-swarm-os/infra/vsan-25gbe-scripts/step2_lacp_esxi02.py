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
dvs = None
for d in content.viewManager.CreateContainerView(content.rootFolder, [vim.DistributedVirtualSwitch], True).view:
    if d.name == "25GB":
        dvs = d
        break
hm_esxi02 = None
for hm in dvs.config.host:
    if hm.config.host.name == "esxi02.boylenet.themfboyles.com":
        hm_esxi02 = hm
        break
assert hm_esxi02 is not None, "esxi02 not found in VDS 25GB"
uplink_pg_key = hm_esxi02.config.backing.pnicSpec[0].uplinkPortgroupKey
print("esxi02 current pnicSpec:", [(ps.pnicDevice, ps.uplinkPortKey, ps.uplinkPortgroupKey) for ps in hm_esxi02.config.backing.pnicSpec])

def reconfig_host_pnics(host_obj, pnic_pairs):
    spec = vim.dvs.VmwareDistributedVirtualSwitch.ConfigSpec()
    spec.configVersion = dvs.config.configVersion
    hspec = vim.dvs.HostMember.ConfigSpec()
    hspec.operation = "edit"
    hspec.host = host_obj
    backing = vim.dvs.HostMember.PnicBacking()
    for dev, pkey in pnic_pairs:
        ps = vim.dvs.HostMember.PnicSpec()
        ps.pnicDevice = dev
        ps.uplinkPortKey = str(pkey)
        ps.uplinkPortgroupKey = uplink_pg_key
        backing.pnicSpec.append(ps)
    hspec.backing = backing
    spec.host = [hspec]
    task = dvs.ReconfigureDvs_Task(spec)
    while task.info.state in ("queued", "running"):
        time.sleep(0.5)
    if task.info.state != "success":
        raise RuntimeError(f"ReconfigureDvs_Task failed: {task.info.error}")
print("[STEP 1] Detaching vmnic4, vmnic5, vmnic7 on esxi02 (keeping vmnic6 25G on portKey 211)...")
reconfig_host_pnics(hm_esxi02.config.host, [("vmnic6", "211")])
print("[STEP 1] Done. vmnic4/5/7 are now idle.")
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
req = urllib.request.Request(stat_url, headers={"X-API-KEY": env["UNIFI_API_KEY"], "Accept": "application/json"})
data = json.loads(urllib.request.urlopen(req, context=ctx, timeout=15).read().decode())
sw = next((d for d in data["data"] if d["_id"] == sw_id))
new_overrides = []
for o in sw.get("port_overrides", []):
    if o.get("port_idx") in (1, 2, 3):
        continue
    new_overrides.append(o)
new_overrides.append({"port_idx": 1, "setting_preference": "manual", "name": "esxi02 - 30G LACP (vmnic4/5/7)", "op_mode": "aggregate", "aggregate_members": [1, 2, 3], "lag_idx": 3, "speed": 10000, "full_duplex": True, "autoneg": False, "forward": "customize", "tagged_vlan_mgmt": "custom", "native_networkconf_id": "", "excluded_networkconf_ids": ["0ed17ee4-576a-482b-82ef-28ac69fdf370", "735a4415-51cf-43b3-a23d-f1cc4f051d38"], "stp_port_mode": True, "stp_edge_state": "auto", "dot1x_ctrl": "force_authorized", "dot1x_idle_timeout": 300, "lldpmed_enabled": True})
new_overrides.sort(key=lambda x: x.get("port_idx", 0))
print("[STEP 2] Applying op_mode=aggregate on USAGGPRO Ports 1-3 (lag_idx=3)...")
put_req = urllib.request.Request(rest_url, data=json.dumps({"port_overrides": new_overrides}).encode(), headers={"X-API-KEY": env["UNIFI_API_KEY"], "Content-Type": "application/json", "Accept": "application/json"}, method="PUT")
put_resp = json.loads(urllib.request.urlopen(put_req, context=ctx, timeout=15).read().decode())
print("[STEP 2] UniFi PUT meta:", put_resp.get("meta"))
time.sleep(6)
print("[STEP 3] Binding esxi02 vmnic4->373 (LAG1-0), vmnic5->374 (LAG1-1), vmnic7->375 (LAG1-2), keeping vmnic6->211 (Uplink 6)...")
reconfig_host_pnics(hm_esxi02.config.host, [("vmnic6", "211"), ("vmnic4", "373"), ("vmnic5", "374"), ("vmnic7", "375")])
print("[STEP 3] Bound! Waiting 6s for LACP negotiation...")
time.sleep(6)
out = subprocess.check_output(["govc", "host.esxcli", "-u", f"https://root:{p}@10.0.20.42/sdk", "-k", "network", "vswitch", "dvs", "vmware", "lacp", "status", "get"], text=True)
print("=== esxi02 LACP STATUS ===")
print(out)
req2 = urllib.request.Request(stat_url, headers={"X-API-KEY": env["UNIFI_API_KEY"], "Accept": "application/json"})
data2 = json.loads(urllib.request.urlopen(req2, context=ctx, timeout=15).read().decode())
sw2 = next((d for d in data2["data"] if d["_id"] == sw_id))
for pt in sw2.get("port_table", []):
    if pt.get("port_idx") in (1, 2, 3, 31):
        print(f"USAGGPRO P{pt['port_idx']:02d}: up={pt.get('up')} spd={pt.get('speed')} stp={pt.get('stp_state')} op={pt.get('op_mode')}")
Disconnect(si)
