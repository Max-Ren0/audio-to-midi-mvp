"""Experiment wrapper around pinned upstream MSST inference; no reference MIDI input."""
import sys,time,json,hashlib
from pathlib import Path
import numpy as np
import torch,yaml,soundfile as sf
from ml_collections import ConfigDict
sys.path.insert(0,str(Path('work/two-methods/msst').resolve()))
from models.bs_roformer import BSRoformer
from utils.model_utils import demix

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
threads = int(sys.argv[4]) if len(sys.argv) > 4 else 2
torch.set_num_threads(threads)
source=Path(sys.argv[1]);out=Path(sys.argv[2]);duration=float(sys.argv[3])
if out.exists():raise FileExistsError(out)
c=ConfigDict(yaml.load(Path('work/two-methods/BS-Rofo-SW-Fixed.yaml').read_text(),Loader=yaml.FullLoader))
c.training.use_amp=False
# Check upstream padding/windowing preserves leading and trailing impulse positions.
class Identity(torch.nn.Module):
 def forward(self,x):return x[:,None].expand(-1,6,-1,-1)
small=ConfigDict({'audio':{'chunk_size':4096},'training':{'instruments':list(c.training.instruments),'target_instrument':None,'use_amp':False},'inference':{'batch_size':1,'num_overlap':2}})
x=np.zeros((2,16000),np.float32);x[:,0]=.2;x[:,-1]=-.3;x[:,8000]=.1
for v in demix(small,Identity(),x,torch.device('cpu'),'bs_roformer').values():assert np.allclose(x,v,atol=1e-6)
print('identity timeline check passed',flush=True)
start=time.monotonic();m=BSRoformer(**c.model.to_dict());state=torch.load('work/models/BS-Rofo-SW-Fixed.ckpt',map_location='cpu',weights_only=True);m.load_state_dict(state,strict=True);del state;m.eval()
y,sr=sf.read(source,dtype='float32',always_2d=True);assert sr==44100 and y.shape[1]==2 and abs(len(y)/sr-duration)<.05
print('model loaded; samples',len(y),flush=True)
result=demix(c,m,y.T,torch.device('cpu'),'bs_roformer',pbar=True)
out.mkdir();files={}
for name,v in result.items():
 assert v.shape==y.T.shape and np.isfinite(v).all()
 p=out/(name.lower()+'.wav');sf.write(p,v.T,sr,subtype='FLOAT');files[name]={'path':str(p),'sha256':sha(p),'rms':float(np.sqrt(np.mean(v*v))),'peak':float(np.max(np.abs(v)))}
(out/'receipt.json').write_text(json.dumps({'input_sha256':sha(source),'duration_seconds':len(y)/sr,'weight_sha256':sha('work/models/BS-Rofo-SW-Fixed.ckpt'),'config_sha256':sha('work/two-methods/BS-Rofo-SW-Fixed.yaml'),'code_commit':'6fdad13686bb7e84d029ec66f9dbe76e65c93ebf','cpu_threads':threads,'amp':False,'elapsed_seconds':time.monotonic()-start,'files':files},indent=2))
print('complete',time.monotonic()-start,flush=True)
