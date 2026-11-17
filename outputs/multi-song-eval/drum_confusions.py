"""Tally which MuScriptor drum keys appear near each BabySlakh reference drum hit.

Rule (descriptive, not a one-to-one assignment): for every reference hit, look at MuScriptor
drum predictions with |onset difference| <= 50 ms. If one of them has the same GM key the hit
counts as 'same'; if there is none the hit counts as 'none nearby'; otherwise the key of the
nearest prediction (first in onset order on ties) is recorded. One prediction can be counted
for several simultaneous reference hits, so "key B appeared nearby" does not prove the model
"heard A as B".

Usage (repo root):
    PYTHONPATH=src .venv/bin/python outputs/multi-song-eval/drum_confusions.py outputs/runs/multi-song-eval/items outputs/multi-song-eval/drum_confusions.json
"""
import json
import sys
from collections import Counter
from pathlib import Path

from audio_midi.muscriptor_routing import parse_note_lines
from audio_midi.quality import read_notes


def main(items, dest):
    tally = Counter(); total = 0
    for m in json.loads((items / 'manifest.json').read_text()):
        if not m['source'].startswith('BabySlakh') or 'drums' not in m['contains']:
            continue
        d = items / m['id']
        ref = [n for n in json.loads((d / 'reference.json').read_text())['notes'] if n['category'] == 'drums']
        mid = d / 'muscriptor/Noto-MuScriptor贝斯鼓.mid'
        notes = read_notes(mid) if mid.exists() else parse_note_lines((d / 'muscriptor/muscriptor.log').read_text())
        pred = sorted((n for n in notes if n.category == 'drums'), key=lambda n: n.onset)
        for r in ref:
            total += 1
            near = [p for p in pred if abs(p.onset - r['onset']) <= 0.05]
            if not near:
                tally[(r['pitch'], 'none nearby')] += 1
            elif any(p.pitch == r['pitch'] for p in near):
                tally[(r['pitch'], 'same')] += 1
            else:
                tally[(r['pitch'], min(near, key=lambda p: abs(p.onset - r['onset'])).pitch)] += 1
    errors = sorted(((k, v) for k, v in tally.items() if k[1] != 'same'), key=lambda kv: -kv[1])
    out = {'reference_hits': total, 'same_key_nearby': sum(v for k, v in tally.items() if k[1] == 'same'),
           'top_errors': [{'reference_key': k[0], 'nearest_prediction': k[1], 'count': v} for k, v in errors[:15]]}
    Path(dest).write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main(Path(sys.argv[1]), sys.argv[2])
