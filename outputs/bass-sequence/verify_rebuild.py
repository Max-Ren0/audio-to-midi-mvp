"""Fresh temporary candidate and score rebuild; no model forward or data mutation."""
from pathlib import Path
import tempfile,subprocess,json,sys,numpy as np
root=Path('outputs/bass-sequence')
with tempfile.TemporaryDirectory(prefix='bass-sequence-rebuild-') as d:
 temp=Path(d);count=0
 for phase in [1,2,3,4]:
  out=temp/f'phase{phase}';ledger=temp/f'phase{phase}-ledger.json';choice=temp/f'phase{phase}-choice.json';scores=temp/f'phase{phase}-scores.json'
  cmd=[sys.executable,str(root/'generate.py'),str(phase),'--output',str(out),'--ledger',str(ledger)]
  if phase>1:cmd+=['--previous-choice',str(temp/f'phase{phase-1}-choice.json'),'--source-ledger',str(temp/'phase1-ledger.json')]
  subprocess.run(cmd,check=True)
  subprocess.run([sys.executable,str(root/'score.py'),str(phase),'--ledger',str(ledger),'--output',str(scores),'--choice',str(choice)],check=True)
  expected=json.loads((root/f'phase{phase}-ledger.json').read_text());actual=json.loads(ledger.read_text());assert len(expected['rows'])==len(actual['rows'])
  for a,b in zip(expected['rows'],actual['rows']):
   assert a['id']==b['id'] and a['sha256']==b['sha256']
   x=json.loads(Path(a['provenance_path']).read_text());y=json.loads(Path(b['provenance_path']).read_text())
   for key in ['notes','recipe','sources','evidence']:assert x[key]==y[key]
   count+=1
  for source in ['demucs','ft','sw']:
   ea=np.load(Path(expected['rows'][-1]['path']).parent/(source+'-features.npz'));aa=np.load(out/(source+'-features.npz'))
   for k in ea.files:np.testing.assert_array_equal(ea[k],aa[k])
  e=json.loads((root/f'phase{phase}-scores.json').read_text());a=json.loads(scores.read_text());assert e['selected']==a['selected']
  for x,y in zip(e['rows'],a['rows']):
   for key in ['matched','predicted','reference','extra','missed','f1','matched_pairs']:assert x[key]==y[key]
 bad=subprocess.run([sys.executable,str(root/'generate.py'),'1','--output',str(temp/'phase1'),'--ledger',str(temp/'guard.json')],capture_output=True)
 assert bad.returncode!=0 and b'Preserve existing output and ledger' in bad.stderr
 print('PASS',count,'stage rows including repeated controls; 10 IDs; MIDI/evidence/features/scores/choices; output guard')
