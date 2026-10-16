"""Stage generation from audio/pitch evidence. Never reads reference MIDI."""
import argparse,json,hashlib
from pathlib import Path
from dataclasses import asdict
import numpy as np,librosa,soundfile as sf
from audio_midi.bass_models import nearest_grid,frequency_to_midi
from audio_midi.bass_refinement import extend_confidence,bounded_backtrack,attack_led_notes
from audio_midi.stitching import clean_notes
from audio_midi.midi import write_midi

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
ROOT=Path('outputs/bass-models');WORK=Path('work/bass-models')
def original():
 meta=json.loads(Path('work/bass-diagnostics/replay/trace.json').read_text())
 assert sha(meta['input_path'])==meta['input_sha256']==json.loads((ROOT/'实验登记.json').read_text())['input_sha256']
 manifest=json.loads(Path('outputs/bass-diagnostics/来源与产物校验.json').read_text())
 for rel in ['work/bass-diagnostics/replay/frames.npz','work/bass-diagnostics/replay/trace.json']:
  assert sha(rel)==next(x['sha256'] for x in manifest['files'] if x['path']==rel)
 with np.load('work/bass-diagnostics/replay/frames.npz') as z:a={k:z[k] for k in z.files}
 assert sha(meta['stem_path'])==meta['stem_sha256']
 return meta,a

def features(source,model):
 meta,old=original()
 wave=Path(meta['stem_path']) if source=='demucs' else WORK/'ft-bass.wav' if source=='ft' else Path('work/two-methods/sw-full/bass.wav')
 if source=='sw':
  receipt=json.loads(Path('work/two-methods/sw-full/separation-receipt.json').read_text())
  assert receipt['input_sha256']==meta['input_sha256'] and receipt['stem_sha256']['bass']==sha(wave)
 if source=='ft':
  receipt=json.loads((WORK/'ft-receipt.json').read_text());assert receipt['input_sha256']==meta['input_sha256'] and receipt['bass_sha256']==sha(wave)
 y,sr=sf.read(wave,dtype='float32',always_2d=True);duration=len(y)/sr
 y=librosa.resample(y.mean(axis=1),orig_sr=sr,target_sr=8000)
 short=librosa.onset.onset_strength(y=y,sr=8000,hop_length=32,n_fft=512,n_mels=64,fmin=30,fmax=2000)
 short_onsets=librosa.onset.onset_detect(onset_envelope=short,sr=8000,hop_length=32,units='time')
 if source=='demucs':
  rms=old['rms'];onsets=old['onsets_seconds'];env=old['onset_strength'];count=len(rms)
 else:
  rms=librosa.feature.rms(y=y,frame_length=2048,hop_length=128)[0];count=len(rms)
  onsets=librosa.onset.onset_detect(y=y,sr=8000,hop_length=128,units='time')
  env=librosa.onset.onset_strength(y=y,sr=8000,hop_length=128)
 if model=='pyin' and source=='demucs':raw=old['raw_pitches'];q=old['probability'];voiced=old['voiced'];pitchfile=Path('work/bass-diagnostics/replay/frames.npz');indices=np.arange(count)
 elif model=='pyin':
  pitchfile=WORK/f'pyin-{source}.npz'
  rec=json.loads(pitchfile.with_suffix('.json').read_text());assert rec['source_audio_sha256']==sha(wave) and rec['output_sha256']==sha(pitchfile)
  with np.load(pitchfile) as z:raw=z['raw_pitches'];q=z['probability'];voiced=z['voiced'];assert len(raw)==count
 else:
  pitchfile=WORK/f'{model}-full.npz' if source=='demucs' else WORK/f'{model}-{source}.npz'
  rec=json.loads(pitchfile.with_suffix('.json').read_text());assert rec['source_audio_sha256']==sha(wave) and rec['output_sha256']==sha(pitchfile)
  with np.load(pitchfile) as z:f,q,indices=nearest_grid(z['f0'],z['periodicity'],.01,.016,count)
  raw=frequency_to_midi(f);voiced=np.isfinite(raw)
 return {'raw':raw,'probability':q,'voiced':voiced,'rms':rms,'energy':max(.001,float(rms.max())*.025),
         'onsets':onsets,'envelope':env,'short_onsets':short_onsets,'short_envelope':short,
         'duration':duration,'wave':str(wave),'wave_sha256':sha(wave),'pitchfile':str(pitchfile),'pitch_sha256':sha(pitchfile)}

