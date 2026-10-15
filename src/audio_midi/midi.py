import math
from pathlib import Path
import mido
from .events import CATEGORIES, PROGRAMS, NoteEvent


def write_midi(notes: list[NoteEvent], path: Path, bpm: float = 120) -> None:
    if not notes or not math.isfinite(bpm) or bpm <= 0:
        raise ValueError('No valid notes or invalid BPM')
    midi=mido.MidiFile(type=1,ticks_per_beat=480)
    tempo=mido.bpm2tempo(bpm)
    meta=mido.MidiTrack([
        mido.MetaMessage('track_name',name='Conductor'),
        mido.MetaMessage('set_tempo',tempo=tempo),
        mido.MetaMessage('time_signature',numerator=4,denominator=4),
        mido.MetaMessage('text',text='Tempo and time signature are defaults, not detected.'),
    ])
    midi.tracks.append(meta)
    channels=iter(c for c in range(16) if c!=9)
    for category in CATEGORIES:
        group=[n for n in notes if n.category==category]
        if not group:
            continue
        channel=9 if category=='drums' else next(channels)
        program=group[0].program
        if program is None or category=='vocal' or not 0<=program<=127:
            program=PROGRAMS[category]
        track=mido.MidiTrack([mido.MetaMessage('track_name',name=category), mido.Message('program_change',channel=channel,program=program)])
        midi.tracks.append(track)
        events=[]
        for n in group:
            if n.offset is None or not all(math.isfinite(x) for x in (n.onset,n.offset)) or n.onset < 0 or n.offset<=n.onset:
                raise ValueError('Invalid note time')
            on=round(mido.second2tick(n.onset,480,tempo))
            off=max(on+1,round(mido.second2tick(n.offset,480,tempo)))
            events.extend([(on,1,n),(off,0,n)])
        prior=0
        for tick,on,n in sorted(events,key=lambda e:(e[0],e[1],e[2].pitch)):
            track.append(mido.Message('note_on' if on else 'note_off',channel=channel,note=n.pitch,velocity=(80 if n.velocity is None else n.velocity) if on else 0,time=tick-prior))
            prior=tick
    if len(midi.tracks)==1:
        raise ValueError('No supported notes')
    midi.save(path)
    check=mido.MidiFile(path)
    if check.type!=1 or check.ticks_per_beat!=480:
        raise ValueError('MIDI validation failed')
