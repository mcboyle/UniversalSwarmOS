#!/usr/bin/env bash
# /home/mboyle/bin/bd-apply-vnuma-52vcpu.sh
# Ready-to-apply vSphere / vim-cmd / PowerCLI script for:
#   - 52 vCPU / 26 cores-per-socket (2 virtual sockets x 26 cores = 2 vNUMA nodes matching dual Xeon Gold 6138 / Platinum 8168)
#   - vNUMA exposure (numa.autosize.vcpu.maxPerVirtualNode=26, numa.vcpu.preferHT=FALSE)
#   - Per-VM EVC Mode: intel-skylake (exposes AVX-512F/DQ/BW/VL/CD to guest kernel & llama.cpp Skylake-X backend)
# Targets:
#   - 10.0.70.72 (VM "AI" on esxi04 / 10.0.20.44)
#   - 10.0.70.83 (VM "AI DEV" on esxi03 / 10.0.20.43)
set -euo pipefail

MODE="${1:---check}"

cat <<'POWERCLI_REFERENCE' >/dev/null
# ============================================================================
# PowerCLI Equivalent Reference (vCenter 10.0.20.70)
# ============================================================================
# Connect-VIServer -Server 10.0.20.70
# foreach ($vmName in @("AI", "AI DEV")) {
#     $vm = Get-VM -Name $vmName
#     if ($vm.PowerState -eq "PoweredOn") {
#         Shutdown-VMGuest -VM $vm -Confirm:$false
#         while ((Get-VM -Name $vmName).PowerState -ne "PoweredOff") { Start-Sleep -Seconds 2 }
#     }
#     Set-VM -VM $vm -NumCpu 52 -CoresPerSocket 26 -Confirm:$false
#     New-AdvancedSetting -Entity $vm -Name "numa.autosize.vcpu.maxPerVirtualNode" -Value "26" -Confirm:$false -Force
#     New-AdvancedSetting -Entity $vm -Name "numa.vcpu.preferHT" -Value "FALSE" -Confirm:$false -Force
#     New-AdvancedSetting -Entity $vm -Name "numa.vcpu.followcorespersocket" -Value "1" -Confirm:$false -Force
#     $vm.ExtensionData.ApplyEvcModeVM_Task("intel-skylake", $null)
#     Start-VM -VM $vm -Confirm:$false
# }
# ============================================================================
# ESXi Direct vim-cmd Equivalent Reference (esxi03 10.0.20.43 / esxi04 10.0.20.44)
# ============================================================================
# vmid=$(vim-cmd vmsvc/getallvms | awk '$2 == "AI" {print $1}')
# vim-cmd vmsvc/power.shutdown "$vmid"
# sed -i -e 's/^numvcpus = .*/numvcpus = "52"/' \
#        -e 's/^cpuid.coresPerSocket = .*/cpuid.coresPerSocket = "26"/' "$vmx_path"
# grep -q '^numa.autosize.vcpu.maxPerVirtualNode' "$vmx_path" || echo 'numa.autosize.vcpu.maxPerVirtualNode = "26"' >> "$vmx_path"
# vim-cmd vmsvc/reload "$vmid"
# vim-cmd vmsvc/power.on "$vmid"
POWERCLI_REFERENCE

python3 - "$MODE" <<'EOF'
import sys
import ssl
import time
sys.path.insert(0, "/home/mboyle/bin")
import lib_vsphere_govc
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
u, p = lib_vsphere_govc.load_vc_credentials()
ctx = ssl._create_unverified_context()
si = SmartConnect(host="10.0.20.70", user=u, pwd=p, sslContext=ctx)
content = si.RetrieveContent()

target_vms = {"AI": "10.0.70.72", "AI DEV": "10.0.70.83"}

def wait_task(task, desc="Task"):
    while task.info.state in (vim.TaskInfo.State.queued, vim.TaskInfo.State.running):
        time.sleep(1.0)
    if task.info.state != vim.TaskInfo.State.success:
        raise RuntimeError(f"{desc} failed: {task.info.error}")

for vm in content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True).view:
    if vm.name not in target_vms:
        continue
    ip = target_vms[vm.name]
    host_name = vm.runtime.host.name if vm.runtime.host else "unknown"
    num_cpu = vm.config.hardware.numCPU
    cores_per_socket = vm.config.hardware.numCoresPerSocket
    evc_mode = getattr(vm.runtime, "minRequiredEVCModeKey", None)
    extra = {opt.key: opt.value for opt in (vm.config.extraConfig or []) if "numa" in opt.key.lower() or "cpuid" in opt.key.lower()}
    print(f"[VM] {vm.name} ({ip}) on {host_name}:")
    print(f"  PowerState     : {vm.runtime.powerState}")
    print(f"  numCPU         : {num_cpu} (target: 52)")
    print(f"  coresPerSocket : {cores_per_socket} (target: 26 -> 2 vNUMA sockets)")
    print(f"  per-VM EVC     : {evc_mode} (target: intel-skylake)")
    print(f"  NUMA extraCfg  : {extra}")

    if mode == "--apply":
        if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
            print(f"  -> Shutting down guest {vm.name} for vNUMA + per-VM EVC reconfiguration...")
            try:
                vm.ShutdownGuest()
            except Exception:
                vm.PowerOffVM_Task()
            for _ in range(90):
                if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOff:
                    break
                time.sleep(2)
            if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOff:
                wait_task(vm.PowerOffVM_Task(), "PowerOffVM")

        spec = vim.vm.ConfigSpec()
        spec.numCPUs = 52
        spec.numCoresPerSocket = 26
        spec.cpuHotAddEnabled = False  # Required so vNUMA is exposed instead of flattened to UMA
        spec.extraConfig = [
            vim.option.OptionValue(key="numa.autosize.vcpu.maxPerVirtualNode", value="26"),
            vim.option.OptionValue(key="numa.vcpu.preferHT", value="FALSE"),
            vim.option.OptionValue(key="numa.vcpu.followcorespersocket", value="1"),
        ]
        print(f"  -> Applying ReconfigVM_Task (52 vCPU / 26 cores-per-socket / cpuHotAdd=False / 2-node vNUMA)...")
        wait_task(vm.ReconfigVM_Task(spec), "ReconfigVM")

        if getattr(vm.runtime, "minRequiredEVCModeKey", None) != "intel-skylake":
            print(f"  -> Applying per-VM EVC mode 'intel-skylake'...")
            try:
                wait_task(vm.ApplyEvcModeVM_Task(evcModeKey="intel-skylake"), "ApplyEvcModeVM")
            except Exception as e:
                print(f"  [WARN] ApplyEvcModeVM_Task note: {e}")

        print(f"  -> Powering on {vm.name}...")
        wait_task(vm.PowerOnVM_Task(), "PowerOnVM")
        print(f"  [OK] {vm.name} reconfigured and powered on.")

Disconnect(si)
EOF
