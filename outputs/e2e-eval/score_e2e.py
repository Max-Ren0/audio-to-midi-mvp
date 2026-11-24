"""Score the published Noto MIDI from every selected run, including failures."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import re
from statistics import median

import mido

from audio_midi.piano_lock import digest

from run_e2e import (ITEMS_RELATIVE, ROOT, SELECTION_RULE, TRACKS, attempts,
                     completed, read_json, select_samples)


CONDITIONAL_RESULTS = Path('outputs/multi-song-eval/results.json')
STAGES = ('baseline', 'piano_b', 'muscriptor')
COUNTS = ('tp', 'fp', 'fn')


def load_conditional_scorer():
    spec = importlib.util.spec_from_file_location(
        'multi_song_score', ROOT / CONDITIONAL_RESULTS.with_name('score.py'),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


multi_song = load_conditional_scorer()


def metrics(tp, fp, fn):
    return {
        'tp': tp, 'fp': fp, 'fn': fn,
        'precision': tp / (tp + fp) if tp + fp else None,
        'recall': tp / (tp + fn) if tp + fn else None,
        'f1': 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else None,
    }


def conditional_metrics(row):
    return {
        category: metrics(**{key: row['tracks'][category]['best'][key] for key in COUNTS})
        for category in TRACKS if category in row['tracks']
    }


def score_tracks(reference, prediction):
    ref = [note for note in reference if note.category in TRACKS]
    pred = [note for note in prediction if note.category in TRACKS]
    counts = multi_song.evaluate(ref, pred)
    tracks = {category: metrics(**{key: counts[category][key] for key in COUNTS})
              for category in TRACKS}
    present = {note.category for note in ref}
    absent = {category: tracks[category]['fp'] for category in TRACKS if category not in present}
    return tracks, absent


def public_error(message):
    # Keep the diagnostic while removing machine-specific paths and the home account name.
    message = str(message).replace(str(Path.home()), '<HOME>')
    message = re.sub(r'(?<![\w./])(?:<HOME>)?/(?![\s/])[^\n\r（），：、\"\'<>]+',
                     '<本机路径>', message)
    return message.replace(Path.home().name, '<本机账户>')


def run_info(directory):
    def optional_json(name):
        path = directory / name
        return read_json(path) if path.is_file() else {}

    receipt = optional_json('receipt.json')
    attempt = optional_json('attempt.json')
    stages = {entry['name']: entry for entry in receipt.get('stages', [])}
    code = attempt.get('returncode')
    success = completed(directory) and code in (None, 0)
    if not success and receipt.get('status') not in ('ok', 'failed') and code is None:
        raise ValueError(f'{directory.name}: run has no terminal receipt or exit code')
    phase = receipt.get('failed_stage')
    reason = stages.get(phase, {}).get('error') or attempt.get('stderr')
    if not success and not reason:
        if receipt.get('status') == 'ok' and not (directory / 'noto.mid').is_file():
            reason = '成功回执缺少最终 MIDI'
        else:
            reason = '一键命令未成功完成，运行未提供诊断'
    stage_info = {}
    for name in STAGES:
        stage = stages.get(name, {})
        stage_info[name] = {
            'status': stage.get('status', 'not_started'),
            'seconds': stage.get('seconds') if stage.get('status') != 'skipped' else None,
        }
        if stage.get('reason'):
            stage_info[name]['reason'] = public_error(stage['reason'])
    total = receipt.get('total_seconds')
    if receipt.get('status') not in ('ok', 'failed'):
        total = attempt.get('wall_seconds')
    return receipt, {
        'attempt': directory.name,
        'success': success,
        'exit_code': code,
        'failed_stage': None if success else phase or 'entry',
        'failure_reason': None if success else public_error(reason),
        'stage_timings': stage_info,
        'total_seconds': total,
        'process_wall_seconds': attempt.get('wall_seconds'),
        'measured_machine': attempt.get('machine'),
        'pipeline_commit': receipt.get('git_commit'),
    }


def verify_midi(midi_path, receipt):
    if digest(midi_path) != receipt['output_sha256']:
        raise ValueError('Final MIDI SHA-256 differs from the receipt')
    actual = Counter()
    for track in mido.MidiFile(midi_path).tracks:
        count = sum(msg.type == 'note_on' and msg.velocity > 0 for msg in track)
        if count:
            actual[track.name] += count
    reported = Counter()
    for track in receipt['tracks']:
        reported[track['instrument']] += track['note_count']
    if actual != reported:
        raise ValueError('Final MIDI note counts differ from the receipt')
    return dict(sorted(actual.items()))


def score_sample(sample, items, runs, conditional):
    sample_id = sample['id']
    directories = attempts(runs, sample_id)
    if not directories:
        raise ValueError(f'{sample_id}: no run attempt')
    attempt_records = [(directory, *run_info(directory)) for directory in directories]
    directory, receipt, run = next(
        (record for record in reversed(attempt_records) if record[2]['success']), attempt_records[-1],
    )
    sample_dir = items / sample_id
    ref_path = sample_dir / 'reference.json'
    ref = multi_song.ref_notes(ref_path, sample['source'])
    ref_counts = Counter(note.category for note in ref)
    conditioned = conditional_metrics(conditional)
    for category in TRACKS:
        counts = conditioned.get(category, {})
        if ref_counts[category] != counts.get('tp', 0) + counts.get('fn', 0):
            raise ValueError(f'{sample_id}: conditional counts use a different {category} reference')
    input_sha = digest(sample_dir / 'input.mp3')
    if receipt.get('input_sha256') and receipt['input_sha256'] != input_sha:
        raise ValueError(f'{sample_id}: input differs from the run receipt')
    baseline_report_path = directory / 'stages/baseline/result.report.json'
    baseline_report = read_json(baseline_report_path) if baseline_report_path.is_file() else {}
    midi_path = directory / 'noto.mid'
    prediction = multi_song.read_notes(midi_path) if run['success'] else []
    midi_counts = verify_midi(midi_path, receipt) if run['success'] else {}
    pred_counts = Counter(note.category for note in prediction)
    if any(midi_counts.get(category, 0) != pred_counts[category] for category in TRACKS):
        raise ValueError(f'{sample_id}: final MIDI target track names and GM categories disagree')
    tracks, absent = score_tracks(ref, prediction)
    start, end = sample['window_seconds']
    duration = receipt.get('duration_seconds')
    audio_seconds = duration if duration is not None else end - start
    total = run['total_seconds']
    return {
        'id': sample_id,
        'source': sample['source'],
        'reference_window_seconds': end - start,
        'audio_seconds': audio_seconds,
        'audio_seconds_source': 'decoded' if duration is not None else 'manifest',
        'realtime_factor': total / audio_seconds if total is not None else None,
        'input_sha256': input_sha,
        'reference_sha256': digest(ref_path),
        'midi_sha256': receipt['output_sha256'] if run['success'] else None,
        **run,
        'attempts': [record for _, _, record in attempt_records],
        'tracks': tracks,
        'reference_note_counts': {category: ref_counts[category] for category in TRACKS},
        'absent_category_false_positives': absent,
        'mvp_notes_outside_reference_window': {
            category: sum(note.category == category and note.onset >= end - start for note in prediction)
            for category in TRACKS
        },
        'mvp_track_sources': {track['instrument']: track['source']
                              for track in receipt.get('tracks', []) if track['instrument'] in TRACKS}
                             if run['success'] else {},
        'baseline_attempts': baseline_report.get('attempts'),
        'baseline_decode_errors': baseline_report.get('model', {}).get('decode_errors', {}),
        'muscriptor_track_actions': (receipt.get('muscriptor') or {}).get('tracks', {}),
        'research_track_note_counts': {category: count for category, count in midi_counts.items()
                                       if category not in TRACKS},
        'conditional_best': conditioned,
        'conditional_unscored_absent_note_counts': {
            category: count for category, count in
            conditional.get('absent_category_extra_notes', {}).get('best', {}).items()
            if category in TRACKS
        },
    }


def pool(rows, field, category):
    counts = [row[field][category] for row in rows if category in row[field]]
    return metrics(**{key: sum(item[key] for item in counts) for key in COUNTS})


def deltas(observed, baseline):
    return {key: observed[key] - baseline[key]
            if observed[key] is not None and baseline[key] is not None else None
            for key in ('precision', 'recall', 'f1')}


def score_batch(items, runs):
    previous = read_json(ROOT / CONDITIONAL_RESULTS)
    conditional = {row['id']: row for row in previous['items']}
    rows = [score_sample(sample, items, runs, conditional[sample['id']])
            for sample in select_samples(items)]
    summary = {}
    for category in TRACKS:
        reference_present = [row for row in rows if row['reference_note_counts'][category]]
        all_e2e = pool(rows, 'tracks', category)
        paired_e2e = pool(reference_present, 'tracks', category)
        best = pool(rows, 'conditional_best', category)
        summary[category] = {
            'e2e_all': all_e2e,
            'conditional_best': best,
            'e2e_minus_conditional': deltas(all_e2e, best),
            'e2e_reference_present': paired_e2e,
            'e2e_reference_present_minus_conditional': deltas(paired_e2e, best),
            'samples_with_reference': len(reference_present),
            'absent_category_false_positives': sum(
                row['absent_category_false_positives'].get(category, 0) for row in rows
            ),
        }
    sources = {}
    for row in rows:
        sources.setdefault(row['source'], []).append(row)
    by_source = {
        source: {
            category: {field: pool(group, field, category)
                       for field in ('tracks', 'conditional_best')}
            for category in TRACKS
        }
        for source, group in sources.items()
    }
    wall_times = [row['total_seconds'] for row in rows if row['total_seconds'] is not None]
    factors = [row['realtime_factor'] for row in rows if row['realtime_factor'] is not None]
    timing_summary = {
        'total_seconds': sum(wall_times) if wall_times else None,
        'median_seconds': median(wall_times) if wall_times else None,
        'realtime_factor_min': min(factors, default=None),
        'realtime_factor_max': max(factors, default=None),
        'stage_seconds': {
            stage: sum(row['stage_timings'][stage]['seconds'] or 0 for row in rows)
            for stage in STAGES
        },
    }
    success = sum(row['success'] for row in rows)
    return {
        'selection': SELECTION_RULE,
        'metric': 'One-to-one same-category same-pitch (drums: GM key) onset matching within 50 ms; '
                  'micro pooling over the eight samples; failed outputs counted as empty predictions.',
        'reference_corrections': previous['reference_corrections'],
        'conditional_results': CONDITIONAL_RESULTS.as_posix(),
        'conditional_raw_muscriptor_samples': [row['id'] for row in rows
                                               if row['id'] in previous['muscriptor_scored_from_raw_log']],
        'samples': len(rows),
        'successes': success,
        'success_rate': success / len(rows),
        'first_attempt_successes': sum(row['attempts'][0]['success'] for row in rows),
        'aggregate': summary,
        'timing_summary': timing_summary,
        'by_source': by_source,
        'items': rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resources', type=Path, required=True)
    parser.add_argument('--runs', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('results.json'))
    args = parser.parse_args()
    result = score_batch(args.resources / ITEMS_RELATIVE, args.runs)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Success: {result['successes']}/{result['samples']}")
    for category, values in result['aggregate'].items():
        print(category, values)


if __name__ == '__main__':
    main()
