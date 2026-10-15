from dataclasses import dataclass, replace
from math import isfinite
from .events import CATEGORIES, NoteEvent

@dataclass(frozen=True)
class Window:
    start: float
    end: float
    valid_start: float
    valid_end: float


def make_windows(duration: float, length: float = 30, overlap: float = 5) -> list[Window]:
    if not isfinite(duration) or duration <= 0 or not 0 <= overlap < length:
        raise ValueError('Invalid window parameters')
    spans=[]
    start=0.0
    while start < duration:
        end=min(start+length,duration)
        spans.append((start,end))
        if end >= duration:
            break
        start += length-overlap
    return [Window(a,b,0 if i==0 else (spans[i-1][1]+a)/2, duration if i==len(spans)-1 else (b+spans[i+1][0])/2) for i,(a,b) in enumerate(spans)]


def clean_notes(notes: list[NoteEvent], duration: float) -> list[NoteEvent]:
    if not isfinite(duration) or duration <= 0:
        raise ValueError('Invalid audio duration')
    grouped={}
    for n in notes:
        if n.category not in CATEGORIES or not isinstance(n.pitch,int) or not 0 <= n.pitch <= 127:
            continue
        if not isfinite(n.onset) or not 0 <= n.onset < duration:
            continue
        end=min(n.onset+10,duration) if n.offset is None else n.offset
        if not isfinite(end):
            continue
        end=min(end,duration)
        if end-n.onset < .03-1e-9:
            continue
        if n.velocity is not None and (not isinstance(n.velocity,int) or not 1 <= n.velocity <= 127):
            continue
        grouped.setdefault((n.category,n.pitch),[]).append(replace(n,offset=end))
    result=[]
    for group in grouped.values():
        unique=[]
        for n in sorted(group,key=lambda n:n.onset):
            if unique and n.onset-unique[-1].onset <= .05+1e-9:
                previous=unique[-1]
                if n.offset-n.onset > previous.offset-previous.onset:
                    unique[-1]=n
            else:
                unique.append(n)
        for i,n in enumerate(unique):
            if i+1<len(unique) and n.offset>unique[i+1].onset:
                n=replace(n,offset=unique[i+1].onset)
            if n.offset-n.onset >= .03-1e-9:
                result.append(n)
    return sorted(result,key=lambda n:(n.onset,n.category,n.pitch))


def stitch(windows: list[Window], predictions: list[list[NoteEvent]], duration: float) -> list[NoteEvent]:
    if len(windows)!=len(predictions):
        raise ValueError('Window prediction count mismatch')
    merged=[]
    for w,notes in zip(windows,predictions):
        for n in notes:
            onset=n.onset+w.start
            if w.valid_start <= onset < w.valid_end:
                merged.append(replace(n,onset=onset,offset=None if n.offset is None else n.offset+w.start))
    return clean_notes(merged,duration)
