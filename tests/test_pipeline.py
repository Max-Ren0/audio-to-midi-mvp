import json
import subprocess
from pathlib import Path
import pytest


def test_existing_output_preserved_before_model(tmp_path):
    from audio_midi.pipeline import transcribe_file
    p=tmp_path/'out.mid';p.write_bytes(b'old')
    with pytest.raises(FileExistsError):
        transcribe_file(tmp_path/'none.mp3',p,checkpoint=tmp_path/'none.ckpt')
    assert p.read_bytes()==b'old'


def test_bad_mp3_creates_no_output(tmp_path):
    from audio_midi.pipeline import transcribe_file
    p=tmp_path/'bad.mp3';p.write_bytes(b'bad')
    out=tmp_path/'out.mid'
    with pytest.raises(ValueError):transcribe_file(p,out,checkpoint=tmp_path/'none')
    assert not out.exists()


def test_report_collision_preserved(tmp_path):
    from audio_midi.pipeline import transcribe_file
    p=tmp_path/'out.report.json';p.write_text('keep')
    with pytest.raises(FileExistsError):transcribe_file(tmp_path/'none.mp3',tmp_path/'out.mid',checkpoint=tmp_path/'none')
    assert p.read_text()=='keep'


def test_atomic_publish_rolls_back_on_collision(tmp_path):
    from audio_midi.pipeline import publish
    source=tmp_path/'source';source.write_bytes(b'new')
    first=tmp_path/'one'; second=tmp_path/'two';second.write_bytes(b'keep')
    with pytest.raises(FileExistsError):publish([(source,first),(source,second)],False)
    assert not first.exists() and second.read_bytes()==b'keep'


def test_pipeline_publishes_real_midi_and_reports_decoder_errors(tmp_path,monkeypatch):
    import audio_midi.pipeline as pipeline
    from audio_midi.worker import WorkerResult
    from test_audio import make_audio
    import mido
    source=tmp_path/'input.mp3';make_audio(source,seconds=2)
    ckpt=tmp_path/'model';ckpt.write_bytes(b'checkpoint')
    def model_boundary(command,deadline,log_path,memory_limit_bytes):
        Path(command[5]).write_text(json.dumps({'notes':[{'category':'piano','pitch':60,'onset':.1,'offset':1.,'velocity':None,'program':0}], 'decode_errors':{'tie':3}}))
        return WorkerResult(1_000_000,1,.01)
    monkeypatch.setattr(pipeline,'run_command',model_boundary)
    out=tmp_path/'out.mid'
    report=pipeline.transcribe_file(source,out,checkpoint=ckpt)
    assert mido.MidiFile(out).type==1
    assert report['note_count']==1 and report['missing_categories']==['acoustic_guitar','electric_guitar','bass','drums','strings','vocal']
    assert report['quality_metrics'] is None
    assert any('解码' in w for w in report['warnings'])
    assert json.loads(out.with_suffix('.report.json').read_text())['note_count']==1
