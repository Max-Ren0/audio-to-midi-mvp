import subprocess
import pytest


def make_audio(path,seconds=1,codec='libmp3lame',freq=440):
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'sine=frequency={freq}:duration={seconds}','-c:a',codec,'-y',str(path)],check=True)


def test_decode_real_mp3_and_chinese_path(tmp_path):
    from audio_midi.audio import decode_mp3
    p=tmp_path/'中文音频.mp3'; make_audio(p)
    a=decode_mp3(p,16000)
    assert a.sample_rate==16000 and a.samples.ndim==1
    assert a.duration_seconds==pytest.approx(1,abs=.002)


def test_reject_disguised_wav(tmp_path):
    from audio_midi.audio import decode_mp3
    p=tmp_path/'fake.mp3'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=duration=1','-f','wav',str(p)],check=True)
    with pytest.raises(ValueError,match='MP3'): decode_mp3(p,16000)


def test_corrupt_mp3_rejected(tmp_path):
    from audio_midi.audio import decode_mp3
    p=tmp_path/'bad.mp3';p.write_bytes(b'not audio')
    with pytest.raises(ValueError): decode_mp3(p,16000)


def test_length_180_limit(tmp_path):
    from audio_midi.audio import decode_mp3
    p=tmp_path/'long.mp3';make_audio(p,181)
    with pytest.raises(ValueError,match='180'): decode_mp3(p,16000)


def test_silence_rejected(tmp_path):
    from audio_midi.audio import decode_mp3
    p=tmp_path/'silence.mp3';make_audio(p,freq=0)
    with pytest.raises(ValueError,match='静音'): decode_mp3(p,16000)


def test_exact_180_seconds_is_accepted(tmp_path):
    from audio_midi.audio import decode_mp3
    p=tmp_path/'boundary.mp3';make_audio(p,180)
    assert decode_mp3(p,16000).duration_seconds==180
