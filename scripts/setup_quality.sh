#!/bin/sh
set -eu
task_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$task_root"
uv sync --frozen --extra model --extra dev
# Only ONNX inference and offline samples are used. Skip optional TensorFlow,
# CoreML and PyAudio dependencies; this command never starts an audio device.
uv pip install --python .venv/bin/python --no-deps basic-pitch==0.4.0 tinysoundfont==0.3.7
uv pip install --python .venv/bin/python -r requirements-quality.txt
[ -x work/sep-env/bin/python ] || uv venv --python 3.11 work/sep-env
uv pip install --python work/sep-env/bin/python -r requirements-separation.txt
printf '%s\n' 'Environments ready. Prepare the fixed Demucs weight and GeneralUser soundfont as described in outputs/v0.0-二次转录说明.md.'
