from pathlib import Path
import json,hashlib,numpy as np
from scipy.signal import find_peaks
from audio_midi.events import NoteEvent
from audio_midi.evaluate import evaluate
from audio_midi.stitching import clean_notes

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=[]
for identity,truth in [('control0','control-kit0'),('control8','control-kit8'),('level','control-hats-level')]:
 gtpath=Path('work/open-hat/'+truth+'.truth.json');gt=json.loads(gtpath.read_text());duration=gt['duration'];ref=[NoteEvent('drums',n['pitch'],n['onset'],n['onset']+.1,n['velocity'],0) for n in gt['notes'] if n['pitch'] in [42,46]]
 for model in ['mt3','idm','yodo-rgb']:
  path=Path('work/open-hat/'+identity+'-'+model+('.npz' if model=='idm' else '.json'))
  if not path.exists():continue
  for threshold in ([.1,.2,.3,.5] if model=='idm' else ([1.,.75,.5] if model=='yodo-rgb' else [None])):
   if model=='idm':
    d=np.load(path);on=d['onset_probs'];notes=[]
    for c,key in [(2,42),(3,46)]:
     peaks,_=find_peaks(on[c],height=threshold,distance=round(.05*44100/256));notes.extend(NoteEvent('drums',key,float(t*256/44100),float(t*256/44100+.1),80,0) for t in peaks)
   else:
    d=json.loads(path.read_text());ns=d['notes']
    if model=='yodo-rgb':
     assert all(np.isfinite(r['objectness_max']) for r in d['raw_stats'])
     ns=[n for n in ns if n['confidence']>=d['author_thresholds'][n['class']]*threshold]
    notes=[NoteEvent(**{k:n[k] for k in ['category','pitch','onset','offset','velocity','program']}) for n in ns if n['category']=='drums' and n['pitch'] in [42,46]]
   notes=clean_notes(notes,duration);score={str(key):evaluate([n for n in ref if n.pitch==key],[n for n in notes if n.pitch==key])['drums'] for key in [42,46]}
   rows.append({'control':identity,'model':model,'threshold_or_multiplier':threshold,'truth_sha256':sha(gtpath),'input_sha256':gt['audio_sha256'],'output_path':str(path),'output_sha256':sha(path),'score':score})
Path('outputs/open-hat/修复后小样评分.json').write_text(json.dumps({'scope':'known synthetic2kits controls plus sharedgain hats-only control, samekey50ms synthesis timing, no fitted shift; no song GT in model generation','rows':rows},indent=2))
for r in rows:
 if r['model']!='idm' or r['threshold_or_multiplier']==.3:print(r['control'],r['model'],r['threshold_or_multiplier'],[(k,v['tp'],v['fp'],v['fn']) for k,v in r['score'].items()])
