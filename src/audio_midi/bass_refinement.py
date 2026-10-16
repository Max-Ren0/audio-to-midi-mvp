"""Reference-free, bounded bass research refinements. Existing default is unchanged."""
import math
import numpy as np
from .contour import contour_to_notes
from .events import NoteEvent,PROGRAMS


def extend_confidence(raw,voiced,probability,rms,frame_seconds,high,low,extension_seconds,energy_threshold):
    raw,voiced,probability,rms=(np.asarray(a) for a in (raw,voiced,probability,rms))
    if not 0<=low<=high<=1 or frame_seconds<=0 or extension_seconds<0:
        raise ValueError('Invalid confidence bounds')
    if not (raw.ndim==1 and raw.shape==voiced.shape==probability.shape==rms.shape):
        raise ValueError('Mismatched frame arrays')
    rounded=np.rint(raw)
    valid=np.isfinite(raw)&voiced&(rms>energy_threshold)
    seeds=valid&(probability>=high);eligible=valid&(probability>=low)
    keep=seeds.copy();radius=int(math.floor(extension_seconds/frame_seconds+1e-9))
    start=0
    while start<len(raw):
        if not eligible[start]:start+=1;continue
        end=start+1
        while end<len(raw) and eligible[end] and rounded[end]==rounded[start]:end+=1
        indices=np.flatnonzero(seeds[start:end])+start
        if len(indices):
            for i in range(start,end):
                if np.min(np.abs(indices-i))<=radius:keep[i]=True
        start=end
    return np.where(keep,raw,np.nan),{'seed_frames':np.flatnonzero(seeds).tolist(),
        'added_frames':np.flatnonzero(keep&~seeds).tolist(),
        'retained_frames':int(keep.sum()),'high':high,'low':low,'extension_seconds':extension_seconds}


def bounded_backtrack(attacks,envelope,frame_seconds,maximum=.096):
    """Use local envelope minima only; reject valleys beyond the bounded lookback."""
    envelope=np.asarray(envelope)
    valleys=[0]+[i for i in range(1,len(envelope)-1) if envelope[i]<=envelope[i-1] and envelope[i]<envelope[i+1]]
    out=[]
    for t in attacks:
        i=round(float(t)/frame_seconds)
        before=[v for v in valleys if v<=i]
        candidate=before[-1]*frame_seconds if before else float(t)
        out.append(candidate if 0<=float(t)-candidate<=maximum+1e-9 else float(t))
    return np.array(out)


def attack_led_notes(pitches,probability,attacks,frame_seconds,duration,lookahead=.32,minimum_support=.08,minimum_spacing=.08):
    pitches=np.asarray(pitches);probability=np.asarray(probability)
    if frame_seconds<=0 or duration<=0 or lookahead<=0 or minimum_support<=0 or minimum_spacing<=0:
        raise ValueError('Invalid timing bounds')
    if pitches.ndim!=1 or pitches.shape!=probability.shape:raise ValueError('Mismatched pitch/probability')
    clean=[]
    for t in sorted(set(float(t) for t in attacks if math.isfinite(t) and 0<=t<duration)):
        if not clean or t-clean[-1]>=minimum_spacing-1e-9:clean.append(t)
    if not clean:
        notes=contour_to_notes(pitches,frame_seconds,'bass')
        return notes,[{'method':'no_attack_fallback','onset':n.onset,'pitch':n.pitch} for n in notes]
    rounded=np.rint(pitches);times=np.arange(len(pitches))*frame_seconds
    notes=[];evidence=[]
    for j,t in enumerate(clean):
        end=clean[j+1] if j+1<len(clean) else duration
        window=(times>=t)&(times<min(duration,t+lookahead))&np.isfinite(rounded)
        candidates=[]
        for pitch in np.unique(rounded[window]):
            idx=np.flatnonzero(window&(rounded==pitch))
            if len(idx)*frame_seconds>=minimum_support-1e-9:
                candidates.append((float(np.nan_to_num(probability[idx],nan=0).sum()),len(idx),int(pitch),idx))
        if not candidates:continue
        _,_,pitch,idx=max(candidates,key=lambda x:(x[0],x[1],-x[2]))
        support=np.flatnonzero((times>=t)&(times<min(duration,max(end,t+lookahead)))&(rounded==pitch))
        offset=min(end,(int(support[-1])+1)*frame_seconds)
        if offset-t<minimum_support-1e-9:continue
        notes.append(NoteEvent('bass',pitch,t,offset,None,PROGRAMS['bass']))
        evidence.append({'method':'attack_led','onset':t,'offset':offset,'pitch':pitch,
                         'support_start':float(times[idx[0]]),'support_end':float(times[idx[-1]]+frame_seconds),
                         'support_frames':idx.tolist(),'weighted_vote':float(np.nan_to_num(probability[idx],nan=0).sum())})
    # Preserve a sustained opening note when the file starts mid-note, before the first attack.
    opening=contour_to_notes(pitches,frame_seconds,'bass')
    for n in opening:
        if n.onset==0 and min(n.offset,clean[0])>=minimum_support:
            n=NoteEvent('bass',n.pitch,0,min(n.offset,clean[0]),None,PROGRAMS['bass'])
            notes.insert(0,n);evidence.insert(0,{'method':'opening_contour','onset':0,'pitch':n.pitch})
            break
    return notes,evidence
