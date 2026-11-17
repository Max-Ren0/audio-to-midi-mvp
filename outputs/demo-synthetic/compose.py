"""Compose the self-authored 30 s demo piece (piano, bass, drums) and its exact reference.

Everything here is original material written for the public demo, so it carries no
third-party music copyright. Usage (repo root):
    PYTHONPATH=src .venv/bin/python outputs/demo-synthetic/compose.py outputs/demo-synthetic/build
"""
import json
import sys
from pathlib import Path

import mido

BPM = 96
BEAT = 60 / BPM            # 0.625 s
BAR = 4 * BEAT             # 2.5 s, 12 bars = 30 s
PPQ = 480

# C - G - Am - F, three times. Chord tones for the piano left hand and bass roots.
CHORDS = [(48, (60, 64, 67)), (43, (59, 62, 67)), (45, (57, 60, 64)), (41, (57, 60, 65))]
# Original right-hand melody, one bar per chord: (beat offset, length in beats, pitch).
MELODY = [
    [(0, 1, 76), (1, .5, 74), (1.5, .5, 72), (2, 1.5, 74), (3.5, .5, 76)],
    [(0, 1.5, 79), (1.5, .5, 77), (2, 1, 74), (3, 1, 71)],
    [(0, 1, 72), (1, 1, 76), (2, .5, 77), (2.5, .5, 76), (3, 1, 72)],
    [(0, 2, 69), (2, .5, 72), (2.5, .5, 74), (3, 1, 77)],
]


def notes():
    out = []
    def add(cat, pitch, start, length, vel):
        out.append({'category': cat, 'pitch': pitch, 'onset': round(start, 6),
                    'offset': round(start + length, 6), 'velocity': vel})
    for bar in range(12):
        t0 = bar * BAR
        root, chord = CHORDS[bar % 4]
        last = bar == 11
        # Piano left hand: chord on beats 1 and 3 (whole bar on the final chord).
        for beat in ((0,) if last else (0, 2)):
            for p in chord:
                add('piano', p, t0 + beat * BEAT, (4 if last else 2) * BEAT * .95, 62)
        # Piano right hand melody from bar 3 on, so the opening is easier to follow.
        if bar >= 2:
            for off, length, p in MELODY[bar % 4]:
                if last and off > 0:
                    break
                add('piano', p, t0 + off * BEAT, (4 if last else length) * BEAT * .9, 84)
        # Bass: root on 1, fifth on 3, passing eighths on 4.
        if last:
            add('bass', root, t0, 4 * BEAT * .95, 96)
        else:
            for off, length, p in ((0, 1.5, root), (1.5, .5, root), (2, 1, root + 7), (3, .5, root + 12), (3.5, .5, root + 7)):
                add('bass', p, t0 + off * BEAT, length * BEAT * .9, 96)
        # Drums enter in bar 2: kick 1 and 3 (+ "and" of 3), snare 2 and 4, closed hats on eighths.
        if bar >= 1:
            if last:
                add('drums', 36, t0, .1, 110); add('drums', 49, t0, .1, 100)
                continue
            for off in (0, 2, 2.5):
                add('drums', 36, t0 + off * BEAT, .1, 110)
            for off in (1, 3):
                add('drums', 38, t0 + off * BEAT, .1, 104)
            for k in range(8):
                add('drums', 42, t0 + k * BEAT / 2, .05, 78 if k % 2 else 92)
            if bar % 4 == 0:
                add('drums', 49, t0, .1, 100)
    return sorted(out, key=lambda n: (n['onset'], n['category'], n['pitch']))


def write_midi(events, path):
    mid = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    meta = mido.MidiTrack(); mid.tracks.append(meta)
    meta.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(BPM)))
    meta.append(mido.MetaMessage('time_signature', numerator=4, denominator=4))
    for cat, ch, program in (('piano', 0, 0), ('bass', 1, 33), ('drums', 9, 0)):
        tr = mido.MidiTrack(); mid.tracks.append(tr)
        tr.append(mido.MetaMessage('track_name', name=cat))
        tr.append(mido.Message('program_change', channel=ch, program=program, time=0))
        msgs = []
        for n in (e for e in events if e['category'] == cat):
            on = round(n['onset'] / BEAT * PPQ); off = round(n['offset'] / BEAT * PPQ)
            msgs += [(on, 1, mido.Message('note_on', channel=ch, note=n['pitch'], velocity=n['velocity'])),
                     (off, 0, mido.Message('note_off', channel=ch, note=n['pitch'], velocity=0))]
        now = 0
        for tick, _, msg in sorted(msgs, key=lambda m: (m[0], m[1])):
            tr.append(msg.copy(time=tick - now)); now = tick
    mid.save(path)


if __name__ == '__main__':
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=False)
    events = notes()
    write_midi(events, out / 'reference.mid')
    (out / 'reference.json').write_text(json.dumps({'notes': events}, indent=1))
    print(len(events), 'notes;', {c: sum(e['category'] == c for e in events) for c in ('piano', 'bass', 'drums')})
