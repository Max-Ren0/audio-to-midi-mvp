from pathlib import Path
import sys,numpy as np,json
sys.path.insert(0,str(Path('work/drums-v2/yodo-deps').resolve()));import cv2
r=Path('work/drums-v2/yodo');net=cv2.dnn.readNetFromDarknet(str(r/'model/tri2.cfg'),str(r/'tri2-80k.weights'))
count=0;bad=[]
for name in net.getLayerNames():
 layer=net.getLayer(net.getLayerId(name));count+=sum(b.size for b in layer.blobs)
 if layer.type=='BatchNorm':
  bad.append({'name':name,'blob_shapes':[list(b.shape) for b in layer.blobs],'variance_min':float(layer.blobs[1].min()),'negative_variance':int(np.sum(layer.blobs[1]<0))})
print('file floats',(r/'tri2-80k.weights').stat().st_size//4-5,'loaded blobs',count,'difference',(r/'tri2-80k.weights').stat().st_size//4-5-count)
print(bad[:5])
Path('work/open-hat/yodo-weight-layout.json').write_text(json.dumps({'file_float_count':(r/'tri2-80k.weights').stat().st_size//4-5,'loaded_float_count':count,'batchnorm':bad},indent=2))
