"""Diagnostic-only reference comparison. Output is not an input to generation."""
from pathlib import Path
from dataclasses import replace,asdict
import json,importlib.util,hashlib,numpy as np
from audio_midi.quality import read_notes,load_reference_tracks
from audio_midi.bass_diagnostics import match_events
spec=importlib.util.spec_from_file_location('old','outputs/bass-evidence/generate.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
f,y,feature,anchors,neural,sources,arrays=old.acoustic()
root=Path('outputs/bass-sequence');path=root/'75基线逐音归因.json'
if path.exists():raise FileExistsError(path)
lock=json.loads(Path('config/bass-evidence.lock.json').read_text());assert old.sha(lock['bass']['path'])==lock['bass']['sha256']
refs=[n for n in load_reference_tracks(Path('outputs/two-methods/标准清单.json')) if n.category=='bass' and .14<=n.onset<.14+.9995*60.0304375]
notes=read_notes(Path(lock['bass']['path']));scaled=[replace(n,onset=n.onset*.9995+.14) for n in notes];pairs=match_events(refs,scaled,.05);ri={i for i,j in pairs};pi={j for i,j in pairs}
rows=[]
for kind,events,hit in [('FN',refs,ri),('FP',notes,pi)]:
 for i,n in enumerate(events):
  if i in hit:continue
  t=(n.onset-.14)/.9995 if kind=='FN' else n.onset;a=max(0,int(np.floor((t-.15)/.016)));b=min(len(f['raw']),int(np.ceil((t+.15)/.016)))
  details={}
  for m,(pitch,q) in {'pyin':(f['raw'],f['probability']),**neural}.items():
   valid=np.isfinite(pitch[a:b]);correct=valid&(np.rint(pitch[a:b])==n.pitch);limit={'pyin':.05,'crepe':.21,'penn':.2}[m];energy=f['rms'][a:b]>=f['energy'];support=correct&(q[a:b]>=limit)&energy
   if m=='pyin':support &= f['voiced'][a:b]
   details[m]={'raw_same_pitch_frames':int(correct.sum()),'qualified_same_pitch_frames':int(support.sum()),'energy_qualified_frames':int(energy.sum()),'raw_median_pitch':float(np.nanmedian(pitch[a:b])) if valid.any() else None}
  nearest=[{'predicted_index':j,'pitch':p.pitch,'delta_seconds':p.onset-t} for j,p in enumerate(notes) if abs(p.onset-t)<=.15]
  nearrefs=[{'reference_index':j,'pitch':r.pitch,'delta_seconds':(r.onset-.14)/.9995-t} for j,r in enumerate(refs) if abs((r.onset-.14)/.9995-t)<=.15]
  sameoverlap=[j for j,r in enumerate(refs) if r.pitch==n.pitch and (r.onset-.14)/.9995<=t<(r.offset-.14)/.9995] if kind=='FP' else []
  if kind=='FN':
   if not any(d['raw_same_pitch_frames'] for d in details.values()):label='no_same_pitch_estimate_in_original_source_window'
   elif not any(d['qualified_same_pitch_frames'] for d in details.values()):label='confidence_or_energy_rejection_signal'
   else:label='pitch_support_exists_but_event_or_anchor_missing_or_competing'
  else:label='same_pitch_reference_span_overlap_not_proof_false_retrigger' if sameoverlap else 'pitch_conflict_or_arrangement_difference' if nearrefs else 'no_near_reference_or_arrangement_difference'
  rows.append({'kind':kind,'index':i,'pitch':n.pitch,'source_time':t,'automatic_signal':label,'original_source_models':details,'audio_at_time':feature(t),'near_audio_anchors':[float(x) for x in anchors if abs(x-t)<=.15],'near_predictions':nearest,'near_reference':nearrefs,'overlap_reference_indices':sameoverlap})
result={'frozen_bass_sha256':lock['bass']['sha256'],'formal_counts':{'matched':len(pairs),'FP':len(notes)-len(pairs),'FN':len(refs)-len(pairs)},'diagnostic_matches':{str(t):len(match_events(refs,scaled,t)) for t in [.05,.1,.15,.3]},'rows':rows,'limits':'automatic nearby evidence, not unique causal attribution/studio truth/manual hearing; generator never reads this file'}
path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
from collections import Counter
print(Counter(r['automatic_signal'] for r in rows))
