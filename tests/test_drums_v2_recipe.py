from audio_midi.events import NoteEvent

def n(p,t,v=80):return NoteEvent('drums',p,t,t+.1,v,0)

def test_v2_uses_corroboration_preserves_anchor_keys_and_rejects_unsupported_hits():
    from audio_midi.drums import optimized_drums_v2
    general=[n(36,1.01),n(43,3),n(55,4),n(55,5)]
    mix=[n(51,6),n(51,7)]
    oaf_sw=[n(36,1,95),n(36,2),n(48,8)]
    oaf_demucs=[n(38,9.02)]
    adtof=[n(35,2),n(38,9),n(38,10),n(42,11),n(49,4.01)]
    cymbal=[n(49,6.02)]
    result=optimized_drums_v2(general,mix,oaf_sw,oaf_demucs,adtof,cymbal,20)
    assert [(e.pitch,e.onset,e.velocity) for e in result]==[(36,1,95),(43,3,80),(55,4,80),(51,6,80),(48,8,80),(38,9,80),(42,11,80)]


def test_v2_rejects_wrong_instrument_even_if_its_pitch_would_be_discarded():
    import pytest
    from audio_midi.drums import optimized_drums_v2
    with pytest.raises(ValueError):
        optimized_drums_v2([],[],[NoteEvent('piano',60,1,2,80,0)],[],[],[],20)
