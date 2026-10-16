from pathlib import Path
import tinysoundfont,numpy as np,soundfile as sf,json,hashlib
root=Path('work/open-hat');font=Path('work/models/GeneralUser-GS.sf2')
for kit in [0,8]:
 synth=tinysoundfont.Synth(gain=-6,samplerate=44100);bank=synth.sfload(str(font));synth.program_select(9,bank,128,kit)
 events=[(1.,42,80),(2.,42,100),(3.,42,60),(5.,46,80),(7.,46,100),(9.,46,60),(11.,38,90),(12.,36,90)]
 chunks=[];cursor=0
 for onset,key,velocity in events:
  frame=round(onset*44100);chunks.append(np.frombuffer(synth.generate_simple(frame-cursor),dtype=np.float32).copy().reshape(-1,2));cursor=frame;synth.noteon(9,key,velocity)
 chunks.append(np.frombuffer(synth.generate_simple(14*44100-cursor),dtype=np.float32).copy().reshape(-1,2));y=np.concatenate(chunks)
 path=root/f'control-kit{kit}.wav';assert not path.exists();sf.write(path,y,44100,subtype='PCM_16')
 gt={'purpose':'known synthetic positive/negative class controls, not song reference or training','soundfont_sha256':hashlib.sha256(font.read_bytes()).hexdigest(),'bank':128,'kit':kit,'duration':14,'audio_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'notes':[{'pitch':k,'onset':t,'velocity':v} for t,k,v in events]}
 path.with_suffix('.truth.json').write_text(json.dumps(gt,indent=2))
print('2 independent kit controls; each3 closed+3 open+2 other hits')
