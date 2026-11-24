import json
from pathlib import Path
import sys

from audio_midi.events import NoteEvent


EVAL_DIR = Path(__file__).resolve().parents[1] / 'outputs/e2e-eval'


def load_eval(monkeypatch):
    monkeypatch.syspath_prepend(str(EVAL_DIR))
    return __import__('score_e2e')


def test_score_counts_absent_predictions_and_matches_one_to_one(monkeypatch):
    scorer = load_eval(monkeypatch)
    reference = [
        NoteEvent('piano', 60, 0.0, 0.1),
        NoteEvent('drums', 38, 0.0, 0.1),
    ]
    prediction = [
        NoteEvent('piano', 60, 0.05, 0.2),
        NoteEvent('piano', 60, 0.04, 0.2),
        NoteEvent('drums', 40, 0.04, 0.1),
        NoteEvent('drums', 38, 0.051, 0.1),
        NoteEvent('bass', 36, 0.0, 0.1),
        NoteEvent('strings', 48, 0.0, 0.1),
    ]
    tracks, absent = scorer.score_tracks(reference, prediction)
    assert tracks['piano'] == scorer.metrics(1, 1, 0)
    assert tracks['drums'] == scorer.metrics(0, 2, 1)
    assert tracks['bass'] == scorer.metrics(0, 1, 0)
    assert tracks['bass']['recall'] is None
    assert absent == {'bass': 1}


def test_failed_sample_keeps_reference_notes_and_private_error_stays_private(monkeypatch, tmp_path):
    scorer = load_eval(monkeypatch)
    sample = {'id': 'slakh-Track00017', 'source': 'BabySlakh', 'window_seconds': [30, 90]}
    items = tmp_path / 'items'
    sample_dir = items / sample['id']
    sample_dir.mkdir(parents=True)
    (sample_dir / 'input.mp3').touch()
    (sample_dir / 'reference.json').write_text(json.dumps({'notes': [
        {'category': 'drums', 'pitch': 38, 'onset': 0.0, 'offset': 0.1},
    ]}))
    runs = tmp_path / 'runs'
    attempt = runs / sample['id']
    attempt.mkdir(parents=True)
    (attempt / 'receipt.json').write_text(json.dumps({
        'status': 'failed', 'failed_stage': 'baseline', 'duration_seconds': 60,
        'total_seconds': 30, 'stages': [
            {'name': 'baseline', 'status': 'failed', 'seconds': 25,
             'error': '缺少资源：/Users/another account/private/model.gguf'},
        ],
    }))
    (attempt / 'attempt.json').write_text(json.dumps({'returncode': 1, 'wall_seconds': 30.1}))
    conditional = {'tracks': {'drums': {'best': {'tp': 1, 'fp': 0, 'fn': 0}}}}
    row = scorer.score_sample(sample, items, runs, conditional)
    assert row['success'] is False
    assert row['exit_code'] == 1
    assert row['failed_stage'] == 'baseline'
    assert row['failure_reason'] == '缺少资源：<本机路径>'
    assert row['total_seconds'] == 30
    assert row['realtime_factor'] == 0.5
    assert row['tracks']['drums'] == scorer.metrics(0, 0, 1)
    assert row['tracks']['bass']['f1'] is None
    assert '/Users/' not in json.dumps(row)
    assert scorer.public_error('缺少依赖：/opt/homebrew/bin/ffprobe') == '缺少依赖：<本机路径>'


def test_retries_keep_original_and_sort_numerically(monkeypatch, tmp_path):
    scorer = load_eval(monkeypatch)
    runner = sys.modules['run_e2e']
    for name in ('sample', 'sample.retry-10', 'sample.retry-2', 'sample.retry-x'):
        (tmp_path / name).mkdir()
    assert [path.name for path in scorer.attempts(tmp_path, 'sample')] == [
        'sample', 'sample.retry-2', 'sample.retry-10',
    ]
    assert runner.next_attempt(tmp_path, 'sample').name == 'sample.retry-1'
