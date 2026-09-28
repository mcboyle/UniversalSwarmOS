#!/usr/bin/env python3
import datetime
import json
import os
import sqlite3
import subprocess

DB_PATH = '/home/mboyle/bd-persist/accounting/usage.sqlite'
WORKING_MD = '/home/mboyle/bd-persist/WORKING.md'
ORDERS_DIR = '/home/mboyle/bd-persist/harness-work/PLAN-2040'
SAY_SH = '/home/mboyle/bd-say.sh'

# Context Limits & Checkpoint Window Policy
WORKER_LIMIT = 150000
ORCHESTRATOR_LIMIT = 250000
CHECKPOINT_WINDOW_TOKENS = 25000


def expected_cache_hit_rate(tokens: int, window_size: int = CHECKPOINT_WINDOW_TOKENS) -> float | None:
    """Expected checkpoint ratio; not measured telemetry or cockpit data.

    None when tokens <= 0: no observation is COULD NOT LOOK, never a ratio.
    """
    if tokens <= 0:
        return None
    if tokens <= window_size:
        return 0.0
    count = tokens // window_size
    if tokens % window_size == 0 and count > 1:
        locked_boundary = (count - 1) * window_size
    elif tokens % window_size == 0 and count == 1:
        locked_boundary = 0
    else:
        locked_boundary = count * window_size
    if locked_boundary <= 0:
        return 0.0
    ratio = locked_boundary / float(tokens)
    return min(1.0, max(0.0, ratio))


def get_busy_seats():
    seats = []
    if not os.path.exists(WORKING_MD):
        return seats
    with open(WORKING_MD, 'r', encoding='utf-8') as f:
        in_busy_section = False
        for line in f:
            if '## BUSY SEATS' in line:
                in_busy_section = True
            elif line.startswith('##') and in_busy_section:
                break
            elif in_busy_section and 'bd-' in line:
                parts = line.strip().split()
                if len(parts) >= 1 and 'bd-' in parts[0]:
                    seat = parts[0].split(':')[0]
                    seats.append(seat)
    return seats


def clear_order(order_path: str):
    """Cleans up compaction or pruning orders when context returns below limit."""
    if os.path.isfile(order_path):
        try:
            os.unlink(order_path)
        except OSError:
            pass


def trigger_zero_reset_pruning(seat: str, max_context: int, limit: int, thread: str | None = None) -> str:
    """Triggers zero-reset checkpoint pruning, suppressing destructive /compact."""
    os.makedirs(ORDERS_DIR, exist_ok=True)

    # Suppress destructive /compact orders: remove any legacy COMPACT-<seat>.md
    compact_order = os.path.join(ORDERS_DIR, f'COMPACT-{seat}.md')
    clear_order(compact_order)

    prune_order = os.path.join(ORDERS_DIR, f'PRUNE-{seat}.md')
    cache_hit_rate = expected_cache_hit_rate(max_context)
    ratio_text = "COULD-NOT-LOOK (no token observation)" if cache_hit_rate is None else f"{cache_hit_rate:.2f}"
    stamp = datetime.datetime.now(datetime.UTC).isoformat().replace('+00:00', 'Z')
    thread_line = f"THREAD: {thread}\n" if thread else ""

    body = (
        f"# ORDER: ZERO-RESET PRUNE\n"
        f"SEAT: {seat}\n"
        f"{thread_line}"
        f"MEASURED-AT: {stamp}\n"
        f"INPUT-TOKENS: {max_context}\n"
        f"LIMIT: {limit}\n"
        f"CHECKPOINT-WINDOW: {CHECKPOINT_WINDOW_TOKENS}\n"
        f"EXPECTED-CACHE-HIT-RATIO: {ratio_text}\n"
        f"PRUNE-TARGET: ephemeral_tool_observations_only\n"
        f"POLICY: zero_reset_checkpoint_pruning\n\n"
        f"Your lane has reached {max_context} tokens (limit {limit}).\n"
        f"Prune Turn 2+ ephemeral tool observations in locked historical windows (<= last locked 25k boundary).\n"
        f"Active 25k window remains 100% append-only and strictly immutable.\n"
        f"DO NOT execute /compact. EXPECTED-CACHE-HIT-RATIO is the locked-window fraction, not measured cache telemetry.\n"
    )

    if os.path.isfile(prune_order):
        try:
            with open(prune_order, 'r', encoding='utf-8') as f:
                if f.read() == body:
                    return prune_order
        except OSError:
            pass

    tmp_order = f"{prune_order}.tmp.{os.getpid()}"
    with open(tmp_order, 'w', encoding='utf-8') as f:
        f.write(body)
    os.replace(tmp_order, prune_order)

    if os.path.exists(SAY_SH):
        subprocess.run([SAY_SH, seat, prune_order], check=False)
    return prune_order


def check_usage():
    if not os.path.exists(DB_PATH):
        return

    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        c = conn.cursor()
        since_iso = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=5)).isoformat().replace('+00:00', 'Z')

        # We pull threads
        c.execute('''
            select r.usage, o.thread 
            from usage_responses r left join usage_occurrences o
              on o.provider=r.provider and o.response_id=r.response_id
            where r.timestamp >= ? and r.quarantined=0
        ''', (since_iso,))

        agg = {}
        for uj, thread in c.fetchall():
            try:
                u = json.loads(uj or '{}') if uj else {}
                ctx = int(u.get('input_tokens', 0) or 0)
                agg.setdefault(thread, 0)
                agg[thread] = max(agg[thread], ctx)
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
        conn.close()
    except (sqlite3.DatabaseError, sqlite3.OperationalError):
        # Gracefully handle database locks, corruption, or concurrent access
        return

    max_context = max(agg.values()) if agg else 0
    busy_seats = get_busy_seats()

    for seat in busy_seats:
        limit = ORCHESTRATOR_LIMIT if ('pm' in seat or 'integrator' in seat) else WORKER_LIMIT
        prune_order_path = os.path.join(ORDERS_DIR, f'PRUNE-{seat}.md')
        compact_order_path = os.path.join(ORDERS_DIR, f'COMPACT-{seat}.md')

        if max_context > limit:
            trigger_zero_reset_pruning(seat, max_context, limit)
        else:
            # Clean up pending orders if context dropped below ceiling (handles oscillation)
            clear_order(prune_order_path)
            clear_order(compact_order_path)


if __name__ == '__main__':
    check_usage()

