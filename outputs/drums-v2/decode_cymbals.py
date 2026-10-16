from pathlib import Path
import json,numpy as np
from adtof_pytorch.post_processing import PeakPicker
root=Path('work/drums-v2/decoded');act=np.load('work/drums/sw-full60.npz')['activations']
for threshold in [.15,.225,.3]:
 peaks=PeakPicker(thresholds=[.165,.18,.24,.165,threshold],fps=100).pick(act,labels=[35,38,47,42,49])[0]
 ns=[{'category':'drums','pitch':49,'onset':float(t),'offset':float(t+.1),'velocity':100,'program':0} for t in peaks[49]]
 p=root/f'cymbal-{threshold}.json';p.write_text(json.dumps({'notes':ns,'threshold':threshold,'reference_used':False},indent=2))
