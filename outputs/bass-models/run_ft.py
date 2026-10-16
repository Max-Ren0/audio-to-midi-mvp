"""Run the official HTDemucs-ft bass specialist only; no reference data."""
from pathlib import Path
import argparse,hashlib,json,random,time
import numpy as np,soundfile as sf,torch
from demucs.pretrained import get_model
from demucs.apply import apply_model
from demucs.separate import load_track
p=argparse.ArgumentParser();p.add_argument('input',type=Path);a=p.parse_args();dest=Path('work/bass-models/ft-bass.wav')
if dest.exists():raise FileExistsError('Preserving ft stem')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(a.input)=='6da0f0ec87ee0b37d83d1c8fc2aa8f89dec1cb38b5c1926484317ac91c5bab98'
weight=Path('work/bass-models/ftrepo/d12395a8-e57c48e6.th');assert sha(weight).startswith('e57c48e6')
torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(0);np.random.seed(0);random.seed(0)
start=time.monotonic();model=get_model('d12395a8',repo=weight.parent).eval().cpu()
assert model.sources==['drums','bass','other','vocals']
y=load_track(a.input,model.audio_channels,model.samplerate);ref=y.mean(0);mean=ref.mean();std=ref.std();y=(y-mean)/std
with torch.inference_mode():z=apply_model(model,y[None],device='cpu',shifts=1,split=True,overlap=.25,segment=6,progress=False,num_workers=0)[0]
z=z*std+mean
if not torch.isfinite(z).all():raise ValueError('Nonfinite ft separation')
bass=z[1].numpy().T;sf.write(dest,bass,model.samplerate,subtype='FLOAT')
r={'input_sha256':sha(a.input),'bass_sha256':sha(dest),'weight_sha256':sha(weight),'model':'d12395a8','official_bag':'htdemucs_ft bass weights [0,1,0,0]','settings':{'seed':0,'shifts':1,'segment':6,'overlap':.25,'normalization':'official mono mean/std, restore each output'},'sample_rate':model.samplerate,'duration':len(bass)/model.samplerate,'elapsed_seconds':time.monotonic()-start,'wrapper_sha256':sha(__file__),'caveat':'Only bass specialist checkpoint run; full bag was not executed, random-shift sequence not bitwise-equivalent to full bag.'}
Path('work/bass-models/ft-receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
