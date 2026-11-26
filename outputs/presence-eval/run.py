"""Calibrate on the frozen presence split and evaluate the selected gate once."""
import argparse
from collections import Counter
from dataclasses import replace
import fcntl
import hashlib
import importlib.util
from itertools import product
import json
import os
from pathlib import Path
from pprint import pformat
import re
import subprocess
import sys
import time
from unittest.mock import patch

import mido
import pretty_midi

from audio_midi.evaluate import evaluate
from audio_midi.midi import write_midi
from audio_midi.presence_gate import TRACKS, gate_midi, removes_track, track_features
from audio_midi.quality import read_notes


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'rwcp-eval'))
import run_pilot as pilot
import run_team as team

spec = importlib.util.spec_from_file_location('presence_prepare', HERE / 'prepare.py')
manifest_builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest_builder)
e2e, multi, present = manifest_builder.e2e, manifest_builder.multi, manifest_builder.present


ROOT = HERE.parents[1]
MANIFEST_SHA = '0a41021d43983fed2738f98931e6c4f712ce4ae185f89c0b1947f7a7fcc4b444'
SPLIT_SHA = '3cdcce57040ff50d90c3d5ec5415e045e0ec09d183e92625e75a26a584d6cb61'
RECIPE = ['P2', 'B2', 'D2']
FEATURES = {
    'notes_per_minute': (0, 4, 8, 16, 24, 40, 60, 80, 100, 120, 150, 200),
    'distinct_pitches': (0, 2, 3, 4, 5, 6, 8, 12, 16, 24),
}
RULE_TYPES = (('notes_per_minute',), ('distinct_pitches',), tuple(FEATURES))


class PendingInference(Exception):
    pass


def committed(path):
    relative = path.relative_to(ROOT)
    frozen = subprocess.check_output(['git', 'show', f'HEAD:{relative}'], cwd=ROOT)
    if frozen != path.read_bytes():
        raise ValueError(f'Requires a Git-frozen copy of {relative}')


def selections(split):
    manifest = HERE / 'manifest.json'
    assignments = HERE / 'split.json'
    for path, expected in ((manifest, MANIFEST_SHA), (assignments, SPLIT_SHA)):
        committed(path)
        pilot.verify_hash(path, expected)
    index = pilot.read_json(assignments)['assignments']
    return [row for row in pilot.read_json(manifest)['samples'] if index[row['id']] == split]


def wait_for_capacity(stage):
    # The coordinator replaced the swap threshold for serial inference.
    # Each stage finishes before the next launch. Below 20% pause the queue.
    while not capacity(stage):
        time.sleep(45)


def capacity(stage):
    uptime = subprocess.check_output(['uptime'], text=True).strip()
    swap = subprocess.check_output(['sysctl', 'vm.swapusage'], text=True).strip()
    pressure = subprocess.check_output(['memory_pressure', '-Q'], text=True).strip()
    match = re.search(r'System-wide memory free percentage: (\d+)%', pressure)
    if match is None:
        raise ValueError(f'Cannot read system memory pressure: {pressure}')
    available = int(match[1])
    ready = os.getloadavg()[0] <= 6 and available >= 30
    decision = 'launch' if ready else 'pause (<20% free)' if available < 20 else 'wait'
    print(f'{stage}: {decision}\n{uptime}\n{pressure}\n{swap}', flush=True)
    return ready


def scheduled(main_cache, allow_inference):
    run_stage = pilot.scheduled_stage

    def stage(cache, name, input_hash, signature, outputs, command):
        version = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
        dirname = f'{name}-{input_hash}-{version}'
        main = main_cache / dirname
        if main.exists():
            return pilot.stage_under_lock(main_cache, main, name, input_hash,
                                          signature, outputs, command)
        if not (cache / dirname).exists() and name in {'sw', 'transkun-piano', 'mu-mix'}:
            if not allow_inference:
                raise PendingInference(f'{name}: cache miss (cache-only)')
            wait_for_capacity(name)
        return run_stage(cache, name, input_hash, signature, outputs, command)

    return stage


def find_e2e_midi(row, runs):
    summary = next(item for item in pilot.read_json(HERE.parent / 'e2e-eval/results.json')['items']
                   if item['id'] == row['id'])
    directory = runs / summary['attempt']
    receipt = pilot.read_json(directory / 'receipt.json')
    path = directory / 'noto.mid'
    if (receipt['status'] != 'ok' or receipt['input_sha256'] != row['audio_sha256']
            or receipt['output_sha256'] != summary['midi_sha256']):
        raise ValueError(f'{row["id"]}: archived S3 receipt changed')
    pilot.verify_hash(path, summary['midi_sha256'])
    return path, receipt['duration_seconds']


