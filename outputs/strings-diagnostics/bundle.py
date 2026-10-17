"""Hash-bound diagnostic-only local bundle; excludes original private inputs and weights."""
from pathlib import Path
import json,hashlib,zipfile
root=Path('outputs/strings-diagnostics');run=Path('outputs/runs/strings-diagnostics');zip_path=run/'弦乐诊断与试听.zip'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
if zip_path.exists():raise FileExistsError('Preserve diagnostic package')
files={p for p in run.rglob('*') if p.is_file()}|{p for p in root.iterdir() if p.is_file() and p.name not in ['来源与产物校验.json','压缩包校验.json']}
files.update(map(Path,['config/bass-frozen.lock.json','tests/test_strings_diagnostics.py']))
x=json.loads((root/'诊断结果.json').read_text());paths=set()
paths.add('outputs/two-methods/标准清单.json')
for e in json.loads(Path('outputs/two-methods/标准清单.json').read_text())['tracks'].values():paths.add(e['path'])
for r in x['rows'].values():paths.update([r['path'],r['raw_path'],r['stem_path'],str(Path(r['stem_path']).parent/'separation-receipt.json')])
for p in x['protected']:paths.add(p['path'])
paths.update(['config/bass-sequence.lock.json','work/v01/runtime/1792079033121801000/strings.npy','outputs/runs/v01/development/运行报告.json','outputs/runs/two-methods/sw-local-control/运行报告.json','src/audio_midi/backends/selected.py','src/audio_midi/quality.py','src/audio_midi/stitching.py','scripts/run_v01.py'])
paths.update(p['source'] for p in json.loads((root/'试听与片段.json').read_text())['clips'])
paths.add('work/models/GeneralUser-GS.sf2')
manifest={'files':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(files)],'sources_not_bundled':[{'path':str(p),'sha256':sha(p)} for p in sorted(paths)],'protected_bass':json.loads(Path('config/bass-frozen.lock.json').read_text()),'note':'analysis only; no prediction edits/model forward; source WAVs/reference not recording-session truth'}
(root/'来源与产物校验.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');files.add(root/'来源与产物校验.json')
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(files):z.write(p,str(p))
with zipfile.ZipFile(zip_path) as z:
 assert z.testzip() is None
 for p in files:assert hashlib.sha256(z.read(str(p))).hexdigest()==sha(p)
result={'path':str(zip_path),'sha256':sha(zip_path),'bytes':zip_path.stat().st_size,'files':len(files),'manifest_sha256':sha(root/'来源与产物校验.json')}
(root/'压缩包校验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result)
