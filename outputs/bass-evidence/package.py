"""Local delivery and diagnostics; predictions are already frozen in stage ledgers."""
from pathlib import Path
from dataclasses import replace
import json,hashlib,shutil,csv,mido,numpy as np,soundfile as sf,librosa
from audio_midi.quality import read_notes,load_reference_tracks
from audio_midi.bass_diagnostics import match_events
from audio_midi.render import render_midi
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path('outputs/bass-evidence');run=Path('outputs/runs/bass-evidence')
scores=[json.loads((root/f'phase{i}-scores.json').read_text()) for i in [1,2,3]]
rows={r['id']:r for s in scores for r in s['rows']};winner=rows[scores[-1]['selected']]
lock=json.loads(Path('config/bass-models.lock.json').read_text())
for key in ['bass','six_track']:assert sha(lock[key]['path'])==lock[key]['sha256']
dest=run/'交付';dest.mkdir(parents=True,exist_ok=False)
labels={'baseline':'00-上版贝斯-62.34','M2':'01-合并弱重复-70.59','A3':'02-补音-72.22','R1':'03-贝斯新版-75.00'}
renders={}
for id,label in labels.items():
 path=dest/(label+'.mid');shutil.copyfile(rows[id]['path'],path)
 renders[label]=render_midi(path,Path('work/models/GeneralUser-GS.sf2'),dest/(label+'.wav'))
old=mido.MidiFile(lock['six_track']['path']);bass=mido.MidiFile(winner['path']);new=mido.MidiFile(type=old.type,ticks_per_beat=old.ticks_per_beat)
assert bass.ticks_per_beat==old.ticks_per_beat
assert [m.tempo for m in bass.tracks[0] if m.type=='set_tempo']==[m.tempo for m in old.tracks[0] if m.type=='set_tempo']
for t in old.tracks:
 if t.name!='bass':new.tracks.append(mido.MidiTrack(m.copy() for m in t));continue
 channel=next(m.channel for m in t if m.type=='program_change');bt=next(t for t in bass.tracks if t.name=='bass')
 new.tracks.append(mido.MidiTrack(m.copy(channel=channel) if not m.is_meta else m.copy() for m in bt))
path=dest/'六轨-仅替换贝斯.mid';new.save(path)
for a,b in zip(old.tracks,mido.MidiFile(path).tracks):
 if a.name!='bass':assert [m.dict() for m in a]==[m.dict() for m in b]
renders['六轨-仅替换贝斯']=render_midi(path,Path('work/models/GeneralUser-GS.sf2'),dest/'六轨-仅替换贝斯.wav')
refs=[n for n in load_reference_tracks(Path('outputs/two-methods/标准清单.json')) if .14<=n.onset<.14+.9995*60.0304375]
ps=[replace(n,onset=n.onset*.9995+.14) for n in read_notes(path)];per={}
for c in ['piano','acoustic_guitar','electric_guitar','bass','drums','strings']:
 r=[n for n in refs if n.category==c];p=[n for n in ps if n.category==c];tp=len(match_events(r,p,.05));per[c]={'matched':tp,'predicted':len(p),'reference':len(r),'f1':2*tp/(len(p)+len(r))}
tp=sum(v['matched'] for v in per.values());summary={'overall':{'matched':tp,'predicted':len(ps),'reference':len(refs),'f1':2*tp/(len(ps)+len(refs))},'per_category':per,'other_five_tracks_and_conductor_unchanged':True,'rendered':renders}
(root/'六轨评分与试听.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
# Development-reference accounting is separate from all generation decisions.
bassrefs=[n for n in refs if n.category=='bass'];detail=[]
for i,n in enumerate(bassrefs):
 r={'reference_index':i,'reference_onset':n.onset,'source_time':(n.onset-.14)/.9995,'pitch':n.pitch}
 for id in labels:r[id+'_matched']=i in rows[id]['matched_reference_indices']
 detail.append(r)
with (root/'36标准音逐步变化.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(detail[0]));w.writeheader();w.writerows(detail)
changes=[]
for previous,id in zip(['baseline','M2','A3'],['M2','A3','R1']):
 a=set(rows[previous]['matched_reference_indices']);b=set(rows[id]['matched_reference_indices'])
 changes.append({'previous':previous,'current':id,'gained_reference_indices':sorted(b-a),'lost_reference_indices':sorted(a-b)})
(root/'逐步命中变化.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
# Every selected edit gets raw-mixture/stem excerpts; no listening claim.
clips=run/'clips';clips.mkdir(exist_ok=False)
input_path=Path('/Users/ringscherry/Desktop/吉他产品/v0.0/test/李荣浩 - 不将就-[AudioTrimmer.com].mp3')
mixture,sr=librosa.load(input_path,sr=16000,mono=True)
trace=json.loads(Path('work/bass-diagnostics/replay/trace.json').read_text());stem,ssr=sf.read(trace['stem_path'],always_2d=True);stem=stem.mean(axis=1)
cliprows=[]
for id in ['M2','A3','R1']:
 evidence=json.loads(Path(rows[id]['provenance_path']).read_text())['edits_and_proposals']
 for j,e in enumerate(evidence):
  if id!='M2' and not e.get('accepted'):continue
  t=e['removed_onset'] if id=='M2' else e['onset'] if id=='A3' else e['old_onset']
  start=max(0,t-.4);end=min(len(mixture)/sr,t+.6);files=[]
  for label,y,s in [('原曲',mixture,sr),('贝斯',stem,ssr)]:
   p=clips/f'{id}-{j:02d}-{label}.wav';sf.write(p,y[int(start*s):int(end*s)],s,subtype='PCM_16');files.append({'path':str(p),'sha256':sha(p)})
  cliprows.append({'stage':id,'event_index':j,'start':start,'end':end,'evidence':e,'files':files})
(root/'修改证据与片段.json').write_text(json.dumps(cliprows,ensure_ascii=False,indent=2)+'\n')
selection={'status':'seen 0–60 development research; not production/generalization/recording truth','selected':winner['id'],'chain':['S2-short-0','M2','A3','R1'],'input_sha256':lock['input_sha256'],'previous_lock':'config/bass-models.lock.json','previous_lock_sha256':sha('config/bass-models.lock.json'),'bass':{'path':str(dest/(labels[winner['id']]+'.mid')),'sha256':sha(dest/(labels[winner['id']]+'.mid'))},'six_track':{'path':str(path),'sha256':sha(path)},'score':{k:winner[k] for k in ['matched','predicted','reference','extra','missed','f1']},'implementation_sha256':sha('src/audio_midi/bass_evidence.py'),'registration_sha256':sha(root/'实验登记.json'),'entrypoint':'outputs/bass-evidence/generate.py; cached research only, default runner unchanged'}
Path('config/bass-evidence.lock.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
print(summary['overall']);print('clips',len(cliprows),'bass',selection['bass'])
