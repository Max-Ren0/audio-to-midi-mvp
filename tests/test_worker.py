import sys
import time
import pytest


def test_child_timeout_and_no_unbounded_retry(tmp_path):
    from audio_midi.worker import run_command, WorkerError
    start=time.monotonic()
    with pytest.raises(WorkerError,match='超时'):
        run_command([sys.executable,'-c','import time; time.sleep(5)'],deadline=start+.3,log_path=tmp_path/'log')
    assert time.monotonic()-start<2


def test_retry_once_for_failure(tmp_path):
    from audio_midi.worker import run_command, WorkerError
    p=tmp_path/'count'
    script=f'from pathlib import Path; p=Path({str(p)!r}); p.write_text(p.read_text()+"x" if p.exists() else "x"); raise SystemExit(1)'
    with pytest.raises(WorkerError):
        run_command([sys.executable,'-c',script],deadline=time.monotonic()+5,log_path=tmp_path/'log')
    assert p.read_text()=='xx'


def test_success_records_memory(tmp_path):
    from audio_midi.worker import run_command
    r=run_command([sys.executable,'-c','import time; time.sleep(.15)'],deadline=time.monotonic()+3,log_path=tmp_path/'log')
    assert r.attempts==1 and r.peak_memory_bytes>0


def test_memory_limit_kills_child(tmp_path):
    from audio_midi.worker import run_command,WorkerError
    with pytest.raises(WorkerError,match='内存'):
        run_command([sys.executable,'-c','import time; b=bytearray(40_000_000); time.sleep(5)'],deadline=time.monotonic()+3,log_path=tmp_path/'log',memory_limit_bytes=15_000_000)


def test_timeout_kills_descendant_ignoring_sigterm(tmp_path):
    import os,signal
    import psutil
    from audio_midi.worker import run_command,WorkerError
    marker=tmp_path/'child.pid'
    child=f'import os,signal,time; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); Path({str(marker)!r}).write_text(str(os.getpid())); time.sleep(30)'
    parent=f'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",{child!r}]); time.sleep(30)'
    pid=None
    try:
        with pytest.raises(WorkerError,match='超时'):
            run_command([sys.executable,'-c',parent],deadline=time.monotonic()+1,log_path=tmp_path/'log')
        assert marker.exists()
        pid=int(marker.read_text());time.sleep(.1)
        assert not psutil.pid_exists(pid) or psutil.Process(pid).status()==psutil.STATUS_ZOMBIE
    finally:
        if pid and psutil.pid_exists(pid):
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
