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
