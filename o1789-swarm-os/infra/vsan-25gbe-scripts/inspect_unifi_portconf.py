import json
import ssl
import urllib.request
env = {}
with open("/home/mboyle/.config/bd/unifi.env") as f:
    for line in f:
        if "=" in line and (not line.startswith("#")):
            k, v = line.strip().split("=", 1)
            env[k] = v.strip("'\"")
cid = "602232292CA100000000069BFAAB0000000006EB9D760000000062F4D112:2071288107"
ctx = ssl._create_unverified_context()
url_pc = f"https://api.ui.com/v1/connector/consoles/{cid}/proxy/network/api/s/default/rest/portconf"
req_pc = urllib.request.Request(url_pc, headers={"X-API-KEY": env["UNIFI_API_KEY"], "Accept": "application/json"})
pc_data = json.loads(urllib.request.urlopen(req_pc, context=ctx, timeout=15).read().decode())
for pc in pc_data.get("data", []):
    print("PORTCONF:", pc.get("_id"), pc.get("name"), pc)
url = f"https://api.ui.com/v1/connector/consoles/{cid}/proxy/network/api/s/default/stat/device"
req = urllib.request.Request(url, headers={"X-API-KEY": env["UNIFI_API_KEY"], "Accept": "application/json"})
data = json.loads(urllib.request.urlopen(req, context=ctx, timeout=15).read().decode())
for d in data.get("data", []):
    if d.get("_id") == "c4b8bfa2-f496-46a8-bb31-cda8baf247fb":
        for o in d.get("port_overrides", []):
            if o.get("port_idx") in (20, 21, 23, 24, 27, 28, 1, 3, 11, 29):
                print("OVR:", o)
