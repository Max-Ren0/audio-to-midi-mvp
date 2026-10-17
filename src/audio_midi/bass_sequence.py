"""Reference-free source support and note-level sequence selection."""
import numpy as np


def cluster_onsets(rows, tolerance=.04):
    clusters=[]
    for row in sorted(rows,key=lambda r:(r['onset'],r['pitch'])):
        if not clusters or row['onset']-clusters[-1][0]['onset']>tolerance+1e-9:
            clusters.append([row])
        else:clusters[-1].append(row)
    return clusters


def summarize_support(sources, step, minimum=.064):
    fractions=[];votes=[];agreement=[]
    for source in sources:
        masks=[np.asarray(source[m],dtype=bool) for m in ['pyin','crepe','penn']]
        if not all(m.shape==masks[0].shape for m in masks):raise ValueError('Unequal evidence grids')
        counts=[int(m.sum()) for m in masks]
        fractions.append(max(counts)/max(1,len(masks[0])))
        votes.append(max(counts)*step+1e-9>=minimum)
        agreement.append(float(np.mean(masks[1]&masks[2])) if len(masks[0]) else 0.)
    return {'source_count':sum(votes),'source_votes':votes,'fractions':fractions,'neural_agreement':agreement}


def decode_sequence(clusters,onset_cost,jump_penalty,minimum_sources,spacing=.08):
    # Keys keep the last emitted note through skipped clusters, including timing.
    states={(None,None):(0.,[])}
    for cluster in clusters:
        next_states=dict(states)
        for candidate in cluster:
            if candidate['source_count']<minimum_sources and not candidate.get('baseline',False):continue
            if candidate['offset']-candidate['onset']<spacing-1e-9:continue
            best=None
            for (pitch,last_onset),(value,path) in states.items():
                if last_onset is not None and candidate['onset']-last_onset<spacing-1e-9:continue
                penalty=0 if pitch is None else jump_penalty*min(abs(candidate['pitch']-pitch)/12,2)
                score=value+candidate['score']-onset_cost-penalty
                if best is None or score>best[0]:best=(score,path+[candidate])
            if best is None:continue
            key=(candidate['pitch'],candidate['onset'])
            if key not in next_states or best[0]>next_states[key][0]:next_states[key]=best
        states=next_states
    value,path=max(states.values(),key=lambda x:x[0])
    return path,{'objective':value,'state_count':len(states),'selected_count':len(path)}
