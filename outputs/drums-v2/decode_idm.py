"""Pre-registered IDM threshold/whole-key controls, no reference."""
from pathlib import Path
from dataclasses import asdict
import numpy as np,json,hashlib
from scipy.signal import find_peaks
from audio_midi.events import NoteEvent
from audio_midi.quality import read_notes
from audio_midi.midi import write_midi
from audio_midi.drums import route_drum_keys
from audio_midi.stitching import clean_notes

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path('outputs/runs/drums-v2/idm');root.mkdir(exist_ok=False);rows=[]
basep=Path('outputs/runs/drums-v2/stage3/combo-1.mid');base=read_notes(basep)
for source in ['sw','demucs']:
 p=Path(f'work/drums-v2/idm-{source}-full60.npz');d=np.load(p);on=d['onset_probs'];vel=d['velocity'];fps=44100/256
 for threshold in [.3,.5,.7]:
  notes=[]
  for c,key in enumerate([49,51,42,46,36,38,41,48,45]):
   peaks,_=find_peaks(on[c],height=threshold,distance=round(.05*fps))
   notes.extend(NoteEvent('drums',key,float(t/fps),float(t/fps+.1),int(np.clip(vel[c,t]*127,1,127)),0) for t in peaks)
  notes=clean_notes(notes,60.0304375)
  for mode in ['solo','replace46-49','replace46','replace49']:
   selected=notes if mode=='solo' else route_drum_keys({'base':base,'idm':notes},'base',{key:'idm' for key in {'replace46-49':[46,49],'replace46':[46],'replace49':[49]}[mode]},60.0304375)
   mid=root/f'idm-{source}-{threshold}-{mode}.mid'
   if selected:write_midi(selected,mid)
   else:
    import mido
    empty=mido.MidiFile(type=1);empty.tracks.append(mido.MidiTrack([mido.MetaMessage('end_of_track')]));empty.save(mid)
   rows.append({'id':mid.stem,'path':str(mid),'sha256':sha(mid),'source_npz':str(p),'activation_sha256':sha(p),'threshold':threshold,'mode':mode,'baseline':str(basep),'baseline_sha256':sha(basep)})
Path('outputs/drums-v2/IDM来源.json').write_text(json.dumps({'class_GM_mapping':[49,51,42,46,36,38,41,48,45],'reference_used':False,'candidates':rows},indent=2))
