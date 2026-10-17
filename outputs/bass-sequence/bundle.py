"""Hash-bound local comparison bundle. No input media/weights/cache archive."""
from pathlib import Path
import hashlib,json,zipfile
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path('outputs/bass-sequence');run=Path('outputs/runs/bass-sequence');dest=run/'贝斯多源序列对照.zip'
if dest.exists():raise FileExistsError('Preserve existing package')
files=set(p for p in run.rglob('*') if p.is_file());files.update(p for p in root.iterdir() if p.is_file() and p.name not in ['产物校验.json','压缩包校验.json'])
files.update(map(Path,['config/bass-sequence.lock.json','config/bass-evidence.lock.json','src/audio_midi/bass_sequence.py','tests/test_bass_sequence.py']))
trace=json.loads(Path('work/bass-diagnostics/replay/trace.json').read_text())
sourcepaths=[trace['input_path'],trace['stem_path'],'work/bass-models/ft-bass.wav','work/two-methods/sw-full/bass.wav','work/bass-diagnostics/replay/trace.json','work/bass-diagnostics/replay/frames.npz','work/bass-models/ft-receipt.json','work/two-methods/sw-full/separation-receipt.json']
for source in ['ft','sw']:
 for model in ['crepe','penn','pyin']:
  folder='work/bass-models' if model=='pyin' else 'work/bass-sequence';p=Path(folder)/(model+'-'+source+'.npz');sourcepaths.extend([str(p),str(p.with_suffix('.json'))])
for m in ['crepe','penn']:sourcepaths.extend([f'work/bass-models/{m}-full.npz',f'work/bass-models/{m}-full.json'])
sourcepaths.extend(['outputs/bass-models/run_pitch.py','outputs/bass-evidence/generate.py','outputs/bass-models/generate.py','src/audio_midi/bass_evidence.py','src/audio_midi/bass_refinement.py','src/audio_midi/bass_models.py'])
for rec in ['work/bass-models/crepe-full.json','work/bass-models/penn-full.json']:sourcepaths.append(json.loads(Path(rec).read_text())['weight_path'])
manifest={'files':[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)],'sources_not_bundled':[{'path':p,'sha256':sha(p)} for p in sorted(set(sourcepaths))],'protected_baseline':json.loads(Path('config/bass-evidence.lock.json').read_text()),'note':'local media, no studio reference or held-out claim'}
(root/'产物校验.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');files.add(root/'产物校验.json')
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(files):z.write(p,str(p))
with zipfile.ZipFile(dest) as z:
 assert z.testzip() is None and len(z.namelist())==len(files)
 for p in files:assert hashlib.sha256(z.read(str(p))).hexdigest()==sha(p)
result={'path':str(dest),'sha256':sha(dest),'bytes':dest.stat().st_size,'files':len(files),'manifest_sha256':sha(root/'产物校验.json')}
(root/'压缩包校验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result)
