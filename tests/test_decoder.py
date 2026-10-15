from types import SimpleNamespace as E


def event(t,v,pitch=60,program=0,drum=False):
    return E(time=t,velocity=v,pitch=pitch,program=program,is_drum=drum)


def test_decoder_preserves_long_closed_and_final_unclosed_notes():
    from audio_midi.backends.selected import decode_segments,normalize_raw
    from audio_midi.stitching import clean_notes
    raw,errors=decode_segments([([event(0,1),event(12,0),event(13,1,61)],[],{(0,61)},0)])
    notes,_=normalize_raw(raw)
    notes=clean_notes(notes,30)
    assert [(n.pitch,n.onset,n.offset) for n in notes]==[(60,0,12),(61,13,23)]


def test_decoder_ties_and_missing_ties():
    from audio_midi.backends.selected import decode_segments
    raw,errors=decode_segments([
      ([event(0,1)],[],{(0,60)},0),
      ([event(3,0)],[event(None,1)],set(),2),
    ])
    assert [(n.onset,n.offset) for n in raw]==[(0,3)]
    assert not errors
    raw,errors=decode_segments([([event(0,1)],[],{(0,60)},0),([],[],set(),2)])
    assert [(n.onset,n.offset) for n in raw]==[(0,2)]
    assert errors['missing_tie']==1
