"""Diagnostic-only cross-source coverage; never used by candidate generation."""
from pathlib import Path
import json,numpy as np
from common import source_features
root=Path('outputs/bass-sequence');dest=root/'三源逐音覆盖.json'
if dest.exists():raise FileExistsError(dest)
rows=json.loads((root/'75基线逐音归因.json').read_text())['rows'];sources={s:source_features(s) for s in ['demucs','ft','sw']};out=[]
for row in rows:
 t=row['source_time'];pitch=row['pitch'];e={}
 for s,d in sources.items():
  a=max(0,int(np.floor((t-.15)/.016)));b=min(len(d['f']['raw']),int(np.ceil((t+.15)/.016)));models={}
  for m,(p,q,v) in d['streams'].items():
   exact=np.isfinite(p[a:b])&(np.rint(p[a:b])==pitch)
   models[m]={'raw_exact_frames':int(exact.sum()),'qualified_exact_frames':int((exact&v[a:b]).sum())}
  e[s]={'models':models,'audio':d['feature'](t),'near_anchors':[float(x) for x in d['anchors'] if abs(float(x)-t)<=.15]}
 out.append({'kind':row['kind'],'index':row['index'],'pitch':pitch,'source_time':t,'evidence':e})
dest.write_text(json.dumps({'rows':out,'limits':'diagnostic neighborhood support, not same-performance ground truth or generator inputs'},ensure_ascii=False,indent=2)+'\n')
print('diagnosed',len(out),'events x3sources x3models')
