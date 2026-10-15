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


def metrics(reference: list[NoteEvent], predicted: list[NoteEvent], scale: float, shift: float, duration: float) -> dict:
    """Score fixed shared alignment; reference never enters candidate assembly."""
    from dataclasses import replace
    from math import isfinite
    from .evaluate import evaluate
    if not all(isfinite(v) for v in (scale,shift,duration)) or scale<=0 or duration<=0:
        raise ValueError('Invalid shared alignment')
    ref=[n for n in reference if n.category in INSTRUMENTS and shift<=n.onset<shift+scale*duration]
    pred=[replace(n,onset=scale*n.onset+shift,offset=None if n.offset is None else scale*n.offset+shift) for n in predicted if n.category in INSTRUMENTS and 0<=n.onset<duration]
    raw=evaluate(ref,pred);per={}
    for cat in INSTRUMENTS:
        m=raw[cat];tp,fp,fn=m['tp'],m['fp'],m['fn']
        per[cat]=dict(reference=tp+fn,predicted=tp+fp,matched=tp,extra=fp,missed=fn,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,f1=m['f1'])
    nr=len(ref);np=len(pred);tp=sum(x['matched'] for x in per.values());valid=[x['f1'] for x in per.values() if x['f1'] is not None]
    overall=dict(reference=nr,predicted=np,matched=tp,extra=np-tp,missed=nr-tp,precision=tp/np if np else None,recall=tp/nr if nr else None,f1=2*tp/(nr+np) if nr+np else None)
    return dict(overall=overall,per_category=per,macro_f1=sum(valid)/len(valid) if valid else None,alignment={'scale':scale,'shift_seconds':shift,'duration_seconds':duration},reference_window=[shift,shift+scale*duration])


def load_sources(manifest_path: Path,input_sha256: str) -> dict[str,list[NoteEvent]]:
    """Explicit reconstruction cache, bound to input and every candidate file hash."""
    import json,hashlib
    data=json.loads(manifest_path.read_text())
    if data['input_sha256']!=input_sha256:raise ValueError('Candidate input hash mismatch')
    result={}
    for name,entry in data['sources'].items():
        path=Path(entry['path'])
        if not path.is_absolute():path=manifest_path.parent/path
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Candidate file hash mismatch')
        if path.suffix.lower() in ('.mid','.midi'):result[name]=read_notes(path)
        else:result[name]=[NoteEvent(**n) for n in json.loads(path.read_text())['notes']]
    return result


def snap_bass_attacks(notes: list[NoteEvent], attacks: list[float], duration: float) -> list[NoteEvent]:
    """Remove <120ms unstable pitch fragments; snap to audio attacks within 300ms."""
    from dataclasses import replace
    if any(n.category!='bass' for n in notes):raise ValueError('Bass-only refinement')
    out=[]
    attacks=sorted(set(t for t in attacks if 0<=t<duration))
    for n in sorted(notes,key=lambda n:n.onset):
        if n.offset is None or n.offset-n.onset<.12:continue
        earlier=[t for t in attacks if n.onset-.3<=t<=n.onset]
        start=earlier[0] if earlier else n.onset
        if out and out[-1].offset>start:out[-1]=replace(out[-1],offset=start)
        out.append(replace(n,onset=start))
    return clean_notes(out,duration)
