"""Compare exported MIDI beat grids on a frozen RWC-P split, without transcription."""
import argparse
from bisect import bisect_right
from contextlib import nullcontext
import csv
from hashlib import sha256
import json
from itertools import accumulate
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import mido
import numpy as np
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from audio_midi.beat_align import (
    DEFAULT_TEMPO_RULE, TEMPO_RULES, BeatEstimate, TempoMap, detect_beat_options,
    write_aligned_midi,
)


MANIFEST_SHA256 = '21a9a1879f33ec84d2191b3deab083f9f6cbe5ef0c0e887f366c0dc1578ff00e'


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


def f_measure(reference, estimate, tolerance=.07):
    i = j = hits = 0
    while i < len(reference) and j < len(estimate):
        delta = estimate[j] - reference[i]
        if delta < -tolerance:
            j += 1
        elif delta > tolerance:
            i += 1
        else:
            hits += 1
            i += 1
            j += 1
    count = len(reference) + len(estimate)
    return 2 * hits / count if count else 0.


def tempo_multiple(ratio):
    for multiple, label in ((.5, 'half'), (1., 'normal'), (2., 'double')):
        if .9 * multiple <= ratio <= 1.1 * multiple:
            return label
    return 'other'


def scores(ref, downbeats, beats, bars, lo, hi):
    beats = beats[(beats >= lo) & (beats < hi)]
    bars = bars[(bars >= lo) & (bars < hi)]
    bpm = 60 / float(np.median(np.diff(beats))) if len(beats) >= 2 else None
    ref_bpm = 60 / float(np.median(np.diff(ref)))
    bpm_ratio = bpm / ref_bpm if bpm is not None else None
    return {
        'downbeat_f1': f_measure(downbeats, bars),
        'bar_count': len(bars), 'reference_bar_count': len(downbeats),
        'bar_count_ratio': len(bars) / len(downbeats) if len(downbeats) else None,
        'beat_f1': f_measure(ref, beats),
        'bpm': bpm, 'bpm_error': abs(bpm - ref_bpm) if bpm is not None else None,
        'bpm_ratio': bpm_ratio, 'tempo_multiple': tempo_multiple(bpm_ratio) if bpm_ratio is not None else None,
    }


def evaluate(song, dataset, scratch, *, rules, start_bpm=120):
    import soundfile as sf

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

    fixed_path = scratch / 'fixed.mid'
    aligned_path = scratch / 'aligned.mid'
    fixed = mido.MidiFile(type=1, ticks_per_beat=480)
    fixed.add_track('Conductor').extend([
        mido.MetaMessage('set_tempo', tempo=500000),
        mido.MetaMessage('time_signature', numerator=4, denominator=4),
        mido.MetaMessage('end_of_track', time=round(len(audio) / 16000 * 960)),
    ])
    fixed.save(fixed_path)
    variants = {'fixed': scores(ref, downbeats, *grid(fixed_path), lo, hi)}
    estimates = detect_beat_options(audio, 16000, start_bpm=start_bpm, rules=rules)
    detections = {}
    for rule, estimate in estimates.items():
        try:
            tempo_map = TempoMap(estimate)
        except ValueError as error:
            estimate = BeatEstimate(fallback_reason=f'ValueError: {error}',
                                    tempo_selection=estimate.tempo_selection)
            tempo_map = TempoMap(estimate)
        if estimate.beats:
            write_aligned_midi(fixed_path, aligned_path, tempo_map)
            variants[rule] = scores(ref, downbeats, *grid(aligned_path), lo, hi)
        else:
            variants[rule] = variants['fixed']
        detections[rule] = tempo_map.receipt(estimate, True, None)
    return {
        'song': song['id'], 'start_bpm': start_bpm,
        'reference_bpm': 60 / float(np.median(np.diff(ref))),
        'reference_max_beat': max(beat for time, beat in annotations if lo <= time < hi),
        'scores': variants, 'detection': detections,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--split', choices=('tuning', 'test'), default='tuning')
    parser.add_argument('--output', type=Path, help='create a new JSONL; required for test')
    parser.add_argument('--experimental-start-bpm', type=float, default=120,
                        help='evaluate an alternate librosa tempo prior without changing the one-click default')
    args = parser.parse_args()
    if not np.isfinite(args.experimental_start_bpm) or args.experimental_start_bpm <= 0:
        parser.error('experimental starting BPM must be positive and finite')
    if args.split == 'test':
        if DEFAULT_TEMPO_RULE not in TEMPO_RULES:
            parser.error('freeze a tuning winner before evaluation on the test split')
        if args.output is None or args.experimental_start_bpm != 120:
            parser.error('test requires a new --output and the original 120 BPM tracking prior')
        rules = ('public12', DEFAULT_TEMPO_RULE)
    else:
        rules = ('public12', *TEMPO_RULES)

    manifest_bytes = args.manifest.read_bytes()
    if sha256(manifest_bytes).hexdigest() != MANIFEST_SHA256:
        parser.error('expected the frozen 72-song RWC-P manifest')
    manifest = json.loads(manifest_bytes)
    songs = [song for song in manifest['songs'] if song['split'] == args.split]
    expected_count = {'tuning': 22, 'test': 50}[args.split]
    if len(songs) != expected_count or len({song['id'] for song in songs}) != expected_count:
        parser.error(f'expected {expected_count} unique songs in {args.split}')
    destination = args.output.open('x') if args.output else nullcontext(sys.stdout)
    with destination as stream, TemporaryDirectory(prefix='noto-beat-eval-') as scratch:
        for song in songs:
            result = evaluate(song, args.dataset, Path(scratch), rules=rules,
                              start_bpm=args.experimental_start_bpm)
            print(json.dumps(result, allow_nan=False), file=stream, flush=True)


if __name__ == '__main__':
    main()
