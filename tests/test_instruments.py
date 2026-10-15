import mido
from audio_midi.events import NoteEvent
from audio_midi.midi import write_midi


def test_category_instruments_and_bank_are_explicit_before_first_note(tmp_path):
    p=tmp_path/'instruments.mid'
    write_midi([NoteEvent('piano',60,0,1,program=7),NoteEvent('acoustic_guitar',64,0,1,program=24),NoteEvent('electric_guitar',67,0,1,program=30),NoteEvent('vocal',69,0,1,program=100)],p)
    m=mido.MidiFile(p)
    expected={'piano':0,'acoustic_guitar':25,'electric_guitar':27,'vocal':53}
    for t in m.tracks[1:]:
        before=t[:next(i for i,x in enumerate(t) if x.type=='note_on')]
        assert any(x.type=='instrument_name' for x in before)
        assert next(x.program for x in before if x.type=='program_change')==expected[t.name]
        assert {(x.control,x.value) for x in before if x.type=='control_change' and x.control in (0,32)}=={(0,0),(32,0)}
        assert any(x.type=='control_change' and x.control==7 for x in before)
