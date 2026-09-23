#!/usr/bin/env python3
"""Wrap the entire shell expression when a test tool is INVOKED (command position); a mention in arguments, strings, heredocs or comments is a no-op."""
import json
import pathlib
import re
import shlex
import sys

_WRAP=('sudo','env','command','exec','nohup','time','nice','timeout')
_KEYWORDS=('!','if','then','do','else','elif','while','until','{','}')
_SHELLS=('bash','sh','zsh','dash')

def _strip_heredocs(text):
    out = []; pending = []; quote = None
    for line in text.split('\n'):
        if pending:
            delim, dash = pending[0]
            if (line.lstrip('\t') if dash else line) == delim:
                pending.pop(0)
            continue
        out.append(line)
        i = 0
        while i < len(line):
            char = line[i]
            if char == '\\' and quote != "'":
                i += 2; continue
            if quote:
                if char == quote: quote = None
                i += 1; continue
            if char in "'\"":
                quote = char; i += 1; continue
            if char == '#' and (i == 0 or line[i-1] in ' \t;&|('):
                break
            if line.startswith('<<<', i):
                i += 3; continue
            if not line.startswith('<<', i):
                i += 1; continue
            i += 2
            dash = i < len(line) and line[i] == '-'
            if dash: i += 1
            while i < len(line) and line[i].isspace(): i += 1
            start = i; delim_quote = None
            while i < len(line):
                char = line[i]
                if char == '\\' and delim_quote != "'":
                    i += 2; continue
                if delim_quote:
                    if char == delim_quote: delim_quote = None
                elif char in "'\"": delim_quote = char
                elif char.isspace() or char in ';&|<>()': break
                i += 1
            words = shlex.split(line[start:i])
            if len(words) != 1: raise ValueError('missing heredoc delimiter')
            pending.append((words[0], dash))
    if pending: raise ValueError('unterminated heredoc')
    return '\n'.join(out)

def _flatten(text, separator):
    # Mark only syntactic separators before shlex removes quoting information.
    out=[];q=None;i=0;n=len(text)
    while i<n:
        c=text[i]
        if q:
            out.append(c)
            if c=='\\' and q=='"' and i+1<n:out.append(text[i+1]);i+=1
            elif c==q:q=None
        elif c=='\\' and i+1<n:
            out.append(' ' if text[i+1]=='\n' else c+text[i+1]);i+=1
        elif c in "'\"":q=c;out.append(c)
        elif c=='#' and (i==0 or text[i-1] in ' \t\n;&|('):
            while i<n and text[i]!='\n':i+=1
            continue
        elif c in '\n;|()' or (c=='&' and (i==0 or text[i-1] not in '<>')):
            out.append(' '+separator+' ')
        else:out.append(c)
        i+=1
    return ''.join(out)

def _clean_args(args):
    if len(args)==2:return args
    out=[];skip=False
    for a in args:
        if skip:skip=False;continue
        if re.fullmatch(r'(\d*|&)[<>]+',a):skip=True;continue
        if re.match(r'(\d*|&)[<>]',a):continue
        out.append(a)
    return out

def _simple(cmd,tools,depth):
    i=0
    while i<len(cmd):
        t=cmd[i];b=t.rsplit('/',1)[-1]
        if re.match(r'[A-Za-z_]\w*=',t) or t in _KEYWORDS:i+=1;continue
        if b in _WRAP:
            i+=1
            while i<len(cmd) and (cmd[i].startswith('-') or re.fullmatch(r'\d+[smhd]?',cmd[i]) or re.match(r'[A-Za-z_]\w*=',cmd[i])):i+=1
            continue
        break
    if i>=len(cmd):return []
    base=cmd[i].rsplit('/',1)[-1];rest=cmd[i+1:]
    if base in tools:return [(base,_clean_args(rest))]
    if base in _SHELLS:
        j=0
        while j<len(rest):
            t=rest[j]
            if t in ('-o','+o'):j+=2;continue
            if t.startswith('-') and not t.startswith('--') and 'c' in t[1:]:
                return _invocations(rest[j+1],tools,depth+1) if j+1<len(rest) and depth<5 else []
            if t.startswith(('-','+')):j+=1;continue
            script=t.rsplit('/',1)[-1]
            return [(script,_clean_args(rest[j+1:]))] if script in tools else []
        return []
    if re.fullmatch(r'python[\d.]*',base):
        j=0
        while j<len(rest):
            t=rest[j]
            if t=='-c':return []
            if t=='-m' and j+1<len(rest):
                mod=rest[j+1].rsplit('/',1)[-1]
                return [(mod,_clean_args(rest[j+2:]))] if mod in tools else []
            if t.startswith('-'):j+=1;continue
            script=t.rsplit('/',1)[-1]
            return [(script,_clean_args(rest[j+1:]))] if script in tools else []
    return []

