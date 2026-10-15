from pathlib import Path
import mido
import pytest
from audio_midi.events import NoteEvent
from audio_midi.quality import assemble, read_notes


def test_route_preserves_category_and_excludes_vocals():
    ns=[NoteEvent('piano',60,0,.5),NoteEvent('electric_guitar',64,1,1.5),NoteEvent('vocal',65,2,2.5)]
    got=assemble({'mix':ns},{'piano':'mix','electric_guitar':'mix'},3)
    assert [(n.category,n.pitch) for n in got]==[('piano',60),('electric_guitar',64)]
    assert assemble({'mix':ns},{'acoustic_guitar':'mix'},3)==[]


def test_missing_source_and_vocal_route_rejected():
    with pytest.raises(ValueError,match='source'):assemble({}, {'piano':'missing'},3)
    with pytest.raises(ValueError,match='category'):assemble({'x':[]},{'vocal':'x'},3)


def test_tempo_map_reader_excludes_choir(tmp_path):
    p=tmp_path/'x.mid';m=mido.MidiFile(ticks_per_beat=480)
    m.tracks.append(mido.MidiTrack([mido.MetaMessage('set_tempo',tempo=1000000),mido.Message('note_on',note=60,velocity=80,time=480),mido.MetaMessage('set_tempo',tempo=500000,time=480),mido.Message('note_off',note=60,time=480),mido.Message('program_change',program=53),mido.Message('note_on',note=64,velocity=80),mido.Message('note_off',note=64,time=480)]));m.save(p)
    ns=read_notes(p)
    assert len(ns)==1 and ns[0].onset==1 and ns[0].offset==2.5


def test_assembly_cleans_duplicate_notes_and_clips_at_end():
    n=NoteEvent('bass',40,.2,2)
    got=assemble({'a':[n,n]}, {'bass':'a'},1)
    assert len(got)==1 and got[0].offset==1


def test_metric_macro_penalizes_absent_category_false_positives():
    from audio_midi.quality import metrics
    ref=[NoteEvent('piano',60,.2,.7)]
    pred=[NoteEvent('piano',60,.2,.7),NoteEvent('strings',64,.4,.8)]
    got=metrics(ref,pred,1,0,1)
    assert got['overall']['matched']==1 and got['overall']['f1']==pytest.approx(2/3)
    assert got['macro_f1']==.5 and got['per_category']['strings']['f1']==0
    assert got['per_category']['drums']['f1'] is None


def test_metrics_fixed_affine_window_and_one_to_one():
    from audio_midi.quality import metrics
    ref=[NoteEvent('piano',60,10.3,10.7),NoteEvent('piano',61,11.2,11.5)]
    pred=[NoteEvent('piano',60,.2,.6),NoteEvent('piano',60,.2,.6)]
    got=metrics(ref,pred,1,10.1,1)
    assert got['overall']['reference']==1 and got['overall']['matched']==1
    assert got['overall']['predicted']==2


def test_candidate_manifest_rejects_wrong_input_and_tampering(tmp_path):
    import hashlib,json
    from audio_midi.quality import load_sources
    data=tmp_path/'notes.json';data.write_text(json.dumps({'notes':[{'category':'piano','pitch':60,'onset':0,'offset':1}]}))
    m=tmp_path/'manifest.json';payload={'input_sha256':'correct','sources':{'piano':{'path':str(data),'sha256':hashlib.sha256(data.read_bytes()).hexdigest()}}};m.write_text(json.dumps(payload))
    assert load_sources(m,'correct')['piano'][0].pitch==60
    with pytest.raises(ValueError,match='input'):load_sources(m,'other')
    data.write_text('{}')
    with pytest.raises(ValueError,match='hash'):load_sources(m,'correct')


def test_bass_attacks_use_audio_and_preserve_pitch():
    from audio_midi.quality import snap_bass_attacks
    ns=[NoteEvent('bass',42,.9,.98),NoteEvent('bass',43,1,2),NoteEvent('bass',41,2.2,3)]
    got=snap_bass_attacks(ns,[.75,.96,2.05],3)
    assert [(n.pitch,n.onset) for n in got]==[(43,.75),(41,2.05)]
    with pytest.raises(ValueError):snap_bass_attacks([NoteEvent('piano',60,1,2)],[.8],3)
