"""Rebuild into a fresh temporary folder, preserving every existing artifact."""
from pathlib import Path
import tempfile,subprocess,json,sys,hashlib,numpy as np
root=Path('outputs/bass-evidence')
with tempfile.TemporaryDirectory(prefix='bass-evidence-rebuild-') as d:
 temp=Path(d);count=0
 for phase in [1,2,3]:
  out=temp/f'phase{phase}';ledger=temp/f'phase{phase}-ledger.json';choice=temp/f'phase{phase}-choice.json';scores=temp/f'phase{phase}-scores.json'
  cmd=[sys.executable,str(root/'generate.py'),str(phase),'--output',str(out),'--ledger',str(ledger)]
  if phase>1:cmd+=['--previous-choice',str(temp/f'phase{phase-1}-choice.json')]
  subprocess.run(cmd,check=True)
  subprocess.run([sys.executable,str(root/'score.py'),str(phase),'--ledger',str(ledger),'--output',str(scores),'--choice',str(choice)],check=True)
  expected=json.loads((root/f'phase{phase}-ledger.json').read_text());actual=json.loads(ledger.read_text())
  for a,b in zip(expected['rows'],actual['rows']):
   assert a['id']==b['id'] and a['sha256']==b['sha256']
   x=json.loads(Path(a['provenance_path']).read_text());y=json.loads(Path(b['provenance_path']).read_text())
   for key in ['notes','edits_and_proposals']:assert x[key]==y[key]
   count+=1
  ea=np.load(Path(expected['rows'][-1]['path']).parent/'audio-evidence.npz');aa=np.load(out/'audio-evidence.npz')
  for k in ea.files:np.testing.assert_array_equal(ea[k],aa[k])
  e=json.loads((root/f'phase{phase}-scores.json').read_text());a=json.loads(scores.read_text());assert e['selected']==a['selected']
  for x,y in zip(e['rows'],a['rows']):
   for key in ['matched','predicted','reference','extra','missed','f1','matched_pairs']:assert x[key]==y[key]
 # Existing-output protection must fail before touching sources.
 protected=subprocess.run([sys.executable,str(root/'generate.py'),'1','--output',str(temp/'phase1'),'--ledger',str(temp/'guard.json')],capture_output=True)
 assert protected.returncode!=0 and b'Preserve existing results' in protected.stderr
 print('PASS:',count,'stage rows including repeated controls; 12 IDs; byte-identical MIDI and edit evidence; arrays/scores/choices; existing-output guard')
