from pathlib import Path
from dataclasses import asdict
import json,hashlib,shutil
from audio_midi.events import NoteEvent
from audio_midi.quality import read_notes,metrics,load_reference_tracks
from audio_midi.stitching import clean_notes
from audio_midi.drums import optimized_drums_v2
from audio_midi.midi import write_midi
from audio_midi.render import render_midi

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths={'general':'outputs/runs/v01/development/单轨/drums.mid','mix':'work/v01/mix.json','oaf_sw':'work/drums-v2/decoded/oaf-sw-t0.5.json','oaf_demucs':'work/drums-v2/decoded/oaf-demucs-t0.35.json','adtof':'work/drums-v2/decoded/adtof-s0.18-h0.165.json','weak_cymbal':'work/drums-v2/decoded/cymbal-0.15.json'}
def load(p):
 p=Path(p)
 if p.suffix=='.mid':return read_notes(p)
 return clean_notes([NoteEvent(**{k:n[k] for k in ['category','pitch','onset','offset','velocity','program']}) for n in json.loads(p.read_text())['notes'] if n['category']=='drums'],60.0304375)
ns=optimized_drums_v2(**{k:load(p) for k,p in paths.items()},duration=60.0304375)
root=Path('outputs/runs/drums-v2/交付');root.mkdir(exist_ok=False);mid=root/'鼓-v0.1-强化版.mid';write_midi(ns,mid)
assert sha(mid)==sha('outputs/runs/drums-v2/selected-combined.mid'),(sha(mid),sha('outputs/runs/drums-v2/selected-combined.mid'))
sf=Path('work/models/GeneralUser-GS.sf2');render=render_midi(mid,sf,root/'鼓-v0.1-强化版试听.wav')
import mido
base=Path('outputs/runs/drums/钢琴B固定-鼓升级六轨/多乐器.mid');old=read_notes(base)
original=mido.MidiFile(base);replacement=mido.MidiFile(mid);assert original.ticks_per_beat==replacement.ticks_per_beat
new=mido.MidiFile(type=original.type,ticks_per_beat=original.ticks_per_beat)
for track in original.tracks:
 name=next((m.name for m in track if m.type=='track_name'),'')
 new.tracks.append(next(t for t in replacement.tracks if any(m.type=='track_name' and m.name=='drums' for m in t)) if name=='drums' else track)
six=root/'六轨-仅替换鼓.mid';new.save(six)
check=mido.MidiFile(six)
assert len(check.tracks)==len(original.tracks)
for before,after in zip(original.tracks,check.tracks):
 if not any(m.type=='track_name' and m.name=='drums' for m in before):assert before==after
render_midi(six,sf,root/'六轨-仅替换鼓试听.wav')
ref=load_reference_tracks(Path('outputs/two-methods/标准清单.json'));score=metrics(ref,read_notes(mid),.9995,.14,60.0304375)['per_category']['drums'];per_key={}
for key in sorted({n.pitch for n in ref if n.category=='drums' and .14<=n.onset<60.14042228125}|{n.pitch for n in ns}):per_key[str(key)]=metrics([n for n in ref if n.category=='drums' and n.pitch==key],[n for n in read_notes(mid) if n.pitch==key],.9995,.14,60.0304375)['overall']
manifest={'input_sha256':'6da0f0ec87ee0b37d83d1c8fc2aa8f89dec1cb38b5c1926484317ac91c5bab98','sources':{k:{'path':str(Path(p).resolve()),'sha256':sha(p)} for k,p in paths.items()},'recipe':'audio_midi.drums.optimized_drums_v2','status':'seen-development research, not blind or commercial approval'}
Path('outputs/drums-v2/固定鼓来源清单.json').write_text(json.dumps(manifest,indent=2))
report={'scope':'current0-60 only; same key onset50ms, fixed .9995/.14 alignment; seen development','score':score,'per_key':per_key,'six_track_score':metrics(ref,read_notes(six),.9995,.14,60.0304375),'other_five_identical':True,'old_six_path':str(base),'old_six_sha256':sha(base),'render':render,'artifacts':{p.name:{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in root.iterdir()}}
Path('outputs/drums-v2/交付校验.json').write_text(json.dumps(report,indent=2));print(score);print(report['six_track_score']['overall'])
