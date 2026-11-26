"""Freeze presence labels and source-stratified assignments before inference."""
import argparse
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import random

import pretty_midi
import soundfile as sf


HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parent
TRACKS = ('piano', 'bass', 'drums')
SEED = 20261126
ORIGINAL_SHA256 = '21a9a1879f33ec84d2191b3deab083f9f6cbe5ef0c0e887f366c0dc1578ff00e'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rwc = load_module('rwcp_prepare', OUTPUTS / 'rwcp-eval/prepare.py')
e2e = load_module('presence_run_e2e', OUTPUTS / 'e2e-eval/run_e2e.py')
multi = load_module('presence_multi_score', OUTPUTS / 'multi-song-eval/score.py')


def present(notes, interval):
    start, end = interval
    return {name: any(note.category == name and note.onset < end
                      and (note.onset >= start or
                           (note.offset is not None and note.offset > start))
                      for note in notes) for name in TRACKS}


def rwc_samples(dataset, original):
    chosen = {song['id']: song for song in original['songs']}
    vocals = defaultdict(set)
    for row in rwc.rows(dataset / rwc.MIDI_PATH.parent / 'metadata_mapping_vocals.csv'):
        vocals[row['RWCID']].add(row['MIDITrackName'].strip().casefold())
    samples = []
    for row in sorted(rwc.rows(dataset / 'annotations/metadata.csv'), key=lambda row: row['RWCID']):
        song = row['RWCID']
        # The original 50 test songs will be read only for final evaluation.
        if song in chosen and chosen[song]['split'] == 'test':
            continue
        midi = dataset / rwc.MIDI_PATH / f'{song}.mid'
        notes = list(rwc.reference_notes(pretty_midi.PrettyMIDI(str(midi)), vocals[song]))
        audio = dataset / 'RWC-P' / f'{song}.wav'
        info = sf.info(audio)
        lower = max(0, float(row['audio_start']))
        upper = min(float(row['audio_end']), info.duration)
        safe = rwc.EXCLUDED.get(song, [])
        if song not in chosen:
            beats = rwc.rows(dataset / rwc.BEAT_PATH / f'{song}.csv')
            start, end = rwc.window([float(beat['t']) for beat in beats], lower, upper, safe)
            source = 'RWC-P excluded'
        else:
            # One non-overlapping source song per row. Search 60 s windows on a 5 s grid
            # and select the earliest one with the most absent tracks.
            windows = [(float(start), float(start + 60))
                       for start in range(0, int(upper) - 59, 5)
                       if lower <= start and not any(start < hi and start + 60 > lo for lo, hi in safe)]
            if not windows:
                continue
            start, end = min(windows, key=lambda window: sum(present(notes, window).values()))
            if all(present(notes, (start, end)).values()):
                continue
            source = 'RWC-P local'
        frames = [round(t * info.samplerate) for t in (start, end)]
        interval = [frame / info.samplerate for frame in frames]
        samples.append({
            'id': song, 'source': source, 'presence': present(notes, interval),
            'seconds': interval, 'input_frames': frames, 'sample_rate': info.samplerate,
            'audio': str(audio.relative_to(dataset)), 'audio_sha256': rwc.digest(audio),
            'midi': str(midi.relative_to(dataset)), 'midi_sha256': rwc.digest(midi),
            'vocal_names': sorted(vocals[song]),
        })
    return samples


def e2e_samples(items):
    samples = []
    for sample in e2e.select_samples(items):
        sample_id = sample['id']
        ref = items / sample_id / 'reference.json'
        audio = items / sample_id / 'input.mp3'
        duration = sample['window_seconds'][1] - sample['window_seconds'][0]
        samples.append({
            'id': sample_id, 'source': 'e2e', 'reference_source': sample['source'],
            'presence': present(multi.ref_notes(ref, sample['source']), (0, duration)),
            'seconds': [0, duration], 'audio': str(audio.relative_to(items)),
            'audio_sha256': rwc.digest(audio), 'reference': str(ref.relative_to(items)),
            'reference_sha256': rwc.digest(ref),
        })
    return samples


def assign(samples):
    """Keep source quotas fixed and balance each instrument's negative labels."""
    rng = random.Random(SEED)
    by_source = defaultdict(list)
    for row in samples:
        by_source[row['source']].append(row)
    assignments = {}
    counts = {source: len(rows) * 2 // 5 for source, rows in by_source.items()}
    order = sorted(by_source, key=lambda source: (-(len(by_source[source]) * 2 % 5), source))
    for source in order[:round(len(samples) * .4) - sum(counts.values())]:
        counts[source] += 1
    for source, rows in sorted(by_source.items()):
        negatives = Counter(name for row in rows for name in TRACKS if not row['presence'][name])
        quota = counts[source]

        def imbalance(subset):
            return sum((sum(not row['presence'][name] for row in subset) * len(rows)
                        - negatives[name] * quota) ** 2 for name in TRACKS)

        selected = min((rng.sample(rows, quota) for _ in range(2048)), key=imbalance)
        assignments.update((row['id'], 'test') for row in rows)
        assignments.update((row['id'], 'tuning') for row in selected)
    if len(assignments) != len(samples):
        raise ValueError('Duplicate presence sample IDs')
    return assignments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resources', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=HERE)
    args = parser.parse_args()
    resources = args.resources
    manifest = resources / 'work/rwcp-eval/manifest.json'
    if rwc.digest(manifest) != ORIGINAL_SHA256:
        raise ValueError('Original RWC-P manifest changed')
    samples = rwc_samples(resources / 'work/datasets/rwc-p', json.loads(manifest.read_text()))
    if sum(row['source'] == 'RWC-P excluded' for row in samples) != 28:
        raise ValueError('Expected all 28 excluded RWC-P songs')
    samples.extend(e2e_samples(resources / e2e.ITEMS_RELATIVE))
    for name, value in (
        ('manifest.json', {'original_manifest_sha256': ORIGINAL_SHA256, 'samples': samples}),
        ('split.json', {'seed': SEED, 'assignments': assign(samples)}),
    ):
        with (args.output / name).open('x', encoding='utf-8') as file:
            json.dump(value, file, ensure_ascii=False, indent=2, sort_keys=True)
            file.write('\n')


if __name__ == '__main__':
    main()
