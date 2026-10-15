"""Quality-first stem transcription building blocks (experimental)."""
from dataclasses import asdict
import json
from pathlib import Path
from .events import NoteEvent


def select_stem_notes(notes: list[NoteEvent], stem: str) -> list[NoteEvent]:
    categories={'guitar':{'acoustic_guitar','electric_guitar'},'drums':{'drums'},'other':{'strings'}}[stem]
    return [n for n in notes if n.category in categories and (n.category!='drums' or 35<=n.pitch<=81)]


def validate_stems(root: Path, duration: float) -> None:
    import soundfile as sf
    for name in ('vocals','bass','piano','guitar','drums','other'):
        info=sf.info(root/f'{name}.wav')
        if abs(info.frames/info.samplerate-duration)>.05:
            raise ValueError(f'{name}分轨时间线与输入不一致')


def _stem_hashes(root: Path) -> dict:
    import hashlib
    result={}
    for name in ('vocals','bass','piano','guitar','drums','other'):
        with (root/f'{name}.wav').open('rb') as f:
            result[name]=hashlib.file_digest(f,'sha256').hexdigest()
    return result


def write_stem_receipt(root: Path, input_sha256: str, configuration: dict) -> dict:
    result={'input_sha256':input_sha256,'stem_sha256':_stem_hashes(root),'configuration':configuration}
    (root/'separation-receipt.json').write_text(json.dumps(result,indent=2))
    return result


def verify_stem_receipt(root: Path, input_sha256: str) -> dict:
    receipt=json.loads((root/'separation-receipt.json').read_text())
    if receipt['input_sha256']!=input_sha256 or receipt['stem_sha256']!=_stem_hashes(root):
        raise ValueError('分离音频与输入来源或文件哈希不符，不复用')
    return receipt


def transcribe_dsp(stem_root: Path, output: Path) -> None:
    from .contour import transcribe_monophonic
    from basic_pitch.inference import Model,predict
    from basic_pitch import build_icassp_2022_model_path,FilenameSuffix
    import onnxruntime as ort
    import time
    notes=[];timings={}
    for category,stem in [('vocal','vocals'),('bass','bass')]:
        start=time.monotonic()
        result=transcribe_monophonic(stem_root/f'{stem}.wav',category)
        print(category,len(result),flush=True)
        notes.extend(result);timings[category]=time.monotonic()-start
    # The standard constructor creates an unbounded ORT thread pool. Override
    # only initialization, keeping Spotify's documented predict interface.
    class LimitedONNX(Model):
        def __init__(self):
            self.model_type=Model.MODEL_TYPES.ONNX
            options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
            self.model=ort.InferenceSession(str(build_icassp_2022_model_path(FilenameSuffix.onnx)),sess_options=options,providers=['CPUExecutionProvider'])
    start=time.monotonic()
    _,_,events=predict(stem_root/'piano.wav',model_or_model_path=LimitedONNX(),onset_threshold=.65,frame_threshold=.4,minimum_note_length=120,minimum_frequency=65,maximum_frequency=2093,multiple_pitch_bends=False)
    piano=[NoteEvent('piano',int(p),float(a),float(b),None,0) for a,b,p,amplitude,bends in events if amplitude>=.3]
    notes.extend(piano);timings['piano']=time.monotonic()-start
    print('piano',len(piano),flush=True)
    output.write_text(json.dumps({'notes':[asdict(n) for n in notes],'timings':timings,'algorithms':{'vocal':'pYIN isolated-vocals monophonic','bass':'pYIN isolated-bass monophonic','piano':'BasicPitch0.4 ONNX isolated-piano'}}))

if __name__=='__main__':
    import sys
    transcribe_dsp(Path(sys.argv[1]),Path(sys.argv[2]))
