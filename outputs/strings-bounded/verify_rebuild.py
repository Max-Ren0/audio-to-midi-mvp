"""Temporary, no-forward rebuild including historical preregistration amendments."""
from pathlib import Path
import tempfile,subprocess,sys,json,hashlib
root=Path('outputs/strings-bounded')
def run(file,*args):subprocess.run([sys.executable,str(root/file),*map(str,args)],check=True)
def check_row(old,new):
 assert old['id']==new['id'] and old['sha256']==new['sha256']
 a=json.loads(Path(old['detail_path']).read_text());b=json.loads(Path(new['detail_path']).read_text());assert a==b
 for k in ['score','duration_pitch','duration_chroma']:
  if k in old:assert old[k]==new[k]
with tempfile.TemporaryDirectory(prefix='strings-bounded-rebuild-') as directory:
 temp=Path(directory)
 # Matrix was created before the two disclosed amendments: replay its actual committed registration.
 text=subprocess.check_output(['git','show','1ed0a2a:outputs/strings-bounded/实验登记.json'])
 reg=temp/'matrix-registration.json';reg.write_bytes(text)
 ledger=json.loads((root/'matrix-ledger.json').read_text());assert hashlib.sha256(text).hexdigest()==ledger['registration_sha256']
 ml=temp/'matrix-ledger.json';ms=temp/'matrix-scores.json'
 run('make_matrix.py','--output',temp/'matrix','--ledger',ml,'--registration',reg)
 run('score_matrix.py','--ledger',ml,'--output',ms)
 old=json.loads((root/'matrix-scores.json').read_text());new=json.loads(ms.read_text())
 assert old['target_presence_and_original_labels']==new['target_presence_and_original_labels']
 for a,b in zip(old['rows'],new['rows']):check_row(a,b)
 for cell,prefix in [('C',''),('A','A-')]:
  pl=temp/(prefix+'post-ledger.json');shortout=temp/(prefix+'post')
  run('postprocess.py','--cell',cell,'--matrix-ledger',ml,'--output',shortout,'--ledger',pl)
  choice=temp/(prefix+'short-choice.json');score=temp/(prefix+'short-scores.json')
  run('score_post.py','short','--ledger',pl,'--output',score,'--choice',choice)
  for stage in ['short','merge','harmonic']:
   if stage!='short':
    prev=choice;pl=temp/(prefix+stage+'-ledger.json');choice=temp/(prefix+stage+'-choice.json');score=temp/(prefix+stage+'-scores.json')
    run('continue_post.py',stage,'--id-prefix',prefix,'--previous-choice',prev,'--output',temp/(prefix+stage),'--ledger',pl)
    run('score_post.py',stage,'--ledger',pl,'--output',score,'--choice',choice)
   old=json.loads((root/(prefix+stage+'-scores.json')).read_text());new=json.loads(score.read_text());assert old['exploratory_selected']==new['exploratory_selected']
   for a,b in zip(old['rows'],new['rows']):check_row(a,b)
 run('compare_shift.py','--output',temp/'shift.json','--diagnostic-dir',temp/'shifted','--overlap-dir',temp/'overlap','--score-dir',temp,'--other-choice',temp/'A-harmonic-choice.json','--mix-choice',temp/'harmonic-choice.json')
 old=json.loads((root/'shift-comparison.json').read_text());new=json.loads((temp/'shift.json').read_text())
 assert old['replay']==new['replay']
 for source in ['other','mix']:
  for k in ['boundary_count','comparable','moving_with_halfblock','positive_signal','details']:assert old['sources'][source][k]==new['sources'][source][k]
  check_row(old['sources'][source]['shifted_diagnostic'],new['sources'][source]['shifted_diagnostic'])
 bad=subprocess.run([sys.executable,str(root/'make_matrix.py'),'--output',str(temp/'matrix'),'--ledger',str(temp/'blocked.json')],capture_output=True)
 assert bad.returncode!=0 and b'Preserve matrix' in bad.stderr
 print('PASS:4matrix+8post+2shift controls MIDI/notes/evidence/metrics/decisions;4event captures replayed;historical registration preserved;existing-output guard')
