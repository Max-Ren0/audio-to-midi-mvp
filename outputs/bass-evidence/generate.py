"""Reference-free, fixed-profile acoustic refinement of the frozen bass."""
import argparse,importlib.util,json,hashlib
from pathlib import Path
from dataclasses import asdict,replace
import numpy as np,librosa,soundfile as sf
from audio_midi.events import NoteEvent
from audio_midi.bass_models import nearest_grid,frequency_to_midi
from audio_midi.bass_evidence import merge_retriggers,support_runs,insert_supported,harmonic_score
from audio_midi.midi import write_midi
ROOT=Path('outputs/bass-evidence')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('prior_generator','outputs/bass-models/generate.py');prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)

def acoustic():
 f=prior.features('demucs','pyin');y,sr=sf.read(f['wave'],always_2d=True,dtype='float32');y=librosa.resample(y.mean(axis=1),orig_sr=sr,target_sr=8000)
 rms=librosa.feature.rms(y=y,frame_length=256,hop_length=32)[0]
 flux=f['short_envelope'];normalizer=max(1e-9,float(np.median([flux[max(0,int(t/.004)):min(len(flux),int(t/.004)+17)].max() for t in f['short_onsets']])))
 rise=np.maximum(0,np.diff(np.log(np.maximum(rms,1e-6)),prepend=np.log(max(rms[0],1e-6))))
 anchors=librosa.onset.onset_detect(onset_envelope=rise,sr=8000,hop_length=32,units='time')
 anchors=np.unique(np.r_[anchors,prior.bounded_backtrack(f['short_onsets'],flux,.004,.032)])
 def feature(t):
  pre=rms[(np.arange(len(rms))*.004>=t-.064)&(np.arange(len(rms))*.004<t-.016)]
  post=rms[(np.arange(len(rms))*.004>=t+.016)&(np.arange(len(rms))*.004<t+.064)]
  amp=float(np.median(post)/max(float(np.median(pre)) if len(pre) else 0,1e-6)) if len(post) else 0.
  a=max(0,int(round(t/.004)));b=min(len(flux),a+17)
  return {'rise':amp,'flux':float(flux[a:b].max()/normalizer) if b>a else 0.,'rms_rise_salience':float(rise[max(0,a-2):min(len(rise),a+3)].max()) if a<len(rise) else 0.}
 neural={};sources={f['wave']:f['wave_sha256'],f['pitchfile']:f['pitch_sha256']}
 for m in ['crepe','penn']:
  path=Path(f'work/bass-models/{m}-full.npz');rec=json.loads(path.with_suffix('.json').read_text())
  assert rec['source_audio_sha256']==f['wave_sha256'] and rec['output_sha256']==sha(path)
  with np.load(path) as z:hz,q,_=nearest_grid(z['f0'],z['periodicity'],.01,.016,len(f['raw']))
  neural[m]=(frequency_to_midi(hz),q);sources[str(path)]=sha(path);sources[str(path.with_suffix('.json'))]=sha(path.with_suffix('.json'))
 return f,y,feature,anchors,neural,sources,{'rms':rms,'flux':flux,'rms_rise':rise,'anchors':anchors,'flux_normalizer':normalizer}

def add_notes(notes,profile,f,feature,anchors,neural):
 raw=f['raw'];c,cq=neural['crepe'];p,pq=neural['penn'];cok=(cq>=.21)&np.isfinite(c);pok=(pq>=.2)&np.isfinite(p)
 with np.errstate(invalid='ignore'):
  agreec=cok&(np.rint(c)==np.rint(raw));agreep=pok&(np.rint(p)==np.rint(raw))
  if profile=='A3':pitch=c;valid=cok&pok&(np.rint(c)==np.rint(p))
  else:pitch=raw;valid=np.isfinite(raw)&f['voiced']&(f['probability']>=.05)&((agreec&agreep) if profile=='A2' else (agreec|agreep))
 valid &= f['rms']>=f['energy'];log=[];out=list(notes)
 for run in support_runs(pitch,valid,.016,.08):
  options=[float(t) for t in anchors if run['start']-.256<=t<=run['start']+.032 and (feature(t)['rise']>=1.1 or feature(t)['flux']>=.5)]
  if not options:log.append(run|{'accepted':False,'reason':'no credible audio anchor'});continue
  t=min(options,key=lambda t:(abs(t-run['start']),t));end=min(f['duration'],run['end'])
  n=NoteEvent('bass',run['pitch'],t,end,None,33);out,ok=insert_supported(out,n)
  log.append(run|{'accepted':ok,'onset':t,'offset':end,'audio':feature(t),'reason':'inserted' if ok else 'duplicate/onset spacing/short remnant'})
 return out,log

