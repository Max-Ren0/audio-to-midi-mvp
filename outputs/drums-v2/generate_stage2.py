"""Reference-free single-factor model-consensus candidates, fixed baseline intact."""
from pathlib import Path
from dataclasses import asdict
import json,hashlib
from audio_midi.events import NoteEvent
from audio_midi.quality import read_notes
from audio_midi.stitching import clean_notes
from audio_midi.drums import consensus_drums,augment_supported_drums,route_drum_keys
from audio_midi.midi import write_midi

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
 p=Path(p)
 if p.suffix=='.mid':return [n for n in read_notes(p) if n.category=='drums']
 return clean_notes([NoteEvent(**{k:n[k] for k in ['category','pitch','onset','offset','velocity','program']}) for n in json.loads(p.read_text())['notes'] if n['category']=='drums'],60.0304375)
base_path=Path('outputs/runs/drums-v2/candidates/adtof-s0.3-h0.165__oaf-gated-ride.mid');base=load(base_path)
root=Path('outputs/runs/drums-v2/stage2');root.mkdir(exist_ok=False)
components=Path('work/drums-v2/components');components.mkdir(exist_ok=False)
rows=[]
def save(group,name,key,notes,rule):
 component=components/(name+'.json');component.write_text(json.dumps({'notes':[asdict(n) for n in notes],'rule':rule,'reference_used':False},indent=2))
 result=route_drum_keys({'base':base,'component':notes},'base',{key:'component'},60.0304375)
 mid=root/(name+'.mid');write_midi(result,mid)
 rows.append({'id':name,'group':group,'key':key,'path':str(mid),'sha256':sha(mid),'component_path':str(component),'component_sha256':sha(component),'rule':rule})
for group,key in [('snare',38),('hat',42),('ride',51)]:save(group,group+'-baseline',key,[n for n in base if n.pitch==key],{'baseline_sha256':sha(base_path)})
anchor_path=Path('work/drums-v2/decoded/adtof-s0.18-h0.165.json');anchor=[n for n in load(anchor_path) if n.pitch==38]
for source in ['sw','demucs']:
 for threshold in [.35,.5]:
  support_path=Path(f'work/drums-v2/decoded/oaf-{source}-t{threshold}.json');support=[n for n in load(support_path) if n.pitch==38]
  for tol in [.05,.08]:
   ns=consensus_drums(anchor,support,tol);name=f'snare-{source}-{threshold}-tol{tol}'
   save('snare',name,38,ns,{'method':'same-key greedy one-use consensus; keep original ADTOF anchor','anchor':str(anchor_path),'anchor_sha256':sha(anchor_path),'support':str(support_path),'support_sha256':sha(support_path),'tolerance':tol})
weak_path=Path('work/drums-v2/decoded/adtof-s0.18-h0.11.json');weak=[n for n in load(weak_path) if n.pitch==42];strong=[n for n in base if n.pitch==42]
for name,path in [('sw','outputs/runs/two-methods/sw-local-control/单轨/drums.mid'),('mix','work/v01/mix.json'),('oaf','work/drums-v2/decoded/oaf-sw-t0.35.json')]:
 support=[n for n in load(path) if n.pitch==42]
 for tol in [.05,.08]:
  ns=augment_supported_drums(strong,weak,support,tol,60.0304375)
  save('hat',f'hat-{name}-tol{tol}',42,ns,{'method':'preserve baseline; add novel weak events only if independent model corroborates; no replacing attacks','baseline':str(base_path),'weak':str(weak_path),'weak_sha256':sha(weak_path),'support':path,'support_sha256':sha(path),'tolerance':tol})
ride_path=Path('work/v01/mix.json');anchor=[n for n in load(ride_path) if n.pitch==51]
for threshold in [.15,.225,.3]:
 support_path=Path(f'work/drums-v2/decoded/cymbal-{threshold}.json');support=load(support_path)
 for tol in [.03,.05,.08]:
  ns=consensus_drums(anchor,support,tol,families=({49,51,53,55,57,59},))
  save('ride',f'ride-cy{threshold}-tol{tol}',51,ns,{'method':'original ride key/time supported by coarse cymbal49; no relabel','anchor':str(ride_path),'anchor_sha256':sha(ride_path),'support':str(support_path),'support_sha256':sha(support_path),'tolerance':tol})
Path('outputs/drums-v2/阶段二来源.json').write_text(json.dumps({'baseline_path':str(base_path),'baseline_sha256':sha(base_path),'reference_used':False,'candidates':rows},indent=2));print(len(rows),'single-factor candidates')
