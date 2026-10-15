"""Read-only scoring with a supplied common alignment; never changes predictions."""
import argparse,hashlib,json
from pathlib import Path
from audio_midi.quality import read_notes,metrics

def main():
    p=argparse.ArgumentParser();p.add_argument('reference',type=Path);p.add_argument('prediction',type=Path);p.add_argument('--duration',type=float,required=True);p.add_argument('--scale',type=float,default=.9995);p.add_argument('--shift',type=float,default=.14);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    d=metrics(read_notes(a.reference),read_notes(a.prediction),a.scale,a.shift,a.duration)
    d['reference_sha256']=hashlib.sha256(a.reference.read_bytes()).hexdigest();d['prediction_sha256']=hashlib.sha256(a.prediction.read_bytes()).hexdigest()
    d['scope']='six instruments, exact pitch/category, 50ms onset, one-to-one; shared alignment; no vocals'
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(d,ensure_ascii=False,indent=2));print(json.dumps(d,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
