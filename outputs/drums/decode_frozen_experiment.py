"""Decode only the frozen drum policy; no parameter search or reference input."""
from pathlib import Path
import json,hashlib,numpy as np
from adtof_pytorch.post_processing import PeakPicker
policy_path=Path('config/drums-hybrid-research.json');policy=json.loads(policy_path.read_text())
source=Path('work/drums/extra-sw-adtof.npz');out=Path('work/drums/extra-sw-adtof-frozen.json')
if out.exists():raise FileExistsError(out)
spec=policy['specialist']
with np.load(source) as f:a=f['activations']
peaks=PeakPicker(thresholds=spec['thresholds'],fps=spec['fps']).pick(a,labels=spec['labels'])[0]
notes=[{'category':'drums','pitch':int(p),'onset':float(t),'offset':float(t+.1),'velocity':100,'program':0} for p,ts in peaks.items() for t in ts]
out.write_text(json.dumps({'notes':notes,'policy_sha256':hashlib.sha256(policy_path.read_bytes()).hexdigest(),'activation_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'reference_used':False,'thresholds':spec['thresholds']},indent=2));print('frozen extra raw predictions',len(notes))
