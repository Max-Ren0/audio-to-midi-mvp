"""YourMT3 raw-note boundary, preserving its explicit singing tokens.

Decoding protocol follows openmirlab/mt3-infer YourMT3 adapter, Apache-2.0
upstream YourMT3 decoding utilities (2024 The YourMT3 Authors).
Model code and weights are installed separately, never copied into this repo.
"""
from collections import Counter
from dataclasses import asdict,dataclass
import hashlib
import json
import os
from pathlib import Path
import time
from ..events import NoteEvent,category_for

MODEL_REVISION='d8cbd287470291dee335f84315c5a9b9ff6e6c8a'
WEIGHT_SHA256='ae38e415c79efd5592dcb9b658cdb99ddb11d4c4e1eaa364cab04a052473fc25'


def normalize_raw(notes) -> tuple[list[NoteEvent],dict]:
    result=[]; dropped=Counter()
    for n in notes:
        category=category_for(int(n.program),bool(n.is_drum),vocal_semantics=True)
        if category is None:
            dropped[str(n.program)]+=1;continue
        # This model predicts binary note activity, not expressive velocity.
        # Drums have onset only. 50ms is a rendering convention, not an estimate.
        end=float(n.onset)+.05 if n.is_drum else (None if n.offset is None else float(n.offset))
        result.append(NoteEvent(category,int(n.pitch),float(n.onset),end,None,int(n.program)))
    return result,dict(dropped)


@dataclass
class ModelNote:
    program: int
    is_drum: bool
    pitch: int
    onset: float
    offset: float | None
    velocity: int = 1


def decode_segments(zipped):
    """Pair raw model events without upstream 10ms long/unclosed-note repair."""
    active={};notes=[];errors=Counter()
    for index,(events,ties,last_activity,start) in enumerate(zipped):
        if index:
            tied={(e.program,e.pitch) for e in ties}
            for key in list(active):
                if key not in tied:
                    e=active.pop(key)
                    notes.append(ModelNote(e.program,False,e.pitch,e.time,start))
                    errors['missing_tie']+=1
        for e in sorted((e for e in events if e.time is not None),key=lambda e:(e.time,e.velocity)):
            if e.is_drum:
                if e.velocity:
                    notes.append(ModelNote(e.program,True,e.pitch,e.time,e.time+.05))
                continue
            key=(e.program,e.pitch)
            prior=active.pop(key,None)
            if prior is not None:
                notes.append(ModelNote(prior.program,False,prior.pitch,prior.time,e.time))
            if e.velocity:
                active[key]=e
            elif prior is None:
                errors['note_off_without_onset']+=1
    for e in active.values():
        notes.append(ModelNote(e.program,False,e.pitch,e.time,None))
        errors['unclosed_note_capped_by_pipeline']+=1
    return notes,dict(errors)


def infer(input_path: Path, checkpoint: Path, device: str, output: Path) -> None:
    import numpy as np
    import torch
    torch.set_num_threads(2)
    from mt3_infer.adapters.yourmt3 import YourMT3Adapter
    start=time.monotonic()
    digest=hashlib.file_digest(checkpoint.open('rb'),'sha256').hexdigest()
    if digest!=WEIGHT_SHA256:
        raise ValueError('模型权重校验失败；只接受已核实的 YourMT3 权重')
    adapter=YourMT3Adapter(model_key='yptf_moe_nops')
    adapter.load_model(str(checkpoint),device=device)
    loaded=time.monotonic()
    audio=np.load(input_path,allow_pickle=False)
    with torch.inference_mode():
        features=adapter.preprocess(audio,16000).to(device)
        batch_size=int(os.environ.get('AUDIO_MIDI_BATCH_SIZE','2'))
        outputs=adapter.model.inference_file(bsz=batch_size,audio_segments=features)
        if isinstance(outputs,tuple): outputs=outputs[0]
    predicted=time.monotonic()
    model=adapter.model
    starts=[model.audio_cfg['input_frames']*i/model.audio_cfg['sample_rate'] for i in range(sum(a.shape[0] for a in outputs))]
    groups=[];errors=Counter()
    for channel in range(model.task_manager.num_decoding_channels):
        zipped,_,event_errors=model.task_manager.detokenize_list_batches([a[:,channel,:] for a in outputs],starts,return_events=True)
        notes,note_errors=decode_segments(zipped)
        groups.append(notes);errors.update(event_errors);errors.update(note_errors)
    notes,dropped=normalize_raw([note for group in groups for note in group])
    result={'notes':[asdict(n) for n in notes], 'model':'YourMT3 yptf_moe_nops',
      'model_revision':MODEL_REVISION,'weight_sha256':digest,'device':device,
      'sample_rate':16000,'model_window_samples':model.audio_cfg['input_frames'],
      'batch_size':batch_size,'dropped_programs':dropped,'decode_errors':dict(errors),
      'model_load_seconds':loaded-start,'inference_seconds':predicted-loaded,
      'velocity_source':'default_80_binary_model','drum_duration_source':'fixed_50ms_rendering_only'}
    output.write_text(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('checkpoint',type=Path);p.add_argument('output',type=Path);p.add_argument('--device',choices=['cpu','mps'],default='cpu')
    a=p.parse_args();infer(a.input,a.checkpoint,a.device,a.output)
