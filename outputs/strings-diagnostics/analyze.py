"""Read-only source/MIDI diagnostics. Never changes notes or runs model inference."""
from pathlib import Path
from dataclasses import replace,asdict
import json,hashlib,subprocess,argparse
from collections import Counter
import numpy as np,soundfile as sf
from scipy.signal import resample_poly
from audio_midi.events import NoteEvent
from audio_midi.quality import read_notes,load_reference_tracks
from audio_midi.bass_diagnostics import match_events
from audio_midi.stems import verify_stem_receipt
from audio_midi.stitching import clean_notes
from audio_midi.midi import write_midi
from metrics import duration_overlap
import tempfile
ROOT=Path('outputs/strings-diagnostics');DURATION=60.0304375
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'诊断结果.json');parser.add_argument('--freeze-output',type=Path,default=Path('config/bass-frozen.lock.json'));args=parser.parse_args();out=args.output
 if out.exists() or args.freeze_output.exists():raise FileExistsError('Preserve diagnostics and freeze record')
 lockpath=Path('config/bass-sequence.lock.json');lock=json.loads(lockpath.read_text());protected=[]
 for key in ['bass','six_track']:
  e=lock[key];assert sha(e['path'])==e['sha256'];protected.append(e)
 code=['src/audio_midi/bass_sequence.py','src/audio_midi/bass_evidence.py','src/audio_midi/bass_models.py','src/audio_midi/bass_refinement.py','outputs/bass-sequence/common.py','outputs/bass-sequence/generate.py','outputs/bass-evidence/generate.py','outputs/bass-models/generate.py']
 freeze={'status':'explicitly frozen by user2026-10-17; no future bass changes without new authorization','selected':'D75+W64','release_tag':'v0.1.0-bass-sequence.1','release_commit':subprocess.check_output(['git','rev-parse','v0.1.0-bass-sequence.1'],text=True).strip(),'lock_path':str(lockpath),'lock_sha256':sha(lockpath),'bass':lock['bass'],'six_track':lock['six_track'],'implementation':[{'path':p,'sha256':sha(p)} for p in code],'note':'research selection and hash guard, not a new production CLI or new model weights'}
 args.freeze_output.write_text(json.dumps(freeze,ensure_ascii=False,indent=2)+'\n')
 reference=load_reference_tracks(Path('outputs/two-methods/标准清单.json'));refs=[n for n in reference if n.category=='strings' and .14<=n.onset<.14+.9995*DURATION]
 fullrefs=[replace(n,onset=(n.onset-.14)/.9995,offset=(n.offset-.14)/.9995) for n in reference if n.category=='strings' and n.offset>.14 and n.onset<.14+.9995*DURATION]
 sources={'A':Path('outputs/runs/v01/development/单轨/strings.mid'),'B':Path('outputs/runs/two-methods/sw-local-control/单轨/strings.mid')}
 oldreport=json.loads(Path('outputs/runs/v01/development/运行报告.json').read_text());rawA=oldreport['provenance']['manifest']['sources']['strings'];assert sha(rawA['path'])==rawA['sha256']
 rawpaths={'A':Path(rawA['path']),'B':Path('work/v01/runtime/1792079033121801000/strings.json')}
 trace=json.loads(Path('work/bass-diagnostics/replay/trace.json').read_text());stemroots={'A':Path(trace['stem_path']).parent,'B':Path('work/two-methods/sw-full')}
 for root in stemroots.values():verify_stem_receipt(root,lock['input_sha256'])
 y,sr=sf.read(stemroots['B']/'other.wav',dtype='float32',always_2d=True);expected=resample_poly(y.mean(axis=1),160,441).astype('float32');actual=np.load('work/v01/runtime/1792079033121801000/strings.npy');np.testing.assert_array_equal(actual,expected)
 current=[n for n in read_notes(Path(lock['six_track']['path'])) if n.category=='strings'];solo=read_notes(sources['B']);assert [n.pitch for n in current]==[n.pitch for n in solo];np.testing.assert_allclose([(n.onset,n.offset) for n in current],[(n.onset,n.offset) for n in solo],rtol=0,atol=1e-10)
 rows={}
 for id,path in sources.items():
  notes=read_notes(path);raw=json.loads(rawpaths[id].read_text());rawstrings=[NoteEvent(**n) for n in raw['notes'] if n['category']=='strings'];cleaned=clean_notes(rawstrings,DURATION)
  with tempfile.TemporaryDirectory() as temp:
   rebuilt=Path(temp)/'strings.mid';write_midi(cleaned,rebuilt);assert sha(rebuilt)==sha(path)
  scaled=[replace(n,onset=n.onset*.9995+.14,offset=n.offset*.9995+.14) for n in notes]
  strict=match_events(refs,scaled,.05);ri={i for i,j in strict};pi={j for i,j in strict}
  durations=[n.offset-n.onset for n in notes]
  timeline=lambda ns:[(n.onset,n.offset,n.pitch) for n in ns]
  nr=timeline(fullrefs);npred=timeline(notes)
  longest=[];run=[]
  for n in notes:
   if run and 0<n.onset-run[-1].onset<=.15+1e-9 and n.pitch>run[-1].pitch:run.append(n)
   else:run=[n]
   if len(run)>len(longest):longest=list(run)
  cross={}
  for cat in ['piano','acoustic_guitar','electric_guitar','bass']:
   other=[replace(n,onset=(n.onset-.14)/.9995,offset=(n.offset-.14)/.9995) for n in reference if n.category==cat and n.offset>.14 and n.onset<.14+.9995*DURATION]
   score=duration_overlap(timeline(other),npred,DURATION)
   cross[cat]={'same_pitch_overlap_seconds':score['matched_pitch_seconds'],'fraction_of_predicted_pitch_seconds':score['precision'],'not_causal_proof_of_leakage':True}
  rows[id]={'path':str(path),'sha256':sha(path),'count':len(notes),'strict':{'matched':len(strict),'extra':len(notes)-len(strict),'missed':len(refs)-len(strict),'f1':2*len(strict)/(len(notes)+len(refs))},'onset_diagnostic':{str(t):len(match_events(refs,scaled,t)) for t in [.05,.1,.15,.3]},'onset_only_50ms':len(match_events(refs,scaled,.05,ignore_pitch=True)),'pitch_class_onset_50ms':len(match_events([replace(n,pitch=n.pitch%12) for n in refs],[replace(n,pitch=n.pitch%12) for n in scaled],.05)),
  'duration_absolute_pitch':duration_overlap(nr,npred,DURATION),'duration_pitch_class':duration_overlap(nr,npred,DURATION,chroma=True),'activity_time':duration_overlap(nr,npred,DURATION,activity=True),
  'duration_summary':{'min':min(durations),'median':float(np.median(durations)),'max':max(durations),'under150ms':sum(d<.15 for d in durations),'under300ms':sum(d<.3 for d in durations)},
  'raw_note_counts':dict(Counter(n['category'] for n in raw['notes'])),'raw_strings_count':len(rawstrings),'raw_strings_programs':dict(Counter(n.program for n in rawstrings)),'decode_errors':raw['decode_errors'],'raw_to_clean_midi_byte_identical':True,
  'model':{k:raw[k] for k in ['model','model_revision','weight_sha256','sample_rate','model_window_samples']},'longest_fast_ascending_run':{'count':len(longest),'notes':[asdict(n) for n in longest]},'cross_reference_coincidence':cross,
  'notes':[asdict(n)|{'index':i,'strict_matched':i in pi} for i,n in enumerate(notes)],'missing_reference_indices':[i for i in range(len(refs)) if i not in ri],
  'raw_path':str(rawpaths[id]),'raw_sha256':sha(rawpaths[id]),'stem_path':str(stemroots[id]/'other.wav'),'stem_sha256':sha(stemroots[id]/'other.wav')}
 result={'scope':'diagnosis only,0–60; no note edits/new inference/alignment fitting; vocals ignored','reference_type':'user says high-similarity MIDI extracted from sameMP3, not original session or studio truth','alignment':{'scale':.9995,'shift':.14,'duration':DURATION},'strict_reference_count':len(refs),'duration_reference_count_including_leading_carry':len(fullrefs),'reference_notes_source_timeline':[asdict(n) for n in fullrefs],'current_source':'B','rows':rows,'bass_frozen_config_sha256':sha(args.freeze_output),'SW_model_input_exact_resample_verified':True,'protected':protected,'limits':'duration/chroma/activity are objective overlap diagnostics, not listening scores or evidence a source is truly strings; decoder errors not localized without raw tokens'}
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print('reference',len(refs))
 for id,r in rows.items():print(id,r['strict'],'duration exact',r['duration_absolute_pitch']['f1'],'chroma',r['duration_pitch_class']['f1'],'activity',r['activity_time']['f1'],'rise',r['longest_fast_ascending_run']['count'])
if __name__=='__main__':main()
