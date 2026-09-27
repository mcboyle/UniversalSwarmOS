#!/usr/bin/env python3
"""Fleet validation. Helpers are captured; stdout is reserved for MCP JSON-RPC."""
from __future__ import annotations
import contextlib
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Optional

logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
with contextlib.redirect_stdout(sys.stderr):
    from mcp.server.fastmcp import FastMCP

HOME = Path(os.environ.get('BD_FLEET_HOME', '/home/mboyle'))
PERSIST = Path(os.environ.get('BD_PERSIST', str(HOME / 'bd-persist')))
HARNESS = Path(os.environ.get('BD_HARNESS', str(PERSIST / 'harness')))
REPO = Path(os.environ.get('BD_REPO', str(HOME / 'BulkDownloader')))
RECENT_SAY_CACHE = Path(os.environ.get('BD_SAY_CACHE', str(Path(__file__).parent / 'state/say-recent.json')))
_default_schema = HOME / '.gemini/antigravity-cli/mcp'
if not _default_schema.is_dir():
    _default_schema = Path('/home/mboyle/.gemini/antigravity-cli/mcp')
SCHEMA_DIR = Path(os.environ.get('BD_MCP_SCHEMA_DIR', str(_default_schema)))
mcp = FastMCP('bd-fleet')

def sort_keys_recursive(val: Any) -> Any:
    """Recursively sort dictionary keys for deterministic canonicalization."""
    if isinstance(val, dict):
        return {k: sort_keys_recursive(v) for k, v in sorted(val.items())}
    if isinstance(val, list):
        return [sort_keys_recursive(x) for x in val]
    return val

def serialize_tools_canonical(tools: list | None = None) -> str:
    """Canonicalize and serialize tool schemas with sorted keys and alphabetical ordering."""
    if tools is None:
        raw_tools = mcp._tool_manager.list_tools()
        tools_data = []
        for t in raw_tools:
            item = {
                "name": t.name,
                "description": t.description or "",
                "inputSchema": t.parameters if isinstance(t.parameters, dict) else {},
            }
            if hasattr(t, "output_schema") and t.output_schema:
                item["outputSchema"] = t.output_schema
            tools_data.append(item)
    else:
        tools_data = tools

    sorted_tools = sorted([sort_keys_recursive(t) for t in tools_data], key=lambda x: x.get("name", ""))
    return json.dumps(sorted_tools, sort_keys=True, separators=(',', ':'), ensure_ascii=True)

def _apply_mcp_canonicalization(mcp_server: FastMCP):
    orig_list = mcp_server._tool_manager.list_tools
    def sorted_list():
        items = orig_list()
        for t in items:
            if hasattr(t, "parameters") and isinstance(t.parameters, dict):
                t.parameters = sort_keys_recursive(t.parameters)
            if hasattr(t, "output_schema") and isinstance(t.output_schema, dict):
                t.output_schema = sort_keys_recursive(t.output_schema)
        return sorted(items, key=lambda t: t.name)
    mcp_server._tool_manager.list_tools = sorted_list

    if hasattr(mcp_server, "_mcp_server") and hasattr(mcp_server._mcp_server, "request_handlers"):
        import mcp.types as types
        orig_handler = mcp_server._mcp_server.request_handlers.get(types.ListToolsRequest)
        if orig_handler:
            async def sorted_list_tools_handler(req: types.ListToolsRequest):
                result = await orig_handler(req)
                if hasattr(result, "root") and hasattr(result.root, "tools"):
                    result.root.tools.sort(key=lambda t: t.name)
                    for t in result.root.tools:
                        if hasattr(t, "inputSchema") and isinstance(t.inputSchema, dict):
                            t.inputSchema = sort_keys_recursive(t.inputSchema)
                return result
            mcp_server._mcp_server.request_handlers[types.ListToolsRequest] = sorted_list_tools_handler

    import mcp.types as types
    def deterministic_model_dump_json(self, *args, **kwargs):
        d = self.model_dump(by_alias=True, exclude_none=True)
        return json.dumps(sort_keys_recursive(d), sort_keys=True, separators=(',', ':'), ensure_ascii=True)

    types.JSONRPCResponse.model_dump_json = deterministic_model_dump_json
    types.JSONRPCNotification.model_dump_json = deterministic_model_dump_json

