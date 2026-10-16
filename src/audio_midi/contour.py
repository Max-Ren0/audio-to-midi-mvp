"""Monophonic transcription for separated lead-vocal and bass stems."""
from pathlib import Path
import numpy as np
from .events import NoteEvent,PROGRAMS


def contour_to_notes(pitches: np.ndarray, frame_seconds: float, category: str,
                     minimum_duration: float = .08, gap_seconds: float = .035,
                     smoothing_frames: int = 5, onsets_seconds=(), trace: dict | None = None) -> list[NoteEvent]:
    values=np.array(pitches,dtype=float,copy=True)
    if trace is not None:
        trace['input_pitches']=values.copy()
        trace['frame_seconds']=frame_seconds
    max_gap=int(gap_seconds/frame_seconds)
    i=0
    while i<len(values):
        if np.isfinite(values[i]):i+=1;continue
        start=i
        while i<len(values) and not np.isfinite(values[i]):i+=1
        if start>0 and i<len(values) and i-start<=max_gap and round(values[start-1])==round(values[i]):
            values[start:i]=values[start-1]
    if trace is not None:trace['gap_filled_pitches']=values.copy()
    rounded=np.where(np.isfinite(values),np.rint(values),np.nan)
    original=rounded.copy();radius=smoothing_frames//2
    for i in range(radius,len(values)-radius):
        local=original[i-radius:i+radius+1]
        if np.isfinite(local).all():rounded[i]=np.median(local)
    attacks={round(t/frame_seconds) for t in onsets_seconds}
    if trace is not None:
        trace['smoothed_pitches']=rounded.copy()
        trace['attack_frames']=sorted(attacks)
        trace['segments']=[]
    result=[];start=0
    for i in range(1,len(rounded)+1):
        same=i<len(rounded) and (rounded[i]==rounded[start] or np.isnan(rounded[i]) and np.isnan(rounded[start]))
        if same and not (i in attacks and (i-start)*frame_seconds>=minimum_duration):continue
        if trace is not None:
            reason=('end_of_audio' if i==len(rounded) else 'retrigger' if same else
                    'voicing_change' if np.isnan(rounded[i]) or np.isnan(rounded[start]) else 'pitch_change')
            status=('unvoiced' if not np.isfinite(rounded[start]) else
                    'short' if (i-start)*frame_seconds<minimum_duration-1e-9 else
                    'invalid_pitch' if not 0<=int(rounded[start])<=127 else 'emitted')
            trace['segments'].append({'start_frame':start,'end_frame':i,
                'onset':start*frame_seconds,'offset':i*frame_seconds,
                'pitch':int(rounded[start]) if np.isfinite(rounded[start]) else None,
                'status':status,'end_reason':reason})
        if np.isfinite(rounded[start]) and (i-start)*frame_seconds>=minimum_duration-1e-9:
            pitch=int(rounded[start])
            if 0<=pitch<=127:
                result.append(NoteEvent(category,pitch,start*frame_seconds,i*frame_seconds,None,PROGRAMS[category]))
        start=i
    return result


def transcribe_monophonic(path: Path, category: str, trace: dict | None = None) -> list[NoteEvent]:
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
    if trace is not None:
        trace.update({'raw_f0':f0.copy(),'raw_pitches':librosa.hz_to_midi(f0),
            'voiced':voiced.copy(),'probability':probability.copy(),'rms':rms.copy(),
            'energy_threshold':max(.001,float(rms.max())*.025),'onsets_seconds':onsets.copy(),
            'onset_strength':librosa.onset.onset_strength(y=y,sr=target,hop_length=hop),
            'sample_rate':target,'source_sample_rate':sr,'samples':len(y),
            'frame_length':2048,'hop_length':hop,'fmin':low,'fmax':high,
            'probability_threshold':.2,'minimum_duration':.08,
            'gap_seconds':.035,'smoothing_frames':5})
    return contour_to_notes(pitches,hop/target,category,onsets_seconds=onsets,trace=trace)
