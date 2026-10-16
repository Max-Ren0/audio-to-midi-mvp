"""Final cross-model false-positive controls; all notes from predictions."""
from pathlib import Path
from dataclasses import asdict
import json,hashlib
from audio_midi.events import NoteEvent
from audio_midi.quality import read_notes
from audio_midi.stitching import clean_notes
from audio_midi.drums import consensus_drums,route_drum_keys
from audio_midi.midi import write_midi

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
 p=Path(p)
 if p.suffix=='.mid':return read_notes(p)
 return clean_notes([NoteEvent(**{k:n[k] for k in ['category','pitch','onset','offset','velocity','program']}) for n in json.loads(p.read_text())['notes'] if n['category']=='drums'],60.0304375)
basep=Path('outputs/runs/drums-v2/stage3/combo-1.mid');base=load(basep);root=Path('outputs/runs/drums-v2/stage4');root.mkdir(exist_ok=False);rows=[]
def save(name,key,notes,rule):
 result=route_drum_keys({'base':base,'new':notes},'base',{key:'new'},60.0304375);p=root/(name+'.mid');write_midi(result,p)
 component=Path('work/drums-v2/components')/(name+'.json');component.write_text(json.dumps({'notes':[asdict(n) for n in notes],'rule':rule,'reference_used':False},indent=2))
 rows.append({'id':name,'key':key,'path':str(p),'sha256':sha(p),'component_path':str(component),'component_sha256':sha(component),'rule':rule})
for key in [36,48,55]:
 anchor=[n for n in base if n.pitch==key];save(f'key{key}-baseline',key,anchor,{'baseline':str(basep),'sha256':sha(basep)})
 supports=[('demucs','outputs/runs/v01/development/单轨/drums.mid',None),('sw','outputs/runs/two-methods/sw-local-control/单轨/drums.mid',None)] if key==36 else [('coarse','work/drums-v2/decoded/adtof-s0.18-h0.165.json',{41,43,45,47,48,50} if key==48 else {49,51,53,55,57,59})]
 for label,path,family in supports:
  support=[n for n in load(path) if n.pitch==(key if family is None else (47 if key==48 else 49))]
  for tol in [.03,.05,.08]:
   notes=consensus_drums(anchor,support,tol,families=() if family is None else (family,));save(f'key{key}-{label}-tol{tol}',key,notes,{'anchor':str(basep),'anchor_sha256':sha(basep),'support':path,'support_sha256':sha(path),'tolerance':tol,'family':None if family is None else sorted(family),'method':'one-use greedy support, unchanged anchor'})
Path('outputs/drums-v2/阶段四来源.json').write_text(json.dumps({'baseline':str(basep),'baseline_sha256':sha(basep),'reference_used':False,'candidates':rows},indent=2))
