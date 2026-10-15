"""Local specialist subprocess. No reference MIDI is accepted by this program."""
import argparse
from pathlib import Path
import torch

def main():
    p=argparse.ArgumentParser();p.add_argument('model',choices=('transkun','adtof'));p.add_argument('input',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();torch.set_num_threads(2);torch.set_num_interop_threads(1)
    if a.output.exists():raise FileExistsError(a.output)
    if a.model=='adtof':
        from adtof_pytorch import transcribe_to_midi
        transcribe_to_midi(str(a.input),str(a.output),device='cpu')
    else:
        import transkun, moduleconf, soundfile as sf, soxr
        from transkun.Data import writeMidi
        root=Path(transkun.__file__).parent/'pretrained'
        cm=moduleconf.parseFromFile(str(root/'2.0.conf'));model=cm['Model'].module.TransKun(conf=cm['Model'].config)
        ck=torch.load(root/'2.0.pt',map_location='cpu',weights_only=False)
        model.load_state_dict(ck.get('best_state_dict',ck.get('state_dict')),strict=True);model.eval()
        y,sr=sf.read(a.input,dtype='float32',always_2d=True)
        if sr!=model.fs:y=soxr.resample(y,sr,model.fs)
        with torch.inference_mode():notes=model.transcribe(torch.from_numpy(y),discardSecondHalf=False)
        writeMidi(notes).write(str(a.output))

if __name__=='__main__':main()
