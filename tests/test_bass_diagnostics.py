import numpy as np
import pytest
from audio_midi.contour import contour_to_notes
from audio_midi.events import NoteEvent


def test_trace_is_observational_and_records_short_note_and_retrigger():
    pitches=np.array([40.]*10+[52.]*2+[np.nan]*5+[41.]*20)
    baseline=contour_to_notes(pitches,.01,'bass',smoothing_frames=1,onsets_seconds=[.27])
    trace={}
    got=contour_to_notes(pitches,.01,'bass',smoothing_frames=1,onsets_seconds=[.27],trace=trace)
    assert got==baseline
    assert np.array_equal(trace['input_pitches'],pitches,equal_nan=True)
    assert any(s['status']=='short' and s['pitch']==52 for s in trace['segments'])
    assert any(s['end_reason']=='retrigger' for s in trace['segments'])
    assert sum(s['status']=='emitted' for s in trace['segments'])==len(got)


def test_trace_records_gap_filling_smoothing_and_exact_minimum():
    trace={}
    ns=contour_to_notes(np.array([40.]*5+[np.nan]*2+[40.]*5+[52.]+[40.]*7),.01,'bass',trace=trace)
    assert np.isfinite(trace['gap_filled_pitches'][5:7]).all()
    assert trace['smoothed_pitches'][12]==40
    assert len(ns)==1
    tiny={}
    assert len(contour_to_notes(np.full(5,40.),.016,'bass',trace=tiny))==1
    assert tiny['segments'][0]['end_reason']=='end_of_audio'


def test_diagnostic_matching_is_maximum_and_preserves_pitch():
    from audio_midi.bass_diagnostics import match_events
    ns=lambda times,p=40:[NoteEvent('bass',p,t,t+.1,None,33) for t in times]
    assert len(match_events(ns([0,.08]),ns([.04,0]),.05))==2
    assert len(match_events(ns([0]),ns([0],52),.05))==0
    assert len(match_events(ns([0]),ns([0],52),.05,octave=True))==1
    assert match_events([],ns([0]),.05)==[]


def test_frame_evidence_keeps_rejection_reasons_and_bounds():
    from audio_midi.bass_diagnostics import frame_evidence
    trace={'frame_seconds':.016,'raw_pitches':np.array([40.,40.,52.,np.nan]),
           'voiced':np.array([True,True,True,False]),'probability':np.array([.9,.1,.9,0]),
           'rms':np.array([1.,1.,0.,0.]),'energy_threshold':.025,
           'input_pitches':np.array([40.,np.nan,np.nan,np.nan]),
           'gap_filled_pitches':np.array([40.,np.nan,np.nan,np.nan]),
           'smoothed_pitches':np.array([40.,np.nan,np.nan,np.nan])}
    got=frame_evidence(trace,40,0,.06)
    assert got['raw_target_frames']==2 and got['kept_target_frames']==1
    assert got['raw_target_rejected_low_probability']==1
    assert got['raw_octave_frames']==1
    assert frame_evidence(trace,40,10,11)['frames']==0


def test_error_evidence_does_not_turn_nearby_events_into_matches():
    from audio_midi.bass_diagnostics import analyze_errors
    trace={}
    contour_to_notes(np.full(50,40.),.016,'bass',trace=trace)
    trace.update(raw_pitches=np.full(50,40.),voiced=np.full(50,True),probability=np.full(50,.9),
                 rms=np.ones(50),energy_threshold=.025,onsets_seconds=np.array([.112]))
    r=[NoteEvent('bass',40,0,.8,None,33)]
    p=[NoteEvent('bass',40,.112,.8,None,33)]
    got=analyze_errors(r,p,trace)
    assert got['counts']['matched']==0
    assert got['same_pitch_onset_tolerance']['0.15']['matched']==1
    assert len(got['false_positives'])==len(got['false_negatives'])==1
    fn=got['false_negatives'][0]
    assert fn['onset_window']['start']==0
    assert fn['nearest_same_pitch_event']['index']==0
    assert 'nearby_same_pitch_onset' in fn['evidence_flags']
    assert fn['onset_window']['raw_target_longest_run_ms']>0
