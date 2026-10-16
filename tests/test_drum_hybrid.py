import pytest
from audio_midi.events import NoteEvent


def n(pitch,start=1):return NoteEvent('drums',pitch,start,start+.05,80,0)


def test_hybrid_preserves_general_fine_keys_and_replaces_only_snare_hat():
    from audio_midi.drums import hybrid_drums
    general=[n(p) for p in [36,38,42,46,48,51]]
    specialist=[n(p,2) for p in [35,38,42,47,49]]
    result=hybrid_drums(general,specialist,10)
    assert {(x.pitch,x.onset) for x in result}=={(36,1),(46,1),(48,1),(51,1),(38,2),(42,2)}
    assert [x.pitch for x in general]==[36,38,42,46,48,51]


def test_hybrid_never_maps_kick35_to36_or_generic_cymbal_to_ride():
    from audio_midi.drums import hybrid_drums
    assert hybrid_drums([], [n(35),n(49)],10)==[]


def test_hybrid_rejects_non_drum_notes():
    from audio_midi.drums import hybrid_drums
    with pytest.raises(ValueError):hybrid_drums([NoteEvent('piano',60,0,1,80,0)],[],10)