def _invocations(command,tools,depth=0):
    """Recognize syntactic command positions; malformed shell text is a no-op."""
    # NUL cannot occur in a shell command or be synthesized by quote removal.
    if '\0' in command:return []
    separator='\0'
    try:
        lexer=shlex.shlex(_flatten(_strip_heredocs(command),separator),posix=True)
        lexer.whitespace_split=True;lexer.commenters=''
        tokens=list(lexer)
    except ValueError:return []
    found=[];cmd=[]
    for t in tokens+[separator]:
        if t==separator:
            if cmd:found+=_simple(cmd,tools,depth)
            cmd=[]
        else:cmd.append(t)
    return found


_SEAT_ROOTS = ('/var/tmp/bd-seats', '/home/mboyle/bd-cuts')
_VALUE_OPTS = ('-k', '-m', '-p', '-c', '-o', '-W', '-n', '--deselect', '--ignore', '--ignore-glob', '--rootdir', '--basetemp', '--junitxml', '--tb', '--maxfail', '--durations', '--confcutdir')

def _pytest_targets(args):
    targets = []; skip = False
    for a in args:
        if skip:
            skip = False; continue
        if a in _VALUE_OPTS:
            skip = True; continue
        if a.startswith('-'):
            continue
        targets.append(a)
    return targets

def _policy_violation(found):
    """Return (token, reason) when a pytest invocation names other than exactly one test file."""
    for tool, args in found:
        if tool != 'pytest':
            continue
        targets = _pytest_targets(args)
        files = {t.split('::', 1)[0] for t in targets}
        if not targets:
            return tool, 'bare pytest names no test file'
        if len(files) != 1 or not next(iter(files)).endswith('.py'):
            return tool, 'named ' + ' '.join(targets)
    return None

_TEST_TOOLS = ('pytest', 'run_tests', 'run_tests.sh', 'run_tests.py', 'bd-worker-band', 'bd-worker-band.sh')

try:
    if len(sys.argv) > 2:
        raise ValueError('expected at most one JSON argument')
    data = json.loads(sys.argv[1] if len(sys.argv) == 2 else sys.stdin.read())
    if not isinstance(data, dict):
        raise ValueError('expected an object')
    agy = 'toolCall' in data
    tool = data.get('toolCall', {}) if agy else data
    name = tool.get('name' if agy else 'tool_name')
    args = tool.get('args' if agy else 'tool_input')
    if not isinstance(name, str) or not isinstance(args, dict):
        raise ValueError('tool name and input object are required')
    key = 'CommandLine' if agy else 'command'
    command = args.get(key, '')
    if not isinstance(command, str):
        raise ValueError('command must be a string')
    result = {'decision': 'allow'} if agy else {}
    found = _invocations(command, _TEST_TOOLS) if name in ('run_command', 'Bash', 'exec_command', 'shell_command') else []
    cwd = next((str(v) for v in (data.get('cwd'), tool.get('cwd'), args.get('cwd'), args.get('Cwd')) if isinstance(v, str)), '')
    def in_seat(path):
        return any(path == root or path.startswith(root + '/') for root in _SEAT_ROOTS)
    seat_cwd = in_seat(cwd) or any(args and in_seat(args[-1]) for _, args in _invocations(command, ('cd',)))
    if found and seat_cwd:
        violation = _policy_violation(found)
        if violation:
            print(f'[BD-TEST-FILTER] REFUSED: name exactly one test file; suites run remotely ({violation[0]}: {violation[1]})', file=sys.stderr)
            sys.exit(2)
    if found:
        path = str(pathlib.Path(__file__).resolve().parents[1] / 'scripts/bd-test-filter.sh')
        # A leading invocation of this exact wrapper is the only bypass.
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = [path]
        if not tokens or tokens[0] != path:
            updated = {**args, key: shlex.join([path, 'bash', '-o', 'pipefail', '-c', command])}
            result = {'decision': 'allow', 'overwrite': updated} if agy else {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'allow', 'updatedInput': updated}}
    if found:
        print(json.dumps(result))
except (ValueError, TypeError, AttributeError):
    # O1093: malformed hook payloads cannot block unrelated work.
    sys.exit(0)
