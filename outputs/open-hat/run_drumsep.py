from pathlib import Path
import sys,hashlib,json,time
root=Path('work/open-hat/mdxnet-infer-cb4779eedeca4f55ba498df8e234e2b5f4b90aaf');sys.path.insert(0,str((root/'src').resolve()))
import torch,soundfile as sf,numpy as np
from mdxnet_infer.inference import MDX23CInference

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=Path(sys.argv[1]);dest=Path(sys.argv[2]);assert not dest.exists()
weights=Path('work/open-hat/drumsep.ckpt');cfg=Path('work/open-hat/drumsep.yaml')
assert sha(weights)=='d2a4aa53eb584d21eead358a4e66d1882ad182911be018f052b5da73be9096d0'
assert sha(cfg)=='17d1649a227f841165bdb4c11a42082898192a1ea3ceab7e7e0b9293d6589dd6'
torch.set_num_threads(2);torch.set_num_interop_threads(1);start=time.monotonic()
engine=MDX23CInference(config_path=cfg,device='cpu')
state=torch.load(weights,map_location='cpu',weights_only=True);engine.model.load_state_dict(state.get('state_dict',state),strict=True)
checks={'frames':0}
def guard(module,inputs,output):
 assert torch.isfinite(output).all(),'Nonfinite model forward'
 checks['frames']+=1
engine.model.register_forward_hook(guard)
y,sr=sf.read(source,dtype='float32',always_2d=True);assert sr==44100 and y.shape[1]==2
stems=engine.separate(y,sample_rate=sr,progress=True);assert set(stems)=={'kick','snare','toms','hh','ride','crash'}
dest.mkdir();result={}
for name,values in stems.items():
 assert np.isfinite(values).all() and len(values)==len(y),(name,values.shape,y.shape)
 p=dest/(name+'.wav');sf.write(p,values,44100,subtype='FLOAT');result[name]={'shape':list(values.shape),'sha256':sha(p),'rms':float(np.sqrt(np.mean(values**2)))}
receipt={'input_sha256':sha(source),'input_path':str(source),'weight_sha256':sha(weights),'config_sha256':sha(cfg),'code_revision':root.name,'script_sha256':sha(__file__),'sample_rate':sr,'duration':len(y)/sr,'stems':result,'elapsed_seconds':time.monotonic()-start,'forward_finiteness_checks':checks['frames'],'reference_used':False}
(dest/'receipt.json').write_text(json.dumps(receipt,indent=2));print(receipt,flush=True)
