from audio_midi.events import NoteEvent
import numpy as np


def ns(p,start,end):return NoteEvent('bass',p,start,end,None,33)


def test_weak_same_pitch_retrigger_merges_but_strong_or_other_pitch_does_not():
    from audio_midi.bass_evidence import merge_retriggers
    notes=[ns(40,0,.5),ns(40,.5,1),ns(40,1,1.5),ns(41,1.5,2)]
    out,log=merge_retriggers(notes,lambda t:{'rise':1.,'flux':.2} if t<1 else {'rise':2.,'flux':.2},1.2,.8)
    assert [(n.pitch,n.onset,n.offset) for n in out]==[(40,0,1),(40,1,1.5),(41,1.5,2)]
    assert len(log)==1 and log[0]['removed_onset']==.5
    out,_=merge_retriggers([ns(40,0,.3),ns(40,.5,1)],lambda t:{'rise':1.,'flux':0},1.2,.8)
    assert len(out)==2


def test_support_runs_require_contiguous_same_pitch_and_minimum_duration():
    from audio_midi.bass_evidence import support_runs
    raw=np.r_[np.full(5,40.),np.nan,np.full(4,40.),np.full(5,41.)]
    runs=support_runs(raw,np.isfinite(raw),.016,.08)
    assert [(r['pitch'],r['start'],r['end']) for r in runs]==[(40,0,.08),(41,.16,.24)]


def test_insert_preserves_monophony_and_does_not_duplicate_existing_same_pitch():
    from audio_midi.bass_evidence import insert_supported
    old=[ns(40,0,1),ns(42,1,2)]
    assert insert_supported(old,ns(40,.4,.8))[1] is False
    new,ok=insert_supported(old,ns(41,.5,.8))
    assert ok and [(n.pitch,n.onset,n.offset) for n in new]==[(40,0,.5),(41,.5,.8),(42,1,2)]
    assert insert_supported(old,ns(41,.95,1.2))[1] is False


def test_harmonic_score_favors_actual_fundamental_and_handles_silence():
    from audio_midi.bass_evidence import harmonic_score
    sr=8000;t=np.arange(sr*.3)/sr
    y=np.sin(2*np.pi*98*t)+.3*np.sin(2*np.pi*196*t)
    assert harmonic_score(y,sr,43)>1.4*harmonic_score(y,sr,31)
    assert harmonic_score(np.zeros(100),sr,40)==0
