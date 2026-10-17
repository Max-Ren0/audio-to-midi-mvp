import numpy as np


def test_onset_clusters_are_not_transitively_chained():
    from audio_midi.bass_sequence import cluster_onsets
    rows=[{'onset':t,'pitch':40} for t in [0,.03,.06]]
    out=cluster_onsets(rows,.04)
    assert [[n['onset'] for n in c] for c in out]==[[0,.03],[.06]]


def test_source_votes_do_not_count_three_estimators_as_three_sources():
    from audio_midi.bass_sequence import summarize_support
    sources=[{'pyin':np.ones(5,dtype=bool),'crepe':np.ones(5,dtype=bool),'penn':np.ones(5,dtype=bool)},
             {'pyin':np.zeros(5,dtype=bool),'crepe':np.zeros(5,dtype=bool),'penn':np.zeros(5,dtype=bool)}]
    x=summarize_support(sources,.016)
    assert x['source_count']==1 and x['fractions']==[1.,0.]


def test_sequence_skips_unsupported_events_and_allows_real_leaps():
    from audio_midi.bass_sequence import decode_sequence
    def n(t,p,score,sources=2):return {'onset':t,'offset':t+.2,'pitch':p,'score':score,'source_count':sources,'baseline':False}
    clusters=[[n(0,30,1)],[n(.3,42,1)],[n(.6,43,.1)],[n(.9,44,1,1)]]
    selected,log=decode_sequence(clusters,.2,.1,2,.08)
    assert [(x['onset'],x['pitch']) for x in selected]==[(0,30),(.3,42)]
    assert np.isfinite(log['objective'])


def test_sequence_spacing_and_empty_input():
    from audio_midi.bass_sequence import decode_sequence
    a={'onset':0.,'offset':.2,'pitch':40,'score':.8,'source_count':2,'baseline':False}
    b=a|{'onset':.05,'score':1.}
    out,_=decode_sequence([[a],[b]],.2,0,2,.08)
    assert len(out)==1 and out[0]['onset']==.05
    assert decode_sequence([],.2,0,2,.08)[0]==[]
