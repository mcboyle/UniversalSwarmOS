#!/usr/bin/env python3
"""Fleet command adapters; all subprocess failures propagate and dry-run never calls mutators."""
import argparse,concurrent.futures,datetime,fcntl,hashlib,json,os,re,secrets,shlex,signal,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HARNESS=Path(os.environ.get('BD_HARNESS','/home/mboyle/bd-persist/harness'))
PERSIST=Path(os.environ.get('BD_PERSIST','/home/mboyle/bd-persist'))
REPO=Path(os.environ.get('BD_REPO','/home/mboyle/BulkDownloader'))
class Refusal(Exception):pass

def name(s):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',s) or s=='bd-capture-test2':raise Refusal('invalid or operator-owned name')
    return s

def read(path):
    p=Path(path)
    if not p.is_file():raise Refusal(f'file missing: {path}')
    text=p.read_text()
    if not text.strip():raise Refusal(f'file empty: {path}')
    return text

def run(args,**kwargs):
    p=subprocess.run([str(x) for x in args],text=True,capture_output=True,timeout=30,**kwargs)
    if p.returncode:raise Refusal(f'helper rc={p.returncode}: {p.stderr.strip() or p.stdout.strip()}')
    return p.stdout

def helper(key,filename):
    p=Path(os.environ.get(key,str(HARNESS/filename)))
    if not p.is_file() or not os.access(p,os.X_OK):raise Refusal(f'helper missing or not executable: {p}')
    return p

def rule21(content):
    if not content.strip():raise Refusal('empty brief')
    patterns=[r'OPERATOR-ACTION',r'bd-capture-test2',r'\b(?:start|execute|live)\s+(?:a\s+|site\s+)?login',r'login\s+capture',r'enter\s+credentials',r'(?:operator|live|production)\b[^\n]*\b(?:soak|capture)',r'\b(?:log\s+in|sign\s+in)\s+(?:to|on)\s+(?:the\s+)?(?:live\s+)?site']
    for pat in patterns:
        if re.search(pat,content,re.I):raise Refusal('RULE-21 REFUSAL: operator-bound row stays PARKED')

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
            value_options={'sudo':('-u','--user','-g','--group','-h','--host','-p','--prompt'),
                           'env':('-u','--unset','-C','--chdir'),
                           'time':('-f','--format','-o','--output'),
                           'nice':('-n','--adjustment'),'timeout':('-s','--signal','-k','--kill-after')}
            i+=1
            while i<len(cmd):
                if cmd[i]=='--':
                    i+=1
                    if b=='timeout' and i<len(cmd) and re.fullmatch(r'\d+[smhd]?',cmd[i]):i+=1
                    break
                if cmd[i] in value_options.get(b,()):i+=2;continue
                if cmd[i].startswith('-') or re.fullmatch(r'\d+[smhd]?',cmd[i]) or re.match(r'[A-Za-z_]\w*=',cmd[i]):i+=1;continue
                break
            continue
        break
    if i>=len(cmd):return []
    base=cmd[i].rsplit('/',1)[-1];rest=cmd[i+1:]
    if base in tools:return [(base,_clean_args(rest))]
    if base in _SHELLS:
        j=0
        has_c=False
        while j<len(rest):
            t=rest[j]
            if t=='--':j+=1;break
            if t in ('-o','+o'):j+=2;continue
            if t.startswith('-') and not t.startswith('--'):
                if 'c' in t[1:]:has_c=True
                j+=1;continue
            if t.startswith('--') or t.startswith('+'):j+=1;continue
            break
        if has_c:
            return _invocations(rest[j],tools,depth+1) if j<len(rest) and depth<5 else []
        if j<len(rest):
            script=rest[j].rsplit('/',1)[-1]
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


def hook(raw):
    # O1093/O1105: unavailable or malformed telemetry never blocks a tool call.
    try:
        obj=json.loads(raw)
        if not isinstance(obj,dict):return
        tool=obj.get('toolCall',obj)
        if not isinstance(tool,dict):return
        inp=tool.get('args' if 'toolCall' in obj else 'tool_input')
        if not isinstance(inp,dict):return
        command=inp.get('command',inp.get('CommandLine',inp.get('cmd')))
        if not isinstance(command,str):return
    except (ValueError,TypeError,AttributeError,RecursionError):return
    command_hook(command)

