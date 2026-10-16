from pathlib import Path
import json,hashlib
from audio_midi.events import NoteEvent
from audio_midi.quality import read_notes
from audio_midi.drums import route_drum_keys
from audio_midi.midi import write_midi

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
d=json.loads(Path('outputs/drums-v2/阶段四评分.json').read_text());best=[next(r for r in d['candidates'] if r['key']==k) for k in [36,48,55]]
basep=Path('outputs/runs/drums-v2/stage3/combo-1.mid');sources={'base':read_notes(basep)};routes={}
for r in best:
 p=Path(r['component_path']);assert sha(p)==r['component_sha256'];sources[r['id']]=[NoteEvent(**n) for n in json.loads(p.read_text())['notes']];routes[r['key']]=r['id']
p=Path('outputs/runs/drums-v2/selected-combined.mid');write_midi(route_drum_keys(sources,'base',routes,60.0304375),p)
Path('outputs/drums-v2/最终来源.json').write_text(json.dumps({'baseline':str(basep),'baseline_sha256':sha(basep),'components':best,'candidates':[{'id':'selected-combined','path':str(p),'sha256':sha(p)}],'selection':'whole-components selected on seen development; final generation no reference notes'},indent=2))
print([(r['key'],r['id'],r['score']['f1']) for r in best])
