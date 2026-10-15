from bisect import bisect_left, bisect_right
from statistics import median
from math import isfinite
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching
from .events import CATEGORIES,NoteEvent


def _match(reference, predicted, pitch=True):
    if not reference or not predicted:
        return []
    ordered=sorted(enumerate(predicted),key=lambda x:x[1].onset)
    times=[n.onset for _,n in ordered]
    rows=[];cols=[]
    for i,n in enumerate(reference):
        lo=bisect_left(times,n.onset-.05-1e-9);hi=bisect_right(times,n.onset+.05+1e-9)
        for j,m in ordered[lo:hi]:
            if not pitch or n.pitch==m.pitch:
                rows.append(i);cols.append(j)
    graph=csr_matrix((np.ones(len(rows)),(rows,cols)),shape=(len(reference),len(predicted)))
    matches=maximum_bipartite_matching(graph,perm_type='column')
    return [(i,int(j)) for i,j in enumerate(matches) if j>=0]


def evaluate(reference: list[NoteEvent], predicted: list[NoteEvent]) -> dict:
    for n in [*reference,*predicted]:
        if n.category not in CATEGORIES or not isinstance(n.pitch,int) or not 0<=n.pitch<=127 or not isfinite(n.onset) or n.onset<0:
            raise ValueError('Invalid annotation or prediction')
    result={}
    for category in CATEGORIES:
        ref=[n for n in reference if n.category==category]
        pred=[n for n in predicted if n.category==category]
        pairs=_match(ref,pred)
        onset_pairs=_match(ref,pred,False)
        tp=len(pairs);fp=len(pred)-tp;fn=len(ref)-tp
        result[category]={'tp':tp,'fp':fp,'fn':fn,'f1':2*tp/(2*tp+fp+fn) if ref or pred else None,
          'onset_only_tp':len(onset_pairs), 'onset_only_f1':2*len(onset_pairs)/(len(ref)+len(pred)) if ref or pred else None,
          'onset_error_median_seconds':median(abs(ref[i].onset-pred[j].onset) for i,j in pairs) if pairs else None}
    return result


def evaluate_dataset(records: list[dict]) -> dict:
    ids=[r['id'] for r in records]
    if len(set(ids))!=len(ids):
        raise ValueError('Duplicate song id')
    totals={c:{'tp':0,'fp':0,'fn':0,'songs':0,'absent_category_extra_notes':0} for c in CATEGORIES}
    onset_counts={c:[0,0] for c in CATEGORIES};errors={c:[] for c in CATEGORIES}
    for record in records:
        if not set(record['contains']).issubset(CATEGORIES):
            raise ValueError('Unknown annotated category')
        metrics=evaluate(record['reference'],record['predicted'])
        if record['kind']!='real':
            continue
        if any(n.category not in record['contains'] for n in record['reference']):
            raise ValueError('Reference notes contradict contains metadata')
        for c in CATEGORIES:
            ref=[n for n in record['reference'] if n.category==c]
            pred=[n for n in record['predicted'] if n.category==c]
            t=totals[c]
            if c not in record['contains']:
                t['absent_category_extra_notes']+=len(pred);continue
            t['songs']+=1
            for key in ('tp','fp','fn'):t[key]+=metrics[c][key]
            onset_counts[c][0]+=metrics[c]['onset_only_tp']
            onset_counts[c][1]+=len(ref)+len(pred)
            errors[c].extend(abs(ref[i].onset-pred[j].onset) for i,j in _match(ref,pred))
    for c,t in totals.items():
        den=2*t['tp']+t['fp']+t['fn'];f1=2*t['tp']/den if den else None
        t['f1']=f1
        t['onset_only_f1']=2*onset_counts[c][0]/onset_counts[c][1] if onset_counts[c][1] else None
        t['onset_error_median_seconds']=median(errors[c]) if errors[c] else None
        t['grade']='insufficient_samples' if t['songs']<5 or f1 is None else ('usable' if f1>=.70 else 'draft' if f1>=.40 else 'below_threshold')
        t['threshold_status']='proposed_pending_final_confirmation'
    return totals
