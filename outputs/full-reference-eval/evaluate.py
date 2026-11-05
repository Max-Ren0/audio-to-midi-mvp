import hashlib,json
from pathlib import Path
from dataclasses import replace
from audio_midi.quality import read_notes,metrics,INSTRUMENTS
from audio_midi.strings_bounded import evaluate_notes
root=Path('/Users/ringscherry/Desktop/Codex项目/吉他产品/v0.0/test')
reference=root/'不将就 - 李荣浩（改编）.mid';test=root/'1.mid'
r=read_notes(reference);p=read_notes(test);duration=60.0304375;scale=.9995;shift=.14
strict=metrics(r,p,scale,shift,duration);ref=[n for n in r if shift<=n.onset<shift+scale*duration]
pred=[replace(n,onset=scale*n.onset+shift,offset=scale*min(n.offset,duration)+shift) for n in p if 0<=n.onset<duration and min(n.offset,duration)>n.onset]
loose={}
for cat in INSTRUMENTS:
 q=evaluate_notes([n for n in ref if n.category==cat],[n for n in pred if n.category==cat]);loose[cat]={k:q[k] for k in ('reference','predicted','near_onset_coverage','sustained_presence_coverage')};loose[cat]['duration_f1']=None if cat=='drums' else q['offset']['f1']
data={'reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),'test_sha256':hashlib.sha256(test.read_bytes()).hexdigest(),'strict':strict,'loose':loose,'identity':metrics(r,p,1.,0.,duration)}
Path('outputs/runs/full-reference-eval/results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2));print(json.dumps(data,ensure_ascii=False,indent=2))
