"""Read-only fixed-artifact diagnostic, never modifies MIDI or accepts a new alignment."""
from pathlib import Path
from dataclasses import replace
import hashlib,json,numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching
from audio_midi.quality import read_notes,load_reference_tracks

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest=Path('outputs/two-methods/标准清单.json');prediction=Path('outputs/runs/drums-v2/交付/鼓-v0.1-强化版.mid')
r=[n for n in load_reference_tracks(manifest) if n.category=='drums' and .14<=n.onset<.14+.9995*60.0304375]
p=[replace(n,onset=n.onset*.9995+.14) for n in read_notes(prediction)]
def match(r,p,tol,same=True):
 rows=[];cols=[]
 for i,a in enumerate(r):
  for j,b in enumerate(p):
   if abs(a.onset-b.onset)<=tol+1e-9 and (not same or a.pitch==b.pitch):rows.append(i);cols.append(j)
 graph=csr_matrix((np.ones(len(rows)),(rows,cols)),shape=(len(r),len(p)))
 return [(i,int(j)) for i,j in enumerate(maximum_bipartite_matching(graph,perm_type='column')) if j>=0]
pairs=match(r,p,.05);ri={i for i,j in pairs};pj={j for i,j in pairs};rn=[x for i,x in enumerate(r) if i not in ri];pn=[x for j,x in enumerate(p) if j not in pj]
d={'prediction_path':str(prediction),'prediction_sha256':sha(prediction),'reference_manifest_sha256':sha(manifest),'alignment':{'scale':.9995,'shift':.14,'duration':60.0304375},'same_key_tp_by_tolerance_seconds':{str(t):len(match(r,p,t)) for t in [.03,.05,.1,.15]},'matched_median_absolute_time_error_ms':float(np.median([abs(r[i].onset-p[j].onset)*1000 for i,j in pairs])),'time_only_full_tp_50ms':len(match(r,p,.05,False)),'residual_cross_key_nearby':[{'reference_key':rn[i].pitch,'prediction_key':pn[j].pitch,'delta_ms':(pn[j].onset-rn[i].onset)*1000} for i,j in match(rn,pn,.05,False)],'caveat':'Residual cross-key proximity is diagnostic only; simultaneous drum hits and reference arrangement differences prevent treating pairs as proven misclassification. Official score stays same-key50ms. No prediction modified.'}
Path('outputs/drums-v2/剩余错误诊断.json').write_text(json.dumps(d,indent=2));print(json.dumps(d,indent=2))
