"""Finite preregistered candidates from cached sources, no reference events."""
from pathlib import Path
from dataclasses import asdict
import json,argparse,numpy as np
from audio_midi.events import NoteEvent
from audio_midi.midi import write_midi
from audio_midi.bass_evidence import insert_supported
from common import *

def main():
 p=argparse.ArgumentParser();p.add_argument('phase',type=int,choices=[1,2,3,4]);p.add_argument('--output',type=Path);p.add_argument('--ledger',type=Path);p.add_argument('--previous-choice',type=Path);p.add_argument('--source-ledger',type=Path);a=p.parse_args()
 output=a.output or RUN/f'phase{a.phase}';ledger=a.ledger or ROOT/f'phase{a.phase}-ledger.json'
 if output.exists() or ledger.exists():raise FileExistsError('Preserve existing output and ledger')
 all_sources={s:source_features(s) for s in ['demucs','ft','sw']};output.mkdir(parents=True);rows=[]
 sources={p:h for d in all_sources.values() for p,h in d['sources'].items()}
 for s,d in all_sources.items():np.savez(output/(s+'-features.npz'),**d['arrays'])
 def save(id,notes,evidence,recipe):
  path=output/(id+'.mid');write_midi(notes,path);detail=output/(id+'.json')
  detail.write_text(json.dumps({'id':id,'recipe':recipe,'sources':sources,'notes':[asdict(n) for n in notes],'evidence':evidence},ensure_ascii=False,indent=2)+'\n')
  row={'id':id,'recipe':recipe,'path':str(path),'sha256':sha(path),'provenance_path':str(detail),'provenance_sha256':sha(detail),'predicted':len(notes)};rows.append(row)
  if id=='D75':
   lock=json.loads(Path('config/bass-evidence.lock.json').read_text());assert row['sha256']==lock['bass']['sha256']
 if a.phase==1:
  for s,id in [('demucs','D75'),('ft','FT75'),('sw','SW75')]:
   notes,e=full_recipe(all_sources[s]);save(id,notes,e,{'source':s,'method':'full frozen75 recipe'})
 else:
  previous=json.loads((a.previous_choice or ROOT/f'phase{a.phase-1}-choice.json').read_text())['row'];base=load_row(previous);rows.append(previous)
  first=json.loads((a.source_ledger or ROOT/'phase1-ledger.json').read_text())['rows']
  basec=[candidate(n,'primary',all_sources,True) for n in base]
  individual=[candidate(n,r['recipe']['source'],all_sources) for r in first for n in load_row(r)]
  if a.phase==2:
   clusters=cluster_onsets(basec+individual,.04)
   for minimum,id in [(2,'F2'),(1,'F1')]:
    selected=[];audit=[]
    for cluster in clusters:
     primary=[x for x in cluster if x['baseline']];eligible=[x for x in cluster if x['source_count']>=minimum and x['credible_attack']]
     best=max(eligible,key=lambda x:(x['source_count'],np.mean(x['neural_agreement']),max(max(v['rise']-1,v['flux']) for v in x['attack'].values()),x['baseline'],-x['onset'])) if eligible else None
     chosen=primary[0] if primary else None
     if best is not None and (chosen is None or best['source_count']>chosen['source_count']):chosen=best
     if chosen:selected.append(chosen)
     audit.append({'cluster':cluster,'selected':chosen})
    save(id,normalize(selected),audit,{'parent':previous['id'],'minimum_sources':minimum,'method':'local source selection'})
  elif a.phase==3:
   pool=basec+individual
   for s,d in all_sources.items():pool+=pitch_proposals(d,s,all_sources,.08)
   clusters=cluster_onsets(pool,.04)
   for profile in json.loads((ROOT/'实验登记.json').read_text())['stage2']['profiles']:
    selected,objective=decode_sequence(clusters,profile['onset_cost'],profile['jump_penalty'],profile['minimum_sources'],.08)
    save(profile['id'],normalize(selected),{'clusters':clusters,'selected_candidates':selected,'objective':objective},profile|{'parent':previous['id']})
  else:
   for profile in json.loads((ROOT/'实验登记.json').read_text())['stage3']['weak_short_profiles']:
    minimum=profile['minimum_run_seconds'];pool=[]
    for s,d in all_sources.items():pool+=pitch_proposals(d,s,all_sources,minimum,True)
    chosen=list(base);audit=[]
    for cluster in cluster_onsets(pool,.04):
     eligible=[]
     for c in cluster:
      neural_votes=0;attacks=0
      for s,d in all_sources.items():
       raw,q,valid=d['streams']['crepe'];pr,pq,pv=d['streams']['penn'];a0=max(0,int(np.ceil(c['onset']/.016)));b=min(len(raw),int(np.ceil(min(c['offset'],c['onset']+.32)/.016)))
       mask=valid[a0:b]&pv[a0:b]&(np.rint(raw[a0:b])==c['pitch'])&(np.rint(pr[a0:b])==c['pitch'])
       neural_votes+=mask.sum()*.016>=minimum-1e-9
       attacks+=any(abs(float(t)-c['onset'])<=.04+1e-9 and (d['feature'](t)['rise']>=1.1 or d['feature'](t)['flux']>=.5) for t in d['anchors'])
      c=c|{'neural_source_votes':int(neural_votes),'attack_source_votes':int(attacks)}
      if neural_votes>=2 and attacks>=2:eligible.append(c)
     best=max(eligible,key=lambda c:(c['score'],-c['onset'])) if eligible else None;ok=False
     if best:
      n=NoteEvent('bass',best['pitch'],best['onset'],best['offset'],None,33);chosen,ok=insert_supported(chosen,n,minimum)
     audit.append({'cluster':cluster,'best':best,'accepted':ok})
    save(profile['id'],chosen,audit,profile|{'parent':previous['id']})
 result={'phase':a.phase,'registration_sha256':sha(ROOT/'实验登记.json'),'generator_sha256':sha(__file__),'common_sha256':sha(ROOT/'common.py'),'implementation_sha256':sha('src/audio_midi/bass_sequence.py'),'rows':rows}
 ledger.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print([(r['id'],r['predicted']) for r in rows])
if __name__=='__main__':main()