def infer_new(row, dataset, work, assets):
    directory = work / row['id']
    directory.mkdir(exist_ok=True)
    path = directory / 's3.mid'
    receipt = directory / 'prediction.json'
    mix, duration = pilot.prepare_clip(row, dataset, work / 'clips')
    clip_sha = pilot.digest(mix)
    if receipt.exists():
        previous = pilot.read_json(receipt)
        if previous['clip_sha256'] != clip_sha:
            raise ValueError('Cached S3 input changed')
        pilot.verify_hash(path, previous['midi_sha256'])
        return path, duration
    products, stages = pilot.run_clip(
        mix, duration, work / 'cache', *assets, needed=team.needed_stages({'S3': RECIPE}),
    )
    routes = team.track_outputs({'S3': RECIPE}, products, duration)
    if set(routes) != set(RECIPE):
        raise RuntimeError(f'{row["id"]}: incomplete S3 stages: {stages}')
    notes = [note for route in RECIPE for note in routes[route][0]]
    if notes:
        write_midi(notes, path)
        if len(read_notes(path)) != len(notes):
            raise ValueError(f'{row["id"]}: MIDI round-trip changed note count')
    else:
        midi = mido.MidiFile()
        midi.add_track('Conductor')
        midi.save(path)
    pilot.write_json(receipt, {'clip_sha256': clip_sha, 'midi_sha256': pilot.digest(path)})
    return path, duration


def inputs(rows, args, dataset):
    assets = None
    observations = {}
    for row in rows:
        sample_id = row['id']
        try:
            if row['source'] == 'e2e':
                path, duration = find_e2e_midi(row, args.e2e_runs)
            else:
                if assets is None:
                    assets = pilot.assets(ROOT)
                path, duration = infer_new(row, dataset, args.work, assets)
        except PendingInference as error:
            print(f'{sample_id}: pending ({error})', flush=True)
            continue
        observations[sample_id] = (path, duration, track_features(mido.MidiFile(path), duration))
    return observations


def calibrate(rows, observations):
    rules, comparison = {}, {}
    for name in TRACKS:
        examples = [(row['presence'][name], observations[row['id']][2][name]) for row in rows]
        positives = sum(present for present, _ in examples)
        negatives = len(examples) - positives
        candidates = []
        for keys in RULE_TYPES:
            options = []
            for limits in product(*(FEATURES[key] for key in keys)):
                thresholds = dict(zip(keys, limits))
                deleted = [(present, f['note_count']) for present, f in examples
                           if removes_track(f, thresholds)]
                options.append({
                    'thresholds': thresholds,
                    'false_deletions': sum(present for present, _ in deleted),
                    'negative_tracks_removed': sum(not present for present, _ in deleted),
                    'false_notes_removed': sum(notes for present, notes in deleted if not present),
                })
            candidates.append(min((opt for opt in options if not opt['false_deletions']),
                                  key=lambda opt: (-opt['false_notes_removed'],
                                                   -opt['negative_tracks_removed'],
                                                   tuple(opt['thresholds'].values()))))
        winner = min(candidates, key=lambda opt: (-opt['false_notes_removed'],
                                                -opt['negative_tracks_removed'],
                                                len(opt['thresholds'])))
        rules[name] = winner['thresholds'] if positives >= 3 and negatives >= 3 else {}
        comparison[name] = {'positives': positives, 'negatives': negatives, 'candidates': candidates}
    return rules, comparison


def raw_reference(row, dataset, items):
    if row['source'] == 'e2e':
        path = items / row['reference']
        pilot.verify_hash(path, row['reference_sha256'])
        return multi.ref_notes(path, row['reference_source'])
    path = dataset / row['midi']
    pilot.verify_hash(path, row['midi_sha256'])
    return list(pilot.reference_notes(pretty_midi.PrettyMIDI(str(path)), set(row['vocal_names'])))


def score_item(row, observed, reference, rules, work, rwc_kit=False):
    path, duration = observed
    gated, decisions = gate_midi(path, work / f'{row["id"]}.mid', duration, rules)
    center = row['seconds']
    if present(reference, center) != row['presence']:
        raise ValueError(f'{row["id"]}: reference presence differs from the freeze')
    scores = {}
    for label, prediction in (('off', read_notes(path)), ('on', read_notes(gated))):
        if rwc_kit:
            scores[label] = {name: team.score_route(reference, prediction, name, center,
                                                    row['input_start'], 0)['exact'] for name in TRACKS}
        else:
            start, end = center
            normalized = [replace(note, onset=note.onset - start)
                          for note in reference if start <= note.onset < end]
            raw = evaluate(normalized, prediction)
            scores[label] = {name: raw[name] for name in TRACKS}
    return {'id': row['id'], 'source': row['source'], 'present': row['presence'],
            'gate': decisions, 'scores': scores, 'before_sha256': pilot.digest(path),
            'after_sha256': pilot.digest(gated)}


def original_tests(resources, rules, work):
    original = resources / 'work/rwcp-eval'
    manifest = original / 'manifest.json'
    pilot.verify_hash(manifest, team.MANIFEST_SHA)
    historical = pilot.read_json(original / 'team-results.json')
    dataset = resources / 'work/datasets/rwc-p'
    result = []
    for row in team.test_songs(pilot.read_json(manifest)):
        item = historical['items'][row['id']]['combinations']['S3']
        path = original / 'team-midi' / row['id'] / 'S3.mid'
        pilot.verify_hash(path, item['midi_sha256'])
        reference = raw_reference({**row, 'source': 'RWC-P original'}, dataset, None)
        first, last = row['input_frames']
        center = row['center_seconds']
        scored = score_item({
            **row, 'seconds': center, 'input_start': first / row['sample_rate'],
            'source': 'RWC-P original', 'presence': present(reference, center),
        }, (path, (last - first) / row['sample_rate']), reference, rules, work, rwc_kit=True)
        for name in TRACKS:
            if scored['scores']['off'][name] != item['scores'][name]['exact']:
                raise ValueError(f'{row["id"]}: baseline score changed for {name}')
        result.append(scored)
    return result


