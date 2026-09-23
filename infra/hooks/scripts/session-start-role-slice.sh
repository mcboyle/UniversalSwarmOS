#!/usr/bin/env python3
"""Inject exact role rules and actual deltas; preserve the full retrievable source."""
import fcntl
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile


def main():
    seat = os.environ.get('BD_SEAT', sys.argv[1] if len(sys.argv) == 2 else '')
    if not seat or not re.fullmatch(r'[A-Za-z0-9_.-]+', seat):
        sys.exit(0)
    path = pathlib.Path(os.environ.get('BD_FLEET_RULE', '/home/mboyle/bd-persist/FLEET_RULE.md')).resolve()
    try:
        text = path.read_text()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f'[RULES] cannot read {path}: {exc}')
    rules = {}; key = None
    for line in text.splitlines(keepends=True):
        m = re.match(r'^\s*(\d+[a-z]?)\.\s+', line)
        if m:
            key = m[1]
            if key in rules:
                raise ValueError(f'[RULES] duplicate rule {key}')
            rules[key] = line
        elif line.startswith('#'):
            key = None
        elif key:
            rules[key] += line
    if not rules or any(k not in rules for k in ('1', '6', '22', '24', '40', '54')):
        raise ValueError('[RULES] required binding rules are missing')
    # O1149: lens roles take the SAME generated floor as every other role plus their own
    # review rules. They no longer receive a second verbatim copy of the full source, which
    # the `cat` emitter in settings.json was already delivering (measured 2026-09-21).
    lens = any(k in seat.lower() for k in ('lens', 'review', 'triage', 'adjudicator'))
    core = ['1', '6', '7', '8', '9', '11', '15', '16', '19', '22', '24', '26', '27', '30', '31b', '33', '33b', '40', '54']
    if lens:
        core += ['17', '18', '20', '35', '35b', '36']
    elif 'integrator' in seat:
        core += ['20', '31', '32']
    elif 'pm' in seat.lower():
        core += ['3', '4', '5', '29']
    else:
        core += ['13', '17', '20']
    if any(k not in rules for k in core):
        raise ValueError('[RULES] role floor contains absent rules')
    root = pathlib.Path(os.environ.get('BD_CONTEXT_STATE_DIR', str(pathlib.Path(__file__).resolve().parents[1] / '.state')))
    root.mkdir(parents=True, exist_ok=True)
    state = root / (seat + '.rules.json')
    with open(root / (seat + '.rules.lock'), 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = json.loads(state.read_text()) if state.exists() else None
        if previous is not None and (not isinstance(previous, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in previous.items())):
            raise ValueError('[RULE-STATE] invalid previous rule snapshot')
        selected = set(core)
        delta = []
        if previous is not None:
            for k in rules:
                if rules[k] != previous.get(k):
                    delta.append('RULE DELTA ' + k + ':\n' + rules[k]); selected.add(k)
            for k in previous.keys() - rules.keys():
                delta.append('RULE DELTA ' + k + ': removed from current source; retrieve prior binding text:\n' + previous[k])
        # Selected rules are verbatim source blocks. Full-source read above proves retrieval.
        header = f'# ACTIVE ROLE FLOOR SLICE\nFull binding law: {path}\nSHA256: {hashlib.sha256(text.encode()).hexdigest()}\nRetrieve an omitted rule: bd law("<rule title>") -- the tool takes a TOPIC, not a number,\nand returns a nearest neighbour, never NONE: check the text carries the id you asked for.\nSlim floor: /home/mboyle/bd-persist/FLEET_RULE-FLOOR.md\n'
        # LENS REPAIR (O1098): THE BUDGET MUST DEGRADE, NEVER DELETE. This cut removes the
        # `cat FLEET_RULE.md` SessionStart/PreCompact hooks, which were the only other
        # unconditional law delivery, so a raise here now means the seat starts with ZERO law
        # instead of the full 15.7 KB. MEASURED: amend rules 41-53 and every role -- lens,
        # worker, pm, integrator -- got rc=2 and 0 bytes. The DELTA is the unbounded part; the
        # floor is not. Ship the floor always, fit what delta will fit, name the rest by id.
        floor = header + ''.join(rules[k] for k in core)
        if len(floor.encode()) > 8192:
            raise ValueError(f'[RULE-BUDGET] the role floor ALONE exceeds 8192 bytes; read full law at {path}')
        output = floor + ''.join(delta)
        if len(output.encode()) > 8192:
            kept, dropped = [], []
            for d in delta:
                rid = d.split(':', 1)[0].replace('RULE DELTA', '').strip()
                if len((floor + ''.join(kept) + d).encode()) <= 7936:
                    kept.append(d)
                else:
                    dropped.append(rid)
            notice = ('RULE DELTA (bodies omitted to keep the floor within budget): '
                      + ', '.join(dropped) + f' changed since this seat last started -- read them at {path}.\n')
            output = floor + ''.join(kept) + notice
            if len(output.encode()) > 8192:
                output = floor + notice
        with tempfile.NamedTemporaryFile(mode='w', dir=root, prefix=seat + '.', delete=False) as f:
            json.dump(rules, f); f.write('\n'); temp = f.name
        os.replace(temp, state)
        print(output, end='' if output.endswith('\n') else '\n')

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr); sys.exit(2)
