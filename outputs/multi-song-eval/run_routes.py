"""Run the baseline and current-best routes on every prepared item, sequentially.

baseline : YourMT3 whole-mix transcription (audio-midi transcribe)
best     : piano from the locked piano-B route (BS-RoFormer SW -> Transkun),
           bass + drums from MuScriptor Medium replacing the baseline tracks.
Finished routes (final MIDI present) are kept, so the script can be re-run to resume;
leftover directories of failed runs are renamed to *.failed-<time> and retried.

Usage (repo root):
    PYTHONPATH=src .venv/bin/python outputs/multi-song-eval/run_routes.py outputs/runs/multi-song-eval/items
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

PY = '.venv/bin/python'
ENV = {'PYTHONPATH': 'src'}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(cmd, log):
    import os
    start = time.monotonic()
    with open(log, 'w') as f:
        code = subprocess.run(['nice', '-n', '10', *cmd], stdout=f, stderr=subprocess.STDOUT,
                              env={**os.environ, **ENV}).returncode
    return {'exit': code, 'seconds': round(time.monotonic() - start, 1)}


def done(d, route):
    """A route is finished when its final MIDI exists. MuScriptor also counts as finished when the
    splice step refused (exit 1) but the raw NOTE lines are in its log; score.py scores those."""
    if route == 'piano-b':
        return (d / 'piano-b/钢琴-B.mid').exists()
    log = d / 'muscriptor/muscriptor.log'
    return (d / 'muscriptor/Noto-MuScriptor贝斯鼓.mid').exists() or (log.exists() and 'NOTE,' in log.read_text())


def clear_failed(path):
    """Move a leftover directory from a failed run aside so the route can be retried cleanly."""
    if path.exists():
        path.rename(path.with_name(f'{path.name}.failed-{int(time.time())}'))


def main(items):
    manifest = json.loads((items / 'manifest.json').read_text())
    status_path = items / 'run-status.json'
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    for m in manifest:
        d = items / m['id']; s = status.setdefault(m['id'], {})
        mp3 = d / 'input.mp3'
        if not (d / 'baseline/result.mid').exists():
            s['baseline'] = run([PY, '-m', 'audio_midi.cli', 'transcribe', str(mp3), '--output', str(d / 'baseline/result.mid')], d / 'baseline.log')
        if 'piano' in m['contains'] and not done(d, 'piano-b'):
            clear_failed(d / 'piano-b')
            s['piano_b'] = run([PY, 'scripts/run_piano_b.py', str(mp3), '--output-dir', str(d / 'piano-b')], d / 'piano-b.log')
        if {'bass', 'drums'} & set(m['contains']) and not done(d, 'muscriptor') and (d / 'baseline/result.mid').exists():
            clear_failed(d / 'muscriptor')
            s['muscriptor'] = run([PY, 'scripts/run_muscriptor_bass_drums.py', '--audio', str(mp3), '--baseline', str(d / 'baseline/result.mid'),
                                   '--baseline-audio-sha256', sha(mp3), '--output-dir', str(d / 'muscriptor')], d / 'muscriptor.log')
        status_path.write_text(json.dumps(status, indent=1))
        print(m['id'], {k: v['exit'] for k, v in s.items()}, flush=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]))
