from pathlib import Path
import json,hashlib,numpy as np,soundfile as sf
pieces=[];notes=[]
for i,kit in enumerate([0,8]):
 y,sr=sf.read(f'work/open-hat/control-kit{kit}.wav',dtype='float32',always_2d=True);pieces.append(y[:int(10.5*sr)])
 gt=json.loads(Path(f'work/open-hat/control-kit{kit}.truth.json').read_text());notes.extend(dict(n,onset=n['onset']+i*10.5,kit=kit) for n in gt['notes'] if n['pitch'] in [42,46])
y=np.concatenate(pieces);gain=.9/float(np.max(np.abs(y)));y*=gain;p=Path('work/open-hat/control-hats-level.wav');assert not p.exists();sf.write(p,y,sr,subtype='PCM_16')
p.with_suffix('.truth.json').write_text(json.dumps({'purpose':'level robustness control, bothkits hats only, single shared gain, known synthesis timing unchanged','notes':notes,'gain':gain,'duration':len(y)/sr,'audio_sha256':hashlib.sha256(p.read_bytes()).hexdigest()},indent=2));print('gain',gain)
r=Path('outputs/open-hat/实验登记.json');d=json.loads(r.read_text());d['level_control']={'purpose':'first controls hat level~10x lower than kick/snare; additional known hats-only sharedgain0.9peak robustness check, not GT song tuning','tasks':['level-mt3','level-idm','level-yodo-rgb']};r.write_text(json.dumps(d,indent=2))
