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
dvs = next((d for d in content.viewManager.CreateContainerView(content.rootFolder, [vim.DistributedVirtualSwitch], True).view if d.name == "25GB"))
target_lag_pgs = {"VCHA", "FT 25GB", "Vmotion 25GB", "Infrastructure 25GB"}
for pg in dvs.portgroup:
    if pg.name in target_lag_pgs:
        spec = vim.dvs.DistributedVirtualPortgroup.ConfigSpec()
        spec.configVersion = pg.config.configVersion
        cfg = pg.config.defaultPortConfig
        cfg.uplinkTeamingPolicy.inherited = False
        cfg.uplinkTeamingPolicy.uplinkPortOrder.inherited = False
        cfg.uplinkTeamingPolicy.uplinkPortOrder.activeUplinkPort = ["LAG1"]
        cfg.uplinkTeamingPolicy.uplinkPortOrder.standbyUplinkPort = []
        spec.defaultPortConfig = cfg
        print(f"Reconfiguring {pg.name} to activeUplinkPort=['LAG1'] (inherited=False)...")
        task = pg.ReconfigureDVPortgroup_Task(spec)
        while task.info.state in ("queued", "running"):
            time.sleep(0.5)
        print(f"  {pg.name} task state:", task.info.state, task.info.error)
for pg in dvs.portgroup:
    if pg.name == "25GB-DVUplinks-9":
        continue
    cfg = pg.config.defaultPortConfig
    tp = cfg.uplinkTeamingPolicy
    po = tp.uplinkPortOrder
    print(f"FINAL PG {pg.name:25s}: active={list(po.activeUplinkPort)} standby={list(po.standbyUplinkPort)}")
Disconnect(si)
