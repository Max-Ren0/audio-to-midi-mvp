"""Local MIDI comparison; preserves inputs. All times use each MIDI's tempo map."""
import json, hashlib
from pathlib import Path
from collections import Counter, defaultdict, deque
import mido
import numpy as np
from scipy.signal import fftconvolve
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching

ROOT=Path(__file__).resolve().parents[2]
REF=Path('/Users/ringscherry/Desktop/吉他产品/v0.0/test/不将就 - 李荣浩（改编）.mid')
PRED=ROOT/'outputs/runs/reprocess-20261015-v2/不将就_多乐器.mid'
OUT=Path(__file__).resolve().parent
CATS=['piano','acoustic_guitar','electric_guitar','bass','drums','strings']

def read(path):
    m=mido.MidiFile(path); merged=[]; names={}
    for ti,tr in enumerate(m.tracks):
        tick=0
        for order,msg in enumerate(tr):
            tick+=msg.time;merged.append((tick,ti,order,msg))
            if msg.type=='track_name': names[ti]=msg.name
    tempo=500000;last=0;sec=0.;program=defaultdict(int);active=defaultdict(deque);notes=[];issues=[]
    for tick,ti,order,msg in sorted(merged,key=lambda x:x[:3]):
        sec+=mido.tick2second(tick-last,m.ticks_per_beat,tempo);last=tick
        if msg.type=='set_tempo':tempo=msg.tempo
        if msg.type=='program_change':program[msg.channel]=msg.program
        if msg.type=='note_on' and msg.velocity:
            p=program[msg.channel]
            c='drums' if msg.channel==9 else ('vocal' if p in (52,53) or names.get(ti,'')=='vocal' else 'piano' if p<8 else 'acoustic_guitar' if p in (24,25) else 'electric_guitar' if 26<=p<=31 else 'bass' if 32<=p<=39 else 'strings' if p in (*range(40,46),*range(48,52)) else 'unknown')
            active[ti,msg.channel,msg.note].append(dict(track=ti,category=c,pitch=msg.note,onset=sec,offset=None,program=p))
        elif msg.type=='note_off' or (msg.type=='note_on' and not msg.velocity):
            key=(ti,msg.channel,msg.note)
            if active[key]:
                n=active[key].popleft();n['offset']=sec;notes.append(n)
            else:issues.append(['unmatched_off',ti,msg.note,sec])
    for values in active.values():
        for n in values:issues.append(['unclosed',n])
    return sorted(notes,key=lambda x:x['onset']),dict(seconds=m.length,ppq=m.ticks_per_beat,tracks=names,issues=issues,sha256=hashlib.sha256(path.read_bytes()).hexdigest())

def pairs(ref,pred,tol=.05,category=True,offset=False):
    rows=[];cols=[]
    by=defaultdict(list)
    for j,n in enumerate(pred):by[(n['category'] if category else '',n['pitch'])].append((j,n))
    for i,n in enumerate(ref):
        for j,p in by[(n['category'] if category else '',n['pitch'])]:
            if (category or (n['category']=='drums')==(p['category']=='drums')) and abs(n['onset']-p['onset'])<=tol+1e-9 and (not offset or abs(n['offset']-p['offset'])<=max(.05,.2*(n['offset']-n['onset']))+1e-9):rows.append(i);cols.append(j)
    g=csr_matrix((np.ones(len(rows)),(rows,cols)),shape=(len(ref),len(pred)))
    return [(i,int(j)) for i,j in enumerate(maximum_bipartite_matching(g,perm_type='column')) if j>=0] if ref and pred else []

def score(ref,pred,tol=.05,category=True,offset=False):
    ps=pairs(ref,pred,tol,category,offset);tp=len(ps)
    return dict(reference=len(ref),predicted=len(pred),matched=tp,extra=len(pred)-tp,missed=len(ref)-tp,precision=tp/len(pred) if pred else None,recall=tp/len(ref) if ref else None,f1=2*tp/(len(ref)+len(pred)) if ref or pred else None)

def aligned(pred,a,b):return [dict(n,onset=a*n['onset']+b,offset=a*n['offset']+b) for n in pred]

