import ssl
import sys
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
for pg in dvs.portgroup:
    cfg = pg.config.defaultPortConfig
    tp = cfg.uplinkTeamingPolicy
    po = tp.uplinkPortOrder
    vlan = getattr(cfg.vlan, "vlanId", None)
    print(f"PG {pg.name:35s} (key={pg.key}, vlan={vlan}): policy={tp.policy.value} active={list(po.activeUplinkPort)} standby={list(po.standbyUplinkPort)}")
Disconnect(si)
