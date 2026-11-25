"""Freeze the RWC-P split, scoring windows and model-independent alignment."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import random

import numpy as np
import pretty_midi
from scipy.ndimage import gaussian_filter1d
import soundfile as sf

from audio_midi.events import NoteEvent


TRACKS = ('piano', 'bass', 'drums')
SEED = 20261125
HOP = 220
RATE = 22050
STEP = HOP / RATE
EXPECTED = {'Drum sequences': 52, 'Live drums': 13, 'Drum loops': 6, 'Without drums': 1}
EXCLUDED = {'RWC_P009': [(0, 3)]}
NON_KEYBOARD = {
    'drums 2', 'sample drums', 'dr', 'loop drums', 'per.', 'tambourine/triang',
    'digital voicekira', 'shaker', 'bd&sd', 'arpeggio c1', 'percus',
    'wow gt', 'gt 2', 'kira',
}
MIDI_PATH = Path('annotations/01_annotations_preprocessed/MIDI_aligned/RWC-P')
BEAT_PATH = Path('annotations/01_annotations_preprocessed/beats/RWC-P')


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def rows(path):
    with path.open(encoding='utf-8-sig') as source:
        return list(csv.DictReader(source, delimiter=';'))


def track_name(track):
    return track.name.strip().casefold()


def reference_notes(midi, voices):
    for track in midi.instruments:
        if track_name(track) in voices:
            continue
        if track.is_drum:
            category = 'drums'
        elif 32 <= track.program <= 39:
            category = 'bass'
        elif 0 <= track.program <= 5 and track_name(track) not in NON_KEYBOARD:
            category = 'piano'
        else:
            continue
        for note in track.notes:
            yield NoteEvent(category, note.pitch, note.start, note.end, note.velocity, track.program)


def window(beats, lower, upper, excluded):
    available = [beat for beat in beats if lower + 1 <= beat <= upper - 1]
    start = min(available, key=lambda beat: (abs(beat - 60), beat))
    end = min(available, key=lambda beat: (abs(beat - (start + 60)), beat))
    if abs(end - start - 60) > 1 or any(start - 1 < hi and end + 1 > lo for lo, hi in excluded):
        raise ValueError('No safe window under the frozen 60-second rule')
    return start, end


def split_songs(by_drum):
    rng = random.Random(SEED)
    tuning = set()
    pilot = []
    quotas = {'Drum sequences': 3, 'Live drums': 2}
    # Largest remainder, 22 tuning songs total; singleton stays in test.
    counts = {name: len(songs) * 3 // 10 for name, songs in by_drum.items()}
    remainder = round(sum(map(len, by_drum.values())) * .30) - sum(counts.values())
    order = sorted(by_drum, key=lambda name: (-((len(by_drum[name]) * 3) % 10), name))
    for name in order[:remainder]:
        counts[name] += 1
    for name, songs in sorted(by_drum.items()):
        shuffled = sorted(songs)
        rng.shuffle(shuffled)
        selected = shuffled[:counts[name]]
        tuning.update(selected)
        pilot.extend(selected[:quotas.get(name, 0)])
    return tuning, pilot


def alignment(onsets, envelope, lo, hi):
    """Positive delay moves MIDI later. Compare over equal support for every lag."""
    indices = np.unique(np.rint(np.asarray(onsets) / STEP).astype(int))
    train = np.zeros(len(envelope))
    train[indices[(indices >= 0) & (indices < len(train))]] = 1
    train = gaussian_filter1d(train, sigma=1.3)
    envelope = gaussian_filter1d(np.asarray(envelope, dtype=float), sigma=1.)
    frames = np.arange(max(25, int(np.ceil((lo + .30) / STEP))),
                       min(len(train) - 25, int(np.ceil((hi - .30) / STEP))))
    if len(frames) < 100 or not train[frames].any():
        return {'seconds': 0., 'peak': None, 'at_zero': None, 'status': 'insufficient_support'}
    lags = np.arange(-25, 26)
    pulse = train[frames] - train[frames].mean()
    audio = envelope[frames + lags[:, None]]
    audio -= audio.mean(axis=1, keepdims=True)
    norms = np.linalg.norm(pulse) * np.linalg.norm(audio, axis=1)
    if not norms.any():
        return {'seconds': 0., 'peak': None, 'at_zero': None, 'status': 'insufficient_support'}
    corr = (audio @ pulse) / np.maximum(norms, 1e-12)
    best = min(range(len(lags)), key=lambda i: (-corr[i], abs(lags[i]), lags[i]))
    return {'seconds': round(float(lags[best] * STEP), 9), 'peak': round(float(corr[best]), 6),
            'at_zero': round(float(corr[25]), 6), 'status': 'search_edge' if best in (0, 50) else 'ok'}


def estimate_offset(path, midi, voices, lo, hi):
    import librosa

    audio, rate = sf.read(path, dtype='float32', always_2d=True)
    mono = librosa.resample(audio.mean(axis=1), orig_sr=rate, target_sr=RATE)
    envelope = librosa.onset.onset_strength(y=mono, sr=RATE, hop_length=HOP, n_fft=1024)
    onsets = sorted(note.start for track in midi.instruments if track_name(track) not in voices
                    for note in track.notes if lo <= note.start < hi)
    distinct = [time for i, time in enumerate(onsets) if i == 0 or time - onsets[i-1] >= .01]
    return alignment(distinct, envelope, lo, hi)


def build(dataset):
    voices_by_song = defaultdict(set)
    for row in rows(dataset / MIDI_PATH.parent / 'metadata_mapping_vocals.csv'):
        voices_by_song[row['RWCID']].add(row['MIDITrackName'].strip().casefold())
    by_drum = defaultdict(list)
    entries = []
    for row in sorted(rows(dataset / 'annotations/metadata.csv'), key=lambda row: row['RWCID']):
        song = row['RWCID']
        midi_path = dataset / MIDI_PATH / f'{song}.mid'
        midi = pretty_midi.PrettyMIDI(str(midi_path))
        voices = voices_by_song[song]
        if set(TRACKS) - {note.category for note in reference_notes(midi, voices)}:
            continue
        wav = dataset / 'RWC-P' / f'{song}.wav'
        beats = dataset / BEAT_PATH / f'{song}.csv'
        info = sf.info(wav)
        lo, hi = float(row['audio_start']), min(float(row['audio_end']), info.duration)
        excluded = EXCLUDED.get(song, [])
        start, end = window([float(beat['t']) for beat in rows(beats)], lo, hi, excluded)
        by_drum[row['DrumInformation']].append(song)
        entries.append({
            'id': song, 'drum_information': row['DrumInformation'],
            'center_seconds': [start, end],
            'input_frames': [round((start - 1) * info.samplerate), round((end + 1) * info.samplerate)],
            'sample_rate': info.samplerate, 'excluded_seconds': excluded, 'vocal_names': sorted(voices),
            'audio': str(wav.relative_to(dataset)), 'audio_sha256': digest(wav),
            'midi': str(midi_path.relative_to(dataset)), 'midi_sha256': digest(midi_path),
            'beats': str(beats.relative_to(dataset)), 'beats_sha256': digest(beats),
            'offset': estimate_offset(wav, midi, voices, lo, hi),
        })
        print(f'Frozen inputs processed: {len(entries)}', flush=True)
    if Counter({name: len(ids) for name, ids in by_drum.items()}) != EXPECTED:
        raise ValueError('Song pool differs from the RWC-P spot check')
    tuning, pilot = split_songs(by_drum)
    for entry in entries:
        entry['split'] = 'tuning' if entry['id'] in tuning else 'test'
    return {'version': 1, 'seed': SEED, 'pilot_ids': pilot, 'songs': entries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    if args.manifest.exists() or args.manifest.with_suffix('.sha256').exists():
        raise FileExistsError('Preserving the frozen manifest')
    manifest = build(args.dataset)
    with args.manifest.open('x', encoding='utf-8') as target:
        target.write(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    with args.manifest.with_suffix('.sha256').open('x', encoding='utf-8') as target:
        target.write(f'{digest(args.manifest)}  {args.manifest.name}\n')


if __name__ == '__main__':
    main()
