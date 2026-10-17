from common import *
import argparse
p=argparse.ArgumentParser();p.add_argument('stage',choices=['short','merge','harmonic']);p.add_argument('--ledger',type=Path);p.add_argument('--output',type=Path);p.add_argument('--choice',type=Path);a=p.parse_args()
ledger=a.ledger or ROOT/({'short':'post-ledger.json','merge':'merge-ledger.json','harmonic':'harmonic-ledger.json'}[a.stage]);output=a.output or ROOT/(a.stage+'-scores.json');choice=a.choice or ROOT/(a.stage+'-choice.json')
if output.exists() or choice.exists():raise FileExistsError('Preserve scores')
data=json.loads(ledger.read_text());control=score(data['parent']);rows=[control,*[score(r) for r in data['rows']]];best=control
for r in rows[1:]:
 s=r['score'];base=best['score']
 if s['onset']['f1']>base['onset']['f1'] and s['offset']['f1']>=base['offset']['f1'] and s['near_onset_coverage']>=base['near_onset_coverage']:best=r
result={'stage':a.stage,'rows':rows,'exploratory_selected':best['id'],'data_gate_passed':False,'limits':'7notes only; no deployed/frozen strings change'}
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');choice.write_text(json.dumps({'row':{k:v for k,v in best.items() if k not in ['score','duration_pitch','duration_chroma']}},ensure_ascii=False,indent=2)+'\n')
for r in rows:print(r['id'],r['predicted'],round(r['score']['onset']['f1']*100,3),round(r['score']['offset']['f1']*100,3))
print('exploratory only',best['id'])
