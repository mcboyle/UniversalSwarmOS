import ssl
import sys
import time
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
if len(dvs.config.uplinkPortPolicy.uplinkPortName) > 8:
    spec = vim.dvs.VmwareDistributedVirtualSwitch.ConfigSpec()
    spec.configVersion = dvs.config.configVersion
    spec.uplinkPortPolicy = vim.DistributedVirtualSwitch.NameArrayUplinkPortPolicy()
    spec.uplinkPortPolicy.uplinkPortName = [f"Uplink {i}" for i in range(1, 9)]
    print("Reconfiguring DVS uplinkPortName to Uplink 1..8...")
    task = dvs.ReconfigureDvs_Task(spec)
    while task.info.state in ("queued", "running"):
        time.sleep(0.5)
    print("ReconfigureDvs_Task state:", task.info.state)
    if task.info.state != "success":
        print("Error:", task.info.error)
        sys.exit(1)
grp_existing = dvs.config.lacpGroupConfig[0]
lag_spec = vim.dvs.VmwareDistributedVirtualSwitch.LacpGroupSpec()
lag_spec.operation = "edit"
grp = vim.dvs.VmwareDistributedVirtualSwitch.LacpGroupConfig()
grp.key = grp_existing.key
grp.name = "LAG1"
grp.mode = "active"
grp.uplinkNum = 5
grp.loadbalanceAlgorithm = "srcDestIpTcpUdpPortVlan"
grp.timeoutMode = "fast"
lag_spec.lacpGroupConfig = grp
print("Syncing LAG1 to ESXi hosts with timeoutMode=fast (LACP fast 1s PDU)...")
task = dvs.UpdateDVSLacpGroupConfig_Task([lag_spec])
while task.info.state in ("queued", "running"):
    time.sleep(0.5)
print("UpdateDVSLacpGroupConfig_Task state:", task.info.state)
if task.info.state != "success":
    print("Error:", task.info.error)
    sys.exit(1)
print("Final uplinkPortNames:", list(dvs.config.uplinkPortPolicy.uplinkPortName))
print("Final lacpGroupConfig:", [(g.name, g.key, g.uplinkNum, g.mode, g.timeoutMode, list(g.uplinkName), list(g.uplinkPortKey)) for g in dvs.config.lacpGroupConfig])
Disconnect(si)
