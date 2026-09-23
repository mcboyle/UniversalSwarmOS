#!/usr/bin/env python3
"""UserPromptSubmit turn-budget guard (O1095, 2026-09-21; H629).

NEVER blocks: always exits 0 (O1093: a non-zero exit here locks the seat).
Counts this seat's turns in bd-persist/state/turns/<seat> (ambient; no env needed).
PM seats (bd-persist/PM-SEAT) are exempt: no count, no message.
At the budget it prints a context line for the seat AND sends ONE message to the PM
(bd-say, rate-limited to once per BD_TURN_NOTIFY_EVERY turns over budget) so the PM
can order handoff / finish / retire. Overrides: BD_TURN_BUDGET (default 50),
BD_TURN_COUNT (explicit, no file), BD_TURN_FILE (explicit counter file),
BD_TOOL_COUNT (explicit tool count), BD_SEAT_IDLE (explicit idle flag),
BD_TURN_RESET (explicit reset flag), BD_PROMPT (explicit prompt override).

H629:
  1. Reset on launch (session ID change / first session seen) and on new dispatch
     (START NOW, NEXT: claim and review, DISPATCH, or BD_DISPATCH_NEW).
  2. Idle seat suppression: no re-ping if tool use has not increased since last ping.
  3. Genuine overrun on a task pings once.
"""
import json, os, pathlib, subprocess, sys, time

P = pathlib.Path(os.environ.get('BD_PERSIST_ROOT') or '/home/mboyle/bd-persist')


def seat_name():
    s = os.environ.get('BD_SEAT')
    if s:
        return s.strip()
    if os.environ.get('TMUX'):
        try:
            return subprocess.run(['tmux', 'display-message', '-p', '#S'], capture_output=True, text=True, timeout=3).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ''
    return ''


def pm_seats():
    try:
        return [l.strip() for l in (P / 'PM-SEAT').read_text().splitlines() if l.strip() and not l.startswith('#')]
    except OSError:
        return []


def get_tool_count(payload, seat, f):
    explicit = os.environ.get('BD_TOOL_COUNT')
    if explicit is not None:
        try:
            return int(explicit)
        except ValueError:
            pass
    tp = payload.get('transcript_path') or os.environ.get('BD_TRANSCRIPT_PATH')
    if tp and os.path.isfile(tp):
        try:
            with open(tp, 'r', errors='replace') as stream:
                return sum(1 for line in stream if '"type":"tool_use"' in line or '"type": "tool_use"' in line)
        except OSError:
            pass
    tf = f.parent / f'{f.name}.tools'
    if tf.exists():
        try:
            t = tf.read_text().strip()
            if t.isdigit():
                return int(t)
        except OSError:
            pass
    return None


def is_dispatch_prompt(prompt):
    # Anchored at line start AFTER stripping the bd-say identity stamp ("[from <seat>] "),
    # which is prepended to EVERY delivered message, and after skipping batch header lines.
    # Unanchored substrings are not usable here: a lens seat's own prose routinely contains
    # "claim and review", and resetting on it silently disables the turn budget (B4 F1).
    # "DISPATCH:" is deliberately NOT a trigger: its only production producer is
    # bd-turn-watch.sh's over-budget nag, which must not reset the counter it is reporting.
    if not isinstance(prompt, str) or not prompt:
        return False
    for line in prompt.splitlines():
        line = line.strip()
        if line.startswith('[from ') and ']' in line:
            line = line.split(']', 1)[1].strip()
        if line.startswith('START NOW:'):
            return True
        if line.startswith('NEXT: claim and review'):
            return True
        if 'is YOUR TASK' in line:
            return True
    return False


