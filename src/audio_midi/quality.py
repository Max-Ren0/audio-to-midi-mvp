"""Reference-free six-instrument assembly for reproducible quality experiments."""
from collections import defaultdict, deque
from pathlib import Path
import mido
from .events import NoteEvent, category_for
from .stitching import clean_notes

INSTRUMENTS=('piano','acoustic_guitar','electric_guitar','bass','drums','strings')


def read_notes(path: Path) -> list[NoteEvent]:
    """Read seconds using the complete MIDI tempo map; omit unsupported programs."""
    programs=defaultdict(int);active=defaultdict(deque);notes=[];now=0.
    for msg in mido.MidiFile(path):
        now+=msg.time
        if msg.type=='program_change':programs[msg.channel]=msg.program
        if msg.type=='note_on' and msg.velocity:
            program=programs[msg.channel]
            cat=category_for(program,msg.channel==9)
            active[msg.channel,msg.note].append((cat,program,now,msg.velocity))
        elif msg.type=='note_off' or (msg.type=='note_on' and not msg.velocity):
            q=active[msg.channel,msg.note]
            if not q:raise ValueError('Unmatched MIDI note off')
            cat,program,start,velocity=q.popleft()
            if cat in INSTRUMENTS:notes.append(NoteEvent(cat,msg.note,start,now,velocity,program))
    if any(active.values()):raise ValueError('Unclosed MIDI note')
    return sorted(notes,key=lambda n:(n.onset,n.category,n.pitch))


def assemble(candidates: dict[str,list[NoteEvent]],routes: dict[str,str],duration: float) -> list[NoteEvent]:
    """Select whole category routes, never relabel individual model predictions."""
    result=[]
    for category,source in routes.items():
        if category not in INSTRUMENTS:raise ValueError('Unsupported category')
        if source not in candidates:raise ValueError(f'Missing source: {source}')
        result.extend(n for n in candidates[source] if n.category==category)
    return clean_notes(result,duration)
