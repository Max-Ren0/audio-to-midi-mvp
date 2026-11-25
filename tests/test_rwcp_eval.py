import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

from audio_midi.events import NoteEvent


HERE = Path(__file__).resolve().parents[1] / 'outputs/rwcp-eval'


def load(name):
    spec = importlib.util.spec_from_file_location(f'rwcp_{name}', HERE / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


score = load('score')


@pytest.fixture
def prepare():
    pytest.importorskip('pretty_midi')
    pytest.importorskip('soundfile')
    return load('prepare')


def note(category, pitch, onset):
    return NoteEvent(category, pitch, onset, onset + .18)


def test_tolerance_inclusive_and_one_to_one():
    ref = [note('piano', 60, 62.00), note('piano', 60, 62.02)]
    pred = [note('piano', 60, 3.05), note('piano', 60, 3.071)]
    metrics = score.score(ref, pred, 'piano', (60, 120), 59, 0)['exact']
    assert (metrics['tp'], metrics['fp'], metrics['fn']) == (1, 1, 1)


def test_offset_changes_membership_and_respects_half_open_windows():
    ref = [note('piano', 60, 59.95), note('piano', 61, 119.94)]
    pred = [note('piano', 62, .99), note('piano', 60, 1.01), note('piano', 61, 61.)]
    raw = score.score(ref, pred, 'piano', (60, 120), 59, 0)
    corrected = score.score(ref, pred, 'piano', (60, 120), 59, .06)
    assert raw['exact']['tp'] == 0
    assert corrected['reference_notes'] == corrected['prediction_notes'] == 1
    assert corrected['exact']['f1'] == 1


def test_drum_aliases_and_other_counts():
    ref = [note('drums', 35, 61), note('drums', 40, 62), note('drums', 42, 63)]
    pred = [note('drums', 36, 2), note('drums', 38, 3), note('drums', 39, 3), note('drums', 49, 4)]
    outcome = score.score(ref, pred, 'drums', (60, 120), 59, 0)
    assert outcome['exact']['f1'] == 1
    assert outcome['other_drum_notes'] == {'reference': {'42': 1}, 'prediction': {'39': 1, '49': 1}}


def test_bass_octave_metric_and_empty_reference_fp():
    ref = [note('bass', 31, 61), note('bass', 43, 61)]
    pred = [note('bass', 55, 2)]
    outcome = score.score(ref, pred, 'bass', (60, 120), 59, 0)
    absent = score.score([], pred, 'bass', (60, 120), 59, 0)
    assert outcome['exact']['f1'] == 0
    assert outcome['octave_free']['tp'] == 1
    assert absent['absent_category_false_positives'] == 1
    assert score.pool([outcome, absent], 'octave_free') == {
        'tp': 1, 'fp': 1, 'fn': 1, 'f1': .5, 'absent_category_false_positives': 1,
    }


def test_offset_correlates_without_predictions(prepare):
    onsets = np.array([200, 315, 544, 780, 881, 930])
    envelope = np.zeros(1100)
    envelope[onsets + 4] = 1
    result = prepare.alignment(onsets * prepare.STEP, envelope, 0, len(envelope) * prepare.STEP)
    assert result['seconds'] == pytest.approx(4 * prepare.STEP)
    assert result['peak'] > result['at_zero']
    assert prepare.alignment([], envelope, 0, 10)['status'] == 'insufficient_support'


def test_split_stratified_deterministic_and_window_exclusion(prepare):
    groups = {label: [f'{label}-{index:02}' for index in range(count)]
              for label, count in prepare.EXPECTED.items()}
    tuning, pilot = prepare.split_songs(groups)
    shuffled_inputs = {label: list(reversed(songs)) for label, songs in reversed(list(groups.items()))}
    assert (tuning, pilot) == prepare.split_songs(shuffled_inputs)
    assert len(tuning) == 22 and set(pilot) <= tuning
    assert sum(song.startswith('Live drums') for song in pilot) == 2
    assert sum(song.startswith('Drum sequences') for song in pilot) == 3
    beats = [i / 2 + .06 for i in range(300)]
    assert prepare.window(beats, 0, 150, [(0, 3)]) == pytest.approx((60.06, 120.06))
    with pytest.raises(ValueError, match='No safe window'):
        prepare.window(beats, 0, 150, [(60, 63)])


def test_pilot_rejects_test_songs(prepare, monkeypatch):
    monkeypatch.syspath_prepend(str(HERE))
    # Generic script names are local to the CLI.
    monkeypatch.setitem(sys.modules, 'prepare', prepare)
    monkeypatch.setitem(sys.modules, 'score', score)
    run = load('run_pilot')
    manifest = {'pilot_ids': [str(i) for i in range(5)],
                'songs': [{'id': str(i), 'split': 'tuning' if i < 5 else 'test'} for i in range(72)]}
    assert [entry['id'] for entry in run.pilot_songs(manifest)] == manifest['pilot_ids']
    manifest['pilot_ids'][-1] = '10'
    with pytest.raises(ValueError, match='tuning'):
        run.pilot_songs(manifest)


def test_b7_octave_repair_preserves_onset_and_p5_no_evidence(prepare):
    specialist = load('specialists')
    sample_rate = 44100
    t = np.arange(sample_rate) / sample_rate
    signal = np.sin(2 * np.pi * specialist.pitch_hz(33) * t)
    original = note('bass', 45, .1)
    corrected, = specialist.octave_correct([original], signal, sample_rate)
    assert corrected.pitch == 33
    assert corrected.onset == original.onset and corrected.offset == original.offset
    assert specialist.choose_piano([], signal, sample_rate)['route'] == 'P1'
