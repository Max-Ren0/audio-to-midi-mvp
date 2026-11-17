"""Run the baseline and current-best routes on every prepared item, sequentially.

baseline : YourMT3 whole-mix transcription (audio-midi transcribe)
best     : piano from the locked piano-B route (BS-RoFormer SW -> Transkun),
           bass + drums from MuScriptor Medium replacing the baseline tracks.
Existing outputs are kept, so the script can be re-run to resume.

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


def main(items):
    manifest = json.loads((items / 'manifest.json').read_text())
    status_path = items / 'run-status.json'
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    for m in manifest:
        d = items / m['id']; s = status.setdefault(m['id'], {})
        mp3 = d / 'input.mp3'
        if not (d / 'baseline/result.mid').exists():
            s['baseline'] = run([PY, '-m', 'audio_midi.cli', 'transcribe', str(mp3), '--output', str(d / 'baseline/result.mid')], d / 'baseline.log')
        if 'piano' in m['contains'] and not (d / 'piano-b').exists():
            s['piano_b'] = run([PY, 'scripts/run_piano_b.py', str(mp3), '--output-dir', str(d / 'piano-b')], d / 'piano-b.log')
        if {'bass', 'drums'} & set(m['contains']) and not (d / 'muscriptor').exists() and (d / 'baseline/result.mid').exists():
            s['muscriptor'] = run([PY, 'scripts/run_muscriptor_bass_drums.py', '--audio', str(mp3), '--baseline', str(d / 'baseline/result.mid'),
                                   '--baseline-audio-sha256', sha(mp3), '--output-dir', str(d / 'muscriptor')], d / 'muscriptor.log')
        status_path.write_text(json.dumps(status, indent=1))
        print(m['id'], {k: v['exit'] for k, v in s.items()}, flush=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]))
