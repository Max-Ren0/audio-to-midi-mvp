"""Run the fixed eight-sample Noto evaluation sequentially."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
ITEMS_RELATIVE = Path('outputs/runs/multi-song-eval/items')
TRACKS = ('piano', 'bass', 'drums')
NICE = 10
THREADS = 2
FIXED_IDS = ('slakh-Track00017', 'slakh-Track00018',
             'maestro-01', 'maestro-02', 'maestro-03')
SELECTION_RULE = (
    'BabySlakh: the first three numbered items whose manifest contains piano, bass and drums, '
    'plus Track00017 and Track00018. MAESTRO: maestro-01 through maestro-03.'
)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def select_samples(items):
    manifest = read_json(items / 'manifest.json')
    by_id = {sample['id']: sample for sample in manifest}
    if len(by_id) != len(manifest):
        raise ValueError('Duplicate sample IDs in manifest')
    eligible = sorted(
        (sample for sample in manifest
         if sample['source'].startswith('BabySlakh') and set(TRACKS) <= set(sample['contains'])),
        key=lambda sample: int(sample['id'].removeprefix('slakh-Track')),
    )
    if len(eligible) < 3:
        raise ValueError('Need at least three BabySlakh samples containing all MVP instruments')
    return [*eligible[:3], *(by_id[sample_id] for sample_id in FIXED_IDS)]


def attempts(runs, sample_id):
    """Return the original attempt followed by retries in numerical order."""
    def attempt_number(directory):
        suffix = directory.name.removeprefix(f'{sample_id}.retry-')
        return int(suffix) if suffix.isascii() and suffix.isdecimal() else 0

    original = runs / sample_id
    retries = sorted(
        (directory for directory in runs.glob(f'{sample_id}.retry-*') if attempt_number(directory)),
        key=attempt_number,
    )
    return ([original] if os.path.lexists(original) else []) + retries


def completed(directory):
    receipt = directory / 'receipt.json'
    try:
        return (directory / 'noto.mid').is_file() and read_json(receipt)['status'] == 'ok'
    except (OSError, ValueError, KeyError, TypeError):
        return False


def next_attempt(runs, sample_id):
    original = runs / sample_id
    if not os.path.lexists(original):
        return original
    number = 1
    while os.path.lexists(candidate := runs / f'{sample_id}.retry-{number}'):
        number += 1
    return candidate


def machine_info():
    cpu = platform.processor() or platform.machine()
    if sys.platform == 'darwin':
        cpu = subprocess.check_output(
            ['sysctl', '-n', 'machdep.cpu.brand_string'], text=True,
        ).strip()
    return {'cpu': cpu, 'logical_cpus': os.cpu_count(), 'threads': THREADS,
            'nice_adjustment': NICE, 'device': 'cpu', 'parallel_samples': 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resources', type=Path, required=True)
    parser.add_argument('--runs', type=Path, required=True)
    args = parser.parse_args()
    resources, runs = args.resources.resolve(), args.runs.resolve()
    items = resources / ITEMS_RELATIVE
    samples = select_samples(items)
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src'), 'PYTHONDONTWRITEBYTECODE': '1',
           'GIT_OPTIONAL_LOCKS': '0'}
    machine = machine_info()
    print('Samples:', ', '.join(sample['id'] for sample in samples), flush=True)
    unsuccessful = 0
    for sample in samples:
        sample_id = sample['id']
        existing = next((directory for directory in reversed(attempts(runs, sample_id))
                         if completed(directory)), None)
        if existing is not None:
            print(f'{sample_id}: skip completed {existing.name}', flush=True)
            continue
        output = next_attempt(runs, sample_id)
        command = [
            'nice', '-n', str(NICE), sys.executable, str(ROOT / 'scripts/run_noto.py'),
            str(items / sample_id / 'input.mp3'), '--output-dir', str(output),
            '--resources', str(resources), '--threads', str(THREADS),
        ]
        print(f'{sample_id}: started ({output.name})', flush=True)
        started = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        elapsed = round(time.monotonic() - started, 3)
        output.mkdir(parents=True, exist_ok=True)
        metadata = {'returncode': result.returncode, 'wall_seconds': elapsed,
                    'machine': machine, 'stderr': result.stderr.strip()}
        (output / 'attempt.json').write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
        )
        if result.returncode or not completed(output):
            unsuccessful += 1
        print(f'{sample_id}: exit={result.returncode}, wall={elapsed:.3f}s', flush=True)
    return int(unsuccessful > 0)


if __name__ == '__main__':
    raise SystemExit(main())
