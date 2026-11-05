#!/usr/bin/env bash
# Dioscuri: start the app and open it in the browser (http://127.0.0.1:8000; DIOSCURI_PORT to change).
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    echo "Run ./install.sh first."
    exit 1
fi
if command -v ollama >/dev/null 2>&1 && ! ollama list >/dev/null 2>&1; then
    echo "Starting the Ollama server ..."
    (ollama serve >/dev/null 2>&1 &)
    sleep 3
fi
unset PYTHONHOME
export PYTHONPATH="$PWD/src" MPLCONFIGDIR="$PWD/.tools/matplotlib"
PORT="${DIOSCURI_PORT:-8000}"
export DIOSCURI_PORT="$PORT" DIOSCURI_OPEN="${DIOSCURI_OPEN:-1}"
echo "Starting Dioscuri; it opens in the browser. Ctrl+C stops it."
exec .venv/bin/python -m gemini_agent.server
