"""Explicit zero-origin time grid conversion for independent pitch estimators."""
import numpy as np


def nearest_grid(pitch,periodicity,native_step,target_step,count):
    pitch=np.asarray(pitch);periodicity=np.asarray(periodicity)
    if pitch.ndim!=1 or pitch.shape!=periodicity.shape or native_step<=0 or target_step<=0 or count<0:
        raise ValueError('Invalid pitch time grid')
    index=np.floor(np.arange(count)*target_step/native_step+.5).astype(int)
    if len(index) and (not len(pitch) or index[-1]>=len(pitch)):raise ValueError('Native pitch does not cover target grid')
    return pitch[index].copy(),periodicity[index].copy(),index


def frequency_to_midi(frequency):
    frequency=np.asarray(frequency,dtype=float)
    result=np.full(frequency.shape,np.nan)
    valid=np.isfinite(frequency)&(frequency>0)
    result[valid]=69+12*np.log2(frequency[valid]/440.)
    return result
