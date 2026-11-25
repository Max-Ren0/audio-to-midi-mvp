"""Compare MIDI beat grids on the frozen RWC-P tuning windows, without transcription."""
import argparse
from bisect import bisect_right
import csv
import json
from itertools import accumulate
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import mido
import numpy as np
from scipy.signal import resample_poly
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from audio_midi.beat_align import TempoMap, detect_beats, write_aligned_midi


def grid(path):
    """Read the conductor of the exported file, including extrapolated tail beats."""
    midi = mido.MidiFile(path)
    conductor = midi.tracks[0]
    ppq = midi.ticks_per_beat
    positions = list(zip(accumulate(msg.time for msg in conductor), conductor))
    ticks, tempo = zip(*[(tick, msg.tempo) for tick, msg in positions if msg.type == 'set_tempo'])
    meter = next(msg.numerator for _, msg in positions if msg.type == 'time_signature')
    seconds = [0., *accumulate(mido.tick2second(b - a, ppq, t)
                              for a, b, t in zip(ticks, ticks[1:], tempo))]
    beats = []
    for tick in range(0, positions[-1][0] + 1, ppq):
        index = bisect_right(ticks, tick) - 1
        beats.append(seconds[index] + mido.tick2second(tick - ticks[index], ppq, tempo[index]))
    return np.array(beats), np.array(beats[::meter])


def scores(ref, downbeats, beats, bars, lo, hi):
    beats = beats[(beats >= lo) & (beats < hi)]
    i = j = hits = 0
    while i < len(ref) and j < len(beats):
        delta = beats[j] - ref[i]
        if delta < -.07:
            j += 1
        elif delta > .07:
            i += 1
        else:
            hits += 1
            i += 1
            j += 1
    bpm = 60 / float(np.median(np.diff(beats))) if len(beats) >= 2 else None
    ref_bpm = 60 / float(np.median(np.diff(ref)))
    return {
        'beat_f1': 2 * hits / (len(ref) + len(beats)),
        'bpm': bpm, 'bpm_error': abs(bpm - ref_bpm) if bpm is not None else None,
        'bar_median_ms': float(1000 * np.median(np.min(np.abs(downbeats[:, None] - bars), axis=1))),
    }


def evaluate(song, dataset, scratch):
    start, end = song['input_frames']
    with sf.SoundFile(dataset / song['audio'], mode='r') as source:
        rate = source.samplerate
        assert rate == song['sample_rate']
        source.seek(start)
        audio = source.read(end - start, dtype='float32', always_2d=True).mean(axis=1)
    audio = resample_poly(audio, 16000, rate)
    origin = start / rate
    lo, hi = (time - origin for time in song['center_seconds'])
    with (dataset / song['beats']).open(encoding='utf-8-sig') as stream:
        annotations = [(float(row['t']) - origin, int(row['beat']))
                       for row in csv.DictReader(stream, delimiter=';')]
    ref = np.array([time for time, _ in annotations if lo <= time < hi])
    downbeats = np.array([time for time, beat in annotations if lo <= time < hi and beat == 1])

    estimate = detect_beats(audio, 16000)
    tempo_map = TempoMap(estimate)
    fixed_path = scratch / 'fixed.mid'
    aligned_path = scratch / 'aligned.mid'
    fixed = mido.MidiFile(type=1, ticks_per_beat=480)
    fixed.add_track('Conductor').extend([
        mido.MetaMessage('set_tempo', tempo=500000),
        mido.MetaMessage('time_signature', numerator=4, denominator=4),
        mido.MetaMessage('end_of_track', time=round(len(audio) / 16000 * 960)),
    ])
    fixed.save(fixed_path)
    if estimate.beats:
        write_aligned_midi(fixed_path, aligned_path, tempo_map)
    else:
        aligned_path = fixed_path
    return {'song': song['id'], 'reference_bpm': 60 / float(np.median(np.diff(ref))),
            'reference_max_beat': max(beat for time, beat in annotations if lo <= time < hi),
            'fixed': scores(ref, downbeats, *grid(fixed_path), lo, hi),
            'aligned': scores(ref, downbeats, *grid(aligned_path), lo, hi),
            'detection': tempo_map.receipt(estimate, True, None)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    tuning = [song for song in manifest['songs'] if song['split'] == 'tuning']
    if not tuning:
        parser.error('manifest has no tuning songs')
    with TemporaryDirectory(prefix='noto-beat-eval-') as scratch:
        for song in tuning:
            print(json.dumps(evaluate(song, args.dataset, Path(scratch))), flush=True)


if __name__ == '__main__':
    main()
