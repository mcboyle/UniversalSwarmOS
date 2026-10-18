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
STEP3_REPORT = os.path.join(BASE_DIR, "agent20_step3_report.json")
GPU_VMS_PLAN = [{"name": "AI Inference", "ip": "10.0.70.125", "roce_ip": "10.0.75.14", "host": "esxi01.boylenet.themfboyles.com", "target_vcpus": 48, "candidate_gib": [576, 560, 544, 528, 512], "initial_before": {"memoryMB": 32768, "memoryGiB": 32.0, "numCPU": 16, "lockedToMax": True}}, {"name": "llama", "ip": "10.0.70.228", "roce_ip": "10.0.75.13", "host": "esxi02.boylenet.themfboyles.com", "target_vcpus": 64, "candidate_gib": [448, 432, 416, 400, 384], "initial_before": {"memoryMB": 49152, "memoryGiB": 48.0, "numCPU": 16, "lockedToMax": True}}, {"name": "AI", "ip": "10.0.70.72", "roce_ip": "10.0.75.12", "host": "esxi04.boylenet.themfboyles.com", "target_vcpus": 64, "candidate_gib": [320, 310, 304, 300, 296, 288, 280], "initial_before": {"memoryMB": 32768, "memoryGiB": 32.0, "numCPU": 16, "lockedToMax": True}}]

def wait_task(task, label):
    while task.info.state in ("queued", "running"):
        time.sleep(0.5)
    state = str(task.info.state)
    err = str(task.info.error.msg) if task.info.error else None
    print(f"  [{label}] state={state}" + (f" error={err}" if err else ""))
    return (state == "success", err)

def find_vm_by_name(content, name):
    view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
    found = None
    for vm in view.view:
        if vm.name == name:
            found = vm
            break
    view.Destroy()
    return found

