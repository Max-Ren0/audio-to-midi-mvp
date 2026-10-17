"""Known prefix removal, boundary movement analysis, no fitted time shift."""
from common import *
from dataclasses import replace
from types import SimpleNamespace
from collections import defaultdict
import numpy as np,argparse
from scipy.optimize import linear_sum_assignment
from audio_midi.backends.selected import decode_segments,normalize_raw
from audio_midi.stitching import clean_notes
from audio_midi.strings_bounded import overlap_extend
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'shift-comparison.json');parser.add_argument('--diagnostic-dir',type=Path,default=RUN/'shifted');parser.add_argument('--overlap-dir',type=Path,default=RUN/'overlap');parser.add_argument('--score-dir',type=Path,default=ROOT);parser.add_argument('--other-choice',type=Path,default=ROOT/'A-harmonic-choice.json');parser.add_argument('--mix-choice',type=Path,default=ROOT/'harmonic-choice.json');args=parser.parse_args();out=args.output
if out.exists():raise FileExistsError('Preserve shift diagnostics')
protect();rows={};replay=[];candidates=[];hop=32767/16000
for source,cache in [('other','work/v01/runtime/1792079033121801000/strings.json'),('mix','work/v01/runtime/1792079033121801000/mix.json')]:
 captures={}
 for prefix in [0,16384]:
  path=Path(f'work/strings-bounded/{source}-{prefix}/raw.json');r=json.loads(path.read_text());assert sha(r['token_path'])==r['token_sha256'] and sha(r['windows_path'])==r['windows_sha256']
  assert r['input_sha256']==sha(r['input_path']) and r['frozen_decoder_sha256']==sha('src/audio_midi/backends/selected.py')
  windows=json.loads(Path(r['windows_path']).read_text());channels=defaultdict(list)
  for w in windows:channels[w['channel']].append(([SimpleNamespace(**e) for e in w['events']],[SimpleNamespace(**e) for e in w['ties']],None,w['start']))
  recovered=[]
  for channel in sorted(channels):ns,err=decode_segments(channels[channel]);recovered+=ns
  ns,dropped=normalize_raw(recovered);assert [asdict(n) for n in ns]==r['notes'];replay.append({'source':source,'prefix':prefix,'tokens_sha256':r['token_sha256'],'windows_sha256':r['windows_sha256'],'event_replay_exact':True})
  captures[prefix]=r
 old=json.loads(Path(cache).read_text());assert captures[0]['notes']==old['notes'] and captures[0]['decode_errors']==old['decode_errors']
 oldnotes=[NoteEvent(**n) for n in old['notes'] if n['category']=='strings' and n['offset'] is not None]
 boundary=[n for n in oldnotes if n.offset>0 and abs(n.offset/hop-round(n.offset/hop))<1e-7]
 shifted=[]
 for r in captures[16384]['notes']:
  n=NoteEvent(**r)
  if n.category in ['vocal','drums'] or n.offset is None:continue
  n=replace(n,onset=max(0,n.onset-1.024),offset=min(DURATION,n.offset-1.024))
  if n.offset>n.onset:shifted.append(n)
 weights=np.zeros((len(boundary),len(shifted)+len(boundary)))
 for i,n in enumerate(boundary):
  for j,s in enumerate(shifted):
   intersection=max(0,min(n.offset,s.offset)-max(n.onset,s.onset));union=max(n.offset,s.offset)-min(n.onset,s.onset);iou=intersection/union
   if n.pitch==s.pitch and (abs(n.onset-s.onset)<=.15+1e-9 or iou>=.3):weights[i,j]=1+iou+.1*max(0,1-abs(n.onset-s.onset)/.15)
 ii,jj=linear_sum_assignment(-weights);details=[]
 for i,j in zip(ii,jj):
  n=boundary[i]
  if j>=len(shifted) or weights[i,j]==0:details.append({'old':asdict(n),'matched':False});continue
  s=shifted[j];delta=s.offset-n.offset;new_grid_distance=abs((s.offset+1.024)/hop-round((s.offset+1.024)/hop))*hop;old_grid_distance=abs(s.offset/hop-round(s.offset/hop))*hop
  following=abs(abs(delta)-hop/2)<=.05 and new_grid_distance<=.02
  details.append({'old':asdict(n),'matched':True,'shifted':asdict(s),'offset_delta':delta,'distance_to_shifted_grid':new_grid_distance,'distance_to_original_grid':old_grid_distance,'follows_halfblock':following})
 comparable=sum(r['matched'] for r in details);moving=sum(r.get('follows_halfblock',False) for r in details);positive=comparable>=3 and moving*2>=comparable
 shifted_strings=clean_notes([replace(n,category='strings',program=48) for n in shifted if n.category=='strings'],DURATION)
 diag=save(source+'-shifted',shifted_strings,args.diagnostic_dir,{'source':source,'raw_path':f'work/strings-bounded/{source}-16384/raw.json','prefix_removed_exact_seconds':1.024,'selection_candidate':False})
 diagnostic_score=score(diag)
 rows[source]={'cached_unshifted_notes_exact':True,'boundary_count':len(boundary),'comparable':comparable,'moving_with_halfblock':moving,'positive_signal':positive,'details':details,'shifted_diagnostic':diagnostic_score,'limits':'other labels may match the same pitch; positional sensitivity not definitive decoder root cause'}
 if positive:
  previous=args.other_choice if source=='other' else args.mix_choice;parent=json.loads(previous.read_text())['row'];notes=[NoteEvent(**n) for n in read_detail(parent)['notes']]
  extended,log=overlap_extend(notes,shifted_strings,hop);id='A-overlap' if source=='other' else 'C-overlap';r=save(id,extended,args.overlap_dir,{'parent':parent['id'],'extension_evidence':log,'rule':'samepitch >half shorter overlap; old onsets unchanged; clip at next same-pitch onset; knownprefix removed, no reference input'})
  candidates.append({'parent':parent,'row':r})
result={'sources':rows,'replay':replay,'overlap_candidates':candidates,'data_gate_passed':False,'registration_sha256':sha(ROOT/'实验登记.json')}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
for s,r in rows.items():print(s,'boundary',r['boundary_count'],'comparable',r['comparable'],'moving',r['moving_with_halfblock'],'positive',r['positive_signal'])
for pair in candidates:
 r=score(pair['row']);p=score(pair['parent']);s=r['score'];b=p['score'];keep=s['onset']['f1']>b['onset']['f1'] and s['offset']['f1']>=b['offset']['f1'] and s['near_onset_coverage']>=b['near_onset_coverage']
 (args.score_dir/(r['id']+'-scores.json')).write_text(json.dumps({'parent':p,'candidate':r,'exploratory_keep':keep,'reason':'strict onset improvement AND offset/coverage no drop; diagnostic only'},ensure_ascii=False,indent=2)+'\n');print(r['id'],r['predicted'],s['onset']['f1'],s['offset']['f1'],'keep',keep)
protect()
