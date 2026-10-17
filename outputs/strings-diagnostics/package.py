"""Local listenable diagnostics; reference transformation is only for comparison."""
from pathlib import Path
from dataclasses import asdict
import json,hashlib,shutil,numpy as np,soundfile as sf,librosa
from audio_midi.events import NoteEvent
from audio_midi.quality import read_notes
from audio_midi.midi import write_midi
from audio_midi.render import render_midi
from metrics import duration_overlap
root=Path('outputs/strings-diagnostics');run=Path('outputs/runs/strings-diagnostics');run.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
x=json.loads((root/'诊断结果.json').read_text());duration=x['alignment']['duration'];ref=[NoteEvent(**n) for n in x['reference_notes_source_timeline']]
ref=[NoteEvent('strings',n.pitch,max(0,n.onset),min(duration,n.offset),n.velocity,48) for n in ref]
reference=run/'参考弦乐-仅当前片段对齐.mid';write_midi(ref,reference)
rendered={'reference':render_midi(reference,Path('work/models/GeneralUser-GS.sf2'),reference.with_suffix('.wav'))};covered=[]
for id,r in x['rows'].items():
 p=run/(id+'-现有弦乐.mid');shutil.copyfile(r['path'],p);rendered[id]=render_midi(p,Path('work/models/GeneralUser-GS.sf2'),p.with_suffix('.wav'));notes=read_notes(p)
 for i,n in enumerate(ref):
  same=[(max(n.onset,v.onset),min(n.offset,v.offset),n.pitch) for v in notes if v.pitch==n.pitch and v.offset>n.onset and v.onset<n.offset]
  s=duration_overlap([(n.onset,n.offset,n.pitch)],same,duration)
  covered.append({'source':id,'reference_index':i,'pitch':n.pitch,'start':n.onset,'end':n.offset,'exact_pitch_time_coverage':s['recall'],'nearest_same_pitch_onset_delta':min((v.onset-n.onset for v in notes if v.pitch==n.pitch),key=abs,default=None)})
(root/'逐音持续覆盖.json').write_text(json.dumps(covered,ensure_ascii=False,indent=2)+'\n')
# Source excerpts preserve original sample rates (mix decoded16k); no sound-source identity claim.
input_path=Path('/Users/ringscherry/Desktop/吉他产品/v0.0/test/李荣浩 - 不将就-[AudioTrimmer.com].mp3');y,sr=librosa.load(input_path,sr=16000,mono=True);audio={'原曲':(y,sr,str(input_path))}
for id,r in x['rows'].items():
 y,s=sf.read(r['stem_path'],always_2d=True);audio[id+'-other']=(y.mean(axis=1),s,r['stem_path'])
clips=[];clipdir=run/'clips';clipdir.mkdir()
for i,(start,end) in enumerate([(6.5,10.5),(10.,14.5),(56.4,57.8)]):
 for label,(y,s,source) in audio.items():
  p=clipdir/f'{i:02d}-{label}.wav';sf.write(p,y[int(start*s):int(end*s)],s,subtype='PCM_16');clips.append({'path':str(p),'sha256':sha(p),'source':source,'source_sha256':sha(source),'start':start,'end':end})
(root/'试听与片段.json').write_text(json.dumps({'reference_midi':str(reference),'reference_sha256':sha(reference),'reference_transform':'(referenceTime-.14)/.9995; clip to0–60.0304375; original user file untouched; diagnostic only, not predictions','rendered':rendered,'clips':clips,'listening_status':'not manually heard; MIDI-only synth for3WAV, source excerpts for9clips; independent peak normalization prevents loudness comparison'},ensure_ascii=False,indent=2)+'\n')
print('Saved',len(covered),'per-note coverage,3MIDI/3synthWAV and',len(clips),'sourceclips')
