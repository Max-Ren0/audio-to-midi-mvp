from pathlib import Path
import sys,json,hashlib
import numpy as np,soundfile as sf
from scipy.signal import resample_poly
from math import gcd
from audio_midi.backends.selected import infer
source=Path(sys.argv[1]);out=Path(sys.argv[2]);y,sr=sf.read(source,dtype='float32',always_2d=True);g=gcd(sr,16000);x=resample_poly(y.mean(axis=1),16000//g,sr//g).astype('float32')
array=out.with_suffix('.npy');assert not array.exists();np.save(array,x)
infer(array,Path('work/models/yourmt3.ckpt'),'cpu',out)
d=json.loads(out.read_text());d['source_wav_sha256']=hashlib.sha256(source.read_bytes()).hexdigest();d['source_wav_path']=str(source);d['wav_wrapper_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();d['reference_used']=False;out.write_text(json.dumps(d,indent=2))
