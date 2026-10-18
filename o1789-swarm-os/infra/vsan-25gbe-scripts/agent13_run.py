import ssl
import subprocess
import json
import time
import datetime
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import vsanapiutils
OUT_DIR = "/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade"

def run_cmd(cmd):
    p = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return (p.returncode, p.stdout, p.stderr)

def get_vc():
    ctx = ssl._create_unverified_context()
    si = SmartConnect(host="10.0.20.70", user="Administrator@boylenet.themfboyles.com", pwd="Matt99!!", sslContext=ctx)
    return (si, ctx)

def query_space(si, ctx, cluster):
    vcMos = vsanapiutils.GetVsanVcMos(si._stub, context=ctx, version="vsan.version.version23")
    space_sys = vcMos["vsan-cluster-space-report-system"]
    u = space_sys.QuerySpaceUsage(cluster=cluster)
    ds_cap = None
    ds_free = None
    for ds in cluster.datastore:
        if ds.name == "vsanDatastore":
            ds.RefreshDatastore()
            ds_cap = ds.summary.capacity
            ds_free = ds.summary.freeSpace
    detail = {}
    if getattr(u, "spaceDetail", None) and getattr(u.spaceDetail, "spaceUsageByObjectType", None):
        for item in u.spaceDetail.spaceUsageByObjectType:
            detail[item.objType] = {"usedB": getattr(item, "usedB", None), "reservedCapacityB": getattr(item, "reservedCapacityB", None), "overheadB": getattr(item, "overheadB", None), "primaryCapacityB": getattr(item, "primaryCapacityB", None), "provisionCapacityB": getattr(item, "provisionCapacityB", None)}
    return {"timestamp_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "totalCapacityB": u.totalCapacityB, "totalCapacityTiB": round(u.totalCapacityB / 1024 ** 4, 4), "totalCapacityTB": round(u.totalCapacityB / 1000 ** 4, 4), "freeCapacityB": u.freeCapacityB, "freeCapacityTiB": round(u.freeCapacityB / 1024 ** 4, 4), "freeCapacityTB": round(u.freeCapacityB / 1000 ** 4, 4), "usedCapacityB": u.totalCapacityB - u.freeCapacityB, "usedCapacityTiB": round((u.totalCapacityB - u.freeCapacityB) / 1024 ** 4, 4), "usedCapacityTB": round((u.totalCapacityB - u.freeCapacityB) / 1000 ** 4, 4), "primaryCapacityB": getattr(u, "primaryCapacityB", None), "provisionCapacityB": getattr(u, "provisionCapacityB", None), "reservedCapacityB": getattr(u, "reservedCapacityB", None), "ds_capacityB": ds_cap, "ds_capacityTiB": round(ds_cap / 1024 ** 4, 4) if ds_cap else None, "ds_capacityTB": round(ds_cap / 1000 ** 4, 4) if ds_cap else None, "ds_freeSpaceB": ds_free, "ds_freeSpaceTiB": round(ds_free / 1024 ** 4, 4) if ds_free else None, "ds_freeSpaceTB": round(ds_free / 1000 ** 4, 4) if ds_free else None, "spaceUsageByObjectType": detail}

def parse_vsan_storage_list(text):
    disks = []
    cur = {}
    cur_dev = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" "):
            if cur_dev and cur:
                disks.append(cur)
            cur_dev = line.strip()
            cur = {"Device": cur_dev}
        elif ":" in line:
            k, v = line.split(":", 1)
            cur[k.strip()] = v.strip()
    if cur_dev and cur:
        disks.append(cur)
    return disks