def main():
    seat = seat_name()
    if not seat or seat in pm_seats():
        return

    raw = ''
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
    except Exception:
        raw = ''

    payload = {}
    if raw.strip().startswith('{'):
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                payload = loaded
        except (ValueError, TypeError):
            payload = {}

    budget = int(os.environ.get('BD_TURN_BUDGET', '50') or 50)
    every = int(os.environ.get('BD_TURN_NOTIFY_EVERY', '25') or 25)
    explicit = os.environ.get('BD_TURN_COUNT')
    f = pathlib.Path(os.environ.get('BD_TURN_FILE') or (P / 'state' / 'turns' / seat))

    if explicit is not None and explicit != '' and explicit.isdigit():
        turns = int(explicit)
    else:
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            sess_file = f.parent / f'{f.name}.session'
            ping_file = f.parent / f'{f.name}.last_ping'

            session_id = payload.get('session_id') or payload.get('sessionId') or os.environ.get('BD_SESSION_ID', '')
            prompt = payload.get('prompt') or os.environ.get('BD_PROMPT', '')

            should_reset = False
            if os.environ.get('BD_TURN_RESET') == '1':
                should_reset = True
            elif session_id:
                if sess_file.exists():
                    try:
                        prev_sess = sess_file.read_text().strip()
                        if prev_sess and prev_sess != session_id:
                            should_reset = True
                    except OSError:
                        pass
                else:
                    # Legacy counter encounter or fresh session marker initialization
                    should_reset = True
                try:
                    sess_file.write_text(f'{session_id}\n')
                except OSError:
                    pass

            if not should_reset and (is_dispatch_prompt(prompt) or os.environ.get('BD_DISPATCH_NEW') == '1'):
                should_reset = True

            if should_reset:
                turns = 1
                f.write_text('1\n')
                if ping_file.exists():
                    try:
                        ping_file.unlink()
                    except OSError:
                        pass
            else:
                text = f.read_text().strip() if f.exists() else '0'
                turns = (int(text) if text.isdigit() else 0) + 1
                f.write_text(f'{turns}\n')
        except OSError:
            return

    if turns >= budget:
        print(f'[CONTEXT-GUARD] turn {turns} >= budget {budget}: finish the current task, write handoff-{seat}.md, then wait for the PM.')
        over = turns - budget
        if over % every == 0:
            ping_file = f.parent / f'{f.name}.last_ping'
            tools_now = get_tool_count(payload, seat, f)

            if ping_file.exists():
                try:
                    prev_line = ping_file.read_text().strip()
                    parts = prev_line.split(':')
                    prev_tools = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                    if os.environ.get('BD_SEAT_IDLE') == '1':
                        print(f'[CONTEXT-GUARD] turn {turns} >= budget {budget}: idle seat; suppressing PM re-ping.')
                        return
                    if tools_now is not None and prev_tools is not None and tools_now <= prev_tools:
                        print(f'[CONTEXT-GUARD] turn {turns} >= budget {budget}: idle seat (no tool use since last ping, tools={tools_now}); suppressing PM re-ping.')
                        return
                except OSError:
                    pass
            elif os.environ.get('BD_SEAT_IDLE') == '1':
                print(f'[CONTEXT-GUARD] turn {turns} >= budget {budget}: idle seat; suppressing PM re-ping.')
                return

            pm = (pm_seats() or ['bd-pm-O5-A'])[0]
            say_bin = os.environ.get('BD_SAY_BIN', '/home/mboyle/bd-say.sh')
            try:
                subprocess.run([say_bin, pm, f'TURN-BUDGET {seat} {turns}/{budget}: order handoff/finish/retire'],
                               capture_output=True, text=True, timeout=20)
                try:
                    recorded_tools = tools_now if tools_now is not None else 0
                    ping_file.write_text(f'{turns}:{recorded_tools}\n')
                except OSError:
                    pass
            except (OSError, subprocess.SubprocessError):
                pass
    elif turns >= int(budget * 0.8):
        print(f'[CONTEXT-GUARD] turn {turns}/{budget}: prepare handoff-{seat}.md.')


try:
    main()
except Exception as exc:  # never block the seat
    print(f'[CONTEXT-GUARD] {exc}', file=sys.stderr)
sys.exit(0)
