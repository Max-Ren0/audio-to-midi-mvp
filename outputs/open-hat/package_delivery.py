from pathlib import Path
import json,hashlib,shutil,zipfile
from audio_midi.render import render_midi
from audio_midi.quality import read_notes
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path('outputs/runs/open-hat/交付');root.mkdir(exist_ok=False)
choices={'00-保留当前85版':'outputs/runs/drums-v2/交付/鼓-v0.1-强化版.mid','01-YourMT3开镲替换-未检出开镲':'outputs/runs/open-hat/candidates/YourMT3__replace-open.mid','02-IDM开镲替换-低门槛':'outputs/runs/open-hat/candidates/IDM-t0.3__replace-open.mid','03-YODO开镲替换-HiHat输入':'outputs/runs/open-hat/candidates/YODO-x1.0__replace-open.mid','04-YODO开镲替换-原鼓输入':'outputs/runs/open-hat/sw-control/YODO-SW-x1.0__replace-open.mid','05-YourMT3仅开闭镲':'outputs/runs/open-hat/candidates/YourMT3__hats-only.mid','06-IDM仅开闭镲':'outputs/runs/open-hat/candidates/IDM-t0.3__hats-only.mid','07-YODO仅开闭镲':'outputs/runs/open-hat/candidates/YODO-x1.0__hats-only.mid'}
rendered={}
for name,source in choices.items():
 target=root/(name+'.mid');shutil.copy2(source,target)
 if read_notes(target):rendered[name]=render_midi(target,Path('work/models/GeneralUser-GS.sf2'),root/(name+'.wav'))
 else:rendered[name]={'status':'empty MIDI control, no sound audition generated'}
shutil.copy2('work/open-hat/drumsep-full60/hh.wav',root/'HiHat分离结果.wav')
for name in ['control-kit0','control-kit8','control-hats-level']:
 shutil.copy2(Path('work/open-hat')/(name+'.wav'),root/(name+'.wav'));shutil.copy2(Path('work/open-hat')/(name+'.truth.json'),root/(name+'.truth.json'))
rows=json.loads(Path('outputs/open-hat/本曲评分.json').read_text())['candidates'];dest=root/'全部80候选MID';dest.mkdir()
for r in rows:
 p=Path(r['path']);assert sha(p)==r['sha256'];shutil.copy2(p,dest/p.name)
report={'reference_only_for_scoring':True,'baseline_preserved_sha256':sha('outputs/runs/drums-v2/交付/鼓-v0.1-强化版.mid'),'candidates':len(rows),'unique_midi_hashes':len(set(r['sha256'] for r in rows)),'render':rendered,'selection':'retain original85.56 version; no qualifying fullF1 improvement with openhat recovered','artifact_files':{str(p.relative_to(root)):{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in root.rglob('*') if p.is_file()}}
Path('outputs/open-hat/交付校验.json').write_text(json.dumps(report,indent=2));print('packaged initial',len(report['artifact_files']),'files')
