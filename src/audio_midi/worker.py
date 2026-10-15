from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
import time
import psutil

@dataclass(frozen=True)
class WorkerResult:
    peak_memory_bytes: int
    attempts: int
    elapsed_seconds: float

class WorkerError(RuntimeError):
    def __init__(self,message,peak_memory_bytes=0,attempts=0):
        super().__init__(message)
        self.peak_memory_bytes=peak_memory_bytes
        self.attempts=attempts


def run_command(command: list[str], deadline: float, log_path: Path, memory_limit_bytes: int | None = None) -> WorkerResult:
    start=time.monotonic(); peak=0
    log_path.parent.mkdir(parents=True,exist_ok=True)
    for attempt in (1,2):
        if time.monotonic()>=deadline:
            raise WorkerError('处理超时',peak,attempt-1)
        env=os.environ.copy()
        env.update({'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','NUMBA_NUM_THREADS':'2','MKL_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false','PYTHONUNBUFFERED':'1','AUDIO_MIDI_BATCH_SIZE':str(2 if attempt==1 else 1)})
        reason=None
        with log_path.open('ab') as log:
            process=subprocess.Popen(command,stdout=log,stderr=log,start_new_session=True,env=env)
            try:
                while process.poll() is None:
                    rss=0
                    try:
                        root=psutil.Process(process.pid)
                        rss=sum(p.memory_info().rss for p in [root,*root.children(recursive=True)] if p.is_running())
                        peak=max(peak,rss)
                    except (psutil.NoSuchProcess,psutil.AccessDenied):
                        pass
                    if time.monotonic()>=deadline:
                        reason='处理超时'; break
                    if memory_limit_bytes and rss>memory_limit_bytes:
                        reason='内存超过上限'; break
                    time.sleep(.03)
            finally:
                if process.poll() is None:
                    try: os.killpg(process.pid,signal.SIGTERM)
                    except ProcessLookupError: pass
                    try: process.wait(timeout=.5)
                    except subprocess.TimeoutExpired:
                        pass
                # The leader exiting does not imply its descendants exited.
                # Always finish cleanup of our dedicated process group.
                try: os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait()
            if reason=='处理超时':
                raise WorkerError(reason,peak,attempt)
            if reason is None and process.returncode==0:
                return WorkerResult(peak,attempt,time.monotonic()-start)
        if attempt==2:
            detail=log_path.read_text(errors='replace')[-2000:]
            raise WorkerError(reason or f'模型执行失败，详情见 {log_path}: {detail}',peak,attempt)
    raise AssertionError('unreachable')
