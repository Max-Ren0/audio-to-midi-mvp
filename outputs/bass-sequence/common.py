"""Verified source adapters and acoustic evidence; never imports reference readers."""
from pathlib import Path
from dataclasses import asdict,replace
import importlib.util,json,hashlib
import numpy as np,librosa,soundfile as sf
from audio_midi.events import NoteEvent
from audio_midi.bass_models import nearest_grid,frequency_to_midi
from audio_midi.bass_refinement import extend_confidence,bounded_backtrack,attack_led_notes
from audio_midi.bass_evidence import merge_retriggers,support_runs,insert_supported
from audio_midi.bass_sequence import cluster_onsets,summarize_support,decode_sequence
from audio_midi.stitching import clean_notes
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ROOT=Path('outputs/bass-sequence');RUN=Path('outputs/runs/bass-sequence')
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
old=module('frozen_evidence','outputs/bass-evidence/generate.py');prior=old.prior

def source_features(source):
 f=prior.features(source,'pyin');y,sr=sf.read(f['wave'],always_2d=True,dtype='float32');y=librosa.resample(y.mean(axis=1),orig_sr=sr,target_sr=8000)
 rms=librosa.feature.rms(y=y,frame_length=256,hop_length=32)[0];flux=f['short_envelope']
 normalizer=max(1e-9,float(np.median([flux[max(0,int(t/.004)):min(len(flux),int(t/.004)+17)].max() for t in f['short_onsets']])))
 rise=np.maximum(0,np.diff(np.log(np.maximum(rms,1e-6)),prepend=np.log(max(rms[0],1e-6))))
 anchors=librosa.onset.onset_detect(onset_envelope=rise,sr=8000,hop_length=32,units='time');anchors=np.unique(np.r_[anchors,bounded_backtrack(f['short_onsets'],flux,.004,.032)])
 def feature(t):
  times=np.arange(len(rms))*.004;pre=rms[(times>=t-.064)&(times<t-.016)];post=rms[(times>=t+.016)&(times<t+.064)]
  amp=float(np.median(post)/max(float(np.median(pre)) if len(pre) else 0,1e-6)) if len(post) else 0.
  a=max(0,int(round(t/.004)));b=min(len(flux),a+17)
  return {'rise':amp,'flux':float(flux[a:b].max()/normalizer) if b>a else 0.,'rms_rise_salience':float(rise[max(0,a-2):min(len(rise),a+3)].max()) if a<len(rise) else 0.}
 neural={};sources={f['wave']:f['wave_sha256'],f['pitchfile']:f['pitch_sha256']}
 for m in ['crepe','penn']:
  path=Path(f'work/bass-models/{m}-full.npz') if source=='demucs' else Path(f'work/bass-sequence/{m}-{source}.npz')
  receipt=json.loads(path.with_suffix('.json').read_text());assert receipt['source_audio_sha256']==f['wave_sha256'] and receipt['output_sha256']==sha(path)
  assert receipt['wrapper_sha256']==sha('outputs/bass-models/run_pitch.py') and receipt['weight_sha256']==sha(receipt['weight_path'])
  with np.load(path) as z:hz,q,index=nearest_grid(z['f0'],z['periodicity'],.01,.016,len(f['raw']));assert np.array_equal(z['times'],np.arange(len(z['times']))*.01)
  neural[m]=(frequency_to_midi(hz),q);sources[str(path)]=sha(path);sources[str(path.with_suffix('.json'))]=sha(path.with_suffix('.json'))
 streams={'pyin':(f['raw'],f['probability'],np.isfinite(f['raw'])&f['voiced']&(f['probability']>=.05)&(f['rms']>=f['energy']))}
 for m,limit in [('crepe',.21),('penn',.2)]:
  raw,q=neural[m];streams[m]=(raw,q,np.isfinite(raw)&(q>=limit)&(f['rms']>=f['energy']))
 return {'f':f,'wave':y,'feature':feature,'anchors':anchors,'neural':neural,'streams':streams,'sources':sources,'arrays':{'rms':rms,'flux':flux,'rise':rise,'anchors':anchors,'normalizer':normalizer}}

