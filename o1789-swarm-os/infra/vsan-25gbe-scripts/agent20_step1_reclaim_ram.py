import json
import os
import ssl
import sys
import time
from datetime import datetime, timezone
sys.path.insert(0, "/home/mboyle/bin")
import lib_vsphere_govc
from pyVim.connect import Disconnect, SmartConnect
from pyVmomi import vim
BASE_DIR = "/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade"
OUT_JSON = os.path.join(BASE_DIR, "temporarily_powered_off_vms.json")
STEP1_REPORT = os.path.join(BASE_DIR, "agent20_step1_report.json")
PROTECTED_VM_NAMES = {"Test5", "VC04", "VC04-Peer", "VC04-Witness", "CI/CD", "CI%2fCD", "MCP", "test5", "Cache", "Bittorrent", "bd1", "bd2", "test", "test4", "test3big", "Test2", "test3", "test6", "test7"}
PROTECTED_IPS = {"10.0.70.164", "10.0.20.70", "10.0.70.162", "10.0.70.25", "10.0.70.107", "10.0.70.182", "10.0.70.181", "10.0.70.51", "10.0.70.52", "10.0.70.194", "10.0.70.85", "10.0.70.82", "10.0.70.95", "10.0.70.80", "10.0.70.249", "10.0.70.84"}
TARGETS_BY_HOST = {"esxi01.boylenet.themfboyles.com": ["bd-ci-r1-20261003", "bd-seat-c1-20261003", "bd-seat-c2-20261003", "bd-ci-r2-20261003", "clm-infer-01", "spare6", "bd3"], "esxi02.boylenet.themfboyles.com": ["spare8", "Test", "lens-r3c-cx4-20261014", "kvcache-cx1-20261014", "spare7", "bd4", "bd", "spare2"], "esxi03.boylenet.themfboyles.com": ["Windows test box", "spare5", "spare3", "spare4", "Fitness", "Plex/JellyFin", "Plex%2fJellyFin"], "esxi04.boylenet.themfboyles.com": ["spare9", "Spare1", "spare", "spare12", "spare10", "Spare11"]}

def get_host_stats(content):
    hosts = {}
    view = content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True)
    for h in view.view:
        mem_bytes = h.hardware.memorySize
        mem_total_mb = mem_bytes / (1024 * 1024)
        mem_total_gib = mem_bytes / 1024 ** 3
        used_mb = h.summary.quickStats.overallMemoryUsage or 0
        free_mb = mem_total_mb - used_mb
        hosts[h.name] = {"name": h.name, "total_mb": round(mem_total_mb, 1), "total_gib": round(mem_total_gib, 2), "quickstats_used_mb": used_mb, "quickstats_used_gib": round(used_mb / 1024.0, 2), "quickstats_free_mb": round(free_mb, 1), "quickstats_free_gib": round(free_mb / 1024.0, 2), "cpu_cores": h.hardware.cpuInfo.numCpuCores, "cpu_threads": h.hardware.cpuInfo.numCpuThreads, "powered_on_vms": [], "powered_on_configured_ram_mb": 0, "powered_on_reserved_ram_mb": 0}
    view.Destroy()
    vm_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
    for vm in vm_view.view:
        try:
            hname = vm.runtime.host.name if vm.runtime.host else "unknown"
            pstate = str(vm.runtime.powerState)
            mem_mb = vm.config.hardware.memoryMB if vm.config else 0
            ncpu = vm.config.hardware.numCPU if vm.config else 0
            locked = bool(vm.config.memoryReservationLockedToMax) if vm.config and vm.config.memoryReservationLockedToMax is not None else False
            res_mb = vm.config.memoryAllocation.reservation if vm.config and vm.config.memoryAllocation else 0
            ip = vm.guest.ipAddress if vm.guest else None
            if pstate == "poweredOn" and hname in hosts:
                hosts[hname]["powered_on_vms"].append({"name": vm.name, "moid": vm._moId, "memoryMB": mem_mb, "memoryGiB": round(mem_mb / 1024.0, 2), "numCPU": ncpu, "lockedToMax": locked, "reservationMB": res_mb, "ip": ip})
                hosts[hname]["powered_on_configured_ram_mb"] += mem_mb
                hosts[hname]["powered_on_reserved_ram_mb"] += mem_mb if locked else res_mb or 0
        except Exception:
            pass
    vm_view.Destroy()
    for hname, hinfo in hosts.items():
        hinfo["powered_on_configured_ram_gib"] = round(hinfo["powered_on_configured_ram_mb"] / 1024.0, 2)
        hinfo["powered_on_reserved_ram_gib"] = round(hinfo["powered_on_reserved_ram_mb"] / 1024.0, 2)
        hinfo["unallocated_configured_ram_mb"] = round(hinfo["total_mb"] - hinfo["powered_on_configured_ram_mb"], 1)
        hinfo["unallocated_configured_ram_gib"] = round(hinfo["unallocated_configured_ram_mb"] / 1024.0, 2)
        hinfo["powered_on_vms"].sort(key=lambda x: (-x["memoryMB"], x["name"]))
    return dict(sorted(hosts.items()))

