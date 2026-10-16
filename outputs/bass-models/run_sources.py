"""Stage3 sequential source comparisons after a fixed stage2 recipe is selected."""
from pathlib import Path
import json,time
from dataclasses import asdict
from audio_midi.worker import run_command,WorkerError
root=Path('outputs/bass-models');path=root/'任务记录.json';rows=json.loads(path.read_text())
def run(id,cmd):
 try:result={'id':id,'command':cmd,'status':'ok',**asdict(run_command(cmd,time.monotonic()+1800,Path('work/bass-models')/(id+'.log'),6*1024**3))}
 except WorkerError as e:result={'id':id,'command':cmd,'status':'failed','attempts':e.attempts,'peak_memory_bytes':e.peak_memory_bytes,'error':str(e)}
 rows.append(result);path.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');print(result,flush=True)
 if result['status']!='ok':raise RuntimeError(result['error'])
if not Path('work/bass-models/ft-receipt.json').exists():
 run('ft-separation',['work/sep-env/bin/python','outputs/bass-models/run_ft.py','/Users/ringscherry/Desktop/吉他产品/v0.0/test/李荣浩 - 不将就-[AudioTrimmer.com].mp3'])
model=json.loads((root/'phase2-choice.json').read_text())['row']['recipe']['model']
for source,audio in [('ft','work/bass-models/ft-bass.wav'),('sw','work/two-methods/sw-full/bass.wav')]:
 if model=='pyin':cmd=['.venv/bin/python','outputs/bass-models/run_pyin.py',audio,f'work/bass-models/pyin-{source}.npz']
 else:cmd=['env','PYTHONPATH=work/bass-models/penn-legacy:work/bass-models/deps:work/bass-models/aux:src','work/sep-env/bin/python','outputs/bass-models/run_pitch.py',model,audio,f'work/bass-models/{model}-{source}.npz']
 run(model+'-'+source,cmd)
assert sum(x['attempts'] for x in rows)<=12
