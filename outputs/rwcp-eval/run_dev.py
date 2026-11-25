"""Freeze v2 offsets and run only the 22 RWC-P tuning songs."""
import argparse
from collections import Counter
from fractions import Fraction
import fcntl
from itertools import combinations
import os
from pathlib import Path
import platform
from statistics import mean
import subprocess
import time

import numpy as np
import pretty_midi
from scipy.ndimage import gaussian_filter1d
import soundfile as sf

from prepare import HOP, RATE, STEP, digest, reference_notes, track_name
from run_pilot import (FIXED_ROUTES, ROOT, assets, pilot_songs, predictions,
                       prepare_clip, read_json, run_clip, verify_hash, write_json)
from score import pool, score


MANIFEST_SHA = '21a9a1879f33ec84d2191b3deab083f9f6cbe5ef0c0e887f366c0dc1578ff00e'
VERSION = 'rwcp-offset-v2'
GOOD_OUTPUTS = {'ok', 'empty'}
CONFIDENT = {'applied', 'dead_zone'}
ROUTE_STAGES = {
    'P1': ('decode-mt3-mix', 'mt3-mix'),
    'P2': ('sw', 'transkun-piano'),
    'P3': ('transkun-mix',),
    'B1': ('decode-mt3-mix', 'mt3-mix'),
    'B2': ('decode-mu', 'mu-mix'),
    'B5': ('sw', 'decode-mt3-bass', 'mt3-bass'),
    'B7': ('sw', 'decode-mu', 'mu-mix', 'bass-octave'),
    'D1': ('decode-mt3-mix', 'mt3-mix'),
    'D2': ('decode-mu', 'mu-mix'),
    'D3': ('sw', 'decode-mt3-drums', 'mt3-drums'),
    'D4': ('sw', 'adtof-drums'),
}


def alignment_v2(onsets, envelope):
    """Input timestamps are relative to the WAV crop including its two context margins."""
    lags = np.arange(-25, 26)
    indices = np.unique(np.rint(np.asarray(onsets) / STEP).astype(int))
    pulses = np.zeros(len(envelope))
    pulses[indices[(indices >= 0) & (indices < len(pulses))]] = 1
    pulses = gaussian_filter1d(pulses, 1.3)
    frames = np.arange(31, len(pulses) - 31)
    x = pulses[frames]
    env = gaussian_filter1d(np.asarray(envelope, dtype=float), 1.)
    if len(frames) < 100 or not x.any():
        return {'seconds': 0., 'status': 'insufficient_support'}
    x -= x.mean()
    y = env[frames + lags[:, None]]
    y -= y.mean(axis=1, keepdims=True)
    norm = np.linalg.norm(x) * np.linalg.norm(y, axis=1)
    if not norm.any():
        return {'seconds': 0., 'status': 'insufficient_support'}
    corr = (y @ x) / np.maximum(norm, 1e-12)
    narrow = np.flatnonzero(np.abs(lags) <= 10)
    best = min(narrow, key=lambda i: (-corr[i], abs(lags[i]), lags[i]))
    outside_peak = np.abs(lags - lags[best]) > 3
    peak = float(corr[best])
    margin = peak - float(max(corr[narrow[outside_peak[narrow]]]))
    calibrated = float(lags[best] * STEP) - .020
    if peak < .30:
        status = 'weak_peak'
    elif abs(lags[best]) == 10:
        status = 'search_edge'
    elif margin < .05:
        status = 'ambiguous'
    else:
        status = 'applied' if abs(calibrated) >= .050 else 'dead_zone'
    return {
        'seconds': calibrated if status == 'applied' else 0.,
        'status': status, 'raw_seconds': float(lags[best] * STEP),
        'calibrated_seconds': calibrated, 'peak': peak, 'margin': margin,
        'periodic_ambiguity': peak - float(max(corr[outside_peak])) < .05,
        'diagnostic_curve': [[float(lag * STEP), float(value)] for lag, value in zip(lags, corr)],
    }


def tuning_songs(manifest):
    pilot = pilot_songs(manifest)
    tuning = [song for song in manifest['songs'] if song['split'] == 'tuning']
    counts = Counter(song['split'] for song in manifest['songs'])
    if len(manifest['songs']) != 72 or counts != {'tuning': 22, 'test': 50}:
        raise ValueError('Expected exactly the original 22 tuning and 50 test songs')
    pilot_ids = {song['id'] for song in pilot}
    return pilot + [song for song in tuning if song['id'] not in pilot_ids]


