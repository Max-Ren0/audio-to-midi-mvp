"""Reference-free activations from installed, hash-verified ADTOF research model."""
from pathlib import Path
import sys,hashlib,json,time,importlib.metadata
import numpy as np,torch
import adtof_pytorch as ad
from adtof_pytorch.model import calculate_n_bins,create_frame_rnn_model,load_pytorch_weights,load_audio_for_model

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=Path(sys.argv[1]);out=Path(sys.argv[2])
if out.exists():raise FileExistsError(out)
torch.set_num_threads(2);torch.set_num_interop_threads(1)
weights=Path(ad.get_default_weights_path())
if sha(weights)!='1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320':raise ValueError('ADTOF weight mismatch')
start=time.monotonic();model=create_frame_rnn_model(calculate_n_bins());model=load_pytorch_weights(model,str(weights),strict=True);model.eval()
x=load_audio_for_model(str(source))
with torch.inference_mode():pred=model(x).cpu().numpy()
if pred.ndim!=3 or pred.shape[0]!=1 or pred.shape[2]!=5 or not np.isfinite(pred).all():raise ValueError('Invalid ADTOF activations')
out.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(out,activations=pred)
code_root=Path(ad.__file__).parent
receipt={'input_sha256':sha(source),'weight_sha256':sha(weights),'package_version':importlib.metadata.version('adtof-pytorch'),'code_sha256':{p.name:sha(p) for p in sorted(code_root.glob('*.py'))},'strict_load':True,'labels':[35,38,47,42,49],'fps':100,'shape':list(pred.shape),'cpu_threads':2,'elapsed_seconds':time.monotonic()-start,'activation_sha256':sha(out),'script_sha256':sha(__file__),'reference_used':False}
out.with_suffix('.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