def evaluate(ref,pred,a,b,duration):
    # Evaluate note onsets within the mapped excerpt; sustained notes beginning before it excluded.
    rr=[n for n in ref if b<=n['onset']<b+a*duration];pp=aligned(pred,a,b)
    return dict(window=[b,b+a*duration],overall=score(rr,pp),per_category={c:score([n for n in rr if n['category']==c],[n for n in pp if n['category']==c]) for c in CATS},tolerance_100ms=score(rr,pp,.1),tolerance_200ms=score(rr,pp,.2),pitch_onset_ignoring_instrument=score(rr,pp,category=False),with_note_offsets=score(rr,pp,offset=True))

if __name__=='__main__':
    ref,rm=read(REF);pred,pm=read(PRED)
    r=[n for n in ref if n['category'] in CATS];p=[n for n in pred if n['category'] in CATS];duration=pm['seconds']
    # Exhaustive coarse affine onset correlation: reference_seconds = scale * prediction_seconds + shift.
    # Pitched notes only, exact pitch (not pitch class); no independent per-track alignment.
    dt=.02;rn=int((rm['seconds']+3)/dt)+1
    R=np.zeros((128,rn))
    for n in r:
        if n['category']!='drums':R[n['pitch'],round(n['onset']/dt)]+=1
    candidates=[]
    for a in np.arange(.85,1.15001,.0025):
        pn=int((duration*a+3)/dt)+1;P=np.zeros((128,pn))
        for n in p:
            if n['category']!='drums':P[n['pitch'],round(a*n['onset']/dt)]+=1
        corr=fftconvolve(R,P[:,::-1],mode='full',axes=1).sum(axis=0)
        # Smooth +-40ms bins for coarse alignment, then refine exact matches below.
        corr=np.convolve(corr,np.ones(5),mode='same')
        valid=np.arange(len(corr));shifts=(valid-(pn-1))*dt
        corr[(shifts<-.5)|(shifts+duration*a>rm['seconds']+.5)]=-1
        for idx in np.argpartition(corr,-3)[-3:]:candidates.append((float(corr[idx]),float(a),float(shifts[idx])))
    candidates.sort(reverse=True); print('coarse candidates',candidates[:12],flush=True)
    best=(-1,None,None)
    rpit=[n for n in r if n['category']!='drums'];ppit=[n for n in p if n['category']!='drums']
    for _,aa,bb in candidates[:8]:
        for a in np.arange(aa-.003,aa+.00301,.0005):
            for b in np.arange(bb-.04,bb+.04001,.005):
                rr=[n for n in rpit if b<=n['onset']<b+a*duration]
                val=score(rr,aligned(ppit,a,b),category=False)['f1']
                if val is not None and val>best[0]:best=(val,float(a),float(b))
    _,a,b=best
    result=dict(reference_path=str(REF),prediction_path=str(PRED),reference_metadata=rm,prediction_metadata=pm,excluded_vocal=dict(reference=sum(n['category']=='vocal' for n in ref),predicted=sum(n['category']=='vocal' for n in pred)),counts_full_reference=dict(Counter(n['category'] for n in r)),counts_prediction=dict(Counter(n['category'] for n in p)),alignment=dict(mapping='reference_seconds = scale * prediction_seconds + shift',scale=a,shift_seconds=b,selection='exploratory optimistic fit to this same sample; exact-pitch onset F1 excluding drums, ignoring instrument; not independently validated synchronization',coarse_top=candidates[:12]),unaligned_first_excerpt=evaluate(r,p,1,0,duration),aligned_excerpt=evaluate(r,p,a,b,duration))
    rr=[n for n in r if b<=n['onset']<b+a*duration];pp=aligned(p,a,b)
    ps=pairs(rr,pp,category=False)
    result['aligned_confusion_matches_ignoring_instrument']=dict(Counter(f"{rr[i]['category']} -> {pp[j]['category']}" for i,j in ps))
    result['excluded_vocal_in_aligned_window']={'reference':sum(n['category']=='vocal' and b<=n['onset']<b+a*duration for n in ref),'predicted':sum(n['category']=='vocal' for n in pred)}
    result['first_onsets']={c:{'reference':next((n['onset'] for n in rr if n['category']==c),None),'predicted_original':next((n['onset'] for n in p if n['category']==c),None)} for c in CATS}
    result['aligned_matches']=[dict(reference=rr[i],prediction=pp[j]) for i,j in pairs(rr,pp)]
    (OUT/'metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ('aligned_matches','reference_metadata','prediction_metadata')},ensure_ascii=False,indent=2))
