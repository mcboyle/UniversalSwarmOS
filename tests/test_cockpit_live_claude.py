"""Offhost controls for reader draft, not source collector installation."""
import json
from pathlib import Path
import os
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / 'infra/scripts'))
from cockpit_live_claude import read_live_claude
from cockpit_usage import read_usage
import sqlite3

PARSER = os.environ.get('BD_TEST_CANONICAL_PARSER', str(Path(__file__).parents[1] / 'Configs_and_Hooks/harness/bd_cost_accounting.py'))


def assistant(identity='probe-one', model='claude-opus-5-5', output=3, fresh=2,
              cache=5, creation=7, stamp='2026-10-01T22:00:00Z'):
    return {'type': 'assistant', 'timestamp': stamp, 'sessionId': 'probe-thread',
            'message': {'id': identity, 'model': model, 'usage': {
                'input_tokens': fresh, 'output_tokens': output,
                'cache_read_input_tokens': cache, 'cache_creation_input_tokens': creation}}}


def write(path, records, trailing=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row)+'\n' for row in records) + (trailing or ''))


def test_fresh_complete_append_changes_current_without_archive_write(tmp_path):
    path = tmp_path/'C'/'project'/'session.jsonl'
    write(path, [assistant('probe-old')])
    before, _ = read_live_claude([('C', str(tmp_path/'C'))], PARSER)
    with path.open('a') as stream:
        stream.write(json.dumps(assistant('probe-new', stamp='2026-10-01T22:01:00.000001Z'))+'\n')
    after, receipt = read_live_claude([('C', str(tmp_path/'C'))], PARSER)
    assert ('claude', 'probe-new') not in before
    assert ('claude', 'probe-new') in after
    assert receipt['responses'] == 2
    assert after[('claude', 'probe-new')]['timestamp'].endswith('000001Z')


def test_clone_duplicate_and_streamed_output_max(tmp_path):
    records = [assistant(output=3), assistant(output=8), assistant(output=4)]
    write(tmp_path/'C'/'p'/'a.jsonl', records)
    write(tmp_path/'D'/'p'/'b.jsonl', [assistant(output=8)])
    rows, receipt = read_live_claude([('C',str(tmp_path/'C')),('D',str(tmp_path/'D'))],PARSER)
    assert receipt['responses'] == 1
    assert receipt['duplicate_occurrences'] == 3
    assert rows[('claude','probe-one')]['usage']['output_tokens'] == 8
    assert rows[('claude','probe-one')]['usage']['input_tokens'] == 14


def test_contradictory_inputs_retains_tombstone_to_suppress_archive(tmp_path):
    write(tmp_path/'C'/'a.jsonl',[assistant(),assistant(fresh=9),assistant()])
    rows,receipt=read_live_claude([('C',str(tmp_path/'C'))],PARSER)
    assert receipt['responses'] == 0 and receipt['quarantined'] == 1
    assert ('claude','probe-one') in rows
    assert rows[('claude','probe-one')]['quarantined']


def test_model_conflict_quarantines(tmp_path):
    write(tmp_path/'C'/'a.jsonl',[assistant(),assistant(model='claude-sonnet-5-5')])
    rows,receipt=read_live_claude([('C',str(tmp_path/'C'))],PARSER)
    assert rows[('claude','probe-one')]['quarantined']


def test_missing_native_zero_distinct_from_explicit_zero(tmp_path):
    missing=assistant('probe-missing',cache=0,creation=0)
    del missing['message']['usage']['cache_read_input_tokens']
    del missing['message']['usage']['cache_creation_input_tokens']
    write(tmp_path/'C'/'a.jsonl',[missing,assistant('probe-zero',cache=0,creation=0)])
    rows,_=read_live_claude([('C',str(tmp_path/'C'))],PARSER)
    assert not rows[('claude','probe-missing')]['metric_provenance']['cache_read']
    assert not rows[('claude','probe-missing')]['metric_provenance']['creation_tokens']
    assert rows[('claude','probe-zero')]['metric_provenance']['cache_read']
    assert rows[('claude','probe-zero')]['metric_provenance']['creation_tokens']


