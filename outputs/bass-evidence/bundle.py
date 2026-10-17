"""Local-only bundle; media/cache files remain excluded from Git."""
from pathlib import Path
import hashlib,json,zipfile
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path('outputs/bass-evidence');run=Path('outputs/runs/bass-evidence');dest=run/'贝斯声学优化-75.00.zip'
if dest.exists():raise FileExistsError('Preserve existing package')
files=set(p for p in run.rglob('*') if p.is_file())
files.update(p for p in root.iterdir() if p.is_file() and p.name not in ['产物校验.json','压缩包校验.json'])
files.update(map(Path,['config/bass-evidence.lock.json','config/bass-models.lock.json','src/audio_midi/bass_evidence.py','tests/test_bass_evidence.py']))
sourcepaths=['work/bass-diagnostics/replay/frames.npz','work/bass-diagnostics/replay/trace.json','work/bass-models/crepe-full.npz','work/bass-models/crepe-full.json','work/bass-models/penn-full.npz','work/bass-models/penn-full.json']
trace=json.loads(Path(sourcepaths[1]).read_text());sourcepaths.extend([trace['input_path'],trace['stem_path']])
manifest={'files':[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)],'sources_not_bundled':[{'path':p,'sha256':sha(p)} for p in sourcepaths],'protected_baseline':json.loads(Path('config/bass-models.lock.json').read_text()),'note':'local-only media and evidence; no studio truth/held-out claim'}
(root/'产物校验.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');files.add(root/'产物校验.json')
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(files):z.write(p,str(p))
with zipfile.ZipFile(dest) as z:
 assert z.testzip() is None and len(z.namelist())==len(files)
 for p in files:assert hashlib.sha256(z.read(str(p))).hexdigest()==sha(p)
result={'path':str(dest),'sha256':sha(dest),'bytes':dest.stat().st_size,'files':len(files),'manifest_sha256':sha(root/'产物校验.json')}
(root/'压缩包校验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result)
