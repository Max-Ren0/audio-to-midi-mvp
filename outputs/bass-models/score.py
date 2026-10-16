"""Fixed-reference stage scoring and whole-recipe selection; no edits to predictions."""
from pathlib import Path
from dataclasses import replace
import argparse,hashlib,json
from audio_midi.quality import read_notes,load_reference_tracks
from audio_midi.bass_diagnostics import match_events
p=argparse.ArgumentParser();p.add_argument('phase',type=int);p.add_argument('--ledger',type=Path);p.add_argument('--output',type=Path);p.add_argument('--choice',type=Path);a=p.parse_args();root=Path('outputs/bass-models')
ledger=a.ledger or root/f'phase{a.phase}-ledger.json';data=json.loads(ledger.read_text())
refs=[n for n in load_reference_tracks(Path('outputs/two-methods/标准清单.json')) if n.category=='bass' and .14<=n.onset<.14+.9995*60.0304375]
rows=[]
for row in data['rows']:
 assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256']
 ns=read_notes(Path(row['path']));ns=[replace(n,onset=n.onset*.9995+.14) for n in ns];pairs=match_events(refs,ns,.05);tp=len(pairs)
 rows.append(row|{'matched':tp,'reference':len(refs),'extra':len(ns)-tp,'missed':len(refs)-tp,'f1':2*tp/(len(ns)+len(refs)),'matched_reference_indices':sorted(i for i,j in pairs),'matched_pairs':pairs})
winner=max(rows,key=lambda r:(r['f1'],-r['extra']))
if winner['f1']<=rows[0]['f1']:winner=rows[0]
result={'phase':a.phase,'rows':rows,'selected':winner['id'],'ledger_sha256':hashlib.sha256(ledger.read_bytes()).hexdigest(),'evaluation':'same-pitch50ms max one-to-one; .9995/.14 fixed; seen development arrangement'}
(a.output or root/f'phase{a.phase}-scores.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(a.choice or root/f'phase{a.phase}-choice.json').write_text(json.dumps({'row':{k:v for k,v in winner.items() if k in ['id','recipe','path','sha256','provenance_path','provenance_sha256','predicted']}},ensure_ascii=False,indent=2)+'\n')
for r in rows:print(r['id'],r['matched'],r['predicted'],r['extra'],r['missed'],round(r['f1']*100,3))
print('selected',winner['id'])
