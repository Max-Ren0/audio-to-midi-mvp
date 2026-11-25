"""Calibrate a conservative note-count gate on the 22 tuning songs only."""
import argparse
from pathlib import Path

from run_dev import MANIFEST_SHA, summarize, tuning_songs
from run_pilot import read_json, verify_hash, write_json


THRESHOLDS = (0, 2, 4, 8, 16)
MIN_NEGATIVES = 3


def choose_threshold(observations):
    """Each observation is the reference and predicted onsets in the center window."""
    positive = sum(ref > 0 for ref, _ in observations)
    negative = len(observations) - positive
    scores = []
    for threshold in THRESHOLDS:
        deleted = sum(ref > 0 and 0 < pred < threshold for ref, pred in observations)
        saved = sum(pred for ref, pred in observations if not ref and pred < threshold)
        scores.append({'threshold': threshold, 'removed_positive_tracks': deleted, 'saved_false_notes': saved})
    eligible = [row for row in scores if not row['removed_positive_tracks']]
    decision = (min(eligible, key=lambda row: (-row['saved_false_notes'], row['threshold']))
                if positive and negative >= MIN_NEGATIVES else scores[0])
    return {**decision, 'positive': positive, 'negative': negative, 'grid': scores,
            'support_sufficient': positive > 0 and negative >= MIN_NEGATIVES}


def note_counts(scored):
    other = scored.get('other_drum_notes', {})
    return tuple(scored[f'{source}_notes'] + sum(other.get(source, {}).values())
                 for source in ('reference', 'prediction'))


def calibrate(work):
    manifest_path = work / 'manifest.json'
    verify_hash(manifest_path, MANIFEST_SHA)
    tuning = tuning_songs(read_json(manifest_path))
    result = read_json(work / 'dev-results.json')
    if set(result['items']) != {song['id'] for song in tuning}:
        raise ValueError('Only exact tuning cohort may calibrate presence')
    results = [result['items'][song['id']] for song in tuning]
    outcome = summarize(results)
    return {category: {'route': choice['winner'], **choose_threshold([
        note_counts(item['routes'][choice['winner']]['corrected']) for item in results
    ])} for category, choice in outcome['winners'].items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    if args.config.exists() or (args.work / 'presence-tuning.json').exists():
        raise FileExistsError('Preserving frozen presence configuration')
    evidence = calibrate(args.work)
    write_json(args.work / 'presence-tuning.json', evidence)
    write_json(args.config, {'version': 1, 'tracks': {
        category: {'route': item['route'], 'threshold': item['threshold']}
        for category, item in evidence.items()
    }})


if __name__ == '__main__':
    main()
