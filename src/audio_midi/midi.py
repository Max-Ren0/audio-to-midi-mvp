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
        # Stable category presets; retain raw model labels in the report.
        program=PROGRAMS[category]
        volume={'piano':72,'acoustic_guitar':65,'electric_guitar':60,'bass':82,'drums':72,'strings':48,'vocal':110}[category]
        names={'piano':'Acoustic Grand Piano','acoustic_guitar':'Steel String Acoustic Guitar','electric_guitar':'Clean Electric Guitar','bass':'Fingered Electric Bass','drums':'GM Standard Drum Kit','strings':'String Ensemble','vocal':'Voice Oohs (melody approximation)'}
        track=mido.MidiTrack([
            mido.MetaMessage('track_name',name=category),
            mido.MetaMessage('instrument_name',name=names[category]),
            mido.Message('control_change',channel=channel,control=0,value=0),
            mido.Message('control_change',channel=channel,control=32,value=0),
            mido.Message('program_change',channel=channel,program=program),
            mido.Message('control_change',channel=channel,control=7,value=volume),
            mido.Message('control_change',channel=channel,control=10,value=64),
        ])
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
