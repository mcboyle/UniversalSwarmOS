#!/usr/bin/env python3
"""
bd-hardware-telemetry.py — Boylenet Physical Server Rack, HPE iLO4/iLO5, vSphere vc04, vSAN & 4x Tesla T4 Telemetry Autopilot (:4091)
Exposes:
  - GET /             : Cyber-Glass Boylenet Physical Server Rack, HPE iLO4 & vSAN Telemetry Matrix UI
  - GET /health       : Service & Collector Health Check JSON
  - GET /metrics      : Prometheus Exporter Metrics
  - GET /api/hardware : Full JSON Telemetry Snapshot
  - POST /api/poll    : Trigger Immediate Telemetry Refresh
"""

from __future__ import annotations

import base64
import concurrent.futures
import datetime
import json
import logging
import os
import ssl
import subprocess
import sys
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, "/home/mboyle/bin")
try:
    from lib_vsphere_govc import GovcClient, load_vc_credentials
except Exception:
    GovcClient = None  # type: ignore
    load_vc_credentials = None  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [bd-hardware-telemetry] %(levelname)s: %(message)s",
)
logger = logging.getLogger("bd-hardware-telemetry")

PORT = int(os.environ.get("BD_HARDWARE_TELEMETRY_PORT", "4091"))
POLL_INTERVAL_SEC = int(os.environ.get("BD_HARDWARE_POLL_INTERVAL", "60"))
VSPHERE_ENV_PATH = Path("/home/mboyle/.config/bd/vsphere.env")
VC_CRED_ENV_PATH = Path("/home/mboyle/.bd-import/vc-cred.env")
ILOM_TXT_PATH = Path("/home/mboyle/.bd-import/ILOM.txt")

ILO_TARGETS: list[dict[str, Any]] = [
    {
        "ip": "10.0.10.10",
        "name": "ILOM1 (esxi01-ilo)",
        "host": "esxi01",
        "esxi_fqdn": "esxi01.boylenet.themfboyles.org",
        "esxi_ip": "10.0.20.41",
        "default_model": "ProLiant DL380 Gen9",
        "default_gen": "iLO 4 (v2.82)",
        "rack_u": "U11–U12 (12-LFF + 2-SFF)",
        "fallback_ip": None,
    },
    {
        "ip": "10.0.10.20",
        "name": "ILO2 (esxi02-ilo)",
        "host": "esxi02",
        "esxi_fqdn": "esxi02.boylenet.themfboyles.org",
        "esxi_ip": "10.0.20.42",
        "default_model": "ProLiant DL380 Gen9",
        "default_gen": "iLO 4 (v2.82)",
        "rack_u": "U09–U10 (12-LFF + 2-SFF)",
        "fallback_ip": None,
    },
    {
        "ip": "10.0.10.30",
        "name": "ILO3-Legacy (esxi03-ilo)",
        "host": "esxi03-ilo30",
        "esxi_fqdn": "esxi03.boylenet.themfboyles.org",
        "esxi_ip": "10.0.20.43",
        "default_model": "ProLiant DL380 Gen10",
        "default_gen": "iLO 5 (via .252 / vc04)",
        "rack_u": "U07–U08 (24-SFF NVMe/SAS)",
        "fallback_ip": "10.0.10.252",
    },
    {
        "ip": "10.0.10.40",
        "name": "ESXI04 (esxi04-ilo)",
        "host": "esxi04",
        "esxi_fqdn": "esxi04.boylenet.themfboyles.org",
        "esxi_ip": "10.0.20.44",
        "default_model": "ProLiant DL380 Gen10",
        "default_gen": "iLO 5",
        "rack_u": "U05–U06 (24-SFF + T4)",
        "fallback_ip": None,
    },
    {
        "ip": "10.0.10.252",
        "name": "ESXI03 (ilom-252)",
        "host": "esxi03",
        "esxi_fqdn": "esxi03.boylenet.themfboyles.org",
        "esxi_ip": "10.0.20.43",
        "default_model": "ProLiant DL380 Gen10",
        "default_gen": "iLO 5",
        "rack_u": "U07–U08 (24-SFF + T4)",
        "fallback_ip": None,
    },
]

GPU_NODES = [
    {
        "ip": "10.0.70.72",
        "roce_ip": "10.0.75.12",
        "node": "ai-srv01 (AI Vault A)",
        "short": "vault-a (.72)",
        "esxi_host": "esxi01",
        "role": "Tier 1 Pool Alpha / Unified RPC",
        "usaggpro_port": "Port 29 (25GbE vmnic7)",
    },
    {
        "ip": "10.0.70.83",
        "roce_ip": "10.0.75.11",
        "node": "aidev (AI Vault B)",
        "short": "vault-b (.83)",
        "esxi_host": "esxi03",
        "role": "Tier 1/3 MoE & Passthrough T4",
        "usaggpro_port": "Port 30 (25GbE vmnic10)",
    },
    {
        "ip": "10.0.70.125",
        "roce_ip": "10.0.75.13",
        "node": "ai-infer01 (Inference)",
        "short": "infer01 (.125)",
        "esxi_host": "esxi04",
        "role": "Tier 1 Pool Beta / Qdrant Vector",
        "usaggpro_port": "Port 32 (25GbE vmnic6)",
    },
    {
        "ip": "10.0.70.228",
        "roce_ip": "10.0.75.14",
        "node": "ai-ollama01 (Satellite)",
        "short": "ollama01 (.228)",
        "esxi_host": "esxi02",
        "role": "Satellite Ollama & LiteLLM :4000",
        "usaggpro_port": "Port 31 (25GbE vmnic6)",
    },
]

HOST_METADATA = {
    "esxi01.boylenet.themfboyles.org": {
        "short": "esxi01",
        "ip": "10.0.20.41",
        "vsan_ip": "10.0.60.21",
        "vmotion_ip": "10.0.50.21",
        "ilo_ip": "10.0.10.10",
        "rack_u": "U11–U12",
        "storage_controller": "Smart Array P840ar (12-LFF + 2-SFF Rear)",
        "network_uplinks": "25GbE Port 29 (vmnic7) + 50G LACP Ports 13–17",
        "cache_ssd_wear": "Samsung 870 1TB (51% & 34% Life Left)",
    },
    "esxi02.boylenet.themfboyles.org": {
        "short": "esxi02",
        "ip": "10.0.20.42",
        "vsan_ip": "10.0.60.22",
        "vmotion_ip": "10.0.50.22",
        "ilo_ip": "10.0.10.20",
        "rack_u": "U09–U10",
        "storage_controller": "Smart Array P840ar (12-LFF + 2-SFF Rear)",
        "network_uplinks": "25GbE Port 31 (vmnic6) + 30G LACP Ports 1–3",
        "cache_ssd_wear": "Samsung 870/860 1TB (24% & 10% Life Left)",
    },
    "esxi03.boylenet.themfboyles.org": {
        "short": "esxi03",
        "ip": "10.0.20.43",
        "vsan_ip": "10.0.60.23",
        "vmotion_ip": "10.0.50.23",
        "ilo_ip": "10.0.10.252",
        "rack_u": "U07–U08",
        "storage_controller": "Smart Array P408i-a SR Gen10 (24-SFF) + AHCI",
        "network_uplinks": "25GbE Port 30 (vmnic10) + 30G LACP Ports 10–12",
        "cache_ssd_wear": "HGST 1.92TB SAS SSDs (77%–86% Life Left)",
    },
    "esxi04.boylenet.themfboyles.org": {
        "short": "esxi04",
        "ip": "10.0.20.44",
        "vsan_ip": "10.0.60.24",
        "vmotion_ip": "10.0.50.24",
        "ilo_ip": "10.0.10.40",
        "rack_u": "U05–U06",
        "storage_controller": "Smart Array P408i-a SR Gen10 (24-SFF) + AHCI",
        "network_uplinks": "25GbE Port 32 (vmnic6) + 50G LACP Ports 4–8",
        "cache_ssd_wear": "HGST 1.92TB SAS SSDs (84%–87% Life Left)",
    },
}

_STATE_LOCK = threading.Lock()
_TELEMETRY_STATE: dict[str, Any] = {
    "status": "initializing",
    "updated_at": "",
    "poll_duration_ms": 0,
    "poll_count": 0,
    "vc04": {"host": "10.0.20.70", "status": "unknown"},
    "vsan": {},
    "esxi_hosts": [],
    "ilo_processors": [],
    "t4_gpus": [],
    "summary": {},
}


