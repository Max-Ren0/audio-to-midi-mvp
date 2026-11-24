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
    raw_args = sys.argv[1:] if argv is None else list(argv)
    args = parser.parse_args(raw_args)
    from audio_midi.one_click import run_noto

    return run_noto(
        args.input, args.output_dir, args.resources, args.threads, args.device,
        command=[sys.executable, sys.argv[0], *raw_args],
    )


if __name__ == '__main__':
    raise SystemExit(main())
