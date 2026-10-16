"""Read-only bass evaluation and evidence export. Never adjusts notes to reference."""
from pathlib import Path
from dataclasses import asdict,replace
from collections import Counter
import argparse,csv,hashlib,json
import numpy as np
import soundfile as sf
from audio_midi.audio import decode_mp3
from audio_midi.quality import load_reference_tracks,read_notes
from audio_midi.bass_diagnostics import analyze_errors
from audio_midi.events import NoteEvent


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output-dir',type=Path,default=Path('outputs/bass-diagnostics'))
 parser.add_argument('--clip-dir',type=Path,default=Path('outputs/runs/bass-diagnostics/clips'))
 args=parser.parse_args();root=args.output_dir;root.mkdir(parents=True,exist_ok=True)
 source=Path(__file__).parent;local=Path('work/bass-diagnostics/replay')
 meta=json.loads((local/'trace.json').read_text())
 with np.load(local/'frames.npz') as arrays:trace=meta|{k:arrays[k] for k in arrays.files}
 lock=json.loads(Path('config/drums-selected.lock.json').read_text())
 for a in lock['assets'].values():assert sha(a['path'])==a['sha256']
 baseline=Path(lock['assets']['bass_midi']['path']);p=read_notes(baseline)
 replay=read_notes(local/'replayed-bass.mid')
 assert [asdict(n) for n in replay]==[asdict(n) for n in p], 'Replay must reproduce every baseline MIDI event'
 assert (local/'replayed-bass.mid').read_bytes()==baseline.read_bytes(), 'Replay must reproduce baseline bytes'
 raw=[NoteEvent(**n) for n in meta['raw_notes']];cleaned=[NoteEvent(**n) for n in meta['cleaned_notes']]
 cleanup_changes=[]
 for i,n in enumerate(raw):
  candidates=[(j,c) for j,c in enumerate(cleaned) if c.pitch==n.pitch and abs(c.onset-n.onset)<1e-9]
  cleanup_changes.append({'raw_note_index':i,'cleaned_note_index':candidates[0][0] if candidates else None,
       'before':asdict(n),'after':asdict(candidates[0][1]) if candidates else None,
       'changed':not candidates or n!=candidates[0][1]})
 refs=load_reference_tracks(Path('outputs/two-methods/标准清单.json'))
 r=[replace(n,onset=(n.onset-.14)/.9995,offset=(n.offset-.14)/.9995) for n in refs
    if n.category=='bass' and .14<=n.onset<.14+.9995*60.0304375]
 result=analyze_errors(r,p,trace)
 provenance=[]
 for j,n in enumerate(p):
  candidates=[(k,s) for k,s in enumerate(trace['segments']) if s['status']=='emitted' and s['pitch']==n.pitch and abs(s['onset']-n.onset)<.0011]
  assert len(candidates)==1
  k,s=candidates[0]
  provenance.append({'prediction_index':j,'segment_index':k,'start_reason':trace['segments'][k-1]['end_reason'] if k else 'start_of_audio','end_reason':s['end_reason']})
 result['prediction_provenance']=provenance
 for row in result['false_positives']:row['prediction_provenance']=provenance[row['index']]
 assert (result['counts']['matched'],len(p),len(r))==(18,51,36)
 result.update({'alignment':{'scale':.9995,'shift':.14,'duration':60.0304375},
  'event_times':'source audio seconds; all evaluation deltas converted to reference time',
  'reference_events':[asdict(n) for n in r],'prediction_events':[asdict(n) for n in p],'cleanup_provenance':cleanup_changes,
  'observations':{'frames':len(trace['raw_f0']),'raw_notes':len(raw),'cleaned_notes':len(cleaned),
    'cleanup_changed_notes':sum(x['changed'] for x in cleanup_changes),'replay_midi_byte_identical':True,
    'segment_status_counts':dict(Counter(s['status'] for s in trace['segments'])),
    'segment_end_reason_counts':dict(Counter(s['end_reason'] for s in trace['segments'])),
    'filter_rejected_unvoiced':int((~trace['voiced']).sum()),
    'filter_rejected_low_probability':int((~(trace['probability']>=.2)).sum()),
    'filter_rejected_low_energy':int((~(trace['rms']>trace['energy_threshold'])).sum()),
    'filter_kept_frames':int(np.isfinite(trace['input_pitches']).sum()),
    'gap_filled_frames':int((~np.isfinite(trace['input_pitches']) & np.isfinite(trace['gap_filled_pitches'])).sum()),
    'smoothing_changed_frames':int((np.isfinite(trace['gap_filled_pitches']) & np.isfinite(trace['smoothed_pitches']) &
                                  (np.rint(trace['gap_filled_pitches'])!=trace['smoothed_pitches'])).sum())}})
 tags={'nearby_same_pitch_onset':'附近有同音高事件（起音/重复音候选）','nearby_octave_candidate':'附近有相差八度事件（八度候选）',
       'overlapping_same_pitch_event':'同音高音符时段重叠','target_frames_removed_by_filter':'附近目标音高帧被过滤',
       'target_frames_reduced_after_contour_processing':'补洞/平滑后目标帧数减少',
       'nearby_short_segment_discarded':'附近目标短音段被删除','no_target_pitch_in_raw_onset_window':'原始起音窗口未出现目标音高','unresolved':'未确定'}
 cliproot=args.clip_dir;cliproot.mkdir(parents=True,exist_ok=True)
 stem,sr=sf.read(meta['stem_path'],dtype='float32',always_2d=True)
 mix=decode_mp3(Path(meta['input_path']),16000)
 errors=result['false_positives']+result['false_negatives']
 for row in errors:
  start=max(0,row['onset']-.35);end=min(mix.duration_seconds,row['onset']+.85)
  name=f"{row['kind']}-{row['index']:02d}-{row['onset']:.3f}s"
  row['audio_clips']={'start':start,'end':end,'mix':str(cliproot/(name+'-mix.wav')),'bass':str(cliproot/(name+'-bass.wav'))}
  sf.write(row['audio_clips']['mix'],mix.samples[round(start*16000):round(end*16000)],16000,subtype='FLOAT')
  sf.write(row['audio_clips']['bass'],stem[round(start*sr):round(end*sr)],sr,subtype='FLOAT')
 (root/'逐音归因.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 with (root/'逐音错误清单.csv').open('w',encoding='utf-8-sig') as f:
  w=csv.writer(f,lineterminator="\n");w.writerow(['类型','索引','音频秒','MIDI音高','结束秒','证据标签（可重叠，不是确定根因）','±150ms原始目标帧','过滤后目标帧','平滑后目标帧','原曲片段','贝斯片段'])
  for row in errors:
   e=row['onset_window'];w.writerow([row['kind'],row['index'],row['onset'],row['pitch'],row['offset'],
         '；'.join(tags[t] for t in row['evidence_flags']),e['raw_target_frames'],e['kept_target_frames'],e['smoothed_target_frames'],row['audio_clips']['mix'],row['audio_clips']['bass']])
 flagcounts={kind:dict(Counter(t for row in rows for t in row['evidence_flags'])) for kind,rows in [('FP',result['false_positives']),('FN',result['false_negatives'])]}
 result_summary={'counts':result['counts'],'same_pitch_onset_tolerance':result['same_pitch_onset_tolerance'],
                 'time_only_50ms_matched':result['time_only_50ms_matched'],
                 'octave_only_50ms_matched':result['octave_only_50ms_matched'],
                 'observations':result['observations'],'nonexclusive_evidence_counts':flagcounts}
 (root/'诊断汇总.json').write_text(json.dumps(result_summary,ensure_ascii=False,indent=2)+'\n')
 # Bind all local frames/media and compact tracked evidence, without uploading audio or frames.
 files=[local/'trace.json',local/'frames.npz',local/'frames.csv',local/'replayed-bass.mid',*sorted(cliproot.glob('*.wav')),
        root/'逐音归因.json',root/'逐音错误清单.csv',root/'诊断汇总.json']
 manifest={'input_sha256':meta['input_sha256'],'stem_sha256':meta['stem_sha256'],
           'separation_receipt_sha256':meta['separation_receipt_sha256'],
           'reference_manifest_sha256':sha('outputs/two-methods/标准清单.json'),
           'baseline_sha256':sha(baseline),'source_sha256':meta['source_sha256']|
             {'bass_diagnostics.py':sha('src/audio_midi/bass_diagnostics.py'),'analyze.py':sha(__file__),'replay.py':sha(source/'replay.py')},
           'files':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in files],
           'limits':'No studio bass reference; no causal proof from note proximity; same seen development excerpt.'}
 (root/'来源与产物校验.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(result_summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
