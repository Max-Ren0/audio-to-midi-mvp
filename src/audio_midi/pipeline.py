from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import time
import numpy as np
from .audio import decode_mp3
from .events import CATEGORIES,NoteEvent
from .midi import write_midi
from .stitching import clean_notes
from .worker import run_command


def publish(files: list[tuple[Path,Path]], overwrite: bool) -> None:
    """Stage first; publish without clobber races, rolling back failures."""
    for _,target in files:
        if target.is_symlink() or (target.exists() and not overwrite):
            raise FileExistsError(f'已有同名输出，未覆盖：{target}')
    created=[]; backups={}
    with tempfile.TemporaryDirectory(dir=files[0][1].parent) as directory:
        try:
            for i,(source,target) in enumerate(files):
                if overwrite and target.exists():
                    backup=Path(directory)/str(i);shutil.copy2(target,backup);backups[target]=backup
                if overwrite:
                    os.replace(source,target)
                else:
                    os.link(source,target)
                created.append(target)
        except BaseException:
            for target in reversed(created):
                if target in backups:
                    os.replace(backups[target],target)
                else:
                    target.unlink(missing_ok=True)
            raise


def transcribe_file(input_path: Path, output_path: Path, checkpoint: Path,
                    device: str='cpu', overwrite: bool=False,
                    memory_limit_bytes: int | None=int(3.2*1024**3)) -> dict:
    start=time.monotonic()
    input_path=Path(input_path).resolve();output_path=Path(output_path).absolute()
    report_path=output_path.with_suffix('.report.json')
    if output_path.suffix.lower() not in ('.mid','.midi'):
        raise ValueError('输出文件必须为 .mid 或 .midi')
    for p in (output_path,report_path):
        if p.is_symlink() or (p.exists() and not overwrite):
            raise FileExistsError(f'已有同名输出，未覆盖：{p}')
    audio=decode_mp3(input_path,16000)
    checkpoint=Path(checkpoint).resolve()
    if not checkpoint.is_file():
        raise ValueError('尚未准备模型权重；请先运行 audio-midi prepare')
    deadline=start+audio.duration_seconds*3
    if time.monotonic()>=deadline:
        raise TimeoutError('处理超时（包含输入解码）')
    output_path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='audio-midi-',dir=output_path.parent) as directory:
        root=Path(directory);source=root/'input.npy';raw=root/'raw.json'
        np.save(source,audio.samples)
        log_path=Path('work/logs')/f'{time.time_ns()}.log'
        worker=run_command([sys.executable,'-m','audio_midi.backends.selected',str(source),str(checkpoint),str(raw),'--device',device],deadline,log_path,memory_limit_bytes)
        data=json.loads(raw.read_text())
        notes=clean_notes([NoteEvent(**n) for n in data.pop('notes')],audio.duration_seconds)
        if not notes:
            raise ValueError('无有效转谱结果：未输出空 MIDI；可能为纯讲话或模型未能识别')
        present={n.category for n in notes}
        warnings=['实验版：七类识别质量尚未经完整人工标注评测','120 BPM 与 4/4 为默认值，未经检测；时间未量化','未识别到某类别不代表原曲不存在该乐器','尚无可靠纯讲话检测，语音误识别风险仍需人工检查']
        if memory_limit_bytes is None:
            warnings.append('本次为内存校准运行，未设置硬内存上限；正式配置须以实测峰值加30%确定')
        if any(data.get('decode_errors',{}).values()):
            warnings.append('模型解码产生错误计数，可能漏音或截断；详情见 model.decode_errors，需人工复查')
        missing=[c for c in CATEGORIES if c not in present]
        report={'schema_version':1,'status':'partial' if missing else 'unvalidated',
          'duration_seconds':audio.duration_seconds,'bpm':120,'bpm_source':'default','time_signature':'4/4','quantized':False,
          'missing_categories':missing,'note_count':len(notes),'category_counts':{c:sum(n.category==c for n in notes) for c in CATEGORIES},
          'notes':[asdict(n) for n in notes],'warnings':warnings,
          'peak_memory_bytes':worker.peak_memory_bytes,'memory_limit_bytes':memory_limit_bytes,'attempts':worker.attempts,
          'machine':{'system':platform.platform(),'architecture':platform.machine()},'model':data,
          'input_sha256':hashlib.file_digest(input_path.open('rb'),'sha256').hexdigest(),
          'quality_metrics':None,'quality_status':'not_evaluated_no_annotations','log_path':str(log_path)}
        midi=root/'result.mid';write_midi(notes,midi)
        report['total_seconds']=time.monotonic()-start
        if report['total_seconds']>audio.duration_seconds*3:
            raise TimeoutError('处理超时：未交付半成品')
        report_file=root/'report.json';report_file.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        publish([(midi,output_path),(report_file,report_path)],overwrite)
    return report