def command_hook(command):
    try:
        invs=_invocations(command,('bd-dispatch.sh','bd-dispatch','bd-dispatch-manifest.sh'))
    except (ValueError,RecursionError):return
    for tool,args in invs:
        try:
            if args and args[0]=='--manifest':
                if len(args)!=2:continue
                manifest_rows(args[1])
            elif tool=='bd-dispatch-manifest.sh':
                if len(args) not in (1,2) or (len(args)==2 and args[1]!='--dry-run'):continue
                manifest_rows(args[0])
            else:
                if len(args) not in (3,4):continue
                name(args[0]);name(args[1]);rule21(read(args[2]))
        except Refusal as exc:
            # Only a measured Rule21 violation may block; missing input is telemetry loss.
            if str(exc).startswith('RULE-21 REFUSAL:'):raise
        except (OSError,ValueError,TypeError):continue

def premise(path):
    h=helper('BD_PREMISE_HELPER','../plugins/bd-fleet-mcp/scripts/premise-verify.sh')
    response=json.loads(run([h,path]))
    if not isinstance(response,dict) or response.get('verdict')!='PROCEED' or response.get('violations')!=[]:raise Refusal('premise verifier did not prove PROCEED')

def manifest_rows(path):
    rows=[];seen=set();dupes=0
    for lineno,line in enumerate(read(path).splitlines(),1):
        if not line.strip() or line.lstrip().startswith('#'):continue
        cells=line.split('\t')
        if len(cells)!=4 or any(not c.strip() or c!=c.strip() for c in cells):raise Refusal(f'manifest line {lineno}: expected four nonempty TSV fields')
        seat,row,brief,tier=cells;name(seat);name(row)
        if tier not in ('T0','T1','T2','T3'):raise Refusal(f'manifest line {lineno}: invalid tier')
        rule21(read(brief))
        if row in seen:dupes+=1;continue
        seen.add(row);rows.append((seat,row,brief,tier))
    if not rows:raise Refusal('empty manifest')
    return rows,dupes

