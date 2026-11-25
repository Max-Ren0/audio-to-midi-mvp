"""Run frozen RWC-P combinations on the sealed test cohort once."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import os
from pathlib import Path
import platform
import re
from statistics import mean
import subprocess
import time

import numpy as np
import pretty_midi

from audio_midi.midi import write_midi
from audio_midi.quality import read_notes
from prepare import digest, reference_notes
from presence import note_counts, THRESHOLDS
from run_dev import (CONFIDENT, MANIFEST_SHA, ROUTE_STAGES, VERSION, estimate,
                     score_route, tuning_songs)
from run_pilot import (FIXED_ROUTES, HERE, ROOT, assets, predictions, prepare_clip,
                       read_json, run_clip, verify_hash, write_json)
from score import pool


TRACKS = ('piano', 'bass', 'drums')
COMBOS = ('S1', 'S3', 'S5', 'S6')
BASE_ROUTES = {'S1': ['P1', 'B1', 'D1'], 'S3': ['P2', 'B2', 'D2']}
BOOTSTRAP_SEED = 20261126
BOOTSTRAP_REPLICATES = 10000
COMPARE = (('S5', 'S3'), ('S5', 'S1'), ('S6', 'S3'), ('S6', 'S1'), ('S6', 'S5'))
RULE_FILES = (
    *(HERE / name for name in ('prepare.py', 'run_team.py', 'run_dev.py', 'run_pilot.py',
                              'score.py', 'presence.py', 'specialists.py')),
    *(ROOT / 'src/audio_midi' / name for name in ('evaluate.py', 'midi.py', 'quality.py')),
)


def config_from_presence(presence):
    tracks = presence['tracks']
    if presence['version'] != 1 or set(tracks) != set(TRACKS):
        raise ValueError('Invalid presence configuration')
    routes = [tracks[category]['route'] for category in TRACKS]
    thresholds = {category: tracks[category]['threshold'] for category in TRACKS}
    if any(FIXED_ROUTES[route][0] != category for route, category in zip(routes, TRACKS)):
        raise ValueError('Mismatched route and track')
    if any(threshold not in THRESHOLDS for threshold in thresholds.values()):
        raise ValueError('Unknown presence threshold')
    return {'version': 1, 'offset_rule': VERSION, 'recipes': {**BASE_ROUTES, 'S5': routes, 'S6': routes},
            'thresholds': thresholds, 'bootstrap_seed': BOOTSTRAP_SEED,
            'bootstrap_replicates': BOOTSTRAP_REPLICATES}


def committed(path):
    relative = path.relative_to(ROOT)
    head = subprocess.check_output(['git', '-C', ROOT, 'show', f'HEAD:{relative}'])
    if head != path.read_bytes():
        raise ValueError(f'Uncommitted evaluation configuration: {relative}')


def test_songs(manifest):
    tuning_songs(manifest)  # Validate the original disjoint 22/50 allocation.
    return [song for song in manifest['songs'] if song['split'] == 'test']


def needed_stages(recipes):
    names = set()
    for route in {route for recipe in recipes.values() for route in recipe}:
        if route == 'P5':
            names.update((*ROUTE_STAGES['P1'], *ROUTE_STAGES['P2'], 'piano-gate'))
        else:
            names.update(ROUTE_STAGES[route])
    return names


def should_suppress(notes, threshold, center, start):
    return sum(center[0] <= note.onset + start < center[1] for note in notes) < threshold


def bootstrap(counts):
    """Use the same random song draw for every combo to preserve paired comparisons."""
    n = len(counts['S1'])
    if not n or any(len(series) != n for series in counts.values()):
        raise ValueError('Need paired song counts for bootstrap')
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draw = rng.integers(0, n, size=(BOOTSTRAP_REPLICATES, n))
    estimates = {}
    for combo, series in counts.items():
        values = np.asarray([[row[k] for k in ('tp', 'fp', 'fn')] for row in series])
        tp, fp, fn = values[draw].sum(axis=1).T
        num = 2 * tp
        den = num + fp + fn
        estimates[combo] = np.divide(num, den, out=np.full(len(draw), np.nan), where=den != 0)

    def interval(values):
        usable = values[np.isfinite(values)]
        return np.quantile(usable, [.025, .975]).tolist() if len(usable) else None

    return {'absolute': {combo: interval(values) for combo, values in estimates.items()},
            'deltas': {f'{a}-{b}': interval(estimates[a] - estimates[b]) for a, b in COMPARE}}


def track_outputs(recipes, products, duration):
    parsings, routes = {}, {}
    gate = read_json(products['piano-gate'] / 'gate.json') if products.get('piano-gate') else None
    for route in sorted({route for recipe in recipes.values() for route in recipe}):
        category, stage = FIXED_ROUTES[route]
        if route == 'P5' and gate:
            stage = FIXED_ROUTES[gate['route']][1]
        path = products.get(stage)
        if path is None:
            continue
        if stage not in parsings:
            parsings[stage] = predictions(path, stage, duration)
        if route == 'P5':
            dependencies = {*ROUTE_STAGES['P2'], 'piano-gate'}
            if gate['route'] == 'P1':
                dependencies.update(ROUTE_STAGES['P1'])
        else:
            dependencies = set(ROUTE_STAGES[route])
        routes[route] = ([note for note in parsings[stage] if note.category == category], dependencies)
    return routes


def publish_combo(path, notes):
    if not notes:
        path.unlink(missing_ok=True)
        return [], None
    scratch = path.with_suffix('.tmp.mid')
    write_midi(notes, scratch)
    saved = read_notes(scratch)
    if len(saved) != len(notes):
        raise ValueError('Published MIDI has a different note count')
    scratch.replace(path)
    return saved, digest(path)


def evaluate_song(song, offset, dataset, work, paths, versions, config):
    began = time.monotonic()
    uptime = subprocess.check_output(['uptime'], text=True).strip()
    song_id = song['id']
    mix, duration = prepare_clip(song, dataset, work / 'clips')
    verify_hash(mix, offset['clip_sha256'])
    print(f'{song_id}: start', flush=True)
    print(f'{song_id}: {uptime}', flush=True)
    recipes = config['recipes']
    products, stages = run_clip(mix, duration, work / 'cache', paths, versions, needed=needed_stages(recipes))
    routes = track_outputs(recipes, products, duration)
    midi_path = dataset / song['midi']
    verify_hash(midi_path, song['midi_sha256'])
    midi = pretty_midi.PrettyMIDI(str(midi_path))
    reference = list(reference_notes(midi, set(song['vocal_names'])))
    center = song['center_seconds']
    input_start = song['input_frames'][0] / song['sample_rate']
    outdir = work / 'team-midi' / song_id
    outdir.mkdir(parents=True, exist_ok=True)
    combinations = {}
    for combo, recipe in recipes.items():
        if any(route not in routes for route in recipe):
            combinations[combo] = {'status': 'failed', 'reason': 'required_stage_unavailable'}
            continue
        publish_start = time.monotonic()
        emitted, model_empty, suppressed, used_stages = [], [], [], set()
        for category, route in zip(TRACKS, recipe):
            notes, dependencies = routes[route]
            used_stages.update(dependencies)
            if not notes:
                model_empty.append(category)
            if combo == 'S6' and should_suppress(notes, config['thresholds'][category], center, input_start):
                if notes:
                    suppressed.append(category)
                continue
            emitted.extend(notes)
        saved, checksum = publish_combo(outdir / f'{combo}.mid', emitted)
        publish_seconds = time.monotonic() - publish_start
        scores = {category: score_route(reference, saved, category, center, input_start, offset['seconds'])
                  for category in TRACKS}
        combinations[combo] = {
            'status': 'ok' if checksum else 'empty', 'midi_sha256': checksum, 'scores': scores,
            'model_empty_tracks': model_empty, 'gated_tracks': suppressed,
            'seconds': sum(stages[stage]['elapsed_seconds'] for stage in used_stages) + publish_seconds,
            'publish_seconds': publish_seconds,
        }
    return {'id': song_id, 'offset': offset, 'center_seconds': center, 'stages': stages,
            'combinations': combinations, 'uptime': uptime, 'wall_seconds': time.monotonic() - began}


def finished(item):
    return set(item['combinations']) == set(COMBOS) and all(
        row['status'] in ('ok', 'empty') for row in item['combinations'].values())


def summarize(items):
    if len(items) != 50 or len({item['id'] for item in items}) != 50 or not all(map(finished, items)):
        raise ValueError('Need exactly 50 paired test songs and all combinations')
    summary = {}
    for combo in COMBOS:
        rows = [item['combinations'][combo] for item in items]
        tracks = {}
        for category in TRACKS:
            scores = [row['scores'][category] for row in rows]
            confident = [score for item, score in zip(items, scores) if item['offset']['status'] in CONFIDENT]
            cohort = {'uncorrected': (scores, 'uncorrected'), 'corrected': (scores, 'corrected'),
                      'confident': (confident, 'corrected')}
            metrics = ('exact', 'octave_free') if category == 'bass' else ('exact',)
            tracks[category] = {variant: {metric: pool([s[source] for s in subset], metric)
                                         for metric in metrics}
                                for variant, (subset, source) in cohort.items()}
            observations = [note_counts(s['corrected']) for s in scores]
            tracks[category].update(
                empty=sum(score['status'] == 'empty' for score in scores),
                model_empty=sum(category in row['model_empty_tracks'] for row in rows),
                gated=sum(category in row['gated_tracks'] for row in rows),
                gated_positive=sum(ref > 0 and category in row['gated_tracks']
                                   for (ref, _), row in zip(observations, rows)),
                reference_absent=sum(ref == 0 for ref, _ in observations),
                absent_false_notes=sum(pred for ref, pred in observations if not ref),
                absent_false_tracks=sum(ref == 0 and pred > 0 for ref, pred in observations),
            )
        summary[combo] = {'tracks': tracks, 'success': sum(row['status'] == 'ok' for row in rows),
                          'mean_seconds': mean(row['seconds'] for row in rows),
                          'total_seconds': sum(row['seconds'] for row in rows)}
    intervals = {category: bootstrap({combo: [
        item['combinations'][combo]['scores'][category]['corrected']['exact'] for item in items
    ] for combo in COMBOS}) for category in TRACKS}
    return {'combinations': summary, 'intervals': intervals}


def swap_free_gib(report):
    match = re.search(r'\bfree\s*=\s*([\d.]+)\s*([BKMGT])', report)
    return float(match[1]) * 1024 ** ('BKMGT'.index(match[2]) - 3) if match else None


def machine_capacity():
    swap_report = pressure_report = ''
    if platform.system() == 'Darwin':
        swap_report = subprocess.run(['/usr/sbin/sysctl', 'vm.swapusage'], text=True,
                                     capture_output=True).stdout.strip()
        pressure_report = subprocess.run(['/usr/bin/memory_pressure', '-Q'], text=True,
                                         capture_output=True).stdout.strip()
    match = re.search(r'System-wide memory free percentage: (\d+)%', pressure_report)
    return {'load': os.getloadavg()[0], 'swap_free_gib': swap_free_gib(swap_report),
            'pressure_free_pct': int(match[1]) if match else None,
            'swap_report': swap_report, 'pressure_report': pressure_report}


def batch_jobs(requested, capacity):
    free, swap = capacity['pressure_free_pct'], capacity['swap_free_gib']
    can_parallel = (capacity['load'] <= 7 and free is not None and free >= 25
                    and swap is not None and swap >= 1.5)
    return 2 if requested == 2 and can_parallel else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze-combinations', 'freeze-offsets', 'run'))
    parser.add_argument('--resources', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--offset-sha256')
    parser.add_argument('--jobs', type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    resources, work = args.resources.resolve(), args.work.resolve()
    dataset = resources / 'work/datasets/rwc-p'
    if not work.is_relative_to(resources / 'work') or work.is_relative_to(dataset):
        raise ValueError('Work must be under work/ and outside the dataset')
    presence_path = HERE / 'presence-config.json'
    recipe_path = HERE / 'team-config.json'
    committed(presence_path)
    expected = config_from_presence(read_json(presence_path))
    if args.command == 'freeze-combinations':
        if recipe_path.exists():
            raise FileExistsError(recipe_path)
        write_json(recipe_path, expected)
        return 0
    for path in (recipe_path, *RULE_FILES):
        committed(path)
    config = read_json(recipe_path)
    if config != expected:
        raise ValueError('Combination and presence freezes do not agree')
    identity = {f'{field}_sha256': digest(path) for field, path in
                [('combinations', recipe_path), ('presence', presence_path)]}
    identity['rule_hashes'] = {str(path.relative_to(ROOT)): digest(path) for path in RULE_FILES}
    manifest_path = work / 'manifest.json'
    verify_hash(manifest_path, MANIFEST_SHA)
    songs = test_songs(read_json(manifest_path))
    offset_path = work / 'team-offsets-v2.json'
    with (work / '.pilot.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command == 'freeze-offsets':
            if offset_path.exists():
                raise FileExistsError(offset_path)
            for name in ('clips', 'cache'):
                (work / name).mkdir(exist_ok=True)
            offsets = {}
            for song in songs:
                mix, _ = prepare_clip(song, dataset, work / 'clips')
                offsets[song['id']] = {'clip_sha256': digest(mix), **estimate(song, dataset, mix)}
            freeze_commit = subprocess.check_output(['git', '-C', ROOT, 'rev-parse', 'HEAD'], text=True).strip()
            write_json(offset_path, {**identity, 'manifest_sha256': MANIFEST_SHA,
                                     'freeze_commit': freeze_commit, 'offsets': offsets})
            print(digest(offset_path), flush=True)
            return 0
        verify_hash(offset_path, args.offset_sha256)
        frozen = read_json(offset_path)
        if any(frozen.get(key) != val for key, val in identity.items()) or frozen['manifest_sha256'] != MANIFEST_SHA:
            raise ValueError('Offsets belong to a different test evaluation')
        offsets = frozen['offsets']
        if set(offsets) != {song['id'] for song in songs}:
            raise ValueError('Offsets must cover the 50 test songs exclusively')
        os.chdir(resources)
        os.environ['GIT_OPTIONAL_LOCKS'] = '0'
        paths, versions = assets(resources)
        result_path = work / 'team-results.json'
        identity.update(manifest_sha256=MANIFEST_SHA, offset_sha256=args.offset_sha256, versions=versions,
                        freeze_commit=frozen['freeze_commit'])
        result = {**identity, 'items': {}, 'batches': []}
        if result_path.exists():
            result = read_json(result_path)
            if any(result.get(key) != val for key, val in identity.items()) or not set(result['items']) <= set(offsets):
                raise ValueError('Existing test checkpoint belongs to another evaluation')
        todo = [song for song in songs if song['id'] not in result['items'] or
                not finished(result['items'][song['id']])]
        while todo:
            capacity = machine_capacity()
            while capacity['load'] > 8:
                print(f'Waiting for load {capacity}', flush=True)
                time.sleep(60)
                capacity = machine_capacity()
            jobs = min(batch_jobs(args.jobs, capacity), len(todo))
            checks = [capacity]
            if jobs == 2:
                checks.append(machine_capacity())
                jobs = batch_jobs(2, checks[-1])
            print(f'Launch {[s["id"] for s in todo[:jobs]]} with {jobs} slot(s): {checks}', flush=True)
            batch, todo = todo[:jobs], todo[jobs:]
            began = time.monotonic()
            failed = False
            with ThreadPoolExecutor(max_workers=jobs) as executor:
                futures = {executor.submit(evaluate_song, song, offsets[song['id']], dataset, work,
                                           paths, versions, config): song['id'] for song in batch}
                for future in as_completed(futures):
                    song_id = futures[future]
                    try:
                        item = future.result()
                    except (OSError, ValueError, KeyError, RuntimeError) as error:
                        item = {'id': song_id, 'combinations': {}, 'error': str(error)}
                    result['items'][song_id] = item
                    write_json(result_path, result)
                    failed |= not finished(item)
                    print(f'{song_id}: {"completed" if finished(item) else "incomplete"}', flush=True)
            result['batches'].append({'capacity_checks': checks, 'jobs': jobs, 'songs': [s['id'] for s in batch],
                                      'elapsed_seconds': time.monotonic() - began})
            write_json(result_path, result)
            if failed:
                return 1
        result['summary'] = summarize([result['items'][song['id']] for song in songs])
        write_json(result_path, result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
