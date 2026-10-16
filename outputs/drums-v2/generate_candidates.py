"""Reference-free whole-key candidate generation from cached predictions only."""
from pathlib import Path
from dataclasses import asdict
import json,hashlib
from audio_midi.events import NoteEvent
from audio_midi.quality import read_notes
from audio_midi.stitching import clean_notes
from audio_midi.drums import route_drum_keys,consensus_drums
from audio_midi.midi import write_midi

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(path):
 path=Path(path)
 if path.suffix=='.mid':return [n for n in read_notes(path) if n.category=='drums']
 return clean_notes([NoteEvent(**{k:n[k] for k in ['category','pitch','onset','offset','velocity','program']}) for n in json.loads(path.read_text())['notes'] if n['category']=='drums'],60.0304375)
root=Path('outputs/runs/drums-v2/candidates');root.mkdir(parents=True,exist_ok=False)
paths={'demucs':'outputs/runs/v01/development/单轨/drums.mid','sw':'outputs/runs/two-methods/sw-local-control/单轨/drums.mid','mix':'work/v01/mix.json','oafsw':'work/drums-v2/decoded/oaf-sw-t0.5.json','oafdemucs':'work/drums-v2/decoded/oaf-demucs-t0.5.json','prev':'outputs/runs/drums/development/H2-Demucs-YourMT3-SW-ADTOF-lower075/鼓.mid'}
sources={k:load(p) for k,p in paths.items()};sources_meta={k:{'path':p,'sha256':sha(p)} for k,p in paths.items()}
support_path=Path('work/drums-v2/decoded/adtof-s0.18-h0.165.json');support=load(support_path)
sources['gatedmix']=consensus_drums([n for n in sources['mix'] if n.pitch in {49,51,53,55}],[n for n in support if n.pitch==49],.05,families=({49,51,53,55,57,59},))
gate=Path('work/drums-v2/gated-mix-cymbals.json');gate.write_text(json.dumps({'notes':[asdict(n) for n in sources['gatedmix']],'anchor_sha256':sha(paths['mix']),'support_sha256':sha(support_path),'support_path':str(support_path),'rule':'anchor original cymbal key supported once within50ms by ADTOF coarse cymbal49; no pitch/time changes, no reference'},indent=2));sources_meta['gatedmix']={'path':str(gate),'sha256':sha(gate)}
policies={'same':{},'mix-ride':{51:'mix'},'mix-cymbals':{49:'mix',51:'mix',53:'mix',55:'mix'},'oaf-sw-mix-ride':{36:'oafsw',48:'oafsw',51:'mix'},'oaf-demu-mix-ride':{36:'oafdemucs',48:'oafdemucs',51:'mix'},'gated-ride':{51:'gatedmix'},'oaf-gated-ride':{36:'oafsw',48:'oafsw',51:'gatedmix'},'oaf-gated-cymbals':{36:'oafsw',48:'oafsw',49:'gatedmix',51:'gatedmix',53:'gatedmix',55:'gatedmix'},'mix-all-fine':{p:'mix' for p in range(35,82) if p not in {38,42}}}
rows=[]
def save(name,notes,meta):
 mid=root/f'{name}.mid';write_midi(notes,mid);rows.append({'id':name,'path':str(mid),'sha256':sha(mid),'notes':len(notes),**meta})
for base in ['demucs','sw','mix','prev','oafsw','oafdemucs']:save('control-'+base,sources[base],{'type':'control','source':base})
for path in sorted(Path('work/drums-v2/decoded').glob('adtof*.json')):
 name=path.stem;sources[name]=load(path);sources_meta[name]={'path':str(path),'sha256':sha(path)}
 for policy,fine in policies.items():
  routes={38:name,42:name,**fine};notes=route_drum_keys(sources,'demucs',routes,60.0304375)
  save(name+'__'+policy,notes,{'type':'whole_key_routes','default':'demucs','routes':routes,'fine_policy':policy})
Path('outputs/drums-v2/候选来源.json').write_text(json.dumps({'input_sha256':'6da0f0ec87ee0b37d83d1c8fc2aa8f89dec1cb38b5c1926484317ac91c5bab98','duration':60.0304375,'reference_used':False,'sources':sources_meta,'candidates':rows,'generator_sha256':sha(__file__)},ensure_ascii=False,indent=2));print('generated',len(rows),'reference-free candidates')
