import pytest


def test_one_to_one_and_wrong_pitch():
    from audio_midi.evaluate import evaluate
    from audio_midi.events import NoteEvent as N
    r=evaluate([N('piano',60,1,2)],[N('piano',60,1,2),N('piano',60,1.01,2),N('piano',61,1,2)])['piano']
    assert (r['tp'],r['fp'],r['fn'])==(1,2,0)
    assert r['f1']==pytest.approx(.5)


def test_maximum_matching_not_greedy():
    from audio_midi.evaluate import evaluate
    from audio_midi.events import NoteEvent as N
    # first reference can match either prediction; second only .04
    r=evaluate([N('piano',60,0,1),N('piano',60,.08,1)],[N('piano',60,.04,1),N('piano',60,0,1)])['piano']
    assert r['tp']==2


def test_empty_class_extra_predictions_and_onset_only():
    from audio_midi.evaluate import evaluate
    from audio_midi.events import NoteEvent as N
    r=evaluate([N('piano',60,1,2)],[N('piano',61,1.05,2),N('bass',40,2,3)])
    assert r['piano']['tp']==0 and r['piano']['onset_only_tp']==1
    assert r['bass']['fp']==1
    assert r['strings']['f1'] is None


def test_dataset_requires_five_real_songs_and_reports_absent_extras():
    from audio_midi.evaluate import evaluate_dataset
    from audio_midi.events import NoteEvent as N
    records=[{'id':str(i),'kind':'real','contains':['piano'],'reference':[N('piano',60,1,2)],'predicted':[N('piano',60,1,2),N('bass',40,1,2)]} for i in range(5)]
    result=evaluate_dataset(records)
    assert result['piano']['grade']=='usable'
    assert result['piano']['songs']==5
    assert result['bass']['grade']=='insufficient_samples'
    assert result['bass']['absent_category_extra_notes']==5
    assert evaluate_dataset(records[:4])['piano']['grade']=='insufficient_samples'
    for r in records:r['kind']='synthetic'
    assert evaluate_dataset(records)['piano']['grade']=='insufficient_samples'


def test_invalid_note_data_is_rejected():
    from audio_midi.evaluate import evaluate
    from audio_midi.events import NoteEvent as N
    with pytest.raises(ValueError):evaluate([N('piano',60,float('nan'),1)],[])
