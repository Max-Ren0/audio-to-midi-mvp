import pytest
from audio_midi.events import NoteEvent
from audio_midi.muscriptor_routing import parse_note_lines, replace_bass_drums

def note(category,pitch,onset,offset,program=None):
    return NoteEvent(category,pitch,onset,offset,80,program)

def test_replace_only_requested_tracks_and_limit_window():
    old=[note('piano',60,.2,.5,0),note('bass',40,.5,.8,33),note('drums',36,1,1.1,0),note('strings',70,1.5,2,48)]
    src=[note('bass',43,.3,.8,33),note('drums',42,1,1.1,0),note('bass',45,9.9,10.5,33),note('bass',46,10.1,10.2,33),note('piano',61,.2,.4,0)]
    out=replace_bass_drums(old,src,10)
    assert [(n.category,n.pitch,n.onset,n.offset) for n in out]==[('piano',60,.2,.5),('bass',43,.3,.8),('drums',42,1,1.1),('strings',70,1.5,2),('bass',45,9.9,10)]

def test_missing_target_track_fails_closed():
    with pytest.raises(ValueError,match='drums'):
        replace_bass_drums([note('bass',40,0,1,33)],[note('bass',40,0,1,33)],2)

def test_raw_parse_ignores_other_instruments_and_rejects_malformed():
    result=parse_note_lines('NOTE,0.100000,0.300000,40,33,0\nNOTE,0.200000,0.210000,42,128,1\nNOTE,0.300000,0.400000,65,0,0\n')
    assert [(x.category,x.pitch) for x in result]==[('bass',40),('drums',42)]
    with pytest.raises(ValueError):parse_note_lines('NOTE,0.1,nan,40,33,0\n')

def test_replacement_preserves_non_target_midi_tracks(tmp_path):
    import mido
    from audio_midi.midi import write_midi
    from audio_midi.muscriptor_routing import replace_midi_tracks
    baseline=tmp_path/'baseline.mid';output=tmp_path/'output.mid'
    write_midi([note('piano',60,.2,.5,0),note('bass',40,.5,.8,33),note('drums',36,1,1.1,0),note('strings',70,1.5,2,48)],baseline)
    original=mido.MidiFile(baseline)
    replace_midi_tracks(baseline,[note('bass',43,.3,.8,33),note('drums',42,1,1.1,0)],output,2)
    result=mido.MidiFile(output)
    bass = next(t for t in result.tracks if t.name == 'bass')
    assert {m.channel for m in bass if m.type == 'program_change'} == {1}
    for name in ('Conductor','piano','strings'):
        assert list(next(t for t in original.tracks if t.name==name))==list(next(t for t in result.tracks if t.name==name))
    with pytest.raises(FileExistsError):replace_midi_tracks(baseline,[note('bass',43,.3,.8,33),note('drums',42,1,1.1,0)],output,2)