def estimate(song, dataset, mix):
    import librosa

    start, end = [frame / song['sample_rate'] for frame in song['input_frames']]
    midi_path = dataset / song['midi']
    verify_hash(midi_path, song['midi_sha256'])
    midi = pretty_midi.PrettyMIDI(str(midi_path))
    voices = set(song['vocal_names'])
    times = sorted(n.start - start for track in midi.instruments if track_name(track) not in voices
                   for n in track.notes if start <= n.start < end)
    onsets = [t for i, t in enumerate(times) if i == 0 or t - times[i - 1] >= .01]
    audio, rate = sf.read(mix, dtype='float32', always_2d=True)
    mono = librosa.resample(audio.mean(axis=1), orig_sr=rate, target_sr=RATE)
    envelope = librosa.onset.onset_strength(y=mono, sr=RATE, hop_length=HOP, n_fft=1024)
    return alignment_v2(onsets, envelope)


def score_route(reference, predicted, category, center, start, delay):
    notes = [note for note in predicted if note.category == category]
    return {'status': 'ok' if notes else 'empty',
            'uncorrected': score(reference, notes, category, center, start, 0.),
            'corrected': score(reference, notes, category, center, start, delay)}


def route_scores(song, dataset, products, stages, duration, delay):
    path = dataset / song['midi']
    verify_hash(path, song['midi_sha256'])
    reference = list(reference_notes(pretty_midi.PrettyMIDI(str(path)), set(song['vocal_names'])))
    center = song['center_seconds']
    start = song['input_frames'][0] / song['sample_rate']
    gate = read_json(products['piano-gate'] / 'gate.json') if products.get('piano-gate') else None
    routes, parsed = {}, {}
    for route, (category, stage) in FIXED_ROUTES.items():
        if route == 'P5' and gate:
            stage = FIXED_ROUTES[gate['route']][1]
        if not products.get(stage):
            routes[route] = {'status': 'unavailable', 'stage': stage}
            continue
        try:
            if stage not in parsed:
                parsed[stage] = predictions(products[stage], stage, duration)
        except (OSError, ValueError, KeyError) as error:
            routes[route] = {'status': 'failed', 'stage': stage, 'error': str(error)}
            continue
        if route == 'P5':
            dependencies = (*ROUTE_STAGES['P2'], 'piano-gate')
            if gate['route'] == 'P1':
                dependencies += ROUTE_STAGES['P1']
        else:
            dependencies = ROUTE_STAGES[route]
        routes[route] = score_route(reference, parsed[stage], category, center, start, delay)
        routes[route].update(stage=stage, seconds=sum(stages[x]['elapsed_seconds'] for x in dependencies))
    return routes, gate


def f1(counts):
    denominator = 2 * counts['tp'] + counts['fp'] + counts['fn']
    return Fraction(2 * counts['tp'], denominator) if denominator else None


def choose(scores, seconds):
    leader = min(scores, key=lambda route: (-scores[route], route))
    ties = sorted(route for route in scores if scores[leader] - scores[route] < Fraction(1, 50))
    winner = min(ties, key=lambda route: (seconds[route], -scores[route], route))
    return {'winner': winner, 'leader': leader, 'ties': ties}


def finished(item):
    return set(item['routes']) == set(FIXED_ROUTES) and all(
        result['status'] in GOOD_OUTPUTS for result in item['routes'].values())


