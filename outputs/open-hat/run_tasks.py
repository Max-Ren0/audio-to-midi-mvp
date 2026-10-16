"""Sequential budgeted model process launcher; counts failures and retries."""
from pathlib import Path
from dataclasses import asdict
import json,time,sys
from audio_midi.worker import run_command,WorkerError
name=sys.argv[1];cmd=sys.argv[2:];registry=Path('outputs/open-hat/实验登记.json');d=json.loads(registry.read_text());count=sum(x.get('run',{}).get('attempts',0) for x in d['attempts'])
if count+2>d['resource_limits']['round_max_model_process_attempts_including_failures']:raise RuntimeError('insufficient retry budget')
row={'id':name,'command':cmd,'status':'running'};d['attempts'].append(row);registry.write_text(json.dumps(d,indent=2))
try:
 r=run_command(cmd,time.monotonic()+1800,Path('work/open-hat')/(name+'.log'),6*1024**3);row.update(status='completed',run=asdict(r))
except WorkerError as e:
 row.update(status='failed',run={'attempts':e.attempts,'peak_memory_bytes':e.peak_memory_bytes},error=str(e));raise
finally:
 registry.write_text(json.dumps(d,indent=2));Path('work/open-hat/'+name+'-run.json').write_text(json.dumps(row,indent=2));print(row,flush=True)