def dispatch(args):
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('--dry-run',action='store_true');a=p.parse_args(args)
    rows,dupes=manifest_rows(a.manifest)
    for _,_,brief,_ in rows:premise(brief)
    if a.dry_run:print(f'DRY-RUN: validated={len(rows)} dupes_skipped={dupes} dispatched=0');return
    h=helper('BD_DISPATCH_HELPER','bd-dispatch.sh')
    if not re.search(r'^# BD_DISPATCH_BATCH_V1(?:[:\s]|$)',read(h),re.M):raise Refusal('dispatch helper lacks unapplied batch patch')
    say=helper('BD_SAY_HELPER','../../bd-say.sh')
    ledger=Path(os.environ.get('BD_DISPATCH_LEDGER',str(PERSIST/'DISPATCH-LEDGER.tsv')))
    if not ledger.parent.is_dir():raise Refusal('ledger directory missing')
    failures=[];records=[]
    with open(str(ledger)+'.lock','a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise Refusal('dispatch lock busy')
        previous={}
        if ledger.exists():
            for line in ledger.read_text().splitlines():
                cells=line.split('\t')
                if len(cells)<5:raise Refusal('ledger malformed')
                previous[cells[2]]=cells[3]
        # Only observed terminal states release a slug; active and unknown states refuse.
        if any(previous.get(row) not in (None,'done','aborted','gone') for _,row,_,_ in rows):raise Refusal('slug already active or unresolved in ledger')
        # Prove append access under the lock before any dispatch, and retain that descriptor.
        with ledger.open('a') as output:
            for seat,row,brief,tier in rows:
                try:
                    run([h,seat,row,brief,tier],env={**os.environ,'BD_DISPATCH_BATCH_V1':'1','BD_DISPATCH_LEDGER':str(ledger)})
                    records.append('\t'.join([datetime.datetime.now(datetime.timezone.utc).isoformat(),seat,row,'dispatched',brief])+'\n')
                except (Refusal,subprocess.SubprocessError,OSError) as exc:failures.append(f'{row}: {exc}');break
            if records:
                output.write(''.join(records));output.flush();os.fsync(output.fileno())
        summary=f'BATCH {len(records)}/{len(rows)} {ledger}'
        try:run([say,os.environ.get('BD_SUMMARY_TARGET','pm'),summary])
        except (Refusal,subprocess.SubprocessError,OSError) as exc:failures.append(f'summary delivery failed: {exc}')
    print(f'dispatched={len(records)} failed={len(failures)} dupes_skipped={dupes}')
    if failures:raise Refusal('; '.join(failures))

def next_id(args):
    p=argparse.ArgumentParser();p.add_argument('--check-stale');a=p.parse_args(args)
    directory=Path(os.environ.get('BD_BRIEFS_DIR','/home/mboyle/bd-codex-briefs'))
    if not directory.is_dir():raise Refusal('brief census unavailable')
    ids={}
    for path in directory.glob('*.md'):
        for match in re.finditer(r'(?:^|[^a-z0-9])(?:row|brief-)(\d+)(?=$|[^0-9])',path.stem,re.I):ids.setdefault(int(match[1]),[]).append(str(path))
    if a.check_stale is not None:
        if not a.check_stale.isdecimal():raise Refusal('invalid row id')
        if int(a.check_stale) in ids:raise Refusal('STALE: '+' '.join(ids[int(a.check_stale)]))
        print('CLEAN: no matching row brief');return
    register=read(os.environ.get('BD_BACKLOG',str(REPO/'project-knowledge/IMPROVEMENT_BACKLOG.md')))
    rows={int(x) for x in re.findall(r'^\|\s*(\d+)\s*\|',register,re.M)}
    if not rows:raise Refusal('register contains no row ids')
    print(max(rows|set(ids))+1)

def launch(args):
    p=argparse.ArgumentParser();p.add_argument('role');p.add_argument('pool',nargs='?',default='A');p.add_argument('--brief');p.add_argument('--cut');p.add_argument('--dry-run',action='store_true');a=p.parse_args(args)
    if a.role not in ('worker','worker-b','review-lite','review-correctness','review-shape','lite','correctness','shape'):raise Refusal('unsupported demand role')
    if a.pool not in ('A','B','codex','auto'):raise Refusal('invalid pool')
    if a.role.startswith('worker'):
        if not a.brief or a.cut:raise Refusal('IDLE-SUPPLY: explicit pending brief required')
        rule21(read(a.brief));premise(a.brief)
    else:
        if not a.cut or a.brief:raise Refusal('IDLE-SUPPLY: explicit claimable cut required')
        cut=Path(a.cut)
        if read(cut/'DONE.md').splitlines()[0]!='VERDICT: PATCH':raise Refusal('cut is not pending PATCH')
        rule21(read(cut/'.review/BRIEF.md'))
        read(cut/'.review/TIER.md')
        out=run([helper('BD_CLAIM_HELPER','bd-claim-object.sh'),'holder',str(cut)])
        if not out.startswith('NOT-HELD '):raise Refusal('cut claim status is not NOT-HELD')
    if a.dry_run:print(f'DRY-RUN: demand verified {a.role} {a.pool}');return
    print(run([helper('BD_LAUNCH_HELPER','bd-launch-role.sh'),a.role,a.pool]),end='')

def retire(args):
    p=argparse.ArgumentParser();p.add_argument('seat');p.add_argument('reason',nargs='?',default='scheduled rotation');p.add_argument('--handoff');p.add_argument('--dry-run',action='store_true');a=p.parse_args(args);name(a.seat)
    if a.dry_run:print(f'DRY-RUN: lessons before STOP; fresh handoff required for {a.seat}');return
    if not a.handoff:raise Refusal('handoff required; collect lessons before retirement')
    data=dict(re.findall(r'^([A-Z-]+):\s*(.+)$',read(a.handoff),re.M))
    if any(not data.get(k) for k in ('SEAT','STATE','STAGED','RECEIPT','REMAINING','LESSONS','WRITTEN-AT','BACKGROUND','PRECUT')):raise Refusal('handoff schema incomplete')
    if data['SEAT']!=a.seat:raise Refusal('handoff seat mismatch')
    written=datetime.datetime.fromisoformat(data['WRITTEN-AT'].replace('Z','+00:00'))
    age=(datetime.datetime.now(datetime.timezone.utc)-written).total_seconds()
    if not 0<=age<=300:raise Refusal('handoff stale')
    if data['STAGED']!='none' or data['BACKGROUND']!='none' or data['PRECUT']!='none':raise Refusal('active staged/background/precut work requires operator-reviewed adoption receipt')
    if data['LESSONS'] in ('none','pending'):raise Refusal('lessons not captured')
    print(run([helper('BD_RETIRE_HELPER','bd-retire-seat.sh'),a.seat,a.reason,'--no-relaunch']),end='')

def seat_verify(args):
    p=argparse.ArgumentParser();p.add_argument('seat');p.add_argument('--probe');a=p.parse_args(args);name(a.seat)
    probe=a.probe or os.environ.get('BD_SEAT_PROBE')
    if not probe:raise Refusal('COULD NOT LOOK: active seat challenge adapter required')
    rule_path=Path(os.environ.get('BD_FLEET_RULE',str(PERSIST/'FLEET_RULE.md')))
    digest=hashlib.sha256(read(rule_path).encode()).hexdigest();nonce=secrets.token_hex(16)
    result=json.loads(run([probe,a.seat,nonce,str(rule_path)]))
    if result.get('seat')!=a.seat or result.get('nonce')!=nonce or result.get('rules_sha256')!=digest:raise Refusal('challenge identity/nonce/rules mismatch')
    if result.get('mcp',{}).get('ok') is not True or not result.get('mcp',{}).get('tool'):raise Refusal('live MCP proof missing')
    if any(not isinstance(result.get(k),list) or any(not isinstance(x,str) or not x for x in result[k]) for k in ('plugins','hooks')):raise Refusal('active plugin/hook attestation missing')
    if result.get('operator_visible') is not True:raise Refusal('operator visibility proof missing')
    print(json.dumps({'verification':'PASS','seat':a.seat,'mcp':result['mcp'],'plugins':result['plugins'],'hooks':result['hooks']}))

def wt_new(args):
    p=argparse.ArgumentParser();p.add_argument('slug');p.add_argument('base',nargs='?',default='origin/main');p.add_argument('--dry-run',action='store_true');p.add_argument('--require-service',action='append',default=[]);a=p.parse_args(args);name(a.slug)
    target=Path(os.environ.get('BD_CUTS','/home/mboyle/bd-cuts/cut'))/a.slug
    py=REPO/'venv/bin/python'
    if not py.is_file() or not os.access(py,os.X_OK):raise Refusal('ENV-FAILURE: pinned interpreter missing')
    run([py,'-c','import sys; assert sys.version_info >= (3, 10)'])
    rg_bin=os.environ.get('BD_RG','rg')
    try:run([rg_bin,'--version'])
    except (FileNotFoundError,OSError):raise Refusal('ENV-FAILURE: rg missing')
    sha=run(['git','-C',REPO,'rev-parse','--verify',a.base+'^{commit}']).strip()
    if target.exists():raise Refusal('target already exists; never overwritten')
    modules=REPO/'frontend/node_modules'
    if not modules.is_dir():raise Refusal('ENV-FAILURE: frontend/node_modules missing')
    if not target.parent.is_dir():raise Refusal('cut root missing')
    for service in a.require_service:
        name(service)
        try:run([helper('BD_SERVICE_PREFLIGHT','bd-service-preflight.sh'),service,str(REPO)])
        except (Refusal,OSError,subprocess.SubprocessError) as exc:raise Refusal(f'service {service}: {exc}')
    if a.dry_run:print(f'DRY-RUN: worktree {target} base={sha} services={a.require_service}');return
    run(['git','-C',REPO,'worktree','add','--detach',target,sha])
    if (target/'venv').exists() or (target/'venv').is_symlink():raise Refusal('worktree has venv; preserved, bootstrap incomplete')
    (target/'venv').symlink_to(REPO/'venv',target_is_directory=True)
    frontend=target/'frontend';frontend.mkdir(exist_ok=True)
    if (frontend/'node_modules').exists() or (frontend/'node_modules').is_symlink():raise Refusal('worktree has node_modules; preserved, bootstrap incomplete')
    (frontend/'node_modules').symlink_to(modules,target_is_directory=True)
    localbin=target/'.bd-bin';localbin.mkdir(exist_ok=True);(localbin/'python3').symlink_to(py)
    tests=target/'tests';tests.mkdir(exist_ok=True)
    stub=tests/('test_'+a.slug.replace('-','_').replace('.','_')+'_scope.py')
    with stub.open('x') as f:f.write('"""Scope declaration; add task regression tests before gating."""\nBD_GATE_SCOPE = "module"\n')
    print(f'BOOTSTRAP: {target}; prepend {localbin} to PATH; requested services checked={a.require_service}')

def gates(args):
    p=argparse.ArgumentParser();p.add_argument('worktree');p.add_argument('tests',nargs='+');p.add_argument('--dry-run',action='store_true');p.add_argument('--jobs',type=int,default=2);a=p.parse_args(args)
    wt=Path(a.worktree).resolve();py=wt/'venv/bin/python';derive=wt/'toolchain/bin/bd-band-derive'
    if not wt.is_dir() or not py.is_file() or not os.access(py,os.X_OK) or not derive.is_file():raise Refusal('gate environment or canonical derivation tool missing')
    if not 1<=a.jobs<=8:raise Refusal('--jobs must be 1..8')
    runner=os.environ.get('BD_GATE_RUNNER','')
    if not runner:raise Refusal('explicit remote gate adapter BD_GATE_RUNNER required')
    runner=Path(runner)
    if not runner.is_file() or not os.access(runner,os.X_OK) or not re.search(r'^# BD_REMOTE_GATE_V1(?:[:\s]|$)',read(runner),re.M):raise Refusal('remote adapter contract missing')
    files=[]
    for test in a.tests:
        path=Path(test.split('::')[0])
        if test.startswith('-') or path.is_absolute() or '..' in path.parts or not (wt/path).is_file():raise Refusal(f'gate test missing or invalid: {test}')
        files.append(str(path))
    if a.dry_run:print(f'DRY-RUN: {len(a.tests)} remote shards + pinned derivation; jobs={a.jobs}');return
    artifacts=Path(os.environ.get('BD_GATE_ARTIFACT_ROOT',str(ROOT/'artifacts/gates')))
    artifacts.mkdir(parents=True,exist_ok=True)
    run_dir=Path(tempfile.mkdtemp(prefix='run-',dir=artifacts))
    tasks=[('derive',[str(py),str(derive),'--work',str(wt),'--files',*files])]
    tasks.extend((f'shard-{i}',[str(runner),str(wt),test]) for i,test in enumerate(a.tests,1))
    def job(task):
        label,cmd=task;log=run_dir/(label+'.log');proc=None
        try:
            with log.open('w') as output:
                proc=subprocess.Popen(cmd,cwd=wt,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
                rc=proc.wait()
            return {'job':label,'rc':rc,'log':str(log)}
        except OSError as exc:
            with log.open('a') as output:output.write(str(exc)+'\n')
            return {'job':label,'rc':2,'log':str(log)}
        finally:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    # Executor caps concurrency; each worker blocks on wait(), with one final completion record.
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:results=list(pool.map(job,tasks))
    summary={'jobs':results,'artifact_dir':str(run_dir),'rc':int(any(r['rc'] for r in results))}
    (run_dir/'summary.json').write_text(json.dumps(summary)+'\n');print(json.dumps(summary))
    if summary['rc']:raise Refusal('one or more remote shards/derivation tasks failed; full logs retained')

def command(args):
    if not args:raise Refusal('command name required')
    cmd,*rest=args
    aliases={'next-id':next_id,'dispatch-manifest':dispatch,'launch-role':launch,'retire-seat':retire,'wt-new':wt_new,'gates-parallel':gates}
    if cmd in aliases:return aliases[cmd](rest)
    if cmd not in ('assign-lens','claim','brief','worker-band'):raise Refusal('unknown command')
    if not rest and cmd!='assign-lens':raise Refusal('command arguments required')
    filename={'assign-lens':'bd-assign-lens.sh','claim':'bd-claim-object.sh','brief':'bd-brief-from-register.sh','worker-band':'bd-worker-band.sh'}[cmd]
    if cmd=='claim':
        if len(rest)!=3:raise Refusal('claim needs object lens seat')
        rest=['take',*rest]
    env=dict(os.environ)
    if cmd=='brief':env['BASE']=run(['git','-C',REPO,'rev-parse','--verify','origin/main^{commit}']).strip()
    h=helper('BD_'+cmd.upper().replace('-','_')+'_HELPER',filename)
    result=subprocess.run([str(h),*rest],env=env)
    if result.returncode:raise Refusal(f'{cmd} rc={result.returncode}')

FUNCS={'bd-dispatch-manifest':dispatch,'bd-next-free-id':next_id,'bd-launch-role-demand':launch,'bd-retire-seat':retire,'bd-seat-verify':seat_verify,'bd-wt-new':wt_new,'bd-gates-parallel':gates,'bd-command':command}
def main():
    try:
        mode=sys.argv[1]
        if mode=='hook':
            if len(sys.argv)>3:return 0
            explicit=len(sys.argv)==3 and sys.argv[2]!='-'
            raw=sys.argv[2] if explicit else sys.stdin.read()
            # Existing harness callers explicitly pass a brief file, not hook telemetry.
            if explicit:
                try:is_brief=Path(raw).is_file()
                except OSError:is_brief=False
                if is_brief:rule21(read(raw));return 0
            hook(raw);return 0
        FUNCS[mode](sys.argv[2:]);return 0
    except (Refusal,ValueError,TypeError,KeyError,OSError,subprocess.SubprocessError) as exc:
        print('REFUSED: '+str(exc),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
