"""Combine separately transcribed consecutive parts; piano comes from frozen B."""
from pathlib import Path
from dataclasses import replace
from audio_midi.quality import read_notes, INSTRUMENTS
from audio_midi.midi import write_midi
from audio_midi.stitching import clean_notes
import hashlib,json,mido
root=Path('outputs/runs/weiyi-noto'); offset=131.; duration=262.401066
out=root/'唯一-Noto-六轨.mid'
if out.exists(): raise FileExistsError(out)
notes=[];sources=[]
for i in (1,2):
 part=root/f'v01-{i:02d}'/'多乐器.mid';piano=root/f'piano-{i:02d}'/'钢琴-B.mid';strings=root/f'strings-{i:02d}.json'
 start=(i-1)*offset; end=offset if i==1 else duration-offset
 for path,select in ((part,lambda n:n.category not in ('piano','strings')),(piano,lambda n:n.category=='piano')):
  src=read_notes(path);sources.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'notes':len(src)})
  notes.extend(replace(n,onset=n.onset+start,offset=min(n.offset,end)+start) for n in src if select(n) and 0<=n.onset<end and n.offset is not None and min(n.offset,end)>n.onset)
 from audio_midi.events import NoteEvent
 data=json.loads(strings.read_text());sources.append({'path':str(strings),'sha256':hashlib.sha256(strings.read_bytes()).hexdigest(),'notes':len(data['notes'])})
 notes.extend(replace(n,onset=n.onset+start,offset=min(n.offset,end)+start) for n in clean_notes([NoteEvent(**x) for x in data['notes'] if x['category']=='strings'],end) if n.category=='strings' and n.offset is not None and 0<=n.onset<end and min(n.offset,end)>n.onset)
if not notes: raise ValueError('no notes')
write_midi(notes,out)
mf=mido.MidiFile(out);mf.tracks[0].append(mido.MetaMessage('end_of_track',time=round(duration*960)));mf.save(out)
observed=read_notes(out)
counts={c:sum(n.category==c for n in observed) for c in INSTRUMENTS}
(root/'合成记录.json').write_text(json.dumps({'input_parts_start':[0,131.0],'duration':duration,'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'sources':sources,'counts':counts,'warnings':['Piano B; strings SW other→YourMT3; guitar/bass/drums v0.1-free baseline, not frozen research drum or bass','Two independently transcribed segments; possible boundary discontinuity','Encoding defaults tempo 120 and 4/4, not detected']},ensure_ascii=False,indent=2))
print(json.dumps(counts))
