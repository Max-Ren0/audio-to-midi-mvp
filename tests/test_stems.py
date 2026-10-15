from audio_midi.events import NoteEvent as N


def test_stem_filter_never_relabels_guitar_or_invents_missing_categories():
    from audio_midi.stems import select_stem_notes
    notes=[N('piano',60,0,1),N('acoustic_guitar',64,0,1),N('electric_guitar',67,0,1),N('strings',72,0,1),N('drums',36,0,.05),N('drums',82,.2,.25)]
    assert [n.category for n in select_stem_notes(notes,'guitar')]==['acoustic_guitar','electric_guitar']
    assert [n.pitch for n in select_stem_notes(notes,'drums')]==[36]
    assert [n.category for n in select_stem_notes(notes,'other')]==['strings']


def test_stems_must_share_the_source_timeline(tmp_path):
    import pytest
    import soundfile as sf
    import numpy as np
    from audio_midi.stems import validate_stems
    for name in ['vocals','bass','piano','guitar','drums','other']:
        sf.write(tmp_path/f'{name}.wav',np.zeros(8000),8000)
    validate_stems(tmp_path,1)
    sf.write(tmp_path/'bass.wav',np.zeros(4000),8000)
    with pytest.raises(ValueError,match='时间'):
        validate_stems(tmp_path,1)


def test_stem_receipt_rejects_wrong_source_and_changed_audio(tmp_path):
    from audio_midi.stems import write_stem_receipt,verify_stem_receipt
    import soundfile as sf
    import numpy as np
    import pytest
    for name in ['vocals','bass','piano','guitar','drums','other']:
        sf.write(tmp_path/f'{name}.wav',np.zeros(8000),8000)
    write_stem_receipt(tmp_path,'source-one',{'model':'test'})
    verify_stem_receipt(tmp_path,'source-one')
    with pytest.raises(ValueError):verify_stem_receipt(tmp_path,'source-two')
    sf.write(tmp_path/'bass.wav',np.ones(8000)*.1,8000)
    with pytest.raises(ValueError):verify_stem_receipt(tmp_path,'source-one')
