"""Generate comparable raw pYIN evidence for a new separated bass source."""
from pathlib import Path
import argparse,json,hashlib,numpy as np
from audio_midi.contour import transcribe_monophonic
p=argparse.ArgumentParser();p.add_argument('audio',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
if a.output.exists():raise FileExistsError('Preserve pitch evidence')
t={};transcribe_monophonic(a.audio,'bass',trace=t)
np.savez_compressed(a.output,**{k:v for k,v in t.items() if isinstance(v,np.ndarray)})
a.output.with_suffix('.json').write_text(json.dumps({'source_audio_sha256':hashlib.sha256(a.audio.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'config':'unchanged pYIN32–261Hz,16ms,256ms window'},indent=2)+'\n')
