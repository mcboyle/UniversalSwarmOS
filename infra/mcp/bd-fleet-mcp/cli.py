#!/usr/bin/env python3
import argparse,json,os,re,shlex,sys
from server import premise_verify,say_validate

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


_SAY_TOOLS=('bd-say','bd-say.sh')

def hook(raw):
    if not raw.strip():return []
    if raw.lstrip().startswith(('{','[')):
        try:obj=json.loads(raw)
        except (ValueError,TypeError):return []
        if not isinstance(obj,dict) or not isinstance(obj.get('tool_input'),dict) or not isinstance(obj.get('tool_name'),str):return []
        inp=obj['tool_input'];name=obj.get('tool_name','')
        if name in ('say','mcp__bd__say'):
            target=inp.get('target',inp.get('recipient'))
            message=inp.get('text',inp.get('message'))
            if not isinstance(target,str) or not isinstance(message,str):return []
            sender=inp.get('sender');from_sender=inp.get('from')
            if sender is not None and from_sender is not None and sender!=from_sender:
                raise ValueError('conflicting sender and from aliases')
            sender=sender if sender is not None else from_sender
            if sender is not None and not isinstance(sender,str):raise ValueError('invalid sender alias')
            return [say_validate(inp.get('target',inp.get('recipient','')),inp.get('text',inp.get('message','')),sender,True)]
        raw=inp.get('command',inp.get('CommandLine',inp.get('cmd','')))
        if not isinstance(raw,str):return []
    results=[]
    for tool,args in _invocations(raw,_SAY_TOOLS):
        if any('$' in a or '`' in a for a in args):raise ValueError(f'{tool}: dynamic argument; say needs literal target and message')
        if len(args)!=2:raise ValueError(f'{tool}: say needs literal target and message (got {len(args)} args)')
        results.append(say_validate(args[0],args[1],None,True))
    return results

def main():
    mode=sys.argv[1]
    try:
        if mode=='hook':
            if len(sys.argv)>3:raise ValueError('one hook payload expected')
            results=hook(sys.argv[2] if len(sys.argv)==3 else sys.stdin.read())
            rejected=[r for r in results if not r['valid']]
            if rejected:raise ValueError(json.dumps(rejected))
            return 0
        parser=argparse.ArgumentParser()
        if mode=='say':
            parser.add_argument('target');parser.add_argument('message');parser.add_argument('sender',nargs='?');parser.add_argument('--record',action='store_true')
            args=parser.parse_args(sys.argv[2:]);res=say_validate(args.target,args.message,args.sender,args.record);ok=res['valid']
        elif mode=='premise':
            parser.add_argument('target',nargs='?');args=parser.parse_args(sys.argv[2:]);res=premise_verify(args.target or sys.stdin.read().strip());ok=res['verdict']=='PROCEED'
        else:raise ValueError('invalid CLI mode')
        print(json.dumps(res));return 0 if ok else 1
    except (ValueError,TypeError,OSError) as exc:
        print('REFUSED: '+str(exc),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
