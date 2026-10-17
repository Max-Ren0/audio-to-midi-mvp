"""Local exploratory delivery only. Never replaces current strings or six-track MIDI."""
from common import *
from audio_midi.render import render_midi
from audio_midi.quality import read_notes
import shutil,csv,importlib.metadata
protect();dest=RUN/'交付';dest.mkdir(parents=True,exist_ok=False)
rows={r['id']:r for r in json.loads((ROOT/'matrix-scores.json').read_text())['rows']}
for name in ['short','merge','harmonic','A-short','A-merge','A-harmonic']:
 for r in json.loads((ROOT/(name+'-scores.json')).read_text())['rows']:rows[r['id']]=r
shift=json.loads((ROOT/'shift-comparison.json').read_text())
for source,r in shift['sources'].items():rows[r['shifted_diagnostic']['id']]=r['shifted_diagnostic']
rendered={};samehash={}
for id,r in rows.items():
 path=dest/(id+'.mid');shutil.copyfile(r['path'],path);wav=path.with_suffix('.wav')
 if r['sha256'] in samehash:
  previous,meta=samehash[r['sha256']];shutil.copyfile(previous,wav);rendered[id]=meta|{'same_midi_as':str(previous)}
 else:rendered[id]=render_midi(path,Path('work/models/GeneralUser-GS.sf2'),wav);samehash[r['sha256']]=(wav,rendered[id])
ref=reference();p=dest/'参考-当前片段对齐.mid';write_midi([replace(n,velocity=80,program=48) for n in ref],p);rendered['reference']=render_midi(p,Path('work/models/GeneralUser-GS.sf2'),p.with_suffix('.wav'))
shutil.copyfile(rows['A-M']['path'],dest/'弦乐-后处理探索-不替换现用.mid');shutil.copyfile(dest/'A-M.wav',dest/'弦乐-后处理探索-不替换现用.wav')
summary=[]
for id,r in rows.items():
 s=r['score'];summary.append({'id':id,'predicted':r['predicted'],'onset_TP':s['onset']['matched'],'onset_F1':s['onset']['f1'],'offset_TP':s['offset']['matched'],'offset_F1':s['offset']['f1'],'chroma_onset_F1':s['chroma_onset']['f1'],'near150ms_coverage':s['near_onset_coverage'],'sustained80ms_presence':s['sustained_presence_coverage'],'duration_pitch_F1':r['duration_pitch']['f1'],'duration_chroma_F1':r['duration_chroma']['f1']})
with (ROOT/'全部诊断评分.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(summary[0]),lineterminator='\n');w.writeheader();w.writerows(summary)
changes=[]
for name in ['short','merge','harmonic','A-short','A-merge','A-harmonic']:
 data=json.loads((ROOT/(name+'-scores.json')).read_text());control=data['rows'][0]
 for r in data['rows'][1:]:
  a=control['score'];b=r['score'];ar={i for i,j in a['onset']['pairs']};br={i for i,j in b['onset']['pairs']}
  changes.append({'parent':control['id'],'candidate':r['id'],'removed_event_count':control['predicted']-r['predicted'],'new_matched_reference_indices':sorted(br-ar),'lost_matched_reference_indices':sorted(ar-br),'lost_near_onset_reference_indices':[i for i,(x,y) in enumerate(zip(a['per_reference'],b['per_reference'])) if x['near_onset_prediction_indices'] and not y['near_onset_prediction_indices']],'lost_sustained_presence_indices':[i for i,(x,y) in enumerate(zip(a['per_reference'],b['per_reference'])) if x['present_80ms'] and not y['present_80ms']]})
(ROOT/'逐步删除与覆盖变化.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
(ROOT/'交付记录.json').write_text(json.dumps({'status':'7note diagnostic only; existing strings and six-track NOT replaced; no new promoted winner','exploratory_listen_id':'A-M','candidate_rows':list(rows.values()),'mir_eval_version':importlib.metadata.version('mir_eval'),'rendered':rendered,'reference_midi':str(p),'reference_transform':'inverse fixed .9995/.14, no reference edits to predictions','protected_bass':protect()['bass'],'notes':'WAV MIDI-only, same GM48/SoundFont, independent peak normalization, ends last note+1.5s; no human listening claim'},ensure_ascii=False,indent=2)+'\n')
print('delivered',len(rows),'matrix/post/shift IDs;',len({r['sha256'] for r in rows.values()}),'distinctMID; source files unchanged')
clips=[]
clipdir=RUN/'源音频片段';clipdir.mkdir(parents=True,exist_ok=False)
for r in json.loads(Path('outputs/strings-diagnostics/试听与片段.json').read_text())['clips']:
 assert sha(r['path'])==r['sha256']
 target=clipdir/Path(r['path']).name;shutil.copyfile(r['path'],target)
 clips.append(r|{'path':str(target),'copied_from':r['path']})
(ROOT/'源片段.json').write_text(json.dumps(clips,ensure_ascii=False,indent=2)+'\n')
