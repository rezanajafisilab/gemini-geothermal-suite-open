#!/usr/bin/env bash

echo "======================================"
echo " Ollama Docker Model Puller"
echo "======================================"
echo

docker info >/dev/null 2>&1 || {
    echo "ERROR: Docker is not running or not reachable."
    exit 1
}

docker inspect ollama >/dev/null 2>&1 || {
    echo 'ERROR: Container "ollama" not found.'
    exit 1
}

RUNNING=$(docker inspect -f '{{.State.Running}}' ollama)

[[ "$RUNNING" == "true" ]] || {
    echo 'ERROR: Container "ollama" is not running.'
    exit 1
}

echo "Pulling models..."
echo

docker exec -it ollama ollama pull llama3.2
docker exec -it ollama ollama pull snowflake-arctic-embed
docker exec -it ollama ollama pull zongwei/gemma3-translator:4b

echo
echo "======================================"
echo " All models pulled successfully!"
echo "======================================"
echo

docker exec ollama ollama list