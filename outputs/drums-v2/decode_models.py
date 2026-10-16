"""Predeclared decoding grid; only model outputs, never a reference MIDI."""
from pathlib import Path
import json,hashlib,numpy as np
from adtof_pytorch.post_processing import PeakPicker

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path('work/drums-v2/decoded');root.mkdir(exist_ok=False)
path=Path('work/drums/sw-full60.npz');act=np.load(path)['activations']
for snare in [.18,.24,.30]:
 for hat in [.11,.165,.22,.275]:
  thresholds=[.165,snare,.24,hat,.225];peaks=PeakPicker(thresholds=thresholds,fps=100).pick(act,labels=[35,38,47,42,49])[0]
  notes=[{'category':'drums','pitch':int(p),'onset':float(t),'offset':float(t+.1),'velocity':100,'program':0} for p,ts in peaks.items() for t in ts]
  name=f'adtof-s{snare}-h{hat}';(root/f'{name}.json').write_text(json.dumps({'notes':notes,'thresholds':thresholds,'input_activation_sha256':sha(path),'reference_used':False},indent=2))
for source in ['sw','demucs']:
 p=Path(f'work/drums-v2/oaf-{source}-full60.npz');d=np.load(p);on=d['onset_probs'][0];vel=d['velocity'][0]
 for threshold in [.35,.5,.65]:
  notes=[]
  for column,pitch in enumerate([36,38,48,42,51,53,49,75]):
   active=on[:,column]>threshold
   bounds=np.diff(np.r_[False,active,False].astype(int));starts=np.flatnonzero(bounds==1);ends=np.flatnonzero(bounds==-1)
   for start,end in zip(starts,ends):
    t=int(start+np.argmax(on[start:end,column]));velocity=max(1,min(127,int(np.clip(vel[t,column],0,1)*127)))
    notes.append({'category':'drums','pitch':pitch,'onset':t/100.,'offset':t/100.+.1,'velocity':velocity,'program':0})
  (root/f'oaf-{source}-t{threshold}.json').write_text(json.dumps({'notes':notes,'onset_threshold':threshold,'decode':'contiguous above-threshold run, retain peak frame as reference converter app','input_activation_sha256':sha(p),'reference_used':False},indent=2))
print('decoded',len(list(root.glob('*.json'))),'sets; zero model inference')
