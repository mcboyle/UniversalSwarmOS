#!/usr/bin/env python3
"""Stop-hook narration meter (O1120).

O966 measures prose only on bd-say MESSAGE TEXT. A seat's own turn output -- the text the
operator actually reads in the pane -- was measured by nothing. This hook closes that gap:
on every Stop it reads the LAST assistant turn and appends one line to the same ledger
bd-prose-enforce.sh already counts (state/prose-violations.tsv).

Transcript sources, in order:
  1. transcript_path (Claude Code and Codex both supply it) -- JSONL, last assistant turn.
  2. last_assistant_message (Codex stop.command.input extension) when 1 is absent/empty.
AGY/Antigravity ships no Stop hook, so AGY seats are COULD NOT MEASURE.

Prose = turn text minus fenced code, minus record-token lines, minus short bullets/tables.
Violation = prose > BD_PROSE_MAX_CHARS (300) or > BD_PROSE_MAX_SENTENCES (2) sentences.

NEVER exits non-zero (O1093: a non-zero Stop hook locks the seat) and NEVER prints on the
happy path (a Stop hook that prints keeps the seat talking).
"""
import json
import os
import pathlib
import re
import subprocess
import stat
import sys
import time

P = pathlib.Path(os.environ.get('BD_PERSIST_ROOT') or '/home/mboyle/bd-persist')

RECORD = re.compile(
    r'^(VERDICT:|OBJECT:|LENS:|COMMAND:|rc=|DEPLOYED|READY|FOUND|COULD NOT LOOK|PATCH|/home/)')
BULLET = re.compile(r'^(?:[-*+]\s|\d+[.)]\s|\|)')
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
SENTENCE = re.compile(r'[.!?][)\'"]*\s+(?=\S)')


def seat_name():
    s = os.environ.get('BD_SEAT')
    if s:
        return s.strip()
    if os.environ.get('TMUX'):
        try:
            return subprocess.run(['tmux', 'display-message', '-p', '#S'],
                                  capture_output=True, text=True, timeout=3).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ''
    return ''


def message_of(entry):
    # Codex JSONL stores messages beneath response_item.payload, not message.
    if entry.get('type') == 'response_item':
        payload = entry.get('payload')
        if isinstance(payload, dict) and payload.get('type') == 'message':
            return payload
        return {}
    return entry.get('message') if isinstance(entry.get('message'), dict) else entry


def text_blocks(entry):
    """Text blocks of one assistant transcript entry, Claude and Codex shapes."""
    msg = message_of(entry)
    if msg.get('channel') == 'analysis':
        return []
    content = msg.get('content')
    if isinstance(content, str):
        return [content]
    out = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get('type') in ('text', 'output_text') and isinstance(block.get('text'), str):
                out.append(block['text'])
            elif isinstance(block, str):
                out.append(block)
    return out


def is_real_user_turn(entry):
    """A user entry that is NOT just tool results -- i.e. the boundary of the last turn."""
    msg = message_of(entry)
    content = msg.get('content')
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return not all(isinstance(b, dict) and b.get('type') in ('tool_result', 'tool_use')
                       for b in content)
    return True


def role_of(entry):
    msg = message_of(entry)
    return msg.get('role') or msg.get('type')


def last_turn_text(path):
    try:
        # Opening a FIFO normally blocks before Python can catch an error.
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        with os.fdopen(fd, 'r', errors='replace') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return ''
            lines = stream.read().splitlines()
    except OSError:
        return ''
    collected = []
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get('isSidechain'):
            continue
        if entry.get('type') == 'event_msg' and isinstance(entry.get('payload'), dict) and entry['payload'].get('type') == 'task_started':
            break
        role = role_of(entry)
        if role == 'assistant':
            collected.extend(reversed(text_blocks(entry)))
        elif role == 'user' and is_real_user_turn(entry):
            break
    return '\n'.join(reversed(collected))


def prose_of(text):
    kept, fence = [], None
    for line in text.splitlines():
        marker = FENCE.match(line)
        if fence:
            if (marker and marker[1][0] == fence[0]
                    and len(marker[1]) >= len(fence) and not marker[2].strip()):
                fence = None
            continue
        if marker and (marker[1][0] != '`' or '`' not in marker[2]):
            fence = marker[1]
            continue
        s = line.strip()
        if not s or RECORD.match(s):
            continue
        if len(s) < 120 and BULLET.match(s):
            continue
        kept.append(s)
    return ' '.join(kept)


def violation(prose):
    if not prose:
        return False
    max_chars = int(os.environ.get('BD_PROSE_MAX_CHARS', '300') or 300)
    max_sent = int(os.environ.get('BD_PROSE_MAX_SENTENCES', '2') or 2)
    sentences = len(SENTENCE.findall(prose)) + 1
    return len(prose) > max_chars or sentences > max_sent


def main():
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    if not isinstance(payload, dict):
        return
    seat = seat_name()
    if not seat:
        return
    text = ''
    tp = payload.get('transcript_path')
    if isinstance(tp, str) and tp:
        text = last_turn_text(tp)
    if not text:
        fallback = payload.get('last_assistant_message')
        if isinstance(fallback, str):
            text = fallback
    prose = prose_of(text)
    if not violation(prose):
        return
    ledger = pathlib.Path(os.environ.get('BD_PROSE_LEDGER') or (P / 'state' / 'prose-violations.tsv'))
    ledger.parent.mkdir(parents=True, exist_ok=True)
    snippet = re.sub(r'\s+', ' ', prose)[:80]
    ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    fd = os.open(ledger, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NONBLOCK, 0o666)
    with os.fdopen(fd, 'a') as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            return
        fh.write(f'{ts}\t{seat}\tlen={len(prose)},turn\t{snippet}\n')


try:
    main()
except Exception:  # never block, never print: O1093
    pass
sys.exit(0)
