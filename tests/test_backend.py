from types import SimpleNamespace as Raw


def test_raw_vocal_identity_and_drum_render_duration():
    from audio_midi.backends.selected import normalize_raw
    result,dropped=normalize_raw([
      Raw(program=100,is_drum=False,pitch=65,onset=0.,offset=1.,velocity=1),
      Raw(program=0,is_drum=True,pitch=36,onset=.2,offset=.21,velocity=1),
      Raw(program=46,is_drum=False,pitch=70,onset=0.,offset=1.,velocity=1)])
    assert [(n.category,n.program,n.velocity) for n in result]==[('vocal',100,None),('drums',0,None)]
    assert result[1].offset==.25
    assert dropped=={'46':1}
