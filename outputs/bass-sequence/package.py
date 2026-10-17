"""Package complete trials and only-bass six-track replacement, local media only."""
from pathlib import Path
from dataclasses import replace
import json,hashlib,shutil,csv,mido,numpy as np,soundfile as sf,librosa
from audio_midi.quality import read_notes,load_reference_tracks
from audio_midi.bass_diagnostics import match_events
from audio_midi.render import render_midi
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path('outputs/bass-sequence');run=Path('outputs/runs/bass-sequence');scores=[json.loads((root/f'phase{i}-scores.json').read_text()) for i in [1,2,3,4]]
rows={r['id']:r for s in scores for r in s['rows']};winner=rows[scores[-1]['selected']];lock=json.loads(Path('config/bass-evidence.lock.json').read_text())
for key in ['bass','six_track']:assert sha(lock[key]['path'])==lock[key]['sha256']
dest=run/'交付';dest.mkdir(parents=True,exist_ok=False);rendered={};byhash={}
for id,row in rows.items():
 p=dest/(id+f"-F1-{row['f1']*100:.2f}.mid");shutil.copyfile(row['path'],p);wav=p.with_suffix('.wav')
 if row['sha256'] in byhash:
  earlier,meta=byhash[row['sha256']];shutil.copyfile(earlier,wav);rendered[id]=meta|{'same_midi_as':str(earlier)}
 else:
  rendered[id]=render_midi(p,Path('work/models/GeneralUser-GS.sf2'),wav);byhash[row['sha256']]=(wav,rendered[id])
selected=dest/'选用贝斯.mid';shutil.copyfile(winner['path'],selected);shutil.copyfile(byhash[winner['sha256']][0],selected.with_suffix('.wav'))
old=mido.MidiFile(lock['six_track']['path']);bass=mido.MidiFile(selected);new=mido.MidiFile(type=old.type,ticks_per_beat=old.ticks_per_beat)
assert bass.ticks_per_beat==old.ticks_per_beat
assert [m.tempo for m in bass.tracks[0] if m.type=='set_tempo']==[m.tempo for m in old.tracks[0] if m.type=='set_tempo']
for t in old.tracks:
 if t.name!='bass':new.tracks.append(mido.MidiTrack(m.copy() for m in t));continue
 channel=next(m.channel for m in t if m.type=='program_change');bt=next(t for t in bass.tracks if t.name=='bass')
 new.tracks.append(mido.MidiTrack(m.copy(channel=channel) if not m.is_meta else m.copy() for m in bt))
six=dest/'六轨-仅替换贝斯.mid';new.save(six)
for a,b in zip(old.tracks,mido.MidiFile(six).tracks):
 if a.name!='bass':assert [m.dict() for m in a]==[m.dict() for m in b]
rendered['six_track']=render_midi(six,Path('work/models/GeneralUser-GS.sf2'),six.with_suffix('.wav'))
refs=[n for n in load_reference_tracks(Path('outputs/two-methods/标准清单.json')) if .14<=n.onset<.14+.9995*60.0304375]
pred=[replace(n,onset=n.onset*.9995+.14) for n in read_notes(six)];per={}
for c in ['piano','acoustic_guitar','electric_guitar','bass','drums','strings']:
 r=[n for n in refs if n.category==c];p=[n for n in pred if n.category==c];tp=len(match_events(r,p,.05));per[c]={'matched':tp,'predicted':len(p),'reference':len(r),'f1':2*tp/(len(p)+len(r))}
