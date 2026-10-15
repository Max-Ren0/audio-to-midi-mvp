import argparse
from dataclasses import fields
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import sys
import urllib.request
import psutil
from .events import NoteEvent

WEIGHT_URL='https://huggingface.co/spaces/mimbres/YourMT3/resolve/5e66c1ea173a8186e0d20432b841d3180cc015b5/amt/logs/2024/mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b36_nops/checkpoints/last.ckpt'


def prepare(path: Path) -> dict:
    from .backends.selected import WEIGHT_SHA256
    def digest(p):
        with p.open('rb') as f:
            return hashlib.file_digest(f,'sha256').hexdigest()
    if path.is_file() and digest(path)==WEIGHT_SHA256:
        return {'status':'ready','checkpoint':str(path),'sha256':WEIGHT_SHA256}
    if path.exists():
        raise ValueError('已有模型文件校验不符，不自动覆盖；请指定新的 --checkpoint 路径')
    path.parent.mkdir(parents=True,exist_ok=True)
    import tempfile
    with tempfile.TemporaryDirectory(dir=path.parent) as directory:
        temp=Path(directory)/'weight'
        request=urllib.request.Request(WEIGHT_URL,headers={'User-Agent':'audio-midi-mvp/0.0'})
        with urllib.request.urlopen(request,timeout=60) as response,temp.open('wb') as output:
            shutil.copyfileobj(response,output)
        if digest(temp)!=WEIGHT_SHA256:
            raise ValueError('下载的模型权重校验失败')
        import os
        os.link(temp,path)
    return {'status':'ready','checkpoint':str(path),'sha256':WEIGHT_SHA256}


def _read_notes(path):
    payload=json.loads(Path(path).read_text())
    raw=payload['notes'] if isinstance(payload,dict) else payload
    allowed={f.name for f in fields(NoteEvent)}
    return [NoteEvent(**{k:v for k,v in n.items() if k in allowed}) for n in raw]


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description='实验版：本地 MP3 → 可编辑多轨 MIDI（七类质量未验收）')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='检查运行环境')
    prep=sub.add_parser('prepare',help='下载并校验固定模型权重')
    prep.add_argument('--checkpoint',type=Path,default=Path('work/models/yourmt3.ckpt'))
    trans=sub.add_parser('transcribe',help='转录不超过180秒的 MP3')
    trans.add_argument('input',type=Path);trans.add_argument('--output',type=Path,required=True)
    trans.add_argument('--checkpoint',type=Path,default=Path('work/models/yourmt3.ckpt'))
    trans.add_argument('--device',choices=['cpu','mps'],default='cpu')
    trans.add_argument('--memory-limit-gib',type=float,default=3.2,help='默认3.2 GiB，依据本机CPU实测峰值加30%向上取整；其他机器须重测')
    trans.add_argument('--overwrite',action='store_true')
    ev=sub.add_parser('evaluate',help='比较人工标注与预测音符 JSON（单样本不判定类别达标）')
    ev.add_argument('reference',type=Path);ev.add_argument('prediction',type=Path)
    ds=sub.add_parser("evaluate-dataset",help="按真实歌曲清单汇总评测")
    ds.add_argument("manifest",type=Path)
    a=parser.parse_args(argv)
    try:
        if a.command=='doctor':
            deps={}
            for name in ('numpy','mido','torch','mt3-infer','transformers'):
                try: deps[name]=importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError: deps[name]=None
            result={'python':platform.python_version(),'machine':platform.platform(),'ffmpeg':shutil.which('ffmpeg'),
                    'ffprobe':shutil.which('ffprobe'),'memory_bytes':psutil.virtual_memory().total,'dependencies':deps}
        elif a.command=='prepare':
            result=prepare(a.checkpoint)
        elif a.command=='transcribe':
            from .pipeline import transcribe_file
            if a.memory_limit_gib is not None and not 0<a.memory_limit_gib<1024:
                raise ValueError('无效内存上限')
            result=transcribe_file(a.input,a.output,a.checkpoint,a.device,a.overwrite,
                 None if a.memory_limit_gib is None else int(a.memory_limit_gib*1024**3))
            result={k:v for k,v in result.items() if k!='notes'}
        elif a.command=='evaluate-dataset':
            from .evaluate import evaluate_dataset
            payload=json.loads(a.manifest.read_text());records=[]
            for sample in payload['samples']:
                records.append({'id':sample['id'],'kind':sample['kind'],'contains':sample['contains'],
                 'reference':_read_notes(a.manifest.parent/sample['reference']),
                 'predicted':_read_notes(a.manifest.parent/sample['prediction'])})
            result={'metrics':evaluate_dataset(records),'warning':'阈值为规格提议；合成样本不计入真实歌曲数量'}
        else:
            from .evaluate import evaluate
            result={'classification':'insufficient_samples','metrics':evaluate(_read_notes(a.reference),_read_notes(a.prediction)),
                    'warning':'单样本仅报告数据，每类至少5首含该类别的真实标注歌曲才可判定'}
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (ValueError,OSError,RuntimeError,TimeoutError,KeyError,TypeError) as e:
        print(json.dumps({'status':'failed','error':str(e)},ensure_ascii=False),file=sys.stderr);return 2

if __name__=='__main__':
    raise SystemExit(main())
