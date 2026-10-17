"""Four cells from existing hash-audited caches, no reference input."""
from common import *
import argparse,numpy as np,soundfile as sf
from scipy.signal import resample_poly
from audio_midi.audio import decode_mp3
from audio_midi.stitching import clean_notes
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=RUN/'matrix');p.add_argument('--ledger',type=Path,default=ROOT/'matrix-ledger.json');p.add_argument('--registration',type=Path,default=ROOT/'实验登记.json');a=p.parse_args()
if a.output.exists() or a.ledger.exists():raise FileExistsError('Preserve matrix')
freeze=protect();input_path=Path('/Users/ringscherry/Desktop/吉他产品/v0.0/test/李荣浩 - 不将就-[AudioTrimmer.com].mp3');lock=json.loads(Path(freeze['lock_path']).read_text());assert sha(input_path)==lock['input_sha256']
mix_npy=Path('work/v01/runtime/1792079033121801000/mix.npy');np.testing.assert_array_equal(np.load(mix_npy),decode_mp3(input_path).samples)
y,sr=sf.read('work/two-methods/sw-full/other.wav',dtype='float32',always_2d=True);other_npy=Path('work/v01/runtime/1792079033121801000/strings.npy');np.testing.assert_array_equal(np.load(other_npy),resample_poly(y.mean(axis=1),160,441).astype('float32'))
source_paths={'other':Path('work/v01/runtime/1792079033121801000/strings.json'),'mix':Path('work/v01/runtime/1792079033121801000/mix.json')}
raw={s:json.loads(p.read_text()) for s,p in source_paths.items()};rows=[]
for id,source,filter_labels in [('A','other',True),('B','other',False),('C','mix',True),('D','mix',False)]:
 original=[n for n in raw[source]['notes'] if n['category']=='strings' if filter_labels] if filter_labels else [n for n in raw[source]['notes'] if n['category'] not in ['vocal','drums']]
 notes=clean_notes([replace(NoteEvent(**n),category='strings',program=48) for n in original],DURATION)
 evidence={'source':source,'strings_label_filter':filter_labels,'raw_path':str(source_paths[source]),'raw_sha256':sha(source_paths[source]),'original_notes':original,'input_path':str(other_npy if source=='other' else mix_npy),'input_sha256':sha(other_npy if source=='other' else mix_npy),'registration_sha256':sha(a.registration),'note':'all-pitched projection is diagnostic, not recovered strings identity'}
 rows.append(save(id,notes,a.output,evidence))
(a.ledger).write_text(json.dumps({'rows':rows,'source_hashes':{str(p):sha(p) for p in [input_path,mix_npy,other_npy,*source_paths.values()]},'registration_sha256':sha(a.registration)},ensure_ascii=False,indent=2)+'\n');protect();print([(r['id'],r['predicted']) for r in rows])
