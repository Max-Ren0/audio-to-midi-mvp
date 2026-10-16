"""CPU YODO adapter: pinned source, OpenCV detector and equivalent FFT superlets.
No reference MIDI, no manual note insertion or GM pitch substitution.
"""
from pathlib import Path
import sys,time,json,hashlib,importlib.util
sys.path.insert(0,str(Path('work/drums-v2/yodo-deps').resolve()))
import cv2,numpy as np,soundfile as sf
from scipy.signal import oaconvolve,correlate2d
from audio_midi.drums import detection_region

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=Path(sys.argv[1]);out=Path(sys.argv[2]);root=Path('work/drums-v2/yodo')
if out.exists():raise FileExistsError(out)
cv2.setNumThreads(2);start=time.monotonic()
spec=importlib.util.spec_from_file_location('yodo_superlets',root/'spectrogram.py');sp=importlib.util.module_from_spec(spec);spec.loader.exec_module(sp)
# Match original sliding-dot convention, including its exclusive final frame.
original=sp._conv

def fast_conv(arr,kernel,stride):
 n=(len(arr)-len(kernel))//stride
 return oaconvolve(np.asarray(arr,dtype=np.float64),np.asarray(kernel)[::-1],mode='valid')[::stride][:n]
rng=np.random.default_rng(451)
errors=[]
for length,stride in [(101,17),(250,23),(501,41)]:
 x=rng.normal(size=6000).astype(np.float32);k=rng.normal(size=length)+1j*rng.normal(size=length)
 a=original(x,k,stride);b=fast_conv(x,k,stride);errors.append(float(np.max(np.abs(a-b))))
 assert np.allclose(a,b,atol=1e-8,rtol=1e-8)
sp._conv=fast_conv
net=cv2.dnn.readNetFromDarknet(str(root/'model/tri2.cfg'),str(root/'tri2-80k.weights'))
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV);net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
y,sr=sf.read(source,dtype='float32',always_2d=True);y=y.mean(axis=1)
if sr!=44100:raise ValueError('Expected44100Hz')
peak=float(np.max(np.abs(y)))
if peak>1:y=y/peak
foi=sp.generate_foi();orders=np.round(np.linspace(1,10,len(foi)),0);slt=sp.Superlets(sr,foi,3,orders)
images=[]
for begin in range(0,len(y),30*sr):
 power=sp.faslt(y[begin:begin+30*sr],orders,slt,100)[0]
 db=10*np.log10(np.maximum(1e-10,power));span=float(db.max()-db.min())
 images.append((db-db.min())/span if span>0 else np.zeros_like(db))
image=(np.hstack(images)*255).astype('uint8');height,width=image.shape
print('spectrogram',image.shape,'elapsed',time.monotonic()-start,flush=True)
rects=[]
for begin in range(0,width,924):
 end=min(begin+1024,width);actual_width=end-begin
 patch=cv2.resize(image[:,begin:end],(1024,128))
 blob=cv2.dnn.blobFromImage(patch,1/255.,(1024,128),swapRB=False,crop=False);net.setInput(blob)
 results=net.forward(net.getUnconnectedOutLayersNames())
 for row in np.concatenate(results):
  c=int(np.argmax(row[5:]));confidence=float(row[5+c])
  if confidence<.20:continue
  x1,x2,y1,y2=detection_region(tuple(float(v) for v in row[:4]),begin,actual_width,height)
  if x2<=x1 or y2<=y1:continue
  rects.append({'class':c,'confidence':confidence,'region':[x1,x2,y1,y2]})
 if end==width:break
# Per-class NMS in original time/frequency coordinates, as opposed to across instruments.
kept=[]
for c in range(11):
 group=[r for r in rects if r['class']==c]
 boxes=[[r['region'][0],r['region'][2],r['region'][1]-r['region'][0],r['region'][3]-r['region'][2]] for r in group]
 if not boxes:continue
 ix=cv2.dnn.NMSBoxes(boxes,[r['confidence'] for r in group],.20,.45)
 kept.extend(group[int(i)] for i in np.asarray(ix).reshape(-1))
templates=[]
for c in range(11):
 im=cv2.imread(str(root/'templates'/f'{c}.png'),cv2.IMREAD_UNCHANGED)
 templates.append((im if im.ndim==2 else im[:,:,2]).astype(float)/255.)
templates[10]=np.maximum(templates[10]-templates[0],0)
widths=[28,21,17,95,104,94,15,22,14,32,60]
templates=[t[:,:w] for t,w in zip(templates,widths)]
masks=[(t>=.4).astype(float) for t in templates]
A=[.46,3.02,9.14,4.87,14.09,4.67,14.49,7.01,9.78,9.23,5.21]
B=[1290.06,187.41,85.18,110.87,22.13,113.53,52.11,294.61,103.04,97.75,193.98]
pitches=[35,40,37,48,45,43,42,46,51,53,49];methods=[2,1,1,1,1,1,1,1,2,2,2]
padded=np.zeros((height,width+110));padded[:,5:-105]=image
notes=[]
for r in kept:
 c=r['class'];x1,_,y1,y2=r['region'];template=templates[c];tw=template.shape[1]
 if x1+tw+5>=width:continue
 patch=padded[y1:y2,x1:x1+tw+5];target=template[y1:y2]
 if not patch.size or target.shape[0]==0:continue
 conv=correlate2d(patch,target,mode='valid')[0];onset=x1+int(np.argmax(conv))
 mask=target if methods[c]==1 else masks[c][y1:y2]
 loudness=float(np.max(padded[y1:y2,onset:onset+tw]*mask))/255.
 velocity=max(1,min(127,int(A[c]*B[c]**loudness)))
 notes.append({'category':'drums','pitch':pitches[c],'onset':onset/100.,'offset':onset/100.+.1,'velocity':velocity,'program':0,'confidence':r['confidence'],'class':c})
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps({'notes':notes,'detections':kept,'author_thresholds':[.65,.70,.68,.78,.82,.72,.52,.67,.60,.41,.79],'pitches':pitches,'input_sha256':sha(source),'weight_sha256':sha(root/'tri2-80k.weights'),'code_commit':'0cb980a11e9ba1a37cbafddec1e85c66d8ffa236','adapter':'OpenCV4.11 CPU; FFT equivalent sliding dot; correct short final-patch geometry; author templates and velocity, no reference','opencv':cv2.__version__,'fft_max_abs_errors':errors,'source_code_hashes':{p.name:sha(p) for p in [root/'spectrogram.py',root/'model/tri2.cfg',root/'model/classes.names']},'template_hashes':{p.name:sha(p) for p in sorted((root/'templates').glob('*.png'))},'script_sha256':sha(__file__),'duration_seconds':len(y)/sr,'elapsed_seconds':time.monotonic()-start,'reference_used':False},indent=2));print('complete',len(notes),time.monotonic()-start,flush=True)
