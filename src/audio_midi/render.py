"""Offline sample-based rendering. Never opens an audio device."""
from pathlib import Path
import os
import tempfile
import mido
import numpy as np


def render_midi(midi_path: Path, soundfont_path: Path, output_path: Path,
                tail_seconds: float = 1.5) -> dict:
    import tinysoundfont
    import soundfile as sf
    output_path=Path(output_path)
    if output_path.exists():
        raise FileExistsError(f'已有音频输出，未覆盖：{output_path}')
    synth=tinysoundfont.Synth(gain=-6,samplerate=44100)
    sfid=synth.sfload(str(soundfont_path))
    for channel in range(16):
        synth.program_select(channel,sfid,128 if channel==9 else 0,0)
    blocks=[];seconds=0.;cursor=0
    for message in mido.MidiFile(midi_path):
        seconds+=message.time
        target=round(seconds*44100)
        if target>cursor:
            blocks.append(np.frombuffer(synth.generate_simple(target-cursor),dtype=np.float32).copy().reshape(-1,2))
            cursor=target
        if message.type=='program_change':
            synth.program_select(message.channel,sfid,128 if message.channel==9 else 0,message.program)
        elif message.type=='note_on' and message.velocity:
            synth.noteon(message.channel,message.note,message.velocity)
        elif message.type in ('note_on','note_off'):
            synth.noteoff(message.channel,message.note)
        elif message.type=='control_change' and message.control not in (0,32):
            synth.control_change(message.channel,message.control,message.value)
        elif message.type=='pitchwheel':
            synth.pitchbend(message.channel,message.pitch+8192)
    if tail_seconds>0:
        blocks.append(np.frombuffer(synth.generate_simple(round(tail_seconds*44100)),dtype=np.float32).copy().reshape(-1,2))
    if not blocks:
        raise ValueError('MIDI没有可渲染内容')
    audio=np.concatenate(blocks)
    peak=float(np.max(np.abs(audio)))
    if not np.isfinite(peak) or peak<1e-8:
        raise ValueError('音色渲染为空或无效')
    # One shared gain preserves track balance. No original audio is mixed in.
    gain=.90/peak
    audio*=gain
    output_path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_path.parent) as directory:
        temp=Path(directory)/'render.wav';sf.write(temp,audio,44100,subtype='PCM_16')
        os.link(temp,output_path)
    return {'sample_rate':44100,'duration_seconds':len(audio)/44100,'soundfont':Path(soundfont_path).name,'gain':gain,'source':'MIDI_only_no_original_audio'}
