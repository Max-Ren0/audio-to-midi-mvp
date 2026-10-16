"""Decode the same cached activations under predeclared thresholds; no reference."""
from pathlib import Path
import json,sys,hashlib
import numpy as np
from adtof_pytorch.post_processing import PeakPicker,FRAME_RNN_THRESHOLDS,LABELS_5
source=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
with np.load(source) as data:a=data['activations']
for name,scale in [('default',1.0),('lower075',.75),('lower050',.5)]:
 thresholds=[x*scale for x in FRAME_RNN_THRESHOLDS]
 peaks=PeakPicker(thresholds=thresholds,fps=100).pick(a,labels=LABELS_5)[0]
 notes=[{'category':'drums','pitch':int(p),'onset':float(t),'offset':float(t+.1),'velocity':100,'program':0} for p,ts in peaks.items() for t in ts]
 (out/f'{name}.json').write_text(json.dumps({'notes':notes,'activation_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'thresholds':thresholds,'labels':LABELS_5,'fps':100,'algorithm':'installed ADTOF PeakPicker unchanged','reference_used':False},indent=2))
 print(name,len(notes))