def test_partial_line_synthetic_and_malformed_records_excluded(tmp_path):
    write(tmp_path/'C'/'a.jsonl',[assistant(),assistant('synth-control'),assistant('probe-fake','<synthetic>')],
          json.dumps(assistant('probe-incomplete')))
    with (tmp_path/'C'/'a.jsonl').open('a') as stream:
        stream.write('\ninvalid JSON\n')
    # The preceding complete-looking line became complete after newline: test separate tail.
    with (tmp_path/'C'/'a.jsonl').open('a') as stream:
        stream.write(json.dumps(assistant('probe-still-incomplete')))
    rows,receipt=read_live_claude([('C',str(tmp_path/'C'))],PARSER)
    assert ('claude','probe-still-incomplete') not in rows
    assert receipt['synthetic_excluded'] == 2
    assert receipt['invalid_records'] == 1
    assert receipt['incomplete_lines'] == 1


def test_parser_top_level_mutations_are_not_executed(tmp_path):
    snapshot=tmp_path/'parser.py'
    snapshot.write_text(Path(PARSER).read_text()+"\nraise RuntimeError('collector module body executed')\n")
    write(tmp_path/'C'/'a.jsonl',[assistant()])
    rows,receipt=read_live_claude([('C',str(tmp_path/'C'))],str(snapshot))
    assert receipt['responses'] == 1
    assert rows[('claude','probe-one')]['model'] == 'claude-opus-5-5'


def test_read_only_source_bytes_and_missing_parser_reason(tmp_path):
    source=tmp_path/'C'/'a.jsonl';write(source,[assistant()])
    before=source.read_bytes();source.chmod(0o444)
    rows,receipt=read_live_claude([('C',str(tmp_path/'C'))],PARSER)
    assert receipt['responses'] == 1 and source.read_bytes() == before
    missing_rows,missing_receipt=read_live_claude([('C',str(tmp_path/'C'))],str(tmp_path/'absent.py'))
    assert missing_rows == {} and missing_receipt['status'] == 'unavailable'
    assert 'parser is unavailable' in missing_receipt['reason']


def test_missing_timestamp_and_invalid_native_metrics_rejected(tmp_path):
    missing_time=assistant('probe-missing-time');del missing_time['timestamp']
    bool_metric=assistant('probe-bool');bool_metric['message']['usage']['cache_read_input_tokens']=True
    null_metric=assistant('probe-null');null_metric['message']['usage']['cache_creation_input_tokens']=None
    write(tmp_path/'C'/'a.jsonl',[missing_time,bool_metric,null_metric,assistant('probe-good')])
    rows,receipt=read_live_claude([('C',str(tmp_path/'C'))],PARSER)
    assert receipt['responses'] == 1 and receipt['invalid_records'] == 3
    assert list(rows) == [('claude','probe-good')]


def test_empty_root_and_missing_root_have_different_evidence(tmp_path):
    absent,missing=read_live_claude([('C',str(tmp_path/'absent'))],PARSER)
    (tmp_path/'C').mkdir()
    empty,found=read_live_claude([('C',str(tmp_path/'C'))],PARSER)
    assert absent == empty == {}
    assert not missing['roots'][0]['exists'] and found['roots'][0]['exists']
    assert missing['reason'] != found['reason']


def test_wrapped_payload_native_zero_keeps_provenance(tmp_path):
    direct=assistant('probe-wrapped',cache=0,creation=0)
    wrapped={'type':direct['type'],'timestamp':direct['timestamp'],'payload':{
        'sessionId':direct['sessionId'],'message':direct['message']}}
    write(tmp_path/'C'/'a.jsonl',[wrapped])
    rows,receipt=read_live_claude([('C',str(tmp_path/'C'))],PARSER)
    assert receipt['responses'] == 1
    row=rows[('claude','probe-wrapped')]
    assert row['usage']['cache_read_input_tokens'] == row['usage']['cache_creation_input_tokens'] == 0
    assert row['metric_provenance']['cache_read'] is True
    assert row['metric_provenance']['creation_tokens'] is True


def test_exact_until_cutoff_applies_before_output_growth_merge(tmp_path):
    write(tmp_path/'C'/'a.jsonl',[
        assistant('probe-growth',output=3,stamp='2026-10-01T22:00:00Z'),
        assistant('probe-growth',output=9,stamp='2026-10-01T22:01:00Z'),
        assistant('probe-boundary',stamp='2026-10-01T22:00:00.000001Z')])
    rows,receipt=read_live_claude([('C',str(tmp_path/'C'))],PARSER,until='2026-10-01T22:00:00.000001Z')
    assert receipt['responses'] == 1 and receipt['outside_cutoff'] == 2
    assert rows[('claude','probe-growth')]['usage']['output_tokens'] == 3
    assert ('claude','probe-boundary') not in rows


