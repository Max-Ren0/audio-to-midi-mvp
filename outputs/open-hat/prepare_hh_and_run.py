from pathlib import Path
import soundfile as sf,numpy as np,json,hashlib,subprocess
p=Path('work/open-hat/drumsep-full60/hh.wav');y,sr=sf.read(p,dtype='float32',always_2d=True);peak=float(np.abs(y).max());assert np.isfinite(y).all() and peak>1e-8
gain=.9/peak;out=Path('work/open-hat/hh-normalized.wav');assert not out.exists();sf.write(out,y*gain,sr,subtype='FLOAT')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
out.with_suffix('.receipt.json').write_text(json.dumps({'source':str(p),'source_sha256':sha(p),'gain':gain,'normalization':'single shared0.9peak no clipping/timechange','output_sha256':sha(out),'samples':len(y),'sample_rate':sr,'reference_used':False},indent=2))
commands=[('fullhh-idm',['work/sep-env/bin/python','work/drums-v2/run_idm.py',str(out),'work/open-hat/fullhh-idm.npz']),('fullhh-mt3',['.venv/bin/python','work/open-hat/run_mt3_wav.py',str(out),'work/open-hat/fullhh-mt3.json']),('fullhh-yodo',['work/sep-env/bin/python','work/open-hat/run_yodo_rgb.py',str(out),'work/open-hat/fullhh-yodo.json'])]
for name,cmd in commands:subprocess.run(['.venv/bin/python','work/open-hat/run_tasks.py',name,*cmd],check=True)
