from pathlib import Path
from dataclasses import asdict,replace
import json,hashlib,importlib.util
from audio_midi.events import NoteEvent
from audio_midi.midi import write_midi
from audio_midi.quality import load_reference_tracks
from audio_midi.strings_bounded import evaluate_notes
ROOT=Path('outputs/strings-bounded');RUN=Path('outputs/runs/strings-bounded');DURATION=60.0304375
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def protect():
 x=json.loads(Path('config/bass-frozen.lock.json').read_text())
 for r in [x['bass'],x['six_track'],*x['implementation']]:assert sha(r['path'])==r['sha256'],r['path']
 assert sha(x['lock_path'])==x['lock_sha256']
 return x

def read_detail(row):
 assert sha(row['path'])==row['sha256'] and sha(row['detail_path'])==row['detail_sha256']
 return json.loads(Path(row['detail_path']).read_text())

def save(id,notes,folder,evidence):
 folder.mkdir(parents=True,exist_ok=True);mid=folder/(id+'.mid');detail=folder/(id+'.json')
 if mid.exists() or detail.exists():raise FileExistsError('Preserve candidates')
 if not notes:raise ValueError('Empty exploratory candidate requires explicit handling')
 write_midi(notes,mid);detail.write_text(json.dumps({'id':id,'notes':[asdict(n) for n in notes],'evidence':evidence},ensure_ascii=False,indent=2)+'\n')
 return {'id':id,'path':str(mid),'sha256':sha(mid),'detail_path':str(detail),'detail_sha256':sha(detail),'predicted':len(notes)}

def reference():
 return [replace(n,onset=(n.onset-.14)/.9995,offset=(n.offset-.14)/.9995) for n in load_reference_tracks(Path('outputs/two-methods/标准清单.json')) if n.category=='strings' and .14<=n.onset<.14+.9995*DURATION]

def score(row):
 data=read_detail(row);ns=[NoteEvent(**n) for n in data['notes']]
 # Evaluate MIDI-quantized events, not just pre-export JSON, including full tempo map.
 from audio_midi.quality import read_notes
 ns=read_notes(Path(row['path']));refs=reference();s=evaluate_notes(refs,ns)
 spec=importlib.util.spec_from_file_location('duration_metrics','outputs/strings-diagnostics/metrics.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 r=[(n.onset,n.offset,n.pitch) for n in refs];p=[(n.onset,n.offset,n.pitch) for n in ns]
 return row|{'score':s,'duration_pitch':m.duration_overlap(r,p,DURATION),'duration_chroma':m.duration_overlap(r,p,DURATION,chroma=True)}
