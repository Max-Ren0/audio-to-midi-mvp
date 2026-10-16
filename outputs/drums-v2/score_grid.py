from pathlib import Path
import json,sys,hashlib
from audio_midi.quality import load_reference_tracks,read_notes,metrics
ref=load_reference_tracks(Path('outputs/two-methods/标准清单.json'));d=json.loads(Path(sys.argv[1]).read_text());rows=d['candidates']
for row in rows:
 p=Path(row['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
 row['score']=metrics(ref,read_notes(p),.9995,.14,60.0304375)['per_category']['drums']
rows.sort(key=lambda x:-(x['score']['f1'] or 0));Path(sys.argv[2]).write_text(json.dumps({'scope':'0-60 seen development; fixed .9995 scale +.14s, same key onset50ms maximum matching','candidates':rows},indent=2));print([(r['id'],r['score']) for r in rows[:3]])
