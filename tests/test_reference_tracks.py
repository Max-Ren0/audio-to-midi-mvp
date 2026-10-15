import hashlib,json
from pathlib import Path
import pytest
from audio_midi.events import NoteEvent
from audio_midi.midi import write_midi
from audio_midi.quality import INSTRUMENTS


def manifest(tmp_path):
    tracks={}
    for i,cat in enumerate(INSTRUMENTS):
        path=tmp_path/f'{cat}.mid'
        write_midi([NoteEvent(cat,36 if cat=='drums' else 60,1+i,1.4+i,80,None)],path)
        tracks[cat]={'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    p=tmp_path/'manifest.json';p.write_text(json.dumps({'tracks':tracks}));return p,tracks


def test_preserves_independent_tracks_absolute_time(tmp_path):
    from audio_midi.quality import load_reference_tracks
    p,_=manifest(tmp_path);notes=load_reference_tracks(p)
    assert {(n.category,n.onset) for n in notes}=={(cat,float(1+i)) for i,cat in enumerate(INSTRUMENTS)}


def test_rejects_reference_hash_change(tmp_path):
    from audio_midi.quality import load_reference_tracks
    p,t=manifest(tmp_path);(tmp_path/t['piano']['path']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash'):load_reference_tracks(p)


def test_rejects_wrong_category_even_when_file_hash_is_valid(tmp_path):
    from audio_midi.quality import load_reference_tracks
    p,t=manifest(tmp_path);t['electric_guitar']=dict(t['acoustic_guitar']);p.write_text(json.dumps({'tracks':t}))
    with pytest.raises(ValueError,match='category'):load_reference_tracks(p)


def test_requires_all_six_explicit_references(tmp_path):
    from audio_midi.quality import load_reference_tracks
    p,t=manifest(tmp_path);del t['strings'];p.write_text(json.dumps({'tracks':t}))
    with pytest.raises(ValueError,match='six'):load_reference_tracks(p)
