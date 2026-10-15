from dataclasses import dataclass
from pathlib import Path
import json
import subprocess
import numpy as np

@dataclass(frozen=True)
class AudioData:
    samples: np.ndarray
    sample_rate: int
    duration_seconds: float


def decode_mp3(path: Path, sample_rate: int = 16000) -> AudioData:
    path=Path(path).resolve()
    if path.suffix.lower()!='.mp3' or not path.is_file():
        raise ValueError('仅支持存在的本地 MP3 文件')
    if not isinstance(sample_rate,int) or sample_rate<=0:
        raise ValueError('无效采样率')
    try:
        probe=subprocess.run(['ffprobe','-v','error','-select_streams','a','-show_entries','stream=codec_name','-of','json',str(path)],capture_output=True,check=True,timeout=10)
        streams=json.loads(probe.stdout)['streams']
        if len(streams)!=1 or streams[0].get('codec_name')!='mp3':
            raise ValueError('输入必须包含一条 MP3 编码音轨')
        # Decode at most 181 seconds: bounded memory, no successful truncated output.
        decoded=subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(path),'-map','0:a:0','-t','181','-ac','1','-ar',str(sample_rate),'-f','f32le','pipe:1'],capture_output=True,check=True,timeout=30)
    except FileNotFoundError as e:
        raise ValueError('需要安装 FFmpeg 和 FFprobe') from e
    except (subprocess.SubprocessError,KeyError,json.JSONDecodeError) as e:
        raise ValueError('MP3 损坏、解码失败或解码超时') from e
    samples=np.frombuffer(decoded.stdout,dtype='<f4').copy()
    duration=len(samples)/sample_rate
    if duration>180:
        # Probe length is explanatory only; acceptance is based on decoded samples.
        detail=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)],capture_output=True,timeout=5)
        try:
            estimated=float(json.loads(detail.stdout)['format']['duration'])
            label=f'文件声明约 {estimated:.2f} 秒，实际解码确认超过 180 秒'
        except (ValueError,KeyError,json.JSONDecodeError):
            label='实际解码长度超过 180 秒'
        raise ValueError(label+'；已拒绝，不自动截断')
    if not len(samples) or not np.isfinite(samples).all():
        raise ValueError('无有效音频采样')
    if np.max(np.abs(samples))<1e-6:
        raise ValueError('静音：无有效转谱结果')
    return AudioData(samples,sample_rate,duration)
