"""Segmentation-invariant interval diagnostics; not a perceptual similarity score."""
import math


def duration_overlap(reference,prediction,duration,chroma=False,activity=False):
    if not math.isfinite(duration) or duration<=0:raise ValueError('Invalid observation duration')
    def clip(rows):
        out=[]
        for start,end,pitch in rows:
            if not all(math.isfinite(v) for v in [start,end,pitch]):raise ValueError('Nonfinite event')
            a=max(0.,start);b=min(duration,end)
            if b>a:out.append((a,b,0 if activity else int(pitch)%12 if chroma else int(pitch)))
        return out
    r=clip(reference);p=clip(prediction);bounds=sorted({0.,duration,*[v for rows in [r,p] for a,b,k in rows for v in [a,b]]})
    matched=rs=ps=0.
    for a,b in zip(bounds,bounds[1:]):
        t=(a+b)/2;rk={k for x,y,k in r if x<=t<y};pk={k for x,y,k in p if x<=t<y}
        rs+=(b-a)*len(rk);ps+=(b-a)*len(pk);matched+=(b-a)*len(rk&pk)
    return {'matched_pitch_seconds':matched,'reference_pitch_seconds':rs,'prediction_pitch_seconds':ps,
            'precision':matched/ps if ps else None,'recall':matched/rs if rs else None,'f1':2*matched/(rs+ps) if rs+ps else None,
            'meaning':'active-time overlap' if activity else 'active pitch-class/time overlap' if chroma else 'active absolute-pitch/time overlap'}
