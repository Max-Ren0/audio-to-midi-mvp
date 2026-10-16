from pathlib import Path
import json,hashlib
from audio_midi.quality import load_reference_tracks,read_notes,metrics
manifest=Path('outputs/open-hat/候选来源.json');d=json.loads(manifest.read_text());ref=load_reference_tracks(Path('outputs/two-methods/标准清单.json'))
for row in d['candidates']:
 p=Path(row['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'];notes=read_notes(p)
 row['score']=metrics(ref,notes,.9995,.14,60.0304375)['per_category']['drums']
 row['hat_score']=metrics([n for n in ref if n.category=='drums' and n.pitch in [42,46]],[n for n in notes if n.pitch in [42,46]],.9995,.14,60.0304375)['overall']
 row['per_key']={str(key):metrics([n for n in ref if n.category=='drums' and n.pitch==key],[n for n in notes if n.pitch==key],.9995,.14,60.0304375)['overall'] for key in [42,46]}
rows=sorted(d['candidates'],key=lambda r:-(r['score']['f1'] or 0));baseline=next(r for r in rows if r['model']=='baseline')
qualifying=[r for r in rows if r['policy']!='hats-only' and r['per_key']['46']['matched']>0 and r['score']['f1']>baseline['score']['f1']]
result={'scope':'current0-60 known development only, fixed .9995/.14 alignment, same GM onset50ms maximum matching, no reference events in generation','candidates':rows,'selected':qualifying[0] if qualifying else baseline,'selection':'best whole rule with overall improvement and openhat recovered; otherwise protect baseline'}
Path('outputs/open-hat/本曲评分.json').write_text(json.dumps(result,indent=2))
for model in ['YourMT3','IDM','YODO','consensus']:
 group=[r for r in rows if r['model'].startswith(model) and r['policy']!='hats-only'];r=group[0];print('BEST',model,r['id'],r['score'],'open',r['per_key']['46'])
print('SELECTED',result['selected']['id'],result['selected']['score'])
