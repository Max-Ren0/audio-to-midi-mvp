"""Approved fixed piano-B pipeline. No reference, model-selection or fallback option."""
import argparse,json,os,sys,time,subprocess
from dataclasses import asdict
from pathlib import Path
from audio_midi.piano_lock import digest,verify_assets,verify_piano_cache
from audio_midi.audio import decode_mp3
from audio_midi.quality import read_notes
from audio_midi.stitching import clean_notes
from audio_midi.midi import write_midi
from audio_midi.render import render_midi
from audio_midi.worker import run_command


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--stems',type=Path,help='Optional hash-bound SW cache for this exact input')
    p.add_argument('--threads', type=int, choices=[1, 2])
    a=p.parse_args();a.input=a.input.resolve();a.output_dir=a.output_dir.resolve()
    if a.stems:a.stems=a.stems.resolve()
    if a.output_dir.exists():raise FileExistsError('Output exists; preserving it')
    root=Path(__file__).resolve().parents[1];os.chdir(root)
    lock_path=root/'config/piano-b.lock.json';lock=json.loads(lock_path.read_text())
    threads = a.threads if a.threads is not None else lock['cpu_threads']
    if lock['pipeline']!=['bs-roformer-sw','transkun-2.0'] or lock['automatic_fallback'] is not False:
        raise ValueError('Unsupported piano route; B must stay locked')
    verify_assets(root,lock)
    source=root/'work/two-methods/msst'
    revision=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if revision!=lock['msst_commit'] or subprocess.run(['git','-C',str(source),'diff','--quiet','HEAD']).returncode:
        raise ValueError('Pinned SW source mismatch')
    specialist=root/'work/sep-env/bin/python'
    version=subprocess.check_output([str(specialist),'-c',"import importlib.metadata as m;print(m.version('transkun'))"],text=True).strip()
    if version!=lock['transkun_package_version']:raise ValueError('Pinned Transkun package mismatch')
    audio=decode_mp3(a.input,16000);input_hash=digest(a.input)
    scratch=root/'work/piano-b'/str(time.time_ns());scratch.mkdir(parents=True)
    start=time.monotonic();runs={}
    def run(cmd,name):
        runs[name]=asdict(run_command(cmd,time.monotonic()+1800,scratch/f'{name}.log',6*1024**3,threads=threads))
    if a.stems:
        stems=a.stems
    else:
        from audio_midi.stems import write_stem_receipt
        wav=scratch/'input.wav';stems=scratch/'sw'
        run(['ffmpeg','-v','error','-nostdin','-threads',str(threads),'-i',str(a.input),'-vn','-ac','2','-ar','44100','-c:a','pcm_f32le',str(wav)],'decode')
        run([str(specialist),str(root/lock['model_assets']['sw_wrapper']['path']),str(wav),str(stems),str(audio.duration_seconds),str(threads)],'sw_separation')
        write_stem_receipt(stems,input_hash,{'model':'locked BS-Roformer-SW','original_input_sha256':input_hash,'source_wav_sha256':digest(wav),'upstream_receipt_sha256':digest(stems/'receipt.json'),'decoder':'FFmpeg 44100 stereo full input; no trim'})
    piano=verify_piano_cache(stems,input_hash,{**lock, 'cpu_threads': threads})
    import soundfile as sf
    info=sf.info(piano)
    if info.samplerate!=44100 or info.channels!=2 or abs(info.duration-audio.duration_seconds)>.05:
        raise ValueError('Piano stem timeline/format mismatch')
    raw=scratch/'transkun.mid'
    run([str(specialist),'scripts/transcribe_specialist.py','transkun',str(piano),str(raw),'--threads',str(threads)],'transkun')
    raw_notes=read_notes(raw)
    if any(n.category!='piano' for n in raw_notes):raise ValueError('Unexpected piano backend category')
    notes=clean_notes(raw_notes,audio.duration_seconds)
    stage=scratch/'delivery';stage.mkdir();mid=stage/'钢琴-B.mid';write_midi(notes,mid)
    import mido
    mf=mido.MidiFile(mid);mf.tracks[0].append(mido.MetaMessage('end_of_track',time=round(audio.duration_seconds*960)));mf.save(mid)
    render=render_midi(mid,root/'work/models/GeneralUser-GS.sf2',stage/'钢琴-B试听.wav')
    report={'version':lock['version'],'route':lock['pipeline'],'input_sha256':input_hash,'duration_seconds':audio.duration_seconds,'lock_sha256':digest(lock_path),'lock':lock,'piano_stem_sha256':digest(piano),'separation_receipt_sha256':digest(stems/'separation-receipt.json'),'separation_cache_reused':bool(a.stems),'raw_midi_sha256':digest(raw),'midi_sha256':digest(mid),'notes':len(notes),'runs':runs,'scratch':str(scratch),'elapsed_seconds':time.monotonic()-start,'render':render,'soundfont_sha256':digest(root/'work/models/GeneralUser-GS.sf2'),'warnings':['MIDI contains GM instructions, not sampled sound','Default120BPM/4-4, not detected','Cached run timing excludes separation','No reference MIDI or automatic alternative route']}
    report['cpu_threads'] = threads
    (stage/'运行报告.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    a.output_dir.parent.mkdir(parents=True,exist_ok=True);os.rename(stage,a.output_dir)
    print(json.dumps({'output':str(a.output_dir),'notes':len(notes),'runs':runs},ensure_ascii=False))


if __name__=='__main__':main()
