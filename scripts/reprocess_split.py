"""Experimental quality-first route. Run from the repository root.

Audio remains local. Default production transcribe limits are unchanged.
"""
import argparse
from dataclasses import asdict,replace
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import numpy as np
from audio_midi.audio import decode_mp3
from audio_midi.events import CATEGORIES,PROGRAMS,NoteEvent
from audio_midi.midi import write_midi
from audio_midi.render import render_midi
from audio_midi.stems import select_stem_notes,validate_stems,write_stem_receipt,verify_stem_receipt
from audio_midi.stitching import clean_notes
from audio_midi.worker import run_command


def main():
    p=argparse.ArgumentParser(description='Quality-first local stem experiment; not a validated release')
    p.add_argument('input',type=Path);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--stems',type=Path,help='Reuse known local Demucs stems; duration checked')
    p.add_argument('--separation-python',type=Path,default=Path('work/sep-env/bin/python'))
    p.add_argument('--checkpoint',type=Path,default=Path('work/models/yourmt3.ckpt'))
    p.add_argument('--soundfont',type=Path,default=Path('work/models/GeneralUser-GS.sf2'))
    p.add_argument('--quality-timeout-seconds',type=int,default=900)
    a=p.parse_args();start=time.monotonic();deadline=start+a.quality_timeout_seconds
    audio=decode_mp3(a.input,16000)
    if a.output_dir.exists():raise FileExistsError('输出目录已存在，请指定新目录，未覆盖')
    scratch=Path('work/quality')/str(time.time_ns());scratch.mkdir(parents=True)
    with a.input.open('rb') as f:
        input_hash=hashlib.file_digest(f,'sha256').hexdigest()
    runs={}
    if a.stems:
        stems=a.stems
        receipt=verify_stem_receipt(stems,input_hash)
    else:
        os.environ['TORCH_HOME']=str(Path('work/models/demucs').resolve())
        command=[str(a.separation_python.resolve()),'-m','demucs.separate','-n','htdemucs_6s','-d','cpu','--shifts','1','--segment','6','--overlap','.25','--float32','-o',str(scratch/'stems'),str(a.input.resolve())]
        result=run_command(command,deadline,scratch/'separation.log',6*1024**3)
        runs['separation']=asdict(result)
        stems=scratch/'stems'/'htdemucs_6s'/a.input.stem
        receipt=write_stem_receipt(stems,input_hash,{'model':'htdemucs_6s','segment':6,'overlap':.25,'shifts':1,'device':'cpu'})
    validate_stems(stems,audio.duration_seconds)
    dsp=scratch/'dsp.json'
    result=run_command([sys.executable,'-m','audio_midi.stems',str(stems.resolve()),str(dsp.resolve())],deadline,scratch/'dsp.log',4*1024**3)
    runs['dsp']=asdict(result)
    data=json.loads(dsp.read_text());notes=[NoteEvent(**n) for n in data['notes']];details={}
    import soundfile as sf
    from scipy.signal import resample_poly
    from math import gcd
    for name in ('guitar','drums','other'):
        print('transcribing',name,flush=True)
        y,sr=sf.read(stems/f'{name}.wav',dtype='float32',always_2d=True);y=y.mean(axis=1)
        factor=gcd(sr,16000);y=resample_poly(y,16000//factor,sr//factor).astype('float32')
        source=scratch/f'{name}.npy';np.save(source,y);raw=scratch/f'{name}.json'
        result=run_command([sys.executable,'-m','audio_midi.backends.selected',str(source.resolve()),str(a.checkpoint.resolve()),str(raw.resolve()),'--device','cpu'],deadline,scratch/f'{name}.log',int(3.2*1024**3))
        runs[name]=asdict(result)
        output=json.loads(raw.read_text());prediction=[NoteEvent(**n) for n in output.pop('notes')]
        selected=select_stem_notes(prediction,name)
        notes.extend(selected);details[name]=output|{'raw_notes':len(prediction),'selected_notes':len(selected)}
    notes=clean_notes(notes,audio.duration_seconds)
    if not notes:raise ValueError('没有可用音符')
    counts={c:sum(n.category==c for n in notes) for c in CATEGORIES}
    # Publish only once all note stages succeeded; no stage is silently omitted.
    staging=scratch/'artifacts';staging.mkdir()
    midi=staging/'不将就_多乐器.mid';write_midi(notes,midi)
    rendered=render_midi(midi,a.soundfont,staging/'不将就_音色试听.wav')
    melody=[replace(n,category='piano',program=0) for n in notes if n.category=='vocal']
    if melody:
        lead=staging/'不将就_主旋律钢琴.mid';write_midi(melody,lead)
        render_midi(lead,a.soundfont,staging/'不将就_主旋律钢琴试听.wav')
    result={'status':'experimental_unvalidated','input_duration_seconds':audio.duration_seconds,
      'input_sha256':hashlib.file_digest(a.input.open('rb'),'sha256').hexdigest(),
      'route':'Demucs6s separation + pYIN vocal/bass + BasicPitch piano + YourMT3 guitar/drums/strings',
      'quality_priority_user_authorized':True,'total_seconds':time.monotonic()-start,'stems_reused':bool(a.stems),'separation_provenance':receipt,
      'category_counts':counts,'missing_categories':[c for c in CATEGORIES if not counts[c]],
      'programs_zero_based':PROGRAMS,'notes':[asdict(n) for n in notes],
      'runs':runs,'dsp':{k:v for k,v in data.items() if k!='notes'},'mt3_stems':details,
      'render':rendered,'soundfont_sha256':hashlib.file_digest(a.soundfont.open('rb'),'sha256').hexdigest(),
      'quality_metrics':None,'warnings':['未经人工标注，不报告准确率；仍需听辨验收','Demucs6s钢琴分离有已知串音风险','音色选择不能保证Logic自动加载具体内置插件','合唱音色只近似人声，未合成原唱声音'],
      'scratch':str(scratch)}
    if 0<counts['electric_guitar']<3:
        result['warnings'].append('电吉他候选音符过少，类别证据不足，未经人工确认')
    (staging/'转录报告.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    a.output_dir.parent.mkdir(parents=True,exist_ok=True)
    os.rename(staging,a.output_dir)
    print(json.dumps({k:v for k,v in result.items() if k not in ('notes','mt3_stems')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
