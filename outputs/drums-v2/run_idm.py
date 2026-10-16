"""Fixed official IDM encoder transcription only; strict state loading; no reference."""
from pathlib import Path
import sys,json,hashlib,time
repo=Path('work/drums-v2/inverse-drum-machine-456656868538205ef756912c7cf5b0fd936de8af')
sys.path[:0]=[str(Path('work/drums-v2/idm-deps').resolve()),str(repo.resolve())]
import torch,numpy as np,soundfile as sf,torchaudio,yaml
from idm.feature_extractor.encoder import Encoder
from idm.feature_extractor.convnext import ConvNeXt
from idm.feature_extractor.mel import MelSpectrogram
from idm.synthesis_conditioning.embedding import DrumKitClassifier
from idm.synthesis_conditioning.transcription import TranscriptionHead

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
start=time.monotonic();torch.set_num_threads(2);torch.set_num_interop_threads(1)
source=Path(sys.argv[1]);out=Path(sys.argv[2]);assert not out.exists()
config=repo/'pretrained/idm-44-train-kits/checkpoints/model.yaml'
ckpt=repo/'pretrained/idm-44-train-kits/checkpoints/val-epoch=518-global_step=0.ckpt'
cfg=yaml.safe_load(config.read_text());ecfg=cfg['encoder']
def kwargs(d):return {k:v for k,v in d.items() if k!='_target_'}
head=kwargs(ecfg['transcription_head']);head['sequence_model']=torch.nn.Identity()
encoder=Encoder(backbone=ConvNeXt(**kwargs(ecfg['backbone'])),pooling=DrumKitClassifier(**kwargs(ecfg['pooling'])),transcription_head=TranscriptionHead(**head),transform=MelSpectrogram(**kwargs(ecfg['transform'])),sampling_rate=44100,embedding_norm=torch.nn.Softmax(dim=-1))
state=torch.load(ckpt,map_location='cpu',weights_only=False)['state_dict'];state={k[len('encoder.'):]:v for k,v in state.items() if k.startswith('encoder.')}
encoder.load_state_dict(state,strict=True);encoder.eval()
y,sr=sf.read(source,dtype='float32',always_2d=True);y=torch.from_numpy(y.mean(axis=1))
if sr!=44100:y=torchaudio.functional.resample(y,sr,44100)
with torch.inference_mode():
 result=encoder(y[None,None])
 onset=torch.sigmoid(result['activations']['onset'])[0].numpy();velocity=result['activations']['velocity'][0].numpy()
assert onset.shape==velocity.shape and onset.shape[0]==9 and np.isfinite(onset).all()
np.savez_compressed(out,onset_probs=onset,velocity=velocity)
report={'input_path':str(source),'input_sha256':sha(source),'model_sha256':sha(ckpt),'config_sha256':sha(config),'repo_revision':'456656868538205ef756912c7cf5b0fd936de8af','classes':list(cfg['train_classes']),'fps':result['activation_rate'],'duration_seconds':len(y)/44100,'shape':list(onset.shape),'max_probability_per_class':onset.max(axis=1).tolist(),'activation_sha256':sha(out),'script_sha256':sha(__file__),'reference_used':False,'elapsed_seconds':time.monotonic()-start}
out.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