def make(recipe,output):
 f=features(recipe['source'],recipe['model'])
 pitches,c=extend_confidence(f['raw'],f['voiced'],f['probability'],f['rms'],.016,recipe['high'],recipe['low'],.128,f['energy'])
 if recipe['onset']=='legacy':attacks=bounded_backtrack(f['onsets'],f['envelope'],.016,.096)
 else:attacks=bounded_backtrack(f['short_onsets'],f['short_envelope'],.004,.032)
 notes,evidence=attack_led_notes(pitches,f['probability'],attacks,.016,f['duration'],vote_guard=recipe['guard'])
 notes=clean_notes(notes,f['duration'])
 if not notes:raise ValueError('Empty candidate requires explicit empty-result handling')
 path=output/(recipe['id']+'.mid');write_midi(notes,path)
 detail=output/(recipe['id']+'.json');detail.write_text(json.dumps({'recipe':recipe,'wave':f['wave'],'wave_sha256':f['wave_sha256'],'pitch_source':f['pitchfile'],'pitch_sha256':f['pitch_sha256'],'confidence':c,'attacks':attacks.tolist(),'events':evidence,'notes':[asdict(n) for n in notes]},ensure_ascii=False,indent=2)+'\n')
 return {'id':recipe['id'],'recipe':recipe,'path':str(path),'sha256':sha(path),'provenance_path':str(detail),'provenance_sha256':sha(detail),'predicted':len(notes)}

def main():
 p=argparse.ArgumentParser();p.add_argument('phase',type=int,choices=[1,2,3]);p.add_argument('--output',type=Path);p.add_argument('--ledger',type=Path);a=p.parse_args()
 output=a.output or Path(f'outputs/runs/bass-models/phase{a.phase}');ledger=a.ledger or ROOT/f'phase{a.phase}-ledger.json'
 if output.exists():raise FileExistsError('Preserve existing phase')
 output.mkdir(parents=True)
 if a.phase==1:
  profiles=json.loads((ROOT/'实验登记.json').read_text())['stage1']['confidence_profiles'];recipes=[]
  for m,values in profiles.items():
   for k,(hi,lo) in enumerate(values):recipes.append({'id':f'S1-{m}-{k}','source':'demucs','model':m,'high':hi,'low':lo,'onset':'legacy','guard':None})
  rows=[make(r,output) for r in recipes]
  assert Path(rows[0]['path']).read_bytes()==Path(json.loads(Path('config/bass-research.lock.json').read_text())['selected_bass']['path']).read_bytes()
 else:
  previous=json.loads((ROOT/f'phase{a.phase-1}-choice.json').read_text());rows=[previous['row']];r=previous['row']['recipe']
  if a.phase==2:recipes=[r|{'id':f'S2-{o}-{g}','onset':o,'guard':g} for o in ['legacy','short'] for g in [0,.032]]
  else:recipes=[r|{'id':f'S3-{s}','source':s} for s in ['ft','sw']]
  rows.extend(make(r,output) for r in recipes)
 result={'phase':a.phase,'registration_sha256':sha(ROOT/'实验登记.json'),'generator_sha256':sha(__file__),'rows':rows}
 ledger.parent.mkdir(parents=True,exist_ok=True);ledger.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print([(x['id'],x['predicted']) for x in rows])
if __name__=='__main__':main()