def summary(rows):
    result = {}
    for name in (*TRACKS, 'overall'):
        names = TRACKS if name == 'overall' else (name,)
        tracks = [(row['present'][track], row['gate'][track]) for row in rows for track in names]
        positives = sum(actual for actual, _ in tracks)
        negatives = len(tracks) - positives
        result[name] = {}
        for enabled, label in ((False, 'off'), (True, 'on')):
            counts = Counter()
            for row in rows:
                for track in names:
                    counts.update({k: row['scores'][label][track][k] for k in ('tp', 'fp', 'fn')})
                    if not row['present'][track]:
                        counts['empty_track_fp'] += row['scores'][label][track]['fp']
            tp, fp, fn = (counts[key] for key in ('tp', 'fp', 'fn'))
            called_absent = [actual for actual, gate in tracks
                             if not gate['features']['note_count'] or enabled and gate['suppressed']]
            detected = sum(not actual for actual in called_absent)
            deleted = sum(actual and enabled and gate['suppressed'] for actual, gate in tracks)
            result[name][label] = {
                **counts, 'positive_tracks': positives, 'negative_tracks': negatives,
                'absent_detected': detected, 'absent_false_alarms': len(called_absent) - detected,
                'false_deletions': deleted, 'f1': ratio(2 * tp, 2 * tp + fp + fn),
                'absence_precision': ratio(detected, len(called_absent)),
                'absence_recall': ratio(detected, negatives),
                'false_deletion_rate': ratio(deleted, positives),
            }
    return result


def ratio(a, b):
    return a / b if b else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('tuning', 'test'))
    parser.add_argument('--resources', required=True, type=Path)
    parser.add_argument('--e2e-runs', required=True, type=Path)
    parser.add_argument('--work', default=ROOT / 'work/presence-eval', type=Path)
    parser.add_argument('--allow-inference', action='store_true')
    args = parser.parse_args()
    args.work = args.work.resolve()
    args.work.mkdir(parents=True, exist_ok=True)
    if args.phase == 'test':
        for path in (HERE / 'rules.json', ROOT / 'src/audio_midi/presence_gate.py', Path(__file__).resolve()):
            committed(path)
        from audio_midi.presence_gate import RULES
        freeze = pilot.read_json(HERE / 'rules.json')
        if (freeze['rules'] != RULES or freeze['manifest_sha256'] != MANIFEST_SHA
                or freeze['split_sha256'] != SPLIT_SHA):
            raise ValueError('Frozen rules differ from the application or split')
        pilot.verify_hash(args.work / 'tuning-results.json', freeze['tuning_results_sha256'])
    result_file = args.work / f'{args.phase}-results.json'
    if result_file.exists():
        raise FileExistsError(f'Preserving frozen evaluation: {result_file}')
    for path in ('clips', 'cache', 'gated'):
        (args.work / path).mkdir(exist_ok=True)
    dataset = args.resources / 'work/datasets/rwc-p'
    rows = selections(args.phase)
    if args.allow_inference:
        print('2026-11-26 coordinator update: serial only, launch with 1-minute load <= 6 '
              'and system free memory >= 30%. Below 20% pause the queue after the current stage. '
              'Swap is recorded for diagnostics.', flush=True)
    compute = scheduled(args.resources / 'work/rwcp-eval/cache', args.allow_inference)
    with (args.work / 'inference.lock').open('a') as lock, patch.object(pilot, 'scheduled_stage', compute):
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        observations = inputs(rows, args, dataset)
        if len(observations) != len(rows):
            print(f'{args.phase}: {len(observations)}/{len(rows)} ready; no evaluation performed')
            return 2
        if args.phase == 'tuning':
            rules, comparison = calibrate(rows, observations)
            result = {'rules': rules, 'comparison': comparison, 'manifest_sha256': MANIFEST_SHA,
                      'split_sha256': SPLIT_SHA,
                      'input_midi_sha256': {k: pilot.digest(v[0]) for k, v in observations.items()}}
            print(f'RULES = {pformat(rules)}')
        else:
            items = args.resources / e2e.ITEMS_RELATIVE
            scored = [score_item(row, observations[row['id']][:2],
                                 raw_reference(row, dataset, items), RULES, args.work / 'gated')
                      for row in rows]
            original = original_tests(args.resources, RULES, args.work / 'gated')
            result = {'test_summary': summary(scored), 'original_summary': summary(original),
                      'e2e_test_summary': summary([row for row in scored if row['source'] == 'e2e']),
                      'items': scored, 'original': original,
                      'rules_sha256': pilot.digest(HERE / 'rules.json')}
        pilot.write_json(result_file, result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