def correct(notes,profile,y,feature,anchors,neural):
 out=list(notes);log=[]
 if 'O' in profile:
  strict='O2' in profile;ratio=2. if strict else 1.5
  for i,n in enumerate(out):
   segment=y[max(0,int(n.onset*8000)):min(len(y),int(min(n.offset,n.onset+.32)*8000))]
   base=harmonic_score(segment,8000,n.pitch);options=[]
   for pitch in [n.pitch-12,n.pitch+12]:
    if not 0<=pitch<=127:continue
    support={}
    for m,threshold in [('crepe',.21),('penn',.2)]:
     raw,q=neural[m];a=max(0,int(np.ceil(n.onset/.016)));b=min(len(raw),int(np.ceil(min(n.offset,n.onset+.32)/.016)))
     mask=(q[a:b]>=threshold)&np.isfinite(raw[a:b])&(np.rint(raw[a:b])==pitch)
     support[m]=float(mask.sum()*.016)
    score=harmonic_score(segment,8000,pitch);supported=all(s>=.064-1e-9 for s in support.values()) if strict else any(s>=.064-1e-9 for s in support.values())
    evidence={'kind':'octave','index':i,'old_pitch':n.pitch,'new_pitch':pitch,'onset':n.onset,'base_score':base,'candidate_score':score,'support_seconds':support,'eligible':base>0 and score>=base*ratio and supported}
    log.append(evidence)
    if evidence['eligible']:options.append((score,pitch,evidence))
   if options:
    _,pitch,e=max(options,key=lambda x:(x[0],-x[1]));out[i]=replace(n,pitch=pitch);e['accepted']=True
 if 'R1' in profile:
  for i,n in enumerate(out):
   current=feature(n.onset);options=[]
   for t in anchors:
    t=float(t);f=feature(t)
    if abs(t-n.onset)>.096+1e-9 or abs(t-n.onset)<.002:continue
    if f['rms_rise_salience']<max(1e-9,1.5*current['rms_rise_salience']) or f['rise']<1.1:continue
    if i and t-out[i-1].onset<.08-1e-9:continue
    if i+1<len(out) and out[i+1].onset-t<.08-1e-9:continue
    if n.offset-t<.08-1e-9:continue
    options.append((abs(t-n.onset),-f['rms_rise_salience'],t,f))
   if options:
    _,_,t,e=min(options);out[i]=replace(n,onset=t)
    if i and out[i-1].offset>t:out[i-1]=replace(out[i-1],offset=t)
    log.append({'kind':'retime','index':i,'old_onset':n.onset,'new_onset':t,'current':current,'new':e,'accepted':True})
 return out,log

def main():
 p=argparse.ArgumentParser();p.add_argument('phase',type=int,choices=[1,2,3]);p.add_argument('--output',type=Path);p.add_argument('--ledger',type=Path);p.add_argument('--previous-choice',type=Path);a=p.parse_args()
 dest=a.output or Path(f'outputs/runs/bass-evidence/phase{a.phase}');ledger=a.ledger or ROOT/f'phase{a.phase}-ledger.json'
 if dest.exists():raise FileExistsError('Preserve existing results')
 if ledger.exists():raise FileExistsError('Preserve existing ledger')
 f,y,feature,anchors,neural,sources,arrays=acoustic();dest.mkdir(parents=True)
 lock=json.loads(Path('config/bass-models.lock.json').read_text());assert sha(lock['bass']['path'])==lock['bass']['sha256']
 if a.phase==1:
  data=json.loads(Path('outputs/runs/bass-models/phase2/S2-short-0.json').read_text());notes=[NoteEvent(**n) for n in data['notes']];rows=[];previous='baseline'
 else:
  previous_row=json.loads((a.previous_choice or ROOT/f'phase{a.phase-1}-choice.json').read_text())['row'];assert sha(previous_row['provenance_path'])==previous_row['provenance_sha256'] and sha(previous_row['path'])==previous_row['sha256']
  notes=[NoteEvent(**n) for n in json.loads(Path(previous_row['provenance_path']).read_text())['notes']];rows=[previous_row];previous=previous_row['id']
 np.savez(dest/'audio-evidence.npz',**arrays);sources[str(dest/'audio-evidence.npz')]=sha(dest/'audio-evidence.npz')
 def save(id,new,log):
  path=dest/(id+'.mid');write_midi(new,path);detail=dest/(id+'.json')
  if id=='baseline':assert path.read_bytes()==Path(lock['bass']['path']).read_bytes()
  detail.write_text(json.dumps({'id':id,'parent':previous,'sources':sources,'notes':[asdict(n) for n in new],'edits_and_proposals':log},ensure_ascii=False,indent=2)+'\n')
  rows.append({'id':id,'recipe':{'parent':previous,'profile':id},'path':str(path),'sha256':sha(path),'predicted':len(new),'provenance_path':str(detail),'provenance_sha256':sha(detail)})
 if a.phase==1:
  save('baseline',notes,[])
  for profile in json.loads((ROOT/'实验登记.json').read_text())['stage1']['profiles']:
   new,log=merge_retriggers(notes,feature,profile['rise'],profile['flux']);save(profile['id'],new,log)
 elif a.phase==2:
  for id in ['A1','A2','A3']:
   new,log=add_notes(notes,id,f,feature,anchors,neural);save(id,new,log)
 else:
  for id in ['O1','O2','R1','O1+R1','O2+R1']:
   new,log=correct(notes,id,y,feature,anchors,neural);save(id,new,log)
 ledger.write_text(json.dumps({'phase':a.phase,'registration_sha256':sha(ROOT/'实验登记.json'),'generator_sha256':sha(__file__),'implementation_sha256':sha('src/audio_midi/bass_evidence.py'),'rows':rows},ensure_ascii=False,indent=2)+'\n');print([(r['id'],r['predicted']) for r in rows])
if __name__=='__main__':main()
