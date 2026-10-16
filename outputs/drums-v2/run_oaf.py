"""Hash-pinned OaF ONNX forward only; no reference input or event relabeling."""
from pathlib import Path
import sys,time,json,hashlib
import numpy as np,soundfile as sf,onnxruntime as ort
from scipy.signal import resample_poly
from math import gcd

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=Path(sys.argv[1]);out=Path(sys.argv[2]);model=Path('work/drums-v2/oaf_drums.onnx')
if out.exists():raise FileExistsError(out)
if sha(model)!='23d4b05ce7e9715bdb4396823d68bc886e8a958fa9f6266c0f7132b78098b521':raise ValueError('OAF weights mismatch')
start=time.monotonic();y,sr=sf.read(source,dtype='float32',always_2d=True);y=y.mean(axis=1)
if sr!=44100:
 g=gcd(sr,44100);y=resample_poly(y,44100//g,sr//g).astype('float32')
clipped=int(np.sum(np.abs(y)>1));y=np.clip(y,-1,1)
options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
session=ort.InferenceSession(str(model),sess_options=options,providers=['CPUExecutionProvider'])
print('inputs',[(i.name,i.shape,i.type) for i in session.get_inputs()],flush=True)
print('outputs',[(i.name,i.shape,i.type) for i in session.get_outputs()],flush=True)
values=session.run(None,{session.get_inputs()[0].name:y[None].astype(np.float32)})
outputs={item.name:value for item,value in zip(session.get_outputs(),values)}
assert all(v.ndim==3 and v.shape[0]==1 and v.shape[2]==8 and np.isfinite(v).all() for v in values)
out.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(out,**outputs)
report={'input_sha256':sha(source),'model_sha256':sha(model),'model_revision':'771fd5529062b9f6f0b58f01cc4b9819db046f4a','sample_rate':44100,'duration_seconds':len(y)/44100,'clipped_samples':clipped,'labels':[36,38,48,42,51,53,49,75],'fps':100,'outputs':{k:list(v.shape) for k,v in outputs.items()},'onnxruntime':ort.__version__,'cpu_threads':2,'elapsed_seconds':time.monotonic()-start,'activation_sha256':sha(out),'script_sha256':sha(__file__),'reference_used':False}
out.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
