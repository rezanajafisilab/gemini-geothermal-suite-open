#!/usr/bin/env bash
# Dioscuri, one-time set-up on Linux or macOS. Everything goes into this folder: uv (a small Python
# manager) and its own Python 3.12 in .tools, the packages in .venv. Any Python already on the
# computer is neither used nor changed. Ollama runs the models (https://ollama.com/download).
# To remove Dioscuri: ./uninstall.sh, or delete this folder. No sudo.
set -e
cd "$(dirname "$0")"

UV_VERSION=0.12.24
export UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_CACHE_DIR="$PWD/.tools/cache" \
    UV_PYTHON_PREFERENCE=only-managed UV_PYTHON_INSTALL_BIN=0 UV_NO_CONFIG=1
UV=.tools/uv

if [ ! -x "$UV" ]; then
    case "$(uname -s)-$(uname -m)" in
        Linux-x86_64) T=x86_64-unknown-linux-gnu ;;
        Linux-aarch64 | Linux-arm64) T=aarch64-unknown-linux-gnu ;;
        Darwin-arm64) T=aarch64-apple-darwin ;;
        Darwin-x86_64) T=x86_64-apple-darwin ;;
        *) echo "No uv for $(uname -s) $(uname -m): see https://docs.astral.sh/uv/"; exit 1 ;;
    esac
    echo "1/3  uv $UV_VERSION into .tools ..."
    mkdir -p .tools
    curl -fsSL "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$T.tar.gz" \
        | tar xz -C .tools --strip-components 1
fi

echo "2/3  Python 3.12 and the packages into .tools and .venv, a few minutes ..."
"$UV" venv --quiet --seed --clear --python 3.12 .venv
"$UV" pip install --quiet --python .venv/bin/python -r requirements-dioscuri.txt

echo "3/3  Local models from Ollama: about 10 GB the first time ..."
if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama is not installed. Install it from https://ollama.com/download, then run ./install.sh again."
    exit 1
fi
if ! ollama list >/dev/null 2>&1; then
    (ollama serve >/dev/null 2>&1 &)
    sleep 3
fi
# Both models: the 9B where it fits (the GPU, else the CPU when the memory holds it), else the
# 4B; the header's model switch picks either.
ollama pull qwen3.5:9b      # 6.6 GB
ollama pull qwen3.5:4b      # 3.3 GB

echo
echo "Done. Start Dioscuri with ./start.sh"
