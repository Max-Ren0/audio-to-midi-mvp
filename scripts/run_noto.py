"""Run the local Noto three-track pipeline on one MP3."""
import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--resources', type=Path, default=ROOT)
    parser.add_argument('--threads', type=int, choices=[2], default=2)
    parser.add_argument('--device', choices=['cpu'], default='cpu')
    parser.add_argument('--parallel', action=argparse.BooleanOptionalAction, default=False,
                        help='run Piano B and MuScriptor concurrently after the baseline')
    parser.add_argument('--piano-threads', type=int, choices=[1, 2], default=2,
                        help='Piano B compute threads (default: 2)')
    parser.add_argument('--muscriptor-threads', type=int, choices=[1, 2], default=2,
                        help='MuScriptor compute threads (default: 2)')
    parser.add_argument('--beat-align', action=argparse.BooleanOptionalAction, default=False,
                        help='detect beats and write a tempo map without quantizing notes')
    parser.add_argument('--quantize', choices=['1/4', '1/8', '1/16'],
                        help='optionally snap note onsets to the given MIDI grid')
    parser.add_argument('--presence-gate', action=argparse.BooleanOptionalAction, default=False,
                        help='optionally suppress tracks judged absent (default: off)')
    raw_args = sys.argv[1:] if argv is None else list(argv)
    args = parser.parse_args(raw_args)
    from audio_midi.one_click import run_noto

    return run_noto(
        args.input, args.output_dir, args.resources, args.threads, args.device,
        parallel=args.parallel, piano_threads=args.piano_threads,
        muscriptor_threads=args.muscriptor_threads,
        beat_align=args.beat_align, quantize=args.quantize, presence_gate=args.presence_gate,
        command=[sys.executable, sys.argv[0], *raw_args],
    )


if __name__ == '__main__':
    raise SystemExit(main())
