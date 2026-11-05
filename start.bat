@echo off
rem Dioscuri: start the app and open it in the browser (http://127.0.0.1:8000; DIOSCURI_PORT to change).
rem Close this window to stop it. If it stops by itself, the window stays open to show why.
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Dioscuri is not set up yet: run install.bat first, from the unzipped folder.
    pause
    exit /b 1
)
set "OLLAMA="
where ollama >nul 2>&1 && set "OLLAMA=ollama"
if not defined OLLAMA if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if defined OLLAMA (
    "%OLLAMA%" list >nul 2>&1
    if errorlevel 1 (
        echo Starting the Ollama server ...
        start "Ollama" /min "%OLLAMA%" serve
        timeout /t 5 /nobreak >nul
    )
)
set "PYTHONHOME="
set "PYTHONPATH=%~dp0src"
set "MPLCONFIGDIR=%~dp0.tools\matplotlib"
if "%DIOSCURI_PORT%"=="" set "DIOSCURI_PORT=8000"
if "%DIOSCURI_OPEN%"=="" set "DIOSCURI_OPEN=1"
echo Starting Dioscuri; it opens in the browser. Close this window to stop it.
.venv\Scripts\python -m gemini_agent.server
echo.
echo Dioscuri stopped. If that was not you, the lines above say why.
pause
endlocal
