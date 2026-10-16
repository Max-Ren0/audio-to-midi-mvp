"""Local pitch inference only, no reference. Native timestamps have explicit zero origin."""
import argparse,json,hashlib,time,sys
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa,torch
from unittest.mock import patch

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('model',choices=['crepe','penn']);p.add_argument('audio',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
if a.output.exists():raise FileExistsError('Preserve existing pitch output')
torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(0);np.random.seed(0)
y,sr=sf.read(a.audio,dtype='float32',always_2d=True);y=y.mean(axis=1);started=time.monotonic();original_load=torch.load
# All upstream checkpoint loads are constrained to tensor-safe loading.
def safe_load(*args,**kwargs):kwargs['weights_only']=True;return original_load(*args,**kwargs)
with torch.inference_mode(),patch('torch.load',safe_load):
 if a.model=='crepe':
  import torchcrepe
  s=16000;audio=librosa.resample(y,orig_sr=sr,target_sr=s)
  posterior=[]
  for frames in torchcrepe.preprocess(torch.from_numpy(audio)[None],s,160,64,'cpu',True):
   z=torchcrepe.infer(frames,'full','cpu',embed=False)
   if not torch.isfinite(z).all():raise ValueError('Nonfinite raw CREPE probabilities')
   posterior.append(z)
  z=torch.cat(posterior,dim=0).reshape(1,-1,360).transpose(1,2)
  f,q=torchcrepe.postprocess(z,32.71,261,torchcrepe.decode.viterbi,False,True)
  weight=Path(torchcrepe.__file__).parent/'assets/full.pth';config={'package':'torchcrepe0.0.24','decoder':'viterbi','pad':True,'forward_batch':64,'whole_file_decode':True,'native_step':.01,'origin_seconds':0,'sample_rate':s}
 else:
  import penn
  weight=Path('work/bass-models/fcnf0-plus-plus.pt')
  penn.DECODER='viterbi-normal'
  posterior=[]
  for frames in penn.preprocess(torch.from_numpy(y)[None],sr,.01,64,'zero'):
   z=penn.infer(frames,weight)
   if not torch.isfinite(z).all():raise ValueError('Nonfinite raw PENN logits')
   posterior.append(z)
  _,f,q=penn.postprocess(torch.cat(posterior,dim=0),32,261)
  config={'package':'penn0.0.14','forward_batch':64,'whole_file_decode':True,'decoder':penn.DECODER,'periodicity':penn.PERIODICITY,'center':'zero','native_step':.01,'origin_seconds':0,'sample_rate':penn.SAMPLE_RATE,'max_octaves_per_second':penn.MAX_OCTAVES_PER_SECOND}
f=f.detach().cpu().numpy().reshape(-1);q=q.detach().cpu().numpy().reshape(-1)
if not(np.isfinite(f).all() and np.isfinite(q).all() and (f>0).all()):raise ValueError('Nonfinite/invalid pitch output')
a.output.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(a.output,f0=f,periodicity=q,times=np.arange(len(f))*.01)
record={'model':a.model,'source_audio_sha256':sha(a.audio),'weight_path':str(weight),'weight_sha256':sha(weight),'config':config,'frames':len(f),'duration':len(y)/sr,'elapsed_seconds':time.monotonic()-started,'output_sha256':sha(a.output),'wrapper_sha256':sha(__file__)}
a.output.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