def ledger(path, rows):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE usage_responses(provider TEXT,response_id TEXT,timestamp TEXT,model TEXT,usage TEXT,quarantined INTEGER,PRIMARY KEY(provider,response_id))')
        for identity, output, quarantined in rows:
            db.execute('INSERT INTO usage_responses VALUES(?,?,?,?,?,?)', ('claude', identity, '2026-10-01T22:00:00Z', 'claude-opus-5-5',
                json.dumps({'input_tokens': 14, 'output_tokens': output, 'cache_read_input_tokens': 5, 'cache_creation_input_tokens': 7}), quarantined))


def test_reader_ledger_live_archive_precedence_and_quarantine_are_atomic(tmp_path):
    main, archive = tmp_path/'main.sqlite', tmp_path/'archive.sqlite'
    ledger(main, [('primary', 3, 0), ('primary-blocked', 3, 1)])
    ledger(archive, [('primary', 999, 0), ('primary-blocked', 999, 0), ('live', 1, 0), ('conflict', 999, 0), ('archive-only', 4, 0)])
    root = tmp_path/'C'
    write(root/'session.jsonl', [assistant('primary', output=7), assistant('primary-blocked', output=7),
        assistant('live', output=7), assistant('conflict'), assistant('conflict', fresh=50)])
    result = read_usage(main, until='2026-10-01T22:01:00Z', range_name='all', history_filename=archive,
                        live_roots=[('C', str(root))], live_parser=PARSER)
    assert result['total_responses'] == 3, 'Primary quarantine and live conflicts must suppress archive twins'
    assert result['totals']['out_tokens'] == 14, 'Priority is primary3 + live7 + archive4, never duplicate999'
    assert result['coverage']['source_counts'] == {'ledger': 1, 'archives': 1, 'claude-live': 1}
    assert result['coverage']['live_claude']['quarantined'] == 1


def test_reader_refreshes_current_and_history_from_appended_source_without_writes(tmp_path):
    main, archive = tmp_path/'main.sqlite', tmp_path/'archive.sqlite'
    ledger(main, []); ledger(archive, [])
    source = tmp_path/'C'/'session.jsonl'
    write(source, [assistant('old', stamp='2026-09-30T22:00:00Z')])
    before_db = (main.read_bytes(), archive.read_bytes())
    options = {'until': '2026-10-01T22:01:00Z', 'range_name': 'all', 'history_filename': archive,
               'live_roots': [('C', str(tmp_path/'C'))], 'live_parser': PARSER}
    first = read_usage(main, **options)
    assert first['platform_models'][0]['current']['metrics'] is None
    with source.open('a') as stream:
        stream.write(json.dumps(assistant('new', stamp='2026-10-01T22:00:00Z', cache=0, creation=0))+'\n')
    second = read_usage(main, **options)
    row = next(row for row in second['platform_models'] if row['platform'] == 'claude')
    assert row['current']['metrics']['turns'] == 1
    assert row['history']['metrics']['turns'] == 2
    assert row['current']['metrics']['cache_read'] == 0, 'Live native zero remains measured'
    assert row['current']['metrics']['cache_creation_tokens'] == 0
    assert (main.read_bytes(), archive.read_bytes()) == before_db, 'Live refresh must not update either database'


def test_losing_live_observation_cannot_supply_primary_zero_provenance(tmp_path):
    main, archive = tmp_path/'main.sqlite', tmp_path/'archive.sqlite'
    ledger(main, [('primary', 3, 0)]); ledger(archive, [])
    with sqlite3.connect(main) as db:
        db.execute('UPDATE usage_responses SET usage=?', (json.dumps({'input_tokens': 10, 'output_tokens': 3,
            'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}),))
    root = tmp_path/'C'
    write(root/'session.jsonl', [assistant('primary', cache=100, creation=7)])
    result = read_usage(main, until='2026-10-01T22:01:00Z', range_name='all', history_filename=archive,
                        live_roots=[('C', str(root))], live_parser=PARSER)
    row = next(row for row in result['platform_models'] if row['platform'] == 'claude')
    assert result['total_responses'] == 1
    assert result['totals']['out_tokens'] == 3
    assert row['history']['metrics']['cache_read'] is None, 'PRIMARY_PROVENANCE_NOT_FROM_LOSER'
    assert row['history']['metrics']['cache_creation_tokens'] is None
    assert row['history']['metrics']['total_ctx'] is None
    assert 'raw-field provenance' in row['history']['unknown_metrics']['cache_read']
