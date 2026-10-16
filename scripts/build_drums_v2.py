"""Rebuild frozen drum research recipe from input/hash-bound cached model decodes.

Does not run fresh separation/inference. No reference MIDI argument exists.
"""
import argparse,hashlib
from pathlib import Path
from audio_midi.quality import load_sources
from audio_midi.stitching import clean_notes
from audio_midi.drums import optimized_drums_v2
from audio_midi.midi import write_midi


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--duration',type=float,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError('Output exists; preserving it')
    input_hash=hashlib.sha256(a.input.read_bytes()).hexdigest()
    sources=load_sources(a.manifest,input_hash)
    sources={k:clean_notes([n for n in notes if n.category=='drums'],a.duration) for k,notes in sources.items()}
    result=optimized_drums_v2(**sources,duration=a.duration)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    write_midi(result,a.output)

if __name__=='__main__':main()
