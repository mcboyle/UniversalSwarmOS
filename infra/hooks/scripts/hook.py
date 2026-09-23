#!/usr/bin/env python3
import fcntl
import hashlib
import json
import os
import pathlib
import re
import shlex
import sys


ASSIGNMENT = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)=(.*)')


def recognized(command):
    if '\n' in command or '\r' in command:
        return None
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    if any(any(mark in word for mark in ('|', ';', '&', '`', '$(')) for word in words):
        return None
    retry = ''
    clean = []
    while words:
        match = ASSIGNMENT.fullmatch(words[0])
        if not match:
            break
        if match.group(1) == 'BD_EFFICIENCY_RETRY_REASON':
            retry = match.group(2).strip()
        else:
            clean.append(words[0])
        words.pop(0)
    if not words:
        return None
    index = 0
    name = pathlib.PurePosixPath(words[index]).name
    if name == 'env':
        index += 1
        while index < len(words) and (words[index].startswith('-') or ASSIGNMENT.fullmatch(words[index])):
            index += 1
    if index < len(words) and pathlib.PurePosixPath(words[index]).name == 'timeout':
        index += 1
        while index < len(words) and words[index].startswith('-'):
            index += 1
        if index < len(words):
            index += 1
    if index < len(words) and pathlib.PurePosixPath(words[index]).name in {'bash', 'sh'}:
        index += 1
    if index >= len(words):
        return None
    executable = pathlib.PurePosixPath(words[index]).name
    if executable.startswith('python'):
        if index + 2 < len(words) and words[index + 1] == '-m' and words[index + 2] == 'pytest':
            executable = 'pytest'; index += 2
        elif index + 1 < len(words):
            index += 1; executable = pathlib.PurePosixPath(words[index]).name
    normalized = shlex.join(clean + words)
    if executable == 'bd-verify-cut.sh':
        return 'bd-verify-cut ' + normalized, retry
    if executable == 'bd-prepush.sh':
        return 'bd-prepush ' + normalized, retry
    if executable == 'bd-precut' and '--gate' in words:
        return 'bd-precut-gate ' + normalized, retry
    if executable == 'pytest' and not any('::' in word for word in words):
        return 'pytest-broad ' + normalized, retry
    return None


def deny(message):
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny', 'permissionDecisionReason': message}}))


payload = json.load(sys.stdin)
if payload.get('hook_event_name') == 'SessionStart':
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart',
        'additionalContext': 'Efficiency: read /home/mboyle/bd-persist/cx-restart-20260909/CURRENT.json and /home/mboyle/bd-persist/CUT-WORKFLOW.md once; reuse unchanged evidence; run each validation once and monitor it.'}}))
    raise SystemExit(0)
if payload.get('hook_event_name') != 'PreToolUse' or payload.get('tool_name') != 'Bash':
    raise SystemExit(0)
tool_input = payload.get('tool_input')
command = tool_input.get('command') if isinstance(tool_input, dict) else None
session = payload.get('session_id')
cwd = payload.get('cwd')
if not all(isinstance(value, str) and value for value in (command, session, cwd)):
    raise SystemExit(0)
match = recognized(command)
if match is None:
    raise SystemExit(0)
normalized, reason = match
state_path = pathlib.Path(os.environ.get(
    'BD_EFFICIENCY_STATE', '/home/mboyle/bd-persist/efficiency-hook/state/attempts.json'))
state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
lock_path = state_path.with_suffix(state_path.suffix + '.lock')
key = hashlib.sha256((session + '\0' + cwd + '\0' + normalized).encode()).hexdigest()
with open(lock_path, 'a+', encoding='utf-8') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        try:
            raw = state_path.read_text(encoding='utf-8')
            # H314: a 0-byte (or whitespace-only) state file is what a crash
            # leaves behind mid-write; it carries no attempts, so it is FRESH
            # state, not corruption. Denying it blocked every recognized
            # validation on this host for ~23 h. A NON-EMPTY malformed file is
            # still corruption and is still denied below.
            state = json.loads(raw) if raw.strip() else {'attempts': {}}
        except FileNotFoundError:
            state = {'attempts': {}}
        except (OSError, ValueError, TypeError):
            deny('recognized validation state unavailable; no attempt was recorded')
            raise SystemExit(0)
        # A parsed state that is not an object has no .get; without this the
        # hook raised AttributeError and exited nonzero instead of deciding.
        attempts = state.get('attempts') if isinstance(state, dict) else None
        if not isinstance(attempts, dict):
            deny('recognized validation state unavailable; no attempt was recorded')
            raise SystemExit(0)
        prior = attempts.get(key)
        if prior and not reason:
            deny('recognized validation was already attempted; set nonempty BD_EFFICIENCY_RETRY_REASON to retry')
        else:
            attempts[key] = {'session': session, 'cwd': cwd, 'command': normalized,
                             'attempts': int(prior.get('attempts', 0) if prior else 0) + 1,
                             'last_retry_reason': reason or None}
            temporary = state_path.with_name('.' + state_path.name + '.tmp')
            temporary.write_text(json.dumps(state, separators=(',', ':')), encoding='utf-8')
            os.replace(temporary, state_path)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
