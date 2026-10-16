"""Observational diagnostics only. Reference proximity is evidence, not causal truth."""
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching


def match_events(reference, predicted, tolerance=.05, *, octave=False, ignore_pitch=False):
    if not reference or not predicted:return []
    def compatible(a,b):
        return ignore_pitch or (abs(a.pitch-b.pitch)==12 if octave else a.pitch==b.pitch)
    edges=[(i,j) for i,a in enumerate(reference) for j,b in enumerate(predicted)
           if abs(a.onset-b.onset)<=tolerance+1e-9 and compatible(a,b)]
    graph=csr_matrix((np.ones(len(edges)),([i for i,j in edges],[j for i,j in edges])),
                     shape=(len(reference),len(predicted)))
    return [(i,int(j)) for i,j in enumerate(maximum_bipartite_matching(graph,perm_type='column')) if j>=0]


def frame_evidence(trace, pitch, start, end):
    """Half-open source-audio time interval, raw stage vs masked/filled/smoothed."""
    times=np.arange(len(trace['raw_pitches']))*trace['frame_seconds']
    window=(times>=max(0,start)) & (times<end)
    raw=np.rint(trace['raw_pitches'])
    target=window & (raw==pitch)
    def longest(mask):
        padded=np.r_[False,mask,False].astype(int)
        bounds=np.flatnonzero(np.diff(padded))
        return int(max(bounds[1::2]-bounds[::2],default=0))
    return {'start':max(0,start),'end':end,'frames':int(window.sum()),
        'raw_target_frames':int(target.sum()),
        'raw_target_longest_run_ms':longest(target)*trace['frame_seconds']*1000,
        'kept_target_frames':int((window & (np.rint(trace['input_pitches'])==pitch)).sum()),
        'filled_target_frames':int((window & (np.rint(trace['gap_filled_pitches'])==pitch)).sum()),
        'smoothed_target_frames':int((window & (trace['smoothed_pitches']==pitch)).sum()),
        'raw_octave_frames':int((window & (np.abs(raw-pitch)==12)).sum()),
        'raw_target_rejected_unvoiced':int((target & ~trace['voiced']).sum()),
        'raw_target_rejected_low_probability':int((target & ~(trace['probability']>=.2)).sum()),
        'raw_target_rejected_low_energy':int((target & ~(trace['rms']>trace['energy_threshold'])).sum())}


def analyze_errors(reference, predicted, trace, scale=.9995, shift=.14):
    """Both event lists use source-audio time; onset tolerance is in reference time."""
    from dataclasses import replace
    aligned_r=[replace(n,onset=n.onset*scale+shift) for n in reference]
    aligned_p=[replace(n,onset=n.onset*scale+shift) for n in predicted]
    pairs=match_events(aligned_r,aligned_p,.05)
    matched_r={i for i,j in pairs};matched_p={j for i,j in pairs}
    def row(kind,idx,n,other,other_matched):
        near=[{'index':j,'pitch':o.pitch,'onset':o.onset,
               'delta_ms':(o.onset-n.onset)*scale*1000,'already_matched':j in other_matched}
              for j,o in enumerate(other) if abs(o.onset-n.onset)*scale<=.15+1e-9]
        near.sort(key=lambda x:abs(x['delta_ms']))
        same=[e for e in near if e['pitch']==n.pitch]
        octave=[e for e in near if abs(e['pitch']-n.pitch)==12 and abs(e['delta_ms'])<=50+1e-6]
        overlaps=[j for j,o in enumerate(other) if o.pitch==n.pitch and
                  min(o.offset,n.offset)>max(o.onset,n.onset)]
        same_any=[(j,o) for j,o in enumerate(other) if o.pitch==n.pitch]
        nearest=min(same_any,key=lambda x:abs(x[1].onset-n.onset)) if same_any else None
        local=frame_evidence(trace,n.pitch,n.onset-.15,n.onset+.15)
        body=frame_evidence(trace,n.pitch,n.onset,min(n.offset,n.onset+.5))
        segments=[{'index':i,**s} for i,s in enumerate(trace['segments'])
                  if s['pitch']==n.pitch and s['onset']<n.onset+.15 and s['offset']>max(0,n.onset-.15)]
        onsets=[float(t) for t in trace['onsets_seconds'] if abs(t-n.onset)<=.15]
        flags=[]
        if same:flags.append('nearby_same_pitch_onset')
        if octave:flags.append('nearby_octave_candidate')
        if overlaps:flags.append('overlapping_same_pitch_event')
        if local['raw_target_frames']>local['kept_target_frames']:flags.append('target_frames_removed_by_filter')
        if local['kept_target_frames']>local['smoothed_target_frames']:flags.append('target_frames_reduced_after_contour_processing')
        if any(s['status']=='short' for s in segments):flags.append('nearby_short_segment_discarded')
        if not local['raw_target_frames']:flags.append('no_target_pitch_in_raw_onset_window')
        if not flags:flags.append('unresolved')
        return {'kind':kind,'index':idx,'pitch':n.pitch,'onset':n.onset,'offset':n.offset,
            'evidence_flags':flags,'nearby_events':near,'same_pitch_overlap_indices':overlaps,
            'nearest_same_pitch_event':None if nearest is None else
              {'index':nearest[0],'onset':nearest[1].onset,'offset':nearest[1].offset,
               'delta_ms':(nearest[1].onset-n.onset)*scale*1000,'already_matched':nearest[0] in other_matched},
            'onset_window':local,'first_500ms_or_note_end':body,'nearby_contour_segments':segments,
            'nearby_detected_audio_onsets':onsets,
            'interpretation':'Non-exclusive diagnostic evidence. Does not prove event identity, studio truth, or separation causality.'}
    fp=[row('FP',j,n,reference,matched_r) for j,n in enumerate(predicted) if j not in matched_p]
    fn=[row('FN',i,n,predicted,matched_p) for i,n in enumerate(reference) if i not in matched_r]
    def score(t):
        tp=len(match_events(aligned_r,aligned_p,t));return {'matched':tp,'f1':2*tp/(len(reference)+len(predicted)) if reference or predicted else 0}
    return {'counts':{'matched':len(pairs),'predicted':len(predicted),'reference':len(reference),
                     'extra':len(fp),'missed':len(fn),'f1':score(.05)['f1']},
        'matched_pairs':[{'reference_index':i,'prediction_index':j,
                         'delta_ms':(predicted[j].onset-reference[i].onset)*scale*1000} for i,j in pairs],
        'same_pitch_onset_tolerance':{str(t):score(t) for t in [.03,.05,.1,.15,.3]},
        'time_only_50ms_matched':len(match_events(aligned_r,aligned_p,.05,ignore_pitch=True)),
        'octave_only_50ms_matched':len(match_events(aligned_r,aligned_p,.05,octave=True)),
        'false_positives':fp,'false_negatives':fn}
