#!/usr/bin/env bash
# Dioscuri: remove what install.sh put on this computer. All of it is in this folder (.venv and
# .tools) except the models, which Ollama keeps; it asks before removing those.
cd "$(dirname "$0")"
read -r -p "Remove Dioscuri's Python and packages (.venv and .tools in this folder)? [y/N] " a
case "$a" in [yY]*) ;; *) exit 0 ;; esac
rm -rf .venv .tools
echo "Removed .venv and .tools."
if command -v ollama >/dev/null 2>&1; then
    read -r -p "Also remove the models from Ollama (qwen3:1.7b, qwen3.5:4b, qwen3.5:9b; up to 11 GB)? Other apps may use them. [y/N] " a
    case "$a" in
        [yY]*) for m in qwen3:1.7b qwen3.5:4b qwen3.5:9b; do ollama rm "$m" 2>/dev/null || true; done ;;
    esac
fi
echo "Done. Delete this folder to finish; Ollama itself is removed as any other program."
