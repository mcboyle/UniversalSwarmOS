#!/usr/bin/env python3
"""bd-vsphere-autoscaler.py -- Elastic vSphere Auto-Scaler Daemon.

Automates the govc vSphere CLI API to elastically scale Boylenet cold spares
(spare3 through spare12) in response to PM Backlog queue depth surges,
floods ready VMs with worker workloads, and gracefully suspends them back
to cold state once the queue is drained and jobs are reconciled.

Enforces:
- Fleet Rule 61: 'Spare1' and 'spare2' permanently protected (never suspended).
- 'spare8' exclusion: permanently excluded from suspension (Cockpit host).
- 8-State FSM: IDLE -> SCALING_UP -> BOOTING_SPARES -> WAITING_SSH ->
               FLOODING_WORKERS -> DRAINING -> SUSPENDING -> IDLE.
- HUB-GATE: iowait < 20.0%, load1 < 36.0 before scaling.
- Hysteresis: SCALE_UP_COOLDOWN_SEC (300s), IDLE_GRACE_PERIOD_SEC (180s).
- State persistence: /home/mboyle/bd-persist/state/autoscaler-state.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure ~/bin is in module search path
_BIN_DIR = str(Path(__file__).resolve().parent)
if _BIN_DIR not in sys.path:
    sys.path.insert(0, _BIN_DIR)

from lib_autoscaler_sensor import (
    DEFAULT_LEDGER_FILE,
    DEFAULT_QUEUE_FILE,
    HUB_MAX_IOWAIT_PCT,
    HUB_MAX_LOAD1,
    IDLE_GRACE_PERIOD_SEC,
    SCALE_UP_COOLDOWN_SEC,
    QueueSensor,
)
from lib_vsphere_govc import (
    COLD_SPARES,
    DEFAULT_VC_CRED_FILE,
    EXCLUDED_VMS,
    HOT_SPARES,
    GovcClient,
    canonicalize_vm_name,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [AUTOSCALER] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("bd_vsphere_autoscaler")

DEFAULT_STATE_FILE = Path("/home/mboyle/bd-persist/state/autoscaler-state.json")
DEFAULT_ALERTS_LOG = Path("/home/mboyle/bd-persist/accounting/alerts.log")

# FSM State Enum
STATE_IDLE = "IDLE"
STATE_SCALING_UP = "SCALING_UP"
STATE_BOOTING_SPARES = "BOOTING_SPARES"
STATE_WAITING_SSH = "WAITING_SSH"
STATE_FLOODING_WORKERS = "FLOODING_WORKERS"
STATE_DRAINING = "DRAINING"
STATE_SUSPENDING = "SUSPENDING"

VALID_STATES = {
    STATE_IDLE,
    STATE_SCALING_UP,
    STATE_BOOTING_SPARES,
    STATE_WAITING_SSH,
    STATE_FLOODING_WORKERS,
    STATE_DRAINING,
    STATE_SUSPENDING,
}


def log_alert(message: str, alerts_file: Path = DEFAULT_ALERTS_LOG) -> None:
    """Log an operational alert to alerts.log."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{now_iso}\tAUTOSCALER\t{message}\n"
    try:
        if alerts_file.parent.is_dir():
            with open(alerts_file, "a", encoding="utf-8") as f:
                f.write(line)
    except OSError as e:
        logger.warning("Failed writing to alerts log %s: %s", alerts_file, e)


