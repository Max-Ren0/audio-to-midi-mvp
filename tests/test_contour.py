import numpy as np


def test_contour_keeps_melody_and_bridges_short_holes_without_filling_rest():
    from audio_midi.contour import contour_to_notes
    pitches=np.array([60.]*10+[np.nan]*2+[60.]*10+[np.nan]*10+[62.]*10)
    notes=contour_to_notes(pitches,.01,'vocal',minimum_duration=.08)
    assert [(n.pitch,round(n.onset,2),round(n.offset,2)) for n in notes]==[(60,0,.22),(62,.32,.42)]


def test_contour_rejects_short_noise_and_preserves_pitch_changes():
    from audio_midi.contour import contour_to_notes
    pitches=np.array([60.]*10+[62.]*10+[70.]*2+[np.nan]*10)
    notes=contour_to_notes(pitches,.01,'bass',minimum_duration=.08,smoothing_frames=1)
    assert [(n.pitch,round(n.onset,2),round(n.offset,2)) for n in notes]==[(60,0,.1),(62,.1,.2)]


def test_same_pitch_attacks_preserve_repeated_note_rhythm():
    from audio_midi.contour import contour_to_notes
    notes=contour_to_notes(np.full(100,60.),.01,'bass',onsets_seconds=[.3,.7])
    assert [(round(n.onset,2),round(n.offset,2)) for n in notes]==[(0,.3),(.3,.7),(.7,1.)]
