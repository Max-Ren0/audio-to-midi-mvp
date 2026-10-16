from pathlib import Path
import sys,json,numpy as np
sys.path.insert(0,str(Path('work/drums-v2/yodo-deps').resolve()));import cv2
cv2.setNumThreads(2);root=Path('work/drums-v2/yodo')
report=[]
for fusion in [True,False]:
 net=cv2.dnn.readNetFromDarknet(str(root/'model/tri2.cfg'),str(root/'tri2-80k.weights'));net.enableFusion(fusion);names=net.getLayerNames();net.setInput(np.full((1,1,128,1024),.5,dtype=np.float32))
 for index in [0,1,2,3,10,len(names)//2,len(names)-1]:
  value=net.forward(names[index]);row={'fusion':fusion,'layer_index':index,'name':names[index],'shape':list(value.shape),'finite':bool(np.isfinite(value).all()),'nonfinite':int(np.sum(~np.isfinite(value)))};print(row,flush=True);report.append(row)
Path('work/open-hat/yodo-numerical-diagnostic.json').write_text(json.dumps(report,indent=2))
