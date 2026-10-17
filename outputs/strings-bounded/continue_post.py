from common import *
from audio_midi.strings_bounded import merge_same_pitch,harmonic_prune
import argparse,numpy as np
p=argparse.ArgumentParser();p.add_argument('stage',choices=['merge','harmonic']);p.add_argument('--id-prefix',default='');p.add_argument('--previous-choice',type=Path);p.add_argument('--output',type=Path);p.add_argument('--ledger',type=Path);p.add_argument('--registration',type=Path,default=ROOT/'实验登记.json');a=p.parse_args()
previous=a.previous_choice or ROOT/('short-choice.json' if a.stage=='merge' else 'merge-choice.json');output=a.output or RUN/a.stage;ledger=a.ledger or ROOT/(a.stage+'-ledger.json')
if output.exists() or ledger.exists():raise FileExistsError('Preserve proposed edits')
parent=json.loads(previous.read_text())['row'];notes=[NoteEvent(**n) for n in read_detail(parent)['notes']]
if a.stage=='merge':out,log=merge_same_pitch(notes,.12);id='M'
else:
 y=np.load('work/v01/runtime/1792079033121801000/mix.npy')
 def energy(n):
  v=y[max(0,int(n.onset*16000)):min(len(y),int(n.offset*16000))]
  if len(v)<2:return 0.
  z=np.abs(np.fft.rfft(v*np.hanning(len(v)),n=8192))**2;f=np.fft.rfftfreq(8192,1/16000);target=440*2**((n.pitch-69)/12);band=np.abs(f-target)<=max(3,.02*target)
  return float(z[band].max()/len(v)**2) if band.any() else 0.
 out,log=harmonic_prune(notes,energy);id='H'
id=a.id_prefix+id
row=save(id,out,output,{'parent':parent['id'],'edits':log});ledger.write_text(json.dumps({'parent':parent,'rows':[row],'registration_sha256':sha(a.registration)},ensure_ascii=False,indent=2)+'\n');print(id,len(notes),'to',len(out),'edits',len(log))
