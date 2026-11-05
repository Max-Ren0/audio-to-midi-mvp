from pathlib import Path
from dataclasses import replace
import hashlib,json,mido
from audio_midi.quality import read_notes,metrics,INSTRUMENTS
from audio_midi.strings_bounded import evaluate_notes
base=Path('outputs/runs/weiyi-eval'); rp=base/'inputs/reference.mid';pp=base/'inputs/test.mid'
r=read_notes(rp);p=read_notes(pp); shift=2.15;scale=1.;duration=mido.MidiFile(rp).length-shift
scores={str(s):metrics(r,p,scale,s,duration) for s in (0.,shift)}
ref=[n for n in r if shift<=n.onset<shift+duration];pred=[replace(n,onset=n.onset+shift,offset=min(n.offset,duration)+shift) for n in p if n.onset<duration and n.offset and min(n.offset,duration)>n.onset]
loose={}
for cat in INSTRUMENTS:
 q=evaluate_notes([n for n in ref if n.category==cat],[n for n in pred if n.category==cat]);loose[cat]={k:q[k] for k in ('reference','predicted','near_onset_coverage','sustained_presence_coverage')};loose[cat]['offset_f1']=q['offset']['f1'] if cat!='drums' else None
out={'sha256':{'reference':hashlib.sha256(rp.read_bytes()).hexdigest(),'test':hashlib.sha256(pp.read_bytes()).hexdigest()},'alignment':{'reference_seconds_equal_test_seconds_plus':shift,'duration':duration,'basis':'early piano note-on same pitch differences in first 40 seconds; rounded 50ms; chosen using same song','caveat':'fixed shift and identical tempo assumption; no timing drift correction'},'scores':scores,'loose':loose}
(base/'results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
