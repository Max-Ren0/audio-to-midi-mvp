from pathlib import Path
import json,hashlib,shutil,zipfile
from audio_midi.render import render_midi

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path('outputs/runs/drums-v2/交付');aud=root/'代表方案试听';aud.mkdir(exist_ok=True)
comparisons=[('01-原始鼓56',Path('outputs/runs/v01/development/单轨/drums.mid')),('02-上版鼓77',Path('outputs/runs/drums/development/H2-Demucs-YourMT3-SW-ADTOF-lower075/鼓.mid')),('03-OAF-SW',Path('outputs/runs/drums-v2/candidates/control-oafsw.mid')),('04-OAF-Demucs',Path('outputs/runs/drums-v2/candidates/control-oafdemucs.mid')),('05-阶段一83',Path('outputs/runs/drums-v2/candidates/adtof-s0.3-h0.165__oaf-gated-ride.mid')),('06-阶段二84',Path('outputs/runs/drums-v2/stage2/ride-cy0.15-tol0.03.mid')),('07-阶段三84',Path('outputs/runs/drums-v2/stage3/combo-1.mid'))]
idm=json.loads(Path('outputs/drums-v2/IDM评分.json').read_text())['candidates']
for source in ['sw','demucs']:
 row=next(r for r in idm if r['mode']=='solo' and r['id'].startswith('idm-'+source));comparisons.append(('08-IDM-'+source,Path(row['path'])))
for name,source in comparisons:
 target=aud/(name+'.mid');shutil.copy2(source,target);render_midi(target,Path('work/models/GeneralUser-GS.sf2'),aud/(name+'.wav'))
# All 188 declared candidate results, including two legitimate empty IDM controls.
allrows=[]
for filename in ['阶段一评分.json','阶段二评分.json','阶段三评分.json','IDM评分.json','阶段四评分.json','最终评分.json']:
 d=json.loads((Path('outputs/drums-v2')/filename).read_text());dest=root/'全部候选MID'/Path(filename).stem;dest.mkdir(parents=True)
 for row in d['candidates']:
  source=Path(row['path']);assert sha(source)==row['sha256'];shutil.copy2(source,dest/source.name);allrows.append(row)
 shutil.copy2(Path('outputs/drums-v2')/filename,root/filename)
report=json.loads(Path('outputs/drums-v2/交付校验.json').read_text());report['declared_candidates']=len(allrows);report['unique_candidate_midi_hashes']=len(set(r['sha256'] for r in allrows));report['representative_auditions']=len(comparisons)+2
report['artifacts']={str(p.relative_to(root)):{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in root.rglob('*') if p.is_file()}
Path('outputs/drums-v2/交付校验.json').write_text(json.dumps(report,indent=2));print({k:report[k] for k in ['declared_candidates','unique_candidate_midi_hashes','representative_auditions']})
