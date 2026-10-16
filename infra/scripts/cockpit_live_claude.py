"""Application-reader draft: current C/D canonical usage; no source writes.

Merge identity priority: ledger (including quarantine), this live map (including
quarantine), frozen archive. Never sum overlapping identity populations.
"""
from __future__ import annotations

import ast
from functools import lru_cache
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import time

DEFAULT_PARSER = '/home/mboyle/bd-persist/harness/bd_cost_accounting.py'
DEFAULT_ROOTS = tuple((tuple(item) for item in json.loads(os.environ['COCKPIT_LIVE_CLAUDE_ROOTS']))) if 'COCKPIT_LIVE_CLAUDE_ROOTS' in os.environ else (('C', '/home/mboyle/.claude-c/projects'), ('D', '/home/mboyle/.claude-d/projects'))
OUTPUT_FIELDS = ('output_tokens', 'reasoning_output_tokens', 'total_tokens')


@lru_cache(maxsize=4)
def _pure_parser(path: str, mtime_ns: int, size: int):
    """Extract the canonical parser, never run its module/CLI/collector body."""
    source = Path(path).read_text()
    functions = {'utc', 'zeros', 'integer', 'normalize', 'parse', 'seed_metadata'}
    body = []
    for node in ast.parse(source, filename=path).body:
        fields = isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == 'FIELDS' for target in node.targets
        )
        if isinstance(node, (ast.Import, ast.ImportFrom)) or fields or (
            isinstance(node, ast.FunctionDef) and node.name in functions
        ):
            body.append(node)
    scope = {'__name__': '_cockpit_canonical_usage_pure'}
    exec(compile(ast.Module(body=body, type_ignores=[]), path, 'exec'), scope)
    missing = functions - scope.keys()
    if missing or 'FIELDS' not in scope:
        raise ValueError('Canonical usage parser is missing required pure functions')
    return scope, hashlib.sha256(source.encode()).hexdigest()


def read_live_claude(roots=DEFAULT_ROOTS, parser_path=DEFAULT_PARSER, until=None):
    """Return (identity->canonical row, receipt), including conflict tombstones.

    Only complete JSONL lines are eligible. Numeric rows never retain prompts,
    arbitrary metadata, timestamps synthesized from filesystem mtime, or tokens
    inferred from activity. `rows[(provider,response_id)]` includes quarantined
    identities so the caller can suppress their frozen archive twins.
    """
    started = time.monotonic()
    receipt = {
        'source': 'claude-live', 'roots': [], 'files': 0, 'bytes': 0,
        'read_errors': 0, 'invalid_records': 0, 'incomplete_lines': 0,
        'synthetic_excluded': 0, 'streamed_merges': 0, 'duplicate_occurrences': 0,
        'responses': 0, 'quarantined': 0, 'outside_cutoff': 0,
    }
    rows = {}
    try:
        path = Path(parser_path)
        stat = path.stat()
        parser, receipt['parser_sha256'] = _pure_parser(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError, SyntaxError):
        receipt.update(status='unavailable', reason='Canonical provider usage parser is unavailable')
        return rows, receipt
    cutoff = parser['utc'](until.isoformat() if isinstance(until, dt.datetime) else until) if until is not None else None
    for pool, root_name in roots:
        root = Path(root_name)
        census = {'pool': pool, 'path': str(root), 'exists': root.is_dir(), 'files': 0, 'read_errors': 0}
        receipt['roots'].append(census)
        if not census['exists']:
            continue
        def walk_error(_error):
            census['read_errors'] += 1
            receipt['read_errors'] += 1
        for directory, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
            dirs[:] = [name for name in dirs if not (Path(directory) / name).is_symlink()]
            for name in names:
                source = Path(directory) / name
                if not name.endswith('.jsonl') or source.is_symlink():
                    continue
                census['files'] += 1
                receipt['files'] += 1
                try:
                    receipt['bytes'] += source.stat().st_size
                    with source.open('rb') as stream:
                        metadata = parser['seed_metadata'](stream, source, 'claude', {})
                        # Metadata seeding consumes the first record; ingestion must reread it.
                        stream.seek(0)
                        for raw in stream:
                            if not raw.endswith(b'\n'):
                                receipt['incomplete_lines'] += 1
                                continue
                            try:
                                record = json.loads(raw)
                                parsed = parser['parse'](record, metadata, 'claude')
                                if parsed is None:
                                    continue
                                response, _thread, stamp, model, usage = parsed
                                if not isinstance(stamp, str) or not stamp:
                                    raise ValueError('No measured timestamp')
                                stamp = parser['utc'](stamp)
                                if not isinstance(response, str) or not response:
                                    raise ValueError('No response identity')
                            except (ValueError, TypeError, AttributeError, OverflowError):
                                receipt['invalid_records'] += 1
                                continue
                            if cutoff is not None and stamp >= cutoff:
                                receipt['outside_cutoff'] += 1
                                continue
                            if response.startswith('synth') or model == '<synthetic>':
                                receipt['synthetic_excluded'] += 1
                                continue
                            envelope = record.get('payload') if isinstance(record.get('payload'), dict) else record
                            message = envelope.get('message') or {}
                            native = message.get('usage', envelope.get('usage')) or {}
                            def measured(field):
                                value = native.get(field)
                                return isinstance(value, int) and not isinstance(value, bool) and value >= 0
                            row = {
                                'provider': 'claude', 'response_id': response,
                                'timestamp': stamp, 'model': model, 'usage': usage,
                                'source': 'claude-live', 'source_pool': pool,
                                'quarantined': False,
                                'metric_provenance': {
                                    'input_tokens': measured('input_tokens'),
                                    'output_tokens': measured('output_tokens'),
                                    'cache_read': measured('cache_read_input_tokens'),
                                    'creation_tokens': measured('cache_creation_input_tokens'),
                                },
                            }
                            key = ('claude', response)
                            previous = rows.get(key)
                            if previous is None:
                                rows[key] = row
                                continue
                            receipt['duplicate_occurrences'] += 1
                            if previous['quarantined']:
                                continue
                            same_model = previous['model'] == model or previous['model'] == 'UNKNOWN' or model == 'UNKNOWN'
                            same_inputs = all(previous['usage'].get(field) == usage.get(field)
                                              for field in parser['FIELDS'] if field not in OUTPUT_FIELDS)
                            if not same_model or not same_inputs:
                                previous['quarantined'] = True
                                continue
                            proof = {field: previous['metric_provenance'].get(field, False) or value
                                     for field, value in row['metric_provenance'].items()}
                            if previous['usage'] != usage:
                                receipt['streamed_merges'] += 1
                                if usage['output_tokens'] > previous['usage']['output_tokens']:
                                    previous['usage'] = usage
                            previous['metric_provenance'] = proof
                            previous['timestamp'] = min(previous['timestamp'], stamp)
                            if previous['model'] == 'UNKNOWN':
                                previous['model'] = model
                except OSError:
                    census['read_errors'] += 1
                    receipt['read_errors'] += 1
    receipt['responses'] = sum(not row['quarantined'] for row in rows.values())
    receipt['quarantined'] = sum(row['quarantined'] for row in rows.values())
    receipt['elapsed_seconds'] = round(time.monotonic() - started, 6)
    receipt['status'] = 'partial' if receipt['read_errors'] else 'observed' if rows else 'empty'
    if not rows:
        receipt['reason'] = ('No readable configured Claude usage roots' if not any(root['exists'] for root in receipt['roots'])
                             else 'No complete eligible numeric response records in configured Claude usage roots')
    return rows, receipt
