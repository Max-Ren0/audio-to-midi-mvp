from pathlib import Path
import hashlib,json
from dataclasses import replace
from audio_midi.quality import read_notes,metrics,INSTRUMENTS
from audio_midi.strings_bounded import evaluate_notes
root=Path('/Users/ringscherry/Desktop/Codex项目/吉他产品/v0.0/test');midi=root/'李荣浩 - 不将就-[AudioTrimmer.com]_NNTranscription.mid'; ref=[]
for f in sorted((root/'tracks').glob('*.mid')): ref+=read_notes(f)
pred=read_notes(midi);duration=60.0304375;scale=.9995;shift=.14
s=metrics(ref,pred,scale,shift,duration)
r=[n for n in ref if shift<=n.onset<shift+scale*duration]
p=[replace(n,onset=scale*n.onset+shift,offset=scale*min(n.offset,duration)+shift) for n in pred if 0<=n.onset<duration and min(n.offset,duration)>n.onset]
loose={}
for cat in INSTRUMENTS:
 q=evaluate_notes([n for n in r if n.category==cat],[n for n in p if n.category==cat]);loose[cat]={k:q[k] for k in ('reference','predicted','near_onset_coverage','sustained_presence_coverage')};loose[cat]['duration_f1']=None if cat=='drums' else q['offset']['f1']
result={'input_sha256':hashlib.sha256(midi.read_bytes()).hexdigest(),'references':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((root/'tracks').glob('*.mid'))},'strict':s,'loose':loose,'raw_supported_notes':len(pred),'outside_window':sum(n.onset>=duration for n in pred)}
out=Path('outputs/runs/neuralnote-user-eval/results.json');out.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
