"""Save local stage comparisons and replace only the bass track in a new six-track MIDI."""
from pathlib import Path
from dataclasses import replace
import json,hashlib,shutil,mido
from audio_midi.quality import read_notes,load_reference_tracks
from audio_midi.bass_diagnostics import match_events
from audio_midi.render import render_midi
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path('outputs/bass-models');scores=[json.loads((root/f'phase{i}-scores.json').read_text()) for i in [1,2,3]]
allrows={r['id']:r for s in scores for r in s['rows']};winner=allrows[scores[-1]['selected']]
baseline=json.loads(Path('config/bass-research.lock.json').read_text())
assert sha(baseline['selected_bass']['path'])==baseline['selected_bass']['sha256']
assert sha(baseline['selected_six_track']['path'])==baseline['selected_six_track']['sha256']
dest=Path('outputs/runs/bass-models/交付');dest.mkdir(parents=True,exist_ok=False)
labels={'S1-pyin-0':'00-上版贝斯-53.33','S1-crepe-0':'01-CREPE-41.03','S1-penn-0':'02-PENN-46.15','S2-legacy-0':'03-仅限制投票-58.33','S2-short-0':'04-贝斯新版-62.34','S3-ft':'05-ft对照-61.11','S3-sw':'06-SW对照-60.61'}
renders={}
for id,label in labels.items():
 path=dest/(label+'.mid');shutil.copyfile(allrows[id]['path'],path)
 renders[label]=render_midi(path,Path('work/models/GeneralUser-GS.sf2'),dest/(label+'.wav'))
old=mido.MidiFile(baseline['selected_six_track']['path']);new=mido.MidiFile(type=old.type,ticks_per_beat=old.ticks_per_beat);bass=mido.MidiFile(winner['path'])
assert bass.ticks_per_beat==old.ticks_per_beat
assert [m.tempo for m in bass.tracks[0] if m.type=='set_tempo']==[m.tempo for m in old.tracks[0] if m.type=='set_tempo']
for t in old.tracks:
 if t.name!='bass':new.tracks.append(mido.MidiTrack(m.copy() for m in t));continue
 channel=next(m.channel for m in t if m.type=='program_change');bt=next(t for t in bass.tracks if t.name=='bass')
 new.tracks.append(mido.MidiTrack(m.copy(channel=channel) if not m.is_meta else m.copy() for m in bt))
path=dest/'六轨-仅替换贝斯.mid';new.save(path)
for a,b in zip(old.tracks,mido.MidiFile(path).tracks):
 if a.name!='bass':assert [m.dict() for m in a]==[m.dict() for m in b]
renders['六轨-仅替换贝斯']=render_midi(path,Path('work/models/GeneralUser-GS.sf2'),dest/'六轨-仅替换贝斯.wav')
r=[n for n in load_reference_tracks(Path('outputs/two-methods/标准清单.json')) if .14<=n.onset<.14+.9995*60.0304375]
p=[replace(n,onset=n.onset*.9995+.14) for n in read_notes(path)]
per={}
for c in ['piano','acoustic_guitar','electric_guitar','bass','drums','strings']:
 a=[n for n in r if n.category==c];b=[n for n in p if n.category==c];tp=len(match_events(a,b,.05));per[c]={'matched':tp,'predicted':len(b),'reference':len(a),'f1':2*tp/(len(a)+len(b))}
tp=sum(x['matched'] for x in per.values());result={'overall':{'matched':tp,'predicted':len(p),'reference':len(r),'f1':2*tp/(len(p)+len(r))},'per_category':per,'other_five_tracks_conductor_messages_unchanged':True,'rendered':renders}
(root/'六轨评分与试听.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
selection={'status':'seen 0–60 development research, not production/generalization/commercial approval','selected':winner['id'],'recipe':winner['recipe'],'source_ledger':str(root/'phase3-ledger.json'),'source_ledger_sha256':sha(root/'phase3-ledger.json'),'input_sha256':baseline['input_sha256'],'bass':{'path':str(dest/(labels[winner['id']]+'.mid')),'sha256':sha(dest/(labels[winner['id']]+'.mid'))},'six_track':{'path':str(path),'sha256':sha(path)},'score':{k:winner[k] for k in ['matched','predicted','reference','extra','missed','f1']},'implementation_sha256':{'bass_models.py':sha('src/audio_midi/bass_models.py'),'bass_refinement.py':sha('src/audio_midi/bass_refinement.py')},'entrypoint':'outputs/bass-models/generate.py: cached research rebuild only; existing default runner unchanged'}
Path('config/bass-models.lock.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result['overall']));print(selection['bass'])
