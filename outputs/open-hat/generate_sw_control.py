"""Corrected YODO on original SW drums, same unchanged GM thresholds/policies."""
from pathlib import Path
import json,hashlib
from audio_midi.events import NoteEvent
from audio_midi.quality import read_notes
from audio_midi.stitching import clean_notes
from audio_midi.drums import route_drum_keys
from audio_midi.midi import write_midi
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=Path('work/open-hat/fullSW-yodo.json');d=json.loads(p.read_text());basep=Path('outputs/runs/drums-v2/交付/鼓-v0.1-强化版.mid');base=read_notes(basep);root=Path('outputs/runs/open-hat/sw-control');root.mkdir(exist_ok=False);rows=[]
for multiplier in [1.,.75,.5]:
 raw=[n for n in d['notes'] if n['pitch'] in [42,46] and n['confidence']>=d['author_thresholds'][n['class']]*multiplier]
 notes=clean_notes([NoteEvent(**{k:n[k] for k in ['category','pitch','onset','offset','velocity','program']}) for n in raw],60.0304375)
 for policy in ['hats-only','replace-hats','replace-open','suppress30ms','suppress50ms']:
  opens=[n for n in notes if n.pitch==46]
  if policy=='hats-only':result=notes
  elif policy=='replace-hats':result=route_drum_keys({'base':base,'new':notes},'base',{42:'new',46:'new'},60.0304375)
  elif policy=='replace-open':result=route_drum_keys({'base':base,'new':notes},'base',{46:'new'},60.0304375)
  else:
   tolerance=.03 if policy=='suppress30ms' else .05
   result=clean_notes([n for n in base if n.pitch!=46 and not(n.pitch==42 and any(abs(n.onset-m.onset)<=tolerance+1e-9 for m in opens))]+opens,60.0304375)
  path=root/f'YODO-SW-x{multiplier}__{policy}.mid'
  if result:write_midi(result,path)
  else:
   import mido
   m=mido.MidiFile(type=1);m.tracks.append(mido.MidiTrack([mido.MetaMessage('end_of_track')]));m.save(path)
  rows.append({'id':path.stem,'model':f'YODO-SW-x{multiplier}','policy':policy,'path':str(path),'sha256':sha(path),'raw_sha256':sha(p),'multiplier':multiplier})
m=Path('outputs/open-hat/候选来源.json');old=json.loads(m.read_text());old['supplemental_control']={'raw_path':str(p),'sha256':sha(p),'reason':'corrected backend directSW comparison, no HH preprocessing'};old['candidates'].extend(rows);m.write_text(json.dumps(old,indent=2));print('total',len(old['candidates']))
