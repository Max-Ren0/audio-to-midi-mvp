"""Per-window pairing reasons, without model forward or reference access."""
from common import *
from collections import defaultdict,Counter
from audio_midi.events import category_for
out=ROOT/'boundary-reasons.json'
if out.exists():raise FileExistsError('Preserve pairing reasons')
result={}
for source in ['other','mix']:
 for prefix in [0,16384]:
  root=Path(f'work/strings-bounded/{source}-{prefix}');raw=json.loads((root/'raw.json').read_text());windows=json.loads((root/'windows.json').read_text());channels=defaultdict(list)
  for w in windows:channels[w['channel']].append(w)
  closures=[]
  for channel,ws in channels.items():
   active={}
   for wi,w in enumerate(ws):
    if wi:
     tied={(e['program'],e['pitch']) for e in w['ties']}
     for key in list(active):
      if key not in tied:
       old=active.pop(key);closures.append({'channel':channel,'window_index':wi,'program':key[0],'pitch':key[1],'onset':old['time'],'offset':w['start'],'reason':'missing_tie','ties_in_next_window':w['ties']})
    for e in sorted([e for e in w['events'] if e['time'] is not None],key=lambda e:(e['time'],e['velocity'])):
     if e['is_drum']:continue
     key=e['program'],e['pitch'];old=active.pop(key,None)
     if old:closures.append({'channel':channel,'window_index':wi,'program':key[0],'pitch':key[1],'onset':old['time'],'offset':e['time'],'reason':'new_onset_same_pitch' if e['velocity'] else 'explicit_note_off'})
     if e['velocity']:active[key]=e
  closed=[c for c in closures if c['reason']=='missing_tie'];assert len(closed)==raw['decode_errors'].get('missing_tie',0)
  result[source+'-'+str(prefix)]={'missing_tie_count':len(closed),'strings_missing_tie_count':sum(category_for(c['program'])=='strings' for c in closed),'missing_tie_closures':closed,'all_closure_reason_counts':dict(Counter(c['reason'] for c in closures)),'notes':'reason describes decoder action from emitted model ties, not proof model should have sustained that note'}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print({k:(v['missing_tie_count'],v['strings_missing_tie_count']) for k,v in result.items()})
