@echo off
setlocal
title Ollama Model Puller

echo ======================================
echo  Ollama Docker Model Puller
echo ======================================
echo.

:: Ensure Docker is reachable
docker info >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker is not running or not reachable.
  echo Start Docker Desktop and try again.
  pause
  exit /b 1
)

:: Ensure the container is running
docker inspect -f "{{.State.Running}}" ollama >nul 2>&1
if errorlevel 1 (
  echo ERROR: Container "ollama" not found.
  echo If you use docker compose, run: docker compose up -d
  pause
  exit /b 1
)

for /f "delims=" %%R in ('docker inspect -f "{{.State.Running}}" ollama') do set RUNNING=%%R

if /I not "%RUNNING%"=="true" (
  echo ERROR: Container "ollama" exists but is not running.
  echo Start it with: docker start ollama
  pause
  exit /b 1
)

echo Container "ollama" is running.
echo.

echo Pulling models...
echo --------------------------------------

docker exec -it ollama ollama pull llama3.2
if errorlevel 1 goto :pullfail

docker exec -it ollama ollama pull snowflake-arctic-embed
if errorlevel 1 goto :pullfail

docker exec -it ollama ollama pull zongwei/gemma3-translator:4b
if errorlevel 1 goto :pullfail

echo.
echo ======================================
echo  All models pulled successfully!
echo ======================================
echo.

docker exec ollama ollama list

echo.
pause
exit /b 0

:pullfail
echo.
echo ERROR: One of the model pulls failed.
echo Check the output above for the exact error.
echo.
pause
exit /b 1
