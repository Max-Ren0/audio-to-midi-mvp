"""Reference-free observational replay of the frozen bass DSP; writes a new local dir."""
import argparse,csv,hashlib,json,platform,time
from pathlib import Path
from dataclasses import asdict
import numpy as np
import librosa,soundfile
from audio_midi.contour import transcribe_monophonic
from audio_midi.stitching import clean_notes
from audio_midi.midi import write_midi
from audio_midi.stems import verify_stem_receipt


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--input',type=Path,required=True);p.add_argument('--stems',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('Preserving existing diagnostics')
 started=time.monotonic();receipt=verify_stem_receipt(a.stems,sha(a.input))
 trace={};notes=transcribe_monophonic(a.stems/'bass.wav','bass',trace=trace)
 duration=soundfile.info(a.stems/'bass.wav').duration
 cleaned=clean_notes(notes,duration)
 a.output.mkdir(parents=True)
 arrays={k:v for k,v in trace.items() if isinstance(v,np.ndarray)}
 np.savez_compressed(a.output/'frames.npz',**arrays)
 meta={k:v for k,v in trace.items() if k not in arrays}
 meta.update({'input_path':str(a.input),'input_sha256':sha(a.input),'stem_path':str(a.stems/'bass.wav'),
              'stem_sha256':receipt['stem_sha256']['bass'],'separation_receipt_sha256':sha(a.stems/'separation-receipt.json'),
              'duration':duration,'elapsed_seconds':time.monotonic()-started,
              'versions':{'python':platform.python_version(),'numpy':np.__version__,'librosa':librosa.__version__,'soundfile':soundfile.__version__},
              'source_sha256':{'contour.py':sha('src/audio_midi/contour.py'),'stitching.py':sha('src/audio_midi/stitching.py')},
              'raw_notes':[asdict(n) for n in notes],'cleaned_notes':[asdict(n) for n in cleaned]})
 (a.output/'trace.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 write_midi(cleaned,a.output/'replayed-bass.mid')
 with (a.output/'frames.csv').open('w') as f:
  keys=['raw_f0','raw_pitches','voiced','probability','rms','input_pitches','gap_filled_pitches','smoothed_pitches','onset_strength']
  w=csv.writer(f);w.writerow(['frame','audio_seconds',*keys,'reject_unvoiced','reject_probability','reject_energy'])
  for i in range(len(trace['raw_f0'])):
   w.writerow([i,i*trace['frame_seconds'],*[arrays[k][i] if i<len(arrays[k]) else '' for k in keys],
               not trace['voiced'][i],not trace['probability'][i]>=.2,not trace['rms'][i]>trace['energy_threshold']])
 print(json.dumps({'frames':len(trace['raw_f0']),'raw_notes':len(notes),'cleaned_notes':len(cleaned),'elapsed_seconds':meta['elapsed_seconds']}))

if __name__=='__main__':main()