def main():
    results = {}
    si, ctx = get_vc()
    content = si.RetrieveContent()
    cluster = None
    for dc in content.rootFolder.childEntity:
        for c in dc.hostFolder.childEntity:
            if c.name == "Boylenet Cluster":
                cluster = c
                break
    print("1. Capturing BEFORE space usage and esxi03 storage list...")
    results["space_before"] = query_space(si, ctx, cluster)
    rc_dev, out_dev, err_dev = run_cmd("govc host.esxcli -u 'https://root:Matt99!!@10.0.20.43/sdk' -k storage core device list -d naa.5000cca06cac4660")
    results["device_info_before"] = {"rc": rc_dev, "stdout": out_dev, "stderr": err_dev}
    rc_vdq, out_vdq, err_vdq = run_cmd("govc host.esxcli -u 'https://root:Matt99!!@10.0.20.43/sdk' -k vsan storage list")
    with open(f"{OUT_DIR}/agent13_esxi03_vsan_storage_before.txt", "w") as f:
        f.write(out_vdq)
    disks_before = parse_vsan_storage_list(out_vdq)
    dg_5288_before = [d for d in disks_before if d.get("VSAN Disk Group UUID") == "528858fc-a4c6-04be-2085-4510652651c2"]
    results["esxi03_storage_before"] = {"rc": rc_vdq, "total_vsan_disks": len(disks_before), "dg_528858fc_disks_count": len(dg_5288_before), "dg_528858fc_disks": dg_5288_before, "all_disks": disks_before}
    print(f"   Before: esxi03 total vSAN disks={len(disks_before)}, DG 528858fc disks={len(dg_5288_before)}")
    has_4660_before = any((d.get("Device") == "naa.5000cca06cac4660" for d in disks_before))
    print(f"   naa.5000cca06cac4660 already in vSAN before? {has_4660_before}")
    if not has_4660_before:
        print("2. Claiming naa.5000cca06cac4660 into DG 528858fc (cache SSD naa.5000cca06cab3ef0) on esxi03...")
        add_cmd = "govc host.esxcli -u https://root:Matt99!!@10.0.20.43/sdk -k vsan storage add -s naa.5000cca06cab3ef0 -d naa.5000cca06cac4660"
        rc_add, out_add, err_add = run_cmd(add_cmd)
        results["vsan_storage_add"] = {"command": add_cmd, "rc": rc_add, "stdout": out_add, "stderr": err_add, "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        print(f"   vsan storage add RC={rc_add}, stdout={out_add!r}, stderr={err_add!r}")
        time.sleep(8)
    else:
        results["vsan_storage_add"] = {"note": "already present"}
    print("3. Capturing AFTER esxi03 storage list and space usage...")
    rc_vdq_after, out_vdq_after, err_vdq_after = run_cmd("govc host.esxcli -u 'https://root:Matt99!!@10.0.20.43/sdk' -k vsan storage list")
    with open(f"{OUT_DIR}/agent13_esxi03_vsan_storage_after.txt", "w") as f:
        f.write(out_vdq_after)
    disks_after = parse_vsan_storage_list(out_vdq_after)
    dg_5288_after = [d for d in disks_after if d.get("VSAN Disk Group UUID") == "528858fc-a4c6-04be-2085-4510652651c2"]
    disk_4660_entry = next((d for d in disks_after if d.get("Device") == "naa.5000cca06cac4660"), None)
    results["esxi03_storage_after"] = {"rc": rc_vdq_after, "total_vsan_disks": len(disks_after), "dg_528858fc_disks_count": len(dg_5288_after), "dg_528858fc_disks": dg_5288_after, "disk_4660_entry": disk_4660_entry, "all_disks": disks_after}
    for h in cluster.host:
        if h.name == "10.0.20.43" or "esxi03" in h.name:
            try:
                h.configManager.storageSystem.RefreshStorageSystem()
                h.configManager.vsanSystem.UpdateVsan_Task()
            except Exception as e:
                pass
    time.sleep(5)
    results["space_after"] = query_space(si, ctx, cluster)
    print(f"   After space: totalCapacityTiB={results['space_after']['totalCapacityTiB']} TiB ({results['space_after']['totalCapacityTB']} TB), freeCapacityTiB={results['space_after']['freeCapacityTiB']} TiB ({results['space_after']['freeCapacityTB']} TB)")
    print("4. Auditing and unregistering orphaned lens-* VMs...")
    container = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
    all_vms_before = list(container.view)
    container.Destroy()
    orphaned_lens_before = []
    all_orphaned_before = []
    for vm in sorted(all_vms_before, key=lambda x: x.name):
        conn_state = vm.runtime.connectionState
        if conn_state == "orphaned":
            all_orphaned_before.append({"name": vm.name, "moId": vm._moId, "connectionState": conn_state})
        if conn_state == "orphaned" and vm.name.startswith("lens-"):
            committed_b = getattr(vm.summary.storage, "committed", 0) if getattr(vm.summary, "storage", None) else 0
            uncommitted_b = getattr(vm.summary.storage, "uncommitted", 0) if getattr(vm.summary, "storage", None) else 0
            vm_path = getattr(vm.summary.config, "vmPathName", None) if getattr(vm.summary, "config", None) else None
            orphaned_lens_before.append({"name": vm.name, "moId": vm._moId, "connectionState": conn_state, "powerState": vm.runtime.powerState, "committedB": committed_b, "uncommittedB": uncommitted_b, "vmPathName": vm_path, "obj": vm})
    print(f"   Found {len(orphaned_lens_before)} orphaned lens-* VMs (out of {len(all_orphaned_before)} total orphaned VMs, {len(all_vms_before)} total VMs)")
    unreg_receipts = []
    for item in orphaned_lens_before:
        vm_obj = item.pop("obj")
        try:
            vm_obj.UnregisterVM()
            unreg_receipts.append({**item, "unregister_status": "SUCCESS (RC=0)", "error": None})
            print(f"   Unregistered {item['name']} ({item['moId']}) -> SUCCESS")
        except Exception as e:
            unreg_receipts.append({**item, "unregister_status": "FAILED", "error": str(e)})
            print(f"   Unregistered {item['name']} ({item['moId']}) -> FAILED: {e}")
    container2 = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
    all_vms_after = list(container2.view)
    container2.Destroy()
    orphaned_after = [{"name": vm.name, "moId": vm._moId, "connectionState": vm.runtime.connectionState} for vm in sorted(all_vms_after, key=lambda x: x.name) if vm.runtime.connectionState == "orphaned"]
    orphaned_lens_after = [x for x in orphaned_after if x["name"].startswith("lens-")]
    results["vm_inventory_hygiene"] = {"total_vms_before": len(all_vms_before), "total_orphaned_before": len(all_orphaned_before), "orphaned_lens_count_before": len(orphaned_lens_before), "unregistered_vms": unreg_receipts, "total_vms_after": len(all_vms_after), "total_orphaned_after": len(orphaned_after), "orphaned_lens_count_after": len(orphaned_lens_after), "remaining_orphaned_vms": orphaned_after}
    print("5. Running esxcli vsan health cluster list...")
    rc_hlth, out_hlth, err_hlth = run_cmd("govc host.esxcli -u 'https://root:Matt99!!@10.0.20.43/sdk' -k vsan health cluster list")
    with open(f"{OUT_DIR}/agent13_vsan_health_cluster_list.txt", "w") as f:
        f.write(out_hlth)
    results["vsan_health_cluster_list"] = {"rc": rc_hlth, "stdout": out_hlth, "stderr": err_hlth}
    non_green = []
    for line in out_hlth.splitlines():
        parts = line.split()
        if parts and parts[-1] in ("yellow", "red"):
            test_name = " ".join(parts[:-1]).strip()
            rc_t, out_t, err_t = run_cmd(f"govc host.esxcli -u 'https://root:Matt99!!@10.0.20.43/sdk' -k vsan health cluster get -t \"{test_name}\"")
            non_green.append({"test_name": test_name, "status": parts[-1], "rc": rc_t, "stdout": out_t})
    results["vsan_health_non_green_details"] = non_green
    cluster_get_hosts = {}
    for host_ip in ["10.0.20.41", "10.0.20.42", "10.0.20.43", "10.0.20.44"]:
        rc_c, out_c, err_c = run_cmd(f"govc host.esxcli -u 'https://root:Matt99!!@{host_ip}/sdk' -k vsan cluster get")
        cluster_get_hosts[host_ip] = {"rc": rc_c, "stdout": out_c, "stderr": err_c}
    results["vsan_cluster_get_all_hosts"] = cluster_get_hosts
    with open(f"{OUT_DIR}/agent13_results.json", "w") as f:
        json.dump(results, f, indent=2)
    Disconnect(si)
    print("DONE! Saved to agent13_results.json")
if __name__ == "__main__":
    main()
