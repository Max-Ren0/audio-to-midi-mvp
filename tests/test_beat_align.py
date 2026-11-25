from itertools import accumulate

import mido
import numpy as np
import pytest

from audio_midi.beat_align import BeatEstimate, TempoMap, _infer_meter, write_aligned_midi


@pytest.mark.parametrize(('profile', 'meter', 'phase'), [
    ([.4, 1.4, .1], 3, 1),
    ([.3, .1, 1.4, .5], 4, 2),
])
def test_meter_and_phase_from_recurring_accents(profile, meter, phase):
    assert _infer_meter(np.tile(profile, 12))[:2] == (meter, phase)
    assert not _infer_meter(np.tile(profile, 12))[-1]
    fallback_meter, _, _, fallback = _infer_meter(np.ones(48))
    assert fallback_meter == 4 and fallback


def test_exported_conductor_places_detected_downbeats_on_bar_lines(tmp_path):
    beats = (0., .49, .98, 1.43, 1.91, 2.42, 2.97, 3.47, 3.99, 4.46, 4.9)
    source = tmp_path / 'source.mid'
    target = tmp_path / 'target.mid'
    fixed = mido.MidiFile(ticks_per_beat=480)
    fixed.add_track('Conductor').extend([
        mido.MetaMessage('set_tempo', tempo=500000),
        mido.MetaMessage('time_signature', numerator=4, denominator=4),
        mido.MetaMessage('end_of_track', time=60 * 960),
    ])
    fixed.save(source)
    tempo_map = TempoMap(BeatEstimate(beats=beats, meter=3, downbeat_index=2))
    assert write_aligned_midi(source, target, tempo_map) == 0
    exported = mido.MidiFile(target)
    assert exported.length == pytest.approx(60., abs=25e-6)
    track = exported.tracks[0]
    quarter = exported.ticks_per_beat
    tempos = [(tick, msg.tempo) for tick, msg in zip(accumulate(msg.time for msg in track), track)
              if msg.type == 'set_tempo']
    signature = next(msg for msg in track if msg.type == 'time_signature')
    assert (signature.numerator, signature.denominator) == (3, 4)
    assert len(tempos) > 1

    def seconds_at(tick):
        boundaries = [start for start, _ in tempos if start < tick] + [tick]
        return sum(mido.tick2second(b - a, quarter, tempo)
                   for a, b, (_, tempo) in zip(boundaries, boundaries[1:], tempos))

    assert [seconds_at(bar * 3 * quarter) for bar in range(1, 4)] == pytest.approx(
        beats[2::3], abs=2e-6,
    )


def test_slow_pickup_keeps_note_time_within_half_of_the_longest_tick(tmp_path):
    source = tmp_path / 'source.mid'
    target = tmp_path / 'target.mid'
    fixed = mido.MidiFile(ticks_per_beat=480)
    fixed.add_track('Conductor').append(mido.MetaMessage('set_tempo', tempo=500000))
    track = fixed.add_track('piano')
    for _ in range(600):
        track.append(mido.Message('note_on', note=60, time=1))
        track.append(mido.Message('note_off', note=60, time=1))
    fixed.save(source)

    estimate = BeatEstimate(beats=tuple(2.21 + i * 1.48 for i in range(9)),
                            downbeat_index=3)
    tempo_map = TempoMap(estimate)
    write_aligned_midi(source, target, tempo_map)

    def note_times(path):
        now = 0.
        for event in mido.MidiFile(path):
            now += event.time
            if event.type in ('note_on', 'note_off'):
                yield now

    maximum_error = max(abs(a - b) for a, b in zip(note_times(source), note_times(target), strict=True))
    half_tick = max(tempo_map.tempos) / mido.MidiFile(target).ticks_per_beat / 2e6
    assert 35e-6 < maximum_error <= half_tick + 1e-12


@pytest.mark.parametrize(('bars', 'f_measure', 'count_ratio'), [
    ([0., 1., 2., 3.], 2 / 3, 2.),
    ([0.], 2 / 3, .5),
    ([0., 2.06, 4.], 1., 1.),
])
def test_scoring_penalizes_extra_and_missing_bar_lines(monkeypatch, bars, f_measure, count_ratio):
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    from eval_noto_beat_align import scores

    quarter_notes = np.arange(0., 4., .5)
    result = scores(quarter_notes, np.array([0., 2.]), quarter_notes,
                    np.array(bars), lo=0., hi=4.)
    assert result['downbeat_f1'] == pytest.approx(f_measure)
    assert result['bar_count_ratio'] == count_ratio
