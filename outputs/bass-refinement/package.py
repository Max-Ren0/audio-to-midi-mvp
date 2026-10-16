"""Publish new local outputs; preserve all existing frozen instrument files."""
from pathlib import Path
from dataclasses import replace
import hashlib,json,shutil,mido
from audio_midi.quality import read_notes,load_reference_tracks
from audio_midi.bass_diagnostics import match_events
from audio_midi.render import render_midi


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

root=Path('outputs/bass-refinement');score=json.loads((root/'逐步评分.json').read_text())
rows={x['id']:x for x in score['rows']};selected=rows[score['selected']]
lock=json.loads(Path('config/drums-selected.lock.json').read_text())
for a in lock['assets'].values():assert sha(a['path'])==a['sha256']
dest=Path('outputs/runs/bass-refinement/交付');dest.mkdir(parents=True,exist_ok=False)
labels={'baseline':'00-原贝斯-41.38','C1':'01-仅置信度-39.56','O2':'02-仅起音-49.32',score['selected']:'03-贝斯优化版-53.33'}
rendered={}
for ident,label in labels.items():
 p=dest/(label+'.mid');shutil.copyfile(rows[ident]['path'],p)
 rendered[label]=render_midi(p,Path('work/models/GeneralUser-GS.sf2'),dest/(label+'.wav'))
old=mido.MidiFile(lock['assets']['six_track_midi']['path']);new=mido.MidiFile(type=old.type,ticks_per_beat=old.ticks_per_beat)
bass=mido.MidiFile(selected['path']);assert bass.ticks_per_beat==old.ticks_per_beat
assert [m.tempo for m in old.tracks[0] if m.type=='set_tempo']==[m.tempo for m in bass.tracks[0] if m.type=='set_tempo']
for t in old.tracks:
 if t.name!='bass':new.tracks.append(mido.MidiTrack(m.copy() for m in t));continue
 channel=next(m.channel for m in t if m.type=='program_change')
 bt=next(t for t in bass.tracks if t.name=='bass')
 new.tracks.append(mido.MidiTrack(m.copy(channel=channel) if not m.is_meta else m.copy() for m in bt))
six=dest/'六轨-仅替换贝斯.mid';new.save(six)
for a,b in zip(old.tracks,mido.MidiFile(six).tracks):
 if a.name!='bass':assert [m.dict() for m in a]==[m.dict() for m in b]
rendered['六轨-仅替换贝斯']=render_midi(six,Path('work/models/GeneralUser-GS.sf2'),dest/'六轨-仅替换贝斯.wav')
refs=[n for n in load_reference_tracks(Path('outputs/two-methods/标准清单.json')) if .14<=n.onset<.14+.9995*60.0304375]
p=[replace(n,onset=n.onset*.9995+.14) for n in read_notes(six)]
per={}
for cat in ['piano','acoustic_guitar','electric_guitar','bass','drums','strings']:
 a=[n for n in refs if n.category==cat];b=[n for n in p if n.category==cat];tp=len(match_events(a,b,.05))
 per[cat]={'matched':tp,'reference':len(a),'predicted':len(b),'f1':2*tp/(len(a)+len(b))}
tp=sum(x['matched'] for x in per.values())
result={'source_six_sha256':lock['assets']['six_track_midi']['sha256'],'prediction_sha256':sha(six),
        'overall':{'matched':tp,'predicted':len(p),'reference':len(refs),'f1':2*tp/(len(p)+len(refs))},'per_category':per,
        'other_five_tracks_and_conductor_exact_messages_unchanged':True,'renders':rendered}
(root/'六轨与试听.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
# Shared baseline equality was verified before generation; this lock is an explicit research selection, not an arbitrary-input runner.
selection={'status':'research selected on seen development excerpt; not production or commercial approval',
           'recipe':'extend_confidence(high=.2,low=.05,extension=.128) -> bounded_backtrack(.096) -> attack_led_notes(.32,.08,.08)',
           'implementation':'src/audio_midi/bass_refinement.py','implementation_sha256':sha('src/audio_midi/bass_refinement.py'),
           'selected_candidate':selected['id'],'source_ledger':'outputs/bass-refinement/候选清单.json',
           'source_ledger_sha256':sha(root/'候选清单.json'),'input_sha256':lock['input_sha256'],
           'baseline_bass':lock['assets']['bass_midi'],
           'selected_bass':{'path':str(dest/(labels[score['selected']]+'.mid')),'sha256':sha(dest/(labels[score['selected']]+'.mid'))},
           'selected_six_track':{'path':str(six),'sha256':sha(six)},
           'score':{k:selected[k] for k in ['matched','predicted','reference','extra','missed','f1']},
           'limits':'Cached 0–60 research rebuild; original default pYIN untouched; no 60–120 or new-song validation.'}
Path('config/bass-research.lock.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
