"""Read-only fixed-reference evaluation, separate from candidate generation."""
from pathlib import Path
from dataclasses import replace
import argparse,json,hashlib,numpy as np
from audio_midi.quality import load_reference_tracks,read_notes
from audio_midi.bass_diagnostics import match_events


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

root=Path('outputs/bass-refinement')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ledger',type=Path,default=root/'候选清单.json')
parser.add_argument('--output',type=Path,default=root/'逐步评分.json')
args=parser.parse_args()
ledger=json.loads(args.ledger.read_text());baseline=read_notes(Path(ledger['rows'][0]['path']))
refmanifest=Path('outputs/two-methods/标准清单.json')
refs=[n for n in load_reference_tracks(refmanifest) if n.category=='bass' and .14<=n.onset<.14+.9995*60.0304375]
def aligned(ns):return [replace(n,onset=n.onset*.9995+.14,offset=n.offset*.9995+.14) for n in ns]
bpairs=match_events(refs,aligned(baseline),.05);basehits={i for i,j in bpairs};results=[]
for row in ledger['rows']:
 assert sha(row['path'])==row['sha256']
 ns=read_notes(Path(row['path']));p=aligned(ns);pairs=match_events(refs,p,.05);hits={i for i,j in pairs}
 tp=len(pairs);pred=len(ns);ref=len(refs)
 # Tie breaker uses nearest baseline event per prediction; no timing or reference modifications.
 onset_change=sum(min(abs(n.onset-b.onset) for b in baseline) for n in ns)/len(ns) if ns else 0
 results.append(row|{'matched':tp,'reference':ref,'extra':pred-tp,'missed':ref-tp,
                     'precision':tp/pred if pred else 0,'recall':tp/ref,'f1':2*tp/(pred+ref),
                     'median_abs_onset_error_ms':float(np.median([abs(refs[i].onset-p[j].onset)*1000 for i,j in pairs])) if pairs else None,
                     'mean_nearest_baseline_onset_change':onset_change,
                     'matched_pairs':[{'reference_index':i,'prediction_index':j,'delta_ms':(p[j].onset-refs[i].onset)*1000} for i,j in pairs],
                     'gained_reference_indices':sorted(hits-basehits),'lost_reference_indices':sorted(basehits-hits)})
def best(rows):return max(rows,key=lambda x:(x['f1'],-x['extra'],-x['mean_nearest_baseline_onset_change']))
stages={'baseline':results[0],
        'confidence_only_best':best([x for x in results if x['confidence']!='base' and x['onset']=='base']),
        'onset_only_best':best([x for x in results if x['confidence']=='base' and x['onset']!='base']),
        'combined_best':best([x for x in results if x['confidence']!='base' and x['onset']!='base'])}
winner=best(results)
if winner['f1']<=results[0]['f1']:winner=results[0]
report={'reference_manifest_sha256':sha(refmanifest),'ledger_sha256':sha(args.ledger),
        'alignment':{'scale':.9995,'shift':.14,'duration':60.0304375,'tolerance':.05},
        'rows':results,'stage_best':{k:v['id'] for k,v in stages.items()},'selected':winner['id'],
        'caveat':'Seen development reference arrangement; no new-song/generalization or studio-truth claim.'}
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('id TP pred ref FP FN F1')
for x in results:print(x['id'],x['matched'],x['predicted'],x['reference'],x['extra'],x['missed'],round(x['f1']*100,3))
print('stages',report['stage_best'],'selected',report['selected'])
