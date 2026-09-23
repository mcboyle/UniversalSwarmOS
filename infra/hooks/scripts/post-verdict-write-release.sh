#!/usr/bin/env python3
"""Release only a validated terminal receipt; use explicit claim and seat identity."""
import json
import os
import pathlib
import re
import subprocess
import sys


def is_receipt(path):
    return path.name == 'DONE.md' or re.fullmatch(r'VERDICT-.+\.md', path.name)


def patch_target(raw, payload):
    """Read operation headers, never header-looking text inside a patch body."""
    if not isinstance(raw, str):
        raise ValueError('[PATCH-PAYLOAD] patch must be a string')
    lines = raw.splitlines()
    if len(lines) < 2 or lines[0] != '*** Begin Patch' or lines[-1] != '*** End Patch':
        raise ValueError('[PATCH-PAYLOAD] expected complete Begin/End Patch envelope')
    base = payload.get('cwd') or os.environ.get('BD_VERDICT_WORKTREE')
    if base is not None and (not isinstance(base, str) or not pathlib.Path(base).is_absolute()):
        raise ValueError('[PATCH-PAYLOAD] cwd/worktree must be an absolute path')

    def resolve(raw_path):
        if not raw_path.strip() or '\x00' in raw_path:
            raise ValueError('[PATCH-PAYLOAD] empty or invalid file header')
        path = pathlib.Path(raw_path)
        if not path.is_absolute():
            if not base:
                raise ValueError('[PATCH-PAYLOAD] relative target requires cwd or BD_VERDICT_WORKTREE')
            path = pathlib.Path(base) / path
        return path.resolve()

    resulting = set()
    index = 1
    while index < len(lines) - 1:
        header = re.fullmatch(r'\*\*\* (Add File|Update File|Delete File): (.+)', lines[index])
        if not header:
            raise ValueError('[PATCH-PAYLOAD] malformed or orphan operation header')
        operation, source = header.groups()
        source = resolve(source)
        target = source
        index += 1
        if operation == 'Update File' and index < len(lines) - 1 and lines[index].startswith('*** Move to:'):
            moved = re.fullmatch(r'\*\*\* Move to: (.+)', lines[index])
            if not moved:
                raise ValueError('[PATCH-PAYLOAD] malformed Move to header')
            target = resolve(moved[1])
            index += 1
        body = []
        while index < len(lines) - 1:
            line = lines[index]
            if line.startswith('*** ') and line != '*** End of File':
                break
            body.append(line)
            index += 1
        if operation == 'Delete File':
            if body:
                raise ValueError('[PATCH-PAYLOAD] deletion cannot contain a patch body')
            resulting.discard(source)
        elif operation == 'Add File':
            if any(not line.startswith('+') for line in body):
                raise ValueError('[PATCH-PAYLOAD] added content requires + line prefixes')
            resulting.add(target)
        else:
            if not body or any(line and not line.startswith(('@@', ' ', '+', '-')) and line != '*** End of File' for line in body):
                raise ValueError('[PATCH-PAYLOAD] malformed update body')
            resulting.discard(source)
            resulting.add(target)
    receipts = sorted(path for path in resulting if is_receipt(path))
    if len(receipts) > 1:
        raise ValueError('[PATCH-AMBIGUOUS] multiple resulting receipts; no claim released')
    return str(receipts[0]) if receipts else ''


def main():
    payload = None
    if len(sys.argv) == 2:
        target = sys.argv[1]
    elif len(sys.argv) == 1:
        try:
            payload = json.load(sys.stdin)
            if not isinstance(payload, dict):
                raise ValueError('expected object')
            agy = 'toolCall' in payload
            tool = payload['toolCall'] if agy else payload
            if not isinstance(tool, dict):
                raise ValueError('tool call must be an object')
            args = tool.get('args' if agy else 'tool_input')
            name = tool.get('name' if agy else 'tool_name', '')
            if isinstance(args, str):
                target = patch_target(args, payload)
            elif isinstance(args, dict):
                keys = [key for key in ('input', 'patch') if key in args]
                if keys or name in ('apply_patch', 'functions.apply_patch'):
                    if len(keys) != 1:
                        raise ValueError('[PATCH-PAYLOAD] exactly one input/patch string is required')
                    target = patch_target(args[keys[0]], payload)
                else:
                    target = args.get('TargetFile', args.get('file_path', args.get('path', '')))
            else:
                raise ValueError('tool input must be an object or patch string')
            if not isinstance(target, str):
                raise ValueError('target must be string')
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f'[PAYLOAD] {exc}')
    else:
        raise ValueError('[USAGE] expected a path or hook JSON on stdin')
    p = pathlib.Path(target)
    if not target or not is_receipt(p):
        return
    lines = p.read_text().splitlines()
    if not lines:
        raise ValueError('[VERDICT] empty receipt; no release')
    if lines[0] not in ('VERDICT: BOARD', 'VERDICT: REFUTE'):
        return
    wt = os.environ.get('BD_VERDICT_WORKTREE')
    if not wt:
        raise ValueError('[IDENTITY] BD_VERDICT_WORKTREE required; no release')
    helper = pathlib.Path(__file__).resolve().parents[1] / 'scripts/bd-worker-done.sh'
    r = subprocess.run([str(helper), '--check', str(p), wt], capture_output=True, text=True)
    if r.returncode:
        raise ValueError('[VALIDATION] ' + (r.stdout + r.stderr).strip())
    required = ('BD_CLAIM_OBJECT', 'BD_LENS', 'BD_SEAT', 'BD_ROLE', 'BD_STATUS_SEAT')
    for key in required:
        if not os.environ.get(key) or '\n' in os.environ[key]:
            raise ValueError(f'[IDENTITY] {key} required; no release')
    calls = [
        ([os.environ.get('BD_CLAIM_HELPER', '/home/mboyle/bd-persist/harness/bd-claim-object.sh'), 'release', os.environ['BD_CLAIM_OBJECT'], os.environ['BD_LENS'], os.environ['BD_SEAT']], 'CLAIM'),
        ([os.environ.get('BD_ROLE_STATE_HELPER', '/home/mboyle/bd-persist/harness/bd-role-state.sh'), 'clear', os.environ['BD_ROLE'], os.environ['BD_SEAT']], 'ROLE-STATE'),
        ([os.environ.get('BD_SAY_HELPER', '/home/mboyle/bd-say.sh'), os.environ['BD_STATUS_SEAT'], f'RELEASED {p}'], 'NOTICE')]
    # Validate every dependency before the first effect; report the exact failed step.
    for command, tag in calls:
        if not os.path.isfile(command[0]) or not os.access(command[0], os.X_OK):
            raise ValueError(f'[{tag}] helper is not executable: {command[0]}')
    for command, tag in calls:
        r = subprocess.run(command, capture_output=True, text=True)
        if r.returncode:
            raise ValueError(f'[{tag}] rc={r.returncode} {(r.stdout + r.stderr).strip()}')
    print('[AUTO-RELEASE] ' + r.stdout.strip(), file=sys.stderr)

if __name__ == '__main__':
    try:
        main()
        print('{}')
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        # PostToolUse reports the failure; the already-completed write is never undone.
        sys.exit(2)
