from audio_midi.events import NoteEvent


def n(p,a,b):return NoteEvent('strings',p,a,b,None,48)


def test_mir_eval_uses_hz_and_distinguishes_onset_from_offset():
    from audio_midi.strings_bounded import evaluate_notes
    s=evaluate_notes([n(60,1,2)],[n(60,1.02,1.2)])
    assert s['onset']['f1']==1 and s['offset']['f1']==0
    assert s['near_onset_coverage']==1


def test_octave_fold_and_one_to_one_matching():
    from audio_midi.strings_bounded import evaluate_notes
    s=evaluate_notes([n(60,1,2)],[n(72,1,2)])
    assert s['onset']['f1']==0 and s['chroma_onset']['f1']==1
    s=evaluate_notes([n(60,1,2)],[n(60,1,2),n(60,1.01,2)])
    assert s['onset']['matched']==1 and s['onset']['f1']==2/3


def test_same_pitch_merge_keeps_polyphony_and_respects_gap():
    from audio_midi.strings_bounded import merge_same_pitch
    out,log=merge_same_pitch([n(60,0,1),n(64,0,2),n(60,1.1,2),n(60,2.2,3)],.12)
    assert [(x.pitch,x.onset,x.offset) for x in out]==[(60,0,2),(64,0,2),(60,2.2,3)]
    assert len(log)==1


def test_sustained_coverage_is_not_onset_coverage():
    from audio_midi.strings_bounded import evaluate_notes
    s=evaluate_notes([n(79,1,2),n(79,2,3)],[n(79,.2,2.5)])
    assert s['near_onset_coverage']==0 and s['sustained_presence_coverage']==1
    assert s['per_reference'][0]['duration_coverage']==1 and s['per_reference'][1]['duration_coverage']==.5


def test_harmonic_prune_requires_audio_evidence_and_keeps_long_upper_voice():
    from audio_midi.strings_bounded import harmonic_prune
    notes=[n(60,0,1),n(72,.1,.2),n(79,.3,.4),n(72,.5,1.2)]
    out,log=harmonic_prune(notes,lambda note:1. if note.pitch==60 else .1)
    assert [(x.pitch,x.onset) for x in out]==[(60,0),(72,.5)] and len(log)==2
    out,log=harmonic_prune(notes,lambda note:1.)
    assert len(out)==4 and not log


def test_metric_results_can_be_written_as_plain_json():
    import json
    from audio_midi.strings_bounded import evaluate_notes
    json.dumps(evaluate_notes([n(60,1,2)],[n(60,1,2)]))


def test_overlap_extension_uses_only_same_pitch_boundary_notes_and_keeps_onset():
    from audio_midi.strings_bounded import overlap_extend
    old=[n(60,.3,1),n(64,.2,.8)]
    shifted=[n(60,.4,1.4),n(64,.2,1.4)]
    out,log=overlap_extend(old,shifted,1.)
    assert [(x.pitch,x.onset,x.offset) for x in out]==[(60,.3,1.4),(64,.2,.8)]
    assert len(log)==1


def test_overlap_extension_does_not_overlap_next_same_pitch_attack():
    from audio_midi.strings_bounded import overlap_extend
    old=[n(60,.3,1),n(60,1.2,1.8)]
    out,log=overlap_extend(old,[n(60,.4,1.6)],1.)
    assert out[0].offset==1.2 and out[1]==old[1]
