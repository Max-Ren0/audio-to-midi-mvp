import numpy as np
import pytest


def test_confidence_extension_requires_high_seed_same_pitch_and_energy():
    from audio_midi.bass_refinement import extend_confidence
    raw=np.array([40.,40.,40.,41.,41.,np.nan,40.,40.])
    prob=np.array([.1,.3,.1,.1,.1,.3,.3,.1]);energy=np.array([1,1,1,1,1,1,1,0])
    got,why=extend_confidence(raw,np.isfinite(raw),prob,energy,.01,.2,.1,.02,.1)
    assert np.all(got[:3]==40)
    assert np.isnan(got[3:6]).all() and np.isnan(got[7])
    assert why['added_frames']==[0,2]


def test_extension_is_bounded_and_does_not_mutate_inputs():
    from audio_midi.bass_refinement import extend_confidence
    raw=np.full(10,40.);before=raw.copy();prob=np.full(10,.1);prob[5]=.3
    got,_=extend_confidence(raw,np.ones(10,bool),prob,np.ones(10),.01,.2,.1,.02,.1)
    assert np.flatnonzero(np.isfinite(got)).tolist()==[3,4,5,6,7]
    assert np.array_equal(raw,before)
    with pytest.raises(ValueError):extend_confidence(raw,np.ones(10,bool),prob,np.ones(10),.01,.1,.2,.02,.1)


def test_attack_led_pitch_is_chosen_after_attack_without_moving_to_stability_time():
    from audio_midi.bass_refinement import attack_led_notes
    pitches=np.r_[np.full(10,np.nan),np.full(30,40.)]
    notes,rows=attack_led_notes(pitches,np.ones(40),np.array([.02]),.01,.4)
    assert len(notes)==1 and notes[0].pitch==40 and notes[0].onset==.02
    assert rows[0]['support_start']>=.1


def test_attack_led_keeps_repeated_notes_and_rejects_short_or_empty_evidence():
    from audio_midi.bass_refinement import attack_led_notes
    notes,_=attack_led_notes(np.full(50,40.),np.ones(50),np.array([0,.2,.22]),.01,.5)
    assert [(n.onset,n.offset) for n in notes]==[(0,.2),(.2,.5)]
    assert attack_led_notes(np.full(50,np.nan),np.ones(50),np.array([.2]),.01,.5)[0]==[]
    assert attack_led_notes(np.r_[np.full(4,40.),np.full(46,np.nan)],np.ones(50),np.array([0]),.01,.5)[0]==[]


def test_no_attack_falls_back_to_existing_contour_and_bounded_backtracking():
    from audio_midi.bass_refinement import attack_led_notes,bounded_backtrack
    notes,_=attack_led_notes(np.full(30,40.),np.ones(30),np.array([]),.01,.3)
    assert len(notes)==1 and notes[0].onset==0
    got=bounded_backtrack(np.array([.1,.5]),np.array([0,0,1,2,1,0,1,2,1,0,1]),.05,.096)
    assert all(0<=a-b<=.096+1e-9 for a,b in zip([.1,.5],got))


def test_attack_led_opening_and_audio_end_are_preserved_without_negative_notes():
    from audio_midi.bass_refinement import attack_led_notes
    pitches=np.r_[np.full(20,40.),np.full(20,41.)]
    notes,_=attack_led_notes(pitches,np.ones(40),np.array([.2,.39]),.01,.4)
    assert notes[0].onset==0
    assert all(0<=n.onset<n.offset<=.4 for n in notes)
    with pytest.raises(ValueError):attack_led_notes(pitches,np.ones(39),np.array([.2]),.01,.4)
