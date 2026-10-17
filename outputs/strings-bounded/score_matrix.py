from common import *
import argparse,importlib.metadata
p=argparse.ArgumentParser();p.add_argument('--ledger',type=Path,default=ROOT/'matrix-ledger.json');p.add_argument('--output',type=Path,default=ROOT/'matrix-scores.json');a=p.parse_args()
if a.output.exists():raise FileExistsError('Preserve scores')
rows=[score(r) for r in json.loads(a.ledger.read_text())['rows']];targets=[];refs=reference()
for row in rows:
 detail=read_detail(row);raw=detail['evidence']['original_notes']
 targets.append({'cell':row['id'],'targets':[{'reference_index':i,'pitch':n.pitch,'start':n.onset,'end':n.offset,'raw_same_pitch_overlap':[e for e in raw if e['pitch']==n.pitch and e['offset'] is not None and e['offset']>n.onset and e['onset']<n.offset],'coverage':row['score']['per_reference'][i]} for i,n in enumerate(refs) if i in [0,1]]})
result={'mir_eval_version':importlib.metadata.version('mir_eval'),'data_gate_passed':False,'reason':'only7 notes; current excerpt diagnostic only per user','reference_type':'complete tool export unedited per user, not studio truth','rows':rows,'target_presence_and_original_labels':targets}
a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
for r in rows:print(r['id'],r['score']['predicted'],'onset',round(r['score']['onset']['f1']*100,3),'offset',round(r['score']['offset']['f1']*100,3),'presence',r['score']['sustained_presence_coverage'])
