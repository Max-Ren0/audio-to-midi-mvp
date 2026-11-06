"""Experimental local MuScriptor medium inference and Noto MIDI track replacement."""
import argparse, hashlib, json, os, subprocess, tempfile, time
from pathlib import Path
import mido
import soundfile as sf
from audio_midi.muscriptor_routing import parse_note_lines, replace_midi_tracks

ENGINE_SHA='6a9c98a1fc5d98b276bdc9e2f1fed986080057dbb5ace0566aab92c681355b00'
MODEL_SHA='3850cc9e5b436b17a09bd25b8f2615cb3366ab96a71e7b50f73a793a917fdf03'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audio',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--baseline-audio-sha256',required=True,help='SHA256 of source audio used to generate baseline')
    p.add_argument('--engine',type=Path,default=Path('work/muscriptor-comparison-engine/build/bench/muscriptor_bench'))
    p.add_argument('--weights',type=Path,default=Path.home()/'Library/NeuralNote/models/muscriptor-medium-f16.gguf')
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--timeout',type=int,default=3600)
    a=p.parse_args()
    if a.output_dir.exists():raise FileExistsError(a.output_dir)
    if sha(a.audio)!=a.baseline_audio_sha256.lower():raise ValueError('Audio SHA does not match baseline source')
    if sha(a.engine)!=ENGINE_SHA or sha(a.weights)!=MODEL_SHA:raise ValueError('Engine or model hash mismatch')
    # The 120-BPM Noto MIDI is supported by replace_midi_tracks; others fail closed.
    start=time.monotonic();a.output_dir.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='muscriptor-input-',dir=a.output_dir) as temp:
        wav=Path(temp)/'input.wav'
        subprocess.run(['ffmpeg','-v','error','-nostdin','-threads','2','-i',str(a.audio),'-vn','-ac','1','-ar','16000','-c:a','pcm_f32le',str(wav)],check=True,timeout=a.timeout)
        info=sf.info(wav);duration=info.frames/info.samplerate
        midi_length=mido.MidiFile(a.baseline).length
        if abs(midi_length-duration)>.1:raise ValueError(f'Baseline and audio lengths differ: {midi_length} vs {duration}')
        log=a.output_dir/'muscriptor.log'
        env=os.environ.copy();env['OMP_NUM_THREADS']='2';env['OPENBLAS_NUM_THREADS']='2'
        with log.open('x') as f:
            subprocess.run([str(a.engine.resolve()),'--transcribe','--weights',str(a.weights.resolve()),'--audio',str(wav.resolve()),'--device','cpu','--threads','2'],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=a.timeout,env=env)
        notes=parse_note_lines(log.read_text());out=a.output_dir/'Noto-MuScriptor贝斯鼓.mid'
        replace_midi_tracks(a.baseline,notes,out,duration)
    receipt={'audio_sha256':sha(a.audio),'baseline_midi_sha256':sha(a.baseline),'engine_sha256':sha(a.engine),'weights_sha256':sha(a.weights),'raw_log_sha256':sha(log),'output_sha256':sha(out),'duration_seconds':duration,'elapsed_seconds':time.monotonic()-start,'conditioning':['AcousticPiano','AcousticGuitar','CleanElectricGuitar','ElectricBass','StringEnsemble','Drums'],'device':'cpu','threads':2,'caveats':['No predicted velocity; fixed MIDI velocity 80','Requires baseline and audio share the same timeline; hash is user-supplied provenance, not independent proof','MuScriptor weights CC BY-NC 4.0; non-commercial use']}
    (a.output_dir/'运行报告.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False))
if __name__=='__main__':main()
