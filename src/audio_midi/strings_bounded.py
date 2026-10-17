"""Exploratory polyphonic strings metrics and conservative cleanup, reference-free edits."""
from dataclasses import replace
import numpy as np
import mir_eval.transcription as transcription


def evaluate_notes(reference,prediction):
    def arrays(notes,chroma=False):
        intervals=np.array([(n.onset,n.offset) for n in notes],dtype=float).reshape(-1,2)
        pitch=np.array([n.pitch%12+60 if chroma else n.pitch for n in notes],dtype=float)
        return intervals,440.*2**((pitch-69)/12)
    r,rp=arrays(reference);p,pp=arrays(prediction)
    def score(offset,chroma=False):
        rr,rpp=arrays(reference,chroma);pr,ppp=arrays(prediction,chroma)
        values=transcription.precision_recall_f1_overlap(rr,rpp,pr,ppp,onset_tolerance=.05,pitch_tolerance=50,offset_ratio=offset,offset_min_tolerance=.05)
        pairs=transcription.match_notes(rr,rpp,pr,ppp,onset_tolerance=.05,pitch_tolerance=50,offset_ratio=offset,offset_min_tolerance=.05) if len(rr) and len(pr) else []
        return dict(precision=float(values[0]),recall=float(values[1]),f1=float(values[2]),average_overlap=float(values[3]),matched=len(pairs),pairs=[(int(i),int(j)) for i,j in pairs])
    coverage=[]
    for i,n in enumerate(reference):
        near=[j for j,e in enumerate(prediction) if e.pitch==n.pitch and abs(e.onset-n.onset)<=.15+1e-9]
        spans=sorted((max(n.onset,e.onset),min(n.offset,e.offset)) for e in prediction if e.pitch==n.pitch and e.offset>n.onset and e.onset<n.offset)
        union=[]
        for a,b in spans:
            if union and a<=union[-1][1]:union[-1]=(union[-1][0],max(union[-1][1],b))
            else:union.append((a,b))
        overlap=sum(b-a for a,b in union)
        coverage.append({'reference_index':i,'near_onset_prediction_indices':near,'overlap_seconds':overlap,'duration_coverage':overlap/(n.offset-n.onset),'present_80ms':overlap>=.08-1e-9})
    return {'reference':len(reference),'predicted':len(prediction),'onset':score(None),'offset':score(.2),'chroma_onset':score(None,True),
            'near_onset_coverage':sum(bool(r['near_onset_prediction_indices']) for r in coverage)/len(reference) if reference else None,
            'sustained_presence_coverage':sum(r['present_80ms'] for r in coverage)/len(reference) if reference else None,'per_reference':coverage}


def merge_same_pitch(notes,gap):
    grouped={};out=[];log=[]
    for n in notes:grouped.setdefault(n.pitch,[]).append(n)
    for pitch,group in grouped.items():
        merged=[]
        for n in sorted(group,key=lambda n:n.onset):
            if merged and n.onset-merged[-1].offset<=gap+1e-9:
                old=merged[-1];merged[-1]=replace(old,offset=max(old.offset,n.offset));log.append({'pitch':pitch,'removed_onset':n.onset,'old_end':old.offset,'new_end':merged[-1].offset})
            else:merged.append(n)
        out.extend(merged)
    return sorted(out,key=lambda n:(n.onset,n.pitch)),log


def harmonic_prune(notes,energy):
    out=[];log=[]
    for i,n in enumerate(notes):
        supports=[]
        if n.offset-n.onset<=.15+1e-9:
            for j,lower in enumerate(notes):
                overlap=max(0,min(n.offset,lower.offset)-max(n.onset,lower.onset))
                if n.pitch-lower.pitch not in [12,19] or lower.offset-lower.onset<.5 or overlap/(n.offset-n.onset)<.8:continue
                low=energy(replace(lower,onset=n.onset,offset=n.offset));high=energy(n)
                if low>0 and high<.25*low:supports.append({'lower_index':j,'lower_pitch':lower.pitch,'low_energy':low,'upper_energy':high})
        if supports:log.append({'removed_index':i,'pitch':n.pitch,'onset':n.onset,'offset':n.offset,'supports':supports,'meaning':'harmonic hypothesis, not proven ghost note'})
        else:out.append(n)
    return out,log


def overlap_extend(notes,shifted,hop):
    out=[];log=[]
    for i,n in enumerate(notes):
        end=n.offset
        if abs(n.offset/hop-round(n.offset/hop))<1e-7:
            for s in shifted:
                if n.pitch!=s.pitch:continue
                overlap=max(0,min(n.offset,s.offset)-max(n.onset,s.onset))
                if overlap/min(n.offset-n.onset,s.offset-s.onset)>.5:end=max(end,s.offset)
            next_attack=min((m.onset for m in notes if m.pitch==n.pitch and m.onset>n.onset),default=end)
            end=min(end,next_attack)
        if end>n.offset+1e-9:
            log.append({'index':i,'pitch':n.pitch,'onset_unchanged':n.onset,'old_end':n.offset,'new_end':end})
        out.append(replace(n,offset=max(n.offset,end)))
    return out,log
