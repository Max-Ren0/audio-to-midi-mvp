"""Official preprocessor impulse check; no model forward or weight loading."""
import torch,torchcrepe,penn,json
results={}
for name,sr in [('crepe',16000),('penn',8000)]:
 x=torch.zeros(1,sr*3);x[0,sr]=1
 if name=='crepe':frames=torch.cat(list(torchcrepe.preprocess(x,sr,sr//100,64,'cpu',True)),dim=0)
 else:frames=torch.cat(list(penn.preprocess(x,sr,.01,64,'zero')),dim=0)
 centers=[]
 for i,row in enumerate(frames):
  peak=int(row.reshape(-1).argmax())
  if abs(float(row.reshape(-1)[peak]))>0 and peak==512:centers.append(i)
 assert 100 in centers
 results[name]={'sample_rate':sr,'impulse_seconds':1,'native_frame_index':100,'frame_center_sample_in_window':512,'native_step':.01,'origin_seconds':0,'total_frames':len(frames),'forward_calls':0}
print(json.dumps(results,indent=2))
