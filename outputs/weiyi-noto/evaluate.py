from pathlib import Path
import hashlib,json
from audio_midi.quality import read_notes,metrics
r=Path('outputs/runs/weiyi-eval/inputs/reference.mid');p=Path('outputs/runs/weiyi-noto/唯一-Noto-六轨.mid');n=read_notes(p);d=metrics(read_notes(r),n,1,2.15,254.9430024166713);d['midi_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();d['reference_sha256']=hashlib.sha256(r.read_bytes()).hexdigest();d['boundary_notes']=[{'category':x.category,'pitch':x.pitch,'onset':x.onset,'offset':x.offset} for x in n if x.onset<131<x.offset or abs(x.onset-131)<.1 or abs(x.offset-131)<.1];out=Path('outputs/runs/weiyi-noto/评估.json');out.write_text(json.dumps(d,ensure_ascii=False,indent=2));print(json.dumps(d['overall'],ensure_ascii=False))
