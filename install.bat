@echo off
rem Dioscuri, one-time set-up on Windows. Everything goes into this folder: uv (a small Python
rem manager) and its own Python 3.12 in .tools, the packages in .venv. Any Python already on the
rem computer is neither used nor changed. Ollama runs the models (https://ollama.com/download).
rem To remove Dioscuri: uninstall.bat, or delete this folder. The window stays open at the end.
setlocal
cd /d "%~dp0"

if not exist "requirements-dioscuri.txt" (
    echo install.bat must run from the unzipped folder, not from inside the zip.
    echo In Explorer: right-click the zip, choose Extract All, open the extracted dioscuri folder
    echo and run install.bat there.
    goto fail
)

set "UV_VERSION=0.12.24"
set "UV=%CD%\.tools\uv.exe"
set "UV_PYTHON_INSTALL_DIR=%CD%\.tools\python"
set "UV_CACHE_DIR=%CD%\.tools\cache"
set "UV_PYTHON_PREFERENCE=only-managed"
set "UV_PYTHON_INSTALL_BIN=0"
set "UV_PYTHON_INSTALL_REGISTRY=0"
set "UV_NO_CONFIG=1"
set "URL=https://github.com/astral-sh/uv/releases/download/%UV_VERSION%/uv-x86_64-pc-windows-msvc.zip"

if exist "%UV%" goto haveuv
echo 1/3  uv %UV_VERSION% into .tools ...
if not exist .tools mkdir .tools
curl.exe -fsSL -o .tools\uv.zip "%URL%" && tar.exe -xf .tools\uv.zip -C .tools
if not exist "%UV%" powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -UseBasicParsing -Uri '%URL%' -OutFile '.tools\uv.zip'; Expand-Archive -Force '.tools\uv.zip' '.tools'"
if not exist "%UV%" (
    echo uv could not be downloaded from github.com: check the internet connection.
    goto fail
)
del .tools\uv.zip >nul 2>&1
:haveuv

echo 2/3  Python 3.12 and the packages into .tools and .venv, a few minutes ...
"%UV%" venv --quiet --seed --clear --python 3.12 .venv
if errorlevel 1 (
    echo Python 3.12 could not be set up in .tools: the lines above say why.
    goto fail
)
"%UV%" pip install --quiet --python .venv\Scripts\python.exe -r requirements-dioscuri.txt
if errorlevel 1 (
    echo The Python packages could not be installed: the lines above say why.
    goto fail
)

echo 3/3  Local models from Ollama: about 10 GB the first time ...
set "OLLAMA="
where ollama >nul 2>&1 && set "OLLAMA=ollama"
if not defined OLLAMA if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA (
    echo Ollama is not installed. Install it from https://ollama.com/download, then run install.bat again.
    goto fail
)
"%OLLAMA%" list >nul 2>&1
if errorlevel 1 (
    start "Ollama" /min "%OLLAMA%" serve
    timeout /t 5 /nobreak >nul
)
"%OLLAMA%" pull qwen3.5:9b
if errorlevel 1 goto nomodels
"%OLLAMA%" pull qwen3.5:4b
if errorlevel 1 goto nomodels

echo.
echo Done. Start Dioscuri with start.bat
pause
exit /b 0

:nomodels
echo The models could not be downloaded. Is Ollama running? Start it from the Start menu,
echo check the internet connection, then run install.bat again.

:fail
echo.
echo The set-up stopped. Fix the problem above, then run install.bat again.
pause
exit /b 1
