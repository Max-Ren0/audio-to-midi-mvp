import json


def test_manifest_evaluation_has_sample_counts(tmp_path,capsys):
    from audio_midi.cli import main
    note={'category':'piano','pitch':60,'onset':1,'offset':2}
    (tmp_path/'ref.json').write_text(json.dumps({'notes':[note]}))
    (tmp_path/'pred.json').write_text(json.dumps({'notes':[note]}))
    manifest={'samples':[{'id':str(i),'kind':'real','contains':['piano'],'reference':'ref.json','prediction':'pred.json'} for i in range(4)]}
    p=tmp_path/'manifest.json';p.write_text(json.dumps(manifest))
    assert main(['evaluate-dataset',str(p)])==0
    result=json.loads(capsys.readouterr().out)
    assert result['metrics']['piano']['songs']==4
    assert result['metrics']['piano']['grade']=='insufficient_samples'
