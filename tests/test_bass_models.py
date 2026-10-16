import numpy as np
import pytest


def test_nearest_grid_preserves_gap_and_declared_time_origin():
    from audio_midi.bass_models import nearest_grid
    f0=np.array([40.,np.nan,42.,43.,44.]);prob=np.array([1.,0.,1.,1.,1.])
    f,p,idx=nearest_grid(f0,prob,.01,.016,3)
    assert idx.tolist()==[0,2,3] and f.tolist()==[40,42,43]
    f,p,idx=nearest_grid(f0,prob,.01,.01,4)
    assert np.isnan(f[1]) and p[1]==0
    with pytest.raises(ValueError):nearest_grid(f0,prob,.01,.016,10)


def test_vote_cap_prevents_later_note_dominating_first_note():
    from audio_midi.bass_refinement import attack_led_notes
    pitches=np.r_[np.full(15,40.),np.full(35,41.)]
    attacks=np.array([0,.1])
    original,_=attack_led_notes(pitches,np.ones(50),attacks,.01,.5)
    fixed,evidence=attack_led_notes(pitches,np.ones(50),attacks,.01,.5,vote_guard=0)
    assert original[0].pitch==41 and fixed[0].pitch==40
    assert max(evidence[0]['support_frames'])<10
    with pytest.raises(ValueError):attack_led_notes(pitches,np.ones(50),attacks,.01,.5,vote_guard=-.1)


def test_native_frequency_is_converted_to_midi_using_440hz_reference():
    from audio_midi.bass_models import frequency_to_midi
    result=frequency_to_midi(np.array([440.,82.406889,0.,np.nan]))
    assert abs(result[0]-69)<1e-9 and abs(result[1]-40)<1e-5
    assert np.isnan(result[2:]).all()