tp=sum(v['matched'] for v in per.values());summary={'overall':{'matched':tp,'predicted':len(pred),'reference':len(refs),'f1':2*tp/(len(pred)+len(refs))},'per_category':per,'other_five_tracks_conductor_unchanged':True,'rendered':rendered}
(root/'六轨评分与试听.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
bassrefs=[n for n in refs if n.category=='bass'];details=[]
for i,n in enumerate(bassrefs):
 details.append({'reference_index':i,'source_time':(n.onset-.14)/.9995,'pitch':n.pitch,**{id:i in r['matched_reference_indices'] for id,r in rows.items()}})
with (root/'36标准音全候选变化.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(details[0]),lineterminator='\n');w.writeheader();w.writerows(details)
base=set(rows['D75']['matched_reference_indices']);changes=[]
for id,r in rows.items():
 current=set(r['matched_reference_indices']);changes.append({'id':id,'gained_vs_75':sorted(current-base),'lost_vs_75':sorted(base-current)})
(root/'所有候选命中变化.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
# Excerpts: 18 diagnostic errors plus all unmatched old/new note events (same-pitch50ms matching, not causes).
clips=run/'clips';clips.mkdir(exist_ok=False)
original=Path('/Users/ringscherry/Desktop/吉他产品/v0.0/test/李荣浩 - 不将就-[AudioTrimmer.com].mp3');mix,sr=librosa.load(original,sr=16000,mono=True)
audio={'原曲':(mix,sr,str(original))}
trace=json.loads(Path('work/bass-diagnostics/replay/trace.json').read_text())
for label,p in [('Demucs',trace['stem_path']),('ft','work/bass-models/ft-bass.wav'),('SW','work/two-methods/sw-full/bass.wav')]:
 y,s=sf.read(p,always_2d=True);audio[label]=(y.mean(axis=1),s,p)
oldnotes=read_notes(Path(lock['bass']['path']));newnotes=read_notes(selected);pairs=match_events(oldnotes,newnotes,.05);oi={i for i,j in pairs};ni={j for i,j in pairs}
events=[{'kind':'baseline_'+r['kind'],'index':r['index'],'pitch':r['pitch'],'time':r['source_time']} for r in json.loads((root/'75基线逐音归因.json').read_text())['rows']]
for kind,ns,hit in [('removed_or_moved',oldnotes,oi),('added_or_moved',newnotes,ni)]:
 events += [{'kind':kind,'index':i,'pitch':n.pitch,'time':n.onset} for i,n in enumerate(ns) if i not in hit]
cliprows=[]
for i,e in enumerate(events):
 start=max(0,e['time']-.4);end=min(len(mix)/sr,e['time']+.6);files=[]
 for label,(y,s,source) in audio.items():
  p=clips/f'{i:02d}-{label}.wav';sf.write(p,y[int(start*s):int(end*s)],s,subtype='PCM_16');files.append({'path':str(p),'sha256':sha(p),'source':source,'source_sha256':sha(source)})
 cliprows.append(e|{'start':start,'end':end,'files':files})
(root/'局部变化与归因片段.json').write_text(json.dumps(cliprows,ensure_ascii=False,indent=2)+'\n')
selection={'status':'seen0–60 development research, not recording truth or production/generalization acceptance','selected':winner['id'],'recipe':winner['recipe'],'previous_lock':'config/bass-evidence.lock.json','previous_lock_sha256':sha('config/bass-evidence.lock.json'),'input_sha256':lock['input_sha256'],'bass':{'path':str(selected),'sha256':sha(selected)},'six_track':{'path':str(six),'sha256':sha(six)},'score':{k:winner[k] for k in ['matched','predicted','reference','extra','missed','f1']},'registration_sha256':sha(root/'实验登记.json'),'implementation_sha256':sha('src/audio_midi/bass_sequence.py'),'common_sha256':sha(root/'common.py'),'stage_choices':[{ 'phase':i,'selected':scores[i-1]['selected'],'ledger_sha256':sha(root/f'phase{i}-ledger.json'),'score_sha256':sha(root/f'phase{i}-scores.json')} for i in [1,2,3,4]],'entrypoint':'outputs/bass-sequence/generate.py; verified cache rebuild only, default runner unchanged'}
Path('config/bass-sequence.lock.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
print('selected',winner['id'],selection['score'],'six',summary['overall'],'clips',len(cliprows)*4)
