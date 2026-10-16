"""Merge sanitized fleet archive usage into a separate, owned history database.

Never opens a fleet accounting ledger or copies transcript text. Runtime readers
deduplicate this archive against the live ledger using (provider, response_id).
"""
import argparse
import datetime as dt
import gzip
import json
import sqlite3
from contextlib import closing
from pathlib import Path

ALLOWED = {'provider', 'response_id', 'timestamp', 'model', 'usage', 'source_host'}
OUTPUT_FIELDS = {'output_tokens', 'reasoning_output_tokens', 'total_tokens'}


def merge_history(artifacts, output, coverage):
    output = Path(output)
    output.touch(exist_ok=False)  # Preserve every earlier artifact, including failed runs.
    stats = {'occurrences': 0, 'duplicates': 0, 'streamed_merges': 0}
    with closing(sqlite3.connect(output)) as db:
        db.execute('CREATE TABLE usage_responses(provider TEXT, response_id TEXT, timestamp TEXT, model TEXT, usage TEXT, quarantined INTEGER, PRIMARY KEY(provider,response_id))')
        db.execute('CREATE TABLE history_metadata(key TEXT PRIMARY KEY, value TEXT)')
        with db:
            for artifact in artifacts:
                with gzip.open(artifact, 'rt', encoding='utf8') as stream:
                    for line in stream:
                        row = json.loads(line)
                        if set(row) != ALLOWED or not all(isinstance(row[key], str) and row[key] for key in ALLOWED - {'usage'}):
                            raise ValueError('Unexpected archive record schema')
                        value = row['usage']
                        if not isinstance(value, dict) or not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in value.values()):
                            raise ValueError('Archive usage must contain nonnegative integer metrics')
                        instant = dt.datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                        if instant.tzinfo is None or row['response_id'].startswith('synth') or row['model'] == '<synthetic>':
                            raise ValueError('Archive identity or timestamp is ineligible')
                        timestamp = instant.astimezone(dt.timezone.utc).isoformat()
                        key = (row['provider'], row['response_id'])
                        previous = db.execute('SELECT timestamp,model,usage,quarantined FROM usage_responses WHERE provider=? AND response_id=?', key).fetchone()
                        stats['occurrences'] += 1
                        if previous is None:
                            db.execute('INSERT INTO usage_responses VALUES(?,?,?,?,?,0)', (*key, timestamp, row['model'], json.dumps(value)))
                            continue
                        stats['duplicates'] += 1
                        old_time, old_model, old_payload, quarantined = previous
                        if quarantined:
                            continue
                        old_value = json.loads(old_payload)
                        compatible_model = old_model == row['model'] or 'UNKNOWN' in (old_model, row['model'])
                        same_input = all(old_value.get(k) == value.get(k) for k in set(old_value) | set(value) if k not in OUTPUT_FIELDS)
                        if not compatible_model or not same_input:
                            db.execute('UPDATE usage_responses SET quarantined=1 WHERE provider=? AND response_id=?', key)
                            continue
                        if old_value != value:
                            if value.get('output_tokens', 0) > old_value.get('output_tokens', 0):
                                old_value = value
                            stats['streamed_merges'] += 1
                        if instant < dt.datetime.fromisoformat(old_time):
                            old_time = timestamp
                        db.execute('UPDATE usage_responses SET timestamp=?,model=?,usage=? WHERE provider=? AND response_id=?',
                                   (old_time, row['model'] if old_model == 'UNKNOWN' else old_model, json.dumps(old_value), *key))
            stats['responses'] = db.execute('SELECT COUNT(*) FROM usage_responses WHERE quarantined=0').fetchone()[0]
            stats['conflicts'] = db.execute('SELECT COUNT(*) FROM usage_responses WHERE quarantined!=0').fetchone()[0]
            db.execute('INSERT INTO history_metadata VALUES(?,?)', ('coverage', json.dumps(coverage)))
            db.execute('INSERT INTO history_metadata VALUES(?,?)', ('merge', json.dumps(stats)))
    return stats


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', nargs='+', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--coverage', required=True)
    args = parser.parse_args()
    print(json.dumps(merge_history(args.input, args.output, json.loads(Path(args.coverage).read_text()))))
