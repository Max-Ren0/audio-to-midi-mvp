"""Finite postprocessing on fixed C probe; scoring is diagnostic, not promotion."""
from common import *
from audio_midi.strings_bounded import merge_same_pitch,harmonic_prune
import argparse,numpy as np
p=argparse.ArgumentParser();p.add_argument('--cell',choices=['A','C'],default='C');p.add_argument('--matrix-ledger',type=Path,default=ROOT/'matrix-ledger.json');p.add_argument('--output',type=Path,default=RUN/'postprocess');p.add_argument('--ledger',type=Path,default=ROOT/'post-ledger.json');p.add_argument('--registration',type=Path,default=ROOT/'实验登记.json');a=p.parse_args()
if a.output.exists() or a.ledger.exists():raise FileExistsError('Preserve postprocessing')
protect();parent=next(r for r in json.loads(a.matrix_ledger.read_text())['rows'] if r['id']==a.cell);data=read_detail(parent);notes=[NoteEvent(**n) for n in data['notes']];short=[]
for minimum,id in [(.08,'S80'),(.12,'S120')]:
 id=id if a.cell=='C' else 'A-'+id
 deleted=[{'index':i,'note':asdict(n),'reason':'duration below'+str(minimum)} for i,n in enumerate(notes) if n.offset-n.onset<minimum-1e-9]
 out=[n for n in notes if n.offset-n.onset>=minimum-1e-9];short.append(save(id,out,a.output,{'parent':parent['id'],'minimum':minimum,'deletions':deleted}))
# Write unscored proposals. Later score/selection is a separate invocation before merge generation.
a.ledger.write_text(json.dumps({'parent':parent,'rows':short,'registration_sha256':sha(a.registration)},ensure_ascii=False,indent=2)+'\n');print([(r['id'],r['predicted']) for r in short])
