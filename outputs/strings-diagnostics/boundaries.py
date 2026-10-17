"""Evidence of block-end coincidence, not proof of a decoder defect."""
from pathlib import Path
import json,hashlib
root=Path('outputs/strings-diagnostics');out=root/'窗口衔接诊断.json'
if out.exists():raise FileExistsError(out)
x=json.loads((root/'诊断结果.json').read_text());rows={}
for id,r in x['rows'].items():
 raw=json.loads(Path(r['raw_path']).read_text());hop=raw['model_window_samples']/raw['sample_rate'];notes=[n for n in raw['notes'] if n['category']=='strings']
 ends=[n for n in notes if n['offset'] is not None and n['offset']>0 and abs(n['offset']/hop-round(n['offset']/hop))<1e-7]
 rows[id]={'window_seconds':hop,'raw_strings':len(notes),'exact_boundary_end_count':len(ends),'events':ends,'decode_errors':raw['decode_errors'],'raw_sha256':hashlib.sha256(Path(r['raw_path']).read_bytes()).hexdigest()}
out.write_text(json.dumps({'rows':rows,'limits':'raw event/tie tokens were not saved; matching a boundary does not prove corruption or justify extending notes. Need controlled token/tie replay before any repair.'},ensure_ascii=False,indent=2)+'\n')
print({id:r['exact_boundary_end_count'] for id,r in rows.items()})
