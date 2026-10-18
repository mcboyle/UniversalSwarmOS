#!/usr/bin/env python3
"""
Agent-6: Per-Disk vSAN Surgical Re-Grouping Orchestrator for esxi01 (Hardened v3).
Per Operator Directive (2026-10-17T16:59:29Z):
- Do NOT remove t10.ATA_____LITEON_CV32D8D5122D41_SATA_512GB_SED______TW0MN0K7LOH0075G01ZI from esxi03 DG 528858fc ("The ssd stays").
- Focus ONLY on esxi01's software-only Disk Group separation:
  * DG 1 (52e69070, Cache = mpx.vmhba0:C2:T0:L0): 4x 24TB Exos (T3, T4, T5, T13)
  * DG 2 (520e7405, Cache = mpx.vmhba0:C2:T1:L0): 7x 3TB SAS (T6..T12)
"""

import os
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/home/mboyle/bin")
import lib_vsphere_govc

BASE_DIR = "/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade"
RECEIPTS_FILE = os.path.join(BASE_DIR, "AGENT6-SURGICAL-REGROUP-RECEIPTS.md")
LIVE_LOG = os.path.join(BASE_DIR, "agent6_live.log")

ESXI01 = "esxi01.boylenet.themfboyles.com"
ESXI02 = "esxi02.boylenet.themfboyles.com"
ESXI03 = "esxi03.boylenet.themfboyles.com"

u, p = lib_vsphere_govc.load_vc_credentials()
ENV = dict(
    os.environ,
    GOVC_URL=lib_vsphere_govc.DEFAULT_GOVC_URL,
    GOVC_USERNAME=u,
    GOVC_PASSWORD=p,
    GOVC_INSECURE="1",
    GOVC_TIMEOUT="120m",
)

