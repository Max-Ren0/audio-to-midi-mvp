import importlib.util
from pathlib import Path


def helper():
    spec=importlib.util.spec_from_file_location('strings_metrics',Path('outputs/strings-diagnostics/metrics.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_duration_overlap_ignores_note_fragmentation_and_duplicate_unisons():
    m=helper()
    ref=[(0.,2.,60)]
    pred=[(0.,1.,60),(1.,2.,60),(0.,2.,60)]
    score=m.duration_overlap(ref,pred,2.)
    assert score['f1']==1 and score['reference_pitch_seconds']==2 and score['prediction_pitch_seconds']==2


def test_chroma_collapses_octaves_but_exact_pitch_does_not():
    m=helper()
    assert m.duration_overlap([(0,1,60)],[(0,1,72)],1)['f1']==0
    assert m.duration_overlap([(0,1,60)],[(0,1,72)],1,chroma=True)['f1']==1


def test_duration_overlap_clips_edges_preserves_polyphony_and_empty_case():
    m=helper()
    s=m.duration_overlap([(-1,2,60),(0,2,64)],[(0,3,60)],2)
    assert s['matched_pitch_seconds']==2 and s['reference_pitch_seconds']==4 and abs(s['f1']-2/3)<1e-12
    assert m.duration_overlap([],[],2)['f1'] is None
