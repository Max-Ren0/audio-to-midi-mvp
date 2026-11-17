"""Build the multi-song evaluation set from BabySlakh and MAESTRO test pieces.

Writes, per item: input.mp3 (what the routes transcribe) and reference.json (exact
note annotations on the same timeline). Downloaded data is only read, never executed.

Usage (repo root):
    PYTHONPATH=src .venv/bin/python outputs/multi-song-eval/prepare.py \
        work/datasets/babyslakh/babyslakh_16k work/datasets/maestro-download outputs/runs/multi-song-eval/items
"""
import json
import subprocess
import sys
from pathlib import Path

import mido
import soundfile as sf
import yaml

from audio_midi.events import category_for
from audio_midi.quality import read_notes

WINDOW = 60.0      # seconds taken from each BabySlakh song
OFFSET = 30.0      # skip intros when the song is long enough
MVP = ('piano', 'bass', 'drums')


def midi_notes(path, category):
    """Notes in seconds from one single-instrument stem MIDI, labelled with a fixed category."""
    active = {}; out = []; now = 0.
    for msg in mido.MidiFile(path):
        now += msg.time
        if msg.type == 'note_on' and msg.velocity:
            active.setdefault(msg.note, []).append(now)
        elif msg.type in ('note_off', 'note_on') and active.get(msg.note):
            start = active[msg.note].pop(0)
            out.append({'category': category, 'pitch': msg.note, 'onset': start, 'offset': now})
    return out


def window(notes, start, length):
    keep = []
    for n in notes:
        if start <= n['onset'] < start + length:
            keep.append({**n, 'onset': round(n['onset'] - start, 6),
                         'offset': round(min(n['offset'], start + length) - start, 6)})
    return keep


def encode(src, dst, start=None, length=None):
    cmd = ['ffmpeg', '-v', 'error', '-nostdin', '-y']
    if start is not None:
        cmd += ['-ss', f'{start:.3f}', '-t', f'{length:.3f}']
    cmd += ['-i', str(src), '-ac', '2', '-ar', '44100', '-b:a', '192k', str(dst)]
    subprocess.run(cmd, check=True)


def slakh(root, out, manifest):
    for track in sorted(Path(root).glob('Track*')):
        meta = yaml.safe_load((track / 'metadata.yaml').read_text())
        info = sf.info(track / 'mix.wav'); dur = info.frames / info.samplerate
        start = OFFSET if dur >= OFFSET + WINDOW else 0.
        length = min(WINDOW, dur - start)
        notes = []; stems = {}
        for sid, stem in meta['stems'].items():
            # BabySlakh metadata marks every stem audio_rendered: false; the stem WAV is the reliable signal.
            if not (track / 'stems' / f'{sid}.wav').exists():
                continue
            cat = category_for(int(stem.get('program_num', 0)), bool(stem.get('is_drum')))
            mid = track / 'MIDI' / f'{sid}.mid'
            if cat is None or not mid.exists():
                stems[sid] = {'class': stem.get('inst_class'), 'category': None}
                continue
            stems[sid] = {'class': stem.get('inst_class'), 'category': cat}
            notes += midi_notes(mid, cat)
        notes = sorted(window(notes, start, length), key=lambda n: (n['onset'], n['category'], n['pitch']))
        item = out / f'slakh-{track.name}'; item.mkdir(parents=True)
        encode(track / 'mix.wav', item / 'input.mp3', start, length)
        (item / 'reference.json').write_text(json.dumps({'notes': notes}))
        manifest.append({'id': item.name, 'source': 'BabySlakh (Slakh2100 train split)', 'track': track.name,
                         'window_seconds': [start, start + length], 'contains': sorted({n['category'] for n in notes}),
                         'notes_per_category': {c: sum(n['category'] == c for n in notes) for c in sorted({n['category'] for n in notes})},
                         'stems': stems})


def maestro(root, out, manifest):
    sel = json.loads((Path(root) / 'selection.json').read_text())
    for k, x in enumerate(sel, 1):
        wav = Path(root) / Path(x['audio_filename']).name
        mid = Path(root) / Path(x['midi_filename']).name
        notes = [{'category': 'piano', 'pitch': n.pitch, 'onset': round(n.onset, 6), 'offset': round(n.offset, 6)}
                 for n in read_notes(mid) if n.category == 'piano']
        item = out / f'maestro-{k:02d}'; item.mkdir(parents=True)
        encode(wav, item / 'input.mp3')
        (item / 'reference.json').write_text(json.dumps({'notes': notes}))
        manifest.append({'id': item.name, 'source': 'MAESTRO v3.0.0 test split',
                         'piece': f"{x['canonical_composer']} — {x['canonical_title']}",
                         'window_seconds': [0, float(x['duration'])], 'contains': ['piano'],
                         'notes_per_category': {'piano': len(notes)}})


if __name__ == '__main__':
    slakh_root, maestro_root, out = (Path(p) for p in sys.argv[1:4])
    out.mkdir(parents=True, exist_ok=False)
    manifest = []
    slakh(slakh_root, out, manifest)
    maestro(maestro_root, out, manifest)
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    for c in MVP:
        print(c, 'songs:', sum(c in m['contains'] for m in manifest))
    print('items:', len(manifest))
