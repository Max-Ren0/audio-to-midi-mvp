import math
from pathlib import Path
import pytest
import mido

# Catch wrong GM boundaries and unsupported vocal guesses.
@pytest.mark.parametrize('program,want', [(0,'piano'),(7,'piano'),(24,'acoustic_guitar'),(25,'acoustic_guitar'),(26,'electric_guitar'),(31,'electric_guitar'),(32,'bass'),(39,'bass'),(40,'strings'),(45,'strings'),(46,None),(47,None),(48,'strings'),(51,'strings'),(52,None),(100,None)])
def test_categories(program,want):
    from audio_midi.events import category_for
    assert category_for(program) == want

def test_vocals_require_model_semantics():
    from audio_midi.events import category_for
    assert category_for(100, vocal_semantics=True) == 'vocal'
    assert category_for(101, vocal_semantics=True) == 'vocal'
    assert category_for(0, is_drum=True) == 'drums'

def test_cleanup_pairs_clamps_and_deduplicates():
    from audio_midi.events import NoteEvent
    from audio_midi.stitching import clean_notes
    notes = [NoteEvent('piano',60,1,1.5),NoteEvent('piano',60,1.04,2),NoteEvent('piano',60,1.8,2.4),NoteEvent('piano',61,2,None),NoteEvent('piano',62,1,1.02),NoteEvent('piano',63,float('nan'),3),NoteEvent('piano',64,-1,1)]
    result = clean_notes(notes,3)
    assert [(n.pitch,n.onset,n.offset) for n in result] == [(60,1.04,1.8),(60,1.8,2.4),(61,2,3)]

def test_windows_no_gaps_or_duplicates():
    from audio_midi.stitching import make_windows, stitch
    from audio_midi.events import NoteEvent
    ws=make_windows(70)
    assert [(w.start,w.end) for w in ws] == [(0,30),(25,55),(50,70)]
    assert [(w.valid_start,w.valid_end) for w in ws] == [(0,27.5),(27.5,52.5),(52.5,70)]
    predictions=[[NoteEvent('piano',60,27.5,28)], [NoteEvent('piano',60,2.5,3)], []]
    ns=stitch(ws,predictions,70)
    assert len(ns)==1 and ns[0].onset==27.5

def test_midi_roundtrip_channels_and_seconds(tmp_path):
    from audio_midi.events import NoteEvent
    from audio_midi.midi import write_midi
    p=tmp_path/'结果.mid'
    write_midi([NoteEvent('piano',60,.123,1.234), NoteEvent('drums',36,.5,.55)],p,bpm=90)
    m=mido.MidiFile(p)
    assert m.type==1 and m.ticks_per_beat==480
    assert len(m.tracks)==3
    ns=[x for t in m.tracks for x in t if x.type=='note_on']
    assert {(x.note,x.channel,x.velocity) for x in ns}=={(60,0,80),(36,9,80)}
    sec=0; starts=[]
    for msg in m:
        sec+=msg.time
        if msg.type=='note_on': starts.append(sec)
    assert starts == pytest.approx([.123,.5],abs=60/90/480)
    assert m.length==pytest.approx(1.234,abs=60/90/480)

def test_empty_midi_is_not_success(tmp_path):
    from audio_midi.midi import write_midi
    with pytest.raises(ValueError): write_midi([],tmp_path/'empty.mid')
    assert not (tmp_path/'empty.mid').exists()