class AutoScalerDaemon:
    """Finite State Machine controller for elastic vSphere scaling."""

    def __init__(
        self,
        govc_client: GovcClient | None = None,
        sensor: QueueSensor | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.config = config or {}
        self.mock_mode = bool(self.config.get("mock", False)) or (
            govc_client is not None and getattr(govc_client, "mock", False)
        )
        if "state_file" in self.config and self.config["state_file"] is not None:
            self.state_file: Path | None = Path(self.config["state_file"])
        elif self.mock_mode:
            self.state_file = None
        else:
            self.state_file = Path(DEFAULT_STATE_FILE)

        self.poll_interval_sec = float(self.config.get("poll_interval_sec", 15.0))
        self.scale_up_threshold = int(self.config.get("scale_up_threshold", 10))
        self.suspend_method = str(self.config.get("suspend_method", "shutdown"))
        self.ssh_timeout_sec = float(self.config.get("ssh_timeout_sec", 180.0))
        self.batch_size = int(self.config.get("power_on_batch_size", 4))

        self.client = govc_client or GovcClient(
            cred_file=self.config.get("vc_cred_file", DEFAULT_VC_CRED_FILE),
            mock=self.mock_mode,
        )

        self.sensor = sensor or QueueSensor(
            queue_file=self.config.get("queue_file", DEFAULT_QUEUE_FILE),
            ledger_file=self.config.get("ledger_file", DEFAULT_LEDGER_FILE),
            scale_up_cooldown_sec=float(self.config.get("scale_up_cooldown_sec", SCALE_UP_COOLDOWN_SEC)),
            idle_grace_period_sec=float(self.config.get("idle_grace_period_sec", IDLE_GRACE_PERIOD_SEC)),
            max_iowait_pct=float(self.config.get("max_iowait_pct", HUB_MAX_IOWAIT_PCT)),
            max_load1=float(self.config.get("max_load1", HUB_MAX_LOAD1)),
            mock_mode=self.mock_mode,
        )
        if self.mock_mode and self.sensor is not None:
            self.sensor.mock_mode = True

        self.hysteresis = self.sensor.hysteresis
        self.state: str = STATE_IDLE
        self.last_state_change: float = time.time()
        self.target_vms: list[str] = []
        self.ready_vms: list[str] = []
        self.running: bool = True
        self.simulated_clock: float | None = None
        self.govc = self.client  # alias

        # Load persisted state if exists
        self.load_state()

    def set_time(self, t: float) -> None:
        self.simulated_clock = t

    def advance_time(self, delta: float) -> None:
        if self.simulated_clock is None:
            self.simulated_clock = time.time()
        self.simulated_clock += delta

    @property
    def last_scale_up_ts(self) -> float:
        return self.hysteresis.last_scale_up_ts

    @last_scale_up_ts.setter
    def last_scale_up_ts(self, val: float) -> None:
        self.hysteresis.last_scale_up_ts = val

    @property
    def drain_start_ts(self) -> float | None:
        return self.hysteresis.idle_since_ts

    @drain_start_ts.setter
    def drain_start_ts(self, val: float | None) -> None:
        self.hysteresis.idle_since_ts = val

    def set_state(self, new_state: str, reason: str = "") -> None:
        """Transition FSM state and record telemetry."""
        if new_state not in VALID_STATES:
            raise ValueError(f"Invalid state: {new_state}")
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self.last_state_change = time.time()
            msg = f"TRANSITION: {old_state} -> {new_state}"
            if reason:
                msg += f" ({reason})"
            logger.info(msg)
            log_alert(msg)
            self.save_state()

    def save_state(self) -> None:
        """Persist current state to state file."""
        if self.state_file is None:
            return
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "state": self.state,
                "current_state": self.state,
                "last_state_change_ts": self.last_state_change,
                "last_scale_up_ts": self.hysteresis.last_scale_up_ts,
                "idle_since_ts": self.hysteresis.idle_since_ts,
                "managed_booted_vms": sorted(self.client.managed_booted_vms),
                "target_vms": self.target_vms,
                "ready_vms": self.ready_vms,
                "queue_depth": self.sensor.get_queue_depth(),
                "active_workers": self.sensor.get_active_workers(),
                "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            tmp_file = self.state_file.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            tmp_file.replace(self.state_file)
        except OSError as e:
            logger.warning("Failed saving autoscaler state to %s: %s", self.state_file, e)

    def load_state(self) -> None:
        """Load state from persistent state file if present."""
        if self.state_file is None or not self.state_file.is_file():
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            saved_state = data.get("current_state") or data.get("state")
            if saved_state in VALID_STATES:
                self.state = saved_state

            raw_change = data.get("last_state_change_ts")
            self.last_state_change = float(raw_change) if raw_change is not None else time.time()

            raw_scale = data.get("last_scale_up_ts")
            self.hysteresis.last_scale_up_ts = float(raw_scale) if raw_scale is not None else 0.0

            idle_ts = data.get("idle_since_ts")
            self.hysteresis.idle_since_ts = float(idle_ts) if idle_ts is not None else None

            booted = data.get("managed_booted_vms", [])
            self.client.managed_booted_vms = set(booted)
            self.target_vms = data.get("target_vms", [])
            self.ready_vms = data.get("ready_vms", [])
            logger.info("Loaded state: %s, managed_vms: %s", self.state, booted)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning("Could not load state file %s: %s", self.state_file, e)

    def get_status(self) -> dict[str, Any]:
        """Return comprehensive status dictionary."""
        q_depth = self.sensor.get_queue_depth()
        active = self.sensor.get_active_workers()
        gate_ok, gate_info = self.sensor.check_hub_gate()
        return {
            "state": self.state,
            "queue_depth": q_depth,
            "active_workers": active,
            "hub_gate": gate_info,
            "hub_gate_ok": gate_ok,
            "managed_booted_vms": sorted(self.client.managed_booted_vms),
            "target_vms": self.target_vms,
            "ready_vms": self.ready_vms,
            "can_scale_up": self.hysteresis.can_scale_up(),
            "idle_remaining_sec": self.hysteresis.idle_remaining_sec(),
            "last_scale_up_ts": self.hysteresis.last_scale_up_ts,
            "idle_since_ts": self.hysteresis.idle_since_ts,
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def _select_cold_candidates(self, count_needed: int) -> list[str]:
        """Select unpowered cold spares up to count_needed."""
        power_states = self.client.get_power_states(COLD_SPARES)
        candidates = []
        for vm in COLD_SPARES:
            c = canonicalize_vm_name(vm)
            # Rule 61 hot spares and excluded VMs must NEVER be selected
            if c in HOT_SPARES or c in EXCLUDED_VMS:
                continue
            pstate = power_states.get(c, "unknown")
            if pstate in ("poweredOff", "suspended"):
                candidates.append(c)
                if len(candidates) >= count_needed:
                    break
        return candidates

    def tick(self, now_ts: float | None = None) -> str:
        """Execute a single FSM evaluation and transition step."""
        if now_ts is not None:
            now = now_ts
        elif self.simulated_clock is not None:
            now = self.simulated_clock
        else:
            now = time.time()

        if self.state == STATE_IDLE:
            q_depth = self.sensor.get_queue_depth()
            if q_depth >= self.scale_up_threshold:
                if self.hysteresis.can_scale_up(now):
                    self.hysteresis.record_scale_up(now)
                    self.set_state(
                        STATE_SCALING_UP,
                        reason=f"Queue depth {q_depth} >= threshold {self.scale_up_threshold}"
                    )
                else:
                    cooldown_left = self.hysteresis.scale_up_cooldown_sec - (now - self.hysteresis.last_scale_up_ts)
                    logger.debug("Queue depth %d but in cooldown (%0.1fs remaining)", q_depth, cooldown_left)

        elif self.state == STATE_SCALING_UP:
            gate_ok, gate_info = self.sensor.check_hub_gate()
            if not gate_ok:
                logger.warning("HUB-GATE breached: %s. Holding scale-up.", gate_info.get("reason"))
                log_alert(f"HUB-GATE-HOLD: {gate_info.get('reason')}")
                self.save_state()
                return self.state

            q_depth = self.sensor.get_queue_depth()
            # Calculate required cold VMs (at least 1, up to needed/2 or max cold)
            needed_vms = min(max(1, (q_depth + 1) // 2), len(COLD_SPARES))
            candidates = self._select_cold_candidates(needed_vms)

            if not candidates:
                logger.warning("No eligible powered-off cold spares available in COLD_POOL.")
                self.set_state(STATE_DRAINING, reason="No available cold spares to boot")
                self.save_state()
                return self.state

            self.target_vms = candidates
            self.set_state(
                STATE_BOOTING_SPARES,
                reason=f"Selected {len(candidates)} spares: {', '.join(candidates)}"
            )

        elif self.state == STATE_BOOTING_SPARES:
            logger.info("Powering on cold spares: %s", self.target_vms)
            results = self.client.power_on(self.target_vms)
            self.hysteresis.record_scale_up(now)
            if not any(results.values()):
                logger.error("Power-on failed for all target VMs: %s. Returning to IDLE.", self.target_vms)
                self.target_vms = []
                self.set_state(STATE_IDLE, reason="All power-on requests failed")
                self.save_state()
                return self.state
            self.set_state(STATE_WAITING_SSH, reason="Power-on issued; awaiting tools and SSH readiness")

        elif self.state == STATE_WAITING_SSH:
            logger.info("Probing readiness on target VMs: %s", self.target_vms)
            readiness = self.client.wait_for_readiness(
                self.target_vms,
                timeout_sec=self.ssh_timeout_sec,
                poll_interval=2.0 if self.mock_mode else 5.0,
            )

            ready_list = [vm for vm, st in readiness.items() if st.get("ready")]
            self.ready_vms = ready_list

            if ready_list:
                logger.info("Readiness verified on %d/%d VMs: %s", len(ready_list), len(self.target_vms), ready_list)
                self.set_state(
                    STATE_FLOODING_WORKERS,
                    reason=f"{len(ready_list)} spares ready for workloads"
                )
            else:
                logger.error("SSH readiness timeout on all target VMs. Quarantining.")
                self.set_state(STATE_DRAINING, reason="Zero spares achieved SSH readiness")

        elif self.state == STATE_FLOODING_WORKERS:
            # Register ready VMs and log workload allocation
            logger.info("FLOODING WORKERS onto ready spares: %s", self.ready_vms)
            log_alert(f"WORKLOAD-FLOOD: Ready spares {self.ready_vms} available for task dispatch")
            self.set_state(STATE_DRAINING, reason="Workloads assigned; monitoring completion")

        elif self.state == STATE_DRAINING:
            # Reconcile ledger
            reconciled = self.sensor.reconcile_ledger()
            if reconciled > 0:
                logger.info("Reconciled %d open ledger rows", reconciled)

            q_depth = self.sensor.get_queue_depth()
            active_workers = self.sensor.get_active_workers()

            # Check for re-spike or backlog during draining
            if q_depth >= self.scale_up_threshold and self.hysteresis.can_scale_up(now):
                logger.info(
                    "DRAINING: Queue re-spike detected (%d >= %d). Transitioning to SCALING_UP.",
                    q_depth,
                    self.scale_up_threshold,
                )
                self.set_state(
                    STATE_SCALING_UP,
                    reason=f"Queue re-spike to {q_depth} >= {self.scale_up_threshold}",
                )
                self.save_state()
                return self.state

            if q_depth == 0 and active_workers == 0:
                self.hysteresis.update_idle_state(q_depth, active_workers, now)
                if self.hysteresis.is_idle_grace_expired(now):
                    self.set_state(
                        STATE_SUSPENDING,
                        reason=f"Queue empty and active=0 for > {self.hysteresis.idle_grace_period_sec}s"
                    )
                else:
                    rem = self.hysteresis.idle_remaining_sec(now)
                    logger.info("DRAINING: Queue empty and active=0. Debouncing grace period (%0.1fs remaining)", rem)
            else:
                # Active work ongoing or re-spike
                self.hysteresis.update_idle_state(q_depth, active_workers, now)
                logger.debug("DRAINING: In-flight work (queue=%d, active=%d)", q_depth, active_workers)

        elif self.state == STATE_SUSPENDING:
            managed_vms = list(self.client.managed_booted_vms)
            if managed_vms:
                logger.info("SUSPENDING managed cold spares via %s: %s", self.suspend_method, managed_vms)
                self.client.suspend_vms(managed_vms, method=self.suspend_method)
            else:
                logger.info("SUSPENDING: No managed cold spares to suspend.")

            self.target_vms = []
            self.ready_vms = []
            self.set_state(STATE_IDLE, reason="All managed cold spares suspended/powered-off")

        self.save_state()
        return self.state

    def run_loop(self) -> None:
        """Run daemon polling loop until interrupted."""
        logger.info("Starting Elastic vSphere Auto-Scaler daemon (interval: %0.1fs)...", self.poll_interval_sec)
        while self.running:
            try:
                self.tick()
            except Exception:
                logger.exception("Unexpected error during daemon tick")
            time.sleep(self.poll_interval_sec)
        logger.info("Daemon loop terminated cleanly.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Elastic vSphere Auto-Scaler Daemon")
    parser.add_argument("--daemon", action="store_true", help="Run as continuous background daemon")
    parser.add_argument("--once", action="store_true", help="Execute single evaluation tick and exit")
    parser.add_argument("--status", action="store_true", help="Output current status JSON and exit")
    parser.add_argument("--config", type=str, default=None, help="Path to config JSON file")
    parser.add_argument("--mock", action="store_true", help="Run with simulated mock vSphere engine")
    parser.add_argument("--interval", type=float, default=None, help="Polling interval in seconds")

    args = parser.parse_args()

    config = {}
    if args.config:
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config = json.load(f)
        except OSError as e:
            logger.error("Failed to read config file %s: %s", args.config, e)
            return 1

    if args.mock:
        config["mock"] = True
    if args.interval is not None:
        config["poll_interval_sec"] = args.interval

    daemon = AutoScalerDaemon(config=config)

    # Signal handlers
    def handle_signal(sig: int, _frame: Any) -> None:
        logger.info("Caught signal %d; shutting down cleanly...", sig)
        daemon.running = False
        daemon.save_state()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if args.status:
        status_data = daemon.get_status()
        print(json.dumps(status_data, indent=2))
        return 0

    if args.once:
        logger.info("Executing single evaluation tick...")
        daemon.tick()
        status_data = daemon.get_status()
        print(json.dumps(status_data, indent=2))
        return 0

    if args.daemon:
        daemon.run_loop()
        return 0

    # Default action if no flags provided
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
