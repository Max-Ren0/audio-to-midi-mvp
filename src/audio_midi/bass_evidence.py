"""Conservative monophonic edits driven only by acoustic evidence."""
from dataclasses import replace
import numpy as np


def merge_retriggers(notes, feature, rise_limit, flux_limit):
    out=[]; log=[]
    for n in notes:
        f=feature(n.onset)
        if (out and out[-1].pitch==n.pitch and 0<=n.onset-out[-1].offset<=.08+1e-9
                and f['rise']<rise_limit and f['flux']<flux_limit):
            log.append({'removed_onset':n.onset,'pitch':n.pitch,'evidence':f})
            out[-1]=replace(out[-1],offset=max(out[-1].offset,n.offset))
        else:out.append(n)
    return out,log


def support_runs(pitches, valid, step, minimum):
    pitches=np.asarray(pitches);valid=np.asarray(valid)&np.isfinite(pitches)
    out=[];i=0
    while i<len(pitches):
        if not valid[i]:i+=1;continue
        p=int(np.rint(pitches[i]));j=i+1
        while j<len(pitches) and valid[j] and int(np.rint(pitches[j]))==p:j+=1
        if (j-i)*step+1e-9>=minimum:
            out.append({'pitch':p,'start':i*step,'end':j*step,'first_frame':i,'last_frame_exclusive':j})
        i=j
    return out


def insert_supported(notes, new, minimum=.08):
    """Insert without duplicates or short remnants; keep all edits monophonic."""
    if any(abs(n.onset-new.onset)<minimum-1e-9 for n in notes):return list(notes),False
    if any(n.pitch==new.pitch and n.onset<=new.onset<n.offset for n in notes):return list(notes),False
    previous=[n for n in notes if n.onset<new.onset]
    following=[n for n in notes if n.onset>new.onset]
    end=min(new.offset,following[0].onset if following else new.offset)
    if end-new.onset<minimum-1e-9:return list(notes),False
    if previous and new.onset-previous[-1].onset<minimum-1e-9:return list(notes),False
    out=[replace(n,offset=new.onset) if n.onset<new.onset<n.offset else n for n in notes]
    out.append(replace(new,offset=end));return sorted(out,key=lambda n:n.onset),True


def harmonic_score(y, sr, pitch):
    y=np.asarray(y,dtype=float)
    if len(y)<2:return 0.
    spectrum=np.abs(np.fft.rfft(y[:int(sr*.32)]*np.hanning(min(len(y),int(sr*.32))),n=8192))
    frequencies=np.fft.rfftfreq(8192,1/sr);fundamental=440*2**((pitch-69)/12)
    score=0.
    for k in range(1,6):
        f=fundamental*k;band=np.abs(frequencies-f)<=max(2.,.02*f)
        if band.any():score+=float(spectrum[band].max())/k
    return score
