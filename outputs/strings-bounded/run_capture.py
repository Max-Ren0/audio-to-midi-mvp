"""Same frozen YourMT3 inference/decoder, with raw token and per-window event capture."""
from pathlib import Path
from dataclasses import asdict
import argparse,time,json,hashlib,numpy as np,torch
from audio_midi.backends.selected import WEIGHT_SHA256,MODEL_REVISION,decode_segments,normalize_raw
from mt3_infer.adapters.yourmt3 import YourMT3Adapter
p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--prefix-samples',type=int,default=0);a=p.parse_args()
if a.output.exists():raise FileExistsError('Preserve model capture')
checkpoint=Path('work/models/yourmt3.ckpt');sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();assert sha(checkpoint)==WEIGHT_SHA256
torch.set_num_threads(2);torch.manual_seed(0);np.random.seed(0);start=time.monotonic();audio=np.load(a.input,allow_pickle=False)
if a.prefix_samples:audio=np.r_[np.zeros(a.prefix_samples,dtype=audio.dtype),audio]
adapter=YourMT3Adapter(model_key='yptf_moe_nops');adapter.load_model(str(checkpoint),device='cpu');loaded=time.monotonic()
with torch.inference_mode():
 features=adapter.preprocess(audio,16000).to('cpu');outputs=adapter.model.inference_file(bsz=2,audio_segments=features)
 if isinstance(outputs,tuple):outputs=outputs[0]
model=adapter.model;starts=[model.audio_cfg['input_frames']*i/model.audio_cfg['sample_rate'] for i in range(sum(z.shape[0] for z in outputs))]
a.output.mkdir(parents=True);tokens=a.output/'tokens.npz';np.savez_compressed(tokens,**{f'batch{i}':np.asarray(z.detach().cpu() if isinstance(z,torch.Tensor) else z) for i,z in enumerate(outputs)})
def event(e):return {'program':int(e.program),'is_drum':bool(e.is_drum),'pitch':int(e.pitch),'velocity':int(e.velocity),'time':None if e.time is None else float(e.time)}
from collections import Counter
errors=Counter();groups=[];windows=[]
for channel in range(model.task_manager.num_decoding_channels):
 zipped,_,event_errors=model.task_manager.detokenize_list_batches([z[:,channel,:] for z in outputs],starts,return_events=True)
 for i,(events,ties,last_activity,window_start) in enumerate(zipped):windows.append({'channel':channel,'index':i,'start':float(window_start),'events':[event(e) for e in events],'ties':[event(e) for e in ties]})
 notes,decode_errors=decode_segments(zipped);groups.extend(notes);errors.update(event_errors);errors.update(decode_errors)
notes,dropped=normalize_raw(groups);events_path=a.output/'windows.json';events_path.write_text(json.dumps(windows,ensure_ascii=False,indent=2)+'\n')
record={'notes':[asdict(n) for n in notes],'model':'YourMT3 yptf_moe_nops','model_revision':MODEL_REVISION,'weight_sha256':WEIGHT_SHA256,'device':'cpu','sample_rate':16000,'model_window_samples':model.audio_cfg['input_frames'],'batch_size':2,'dropped_programs':dropped,'decode_errors':dict(errors),'input_path':str(a.input),'input_sha256':sha(a.input),'prefix_samples':a.prefix_samples,'prefix_seconds':a.prefix_samples/16000,'input_duration_before_prefix':len(np.load(a.input))/16000,'token_path':str(tokens),'token_sha256':sha(tokens),'windows_path':str(events_path),'windows_sha256':sha(events_path),'wrapper_sha256':sha(__file__),'frozen_decoder_sha256':sha('src/audio_midi/backends/selected.py'),'model_load_seconds':loaded-start,'total_seconds':time.monotonic()-start}
(a.output/'raw.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print('captured',len(notes),'notes',len(windows),'windows',record['total_seconds'],flush=True)
