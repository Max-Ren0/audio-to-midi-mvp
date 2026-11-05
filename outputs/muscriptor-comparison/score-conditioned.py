import json, hashlib
from pathlib import Path
import mido
from audio_midi.quality import read_notes, metrics
base=Path('outputs/runs/muscriptor-comparison')
lines=(base/'conditioned.log').read_text().splitlines()
notes=[]
for line in lines:
 if line.startswith('NOTE,'):
  _,a,b,p,pr,dr=line.split(','); notes.append((float(a),float(b),int(p),int(pr),int(dr)))
notes=[(a,min(b,60.0304375),p,pr,dr) for a,b,p,pr,dr in notes if 0 <= a < 60.0304375 and min(b,60.0304375)>a]
if not notes: raise RuntimeError('no model notes')
m=mido.MidiFile(type=1,ticks_per_beat=480)
con=mido.MidiTrack(); m.tracks.append(con); con.append(mido.MetaMessage('set_tempo',tempo=500000))
for channel,(pr,dr) in enumerate(sorted({(n[3],n[4]) for n in notes})):
 if channel>=15: raise RuntimeError('too many distinct instruments for simple MIDI export')
 ch=9 if dr else channel if channel<9 else channel+1
 if ch==9 and not dr: raise RuntimeError('invalid channel')
 tr=mido.MidiTrack();m.tracks.append(tr)
 if not dr:tr.append(mido.Message('program_change',channel=ch,program=pr,time=0))
 ev=[]
 for a,b,p,p2,d2 in notes:
  if (p2,d2)==(pr,dr): ev.extend([(round(a*960),1,p),(round(b*960),0,p)])
 prev=0
 for t,on,p in sorted(ev):
  tr.append(mido.Message('note_on' if on else 'note_off',channel=ch,note=p,velocity=80 if on else 0,time=t-prev));prev=t
m.save(base/'muscriptor-medium-conditioned.mid')
refs=Path('/Users/ringscherry/Desktop/Codex项目/吉他产品/v0.0/test/tracks')
reference=[]
for p in sorted(refs.glob('*.mid')): reference.extend(read_notes(p))
paths={'noto':Path('outputs/runs/bass-sequence/交付/六轨-仅替换贝斯.mid'),'muscriptor':base/'muscriptor-medium-conditioned.mid'}
out={k:metrics(reference,read_notes(p),.9995,.14,60.0304375) for k,p in paths.items()}
(base/'strict-conditioned.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2))
