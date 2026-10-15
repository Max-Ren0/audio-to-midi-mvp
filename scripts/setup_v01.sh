#!/bin/sh
set -eu
# Run from repository root. This uses project-local environments only.
sh scripts/setup_quality.sh
uv pip install --python work/sep-env/bin/python -r requirements-v01-specialists.txt
