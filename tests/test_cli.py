import json
from pathlib import Path


def test_cli_invalid_input_returns_nonzero(tmp_path,capsys):
    from audio_midi.cli import main
    assert main(['transcribe',str(tmp_path/'bad.mp3'),'--output',str(tmp_path/'out.mid')])==2
    assert 'MP3' in capsys.readouterr().err


def test_doctor_reports_actual_environment(capsys):
    from audio_midi.cli import main
    assert main(['doctor'])==0
    info=json.loads(capsys.readouterr().out)
    assert info['ffmpeg'] and info['memory_bytes']>0


def test_evaluation_does_not_grade_single_song(tmp_path,capsys):
    from audio_midi.cli import main
    note={'category':'piano','pitch':60,'onset':1,'offset':2}
    a=tmp_path/'reference.json';b=tmp_path/'prediction.json'
    a.write_text(json.dumps({'notes':[note]}));b.write_text(json.dumps({'notes':[note]}))
    assert main(['evaluate',str(a),str(b)])==0
    r=json.loads(capsys.readouterr().out)
    assert r['metrics']['piano']['f1']==1
    assert r['classification']=='insufficient_samples'


def test_prepare_does_not_replace_invalid_existing_weight(tmp_path,capsys):
    from audio_midi.cli import main
    p=tmp_path/'weight.ckpt';p.write_bytes(b'user file')
    assert main(['prepare','--checkpoint',str(p)])==2
    assert p.read_bytes()==b'user file'
