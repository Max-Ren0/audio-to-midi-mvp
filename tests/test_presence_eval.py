import importlib.util
from pathlib import Path

import pytest

from audio_midi.events import NoteEvent
from audio_midi.midi import write_midi


def test_original_cohort_uses_nested_historical_score_and_fixed_drum_mapping(tmp_path, monkeypatch):
    pytest.importorskip('pretty_midi')
    pytest.importorskip('soundfile')
    runner = Path(__file__).resolve().parents[1] / 'outputs/presence-eval/run.py'
    spec = importlib.util.spec_from_file_location('presence_eval', runner)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.syspath_prepend(str(runner.parent))
    spec.loader.exec_module(module)

    row = {'id': 'song', 'center_seconds': [1, 61], 'sample_rate': 1, 'input_frames': [0, 62]}
    reference = [NoteEvent('drums', 35, 2, 2.5)]
    prediction = [NoteEvent('drums', 36, 2, 2.5)]
    rules = {'piano': {}, 'bass': {}, 'drums': {'notes_per_minute': 100}}
    work = tmp_path / 'work/rwcp-eval'
    path = work / 'team-midi/song/S3.mid'
    path.parent.mkdir(parents=True)
    write_midi(prediction, path)
    historical = {
        'midi_sha256': module.pilot.digest(path),
        'scores': {name: module.team.score_route(reference, module.read_notes(path), name, [1, 61], 0, 0)
                   for name in module.TRACKS},
    }
    monkeypatch.setattr(module.team, 'test_songs', lambda _: [row])
    monkeypatch.setattr(module, 'raw_reference', lambda *_: reference)
    (work / 'manifest.json').write_text('{}')
    monkeypatch.setattr(module.team, 'MANIFEST_SHA', module.pilot.digest(work / 'manifest.json'))
    module.pilot.write_json(work / 'team-results.json', {
        'items': {'song': {'combinations': {'S3': historical}}},
    })
    results = module.original_tests(tmp_path, rules, tmp_path)
    assert results[0]['scores']['off']['drums']['tp'] == 1
    assert results[0]['scores']['on']['drums']['fn'] == 1
    assert results[0]['gate']['drums']['suppressed']
