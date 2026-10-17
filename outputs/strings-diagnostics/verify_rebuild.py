"""Safe temporary rebuild of diagnostics and freeze record; no model forward."""
import tempfile,subprocess,sys,json
from pathlib import Path
root=Path('outputs/strings-diagnostics')
with tempfile.TemporaryDirectory(prefix='strings-diag-') as t:
 out=Path(t)/'diagnostics.json';freeze=Path(t)/'freeze.json'
 subprocess.run([sys.executable,str(root/'analyze.py'),'--output',str(out),'--freeze-output',str(freeze)],check=True)
 assert out.read_bytes()==(root/'诊断结果.json').read_bytes()
 assert freeze.read_bytes()==Path('config/bass-frozen.lock.json').read_bytes()
 bad=subprocess.run([sys.executable,str(root/'analyze.py'),'--output',str(out),'--freeze-output',str(freeze)],capture_output=True)
 assert bad.returncode!=0 and b'Preserve diagnostics and freeze record' in bad.stderr
 print('PASS: diagnosis/freeze byte-identical; existing output guard; original artifacts untouched')