def full_recipe(data):
 f=data['f'];p,c=extend_confidence(f['raw'],f['voiced'],f['probability'],f['rms'],.016,.2,.05,.128,f['energy'])
 attacks=bounded_backtrack(f['short_onsets'],f['short_envelope'],.004,.032)
 notes,e=attack_led_notes(p,f['probability'],attacks,.016,f['duration'],vote_guard=0);notes=clean_notes(notes,f['duration'])
 notes,m=merge_retriggers(notes,data['feature'],1.2,.8)
 notes,a=old.add_notes(notes,'A3',f,data['feature'],data['anchors'],data['neural'])
 notes,r=old.correct(notes,'R1',data['wave'],data['feature'],data['anchors'],data['neural'])
 return notes,{'confidence':c,'attacks':attacks.tolist(),'initial_events':e,'merge':m,'add':a,'retime':r}

def evidence(note,all_sources):
 supports=[];attacks={};dur=max(.016,min(.32,note.offset-note.onset))
 for source,data in all_sources.items():
  masks={}
  for m,(pitch,q,valid) in data['streams'].items():
   a=max(0,int(np.ceil(note.onset/.016)));b=min(len(pitch),int(np.ceil((note.onset+dur)/.016)))
   masks[m]=valid[a:b]&(np.rint(pitch[a:b])==note.pitch)
  supports.append(masks);attacks[source]=data['feature'](note.onset)
 s=summarize_support(supports,.016)
 attack=np.mean([min(2,max(x['rise']-1,x['flux'],0)) for x in attacks.values()])
 score=float(np.mean(s['fractions'])+.2*np.mean(s['neural_agreement'])+.05*attack)
 return s|{'score':score,'attack':attacks,'credible_attack':any(x['rise']>=1.1 or x['flux']>=.5 for x in attacks.values())}

def candidate(n,source,all_sources,baseline=False):
 return asdict(n)|{'source':source,'baseline':baseline,**evidence(n,all_sources)}

def normalize(rows,minimum=.08,duration=60.03045351473923):
 chosen=[]
 for r in sorted(rows,key=lambda r:(r['onset'],-r['score'],r['pitch'])):
  if chosen and r['onset']-chosen[-1]['onset']<minimum-1e-9:
   if r['score']>chosen[-1]['score']:chosen[-1]=r
   continue
  chosen.append(r)
 out=[]
 for i,r in enumerate(chosen):
  end=min(r['offset'],duration,chosen[i+1]['onset'] if i+1<len(chosen) else duration)
  if end-r['onset']>=minimum-1e-9:out.append(NoteEvent('bass',r['pitch'],r['onset'],end,None,33))
 return out

def pitch_proposals(data,source,all_sources,minimum=.08,neural_only=False):
 proposed=[]
 if neural_only:
  c,cq,cv=data['streams']['crepe'];p,pq,pv=data['streams']['penn'];streams=[(c,cv&pv&(np.rint(c)==np.rint(p)))]
 else:streams=[(p,v) for p,q,v in data['streams'].values()]
 for raw,valid in streams:
  for run in support_runs(raw,valid,.016,minimum):
   options=[float(t) for t in data['anchors'] if run['start']-.256<=t<=run['start']+.032 and (data['feature'](t)['rise']>=1.1 or data['feature'](t)['flux']>=.5)]
   if not options:continue
   t=min(options,key=lambda t:(abs(t-run['start']),t));end=min(run['end'],data['f']['duration'])
   if end-t<minimum-1e-9:continue
   n=NoteEvent('bass',run['pitch'],t,end,None,33);proposed.append(candidate(n,source,all_sources))
 return proposed

def load_row(row):
 assert sha(row['path'])==row['sha256'] and sha(row['provenance_path'])==row['provenance_sha256']
 return [NoteEvent(**n) for n in json.loads(Path(row['provenance_path']).read_text())['notes']]
