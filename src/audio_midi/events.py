from dataclasses import dataclass

CATEGORIES = ('piano', 'acoustic_guitar', 'electric_guitar', 'bass', 'drums', 'strings', 'vocal')
PROGRAMS = {'piano': 0, 'acoustic_guitar': 25, 'electric_guitar': 27, 'bass': 33, 'drums': 0, 'strings': 48, 'vocal': 53}

@dataclass(frozen=True)
class NoteEvent:
    category: str
    pitch: int
    onset: float
    offset: float | None
    velocity: int | None = None
    program: int | None = None


def category_for(program: int, is_drum: bool = False, vocal_semantics: bool = False) -> str | None:
    if is_drum:
        return 'drums'
    if vocal_semantics and program in (100, 101):
        return 'vocal'
    for category, programs in [('piano', range(0,8)), ('acoustic_guitar', range(24,26)), ('electric_guitar', range(26,32)), ('bass', range(32,40)), ('strings', (*range(40,46), *range(48,52)))]:
        if program in programs:
            return category
    return None