def summarize(items):
    if len(items) != 22 or len({item['id'] for item in items}) != 22 or not all(map(finished, items)):
        raise ValueError('Selecting winners requires all 22 tuning songs and all routes')
    summary, winners, head_to_head = {}, {}, {}
    for route, (category, _) in FIXED_ROUTES.items():
        rows = [item['routes'][route] for item in items]
        confident = [row for item, row in zip(items, rows) if item['offset']['status'] in CONFIDENT]
        variants = {'uncorrected': (rows, 'uncorrected'), 'corrected': (rows, 'corrected'),
                    'confident': (confident, 'corrected')}
        metrics = ('exact', 'octave_free') if category == 'bass' else ('exact',)
        summary[route] = {label: {metric: pool([r[source] for r in cohort], metric) for metric in metrics}
                          for label, (cohort, source) in variants.items()}
        summary[route].update(empty=sum(row['status'] == 'empty' for row in rows),
                              empty_ids=[item['id'] for item, row in zip(items, rows) if row['status'] == 'empty'],
                              seconds=mean(row['seconds'] for row in rows))
    for category in ('piano', 'bass', 'drums'):
        routes = [route for route, (cat, _) in FIXED_ROUTES.items() if cat == category]
        main = {route: f1(summary[route]['corrected']['exact']) for route in routes}
        if any(value is None for value in main.values()):
            raise ValueError(f'Undefined tuning F1 for {category}')
        winners[category] = choose(main, {route: summary[route]['seconds'] for route in routes})
        pairs = []
        for left, right in combinations(routes, 2):
            counts = dict.fromkeys(('win', 'draw', 'loss', 'undefined'), 0)
            for row in items:
                a, b = (f1(row['routes'][route]['corrected']['exact']) for route in (left, right))
                key = 'undefined' if a is None or b is None else 'win' if a > b else 'loss' if a < b else 'draw'
                counts[key] += 1
            pairs.append({'left': left, 'right': right, **counts})
        head_to_head[category] = pairs
    return {'routes': summary, 'winners': winners, 'head_to_head': head_to_head}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze-offsets', 'run'))
    parser.add_argument('--resources', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--offset-sha256')
    args = parser.parse_args()
    resources, work = args.resources.resolve(), args.work.resolve()
    dataset = resources / 'work/datasets/rwc-p'
    if not work.is_relative_to(resources / 'work') or work.is_relative_to(dataset):
        raise ValueError('Work must be under work/ and outside the dataset')
    manifest = work / 'manifest.json'
    verify_hash(manifest, MANIFEST_SHA)
    songs = tuning_songs(read_json(manifest))
    ids = [song['id'] for song in songs]
    offset_path = work / 'dev-offsets-v2.json'
    for name in ('clips', 'cache'):
        (work / name).mkdir(exist_ok=True)
    with (work / '.pilot.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command == 'freeze-offsets':
            if offset_path.exists():
                raise FileExistsError(offset_path)
            entries = {}
            for song in songs:
                mix, _ = prepare_clip(song, dataset, work / 'clips')
                entries[song['id']] = {'clip_sha256': digest(mix), **estimate(song, dataset, mix)}
            commit = subprocess.check_output(['git', '-C', ROOT, 'rev-parse', 'HEAD'], text=True).strip()
            write_json(offset_path, {'version': VERSION, 'manifest_sha256': MANIFEST_SHA,
                                     'rule_commit': commit, 'offsets': entries})
            print(digest(offset_path), flush=True)
            return 0
        verify_hash(offset_path, args.offset_sha256)
        frozen = read_json(offset_path)
        offsets = frozen['offsets']
        if frozen['version'] != VERSION or frozen['manifest_sha256'] != MANIFEST_SHA or list(offsets) != ids:
            raise ValueError('Offsets must cover exactly the tuning cohort in frozen order')
        os.chdir(resources)
        os.environ['GIT_OPTIONAL_LOCKS'] = '0'
        paths, versions = assets(resources)
        result_path = work / 'dev-results.json'
        result = {'offset_sha256': args.offset_sha256, 'rule_commit': frozen['rule_commit'],
                  'manifest_sha256': MANIFEST_SHA, 'machine': platform.platform(),
                  'versions': versions, 'items': {}}
        if result_path.exists():
            saved = read_json(result_path)
            if any(saved.get(key) != val for key, val in result.items() if key != 'items'):
                raise ValueError('Existing checkpoint belongs to another evaluation')
            if not set(saved['items']) <= set(ids):
                raise ValueError('Unexpected checkpoint song')
            result['items'] = saved['items']
        for song in songs:
            song_id = song['id']
            if song_id in result['items'] and finished(result['items'][song_id]):
                continue
            waiting = time.monotonic()
            while os.getloadavg()[0] > 4:
                print(f'{song_id}: waiting for load {os.getloadavg()[0]:.2f}', flush=True)
                time.sleep(60)
            begin = time.monotonic()
            load = os.getloadavg()[0]
            print(f'{song_id}: start ({load:.2f})', flush=True)
            mix, duration = prepare_clip(song, dataset, work / 'clips')
            offset = offsets[song_id]
            verify_hash(mix, offset['clip_sha256'])
            products, stages = run_clip(mix, duration, work / 'cache', paths, versions)
            routes, gate = route_scores(song, dataset, products, stages, duration, offset['seconds'])
            entry = {'id': song_id, 'center_seconds': song['center_seconds'], 'offset': offset,
                     'load': load, 'wait_seconds': begin - waiting,
                     'elapsed_seconds': time.monotonic() - begin,
                     'stages': stages, 'routes': routes, 'p5': gate}
            result['items'][song_id] = entry
            write_json(result_path, result)
            print(f'{song_id}: {"completed" if finished(entry) else "incomplete"}', flush=True)
        items = list(result['items'].values())
        if len(items) != 22 or not all(map(finished, items)):
            return 1
        result['summary'] = summarize(items)
        write_json(result_path, result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
