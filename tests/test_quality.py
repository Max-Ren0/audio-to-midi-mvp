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
