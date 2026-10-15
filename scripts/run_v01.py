"""Reference-free local v0.1 runner. MIDI references belong only in evaluate_v01.py."""
import argparse
from dataclasses import asdict
import hashlib,json,os,sys,time
from pathlib import Path
import numpy as np
from audio_midi.audio import decode_mp3
from audio_midi.events import NoteEvent
from audio_midi.quality import INSTRUMENTS,assemble,load_sources
from audio_midi.midi import write_midi
from audio_midi.render import render_midi
from audio_midi.worker import run_command
from audio_midi.stems import verify_stem_receipt,write_stem_receipt,validate_stems


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path);p.add_argument('--config',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--candidates',type=Path,help='Reconstruct from an explicitly hash-bound prior candidate manifest')
    p.add_argument('--stems',type=Path);p.add_argument('--specialist-python',type=Path,default=Path('work/sep-env/bin/python'))
    p.add_argument('--checkpoint',type=Path,default=Path('work/models/yourmt3.ckpt'));p.add_argument('--soundfont',type=Path,default=Path('work/models/GeneralUser-GS.sf2'))
    p.add_argument('--timeout',type=float,default=1800);p.add_argument('--solo',action='store_true')
    a=p.parse_args();start=time.monotonic();deadline=start+a.timeout
    if a.output_dir.exists():raise FileExistsError('Output already exists; preserving it')
    data=json.loads(a.config.read_text());routes=data['routes']
    if set(routes)!=set(INSTRUMENTS):raise ValueError('Config must explicitly cover six instrumental categories')
    audio=decode_mp3(a.input,16000);input_hash=sha(a.input)
    scratch=Path('work/v01/runtime')/str(time.time_ns());scratch.mkdir(parents=True)
    stats={};receipt=None
    def run(cmd,name,memory=6*1024**3):
        result=run_command(cmd,deadline,scratch/f'{name}.log',memory);stats[name]=asdict(result)
    def model_audio(path):
        import soundfile as sf
        from scipy.signal import resample_poly
        from math import gcd
        y,sr=sf.read(path,dtype='float32',always_2d=True);g=gcd(sr,16000)
        return resample_poly(y.mean(axis=1),16000//g,sr//g).astype('float32')
    if a.candidates:
        sources=load_sources(a.candidates,input_hash)
        provenance={'mode':'hash_bound_candidate_reconstruction','manifest_sha256':sha(a.candidates),'manifest':json.loads(a.candidates.read_text())}
    else:
        required=set(routes.values());sources={}
        if required-{'mix'}:
            if a.stems:
                stems=a.stems;receipt=verify_stem_receipt(stems,input_hash)
            else:
                os.environ['TORCH_HOME']=str(Path('work/models/demucs').resolve())
                run([str(a.specialist_python.absolute()),'-m','demucs.separate','-n','htdemucs_6s','-d','cpu','--shifts','1','--segment','6','--overlap','.25','--float32','-o',str(scratch/'stems'),str(a.input.absolute())],'separation')
                stems=scratch/'stems'/'htdemucs_6s'/a.input.stem
                receipt=write_stem_receipt(stems,input_hash,{'model':'htdemucs_6s','device':'cpu','segment':6,'overlap':.25,'shifts':1})
            validate_stems(stems,audio.duration_seconds)
        for name in sorted(required):
            print('stage',name,flush=True)
            if name in ('mix','guitar','strings','drums_mt3'):
                y=audio.samples if name=='mix' else model_audio(stems/f"{dict(guitar='guitar',strings='other',drums_mt3='drums')[name]}.wav")
                src=scratch/f'{name}.npy';np.save(src,y);dest=scratch/f'{name}.json'
                run([sys.executable,'-m','audio_midi.backends.selected',str(src.absolute()),str(a.checkpoint.absolute()),str(dest.absolute()),'--device','cpu'],name,int(3.2*1024**3))
                sources[name]=[NoteEvent(**n) for n in json.loads(dest.read_text())['notes']]
            elif name in ('piano','drums','bass_bp'):
                model={'piano':'transkun','drums':'adtof','bass_bp':'basicpitch-bass'}[name]
                stem={'piano':'piano','drums':'drums','bass_bp':'bass'}[name]
                dest=scratch/f'{name}.{ "json" if name=="bass_bp" else "mid"}'
                py=sys.executable if name=='bass_bp' else str(a.specialist_python.absolute())
                run([py,'scripts/transcribe_specialist.py',model,str(stems/f'{stem}.wav'),str(dest)],name)
                if name=='bass_bp':sources[name]=[NoteEvent(**n) for n in json.loads(dest.read_text())['notes']]
                else:
                    from audio_midi.quality import read_notes
                    sources[name]=read_notes(dest)
            elif name=='bass':
                dest=scratch/'bass.json'
                run([sys.executable,'-c',"from audio_midi.contour import transcribe_monophonic;from dataclasses import asdict;import json,sys;from pathlib import Path;Path(sys.argv[2]).write_text(json.dumps({'notes':[asdict(n) for n in transcribe_monophonic(Path(sys.argv[1]),'bass')]}))",str(stems/'bass.wav'),str(dest)],name)
                sources[name]=[NoteEvent(**n) for n in json.loads(dest.read_text())['notes']]
            else:raise ValueError(f'Unknown source: {name}')
        provenance={'mode':'fresh_inference','separation_receipt':receipt}
    notes=assemble(sources,routes,audio.duration_seconds)
    if not notes:raise ValueError('No notes produced')
    staging=scratch/'delivery';staging.mkdir()
    midi=staging/'多乐器.mid';write_midi(notes,midi)
    # Explicitly retain the input excerpt length, including any trailing silence.
    import mido
    mf=mido.MidiFile(midi);mf.tracks[0].append(mido.MetaMessage('end_of_track',time=round(audio.duration_seconds*960)));mf.save(midi)
    rendered=render_midi(midi,a.soundfont,staging/'音色试听.wav')
    if a.solo:
        solo=staging/'单轨';solo.mkdir()
        for category in INSTRUMENTS:
            group=[n for n in notes if n.category==category]
            if group:
                path=solo/f'{category}.mid';write_midi(group,path);render_midi(path,a.soundfont,solo/f'{category}.wav')
    report={'version':data.get('version','0.1.0rc1'),'quality_status':'experimental_pending_evaluation','input_sha256':input_hash,'input_duration_seconds':audio.duration_seconds,'config_sha256':sha(a.config),'routes':routes,'notes':[asdict(n) for n in notes],'counts':{c:sum(n.category==c for n in notes) for c in INSTRUMENTS},'runs':stats,'provenance':provenance,'runtime_seconds':time.monotonic()-start,'render':rendered,'soundfont_sha256':sha(a.soundfont),'midi_sha256':sha(midi),'scratch':str(scratch),'warnings':['No vocals are exported','MIDI contains instrument instructions, not samples','Default tempo120 and meter4/4 are encoding defaults, not detected','No reference MIDI is used by this runner','Reconstruction runtime excludes cached inference; consult stage receipts']}
    (staging/'运行报告.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    a.output_dir.parent.mkdir(parents=True,exist_ok=True);os.rename(staging,a.output_dir)
    print(json.dumps({k:v for k,v in report.items() if k not in ('notes','provenance')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
