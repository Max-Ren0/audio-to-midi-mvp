"""Single-attempt, CPU2, four sequential captures after postprocessing saved."""
from pathlib import Path
import os,signal,subprocess,time,json,psutil
root=Path('outputs/strings-bounded');work=Path('work/strings-bounded');ledger=root/'任务记录.json'
if ledger.exists():raise FileExistsError('Preserve attempts')
assert (root/'harmonic-scores.json').exists()
rows=[]
for source,input in [('other','work/v01/runtime/1792079033121801000/strings.npy'),('mix','work/v01/runtime/1792079033121801000/mix.npy')]:
 for prefix in [0,16384]:
  id=f'{source}-{prefix}';output=work/id
  if output.exists():raise FileExistsError(output)
  cmd=['.venv/bin/python','outputs/strings-bounded/run_capture.py',input,str(output),'--prefix-samples',str(prefix)]
  env=os.environ.copy();env.update({'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','MKL_NUM_THREADS':'2','NUMBA_NUM_THREADS':'2','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'})
  log=work/(id+'.log');start=time.monotonic();peak=0;reason=None
  with log.open('xb') as f:
   process=subprocess.Popen(cmd,stdout=f,stderr=f,env=env,start_new_session=True)
   try:
    while process.poll() is None:
     try:
      p=psutil.Process(process.pid);peak=max(peak,sum(c.memory_info().rss for c in [p,*p.children(recursive=True)] if c.is_running()))
     except psutil.NoSuchProcess:pass
     if time.monotonic()-start>1800:reason='timeout';break
     if peak>3.2*1024**3:reason='memory limit';break
     time.sleep(.1)
   finally:
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    process.wait()
  row={'id':id,'command':cmd,'status':'ok' if not reason and process.returncode==0 else 'failed','reason':reason,'returncode':process.returncode,'attempts':1,'peak_memory_bytes':peak,'elapsed_seconds':time.monotonic()-start,'log_path':str(log)}
  rows.append(row);ledger.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');print(row,flush=True)
  if row['status']!='ok':raise RuntimeError('Preserve failed attempt and stop')