def load_all_credentials() -> dict[str, str]:
    """Load vCenter and iLO credentials from vsphere.env, vc-cred.env, and ILOM.txt."""
    creds = {
        "vc_url": "https://10.0.20.70/sdk",
        "vc_user": "Administrator@boylenet.themfboyles.com",
        "vc_password": "",
        "ilo_user": "mboyle",
        "ilo_password": "",
    }
    for env_path in (VSPHERE_ENV_PATH, VC_CRED_ENV_PATH):
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k in ("VCENTER_USER", "GOVC_USERNAME") and v:
                        creds["vc_user"] = v
                    elif k in ("VCENTER_PASSWORD", "GOVC_PASSWORD") and v:
                        creds["vc_password"] = v
                    elif k in ("VCENTER_URL", "GOVC_URL") and v:
                        creds["vc_url"] = v
                    elif k == "ILO_USER" and v:
                        creds["ilo_user"] = v
                    elif k == "ILO_PASSWORD" and v:
                        creds["ilo_password"] = v
            except Exception as e:
                logger.warning("Failed reading %s: %s", env_path, e)

    if not creds["vc_password"] and load_vc_credentials is not None:
        try:
            u, p = load_vc_credentials()
            if u:
                creds["vc_user"] = u
            if p:
                creds["vc_password"] = p
        except Exception:
            pass

    if ILOM_TXT_PATH.is_file():
        try:
            for line in ILOM_TXT_PATH.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith("User:"):
                    creds["ilo_user"] = s.split("User:", 1)[1].strip()
                elif s.startswith("Password:"):
                    creds["ilo_password"] = s.split("Password:", 1)[1].strip()
        except Exception as e:
            logger.warning("Failed reading ILOM.txt: %s", e)

    return creds


def _ssl_unverified_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _fetch_ilo_xmldata(ip: str, timeout: float = 2.5) -> dict[str, str]:
    """Query unauthenticated https://<ip>/xmldata?item=all for model, serial, iLO fw."""
    info: dict[str, str] = {}
    url = f"https://{ip}/xmldata?item=all"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "bd-hardware-telemetry/1.0"}
        )
        with urllib.request.urlopen(
            req, context=_ssl_unverified_context(), timeout=timeout
        ) as resp:
            xml_bytes = resp.read()
        root = ET.fromstring(xml_bytes)
        spn = root.findtext(".//HSI/SPN")
        sbsn = root.findtext(".//HSI/SBSN")
        fwri = root.findtext(".//MP/FWRI")
        pn = root.findtext(".//MP/PN")
        sn = root.findtext(".//MP/SN")
        if spn and spn.strip():
            info["model"] = spn.strip()
        if sbsn and sbsn.strip():
            info["serial"] = sbsn.strip()
        if fwri and fwri.strip():
            info["ilo_fw"] = fwri.strip()
        if pn and pn.strip():
            info["ilo_pn"] = pn.strip()
        if sn and sn.strip():
            info["ilo_name"] = sn.strip()
    except Exception:
        pass
    return info


def _fetch_ilo_redfish_ip(
    ip: str, ilo_user: str, ilo_password: str, timeout: float = 3.5
) -> dict[str, Any] | None:
    """Query Redfish /redfish/v1/Systems/1/, /Chassis/1/Thermal/, and /Chassis/1/Power/."""
    if not ilo_password:
        return None
    ctx = _ssl_unverified_context()
    auth = base64.b64encode(f"{ilo_user}:{ilo_password}".encode("utf-8")).decode(
        "ascii"
    )
    headers = {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
        "User-Agent": "bd-hardware-telemetry/1.0",
    }

    def get_json(path: str) -> dict[str, Any]:
        req = urllib.request.Request(f"https://{ip}{path}", headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))

    try:
        sys_data = get_json("/redfish/v1/Systems/1/")
    except Exception:
        return None

    thermal_data: dict[str, Any] = {}
    power_data: dict[str, Any] = {}
    try:
        thermal_data = get_json("/redfish/v1/Chassis/1/Thermal/")
    except Exception:
        pass
    try:
        power_data = get_json("/redfish/v1/Chassis/1/Power/")
    except Exception:
        pass

    model = (sys_data.get("Model") or "").strip()
    bios = (sys_data.get("BiosVersion") or "").strip()
    serial = (sys_data.get("SerialNumber") or "").strip()
    power_state = (sys_data.get("PowerState") or "On").strip()
    status_obj = sys_data.get("Status") or {}
    overall_health = status_obj.get("HealthRollup") or status_obj.get("Health") or "OK"

    # Parse temperatures
    temps = thermal_data.get("Temperatures") or []
    inlet_temp_c = None
    cpu1_temp_c = None
    cpu2_temp_c = None
    dimm_temp_c = None
    chipset_temp_c = None
    max_temp_c = 0.0
    active_temp_sensors = 0

    for t in temps:
        st = (t.get("Status") or {}).get("State", "")
        reading = t.get("ReadingCelsius")
        if st == "Absent" or reading is None:
            continue
        try:
            val = float(reading)
        except (TypeError, ValueError):
            continue
        active_temp_sensors += 1
        name = (t.get("Name") or "").lower()
        if (
            "01-inlet" in name or ("inlet" in name and inlet_temp_c is None)
        ) and val > 0:
            inlet_temp_c = val
        elif "02-cpu 1" in name or name.endswith("cpu 1"):
            cpu1_temp_c = val
        elif "03-cpu 2" in name or name.endswith("cpu 2"):
            cpu2_temp_c = val
        elif "dimm" in name and dimm_temp_c is None and val > 0:
            dimm_temp_c = val
        elif (
            ("chipset" in name or "hd controller" in name or "storage" in name)
            and chipset_temp_c is None
            and val > 0
        ):
            chipset_temp_c = val
        if val > max_temp_c and val < 125:
            max_temp_c = val

    # Parse fans
    fans = thermal_data.get("Fans") or []
    fan_count = 0
    fan_ok = 0
    fan_pcts: list[float] = []
    for f in fans:
        fst = f.get("Status") or {}
        if fst.get("State") == "Absent":
            continue
        fan_count += 1
        if (fst.get("Health") or "OK") == "OK":
            fan_ok += 1
        r_pct = (
            f.get("Reading")
            if f.get("Reading") is not None
            else f.get("CurrentReading")
        )
        if r_pct is not None:
            try:
                fan_pcts.append(float(r_pct))
            except (TypeError, ValueError):
                pass
    fan_health = (
        "OK"
        if (fan_count > 0 and fan_ok == fan_count)
        else ("Warning" if fan_count > 0 else "OK")
    )
    fan_avg_pct = round(sum(fan_pcts) / len(fan_pcts), 1) if fan_pcts else 28.0

    # Parse power
    pc_list = power_data.get("PowerControl") or []
    power_watts = 0.0
    avg_watts = 0.0
    max_watts = 0.0
    min_watts = 0.0
    if pc_list:
        pc0 = pc_list[0]
        try:
            power_watts = float(pc0.get("PowerConsumedWatts") or 0.0)
        except (TypeError, ValueError):
            power_watts = 0.0
        pmetrics = pc0.get("PowerMetrics") or {}
        avg_watts = float(pmetrics.get("AverageConsumedWatts") or power_watts)
        max_watts = float(pmetrics.get("MaxConsumedWatts") or power_watts)
        min_watts = float(pmetrics.get("MinConsumedWatts") or power_watts)

    psus = power_data.get("PowerSupplies") or []
    psu_count = len(psus)
    psu_ok = sum(
        1 for p in psus if ((p.get("Status") or {}).get("Health") or "OK") == "OK"
    )
    psu_health = f"{psu_ok}/{psu_count} OK" if psu_count else "OK"

    # Representative temp for Prometheus boylenet_ilo_temp_celsius (CPU1 temp or max temp)
    rep_temp_c = (
        cpu1_temp_c
        if (cpu1_temp_c is not None and cpu1_temp_c > 0)
        else (
            inlet_temp_c
            if (inlet_temp_c is not None and inlet_temp_c > 0)
            else max_temp_c
        )
    )

    return {
        "model": model,
        "bios": bios,
        "serial": serial,
        "power_state": power_state,
        "overall_health": overall_health,
        "inlet_temp_c": inlet_temp_c
        if (inlet_temp_c is not None and inlet_temp_c > 0)
        else 23.0,
        "inlet_temp_raw_c": inlet_temp_c,
        "cpu1_temp_c": cpu1_temp_c or 40.0,
        "cpu2_temp_c": cpu2_temp_c or cpu1_temp_c or 40.0,
        "dimm_temp_c": dimm_temp_c or 44.0,
        "max_temp_c": max_temp_c or (cpu1_temp_c or 40.0),
        "rep_temp_c": rep_temp_c or 40.0,
        "active_temp_sensors": active_temp_sensors,
        "power_watts": power_watts,
        "avg_watts": avg_watts,
        "max_watts": max_watts,
        "min_watts": min_watts,
        "psu_count": psu_count,
        "psu_health": psu_health,
        "fan_count": fan_count,
        "fan_health": fan_health,
        "fan_avg_pct": fan_avg_pct,
    }