def main():
    u, p = lib_vsphere_govc.load_vc_credentials()
    ctx = ssl._create_unverified_context()
    si = SmartConnect(host="10.0.20.70", user=u, pwd=p, sslContext=ctx)
    content = si.RetrieveContent()
    print("=== STEP 1A: BEFORE HOST & VM MEMORY STATS ===")
    before_stats = get_host_stats(content)
    for hname, hinfo in before_stats.items():
        print(f"[{hname}] Total={hinfo['total_gib']} GiB | QuickStats Used={hinfo['quickstats_used_gib']} GiB Free={hinfo['quickstats_free_gib']} GiB | "
            f"PoweredOn Configured={hinfo['powered_on_configured_ram_gib']} GiB (Unallocated={hinfo['unallocated_configured_ram_gib']} GiB)")
        for v in hinfo["powered_on_vms"]:
            print(f"  - {v['name']} ({v['moid']}): {v['memoryGiB']} GiB ({v['memoryMB']} MB), {v['numCPU']} vCPU, locked={v['lockedToMax']}, ip={v['ip']}")
    all_target_names = set()
    for tlist in TARGETS_BY_HOST.values():
        for t in tlist:
            assert t not in PROTECTED_VM_NAMES, f"FATAL: {t} is in PROTECTED_VM_NAMES"
            all_target_names.add(t)
    vm_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
    target_vms = []
    recorded_vms = []
    for vm in vm_view.view:
        vname = vm.name
        if vname in all_target_names:
            hname = vm.runtime.host.name if vm.runtime.host else "unknown"
            ip = vm.guest.ipAddress if vm.guest else None
            if vname in PROTECTED_VM_NAMES or (ip and ip in PROTECTED_IPS):
                raise RuntimeError(f"SAFETY HALT: Attempted to target protected VM {vname} ({ip})")
            pstate = str(vm.runtime.powerState)
            mem_mb = vm.config.hardware.memoryMB if vm.config else 0
            ncpu = vm.config.hardware.numCPU if vm.config else 0
            rec = {"name": vname, "moid": vm._moId, "host": hname, "memoryMB": mem_mb, "memoryGiB": round(mem_mb / 1024.0, 2), "numCPU": ncpu, "ip": ip, "initialPowerState": pstate, "timestamp_utc": datetime.now(timezone.utc).isoformat()}
            recorded_vms.append(rec)
            target_vms.append((vm, rec))
    vm_view.Destroy()
    recorded_vms.sort(key=lambda x: (x["host"], x["name"]))
    with open(OUT_JSON, "w") as f:
        json.dump({"created_at_utc": datetime.now(timezone.utc).isoformat(), "purpose": "O1789 Agent-20 temporarily powered off non-essential VMs to reclaim DDR4 RAM across esxi01..04", "count": len(recorded_vms), "vms": recorded_vms}, f, indent=2)
    print(f"\nSaved {len(recorded_vms)} target VMs to {OUT_JSON}")
    print("\n=== STEP 1B: ISSUING ShutdownGuest ON POWERED-ON TARGET VMS ===")
    powered_on_targets = []
    for vm, rec in target_vms:
        if str(vm.runtime.powerState) == "poweredOn":
            powered_on_targets.append((vm, rec))
            try:
                vm.ShutdownGuest()
                print(f"  [ShutdownGuest sent] {rec['name']} on {rec['host']} ({rec['memoryGiB']} GiB, ip={rec['ip']})")
                rec["shutdown_action"] = "ShutdownGuest_sent"
            except Exception as e:
                print(f"  [ShutdownGuest failed -> will PowerOffVM_Task] {rec['name']} on {rec['host']}: {e}")
                rec["shutdown_action"] = f"ShutdownGuest_err:{type(e).__name__}"
        else:
            print(f"  [Already {vm.runtime.powerState}] {rec['name']} on {rec['host']} ({rec['memoryGiB']} GiB)")
            rec["shutdown_action"] = "already_off"
    if powered_on_targets:
        print("Waiting 10 seconds for graceful guest shutdown...")
        time.sleep(10)
    print("\n=== STEP 1C: ISSUING PowerOffVM_Task FOR REMAINING POWERED-ON TARGET VMS ===")
    tasks = []
    for vm, rec in powered_on_targets:
        if str(vm.runtime.powerState) == "poweredOn":
            print(f"  [PowerOffVM_Task] {rec['name']} on {rec['host']} ({vm._moId})")
            t = vm.PowerOffVM_Task()
            tasks.append((t, vm, rec))
        else:
            print(f"  [Cleanly poweredOff via ShutdownGuest] {rec['name']} on {rec['host']}")
            rec["finalPowerState"] = str(vm.runtime.powerState)
    for t, vm, rec in tasks:
        while t.info.state in ("queued", "running"):
            time.sleep(0.5)
        print(f"  [Task done] {rec['name']} ({vm._moId}): state={t.info.state} powerState={vm.runtime.powerState}")
        if t.info.state != "success":
            print(f"  [ERROR] {rec['name']}: {t.info.error}")
            sys.exit(1)
        rec["finalPowerState"] = str(vm.runtime.powerState)
    for vm, rec in target_vms:
        rec["finalPowerState"] = str(vm.runtime.powerState)
    with open(OUT_JSON, "w") as f:
        json.dump({"created_at_utc": datetime.now(timezone.utc).isoformat(), "purpose": "O1789 Agent-20 temporarily powered off non-essential VMs to reclaim DDR4 RAM across esxi01..04", "count": len(recorded_vms), "vms": recorded_vms}, f, indent=2)
    time.sleep(3)
    print("\n=== STEP 1D: AFTER HOST & VM MEMORY STATS ===")
    after_stats = get_host_stats(content)
    for hname, hinfo in after_stats.items():
        print(f"[{hname}] Total={hinfo['total_gib']} GiB | QuickStats Used={hinfo['quickstats_used_gib']} GiB Free={hinfo['quickstats_free_gib']} GiB | "
            f"PoweredOn Configured={hinfo['powered_on_configured_ram_gib']} GiB (Unallocated={hinfo['unallocated_configured_ram_gib']} GiB)")
        for v in hinfo["powered_on_vms"]:
            print(f"  - {v['name']} ({v['moid']}): {v['memoryGiB']} GiB ({v['memoryMB']} MB), {v['numCPU']} vCPU, locked={v['lockedToMax']}, ip={v['ip']}")
    with open(STEP1_REPORT, "w") as f:
        json.dump({"before_stats": before_stats, "after_stats": after_stats, "powered_off_vms": recorded_vms}, f, indent=2)
    Disconnect(si)
    print("\nSTEP 1 COMPLETE (rc=0)")
if __name__ == "__main__":
    main()
