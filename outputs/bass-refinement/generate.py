"""Generate the 12 preregistered candidates. No reference MIDI is read."""
import argparse,hashlib,json
from pathlib import Path
from dataclasses import asdict
import numpy as np
from audio_midi.bass_refinement import extend_confidence,attack_led_notes,bounded_backtrack
from audio_midi.contour import contour_to_notes
from audio_midi.stitching import clean_notes
from audio_midi.midi import write_midi


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True)
 p.add_argument('--ledger',type=Path,help='Optional separate ledger output for temporary reproduction');a=p.parse_args()
 if a.output.exists():raise FileExistsError('Preserving existing candidates')
 source=Path('outputs/bass-refinement');registration=json.loads((source/'实验登记.json').read_text())
 if sha(a.input)!=registration['input_sha256']:raise ValueError('Input hash mismatch')
 manifest=json.loads(Path(registration['frame_manifest']).read_text())
 for rel in ['work/bass-diagnostics/replay/frames.npz','work/bass-diagnostics/replay/trace.json']:
  entry=next(x for x in manifest['files'] if x['path']==rel)
  if sha(rel)!=entry['sha256']:raise ValueError('Frame cache hash mismatch')
 meta=json.loads(Path('work/bass-diagnostics/replay/trace.json').read_text())
 if meta['input_sha256']!=sha(a.input) or sha(meta['stem_path'])!=meta['stem_sha256']:raise ValueError('Stem mismatch')
 lock=json.loads(Path('config/drums-selected.lock.json').read_text())
 for x in lock['assets'].values():
  if sha(x['path'])!=x['sha256']:raise ValueError('Protected MIDI changed')
 with np.load('work/bass-diagnostics/replay/frames.npz') as z:frames={k:z[k] for k in z.files}
 dt=meta['frame_seconds'];duration=meta['duration'];a.output.mkdir(parents=True)
 confidence={'base':(frames['input_pitches'],{'method':'original_probability_0.2'})}
 for c in registration['confidence_candidates']:
  confidence[c['id']]=extend_confidence(frames['raw_pitches'],frames['voiced'],frames['probability'],frames['rms'],dt,
          c['high'],c['low'],c['extension_seconds'],meta['energy_threshold'])
 rows=[]
 for cid,(pitches,confidence_provenance) in confidence.items():
  for oid in ['base','O1','O2']:
   ident='baseline' if (cid,oid)==('base','base') else oid if cid=='base' else cid if oid=='base' else f'{cid}-{oid}'
   onset_provenance={}
   if oid=='base':
    trace={};notes=contour_to_notes(pitches,dt,'bass',onsets_seconds=frames['onsets_seconds'],trace=trace)
    onset_provenance={'method':'original_contour','segments':trace['segments']}
   else:
    attacks=frames['onsets_seconds'].copy()
    if oid=='O2':attacks=bounded_backtrack(attacks,frames['onset_strength'],dt,.096)
    notes,evidence=attack_led_notes(pitches,frames['probability'],attacks,dt,duration)
    onset_provenance={'method':oid,'source_audio_attacks':frames['onsets_seconds'].tolist(),
                      'processed_attacks_before_spacing':attacks.tolist(),'events':evidence}
   notes=clean_notes(notes,duration)
   dest=a.output/f'{ident}.mid'
   if not notes:
    raise ValueError(f'{ident}: no valid notes; preserve as explicit empty experiment before proceeding')
   write_midi(notes,dest)
   detail={'id':ident,'confidence':confidence_provenance,'onset':onset_provenance,'notes':[asdict(n) for n in notes]}
   detailpath=a.output/f'{ident}.json';detailpath.write_text(json.dumps(detail,ensure_ascii=False,indent=2)+'\n')
   np.savez_compressed(a.output/f'{ident}.npz',pitches=pitches)
   rows.append({'id':ident,'confidence':cid,'onset':oid,'path':str(dest),'sha256':sha(dest),'predicted':len(notes),
                'provenance_path':str(detailpath),'provenance_sha256':sha(detailpath),
                'frame_path':str(a.output/f'{ident}.npz'),'frame_sha256':sha(a.output/f'{ident}.npz')})
 assert len(rows)==registration['maximum_candidates']
 assert (a.output/'baseline.mid').read_bytes()==Path(lock['assets']['bass_midi']['path']).read_bytes()
 ledger={'input_sha256':sha(a.input),'stem_sha256':meta['stem_sha256'],
         'frame_npz_sha256':sha('work/bass-diagnostics/replay/frames.npz'),
         'frame_meta_sha256':sha('work/bass-diagnostics/replay/trace.json'),
         'registration_sha256':sha(source/'实验登记.json'),
         'generator_sha256':sha(__file__),'module_sha256':sha('src/audio_midi/bass_refinement.py'),
         'duration':duration,'rows':rows,'status':'all generated before reference scoring'}
 ledger_output=a.ledger if a.ledger is not None else source/'候选清单.json'
 ledger_output.parent.mkdir(parents=True,exist_ok=True)
 ledger_output.write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps([{'id':x['id'],'notes':x['predicted']} for x in rows],indent=2))

if __name__=='__main__':main()