_apply_mcp_canonicalization(mcp)


def _run_cmd(cmd, timeout=30.0):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')

def _name(value, field):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise ValueError(f'invalid {field}')
    if value == 'bd-capture-test2':
        raise ValueError('operator-owned target: Rule 21')
    return value

def _git(*args):
    p = _run_cmd(['git', '-C', str(REPO), *args])
    if p.returncode:
        raise ValueError(f'COULD NOT LOOK: git {args[0]} rc={p.returncode}')
    return p.stdout.strip()

def _repo_path(path):
    if not path or Path(path).is_absolute() or '..' in Path(path).parts:
        raise ValueError(f'invalid repository path: {path}')
    return path

@mcp.tool()
def premise_verify(brief_or_row: str, check_symbols: Optional[list[str]] = None,
                   check_tests: Optional[list[str]] = None, check_cut_dir: Optional[str] = None) -> dict:
    """Check BASE, OWNS, WIRING and supplied tests/symbols against local origin/main; unknown refuses."""
    result = dict(target=brief_or_row, verdict='REFUTE', violations=[], symbols={}, tests={}, landed_check=None)
    errors = result['violations']
    try:
        target = Path(brief_or_row)
        if not target.is_file():
            candidates = [HOME/'bd-codex-briefs'/f'{prefix}{brief_or_row}.md' for prefix in ('brief-', 'brief-row', 'ROW')]
            target = next((p for p in candidates if p.is_file()), target)
        if not target.is_file():
            raise ValueError('brief_missing')
        content = target.read_text()
        result['brief_path'] = str(target)
        fields = {}
        for key, value in re.findall(r'^([A-Z][A-Z_-]*):\s*(.+)$', content, re.M):
            if key in fields:
                raise ValueError(f'duplicate brief header: {key}')
            fields[key] = value.strip()
        is_harness = fields.get('KIND', '').strip().lower() == 'harness'
        required = ('BASE', 'OWNS') if is_harness else ('BASE', 'OWNS', 'WIRING')
        for key in required:
            if not fields.get(key):
                raise ValueError(f'brief_missing_{key}')
        if is_harness:
            m_sha = re.search(r'\b([0-9a-f]{64})\b', fields['BASE'])
            if not m_sha:
                raise ValueError('stale_or_unknown_BASE')
            expected_sha = m_sha.group(1).lower()
            file_part = fields['BASE'][:m_sha.start()].strip()
            file_part = re.sub(r'\bsha256\b', '', file_part).strip()
            if not file_part:
                raise ValueError('stale_or_unknown_BASE')
            base_p = Path(file_part)
            if not base_p.is_file():
                for candidate in (PERSIST / file_part, HOME / file_part, REPO / file_part):
                    if candidate.is_file():
                        base_p = candidate
                        break
            if not base_p.is_file():
                raise ValueError('stale_or_unknown_BASE')
            if hashlib.sha256(base_p.read_bytes()).hexdigest() != expected_sha:
                raise ValueError('stale_or_unknown_BASE')
        else:
            main = _git('rev-parse', '--verify', 'origin/main^{commit}')
            base = re.search(r'\b[0-9a-f]{7,40}\b', fields['BASE'])
            if not base or _git('rev-parse', '--verify', base.group()+'^{commit}') != main:
                raise ValueError('stale_or_unknown_BASE')
        if is_harness:
            for owned in fields['OWNS'].split(';'):
                path = re.sub(r'\s*\([^)]*\).*$', '', owned).strip()
                if not path:
                    path = owned.split()[0].strip()
                path = path.rstrip('/')
                p = Path(path)
                target = p if p.is_absolute() else (PERSIST / path)
                if not target.exists() and not (HOME / path).exists() and not (REPO / path).exists():
                    if not target.parent.exists() and not (HOME / path).parent.exists() and not (REPO / path).parent.exists():
                        errors.append(f'OWNS absent: {path}')
            if fields.get('WIRING'):
                for path in fields['WIRING'].split(';'):
                    w = path.strip()
                    if not w: continue
                    p_w = Path(w)
                    if not (p_w.is_absolute() and p_w.exists()):
                        if not (PERSIST / w).exists() and not (HOME / w).exists() and not (REPO / w).exists():
                            p_git = _run_cmd(['git','-C',str(REPO),'cat-file','-e',f'origin/main:{_repo_path(w)}'])
                            if p_git.returncode != 0:
                                errors.append(f'WIRING absent: {w}')
        else:
            def exists(path):
                p = _run_cmd(['git','-C',str(REPO),'cat-file','-e',f'origin/main:{_repo_path(path)}'])
                return p.returncode == 0
            for owned in fields['OWNS'].split(';'):
                path = owned.strip(); new = path.endswith('(new)'); path = path.removesuffix('(new)').strip()
                if new:
                    parent = str(Path(path).parent)
                    if parent != '.' and not exists(parent): errors.append(f'OWNS parent absent: {path}')
                    if exists(path): errors.append(f'OWNS new path already exists: {path}')
                elif not exists(path): errors.append(f'OWNS absent: {path}')
            for path in fields['WIRING'].split(';'):
                if not exists(path.strip()): errors.append(f'WIRING absent: {path.strip()}')
        # A size of an arbitrary file does not verify a latency/percentage premise.
        if re.search(r'\d+\s*(?:(?:KB|MB|GB|ms)\b|%)|p\d\d\b|\bn\s*=\s*\d+', fields.get('EVIDENCE',''), re.I):
            errors.append('COULD NOT LOOK: quantitative EVIDENCE requires a domain verifier')
        row = fields.get('ROW')
        if row:
            if is_harness:
                m_h = re.fullmatch(r'H?(\d+)', row, re.I)
                if not m_h:
                    errors.append('invalid ROW')
                else:
                    h_id = f'H{m_h.group(1)}'
                    backlog_p = PERSIST / 'HARNESS_BACKLOG.md'
                    if backlog_p.is_file():
                        # HARNESS_BACKLOG.md declares a row EITHER as a list item (`- H627 ...`)
                        # OR as a section heading (`## H633 -- ...`); a row may carry both.
                        # Requiring exactly one list-item match refused 129 of 373 real ids.
                        decl = re.compile(rf'^(?:[-*]\s*|#+\s*){h_id}\b')
                        h_rows = [x for x in backlog_p.read_text().splitlines() if decl.search(x)]
                        if not h_rows: errors.append('ROW absent from HARNESS_BACKLOG.md')
            else:
                rid = re.fullmatch(r'(?:row)?(\d+[a-z]?)', row)
                if not rid: raise ValueError('invalid ROW')
                register = _git('show','origin/main:project-knowledge/IMPROVEMENT_BACKLOG.md')
                rows = [x.split('|') for x in register.splitlines() if re.match(r'^\|\s*'+rid[1]+r'\s*\|',x)]
                if len(rows)!=1 or rows[0][2].strip()!='OPEN': errors.append('ROW absent, duplicated or not OPEN')
                elif not fields.get('TITLE') or fields['TITLE'] != rows[0][3].strip(): errors.append('ROW TITLE mismatch')
        for symbol in check_symbols or []:
            if not symbol: raise ValueError('empty symbol')
            p = _run_cmd(['git','-C',str(REPO),'grep','-n','-F','-e',symbol,'origin/main','--'])
            count = len(p.stdout.splitlines()) if p.returncode == 0 else 0
            result['symbols'][symbol] = {'found': count>0, 'count':count, 'rc':p.returncode}
            if not count: errors.append(f'symbol absent or unavailable: {symbol}')
        for path in check_tests or []:
            found = exists(path)
            result['tests'][path] = {'exists':found}
            if not found: errors.append(f'test absent: {path}')
        if check_cut_dir:
            landed = result['landed_check'] = landed_by_content(check_cut_dir)
            if landed['state']=='UNKNOWN': errors.append('landed check UNKNOWN')
            elif landed['already_landed']: errors.append('already landed')
        if not errors: result['verdict']='PROCEED'
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        errors.append(str(exc))
    return result

