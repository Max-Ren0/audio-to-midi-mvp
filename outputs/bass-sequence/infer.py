"""Four sequential, single-attempt isolated pitch jobs; no reference access."""
from pathlib import Path
import os,signal,subprocess,time,json,hashlib,psutil
root=Path('outputs/bass-sequence');ledger=root/'任务记录.json'
if ledger.exists():raise FileExistsError('Preserve existing attempts')
rows=[]
for source,audio in [('ft','work/bass-models/ft-bass.wav'),('sw','work/two-methods/sw-full/bass.wav')]:
 for model in ['crepe','penn']:
  output=f'work/bass-sequence/{model}-{source}.npz'
  if Path(output).exists():raise FileExistsError(output)
  cmd=['work/sep-env/bin/python','outputs/bass-models/run_pitch.py',model,audio,output]
  env=os.environ.copy();env.update({'PYTHONPATH':'work/bass-models/penn-legacy:work/bass-models/deps:work/bass-models/aux:src','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','NUMBA_NUM_THREADS':'2','MKL_NUM_THREADS':'2'})
  log=Path(f'work/bass-sequence/{model}-{source}.log');start=time.monotonic();peak=0;reason=None
  with log.open('xb') as f:
   p=subprocess.Popen(cmd,stdout=f,stderr=f,env=env,start_new_session=True)
   try:
    while p.poll() is None:
     try:
      process=psutil.Process(p.pid);rss=sum(q.memory_info().rss for q in [process,*process.children(recursive=True)] if q.is_running());peak=max(peak,rss)
     except psutil.NoSuchProcess:pass
     if time.monotonic()-start>1800:reason='timeout';break
     if peak>6*1024**3:reason='memory limit';break
     time.sleep(.1)
   finally:
    try:os.killpg(p.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    p.wait()
  row={'id':f'{model}-{source}','command':cmd,'source_sha256':hashlib.sha256(Path(audio).read_bytes()).hexdigest(),'status':'ok' if p.returncode==0 and not reason else 'failed','reason':reason,'attempts':1,'elapsed_seconds':time.monotonic()-start,'peak_memory_bytes':peak,'returncode':p.returncode,'log_path':str(log)}
  rows.append(row);ledger.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');print(row,flush=True)
  if row['status']!='ok':raise RuntimeError('Stop on failure; inspect preserved log')
