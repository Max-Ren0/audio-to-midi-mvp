"""Whole-component shortlist combinations; no reference MIDI read."""
import json,hashlib,itertools
from pathlib import Path
from audio_midi.quality import read_notes
from audio_midi.events import NoteEvent
from audio_midi.drums import route_drum_keys
from audio_midi.midi import write_midi

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
basepath=Path('outputs/runs/drums-v2/candidates/adtof-s0.3-h0.165__oaf-gated-ride.mid');base=read_notes(basepath)
shortlist=json.loads(Path('work/drums-v2/component-shortlist.json').read_text());root=Path('outputs/runs/drums-v2/stage3');root.mkdir(exist_ok=False);rows=[]
for i,selection in enumerate(itertools.product(*shortlist.values())):
 sources={'base':base};routes={}
 for row in selection:
  p=Path(row['component_path']);assert sha(p)==row['component_sha256']
  sources[row['id']]=[NoteEvent(**n) for n in json.loads(p.read_text())['notes']];routes[row['key']]=row['id']
 ns=route_drum_keys(sources,'base',routes,60.0304375);p=root/f'combo-{i+1}.mid';write_midi(ns,p)
 rows.append({'id':f'combo-{i+1}','path':str(p),'sha256':sha(p),'components':selection})
Path('outputs/drums-v2/阶段三来源.json').write_text(json.dumps({'baseline':str(basepath),'baseline_sha256':sha(basepath),'selection_policy':'development whole-component shortlist, no reference notes read in generation','candidates':rows},indent=2))
