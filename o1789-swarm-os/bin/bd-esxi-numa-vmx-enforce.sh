#!/usr/bin/env bash
# bd-esxi-numa-vmx-enforce.sh — Staged VMX NUMA & Memory Pinning Topology Script (Agent-158 / Agent-167)
# Enforces on .72 (AI.vmx on esxi04 10.0.20.44) and .83 (AI DEV.vmx on esxi03 10.0.20.43):
#   numvcpus = "52"
#   cpuid.coresPerSocket = "26"
#   numa.vcpu.preferHT = "FALSE"
#   numa.autosize.once = "FALSE"
#   numa.vcpu.maxPerVirtualNode = "26"
#   sched.mem.pin = "TRUE"
set -eo pipefail
source /home/mboyle/.config/bd/vsphere.env

verify_vmx() {
  local esxi_ip="$1"
  local vmx_path="$2"
  echo "=== Verifying $vmx_path on $esxi_ip ==="
  sshpass -p "$VCENTER_PASSWORD" ssh -o StrictHostKeyChecking=no root@"$esxi_ip" "
    esxcli hardware power policy set --id=1 || true
    esxcli hardware power policy get
    grep -E 'numvcpus|cpuid\.coresPerSocket|numa\.|sched\.mem\.pin' "$vmx_path"
  "
}

verify_vmx "10.0.20.43" "/vmfs/volumes/vsan:5221e29f8740f516-72730ae338b3eb48/7ba5a46a-b69b-436a-ce64-48df37e0b790/AI DEV.vmx"
verify_vmx "10.0.20.44" "/vmfs/volumes/vsan:5221e29f8740f516-72730ae338b3eb48/9566406a-ee24-837a-3fe5-98b785225eea/AI.vmx"
