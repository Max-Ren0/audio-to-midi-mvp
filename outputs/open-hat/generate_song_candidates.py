"""Generate whole-model open/closed-hat variants without reading reference MIDI."""
from pathlib import Path
from dataclasses import asdict
import json,hashlib,numpy as np
from scipy.signal import find_peaks
from audio_midi.events import NoteEvent
from audio_midi.quality import read_notes
from audio_midi.stitching import clean_notes
from audio_midi.drums import consensus_drums,route_drum_keys
from audio_midi.midi import write_midi

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def raw_notes(d):return [NoteEvent(**{k:n[k] for k in ['category','pitch','onset','offset','velocity','program']}) for n in d['notes'] if n['category']=='drums' and n['pitch'] in [42,46]]
duration=60.0304375;basepath=Path('outputs/runs/drums-v2/交付/鼓-v0.1-强化版.mid');base=read_notes(basepath)
assert sha(basepath)=='3c13d77e0fa3d8d04cee1089829322939c9f7711246d4fafa0bdb992106aa50d'
root=Path('outputs/runs/open-hat/candidates');root.mkdir(parents=True,exist_ok=False);sources={};provenance={}
p=Path('work/open-hat/fullhh-mt3.json');sources['YourMT3']=clean_notes(raw_notes(json.loads(p.read_text())),duration);provenance['YourMT3']={'raw':str(p),'sha256':sha(p)}
p=Path('work/open-hat/fullhh-idm.npz');d=np.load(p);assert np.isfinite(d['onset_probs']).all()
for threshold in [.1,.2,.3,.5]:
 notes=[]
 for col,key in [(2,42),(3,46)]:
  peaks,_=find_peaks(d['onset_probs'][col],height=threshold,distance=round(.05*44100/256))
  notes.extend(NoteEvent('drums',key,float(t*256/44100),float(t*256/44100+.1),int(np.clip(d['velocity'][col,t]*127,1,127)),0) for t in peaks)
 name=f'IDM-t{threshold}';sources[name]=clean_notes(notes,duration);provenance[name]={'raw':str(p),'sha256':sha(p),'threshold':threshold,'peak_distance':.05}
p=Path('work/open-hat/fullhh-yodo.json');d=json.loads(p.read_text());assert all(np.isfinite(s['objectness_max']) for s in d['raw_stats'])
for multiplier in [1.,.75,.5]:
 filtered=dict(d,notes=[n for n in d['notes'] if n['confidence']>=d['author_thresholds'][n['class']]*multiplier]);name=f'YODO-x{multiplier}'
 sources[name]=clean_notes(raw_notes(filtered),duration);provenance[name]={'raw':str(p),'sha256':sha(p),'multiplier':multiplier,'thresholds':d['author_thresholds']}
for y in [.75,.5]:
 for i in [.2,.3]:
  for tolerance in [.03,.05]:
   name=f'consensus-y{y}-i{i}-tol{tolerance}'
   anchor=[n for n in sources[f'YODO-x{y}'] if n.pitch==46];support=[n for n in sources[f'IDM-t{i}'] if n.pitch==46]
   sources[name]=consensus_drums(anchor,support,tolerance);provenance[name]={'method':'YODO original open46 anchors supported once byIDM46, originalkey/time retained','anchor':f'YODO-x{y}','support':f'IDM-t{i}','tolerance':tolerance}
rows=[]
def save(name,model,policy,notes):
 p=root/(name+'.mid')
 if notes:write_midi(notes,p)
 else:
  import mido
  empty=mido.MidiFile(type=1);empty.tracks.append(mido.MidiTrack([mido.MetaMessage('end_of_track')]));empty.save(p)
 rows.append({'id':name,'model':model,'policy':policy,'path':str(p),'sha256':sha(p)})
save('baseline85','baseline','unchanged',base)
for name,notes in sources.items():
 policies=['replace-open','suppress30ms','suppress50ms'] if name.startswith('consensus') else ['hats-only','replace-hats','replace-open','suppress30ms','suppress50ms']
 for policy in policies:
  opens=[n for n in notes if n.pitch==46]
  if policy=='hats-only':result=notes
  elif policy=='replace-hats':result=route_drum_keys({'base':base,'new':notes},'base',{42:'new',46:'new'},duration)
  elif policy=='replace-open':result=route_drum_keys({'base':base,'new':notes},'base',{46:'new'},duration)
  else:
   tolerance=.03 if policy=='suppress30ms' else .05
   kept=[n for n in base if n.pitch!=46 and not(n.pitch==42 and any(abs(n.onset-m.onset)<=tolerance+1e-9 for m in opens))]
   result=clean_notes([*kept,*opens],duration)
  save(name+'__'+policy,name,policy,result)
sourcefile=Path('work/open-hat/decoded-hat-sources.json');sourcefile.write_text(json.dumps({'sources':{k:[asdict(n) for n in ns] for k,ns in sources.items()},'provenance':provenance,'reference_used':False},indent=2))
Path('outputs/open-hat/候选来源.json').write_text(json.dumps({'baseline':str(basepath),'baseline_sha256':sha(basepath),'decoded_sources':str(sourcefile),'decoded_sources_sha256':sha(sourcefile),'raw_provenance':provenance,'reference_in_generation':False,'candidates':rows},indent=2));print('generated',len(rows),'whole-rule candidates')
