from pathlib import Path
from dataclasses import replace
import json
from audio_midi.quality import read_notes,INSTRUMENTS
from audio_midi.strings_bounded import evaluate_notes
base=Path('outputs/runs/muscriptor-comparison');r=[]
for p in Path('/Users/ringscherry/Desktop/Codex项目/吉他产品/v0.0/test/tracks').glob('*.mid'):r+=read_notes(p)
r=[n for n in r if .14<=n.onset<.14+.9995*60.0304375]
paths={'noto':Path('outputs/runs/bass-sequence/交付/六轨-仅替换贝斯.mid'),'auto':base/'muscriptor-medium.mid','conditioned':base/'muscriptor-medium-conditioned.mid'}
out={}
for label,path in paths.items():
 pred=[replace(n,onset=.9995*n.onset+.14,offset=.9995*n.offset+.14) for n in read_notes(path) if n.onset<60.0304375]
 out[label]={}
 for cat in INSTRUMENTS:
  ref=[n for n in r if n.category==cat];p=[n for n in pred if n.category==cat]
  q=evaluate_notes(ref,p)
  out[label][cat]={k:q[k] for k in ('reference','predicted','near_onset_coverage','sustained_presence_coverage')}
  out[label][cat]['duration_f1']=q['offset']['f1'] if cat!='drums' else None
(base/'loose.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
