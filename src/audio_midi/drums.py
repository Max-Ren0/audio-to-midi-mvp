"""Fixed drum-key routing; never reads a reference or changes GM keys."""
from .events import NoteEvent
from .stitching import clean_notes


def hybrid_drums(general: list[NoteEvent], specialist: list[NoteEvent], duration: float) -> list[NoteEvent]:
    """Use specialist snare38/hat42; preserve general fine drum keys elsewhere.

    ADTOF's five coarse classes cannot infer fine tom, ride or open-hat keys.
    This fixed research rule replaces entire keys, never individual notes by score.
    """
    if any(n.category!='drums' for n in [*general,*specialist]):
        raise ValueError('Drum-only inputs required')
    replaced={38,42}
    notes=[n for n in general if n.pitch not in replaced]+[n for n in specialist if n.pitch in replaced]
    return clean_notes(notes,duration)


def route_drum_keys(sources: dict[str,list[NoteEvent]], default: str, routes: dict[int,str], duration: float) -> list[NoteEvent]:
    """Select entire unchanged GM keys from named, reference-free predictions."""
    if default not in sources or any(source not in sources for source in routes.values()):
        raise ValueError('Missing drum source')
    if any(not isinstance(key,int) or not 35<=key<=81 for key in routes):
        raise ValueError('Invalid drum key')
    if any(n.category!='drums' for notes in sources.values() for n in notes):
        raise ValueError('Drum-only sources required')
    selected=[n for name,notes in sources.items() for n in notes if routes.get(n.pitch,default)==name]
    return clean_notes(selected,duration)


def consensus_drums(anchor: list[NoteEvent], support: list[NoteEvent], tolerance: float, *, families: tuple[set[int], ...] = ()) -> list[NoteEvent]:
    """Keep anchor events corroborated once by another model at the same key."""
    from math import isfinite
    if not isfinite(tolerance) or tolerance<0:raise ValueError('Invalid consensus tolerance')
    if any(n.category!='drums' for n in [*anchor,*support]):raise ValueError('Drum-only sources required')
    used=set();kept=[]
    for n in sorted(anchor,key=lambda n:(n.onset,n.pitch)):
        candidates=[(abs(n.onset-m.onset),i) for i,m in enumerate(support) if i not in used and (n.pitch==m.pitch or any(n.pitch in group and m.pitch in group for group in families)) and abs(n.onset-m.onset)<=tolerance+1e-9]
        if candidates:
            _,i=min(candidates);used.add(i);kept.append(n)
    return kept


def detection_region(box: tuple[float,float,float,float], start: int, width: int, height: int) -> tuple[int,int,int,int]:
    """Map a resized detector patch back to the true, possibly short last patch."""
    from math import isfinite
    if start<0 or width<=0 or height<=0 or len(box)!=4 or not all(isfinite(v) for v in box):
        raise ValueError('Invalid detection geometry')
    cx,cy,bw,bh=box
    if bw<0 or bh<0:raise ValueError('Negative detection size')
    x1=max(0,min(width,int((cx-bw/2)*width)));x2=max(0,min(width,int((cx+bw/2)*width)))
    y1=max(0,min(height,int((cy-bh/2)*height)));y2=max(0,min(height,int((cy+bh/2)*height)))
    return start+x1,start+x2,y1,y2
