import concurrent.futures
import subprocess
import time
TARGET_HOSTS = ["10.0.70.50", "10.0.70.51", "10.0.70.52", "10.0.70.53", "10.0.70.54", "10.0.70.194", "10.0.70.95", "10.0.70.80", "10.0.70.82", "10.0.70.85", "10.0.70.249", "10.0.70.84", "10.0.70.120", "10.0.70.183", "10.0.70.149", "10.0.70.197", "10.0.70.193", "10.0.70.81", "10.0.70.185", "10.0.70.186", "10.0.70.187", "10.0.70.184", "10.0.70.196", "10.0.70.195", "10.0.70.35", "10.0.70.171", "10.0.70.121", "10.0.70.86", "10.0.70.122", "10.0.70.224", "10.0.70.198", "10.0.70.25", "10.0.70.162", "10.0.70.107", "10.0.70.182", "10.0.70.83", "10.0.70.228", "10.0.70.125", "10.0.70.72"]

def sync_host(ip: str):
    start = time.time()
    ping_cmd = ["ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4", "-o", "StrictHostKeyChecking=no", "-o", "ControlMaster=no", "-o", "ControlPath=none", f"mboyle@{ip}", "true"]
    try:
        subprocess.check_call(ping_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=6)
    except (subprocess.SubprocessError, OSError) as e:
        return (ip, False, f"unreachable: {e}")
    try:
        subprocess.check_call(["/home/mboyle/bin/bd-fleet-sync-parity.sh", ip], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180)
    except subprocess.CalledProcessError as e:
        err = (e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)).strip()
        return (ip, False, f"sync failed: {err[:120]}")
    except (subprocess.SubprocessError, OSError) as e:
        return (ip, False, f"sync error: {e}")
    elapsed = round(time.time() - start, 1)
    return (ip, True, f"synced in {elapsed}s")

def main():
    print(f"Starting parallel reconciliation across {len(TARGET_HOSTS)} fleet hosts (concurrency=8)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(sync_host, TARGET_HOSTS))
    success = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]
    print(f"\nReconciliation Summary: {len(success)} SUCCESS, {len(failed)} UNREACHABLE/FAILED")
    for ip, ok, msg in results:
        print(f"  {ip:15}: {'PASS' if ok else 'SKIP/FAIL'} ({msg})")
if __name__ == "__main__":
    main()
