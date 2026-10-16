from pathlib import Path
import sys,numpy as np,torch
sys.path.insert(0,str(Path('work/open-hat/mdxnet-infer-cb4779eedeca4f55ba498df8e234e2b5f4b90aaf/src').resolve()))
from mdxnet_infer.inference import MDX23CInference
from mdxnet_infer.config import MDX23CConfig
class Identity(torch.nn.Module):
 num_target_instruments=6
 def forward(self,x):return x[:,None].repeat(1,6,1,1)
engine=object.__new__(MDX23CInference);engine.device=torch.device('cpu');engine.model=Identity();engine.config=MDX23CConfig.drumsep_6stem()
y=np.zeros((44100*7+17,2),dtype=np.float32);y[[0,1000,len(y)//2,len(y)-1]]=[.2,.8]
stems=engine.separate(y,progress=False)
assert len(stems)==6
for k,v in stems.items():assert v.shape==y.shape and np.allclose(v,y,rtol=1e-5,atol=1e-6),(k,v.shape)
print('identity chunking first/middle/last impulses unchanged; no learned forward')
