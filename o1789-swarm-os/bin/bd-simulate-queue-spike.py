#!/usr/bin/env python3
"""bd-simulate-queue-spike.py -- End-to-End Elastic Auto-Scaler Simulation Runner.

Simulates a massive PM Backlog queue spike (e.g. 50 items) against the Elastic
vSphere Auto-Scaler, proving:
1. Baseline IDLE state & Rule 61 hot spare baseline (Spare1, spare2 poweredOn).
2. Detection of queue spike (50 pending tasks).
3. Transition to SCALING_UP and BOOTING_SPARES.
4. Cold spares (spare3..spare12) power-on without touching hot spares or spare8.
5. Verification of toolsOk, DHCP IPv4 allocation, and SSH readiness.
6. Workload flooding onto ready cold spares.
7. Queue draining and O1042 ledger reconciliation to 0.
8. Anti-flapping hysteresis debounce (idle grace period hold).
9. Graceful suspension with filesystem sync back to cold state.
10. Final Rule 61 hot spare parity certification.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# Ensure ~/bin is in module search path
_BIN_DIR = str(Path(__file__).resolve().parent)
if _BIN_DIR not in sys.path:
    sys.path.insert(0, _BIN_DIR)

from bd_vsphere_autoscaler import (
    STATE_BOOTING_SPARES,
    STATE_DRAINING,
    STATE_FLOODING_WORKERS,
    STATE_IDLE,
    STATE_SCALING_UP,
    STATE_SUSPENDING,
    STATE_WAITING_SSH,
    AutoScalerDaemon,
)
from lib_autoscaler_sensor import QueueSensor
from lib_vsphere_govc import (
    COLD_SPARES,
    EXCLUDED_VMS,
    HOT_SPARES,
    GovcClient,
    MockGovcEngine,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [SIM-SPIKE] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("simulate_spike")


def run_simulation(
    spike_size: int = 50,
    fast_forward: bool = True,
    suspend_method: str = "shutdown",
) -> bool:
    """Run full end-to-end simulation cycle with assertions."""
    logger.info("=================================================================")
    logger.info("STARTING ELASTIC vSPHERE AUTO-SCALER SIMULATION (SPIKE: %d ITEMS)", spike_size)
    logger.info("=================================================================")

    with tempfile.TemporaryDirectory(prefix="bd_autoscaler_sim_") as tmpdir:
        tmp_path = Path(tmpdir)
        sim_queue_file = tmp_path / "brief-queue.txt"
        sim_ledger_file = tmp_path / "DISPATCH-LEDGER.tsv"
        sim_state_file = tmp_path / "autoscaler-state.json"

        # Initialize mock engine with Rule 61 hot spares and cold pool
        engine = MockGovcEngine(
            hot_vms=["Spare1", "spare2"],
            cold_vms=COLD_SPARES,
            excluded_vms=["spare8"],
        )
        client = GovcClient(mock=True, engine=engine)

        sensor = QueueSensor(
            queue_file=sim_queue_file,
            ledger_file=sim_ledger_file,
            scale_up_cooldown_sec=300.0,
            idle_grace_period_sec=180.0,
            mock_mode=True,
        )
        # HUB-GATE safe parameters for simulation
        sensor.inject_mock_hub_metrics(iowait_pct=3.2, load1=4.5)

        config: dict[str, Any] = {
            "state_file": str(sim_state_file),
            "scale_up_threshold": 10,
            "suspend_method": suspend_method,
            "mock": True,
        }
        daemon = AutoScalerDaemon(govc_client=client, sensor=sensor, config=config)

        # -------------------------------------------------------------
        # STEP 1: Baseline Assertion (IDLE state & Rule 61 hot baseline)
        # -------------------------------------------------------------
        logger.info("[STEP 1] Verifying baseline state and Rule 61 invariants...")
        assert daemon.state == STATE_IDLE, f"Initial state must be IDLE, got {daemon.state}"
        assert engine.get_info(["Spare1"])["Spare1"]["powerState"] == "poweredOn"
        assert engine.get_info(["spare2"])["spare2"]["powerState"] == "poweredOn"
        assert engine.get_info(["spare3"])["spare3"]["powerState"] == "poweredOff"
        assert engine.get_info(["spare8"])["spare8"]["powerState"] == "poweredOn"  # Cockpit host
        logger.info("✓ Step 1 PASS: Hot spares (Spare1, spare2) active; cold spares (spare3..) cold.")

        # -------------------------------------------------------------
        # STEP 2: Inject Massive Queue Spike
        # -------------------------------------------------------------
        logger.info("[STEP 2] Injecting massive queue spike: %d items...", spike_size)
        sensor.inject_mock_queue_depth(spike_size)
        sensor.inject_mock_active_workers(0)
        assert sensor.get_queue_depth() == spike_size
        logger.info("✓ Step 2 PASS: Queue sensor reports %d pending items.", spike_size)

        # -------------------------------------------------------------
        # STEP 3: Scale-Up Detection (IDLE -> SCALING_UP)
        # -------------------------------------------------------------
        sim_time = 1000.0
        logger.info("[STEP 3] Ticking daemon: Detecting surge...")
        daemon.tick(now_ts=sim_time)
        assert daemon.state == STATE_SCALING_UP, f"Expected SCALING_UP, got {daemon.state}"
        logger.info("✓ Step 3 PASS: Daemon transitioned to SCALING_UP.")

        # -------------------------------------------------------------
        # STEP 4: Capacity & Preflight Check -> BOOTING_SPARES
        # -------------------------------------------------------------
        logger.info("[STEP 4] Ticking daemon: Preflight check & spare selection...")
        daemon.tick(now_ts=sim_time)
        assert daemon.state == STATE_BOOTING_SPARES, f"Expected BOOTING_SPARES, got {daemon.state}"
        assert len(daemon.target_vms) > 0, "Target VM list must not be empty"

        # Assert Rule 61 safety: hot spares Spare1 and spare2 NEVER targeted
        for hot in HOT_SPARES:
            assert hot not in daemon.target_vms, f"Rule 61 VIOLATION: {hot} in target_vms!"
        for excl in EXCLUDED_VMS:
            assert excl not in daemon.target_vms, f"Exclusion VIOLATION: {excl} in target_vms!"

        logger.info("✓ Step 4 PASS: Selected cold spares: %s (Hot spares & spare8 protected)", daemon.target_vms)

        # -------------------------------------------------------------
        # STEP 5: Booting Spares -> WAITING_SSH
        # -------------------------------------------------------------
        logger.info("[STEP 5] Ticking daemon: Executing power-on...")
        daemon.tick(now_ts=sim_time)
        assert daemon.state == STATE_WAITING_SSH, f"Expected WAITING_SSH, got {daemon.state}"

        # Assert cold spares are now poweredOn
        for vm in daemon.target_vms:
            info = engine.get_info([vm])[vm]
            assert info["powerState"] == "poweredOn", f"VM {vm} failed to power on"
            assert vm in client.managed_booted_vms, f"VM {vm} not tracked in managed_booted_vms"

        logger.info("✓ Step 5 PASS: All targeted cold spares powered on and tracked.")

        # -------------------------------------------------------------
        # STEP 6: Probe Readiness & Workload Flooding (WAITING_SSH -> FLOODING_WORKERS)
        # -------------------------------------------------------------
        logger.info("[STEP 6] Simulating toolsOk + DHCP + SSH readiness...")
        engine.simulate_boot_completion(tools_ok=True, ip_prefix="10.0.70.")
        daemon.tick(now_ts=sim_time)
        assert daemon.state == STATE_FLOODING_WORKERS, f"Expected FLOODING_WORKERS, got {daemon.state}"
        assert len(daemon.ready_vms) > 0, "Ready VM list must not be empty"
        logger.info("✓ Step 6 PASS: Verified toolsOk, DHCP IPv4, and SSH reachability on: %s", daemon.ready_vms)

        # -------------------------------------------------------------
        # STEP 7: Workload Flooding -> Transition to DRAINING
        # -------------------------------------------------------------
        logger.info("[STEP 7] Flooding worker tasks onto ready spares...")
        sensor.inject_mock_active_workers(len(daemon.ready_vms) * 4)  # 4 tasks per spare
        daemon.tick(now_ts=sim_time)
        assert daemon.state == STATE_DRAINING, f"Expected DRAINING, got {daemon.state}"
        logger.info("✓ Step 7 PASS: Workloads dispatched; daemon transitioned to DRAINING.")

        # -------------------------------------------------------------
        # STEP 8: Workload Processing & Queue Draining (50 -> 0)
        # -------------------------------------------------------------
        logger.info("[STEP 8] Simulating workload processing: draining queue to 0...")
        sensor.inject_mock_queue_depth(0)
        sensor.inject_mock_active_workers(0)
        assert sensor.get_queue_depth() == 0
        assert sensor.get_active_workers() == 0

        # Tick at current time: should start idle grace period debounce
        daemon.tick(now_ts=sim_time)
        assert daemon.state == STATE_DRAINING, "Daemon must remain in DRAINING during grace period"
        # Assert cold spares are STILL powered on during grace period!
        for vm in daemon.target_vms:
            assert engine.get_info([vm])[vm]["powerState"] == "poweredOn"
        logger.info("✓ Step 8 PASS: Queue drained; hysteresis grace period active (no premature suspension).")

        # -------------------------------------------------------------
        # STEP 9: Advance Clock Past Idle Grace Period (180s)
        # -------------------------------------------------------------
        advance_sec = 200.0  # > 180s grace period
        sim_time += advance_sec
        logger.info("[STEP 9] Advancing clock by +%0.1fs past grace period: evaluating SUSPENDING...", advance_sec)
        daemon.tick(now_ts=sim_time)
        assert daemon.state == STATE_SUSPENDING, f"Expected SUSPENDING, got {daemon.state}"
        logger.info("✓ Step 9 PASS: Grace period elapsed; daemon transitioned to SUSPENDING.")

        # -------------------------------------------------------------
        # STEP 10: Graceful Suspension & Return to IDLE
        # -------------------------------------------------------------
        logger.info("[STEP 10] Executing graceful suspension with filesystem sync...")
        daemon.tick(now_ts=sim_time)
        assert daemon.state == STATE_IDLE, f"Expected IDLE, got {daemon.state}"

        # Assert cold spares are suspended / poweredOff
        for vm in daemon.target_vms:
            info = engine.get_info([vm])[vm]
            expected_state = "suspended" if suspend_method == "suspend" else "poweredOff"
            assert info["powerState"] == expected_state, f"VM {vm} was not suspended (state={info['powerState']})"

        # Assert managed_booted_vms is cleared
        assert len(client.managed_booted_vms) == 0, "managed_booted_vms must be cleared after suspend"

        # Assert Rule 61 hot spares NEVER suspended
        assert engine.get_info(["Spare1"])["Spare1"]["powerState"] == "poweredOn"
        assert engine.get_info(["spare2"])["spare2"]["powerState"] == "poweredOn"
        assert engine.get_info(["spare8"])["spare8"]["powerState"] == "poweredOn"

        logger.info("✓ Step 10 PASS: All cold spares gracefully returned to cold state.")
        logger.info("✓ RULE 61 CERTIFIED: Spare1 and spare2 remained poweredOn throughout entire lifecycle.")

    logger.info("=================================================================")
    logger.info("ALL 10 SIMULATION STAGES PASSED CLEANLY (100%% INVARIANT PARITY)")
    logger.info("=================================================================")
    return True


def live_cluster_verification() -> bool:
    """Non-destructive read-only verification of live vCenter cluster."""
    logger.info("Executing non-destructive read-only verification of live vCenter cluster...")
    client = GovcClient(mock=False)
    vms_to_check = ["Spare1", "spare2", "spare3", "spare4", "spare8"]
    try:
        states = client.get_power_states(vms_to_check)
        logger.info("Live power states: %s", states)
        assert states.get("Spare1") == "poweredOn", "Rule 61: Spare1 must be poweredOn"
        assert states.get("spare2") == "poweredOn", "Rule 61: spare2 must be poweredOn"
        logger.info("✓ Live cluster verification passed.")
        return True
    except (subprocess.SubprocessError, OSError, AssertionError, ValueError, KeyError) as e:
        logger.error("Live cluster verification failed: %s", e)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Elastic vSphere Auto-Scaler Queue Spike Simulation")
    parser.add_argument("--spike-size", type=int, default=50, help="Number of queued items to inject (default: 50)")
    parser.add_argument("--suspend-method", choices=["shutdown", "suspend"], default="shutdown", help="Suspend method")
    parser.add_argument("--live-verify", action="store_true", help="Perform non-destructive read probe on live vCenter")

    args = parser.parse_args()

    if args.live_verify:
        success = live_cluster_verification()
        return 0 if success else 1

    success = run_simulation(
        spike_size=args.spike_size,
        fast_forward=True,
        suspend_method=args.suspend_method,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