def expand_gpu_vm(content, plan):
    vname = plan["name"]
    vm = find_vm_by_name(content, vname)
    if not vm:
        raise RuntimeError(f"VM {vname} not found!")
    current = {"name": vm.name, "moid": vm._moId, "host": vm.runtime.host.name, "powerState": str(vm.runtime.powerState), "memoryMB": vm.config.hardware.memoryMB, "memoryGiB": round(vm.config.hardware.memoryMB / 1024.0, 2), "numCPU": vm.config.hardware.numCPU, "lockedToMax": bool(vm.config.memoryReservationLockedToMax), "reservationMB": vm.config.memoryAllocation.reservation if vm.config.memoryAllocation else None}
    print(f"\n=== EXPANDING {vname} ({vm._moId}) on {current['host']} ===")
    print(f"  CURRENT: {current['memoryGiB']} GiB ({current['memoryMB']} MB), {current['numCPU']} vCPU, locked={current['lockedToMax']}, powerState={current['powerState']}")
    if str(vm.runtime.powerState) == "poweredOn" and vm.config.hardware.memoryMB >= int(plan["candidate_gib"][-1] * 1024) and (vm.config.hardware.numCPU == plan["target_vcpus"]) and bool(vm.config.memoryReservationLockedToMax):
        print(f"  [ALREADY EXPANDED & POWERED ON] {vname}: {current['memoryGiB']} GiB, {current['numCPU']} vCPU")
        return {"before": plan["initial_before"], "after": current}
    if str(vm.runtime.powerState) == "poweredOn":
        try:
            vm.ShutdownGuest()
            print(f"  Sent ShutdownGuest to {vname}, waiting up to 15s...")
            for _ in range(30):
                if str(vm.runtime.powerState) == "poweredOff":
                    break
                time.sleep(0.5)
        except Exception as e:
            print(f"  ShutdownGuest exception on {vname}: {e}")
        if str(vm.runtime.powerState) != "poweredOff":
            print(f"  Still {vm.runtime.powerState}, calling PowerOffVM_Task...")
            ok, err = wait_task(vm.PowerOffVM_Task(), f"{vname} PowerOffVM_Task")
            if not ok and str(vm.runtime.powerState) != "poweredOff":
                raise RuntimeError(f"Failed to power off {vname}: {err}")
        else:
            print(f"  {vname} cleanly poweredOff via ShutdownGuest.")
    attempts = []
    target_vcpus = plan["target_vcpus"]
    powered_on_ok = False
    chosen_gib = None
    chosen_mb = None
    for gib in plan["candidate_gib"]:
        mem_mb = int(gib * 1024)
        print(f"  Attempting ReconfigVM_Task: memoryMB={mem_mb} ({gib} GiB), numCPUs={target_vcpus}, memoryReservationLockedToMax=True...")
        spec = vim.vm.ConfigSpec()
        spec.memoryMB = mem_mb
        spec.numCPUs = target_vcpus
        spec.memoryReservationLockedToMax = True
        mem_alloc = vim.ResourceAllocationInfo()
        mem_alloc.reservation = mem_mb
        mem_alloc.limit = mem_mb
        spec.memoryAllocation = mem_alloc
        ok_reconf, err_reconf = wait_task(vm.ReconfigVM_Task(spec), f"{vname} Reconfig({gib}GiB/{target_vcpus}vCPU)")
        if not ok_reconf:
            attempts.append({"gib": gib, "mb": mem_mb, "stage": "reconfig", "ok": False, "error": err_reconf})
            continue
        print(f"  Attempting PowerOnVM_Task for {vname} at {gib} GiB ({mem_mb} MB) locked...")
        ok_on, err_on = wait_task(vm.PowerOnVM_Task(), f"{vname} PowerOn({gib}GiB/{target_vcpus}vCPU)")
        attempts.append({"gib": gib, "mb": mem_mb, "stage": "poweron", "ok": ok_on, "error": err_on})
        if ok_on:
            powered_on_ok = True
            chosen_gib = gib
            chosen_mb = mem_mb
            break
        else:
            print(f"  PowerOn failed at {gib} GiB ({err_on}), trying next candidate...")
    if not powered_on_ok:
        raise RuntimeError(f"All candidates failed for {vname}: {attempts}")
    after = {"name": vm.name, "moid": vm._moId, "host": vm.runtime.host.name, "powerState": str(vm.runtime.powerState), "memoryMB": vm.config.hardware.memoryMB, "memoryGiB": round(vm.config.hardware.memoryMB / 1024.0, 2), "numCPU": vm.config.hardware.numCPU, "lockedToMax": bool(vm.config.memoryReservationLockedToMax), "reservationMB": vm.config.memoryAllocation.reservation if vm.config.memoryAllocation else None, "limitMB": vm.config.memoryAllocation.limit if vm.config.memoryAllocation else None, "chosen_gib": chosen_gib, "chosen_mb": chosen_mb, "attempts": attempts}
    print(f"  SUCCESS: {vname} poweredOn with {after['memoryGiB']} GiB ({after['memoryMB']} MB), {after['numCPU']} vCPU, locked={after['lockedToMax']}!")
    return {"before": plan["initial_before"], "after": after}

def main():
    u, p = lib_vsphere_govc.load_vc_credentials()
    ctx = ssl._create_unverified_context()
    si = SmartConnect(host="10.0.20.70", user=u, pwd=p, sslContext=ctx)
    content = si.RetrieveContent()
    results = {}
    aidev = find_vm_by_name(content, "AI DEV")
    results["AI DEV"] = {"note": "Already at 386.0 GiB (395264 MB) + 64 vCPUs locked=True on esxi03 (zero reboot required)", "state": {"name": aidev.name, "moid": aidev._moId, "host": aidev.runtime.host.name, "powerState": str(aidev.runtime.powerState), "memoryMB": aidev.config.hardware.memoryMB, "memoryGiB": round(aidev.config.hardware.memoryMB / 1024.0, 2), "numCPU": aidev.config.hardware.numCPU, "lockedToMax": bool(aidev.config.memoryReservationLockedToMax), "reservationMB": aidev.config.memoryAllocation.reservation}}
    for plan in GPU_VMS_PLAN:
        results[plan["name"]] = expand_gpu_vm(content, plan)
    with open(STEP3_REPORT, "w") as f:
        json.dump({"timestamp_utc": datetime.now(timezone.utc).isoformat(), "results": results}, f, indent=2)
    Disconnect(si)
    print("\nSTEP 3 GPU VM EXPANSION COMPLETE (rc=0)")
if __name__ == "__main__":
    main()
