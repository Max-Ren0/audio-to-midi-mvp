"""Sequential bounded model jobs. Existing resource worker permits <=1 retry."""
import argparse,json,time
from dataclasses import asdict
from pathlib import Path
from audio_midi.worker import run_command,WorkerError
p=argparse.ArgumentParser();p.add_argument('mode',choices=['probes','global-probes','full']);a=p.parse_args()
root=Path('outputs/bass-models');logpath=root/'任务记录.json';tasks=json.loads(logpath.read_text()) if logpath.exists() else []
audio='work/bass-models/control15.wav' if a.mode in ('probes','global-probes') else 'work/new/stems/htdemucs_6s/李荣浩 - 不将就-[AudioTrimmer.com]/bass.wav'
for model in ['crepe','penn']:
 id=f'{model}-{a.mode}';out=f'work/bass-models/{id}.npz'
 cmd=['env','PYTHONPATH=work/bass-models/penn-legacy:work/bass-models/deps:work/bass-models/aux:src','work/sep-env/bin/python','outputs/bass-models/run_pitch.py',model,audio,out]
 try:r=asdict(run_command(cmd,time.monotonic()+1800,Path(f'work/bass-models/{id}.log'),6*1024**3));row={'id':id,'command':cmd,'status':'ok',**r}
 except WorkerError as e:
  row={'id':id,'command':cmd,'status':'failed','attempts':e.attempts,'peak_memory_bytes':e.peak_memory_bytes,'error':str(e)}
 tasks.append(row);logpath.write_text(json.dumps(tasks,ensure_ascii=False,indent=2)+'\n');print(row,flush=True)
 if row['status']!='ok':raise RuntimeError(row['error'])
 if a.mode in ('probes','global-probes'):
  import numpy as np
  z=np.load(out);f=z['f0'][130:270];error=np.median(abs(12*np.log2(f/82.406889)))
  if error>.5:raise ValueError(f'{model} failed known-pitch control: {error}')
  print(model,'known-tone median semitone error',float(error),flush=True)
