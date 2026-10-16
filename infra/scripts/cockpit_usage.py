"""Read the accounting ledger without changing its journal or acquiring a writer."""
import argparse
import calendar
import datetime as dt
import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path
from cockpit_live_claude import read_live_claude


def number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
        return value
    return None


def epoch_us(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            return None
        delta = parsed.astimezone(dt.timezone.utc) - dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
        return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    except (TypeError, ValueError, AttributeError):
        return None


RANGES = {'5m': 300, '30m': 1800, '1h': 3600, '6h': 21600, '12h': 43200,
          '24h': 86400, '7d': 604800, '14d': 1209600, '30d': 2592000,
          '3mo': None, '6mo': None, '1yr': None, 'all': None}
FIELDS = ('input_tokens', 'cache_read', 'fresh_tokens', 'creation_tokens', 'output_tokens')


def range_start(name, end):
    if name not in RANGES:
        raise ValueError('Unsupported history range')
    if name == 'all':
        return None
    seconds = RANGES[name]
    if seconds is not None:
        return end - dt.timedelta(seconds=seconds)
    months = {'3mo': 3, '6mo': 6, '1yr': 12}[name]
    year, month = divmod(end.year * 12 + end.month - 1 - months, 12)
    month += 1
    return end.replace(year=year, month=month, day=min(end.day, calendar.monthrange(year, month)[1]))


def accumulator():
    return {'turns': 0, **{key: 0 for key in FIELDS}}


def add(target, row):
    target['turns'] += 1
    for key in FIELDS:
        target[key] = target[key] + row[key] if target[key] is not None and row[key] is not None else None


def summarize(item):
    context, cached = item['input_tokens'], item['cache_read']
    return {'turns': item['turns'], 'total_ctx': context, 'cache_read': cached,
            'fresh_tokens': item['fresh_tokens'], 'cache_creation_tokens': item['creation_tokens'],
            'out_tokens': item['output_tokens'],
            'cache_efficiency_pct': cached / context * 100 if context and cached is not None else None}


PLATFORMS = ('claude', 'codex', 'agy', 'grok', 'kimi')


def platform_name(provider):
    return {'anthropic': 'claude', 'openai': 'codex', 'gemini': 'agy',
            'xai': 'grok', 'moonshot': 'kimi'}.get(provider, provider if provider in PLATFORMS else 'other')


def measured_window(values, reasons, empty_reason):
    if not values['turns']:
        return {'metrics': None, 'reason': empty_reason, 'unknown_metrics': {}}
    names = {'input_tokens': 'total_ctx', 'creation_tokens': 'cache_creation_tokens', 'output_tokens': 'out_tokens'}
    return {'metrics': summarize(values), 'reason': None,
            'unknown_metrics': {names.get(key, key): value for key, value in reasons.items()}}


def strict_measurement(provider, row, proof):
    values, reasons = dict(row), {}
    for key in FIELDS:
        if values[key] is None:
            reasons[key] = 'A retained response is missing a valid measured value for this metric'
        elif values[key] == 0 and (key in ('cache_read', 'creation_tokens') or
                                  (provider == 'grok' and key == 'input_tokens')) and proof.get(key) is not True:
            values[key] = None
            reasons[key] = 'Normalized zero has no retained raw-field provenance; an omitted field cannot establish measured zero'
    if provider in ('claude', 'kimi') and (values['cache_read'] is None or values['creation_tokens'] is None):
        values['input_tokens'] = None
        reasons['input_tokens'] = 'Normalized total input includes cache components whose measured values are unavailable'
    values['fresh_tokens'] = values['input_tokens'] - values['cache_read'] if values['input_tokens'] is not None and values['cache_read'] is not None else None
    if values['fresh_tokens'] is None:
        reasons['fresh_tokens'] = 'Measured input and cache-read values are both required'
    return values, reasons


def usage_rows(connection, query, live):
    for row in connection.execute(query):
        if row[-1] == 'archives' and (row[0], row[1]) in live:
            continue
        yield row
    for (provider, response_id), row in live.items():
        if row['quarantined'] or connection.execute('SELECT 1 FROM main.usage_responses WHERE provider=? AND response_id=?', (provider, response_id)).fetchone():
            continue
        yield provider, response_id, row['timestamp'], row['model'], json.dumps(row['usage']), 'claude-live'


def read_usage(filename, hours=6, until=None, range_name=None, history_filename=None, live_roots=None, live_parser=None):
    end = dt.datetime.fromisoformat(until.replace('Z', '+00:00')) if until else dt.datetime.now(dt.timezone.utc)
    if end.tzinfo is None:
        raise ValueError('History end must include a timezone')
    end = end.astimezone(dt.timezone.utc)
    start = range_start(range_name, end) if range_name else end - dt.timedelta(hours=hours)
    start_us, end_us = epoch_us(start.isoformat()) if start else None, epoch_us(end.isoformat())
    sums, models, buckets, platform_models = accumulator(), {}, {}, {}
    current_start = end - dt.timedelta(minutes=5)
    current_start_us = epoch_us(current_start.isoformat())
    provenance = {}
    live_options = {'until': end}
    if live_roots is not None:
        live_options['roots'] = live_roots
    if live_parser is not None:
        live_options['parser_path'] = live_parser
    live, live_receipt = read_live_claude(**live_options)
    first_at, last_at, observed_at = None, None, None
    first_us, last_us, observed_us = None, None, None
    source_counts, backfill = {}, None
    widths = {'5m': 10, '30m': 60, '1h': 60, '6h': 300, '12h': 600, '24h': 900,
              '7d': 3600, '14d': 7200, '30d': 14400, '3mo': 86400, '6mo': 86400, '1yr': 172800}
    bucket_seconds = widths.get(range_name, 86400 if range_name == 'all' else 3600)
    with closing(sqlite3.connect(Path(filename).resolve().as_uri() + '?mode=ro', uri=True, timeout=1.0)) as connection:
        # One pass; never join occurrences or write indexes/checkpoints to a fleet ledger.
        query = "SELECT provider, response_id, timestamp, model, usage, 'ledger' FROM main.usage_responses WHERE quarantined = 0 AND response_id NOT LIKE 'synth%' AND COALESCE(model, '') != '<synthetic>'"
        if history_filename and Path(history_filename).is_file():
            connection.execute('ATTACH DATABASE ? AS history', (Path(history_filename).resolve().as_uri() + '?mode=ro',))
            query += """ UNION ALL SELECT h.provider, h.response_id, h.timestamp, h.model, h.usage, 'archives' FROM history.usage_responses h
              WHERE h.quarantined = 0 AND h.response_id NOT LIKE 'synth%' AND COALESCE(h.model, '') != '<synthetic>'
              AND NOT EXISTS (SELECT 1 FROM main.usage_responses m WHERE m.provider = h.provider AND m.response_id = h.response_id)"""
            if connection.execute("SELECT 1 FROM history.sqlite_master WHERE type='table' AND name='history_metadata'").fetchone():
                metadata = connection.execute("SELECT value FROM history.history_metadata WHERE key='coverage'").fetchone()
                backfill = json.loads(metadata[0]) if metadata else None
            if connection.execute("SELECT 1 FROM history.sqlite_master WHERE type='table' AND name='metric_provenance'").fetchone():
                for provider, response_id, fields in connection.execute('SELECT provider, response_id, fields FROM history.metric_provenance'):
                    try:
                        flags = json.loads(fields)
                        if isinstance(flags, dict):
                            provenance[(provider, response_id)] = flags
                    except (ValueError, TypeError):
                        continue
        elif history_filename:
            backfill = {'reason': 'Fleet archive backfill unavailable'}
        for provider, response_id, timestamp, model, payload, source in usage_rows(connection, query, live):
            stamp = epoch_us(timestamp)
            if stamp is None:
                continue
            if observed_us is None or stamp > observed_us:
                observed_at, observed_us = timestamp, stamp
            if stamp >= end_us:
                continue
            if first_us is None or stamp < first_us:
                first_at, first_us = timestamp, stamp
            if last_us is None or stamp > last_us:
                last_at, last_us = timestamp, stamp
            source_counts[source] = source_counts.get(source, 0) + 1
            identity = (provider or 'UNKNOWN', model or 'UNKNOWN')
            item = platform_models.setdefault(identity, {'current': accumulator(), 'history': accumulator(),
                'current_reasons': {}, 'history_reasons': {}, 'first_at': timestamp, 'last_at': timestamp,
                'first_us': stamp, 'last_us': stamp})
            if stamp < item['first_us']:
                item['first_at'], item['first_us'] = timestamp, stamp
            if stamp > item['last_us']:
                item['last_at'], item['last_us'] = timestamp, stamp
            history_eligible = start_us is None or stamp >= start_us
            current_eligible = stamp >= current_start_us and platform_name(provider) != 'grok'
            if not history_eligible and not current_eligible:
                continue
            try:
                usage = json.loads(payload)
                if not isinstance(usage, dict):
                    usage = {}
            except (ValueError, TypeError):
                usage = {}
            input_tokens = number(usage.get('input_tokens'))
            cache_values = [number(usage.get(key)) for key in ('cache_read_input_tokens', 'cached_input_tokens') if key in usage]
            cache = max(cache_values) if cache_values and all(value is not None for value in cache_values) else None
            if input_tokens is not None and cache is not None and cache > input_tokens:
                cache = None
            creation_values = [number(usage.get(key)) for key in ('cache_creation_input_tokens', 'cache_write_input_tokens') if key in usage]
            creation = max(creation_values) if creation_values and all(value is not None for value in creation_values) else None
            fresh = input_tokens - cache if input_tokens is not None and cache is not None else None
            if creation is not None and fresh is not None and creation > fresh:
                creation = None
            row = {'input_tokens': input_tokens, 'cache_read': cache, 'fresh_tokens': fresh,
                   'creation_tokens': creation, 'output_tokens': number(usage.get('output_tokens'))}
            proof = live[(provider, response_id)]['metric_provenance'] if source == 'claude-live' else provenance.get((provider, response_id), {})
            strict, reasons = strict_measurement(platform_name(provider), row, proof)
            if stamp >= current_start_us and platform_name(provider) != 'grok':
                add(item['current'], strict)
                item['current_reasons'].update(reasons)
            if start_us is not None and stamp < start_us:
                continue
            add(item['history'], strict)
            item['history_reasons'].update(reasons)
            add(sums, row)
            add(models.setdefault(identity, accumulator()), row)
            # All can span years: coarsen existing bins without inventing samples.
            bucket = stamp // (bucket_seconds * 1_000_000) * bucket_seconds
            add(buckets.setdefault(bucket, accumulator()), row)
            while len(buckets) > 400:
                bucket_seconds *= 2
                coarse = {}
                for previous, values in buckets.items():
                    target = coarse.setdefault(previous // bucket_seconds * bucket_seconds, accumulator())
                    target['turns'] += values['turns']
                    for key in FIELDS:
                        target[key] = target[key] + values[key] if target[key] is not None and values[key] is not None else None
                buckets = coarse
    if start is None:
        start = dt.datetime.fromisoformat(first_at.replace('Z', '+00:00')) if first_at else end
    platform_rows = []
    for (provider, model), values in sorted(platform_models.items()):
        platform = platform_name(provider)
        platform_rows.append({'platform': platform, 'provider': provider, 'model': None if model == 'UNKNOWN' else model,
            'coverage': {'first_at': values['first_at'], 'last_at': values['last_at']},
            'current': measured_window(values['current'], values['current_reasons'],
                'History only: Grok retired 2026-09-28 (O1468)' if platform == 'grok' else
                'No verified responses retained for this model in the last 5m; zero usage is unverified'),
            'history': measured_window(values['history'], values['history_reasons'],
                'No verified responses retained for this model in the selected range; zero usage is unverified')})
    for platform in PLATFORMS:
        if any(row['platform'] == platform for row in platform_rows):
            continue
        reason = 'AGY archive usage cannot be decoded into verified model-tagged responses; synthetic records are excluded' if platform == 'agy' else 'No verified model-tagged responses retained for this platform'
        platform_rows.append({'platform': platform, 'provider': platform, 'model': None,
            'coverage': {'first_at': None, 'last_at': None},
            'current': {'metrics': None, 'reason': 'History only: Grok retired 2026-09-28 (O1468)' if platform == 'grok' else reason, 'unknown_metrics': {}},
            'history': {'metrics': None, 'reason': reason, 'unknown_metrics': {}}})
    return {'source': 'live', 'range': range_name or f'{hours}h', 'observed_at': observed_at,
            'since': start.isoformat(), 'until': end.isoformat(), 'window_hours': (end - start).total_seconds() / 3600,
            'bucket_seconds': bucket_seconds,
            'coverage': {'first_at': first_at, 'last_at': last_at, 'source_counts': source_counts, 'backfill': backfill, 'live_claude': live_receipt,
                         'partial_window': start_us is not None and (first_us is None or first_us > start_us)},
            'total_responses': sums['turns'], 'totals': summarize(sums),
            'breakdown': [{'key': model, 'provider': provider, **summarize(values)} for (provider, model), values in sorted(models.items())],
            'current_window': {'since': current_start.isoformat(), 'until': end.isoformat(), 'seconds': 300},
            'platform_models': platform_rows,
            'series': [{'hour': dt.datetime.fromtimestamp(bucket, dt.timezone.utc).isoformat(), **summarize(values)}
                       for bucket, values in sorted(buckets.items())]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--hours', type=float, default=6)
    parser.add_argument('--range', choices=RANGES)
    parser.add_argument('--history-database')
    args = parser.parse_args()
    try:
        print(json.dumps(read_usage(args.database, args.hours, range_name=args.range, history_filename=args.history_database), allow_nan=False))
    except (OSError, sqlite3.Error, ValueError):
        print(json.dumps({'source': 'unknown', 'reason': 'Accounting ledger unavailable', 'total_responses': None,
                          'breakdown': [], 'series': [], 'totals': None}))
