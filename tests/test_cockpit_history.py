import gzip
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('cockpit_history', Path(__file__).parents[1] / 'infra/scripts/cockpit_history.py')
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


def artifact(tmp_path, name, rows):
    path = tmp_path / name
    with gzip.open(path, 'wt') as stream:
        for provider, response, timestamp, model, value in rows:
            stream.write(json.dumps({'provider': provider, 'response_id': response, 'timestamp': timestamp,
                                     'model': model, 'usage': value, 'source_host': 'verified-host'}) + '\n')
    return path


def test_clones_streaming_and_conflicts_use_real_provider_identity(tmp_path):
    first = {'input_tokens': 100, 'cached_input_tokens': 40, 'output_tokens': 10}
    last = {**first, 'output_tokens': 20}
    conflict = {**first, 'input_tokens': 200}
    records = [('claude', 'same-id', '2026-07-25T01:00:00Z', 'known', first),
               ('codex', 'same-id', '2026-07-25T01:00:00Z', 'known', first),
               ('claude', 'conflict', '2026-07-25T01:00:00Z', 'known', first)]
    a = artifact(tmp_path, 'a.gz', records)
    b = artifact(tmp_path, 'b.gz', [records[0], ('claude', 'same-id', '2026-07-25T01:01:00Z', 'known', last),
                                  ('claude', 'conflict', '2026-07-25T01:00:00Z', 'known', conflict)])
    output = tmp_path / 'owned.sqlite'
    result = history.merge_history([a, b], output, {'inspected_hosts': 2})
    assert result['responses'] == 2, 'CLONES_AND_STREAMING_COUNT_ONCE_PER_PROVIDER'
    assert result['conflicts'] == 1, 'CONFLICT_IS_EXCLUDED_NOT_CAUGHT_AS_VALID'
    with sqlite3.connect(output.as_uri() + '?mode=ro', uri=True) as db:
        stamp, payload = db.execute("SELECT timestamp,usage FROM usage_responses WHERE provider='claude' AND response_id='same-id'").fetchone()
        assert stamp == '2026-07-25T01:00:00+00:00'
        assert json.loads(payload)['output_tokens'] == 20
    with pytest.raises(FileExistsError):
        history.merge_history([a], output, {})


def test_invalid_archive_numeric_data_is_rejected(tmp_path):
    a = artifact(tmp_path, 'invalid.gz', [('codex', 'real-id', '2026-07-25T01:00:00Z', 'known', {'input_tokens': -1})])
    with pytest.raises(ValueError, match='nonnegative'):
        history.merge_history([a], tmp_path / 'invalid.sqlite', {})
