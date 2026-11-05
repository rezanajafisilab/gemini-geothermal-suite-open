#!/bin/bash
# Run a scratch script against the repo, read-only: no bytecode, GEMINI cache in the scratchpad.
cd "$(dirname "$0")/../../../../.."
export PYTHONNOUSERSITE=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1
export DIOSCURI_GEMINI_CACHE=${DIOSCURI_GEMINI_CACHE:-/tmp/dioscuri-audit/subsurface/gemini_cache}
export DIOSCURI_WORKERS=1 DIOSCURI_SWEEP=0
exec python "$@"
