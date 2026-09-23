#!/usr/bin/env python3
import sqlite3, json, datetime, os, subprocess

DB_PATH = '/home/mboyle/bd-persist/accounting/usage.sqlite'
WORKING_MD = '/home/mboyle/bd-persist/WORKING.md'
ORDERS_DIR = '/home/mboyle/bd-persist/harness-work/PLAN-2040'
SAY_SH = '/home/mboyle/bd-say.sh'

# Context Limits
WORKER_LIMIT = 150000
ORCHESTRATOR_LIMIT = 250000

def get_busy_seats():
    seats = []
    if not os.path.exists(WORKING_MD): return seats
    with open(WORKING_MD, 'r') as f:
        in_busy_section = False
        for line in f:
            if '## BUSY SEATS' in line: in_busy_section = True
            elif line.startswith('##') and in_busy_section: break
            elif in_busy_section and 'bd-' in line:
                parts = line.strip().split()
                if len(parts) >= 1 and 'bd-' in parts[0]:
                    seat = parts[0].split(':')[0]
                    seats.append(seat)
    return seats

def check_usage():
    if not os.path.exists(DB_PATH): return
    conn = sqlite3.connect(DB_PATH)
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
        u = json.loads(uj or '{}') if uj else {}
        ctx = int(u.get('input_tokens', 0) or 0)
        agg.setdefault(thread, 0)
        agg[thread] = max(agg[thread], ctx)
        
    # Since we can't perfectly map threads to seats in usage.sqlite easily,
    # we just warn all busy seats if ANY thread is wildly over limit.
    # This acts as a broadcast fail-safe.
    max_context = max(agg.values()) if agg else 0
    busy_seats = get_busy_seats()
    
    for seat in busy_seats:
        limit = ORCHESTRATOR_LIMIT if ('pm' in seat or 'integrator' in seat) else WORKER_LIMIT
        if max_context > limit:
            order_path = os.path.join(ORDERS_DIR, f'COMPACT-{seat}.md')
            with open(order_path, 'w') as f:
                f.write(f"# ORDER: COMPACT NOW\n\nYour lane has breached {limit} tokens. Write RESUME_STATE.md, compress it using the `caveman-compress` skill, and execute /compact.\n")
            subprocess.run([SAY_SH, seat, order_path], check=False)

if __name__ == '__main__':
    check_usage()
