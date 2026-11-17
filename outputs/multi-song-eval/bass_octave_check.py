"""Check whether Slakh bass MIDI matches the sounding pitch of the rendered bass stem.

For every BabySlakh bass note in the evaluation window that lasts >= 0.2 s, estimate the
stem's f0 with pYIN over the note body and compare it with the MIDI pitch.

Usage (repo root):
    PYTHONPATH=src .venv/bin/python outputs/multi-song-eval/bass_octave_check.py \
        work/datasets/babyslakh/babyslakh_16k outputs/runs/multi-song-eval/items outputs/multi-song-eval/bass_octave_check.json
"""
import json
import sys
from collections import Counter
from pathlib import Path

import librosa
import numpy as np


def main(root, items, dest):
    manifest = json.loads((items / 'manifest.json').read_text())
    rows = []
    for m in manifest:
        if not m['source'].startswith('BabySlakh'):
            continue
        sids = [s for s, v in m['stems'].items() if v['category'] == 'bass']
        if not sids:
            continue
        start = m['window_seconds'][0]
        notes = [n for n in json.loads((items / m['id'] / 'reference.json').read_text())['notes']
                 if n['category'] == 'bass' and n['offset'] - n['onset'] >= 0.2]
        y = sum(librosa.load(root / m['track'] / 'stems' / f'{s}.wav', sr=16000, offset=start,
                             duration=m['window_seconds'][1] - start)[0] for s in sids)
        f0, _, _ = librosa.pyin(y, fmin=25, fmax=500, sr=16000, frame_length=2048, hop_length=160)
        diffs = Counter()
        for n in notes:
            a, b = int((n['onset'] + 0.05) * 100), int((n['offset'] - 0.03) * 100)
            seg = f0[a:b]; seg = seg[~np.isnan(seg)]
            if len(seg) < 3:
                continue
            diffs[int(round(float(np.median(librosa.hz_to_midi(seg))) - n['pitch']))] += 1
        mode = diffs.most_common(1)[0] if diffs else None
        rows.append({'id': m['id'], 'notes_checked': sum(diffs.values()), 'mode_audio_minus_midi': mode,
                     'share_at_minus_12': round(diffs[-12] / sum(diffs.values()), 3) if diffs else None,
                     'histogram': dict(diffs.most_common(5))})
        print(rows[-1], flush=True)
    Path(dest).write_text(json.dumps(rows, indent=1))


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
