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
url = f"https://api.ui.com/v1/connector/consoles/{cid}/proxy/network/api/s/default/stat/device"
req = urllib.request.Request(url, headers={"X-API-KEY": env["UNIFI_API_KEY"], "Accept": "application/json"})
data = json.loads(urllib.request.urlopen(req, context=ssl._create_unverified_context(), timeout=15).read().decode())
for d in data.get("data", []):
    if d.get("_id") == "c4b8bfa2-f496-46a8-bb31-cda8baf247fb":
        overrides = {o.get("port_idx"): o for o in d.get("port_overrides", [])}
        for p in d.get("port_table", []):
            idx = p.get("port_idx")
            if idx in range(1, 18) or idx in range(29, 33):
                print(f"P{idx:02d} ({p.get('name')}): up={p.get('up')} spd={p.get('speed')} stp={p.get('stp_state')} op={p.get('op_mode')} ovr={overrides.get(idx)}")
