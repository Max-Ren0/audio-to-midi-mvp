from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def dev(monkeypatch):
    pytest.importorskip('pretty_midi')
    pytest.importorskip('soundfile')
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'outputs/rwcp-eval'))
    import run_dev
    return run_dev


@pytest.mark.parametrize(('lag', 'applied', 'status'), [
    (8, .0598185941043, 'applied'),
    (7, 0, 'dead_zone'),
    (-4, -.0599092970522, 'applied'),
    (10, 0, 'search_edge'),
])
def test_offset_calibration_and_dead_zone(dev, lag, applied, status):
    envelope = np.zeros(1200)
    frames = np.array([201, 315, 544, 780, 881])
    envelope[frames + lag] = 1
    offset = dev.alignment_v2(frames * dev.STEP, envelope)
    assert offset['status'] == status
    assert offset['seconds'] == pytest.approx(applied)


def test_offset_rejects_periodic_peaks_and_missing_support(dev):
    frames = np.arange(100, 1100, 12)
    envelope = np.zeros(1200)
    envelope[frames + 6] = 1
    assert dev.alignment_v2(frames * dev.STEP, envelope)['status'] == 'ambiguous'
    assert dev.alignment_v2([], envelope)['status'] == 'insufficient_support'


def test_tiebreak_compares_all_routes_within_two_points_of_leader(dev):
    scores = {'P1': Fraction('0.80'), 'P2': Fraction('0.819'), 'P3': Fraction('0.799')}
    result = dev.choose(scores, {'P1': 20., 'P2': 60., 'P3': 1.})
    assert result == {'winner': 'P1', 'leader': 'P2', 'ties': ['P1', 'P2']}
    assert dev.choose({'P1': Fraction('.80'), 'P2': Fraction('.82')},
                      {'P1': 20., 'P2': 60.})['winner'] == 'P2'


def test_empty_output_counts_as_misses_and_undefined_pair_is_separate(dev):
    from audio_midi.events import NoteEvent
    ref = [NoteEvent('drums', 36, 4., 4.2)]
    scores = dev.score_route(ref, [], 'drums', (3., 5.), 2., 0.)
    assert scores['status'] == 'empty'
    assert scores['corrected']['exact']['fn'] == 1
    assert scores['corrected']['exact']['f1'] == 0
    cymbal = NoteEvent('drums', 42, 2., 2.2)
    assert dev.score_route(ref, [cymbal], 'drums', (3., 5.), 2., 0.)['status'] == 'ok'


def test_tuning_ids_keep_pilot_order_and_reject_duplicate(dev):
    songs = [{'id': str(i), 'split': 'tuning' if i < 22 else 'test'} for i in range(72)]
    assert [s['id'] for s in dev.tuning_songs({'songs': songs, 'pilot_ids': ['3','1','5','4','6']})][:6] == [
        '3', '1', '5', '4', '6', '0',
    ]
    songs[-1]['id'] = '3'
    with pytest.raises(ValueError):
        dev.tuning_songs({'songs': songs, 'pilot_ids': ['3','1','5','4','6']})