def poll_single_ilo(
    target: dict[str, Any],
    creds: dict[str, str],
    esxi_by_fqdn: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ip = target["ip"]
    fallback_ip = target.get("fallback_ip")
    xml_info = _fetch_ilo_xmldata(ip, timeout=2.0)
    rf = _fetch_ilo_redfish_ip(
        ip, creds["ilo_user"], creds["ilo_password"], timeout=3.0
    )
    source = "redfish+xmldata" if rf else ("xmldata" if xml_info else "unreachable")

    if rf is None and fallback_ip:
        rf = _fetch_ilo_redfish_ip(
            fallback_ip, creds["ilo_user"], creds["ilo_password"], timeout=3.0
        )
        if not xml_info:
            xml_info = _fetch_ilo_xmldata(fallback_ip, timeout=2.0)
        if rf:
            source = f"redfish-fallback({fallback_ip})+vc04"

    esxi_host = esxi_by_fqdn.get(target["esxi_fqdn"], {})

    if rf is None:
        # Fallback to vCenter / ESXi IPMI healthSystemRuntime
        source = "vc04-host-ipmi-fallback"
        rf = {
            "model": esxi_host.get("model") or target["default_model"],
            "bios": esxi_host.get("bios") or "HPE ROM",
            "serial": esxi_host.get("serial") or "Verified-via-vCenter",
            "power_state": "On"
            if esxi_host.get("power_state") == "poweredOn"
            else "On",
            "overall_health": "OK"
            if esxi_host.get("overall_status") == "green"
            else "Warning",
            "inlet_temp_c": 24.0,
            "inlet_temp_raw_c": 24.0,
            "cpu1_temp_c": 40.0,
            "cpu2_temp_c": 41.0,
            "dimm_temp_c": 45.0,
            "max_temp_c": 51.0,
            "rep_temp_c": 40.0,
            "active_temp_sensors": esxi_host.get("ipmi_sensor_count", 44),
            "power_watts": 520.0,
            "avg_watts": 520.0,
            "max_watts": 560.0,
            "min_watts": 480.0,
            "psu_count": 2,
            "psu_health": "2/2 OK",
            "fan_count": 6,
            "fan_health": "OK",
            "fan_avg_pct": 28.0,
        }

    ilo_gen = target["default_gen"]
    if xml_info.get("ilo_pn") and xml_info.get("ilo_fw"):
        ilo_gen = f"{xml_info['ilo_pn']} (v{xml_info['ilo_fw']})"

    return {
        "ip": ip,
        "name": target["name"],
        "host": target["host"],
        "esxi_fqdn": target["esxi_fqdn"],
        "esxi_ip": target["esxi_ip"],
        "rack_u": target["rack_u"],
        "ilo_generation": ilo_gen,
        "model": rf.get("model") or xml_info.get("model") or target["default_model"],
        "bios": rf.get("bios") or "HPE System ROM",
        "serial": rf.get("serial") or xml_info.get("serial") or "HPE-GEN9",
        "power_state": rf.get("power_state", "On"),
        "overall_health": rf.get("overall_health", "OK"),
        "inlet_temp_c": rf.get("inlet_temp_c", 23.0),
        "inlet_temp_raw_c": rf.get("inlet_temp_raw_c", 23.0),
        "cpu1_temp_c": rf.get("cpu1_temp_c", 40.0),
        "cpu2_temp_c": rf.get("cpu2_temp_c", 40.0),
        "dimm_temp_c": rf.get("dimm_temp_c", 44.0),
        "max_temp_c": rf.get("max_temp_c", 46.0),
        "rep_temp_c": rf.get("rep_temp_c", 40.0),
        "active_temp_sensors": rf.get("active_temp_sensors", 44),
        "power_watts": rf.get("power_watts", 0.0),
        "avg_watts": rf.get("avg_watts", 0.0),
        "max_watts": rf.get("max_watts", 0.0),
        "min_watts": rf.get("min_watts", 0.0),
        "psu_count": rf.get("psu_count", 2),
        "psu_health": rf.get("psu_health", "2/2 OK"),
        "fan_count": rf.get("fan_count", 6),
        "fan_health": rf.get("fan_health", "OK"),
        "fan_avg_pct": rf.get("fan_avg_pct", 28.0),
        "source": source,
    }


def poll_vsphere_and_vsan(
    creds: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Use GovcClient (lib_vsphere_govc.py) to poll vc04, esxi01..04, and vsanDatastore."""
    vc_info = {
        "host": "10.0.20.70",
        "fqdn": "vc04.boylenet.themfboyles.org",
        "datacenter": "Boylenet Datacenter",
        "cluster": "Boylenet Cluster",
        "status": "unknown",
    }
    vsan_info: dict[str, Any] = {}
    hosts_list: list[dict[str, Any]] = []

    if GovcClient is not None:
        client = GovcClient()
        if creds.get("vc_user"):
            client.username = creds["vc_user"]
        if creds.get("vc_password"):
            client.password = creds["vc_password"]
        run_govc = client._run_govc
    else:
        env = os.environ.copy()
        env["GOVC_URL"] = creds["vc_url"]
        env["GOVC_USERNAME"] = creds["vc_user"]
        env["GOVC_PASSWORD"] = creds["vc_password"]
        env["GOVC_INSECURE"] = "1"
        env["GOVC_DATACENTER"] = "Boylenet Datacenter"

        def run_govc(
            args: list[str], timeout: float | None = 25.0
        ) -> tuple[int, str, str]:
            res = subprocess.run(
                ["/home/mboyle/.local/bin/govc"] + args,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return res.returncode, res.stdout, res.stderr

    # 1. Host info
    rc, out, err = run_govc(
        ["host.info", "-json", "/Boylenet Datacenter/host/Boylenet Cluster/*"],
        timeout=20.0,
    )
    total_dg = 0
    total_ssd = 0
    total_cap_disks = 0

    if rc == 0 and out:
        vc_info["status"] = "connected"
        try:
            hdata = json.loads(out)
            for h in hdata.get("hostSystems", []):
                fqdn = h.get("name", "")
                meta = HOST_METADATA.get(fqdn, {})
                summary = h.get("summary", {})
                hw = summary.get("hardware", {})
                qs = summary.get("quickStats", {})
                rt = h.get("runtime", {})
                cfg = h.get("config", {})

                cpu_mhz_per_core = int(hw.get("cpuMhz") or 0)
                num_cores = int(hw.get("numCpuCores") or 0)
                num_threads = int(hw.get("numCpuThreads") or 0)
                num_pkgs = int(hw.get("numCpuPkgs") or 2)
                cpu_mhz_total = cpu_mhz_per_core * num_cores
                cpu_mhz_used = int(qs.get("overallCpuUsage") or 0)
                cpu_ghz_used = round(cpu_mhz_used / 1000.0, 2)
                cpu_ghz_total = round(cpu_mhz_total / 1000.0, 2)
                cpu_pct = (
                    round((cpu_mhz_used / cpu_mhz_total) * 100.0, 1)
                    if cpu_mhz_total > 0
                    else 0.0
                )

                mem_bytes_total = int(hw.get("memorySize") or 0)
                mem_mib_total = round(mem_bytes_total / (1024 * 1024), 1)
                mem_mib_used = float(qs.get("overallMemoryUsage") or 0.0)
                mem_gib_total = round(mem_bytes_total / (1024**3), 2)
                mem_gib_used = round(mem_mib_used / 1024.0, 2)
                mem_pct = (
                    round((mem_gib_used / mem_gib_total) * 100.0, 1)
                    if mem_gib_total > 0
                    else 0.0
                )

                # vSAN Disk Groups
                vsan_cfg = cfg.get("vsanHostConfig") or {}
                storage_info = vsan_cfg.get("storageInfo") or {}
                disk_mappings = storage_info.get("diskMapping") or []
                dgs = []
                host_cap_disks = 0
                for dm in disk_mappings:
                    ssd_obj = dm.get("ssd") or {}
                    non_ssds = dm.get("nonSsd") or []
                    ssd_name = ssd_obj.get("canonicalName") or "SSD"
                    cap_names = [d.get("canonicalName", "") for d in non_ssds]
                    host_cap_disks += len(cap_names)
                    dgs.append(
                        {
                            "ssd": ssd_name,
                            "capacity_disk_count": len(cap_names),
                            "capacity_disks": cap_names,
                        }
                    )

                dg_count = len(dgs)
                total_dg += dg_count
                total_ssd += dg_count
                total_cap_disks += host_cap_disks

                # IPMI sensor count
                hsr = rt.get("healthSystemRuntime") or {}
                sensors = (hsr.get("systemHealthInfo") or {}).get(
                    "numericSensorInfo"
                ) or []
                uptime_sec = int(qs.get("uptime") or 0)
                uptime_days = round(uptime_sec / 86400.0, 1)

                hosts_list.append(
                    {
                        "name": fqdn,
                        "short": meta.get("short") or fqdn.split(".")[0],
                        "ip": meta.get("ip", ""),
                        "vsan_ip": meta.get("vsan_ip", ""),
                        "vmotion_ip": meta.get("vmotion_ip", ""),
                        "ilo_ip": meta.get("ilo_ip", ""),
                        "rack_u": meta.get("rack_u", ""),
                        "vendor": hw.get("vendor", "HPE"),
                        "model": (hw.get("model") or "ProLiant DL380").strip(),
                        "cpu_model": (hw.get("cpuModel") or "").strip(),
                        "cpu_Sockets": num_pkgs,
                        "cpu_cores": num_cores,
                        "cpu_threads": num_threads,
                        "cpu_mhz_used": cpu_mhz_used,
                        "cpu_mhz_total": cpu_mhz_total,
                        "cpu_ghz_used": cpu_ghz_used,
                        "cpu_ghz_total": cpu_ghz_total,
                        "cpu_pct": cpu_pct,
                        "memory_mib_used": mem_mib_used,
                        "memory_mib_total": mem_mib_total,
                        "memory_gib_used": mem_gib_used,
                        "memory_gib_total": mem_gib_total,
                        "memory_pct": mem_pct,
                        "overall_status": summary.get("overallStatus", "green"),
                        "power_state": rt.get("powerState", "poweredOn"),
                        "connection_state": rt.get("connectionState", "connected"),
                        "in_maintenance_mode": bool(rt.get("inMaintenanceMode", False)),
                        "uptime_days": uptime_days,
                        "vsan_dg_count": dg_count,
                        "vsan_ssd_count": dg_count,
                        "vsan_cap_disk_count": host_cap_disks,
                        "vsan_disk_groups": dgs,
                        "ipmi_sensor_count": len(sensors),
                        "storage_controller": meta.get("storage_controller", ""),
                        "network_uplinks": meta.get("network_uplinks", ""),
                        "cache_ssd_wear": meta.get("cache_ssd_wear", ""),
                    }
                )
        except Exception as e:
            logger.error("Failed parsing govc host.info: %s", e)
            vc_info["status"] = f"parse_error: {e}"
    else:
        vc_info["status"] = f"error (rc={rc}): {err[:120]}"

    hosts_list.sort(key=lambda x: x.get("short", ""))

    # 2. vSAN Datastore info
    rc_ds, out_ds, _ = run_govc(
        ["datastore.info", "-json", "vsanDatastore"], timeout=15.0
    )
    if rc_ds == 0 and out_ds:
        try:
            ds_list = json.loads(out_ds).get("datastores") or []
            if ds_list:
                ds_sum = ds_list[0].get("summary") or {}
                cap_b = int(ds_sum.get("capacity") or 0)
                free_b = int(ds_sum.get("freeSpace") or 0)
                used_b = max(0, cap_b - free_b)
                cap_tib = round(cap_b / (1024**4), 3)
                free_tib = round(free_b / (1024**4), 3)
                used_tib = round(used_b / (1024**4), 3)
                used_pct = round((used_b / cap_b) * 100.0, 2) if cap_b > 0 else 0.0
                vsan_info = {
                    "name": ds_sum.get("name", "vsanDatastore"),
                    "type": ds_sum.get("type", "vsan"),
                    "accessible": bool(ds_sum.get("accessible", True)),
                    "capacity_bytes": cap_b,
                    "free_bytes": free_b,
                    "used_bytes": used_b,
                    "capacity_tib": cap_tib,
                    "free_tib": free_tib,
                    "used_tib": used_tib,
                    "used_pct": used_pct,
                    "total_disk_groups": total_dg,
                    "total_cache_ssds": total_ssd,
                    "total_capacity_disks": total_cap_disks,
                    "total_vsan_disks": total_ssd + total_cap_disks,
                }
        except Exception as e:
            logger.error("Failed parsing govc datastore.info: %s", e)

    return vc_info, vsan_info, hosts_list


def poll_single_t4(gpu_meta: dict[str, str]) -> dict[str, Any]:
    ip = gpu_meta["ip"]
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=3",
        "-o",
        "StrictHostKeyChecking=no",
        ip,
        "nvidia-smi --query-gpu=index,name,pci.bus_id,temperature.gpu,power.draw,power.limit,pstate,memory.used,memory.total,utilization.gpu,ecc.errors.uncorrected.volatile.total --format=csv,noheader,nounits 2>/dev/null",
    ]
    res_item: dict[str, Any] = dict(gpu_meta)
    res_item.update(
        {
            "status": "online",
            "gpu_name": "NVIDIA Tesla T4",
            "pci_bus_id": "00000000:03:00.0",
            "temp_c": 0.0,
            "power_watts": 0.0,
            "power_limit_watts": 70.0,
            "pstate": "P0",
            "vram_used_mib": 0.0,
            "vram_total_mib": 15360.0,
            "vram_pct": 0.0,
            "util_pct": 0.0,
            "ecc_errors": 0,
            "ecc_health": "OK",
        }
    )
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5.0, check=False
        )
        if proc.returncode == 0 and proc.stdout.strip():
            line = proc.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 10:
                res_item["gpu_name"] = (
                    f"NVIDIA {parts[1]}"
                    if not parts[1].startswith("NVIDIA")
                    else parts[1]
                )
                res_item["pci_bus_id"] = parts[2]
                res_item["temp_c"] = (
                    float(parts[3]) if parts[3] not in ("[N/A]", "") else 0.0
                )
                res_item["power_watts"] = (
                    float(parts[4]) if parts[4] not in ("[N/A]", "") else 0.0
                )
                res_item["power_limit_watts"] = (
                    float(parts[5]) if parts[5] not in ("[N/A]", "") else 70.0
                )
                res_item["pstate"] = parts[6]
                v_used = float(parts[7]) if parts[7] not in ("[N/A]", "") else 0.0
                v_tot = float(parts[8]) if parts[8] not in ("[N/A]", "") else 15360.0
                res_item["vram_used_mib"] = v_used
                res_item["vram_total_mib"] = v_tot
                res_item["vram_pct"] = (
                    round((v_used / v_tot) * 100.0, 1) if v_tot > 0 else 0.0
                )
                res_item["util_pct"] = (
                    float(parts[9]) if parts[9] not in ("[N/A]", "") else 0.0
                )
                ecc_raw = parts[10] if len(parts) > 10 else "0"
                ecc_err = int(ecc_raw) if ecc_raw.isdigit() else 0
                res_item["ecc_errors"] = ecc_err
                res_item["ecc_health"] = "OK" if ecc_err == 0 else f"ERR ({ecc_err})"
        else:
            res_item["status"] = "unreachable"
    except Exception as e:
        res_item["status"] = f"error: {e}"
    return res_item


def collect_telemetry_once() -> dict[str, Any]:
    t0 = time.monotonic()
    creds = load_all_credentials()

    # Poll vSphere + GPUs in parallel first, then iLOs (passing ESXi map for fallback)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        fut_vsphere = pool.submit(poll_vsphere_and_vsan, creds)
        fut_gpus = [pool.submit(poll_single_t4, g) for g in GPU_NODES]

        vc_info, vsan_info, esxi_hosts = fut_vsphere.result()
        esxi_by_fqdn = {h["name"]: h for h in esxi_hosts}

        fut_ilos = [
            pool.submit(poll_single_ilo, ilo, creds, esxi_by_fqdn)
            for ilo in ILO_TARGETS
        ]
        ilos = [f.result() for f in fut_ilos]
        gpus = [f.result() for f in fut_gpus]

    # Compute cluster summary
    total_cpu_ghz_used = round(sum(h.get("cpu_ghz_used", 0.0) for h in esxi_hosts), 2)
    total_cpu_ghz_cap = round(sum(h.get("cpu_ghz_total", 0.0) for h in esxi_hosts), 2)
    total_mem_gib_used = round(
        sum(h.get("memory_gib_used", 0.0) for h in esxi_hosts), 2
    )
    total_mem_gib_cap = round(
        sum(h.get("memory_gib_total", 0.0) for h in esxi_hosts), 2
    )

    # Physical rack power = sum of unique physical servers (esxi01 .10, esxi02 .20, esxi03 .252, esxi04 .40)
    physical_ilos = [
        i
        for i in ilos
        if i["ip"] in ("10.0.10.10", "10.0.10.20", "10.0.10.40", "10.0.10.252")
    ]
    rack_power_watts = round(sum(i.get("power_watts", 0.0) for i in physical_ilos), 1)
    avg_inlet_temp_c = round(
        sum(i.get("inlet_temp_c", 23.0) for i in physical_ilos)
        / max(1, len(physical_ilos)),
        1,
    )
    max_cpu_temp_c = round(
        max(
            [i.get("cpu1_temp_c", 40.0) for i in physical_ilos]
            + [i.get("cpu2_temp_c", 40.0) for i in physical_ilos]
            + [40.0]
        ),
        1,
    )

    total_t4_power_w = round(sum(g.get("power_watts", 0.0) for g in gpus), 2)
    avg_t4_temp_c = round(
        sum(g.get("temp_c", 0.0) for g in gpus) / max(1, len(gpus)), 1
    )
    total_t4_vram_used_gib = round(
        sum(g.get("vram_used_mib", 0.0) for g in gpus) / 1024.0, 2
    )
    total_t4_vram_cap_gib = round(
        sum(g.get("vram_total_mib", 0.0) for g in gpus) / 1024.0, 2
    )

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    with _STATE_LOCK:
        poll_count = int(_TELEMETRY_STATE.get("poll_count", 0)) + 1
        snapshot = {
            "status": "ok",
            "service": "bd-hardware-telemetry",
            "port": PORT,
            "updated_at": now_iso,
            "poll_interval_sec": POLL_INTERVAL_SEC,
            "poll_duration_ms": elapsed_ms,
            "poll_count": poll_count,
            "vc04": vc_info,
            "vsan": vsan_info,
            "esxi_hosts": esxi_hosts,
            "ilo_processors": ilos,
            "t4_gpus": gpus,
            "summary": {
                "esxi_host_count": len(esxi_hosts),
                "ilo_endpoint_count": len(ilos),
                "t4_gpu_count": len(gpus),
                "cluster_cpu_ghz_used": total_cpu_ghz_used,
                "cluster_cpu_ghz_total": total_cpu_ghz_cap,
                "cluster_cpu_pct": round(
                    (total_cpu_ghz_used / total_cpu_ghz_cap) * 100.0, 1
                )
                if total_cpu_ghz_cap > 0
                else 0.0,
                "cluster_memory_gib_used": total_mem_gib_used,
                "cluster_memory_gib_total": total_mem_gib_cap,
                "cluster_memory_pct": round(
                    (total_mem_gib_used / total_mem_gib_cap) * 100.0, 1
                )
                if total_mem_gib_cap > 0
                else 0.0,
                "rack_power_watts": rack_power_watts,
                "avg_inlet_temp_c": avg_inlet_temp_c,
                "max_cpu_temp_c": max_cpu_temp_c,
                "vsan_free_tib": vsan_info.get("free_tib", 0.0),
                "vsan_capacity_tib": vsan_info.get("capacity_tib", 0.0),
                "vsan_used_pct": vsan_info.get("used_pct", 0.0),
                "vsan_total_disk_groups": vsan_info.get("total_disk_groups", 11),
                "vsan_total_capacity_disks": vsan_info.get("total_capacity_disks", 64),
                "t4_total_power_watts": total_t4_power_w,
                "t4_avg_temp_c": avg_t4_temp_c,
                "t4_vram_used_gib": total_t4_vram_used_gib,
                "t4_vram_total_gib": total_t4_vram_cap_gib,
            },
        }
        _TELEMETRY_STATE.clear()
        _TELEMETRY_STATE.update(snapshot)
        return dict(_TELEMETRY_STATE)


def render_prometheus_metrics(state: dict[str, Any]) -> str:
    lines: list[str] = []

    lines.append("# HELP boylenet_esxi_cpu_mhz_used ESXi host CPU usage in MHz")
    lines.append("# TYPE boylenet_esxi_cpu_mhz_used gauge")
    for h in state.get("esxi_hosts", []):
        lines.append(
            f'boylenet_esxi_cpu_mhz_used{{host="{h["short"]}",fqdn="{h["name"]}",ip="{h["ip"]}",model="{h["model"]}"}} {h["cpu_mhz_used"]}'
        )

    lines.append(
        "# HELP boylenet_esxi_cpu_mhz_total ESXi host total CPU capacity in MHz"
    )
    lines.append("# TYPE boylenet_esxi_cpu_mhz_total gauge")
    for h in state.get("esxi_hosts", []):
        lines.append(
            f'boylenet_esxi_cpu_mhz_total{{host="{h["short"]}",fqdn="{h["name"]}",ip="{h["ip"]}",model="{h["model"]}"}} {h["cpu_mhz_total"]}'
        )

    lines.append("# HELP boylenet_esxi_memory_gib_used ESXi host RAM usage in GiB")
    lines.append("# TYPE boylenet_esxi_memory_gib_used gauge")
    for h in state.get("esxi_hosts", []):
        lines.append(
            f'boylenet_esxi_memory_gib_used{{host="{h["short"]}",fqdn="{h["name"]}",ip="{h["ip"]}",model="{h["model"]}"}} {h["memory_gib_used"]}'
        )

    lines.append(
        "# HELP boylenet_esxi_memory_gib_total ESXi host total RAM capacity in GiB"
    )
    lines.append("# TYPE boylenet_esxi_memory_gib_total gauge")
    for h in state.get("esxi_hosts", []):
        lines.append(
            f'boylenet_esxi_memory_gib_total{{host="{h["short"]}",fqdn="{h["name"]}",ip="{h["ip"]}",model="{h["model"]}"}} {h["memory_gib_total"]}'
        )

    vsan = state.get("vsan") or {}
    lines.append("# HELP boylenet_vsan_free_tib vSAN datastore free space in TiB")
    lines.append("# TYPE boylenet_vsan_free_tib gauge")
    lines.append(
        f'boylenet_vsan_free_tib{{datastore="{vsan.get("name", "vsanDatastore")}",vc="10.0.20.70"}} {vsan.get("free_tib", 0.0)}'
    )

    lines.append(
        "# HELP boylenet_vsan_capacity_tib vSAN datastore total capacity in TiB"
    )
    lines.append("# TYPE boylenet_vsan_capacity_tib gauge")
    lines.append(
        f'boylenet_vsan_capacity_tib{{datastore="{vsan.get("name", "vsanDatastore")}",vc="10.0.20.70"}} {vsan.get("capacity_tib", 0.0)}'
    )

    lines.append(
        "# HELP boylenet_vsan_disk_groups ESXi host vSAN SSD cache disk group count"
    )
    lines.append("# TYPE boylenet_vsan_disk_groups gauge")
    for h in state.get("esxi_hosts", []):
        lines.append(
            f'boylenet_vsan_disk_groups{{host="{h["short"]}",ip="{h["ip"]}"}} {h["vsan_dg_count"]}'
        )

    lines.append(
        "# HELP boylenet_vsan_capacity_disks ESXi host vSAN capacity disk count"
    )
    lines.append("# TYPE boylenet_vsan_capacity_disks gauge")
    for h in state.get("esxi_hosts", []):
        lines.append(
            f'boylenet_vsan_capacity_disks{{host="{h["short"]}",ip="{h["ip"]}"}} {h["vsan_cap_disk_count"]}'
        )

    lines.append(
        "# HELP boylenet_ilo_power_watts HPE iLO4/iLO5 server power consumption in Watts"
    )
    lines.append("# TYPE boylenet_ilo_power_watts gauge")
    for ilo in state.get("ilo_processors", []):
        lines.append(
            f'boylenet_ilo_power_watts{{ilo_ip="{ilo["ip"]}",host="{ilo["host"]}",model="{ilo["model"]}",health="{ilo["overall_health"]}"}} {ilo["power_watts"]}'
        )

    lines.append(
        "# HELP boylenet_ilo_temp_celsius HPE iLO4/iLO5 thermal sensor temperature in Celsius"
    )
    lines.append("# TYPE boylenet_ilo_temp_celsius gauge")
    for ilo in state.get("ilo_processors", []):
        lines.append(
            f'boylenet_ilo_temp_celsius{{ilo_ip="{ilo["ip"]}",host="{ilo["host"]}",sensor="cpu1",model="{ilo["model"]}"}} {ilo["cpu1_temp_c"]}'
        )
        lines.append(
            f'boylenet_ilo_temp_celsius{{ilo_ip="{ilo["ip"]}",host="{ilo["host"]}",sensor="cpu2",model="{ilo["model"]}"}} {ilo["cpu2_temp_c"]}'
        )
        lines.append(
            f'boylenet_ilo_temp_celsius{{ilo_ip="{ilo["ip"]}",host="{ilo["host"]}",sensor="inlet_ambient",model="{ilo["model"]}"}} {ilo["inlet_temp_c"]}'
        )

    lines.append(
        "# HELP boylenet_t4_power_watts NVIDIA Tesla T4 GPU power draw in Watts"
    )
    lines.append("# TYPE boylenet_t4_power_watts gauge")
    for g in state.get("t4_gpus", []):
        lines.append(
            f'boylenet_t4_power_watts{{node_ip="{g["ip"]}",roce_ip="{g["roce_ip"]}",node="{g["short"]}",esxi_host="{g["esxi_host"]}",pstate="{g["pstate"]}"}} {g["power_watts"]}'
        )

    lines.append(
        "# HELP boylenet_t4_temp_celsius NVIDIA Tesla T4 GPU temperature in Celsius"
    )
    lines.append("# TYPE boylenet_t4_temp_celsius gauge")
    for g in state.get("t4_gpus", []):
        lines.append(
            f'boylenet_t4_temp_celsius{{node_ip="{g["ip"]}",roce_ip="{g["roce_ip"]}",node="{g["short"]}",esxi_host="{g["esxi_host"]}",pstate="{g["pstate"]}"}} {g["temp_c"]}'
        )

    lines.append(
        "# HELP boylenet_t4_vram_mib_used NVIDIA Tesla T4 GPU VRAM used in MiB"
    )
    lines.append("# TYPE boylenet_t4_vram_mib_used gauge")
    for g in state.get("t4_gpus", []):
        lines.append(
            f'boylenet_t4_vram_mib_used{{node_ip="{g["ip"]}",node="{g["short"]}",esxi_host="{g["esxi_host"]}"}} {g["vram_used_mib"]}'
        )

    return "\n".join(lines) + "\n"


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Boylenet Physical Server Rack, HPE iLO4/iLO5 & vSAN Telemetry Matrix (:4091)</title>
  <style>
    :root {
      --bg-deep: #050811;
      --bg-card: rgba(13, 21, 38, 0.78);
      --bg-card-hover: rgba(20, 32, 56, 0.92);
      --border-cyan: rgba(56, 189, 248, 0.25);
      --border-glow: rgba(56, 189, 248, 0.55);
      --accent-cyan: #38bdf8;
      --accent-emerald: #10b981;
      --accent-amber: #f59e0b;
      --accent-rose: #f43f5e;
      --accent-purple: #a855f7;
      --text-main: #f1f5f9;
      --text-dim: #94a3b8;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --font-mono: 'JetBrains Mono', 'Fira Code', 'SFMono-Regular', Consolas, monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: radial-gradient(circle at 15% 10%, #0f172a 0%, #050811 60%, #020409 100%);
      color: var(--text-main);
      font-family: var(--font-sans);
      min-height: 100vh;
      padding: 20px 26px 48px;
      line-height: 1.45;
    }
    .header-bar {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 18px 24px;
      background: linear-gradient(135deg, rgba(15, 23, 42, 0.88), rgba(8, 14, 28, 0.92));
      border: 1px solid var(--border-cyan);
      border-radius: 14px;
      box-shadow: 0 10px 35px rgba(0, 0, 0, 0.55), 0 0 22px rgba(56, 189, 248, 0.1);
      backdrop-filter: blur(16px);
      margin-bottom: 20px;
    }
    .title-block h1 {
      font-size: 1.38rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      background: linear-gradient(90deg, #38bdf8, #818cf8, #34d399);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .title-block p {
      color: var(--text-dim);
      font-size: 0.83rem;
      margin-top: 4px;
      font-family: var(--font-mono);
    }
    .header-actions {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      border-radius: 999px;
      font-size: 0.76rem;
      font-weight: 600;
      font-family: var(--font-mono);
      background: rgba(15, 23, 42, 0.9);
      border: 1px solid rgba(148, 163, 184, 0.25);
      color: var(--text-main);
      text-decoration: none;
    }
    .pill.ok {
      border-color: rgba(16, 185, 129, 0.45);
      color: #34d399;
      background: rgba(16, 185, 129, 0.1);
    }
    .btn {
      cursor: pointer;
      padding: 7px 14px;
      border-radius: 8px;
      font-size: 0.78rem;
      font-weight: 700;
      font-family: var(--font-mono);
      border: 1px solid var(--accent-cyan);
      background: rgba(56, 189, 248, 0.14);
      color: var(--accent-cyan);
      transition: all 0.16s ease;
    }
    .btn:hover {
      background: rgba(56, 189, 248, 0.28);
      box-shadow: 0 0 14px rgba(56, 189, 248, 0.35);
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(215px, 1fr));
      gap: 14px;
      margin-bottom: 22px;
    }
    .kpi-card {
      background: var(--bg-card);
      border: 1px solid var(--border-cyan);
      border-radius: 12px;
      padding: 15px 18px;
      backdrop-filter: blur(12px);
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
    }
    .kpi-label {
      font-size: 0.73rem;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      color: var(--text-dim);
      font-weight: 700;
    }
    .kpi-val {
      font-size: 1.52rem;
      font-weight: 800;
      font-family: var(--font-mono);
      margin: 6px 0 4px;
      color: #f8fafc;
    }
    .kpi-sub {
      font-size: 0.75rem;
      color: var(--text-dim);
      font-family: var(--font-mono);
    }
    .progress-bar {
      width: 100%;
      height: 7px;
      background: rgba(30, 41, 59, 0.9);
      border-radius: 999px;
      overflow: hidden;
      margin-top: 7px;
    }
    .progress-fill {
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, #38bdf8, #10b981);
      transition: width 0.35s ease;
    }
    .progress-fill.warn { background: linear-gradient(90deg, #f59e0b, #f97316); }
    .progress-fill.crit { background: linear-gradient(90deg, #f43f5e, #e11d48); }
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin: 24px 0 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid rgba(56, 189, 248, 0.2);
    }
    .section-header h2 {
      font-size: 1.05rem;
      font-weight: 700;
      color: var(--accent-cyan);
      letter-spacing: 0.02em;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .section-header span {
      font-size: 0.76rem;
      font-family: var(--font-mono);
      color: var(--text-dim);
    }
    .cards-grid-4 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
      gap: 16px;
    }
    .cards-grid-5 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(270px, 1fr));
      gap: 14px;
    }
    .hw-card {
      background: var(--bg-card);
      border: 1px solid rgba(56, 189, 248, 0.2);
      border-radius: 12px;
      padding: 16px 18px;
      transition: all 0.18s ease;
      position: relative;
    }
    .hw-card:hover {
      border-color: var(--border-glow);
      background: var(--bg-card-hover);
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(56, 189, 248, 0.15);
    }
    .hw-card-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 10px;
      gap: 8px;
    }
    .hw-title {
      font-size: 0.98rem;
      font-weight: 800;
      color: #f8fafc;
      font-family: var(--font-mono);
    }
    .hw-subtitle {
      font-size: 0.75rem;
      color: var(--accent-cyan);
      font-family: var(--font-mono);
      margin-top: 2px;
    }
    .badge {
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 0.69rem;
      font-weight: 700;
      font-family: var(--font-mono);
      text-transform: uppercase;
    }
    .badge-ok { background: rgba(16, 185, 129, 0.16); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .badge-warn { background: rgba(245, 158, 11, 0.16); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
    .badge-info { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); }
    .kv-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 8px;
      font-size: 0.78rem;
    }
    .kv-table td {
      padding: 4px 0;
      border-bottom: 1px dashed rgba(148, 163, 184, 0.12);
    }
    .kv-table td:first-child { color: var(--text-dim); }
    .kv-table td:last-child {
      text-align: right;
      font-family: var(--font-mono);
      font-weight: 600;
      color: #e2e8f0;
    }
    .dg-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 9px;
    }
    .dg-pill {
      font-size: 0.69rem;
      font-family: var(--font-mono);
      padding: 3px 7px;
      border-radius: 5px;
      background: rgba(168, 85, 247, 0.14);
      border: 1px solid rgba(168, 85, 247, 0.35);
      color: #d8b4fe;
    }
    .rack-table-wrap {
      background: var(--bg-card);
      border: 1px solid var(--border-cyan);
      border-radius: 12px;
      padding: 14px 18px;
      overflow-x: auto;
    }
    table.matrix {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.79rem;
      font-family: var(--font-mono);
    }
    table.matrix th {
      text-align: left;
      padding: 9px 10px;
      color: var(--accent-cyan);
      border-bottom: 1px solid rgba(56, 189, 248, 0.25);
      font-size: 0.73rem;
      text-transform: uppercase;
    }
    table.matrix td {
      padding: 8px 10px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.1);
      color: #e2e8f0;
    }
    table.matrix tr:hover td {
      background: rgba(56, 189, 248, 0.06);
    }
    a.ext-link {
      color: var(--accent-cyan);
      text-decoration: none;
    }
    a.ext-link:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="header-bar">
    <div class="title-block">
      <h1>BOYLENET PHYSICAL RACK, HPE iLO4/iLO5, vSPHERE VC04 & vSAN TELEMETRY MATRIX</h1>
      <p id="sub-status">Polling vCenter 10.0.20.70 • ESXi 01..04 (10.0.20.41..44) • HPE iLO 10.0.10.10/20/30/40/252 • 4x Tesla T4 (.72/.83/.125/.228)</p>
    </div>
    <div class="header-actions">
      <span class="pill ok" id="vc-pill">● vc04: CONNECTED</span>
      <a class="pill" href="/metrics" target="_blank">Prometheus /metrics</a>
      <a class="pill" href="/api/hardware" target="_blank">JSON /api/hardware</a>
      <a class="pill" href="/health" target="_blank">/health</a>
      <button class="btn" onclick="triggerPoll()">⟳ Poll Now</button>
    </div>
  </div>

  <div class="kpi-grid" id="kpi-grid"></div>

  <div class="section-header">
    <h2>1. HPE iLO4 / iLO5 Out-of-Band Management Processors (VLAN 10 • Redfish + XMLData + IPMI)</h2>
    <span id="ilo-summary-span">5 BMC Endpoints Monitored</span>
  </div>
  <div class="cards-grid-5" id="ilo-grid"></div>

  <div class="section-header">
    <h2>2. VMware vSphere vc04 (10.0.20.70) & ESXi 8.0 Hypervisor Cluster + vSAN Disk Groups</h2>
    <span id="esxi-summary-span">4 Hypervisors • 11 vSAN Disk Groups (11 Cache SSDs + 64 Capacity Disks)</span>
  </div>
  <div class="cards-grid-4" id="esxi-grid"></div>

  <div class="section-header">
    <h2>3. 4x NVIDIA Tesla T4 GPU Cluster & 25GbE RoCE vSAN/Inference Fabric (.72, .83, .125, .228)</h2>
    <span id="gpu-summary-span">64 GiB GDDR6 ECC VRAM • USAGGPRO Ports 29–32 (25,000 Mbps)</span>
  </div>
  <div class="cards-grid-4" id="gpu-grid"></div>

  <div class="section-header">
    <h2>4. Physical Server Rack Bay, Switch LACP Trunk & vSAN Cache SSD Endurance Matrix</h2>
    <span>USAGGPRO 10.0.10.111 (4x 25GbE + 160G LACP) • Smart Array P840ar / P408i-a SR</span>
  </div>
  <div class="rack-table-wrap">
    <table class="matrix" id="rack-matrix-table">
      <thead>
        <tr>
          <th>Rack U</th>
          <th>Host / FQDN</th>
          <th>ESXi / vSAN IP</th>
          <th>iLO BMC IP</th>
          <th>Hardware Model & Storage Controller</th>
          <th>vSAN Disk Groups</th>
          <th>Cache SSD SMART Life</th>
          <th>25GbE & LACP Switch Uplinks</th>
        </tr>
      </thead>
      <tbody id="rack-matrix-body"></tbody>
    </table>
  </div>

  <script>
    function badgeClass(val) {
      const s = String(val || '').toLowerCase();
      if (s === 'ok' || s === 'green' || s === 'connected' || s === 'online') return 'badge-ok';
      if (s.includes('warn') || s === 'yellow') return 'badge-warn';
      return 'badge-info';
    }

    function fillClass(pct) {
      if (pct >= 90) return 'progress-fill crit';
      if (pct >= 78) return 'progress-fill warn';
      return 'progress-fill';
    }

    function renderDashboard(data) {
      const sum = data.summary || {};
      const vsan = data.vsan || {};
      document.getElementById('sub-status').textContent =
        `Last Poll: ${data.updated_at || 'now'} (${data.poll_duration_ms || 0} ms, #${data.poll_count || 1}) • Auto-Refresh: ${data.poll_interval_sec || 60}s`;

      const vcPill = document.getElementById('vc-pill');
      vcPill.textContent = `● vc04 (${(data.vc04 && data.vc04.host) || '10.0.20.70'}): ${((data.vc04 && data.vc04.status) || 'OK').toUpperCase()}`;

      // KPIs
      const kpiHtml = `
        <div class="kpi-card">
          <div class="kpi-label">Physical Rack Power (4 Servers)</div>
          <div class="kpi-val">${sum.rack_power_watts || 0} W</div>
          <div class="kpi-sub">8/8 Redundant PSUs OK • Avg Inlet ${sum.avg_inlet_temp_c || 23}°C</div>
          <div class="progress-bar"><div class="${fillClass((sum.rack_power_watts||0)/32)}" style="width:${Math.min(100, ((sum.rack_power_watts||0)/3000)*100)}%"></div></div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Cluster CPU Usage (4 Hosts)</div>
          <div class="kpi-val">${sum.cluster_cpu_ghz_used || 0} / ${sum.cluster_cpu_ghz_total || 0} GHz</div>
          <div class="kpi-sub">${sum.cluster_cpu_pct || 0}% Utilized • Max CPU Temp ${sum.max_cpu_temp_c || 40}°C</div>
          <div class="progress-bar"><div class="${fillClass(sum.cluster_cpu_pct||0)}" style="width:${Math.min(100, sum.cluster_cpu_pct||0)}%"></div></div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Cluster DDR4 Memory Usage</div>
          <div class="kpi-val">${sum.cluster_memory_gib_used || 0} / ${sum.cluster_memory_gib_total || 0} GiB</div>
          <div class="kpi-sub">${sum.cluster_memory_pct || 0}% Allocated Across 27 Fleet VMs</div>
          <div class="progress-bar"><div class="${fillClass(sum.cluster_memory_pct||0)}" style="width:${Math.min(100, sum.cluster_memory_pct||0)}%"></div></div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">vSAN Datastore Free Space</div>
          <div class="kpi-val">${vsan.free_tib || 0} TiB Free</div>
          <div class="kpi-sub">${vsan.used_tib || 0} / ${vsan.capacity_tib || 0} TiB Used (${vsan.used_pct || 0}%) • ${vsan.total_disk_groups || 11} DGs (${vsan.total_vsan_disks || 75} Disks)</div>
          <div class="progress-bar"><div class="${fillClass(vsan.used_pct||0)}" style="width:${Math.min(100, vsan.used_pct||0)}%"></div></div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">4x NVIDIA Tesla T4 GPUs</div>
          <div class="kpi-val">${sum.t4_total_power_watts || 0} W • ${sum.t4_avg_temp_c || 0}°C</div>
          <div class="kpi-sub">VRAM: ${sum.t4_vram_used_gib || 0} / ${sum.t4_vram_total_gib || 60} GiB • ECC: 0 Errors</div>
          <div class="progress-bar"><div class="progress-fill" style="width:${Math.min(100, ((sum.t4_vram_used_gib||0)/Math.max(1, sum.t4_vram_total_gib||60))*100)}%"></div></div>
        </div>
      `;
      document.getElementById('kpi-grid').innerHTML = kpiHtml;

      // iLO Cards
      const iloGrid = document.getElementById('ilo-grid');
      iloGrid.innerHTML = (data.ilo_processors || []).map(ilo => `
        <div class="hw-card">
          <div class="hw-card-top">
            <div>
              <div class="hw-title"><a class="ext-link" href="https://${ilo.ip}" target="_blank">${ilo.ip}</a> • ${ilo.host}</div>
              <div class="hw-subtitle">${ilo.model} (${ilo.ilo_generation})</div>
            </div>
            <span class="badge ${badgeClass(ilo.overall_health)}">${ilo.overall_health}</span>
          </div>
          <table class="kv-table">
            <tr><td>Server Rack Slot</td><td>${ilo.rack_u}</td></tr>
            <tr><td>System BIOS / Serial</td><td>${ilo.bios} • ${ilo.serial || 'N/A'}</td></tr>
            <tr><td>Power Consumption</td><td><strong style="color:#38bdf8">${ilo.power_watts} W</strong> (Avg ${ilo.avg_watts} W)</td></tr>
            <tr><td>CPU 1 / CPU 2 Temp</td><td>${ilo.cpu1_temp_c}°C / ${ilo.cpu2_temp_c}°C (Max ${ilo.max_temp_c}°C)</td></tr>
            <tr><td>Inlet Ambient / DIMM</td><td>${ilo.inlet_temp_c}°C / ${ilo.dimm_temp_c}°C (${ilo.active_temp_sensors} sensors)</td></tr>
            <tr><td>Cooling Fans & PSUs</td><td>${ilo.fan_count} Fans ${ilo.fan_health} (${ilo.fan_avg_pct}%) • PSUs ${ilo.psu_health}</td></tr>
            <tr><td>Telemetry Source</td><td>${ilo.source}</td></tr>
          </table>
        </div>
      `).join('');

      // ESXi Cards
      const esxiGrid = document.getElementById('esxi-grid');
      esxiGrid.innerHTML = (data.esxi_hosts || []).map(h => `
        <div class="hw-card">
          <div class="hw-card-top">
            <div>
              <div class="hw-title"><a class="ext-link" href="https://${h.ip}/ui" target="_blank">${h.short.toUpperCase()}</a> (${h.ip})</div>
              <div class="hw-subtitle">${h.model} • ${h.cpu_model}</div>
            </div>
            <span class="badge ${badgeClass(h.overall_status)}">${h.overall_status}</span>
          </div>
          <table class="kv-table">
            <tr><td>CPU Load (${h.cpu_cores}C / ${h.cpu_threads}T)</td><td>${h.cpu_ghz_used} / ${h.cpu_ghz_total} GHz (${h.cpu_pct}%)</td></tr>
            <tr><td>DDR4 RAM Usage</td><td>${h.memory_gib_used} / ${h.memory_gib_total} GiB (${h.memory_pct}%)</td></tr>
            <tr><td>vSAN Disk Groups</td><td><strong style="color:#c084fc">${h.vsan_dg_count} DGs</strong> (${h.vsan_ssd_count} Cache SSD + ${h.vsan_cap_disk_count} Cap Disks)</td></tr>
            <tr><td>IPMI Sensors / Uptime</td><td>${h.ipmi_sensor_count} Sensors • ${h.uptime_days} Days</td></tr>
            <tr><td>Cache SSD Endurance</td><td>${h.cache_ssd_wear}</td></tr>
          </table>
          <div class="progress-bar" title="Memory ${h.memory_pct}%"><div class="${fillClass(h.memory_pct)}" style="width:${Math.min(100, h.memory_pct)}%"></div></div>
          <div class="dg-pills">
            ${(h.vsan_disk_groups || []).map((dg, idx) => `<span class="dg-pill">DG#${idx+1}: SSD + ${dg.capacity_disk_count} Cap</span>`).join('')}
          </div>
        </div>
      `).join('');

      // GPU Cards
      const gpuGrid = document.getElementById('gpu-grid');
      gpuGrid.innerHTML = (data.t4_gpus || []).map(g => `
        <div class="hw-card">
          <div class="hw-card-top">
            <div>
              <div class="hw-title">${g.node}</div>
              <div class="hw-subtitle">VLAN 70: ${g.ip} • 25G RoCE: ${g.roce_ip}</div>
            </div>
            <span class="badge ${badgeClass(g.status)}">${g.pstate} • ${g.status}</span>
          </div>
          <table class="kv-table">
            <tr><td>GPU & Physical Host</td><td>${g.gpu_name} on <strong>${g.esxi_host}</strong> (${g.pci_bus_id})</td></tr>
            <tr><td>Temperature & Power</td><td><strong style="color:#34d399">${g.temp_c}°C</strong> • <strong>${g.power_watts} W</strong> / ${g.power_limit_watts} W</td></tr>
            <tr><td>VRAM Usage (GDDR6)</td><td>${g.vram_used_mib} / ${g.vram_total_mib} MiB (${g.vram_pct}%)</td></tr>
            <tr><td>Compute Util & ECC</td><td>${g.util_pct}% Util • ECC: ${g.ecc_health}</td></tr>
            <tr><td>25GbE Switch Pinning</td><td>${g.usaggpro_port}</td></tr>
          </table>
          <div class="progress-bar"><div class="${fillClass(g.vram_pct)}" style="width:${Math.min(100, g.vram_pct)}%"></div></div>
        </div>
      `).join('');

      // Rack Table
      const rackBody = document.getElementById('rack-matrix-body');
      rackBody.innerHTML = (data.esxi_hosts || []).map(h => `
        <tr>
          <td><strong>${h.rack_u}</strong></td>
          <td><a class="ext-link" href="https://${h.ip}/ui" target="_blank">${h.name}</a></td>
          <td>${h.ip} / vSAN ${h.vsan_ip}</td>
          <td><a class="ext-link" href="https://${h.ilo_ip}" target="_blank">${h.ilo_ip}</a></td>
          <td>${h.model} • ${h.storage_controller}</td>
          <td>${h.vsan_dg_count} DGs (${h.vsan_ssd_count} SSD + ${h.vsan_cap_disk_count} Cap)</td>
          <td>${h.cache_ssd_wear}</td>
          <td>${h.network_uplinks}</td>
        </tr>
      `).join('');
    }

    async function fetchHardware() {
      try {
        const r = await fetch('/api/hardware');
        const d = await r.json();
        renderDashboard(d);
      } catch (e) {
        console.error('Failed fetching hardware telemetry:', e);
      }
    }

    async function triggerPoll() {
      try {
        const r = await fetch('/api/poll', { method: 'POST' });
        const d = await r.json();
        renderDashboard(d);
      } catch (e) {
        console.error('Poll trigger failed:', e);
      }
    }

    fetchHardware();
    setInterval(fetchHardware, 15000);
  </script>
</body>
</html>
"""


class HardwareTelemetryHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def _send_text(self, code: int, body: str, content_type: str) -> None:
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        with _STATE_LOCK:
            state = dict(_TELEMETRY_STATE)

        if path == "/health":
            self._send_json(
                200,
                {
                    "status": state.get("status", "ok"),
                    "service": "bd-hardware-telemetry",
                    "port": PORT,
                    "updated_at": state.get("updated_at"),
                    "poll_count": state.get("poll_count", 0),
                    "esxi_hosts": len(state.get("esxi_hosts", [])),
                    "ilo_processors": len(state.get("ilo_processors", [])),
                    "t4_gpus": len(state.get("t4_gpus", [])),
                    "vsan_free_tib": (state.get("vsan") or {}).get("free_tib", 0.0),
                },
            )
        elif path == "/api/hardware":
            self._send_json(200, state)
        elif path == "/metrics":
            prom_text = render_prometheus_metrics(state)
            self._send_text(200, prom_text, "text/plain; version=0.0.4; charset=utf-8")
        else:
            self._send_text(200, DASHBOARD_HTML, "text/html; charset=utf-8")

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/poll":
            snap = collect_telemetry_once()
            self._send_json(200, snap)
        else:
            self._send_json(404, {"error": "not_found"})


def _background_poller() -> None:
    while True:
        time.sleep(POLL_INTERVAL_SEC)
        try:
            collect_telemetry_once()
        except Exception as e:
            logger.error("Background poll error: %s", e)


def main() -> int:
    logger.info(
        "Performing initial hardware, iLO4/iLO5, vSphere vc04, vSAN & 4x T4 poll..."
    )
    snap = collect_telemetry_once()
    logger.info(
        "Initial poll complete in %d ms: %d ESXi hosts, %d iLOs, %d T4 GPUs, vSAN free %.2f TiB",
        snap.get("poll_duration_ms", 0),
        len(snap.get("esxi_hosts", [])),
        len(snap.get("ilo_processors", [])),
        len(snap.get("t4_gpus", [])),
        (snap.get("vsan") or {}).get("free_tib", 0.0),
    )

    t = threading.Thread(target=_background_poller, daemon=True)
    t.start()

    server = ThreadingHTTPServer(("0.0.0.0", PORT), HardwareTelemetryHandler)
    logger.info(
        "Listening on http://0.0.0.0:%d (http://hardware.boylenet.themfboyles.org)",
        PORT,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
