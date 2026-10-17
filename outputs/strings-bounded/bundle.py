"""Immutable local bundle; inputs/weights are hashed, never embedded."""
from common import *
import zipfile
protect()
manifest=RUN/'交付清单.json';archive=RUN/'弦乐-有限诊断与后处理探索.zip'
if manifest.exists() or archive.exists():raise FileExistsError('Preserve frozen bundle')
files=sorted(p for p in RUN.rglob('*') if p.is_file())
files+=sorted(p for p in ROOT.iterdir() if p.suffix in {'.py','.json','.md','.csv'} and p.name!='打包记录.json')
files += [Path('src/audio_midi/strings_bounded.py'),Path('tests/test_strings_bounded.py'),Path('pyproject.toml'),Path('uv.lock')]
files+=sorted(p for p in Path('work/strings-bounded').rglob('*') if p.is_file())
files=list(dict.fromkeys(files))
protected=protect();sources=[Path('/Users/ringscherry/Desktop/吉他产品/v0.0/test/李荣浩 - 不将就-[AudioTrimmer.com].mp3'),Path('/Users/ringscherry/.codex/attachments/892492b7-6157-4e77-a757-de3de435e2c7/06-弦乐.mid'),Path('work/models/GeneralUser-GS.sf2')]
sources += [Path(r['path']) for r in [protected['bass'],protected['six_track'],*protected['implementation']]]
records=[{'path':str(p),'size':p.stat().st_size,'sha256':sha(p)} for p in files]
manifest.write_text(json.dumps({'artifacts':records,'sources_not_bundled':[{'path':str(p),'sha256':sha(p)} for p in sources],'scope':'0–60 diagnostic only; 7 references; no default replacement; local bundle only'},ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
 for p in files+[manifest]:z.write(p,str(p))
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for r in records:assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256']
(ROOT/'打包记录.json').write_text(json.dumps({'archive':str(archive),'sha256':sha(archive),'manifest':str(manifest),'manifest_sha256':sha(manifest),'artifacts':len(records),'zip_members':len(records)+1},ensure_ascii=False,indent=2)+'\n')
print('bundle verified',len(records),sha(archive))
