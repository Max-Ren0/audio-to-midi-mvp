"""Local specialist subprocess. No reference MIDI is accepted by this program."""
import argparse
from pathlib import Path
import torch

def main():
    p=argparse.ArgumentParser();p.add_argument('model',choices=('transkun','adtof','basicpitch-bass'));p.add_argument('input',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--threads', type=int, choices=[1, 2], default=2)
    a=p.parse_args();torch.set_num_threads(a.threads);torch.set_num_interop_threads(1)
    if a.output.exists():raise FileExistsError(a.output)
    if a.model=='basicpitch-bass':
        import json
        import onnxruntime as ort
        from basic_pitch.inference import Model,predict
        from basic_pitch import build_icassp_2022_model_path,FilenameSuffix
        class Limited(Model):
            def __init__(self):
                self.model_type=Model.MODEL_TYPES.ONNX
                options=ort.SessionOptions();options.intra_op_num_threads=a.threads;options.inter_op_num_threads=1
                self.model=ort.InferenceSession(str(build_icassp_2022_model_path(FilenameSuffix.onnx)),sess_options=options,providers=['CPUExecutionProvider'])
        _,_,events=predict(a.input,model_or_model_path=Limited(),onset_threshold=.5,frame_threshold=.3,minimum_note_length=120,minimum_frequency=30,maximum_frequency=261,multiple_pitch_bends=False)
        notes=[dict(category='bass',pitch=int(p),onset=float(t),offset=float(end),velocity=None,program=33) for t,end,p,amp,bends in events if amp>=.2]
        a.output.write_text(json.dumps({'notes':notes}))
    elif a.model=='adtof':
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
