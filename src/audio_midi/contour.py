"""Monophonic transcription for separated lead-vocal and bass stems."""
from pathlib import Path
import numpy as np
from .events import NoteEvent,PROGRAMS


def contour_to_notes(pitches: np.ndarray, frame_seconds: float, category: str,
                     minimum_duration: float = .08, gap_seconds: float = .035,
                     smoothing_frames: int = 5, onsets_seconds=()) -> list[NoteEvent]:
    values=np.array(pitches,dtype=float,copy=True)
    max_gap=int(gap_seconds/frame_seconds)
    i=0
    while i<len(values):
        if np.isfinite(values[i]):i+=1;continue
        start=i
        while i<len(values) and not np.isfinite(values[i]):i+=1
        if start>0 and i<len(values) and i-start<=max_gap and round(values[start-1])==round(values[i]):
            values[start:i]=values[start-1]
    rounded=np.where(np.isfinite(values),np.rint(values),np.nan)
    original=rounded.copy();radius=smoothing_frames//2
    for i in range(radius,len(values)-radius):
        local=original[i-radius:i+radius+1]
        if np.isfinite(local).all():rounded[i]=np.median(local)
    attacks={round(t/frame_seconds) for t in onsets_seconds}
    result=[];start=0
    for i in range(1,len(rounded)+1):
        same=i<len(rounded) and (rounded[i]==rounded[start] or np.isnan(rounded[i]) and np.isnan(rounded[start]))
        if same and not (i in attacks and (i-start)*frame_seconds>=minimum_duration):continue
        if np.isfinite(rounded[start]) and (i-start)*frame_seconds>=minimum_duration-1e-9:
            pitch=int(rounded[start])
            if 0<=pitch<=127:
                result.append(NoteEvent(category,pitch,start*frame_seconds,i*frame_seconds,None,PROGRAMS[category]))
        start=i
    return result


def transcribe_monophonic(path: Path, category: str) -> list[NoteEvent]:
    import librosa
    import soundfile as sf
    y,sr=sf.read(path,dtype='float32',always_2d=True);y=y.mean(axis=1)
    target=22050 if category=='vocal' else 8000
    y=librosa.resample(y,orig_sr=sr,target_sr=target)
    hop=256 if category=='vocal' else 128
    low,high=(98,784) if category=='vocal' else (32,261)
    f0,voiced,probability=librosa.pyin(y,fmin=low,fmax=high,sr=target,frame_length=2048,hop_length=hop,fill_na=np.nan)
    rms=librosa.feature.rms(y=y,frame_length=2048,hop_length=hop)[0][:len(f0)]
    mask=voiced & (probability>=.2) & (rms>max(.001,float(rms.max())*.025))
    pitches=librosa.hz_to_midi(np.where(mask,f0,np.nan))
    onsets=librosa.onset.onset_detect(y=y,sr=target,hop_length=hop,units='time')
    return contour_to_notes(pitches,hop/target,category,onsets_seconds=onsets)