@mcp.tool()
def landed_by_content(cut_dir: str) -> dict:
    """Wrap the harness TSV measurement, preserving OPEN and UNKNOWN independently of percentage."""
    result = {'cut':cut_dir,'state':'UNKNOWN','already_landed':False}
    try:
        target = Path(cut_dir).resolve()
        script = HARNESS/'bd-landed-by-content.py'
        if not target.is_dir() or not script.is_file(): raise ValueError('cut_or_helper_missing')
        p = _run_cmd([sys.executable,str(script),str(target)])
        if p.returncode: raise ValueError(f'landed_helper_rc={p.returncode}')
        lines = p.stdout.strip().splitlines()
        if len(lines)!=1: raise ValueError('invalid landed output line count')
        name,total,found,pct,state = lines[0].split('\t')
        total,found,pct = int(total),int(found),int(pct)
        if not 0<=found<=total or not 0<=pct<=100 or pct != (found*100//total if total else 0):
            raise ValueError('invalid landed counts')
        if state not in ('LANDED','OPEN') or (state=='LANDED' and (not total or pct<95)):
            raise ValueError('invalid landed state')
        result.update(cut=name,added_lines=total,present_on_main=found,percent=pct,state=state,already_landed=state=='LANDED')
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        result['error']=str(exc)
    return result

def _targets():
    helper = Path(os.environ.get('BD_ROLE_CLAIM_HELPER', str(HOME/'bd-role-claim.sh')))
    p = _run_cmd(['bash',str(helper),'who-all'],timeout=10)
    if p.returncode: raise ValueError(f'target_registry_unavailable: rc={p.returncode}')
    seats = {line.split('\t')[1] for line in p.stdout.splitlines() if len(line.split('\t'))>=2}
    if not seats: raise ValueError('target_registry_empty')
    return seats

@contextlib.contextmanager
def _cache_transaction(record):
    path = RECENT_SAY_CACHE
    lock = None
    try:
        if record:
            path.parent.mkdir(parents=True,exist_ok=True)
            lock = open(str(path)+'.lock','a')
            until=time.monotonic()+2
            while True:
                try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.monotonic()>=until:raise ValueError('cache_lock_timeout')
                    time.sleep(.02)
        cache = json.loads(path.read_text()) if path.exists() else {}
        if not isinstance(cache,dict): raise ValueError('cache_invalid_schema')
        now=time.time()
        for sender, entries in cache.items():
            if not isinstance(entries,list) or any(not isinstance(e,dict) or not isinstance(e.get('msg'),str) or type(e.get('ts')) not in (int,float) for e in entries):
                raise ValueError('cache_invalid_schema')
        cache={s:[e for e in es if 0<=now-e['ts']<600] for s,es in cache.items()}
        yield cache
        if record:
            fd,tmp=tempfile.mkstemp(prefix=path.name+'.',dir=path.parent)
            try:
                with os.fdopen(fd,'w') as f:json.dump(cache,f);f.flush();os.fsync(f.fileno())
                os.replace(tmp,path)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
    finally:
        if lock is not None:lock.close()

def _say_static(target, message, sender):
    """Everything that needs no cache: names, sender, registry, length. Runs OUTSIDE the cache lock
    (H704: who-all is a subprocess; holding the 2 s lock across it timed out concurrent senders)."""
    result=dict(valid=False,target_requested=target,target_resolved=target,violations=[],strikes=0,
                duplicate_count=0,is_duplicate=False,verdict='REJECT',delivery='NOT_ATTEMPTED')
    errors=result['violations']
    try:
        _name(target,'target')
        sender=sender or os.environ.get('BD_SEAT')
        if not sender and os.environ.get('TMUX'):
            probe=_run_cmd(['tmux','display-message','-p','#S'],timeout=5)
            if probe.returncode==0:sender=probe.stdout.strip()
        sender=(sender or '').strip();_name(sender,'sender')
        if not isinstance(message,str) or not message.strip():raise ValueError('empty_or_invalid_message')
        if target.lower() in ('pm','bd-pm'):
            rows=[x.strip() for x in (PERSIST/'PM-SEAT').read_text().splitlines() if x.strip() and not x.lstrip().startswith('#')]
            if len(rows)!=1:raise ValueError('PM_alias_unknown')
            target=rows[0];_name(target,'resolved target');result['target_resolved']=target
        if target not in _targets():raise ValueError('target_not_claimed')
        has_path=bool(re.search(r'(?:^|\s)(?:/[^\s]+|https?://\S+|[\w./-]+\.(?:md|log|txt|json|tsv))(?=\s|$)',message))
        result.update(char_count=len(message),has_path=has_path)
        if len(message)>30 and not has_path:errors.append('length_exceeded: >30 chars without path')
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        errors.append(str(exc));result['strikes']=max(1,result['strikes'])
        return result,sender,None
    return result,sender,target

def _say_dedupe(result, sender, target, message, cache, pending):
    """Under the cache lock: repeats + strikes; returns the entry to record."""
    errors=result['violations']
    # H704: a duplicate is the same text to the SAME target that was ALLOWED before; a broadcast
    # (same text, other targets) and a refused attempt are not sends.
    history=cache.get(sender,[])+[e for s,e in pending if s==sender]
    repeats=sum(e['msg']==message and e.get('target')==target and not e.get('rejected') for e in history)
    result.update(duplicate_count=repeats,is_duplicate=repeats>0)
    if repeats>=2:errors.append('duplicate_repeat_suppressed')
    result['strikes']=sum(bool(e.get('rejected')) for e in history)+bool(errors) or len(errors)
    return {'msg':message,'target':target,'ts':time.time(),'rejected':bool(errors)}

def _verdict(result):
    result.update(valid=not result['violations'],verdict='REJECT' if result['violations'] else 'ALLOW')
    return result

def say_validate_batch(items, record_send=False):
    """Validate (target, message, sender) sends under one cache transaction. With record_send, refused
    lines are recorded as strikes; allowed lines are recorded only when no line refuses (H704: a
    blocked Bash sends nothing, so its allowed lines must not count against the retry)."""
    prepared=[_say_static(t,m,s)+(m,) for t,m,s in items]
    results=[];pending=[]
    try:
        with _cache_transaction(record_send) as cache:
            for result,sender,target,message in prepared:
                if target is not None:pending.append((sender,_say_dedupe(result,sender,target,message,cache,pending)))
                results.append(_verdict(result))
            if record_send:
                blocked=any(not r['valid'] for r in results)
                for sender,entry in pending:
                    if entry['rejected'] or not blocked:cache.setdefault(sender,[]).append(entry)
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        results=[]
        for target,_message,_sender in items:
            results.append(dict(valid=False,target_requested=target,target_resolved=target,violations=[str(exc)],strikes=1,
                                duplicate_count=0,is_duplicate=False,verdict='REJECT',delivery='NOT_ATTEMPTED'))
    return results

@mcp.tool()
def say_validate(target: str, message: str, sender: Optional[str] = None, record_send: bool = False) -> dict:
    """Validate target and terse content; --record reserves attempts atomically, never proves delivery."""
    return say_validate_batch([(target,message,sender)],record_send)[0]

@mcp.tool()
def role_state_set(role: str, seat: str, text: Optional[str] = None, state: Optional[str] = None) -> dict:
    """Normalize text/state aliases and reject conflicting or empty payloads before the helper call."""
    _name(role,'role');_name(seat,'seat')
    if text is not None and state is not None and text!=state:raise ValueError('conflicting text and state')
    payload=text if text is not None else state
    if not isinstance(payload,str) or not payload.strip():raise ValueError('text or state is required')
    try:
        p=_run_cmd(['bash',str(HARNESS/'bd-role-state.sh'),'set',role,seat,payload],timeout=10)
        return dict(role=role,seat=seat,state=payload,rc=p.returncode,result=(p.stdout+p.stderr).strip())
    except (OSError,subprocess.SubprocessError) as exc:return dict(role=role,rc=2,error=str(exc))

@mcp.tool()
def role_state_get(role: str) -> dict:
    """Read role state through the canonical helper; preserve missing-state return status."""
    _name(role,'role')
    try:
        p=_run_cmd(['bash',str(HARNESS/'bd-role-state.sh'),'get',role],timeout=10)
        return dict(role=role,rc=p.returncode,state=p.stdout.strip(),error=p.stderr.strip())
    except (OSError,subprocess.SubprocessError) as exc:return dict(role=role,rc=2,error=str(exc))

SERVER_CATEGORIES = {
    'vmware-clones': 'infra',
    'bd-bus': 'bus',
    'bd-fleet': 'fleet',
    'bd-fleet-mcp_bd-fleet': 'fleet',
    'bd': 'harness',
    'python-linter': 'linter',
    'type-enforcer': 'typecheck',
    'ratf': 'ast',
    'pg-local': 'database',
    'caveman': 'compression',
    'context-mode': 'context',
    'chrome_devtools': 'browser',
}

def _clean_summary(desc: str) -> str:
    """Generate concise tool summary under ~15 tokens."""
    if not desc:
        return ''
    line = desc.strip().splitlines()[0]
    sentence = line.split('. ')[0].rstrip('.')
    if len(sentence) > 80:
        sentence = sentence[:77] + '...'
    return sentence

def mcp_discover(category: Optional[str] = None, filter_query: Optional[str] = None) -> list[dict]:
    """Return compact list of available MCP tools and concise summaries (~15 tokens per tool)."""
    cat_filter = str(category).lower().strip() if category is not None else None
    q = str(filter_query).lower().strip() if filter_query is not None else None

    schema_base = SCHEMA_DIR
    if not schema_base.is_dir():
        return []

    tools_catalog = []
    seen = set()

    for server_dir in sorted(schema_base.iterdir()):
        if not server_dir.is_dir():
            continue
        server_name = server_dir.name
        # Skip duplicate internal plugin mirror if canonical directory exists
        if server_name == 'bd-fleet-mcp_bd-fleet' and (schema_base / 'bd-fleet').is_dir():
            continue

        default_cat = SERVER_CATEGORIES.get(server_name, 'general')

        for schema_file in sorted(server_dir.glob('*.json')):
            try:
                data = json.loads(schema_file.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue

            tool_name = data.get('name') or schema_file.stem
            dedup_key = (server_name, tool_name)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            tool_desc = data.get('description', '')
            tool_cat = data.get('category') or default_cat
            summary = _clean_summary(tool_desc)

            if cat_filter:
                cat_match = (
                    cat_filter == tool_cat.lower()
                    or cat_filter in tool_cat.lower()
                    or cat_filter == server_name.lower()
                    or cat_filter in server_name.lower()
                )
                if not cat_match:
                    continue

            if q:
                q_match = (
                    q in tool_name.lower()
                    or q in tool_desc.lower()
                    or q in tool_cat.lower()
                    or q in server_name.lower()
                    or q in summary.lower()
                )
                if not q_match:
                    continue

            tools_catalog.append({
                'name': tool_name,
                'server': server_name,
                'category': tool_cat,
                'summary': summary
            })

    return tools_catalog

def mcp_hydrate(tools: list[str], server: Optional[str] = None) -> dict:
    """Load and return full tool schema dictionary for requested tool(s) from schema catalog."""
    if not tools:
        return {}

    if isinstance(tools, str):
        tool_names = [tools]
    elif isinstance(tools, (list, tuple, set)):
        tool_names = [str(t) for t in tools]
    else:
        tool_names = [str(tools)]

    schema_base = SCHEMA_DIR
    if not schema_base.is_dir():
        return {}

    server_filter = str(server).strip() if server is not None else None
    if server_filter and (Path(server_filter).name != server_filter or '..' in server_filter):
        raise ValueError('invalid server name')

    hydrated = {}

    for t_name in tool_names:
        t_clean = t_name.strip()
        if not t_clean or Path(t_clean).name != t_clean or '..' in t_clean:
            continue

        matched_schema = None

        if server_filter:
            target_file = schema_base / server_filter / f"{t_clean}.json"
            if target_file.is_file():
                try:
                    matched_schema = json.loads(target_file.read_text(encoding='utf-8'))
                except (OSError, json.JSONDecodeError):
                    pass
        else:
            for s_dir in sorted(schema_base.iterdir()):
                if not s_dir.is_dir():
                    continue
                target_file = s_dir / f"{t_clean}.json"
                if target_file.is_file():
                    try:
                        matched_schema = json.loads(target_file.read_text(encoding='utf-8'))
                        break
                    except (OSError, json.JSONDecodeError):
                        continue

        if matched_schema is not None:
            hydrated[t_clean] = matched_schema

    return hydrated

if os.environ.get('BD_SEAT') != 'fixture':
    mcp.tool()(mcp_discover)
    mcp.tool()(mcp_hydrate)

if __name__=='__main__':
    if '--canonical-schemas' in sys.argv or '--tools' in sys.argv:
        print(serialize_tools_canonical())
        sys.exit(0)
    if sys.argv[1:]==['--selftest']:
        os.execv(sys.executable,[sys.executable,str(Path(__file__).parent/'tests/checks.py')])
    if len(sys.argv)>1:raise SystemExit('usage: server.py [--selftest]')
    mcp.run(transport='stdio')