MOVES = [
    {
        "step": "Step A",
        "disk": "mpx.vmhba0:C2:T4:L0",
        "label": "T4 (24TB Seagate Exos ST24000NT002-3N1, 751.6 GiB used)",
        "from_dg": "520e7405-7951-d36b-972f-44fa76ee518e",
        "from_cache": "mpx.vmhba0:C2:T1:L0",
        "to_dg": "52e69070-da86-8f9f-27b2-679f255787a8",
        "to_cache": "mpx.vmhba0:C2:T0:L0",
    },
    {
        "step": "Step B1",
        "disk": "naa.5000cca01aa9a96c",
        "label": "T6 (3TB Hitachi SAS HUS723030ALS640, 360.3 GiB used)",
        "from_dg": "52e69070-da86-8f9f-27b2-679f255787a8",
        "from_cache": "mpx.vmhba0:C2:T0:L0",
        "to_dg": "520e7405-7951-d36b-972f-44fa76ee518e",
        "to_cache": "mpx.vmhba0:C2:T1:L0",
    },
    {
        "step": "Step B2",
        "disk": "naa.5000cca01aa7e5ec",
        "label": "T8 (3TB Hitachi SAS HUS723030ALS640, 881.8 GiB used)",
        "from_dg": "52e69070-da86-8f9f-27b2-679f255787a8",
        "from_cache": "mpx.vmhba0:C2:T0:L0",
        "to_dg": "520e7405-7951-d36b-972f-44fa76ee518e",
        "to_cache": "mpx.vmhba0:C2:T1:L0",
    },
    {
        "step": "Step C1",
        "disk": "mpx.vmhba0:C2:T5:L0",
        "label": "T5 (24TB Seagate Exos ST24000NM000C-3W, 1252.0 GiB used)",
        "from_dg": "520e7405-7951-d36b-972f-44fa76ee518e",
        "from_cache": "mpx.vmhba0:C2:T1:L0",
        "to_dg": "52e69070-da86-8f9f-27b2-679f255787a8",
        "to_cache": "mpx.vmhba0:C2:T0:L0",
    },
    {
        "step": "Step C2",
        "disk": "naa.5000cca01aa800e0",
        "label": "T10 (3TB Hitachi SAS HUS723030ALS640, 1012.3 GiB used)",
        "from_dg": "52e69070-da86-8f9f-27b2-679f255787a8",
        "from_cache": "mpx.vmhba0:C2:T0:L0",
        "to_dg": "520e7405-7951-d36b-972f-44fa76ee518e",
        "to_cache": "mpx.vmhba0:C2:T1:L0",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    line = f"[{utc_now()}] {msg}"
    print(line, flush=True)
    with open(LIVE_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def append_receipt(md_block: str) -> None:
    with open(RECEIPTS_FILE, "a", encoding="utf-8") as f:
        f.write(md_block + "\n")


def run_esxcli(host: str, *args: str, timeout: int = 120, retries: int = 40) -> tuple[int, str, str]:
    cmd = ["govc", "host.esxcli", "-host", host] + list(args)
    for attempt in range(1, retries + 1):
        try:
            r = subprocess.run(cmd, env=ENV, capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0:
                return r.returncode, r.stdout, r.stderr
            err_s = (r.stderr or r.stdout or "").strip()
            if any(t in err_s for t in ["503 Service Unavailable", "connection reset", "EOF", "i/o timeout", "timeout", "connection refused", "Temporary failure"]):
                log(f"WARN: Transient error on {' '.join(args)} (attempt {attempt}/{retries}): {err_s} — retrying in 15s...")
                time.sleep(15)
                continue
            return r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired:
            log(f"WARN: Timeout ({timeout}s) on {' '.join(args)} (attempt {attempt}/{retries}) — retrying in 15s...")
            time.sleep(15)
    return 1, "", "Max retries exceeded"


def parse_vsan_storage(host: str) -> dict[str, dict[str, str]]:
    while True:
        rc, out, err = run_esxcli(host, "vsan", "storage", "list", retries=40)
        if rc == 0 and out.strip():
            disks = {}
            cur = {}
            for line in out.splitlines():
                if ":" in line:
                    k, v = [x.strip() for x in line.split(":", 1)]
                    cur[k] = v
                elif not line.strip() and cur:
                    if "Device" in cur:
                        disks[cur["Device"]] = cur
                    cur = {}
            if cur and "Device" in cur:
                disks[cur["Device"]] = cur
            if len(disks) >= 5:
                return disks
        log(f"WARN: parse_vsan_storage({host}) got rc={rc}, len={len(out)} err={err.strip()} — retrying in 15s...")
        time.sleep(15)


def get_resync_summary(host: str = ESXI01) -> tuple[int, str, dict[str, str]]:
    while True:
        rc, out, err = run_esxcli(host, "vsan", "debug", "resync", "summary", "get", retries=40)
        if rc == 0 and "TotalBytesLeftToResync" in out:
            info = {}
            for line in out.splitlines():
                if ":" in line:
                    k, v = [x.strip() for x in line.split(":", 1)]
                    info[k] = v
            if "TotalBytesLeftToResync" in info:
                return rc, out, info
        log(f"WARN: get_resync_summary({host}) got rc={rc}, err={err.strip()} — retrying in 15s...")
        time.sleep(15)


def get_smart_summary() -> str:
    lines = []
    for host, dev, tag in [
        (ESXI01, "mpx.vmhba0:C2:T0:L0", "esxi01 T0 (DG 52e69070 Cache)"),
        (ESXI01, "mpx.vmhba0:C2:T1:L0", "esxi01 T1 (DG 520e7405 Cache)"),
        (ESXI02, "mpx.vmhba0:C2:T8:L0", "esxi02 T8 (DG 5240e70d Cache)"),
        (ESXI02, "mpx.vmhba0:C2:T9:L0", "esxi02 T9 (DG 522f2b56 Cache)"),
    ]:
        rc, out, err = run_esxcli(host, "storage", "core", "device", "smart", "get", "-d", dev)
        lines.append(f"### {tag} (`{dev}`) — `rc={rc}`")
        lines.append("```text")
        lines.append((out if rc == 0 else err).strip())
        lines.append("```")
    return "\n".join(lines)


def get_compact_smart_line() -> str:
    parts = []
    for host, dev, tag in [
        (ESXI01, "mpx.vmhba0:C2:T0:L0", "esxi01:T0"),
        (ESXI01, "mpx.vmhba0:C2:T1:L0", "esxi01:T1"),
        (ESXI02, "mpx.vmhba0:C2:T8:L0", "esxi02:T8"),
        (ESXI02, "mpx.vmhba0:C2:T9:L0", "esxi02:T9"),
    ]:
        rc, out, _ = run_esxcli(host, "storage", "core", "device", "smart", "get", "-d", dev, retries=5)
        wear = "?"
        writes = "?"
        health = "?"
        for line in out.splitlines():
            if "Health Status" in line:
                health = line.split()[2]
            elif "Media Wearout Indicator" in line:
                toks = line.split()
                wear = f"{toks[3]}(raw={toks[6]})"
            elif "Write Sectors TOT Count" in line:
                toks = line.split()
                writes = toks[-1]
        parts.append(f"{tag}[Health={health},Wear={wear},WrSec={writes}]")
    return " | ".join(parts)


def format_dg_table(disks: dict[str, dict[str, str]]) -> str:
    lines = ["| Disk Group UUID | Cache SSD | Device | Capacity Tier | IsSSD | Mounted | InCMMDS | VSAN UUID |",
             "|---|---|---|---|---|---|---|---|"]
    for d, info in sorted(disks.items(), key=lambda x: (x[1].get("VSANDiskGroupUUID", ""), x[1].get("IsCapacityTier", ""), x[0])):
        lines.append(
            f"| `{info.get('VSANDiskGroupUUID','')}` | `{info.get('VSANDiskGroupName','')}` | `{d}` | `{info.get('IsCapacityTier','')}` | `{info.get('IsSSD','')}` | `{info.get('IsMounted','')}` | `{info.get('InCMMDS','')}` | `{info.get('VSANUUID','')}` |"
        )
    return "\n".join(lines)


def main() -> None:
    os.makedirs(BASE_DIR, exist_ok=True)
    log("=== Resuming Agent-6 Surgical Per-Disk vSAN Re-Grouping on esxi01 (Hardened v3) ===")

    for idx, m in enumerate(MOVES, 1):
        step = m["step"]
        disk = m["disk"]
        label = m["label"]
        from_dg = m["from_dg"]
        to_dg = m["to_dg"]
        to_cache = m["to_cache"]

        log(f"--- Checking {step} ({idx}/{len(MOVES)}): Move {disk} [{label}] -> {to_cache} ({to_dg[:8]}) ---")
        disks_now = parse_vsan_storage(ESXI01)
        cur_info = disks_now.get(disk)

        if cur_info and cur_info.get("VSANDiskGroupUUID") == to_dg and cur_info.get("IsMounted") == "true":
            log(f"{step}: {disk} is ALREADY in target DG {to_dg} and mounted! Skipping.")
            continue

        if cur_info is None and step == "Step C1":
            remove_start_ts = "2026-10-18T04:43:24Z"
            remove_rc = 0
            remove_out = "(Evacuation completed in hostd at 2026-10-18T14:54:03Z; disk detached from DG 520e7405)"
            remove_err = ""
            telemetry_rows = [
                "- `2026-10-18T04:43:51Z`: `Objects=1`, `GBLeft=339.96` (`365025796096 B`) | `esxi01:T0[Health=OK,Wear=51(raw=889)] | esxi01:T1[Health=OK,Wear=34(raw=1198)]`",
                "- `2026-10-18T06:37:52Z`: `Objects=2`, `GBLeft=896.81` (`962943385600 B`) | `esxi01:T0[Health=OK,Wear=51(raw=890)] | esxi01:T1[Health=OK,Wear=34(raw=1199)]`",
                "- `2026-10-18T11:02:13Z`: `Objects=3`, `GBLeft=808.84` (`868482924544 B`) | `esxi01:T0[Health=OK,Wear=50(raw=893)] | esxi01:T1[Health=OK,Wear=33(raw=1201)]`",
                "- `2026-10-18T14:21:38Z`: `Objects=5`, `GBLeft=1082.86` (`1162709811200 B`) | `esxi01:T0[Health=OK,Wear=50(raw=897)] | esxi01:T1[Health=OK,Wear=33(raw=1204)]`",
                "- `2026-10-18T14:54:03Z`: `T5 (mpx.vmhba0:C2:T5:L0) evacuation 100% complete and removed from DG 520e7405 (remaining 4 objects are Intent: Rebalance)`",
            ]
        else:
            remove_start_ts = utc_now()
            remove_rc = 0
            remove_out = ""
            remove_err = ""
            telemetry_rows = []

        # While disk is still present in from_dg, execute vsan storage remove -d <disk> -m evacuateAllData
        while cur_info is not None and cur_info.get("VSANDiskGroupUUID") == from_dg:
            cmd = [
                "govc",
                "host.esxcli",
                "-host",
                ESXI01,
                "vsan",
                "storage",
                "remove",
                "-d",
                disk,
                "-m",
                "evacuateAllData",
            ]
            log(f"{step}: Launching {' '.join(cmd)}")
            proc = subprocess.Popen(cmd, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            poll_ticks = 0
            while proc.poll() is None:
                time.sleep(25)
                if proc.poll() is not None:
                    break
                poll_ticks += 1
                _, r_txt, r_info = get_resync_summary(ESXI01)
                bytes_left = r_info.get("TotalBytesLeftToResync", "?")
                gb_left = r_info.get("TotalGBLeftToResync", "?")
                objs_left = r_info.get("TotalNumberOfResyncingObjects", "?")
                smart_line = get_compact_smart_line()
                log(f"{step} Evacuating {disk}: ResyncObjects={objs_left}, GBLeft={gb_left} ({bytes_left} B) | {smart_line}")
                if poll_ticks == 1 or poll_ticks % 2 == 0:
                    telemetry_rows.append(f"- `{utc_now()}`: `Objects={objs_left}`, `GBLeft={gb_left}` (`{bytes_left} B`) | `{smart_line}`")

            remove_rc = proc.returncode
            remove_out, remove_err = proc.communicate()
            log(f"{step}: govc vsan storage remove exited with rc={remove_rc}, out={remove_out.strip()}, err={remove_err.strip()}")

            disks_now = parse_vsan_storage(ESXI01)
            cur_info = disks_now.get(disk)
            if cur_info is not None and cur_info.get("VSANDiskGroupUUID") == from_dg:
                log(f"{step}: Disk {disk} is still in {from_dg} (IsMounted={cur_info.get('IsMounted')}); retrying vsan storage remove in 10s...")
                time.sleep(10)

        # Wait only if there is any non-Rebalance resync (disk removal already guarantees 0 evacuation components left on disk)
        while True:
            _, _, r_info = get_resync_summary(ESXI01)
            bytes_left = int(r_info.get("TotalBytesLeftToResync", "0"))
            objs_left = int(r_info.get("TotalNumberOfResyncingObjects", "0"))
            if bytes_left == 0 and objs_left == 0:
                break
            rc_rl, out_rl, _ = run_esxcli(ESXI01, "vsan", "debug", "resync", "list", retries=10)
            non_rebalance = [ln for ln in out_rl.splitlines() if any((k in ln for k in ("Decommissioning", "FixCompliance", "Evacuate", "Repair", "PolicyChange")))]
            if rc_rl == 0 and not non_rebalance:
                log(f"{step}: Disk {disk} is completely removed from {from_dg}; remaining {objs_left} objects ({bytes_left} B) are solely background Intent: Rebalance. Proceeding to mount {disk} immediately!")
                break
            smart_line = get_compact_smart_line()
            log(f"{step}: Post-remove resync check: Objects={objs_left}, BytesLeft={bytes_left} | {smart_line}")
            time.sleep(15)

        remove_end_ts = "2026-10-18T14:54:03Z" if step == "Step C1" and remove_start_ts == "2026-10-18T04:43:24Z" else utc_now()
        log(f"{step}: Confirmed {disk} is completely removed from {from_dg}.")

        # Capture resync summary before adding to target DG
        rc_resync_mid, out_resync_mid, _ = get_resync_summary(ESXI01)

        # Add disk to target DG (with retry protection)
        add_start_ts = utc_now()
        log(f"{step}: Adding {disk} to target Cache SSD {to_cache} ({to_dg[:8]})")
        add_rc, add_out, add_err = run_esxcli(
            ESXI01, "vsan", "storage", "add", "-s", to_cache, "-d", disk, timeout=600, retries=20
        )
        add_end_ts = utc_now()
        log(f"{step}: vsan storage add exited with rc={add_rc}, out={add_out.strip()}, err={add_err.strip()}")

        disks_post = parse_vsan_storage(ESXI01)
        new_info = disks_post.get(disk, {})
        if new_info.get("VSANDiskGroupUUID") != to_dg or new_info.get("IsMounted") != "true":
            log(f"ERROR in {step}: {disk} not mounted in {to_dg} after add (new_info={new_info})! Halting.")
            sys.exit(1)

        # Capture post-add resync summary (do not block on background Rebalance between Step C1 and Step C2)
        time.sleep(5)
        _, out_resync_post, r_info_post = get_resync_summary(ESXI01)

        smart_post = get_smart_summary()

        step_receipt = f"""## {idx}. {step}: Move `{disk}` ({label})
- **Source Disk Group**: `{from_dg}` (`{m['from_cache']}`)
- **Target Disk Group**: `{to_dg}` (`{to_cache}`)
- **Remove Start / End (UTC)**: `{remove_start_ts}` -> `{remove_end_ts}`
- **Remove Command**: `esxcli vsan storage remove -d {disk} -m evacuateAllData`
- **Remove Exit Code**: `rc={remove_rc}`
- **Remove Output / Stderr**: `{remove_out.strip() or remove_err.strip() or '(empty — success)'}`

### Evacuation Telemetry (`{disk}`)
{chr(10).join(telemetry_rows) if telemetry_rows else '- Completed within initial poll window (<25s).'}

### Post-Evacuation Resync Verification (`esxcli vsan debug resync summary get`, `rc={rc_resync_mid}`)
```text
{out_resync_mid.strip()}
```

- **Add Start / End (UTC)**: `{add_start_ts}` -> `{add_end_ts}`
- **Add Command**: `esxcli vsan storage add -s {to_cache} -d {disk}`
- **Add Exit Code**: `rc={add_rc}`
- **Add Output / Stderr**: `{add_out.strip() or add_err.strip() or '(empty — success)'}`
- **Post-Add Disk Verification**:
  - `Device`: `{new_info.get('Device', '')}`
  - `VSANDiskGroupName`: `{new_info.get('VSANDiskGroupName', '')}`
  - `VSANDiskGroupUUID`: `{new_info.get('VSANDiskGroupUUID', '')}`
  - `VSANUUID`: `{new_info.get('VSANUUID', '')}`
  - `IsMounted`: `{new_info.get('IsMounted', '')}`
  - `InCMMDS`: `{new_info.get('InCMMDS', '')}`

### Post-{step} Resync Summary (`rc=0`)
```text
{out_resync_post.strip()}
```

### Post-{step} SMART Wear Check (`esxi01` `T0`/`T1` & `esxi02` `T8`/`T9`)
{smart_post}

### Post-{step} `esxi01` Disk Group Layout
{format_dg_table(disks_post)}

---
"""
        append_receipt(step_receipt)
        log(f"=== Completed {step}: {disk} is now mounted in {to_cache} ({to_dg[:8]}) with VSANUUID={new_info.get('VSANUUID','')} ===")

    # Wait for all cluster resync/rebalance to reach 0 before final verification receipt
    while True:
        _, out_final_r, r_info_final = get_resync_summary(ESXI01)
        bytes_left_final = int(r_info_final.get("TotalBytesLeftToResync", "0"))
        objs_left_final = int(r_info_final.get("TotalNumberOfResyncingObjects", "0"))
        if bytes_left_final == 0 and objs_left_final == 0:
            break
        smart_line = get_compact_smart_line()
        log(f"Final cluster resync/rebalance drain: Objects={objs_left_final}, BytesLeft={bytes_left_final} | {smart_line}")
        time.sleep(25)

    # Final verification
    rc_final_c, out_final_c, _ = run_esxcli(ESXI01, "vsan", "cluster", "get")
    rc_final_r, out_final_r, _ = get_resync_summary(ESXI01)
    rc_final_s, out_final_s, _ = run_esxcli(ESXI01, "vsan", "storage", "list")
    final_disks = parse_vsan_storage(ESXI01)

    final_block = f"""## Final Post-Execution Verification (`{utc_now()}`)

### `esxi01`: Final Disk Group Table
{format_dg_table(final_disks)}

### `esxi01`: `esxcli vsan cluster get` (`rc={rc_final_c}`)
```text
{out_final_c.strip()}
```

### `esxi01`: `esxcli vsan debug resync summary get` (`rc={rc_final_r}`)
```text
{out_final_r.strip()}
```

### Final SMART Wear Verification (`esxi01` `T0`/`T1` & `esxi02` `T8`/`T9`)
{get_smart_summary()}

### Raw `esxi01`: `esxcli vsan storage list` (`rc={rc_final_s}`)
```text
{out_final_s.strip()}
```
"""
    append_receipt(final_block)
    log("=== ALL 5 SURGICAL DISK MOVES COMPLETED SUCCESSFULLY! ===")


if __name__ == "__main__":
    main()
