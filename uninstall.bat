@echo off
rem Dioscuri: remove what install.bat put on this computer. All of it is in this folder (.venv and
rem .tools) except the models, which Ollama keeps; it asks before removing those.
setlocal
cd /d "%~dp0"
choice /m "Remove Dioscuri's Python and packages, the .venv and .tools folders here"
if errorlevel 2 exit /b 0
if exist .venv rmdir /s /q .venv
if exist .tools rmdir /s /q .tools
echo Removed .venv and .tools.

set "OLLAMA="
where ollama >nul 2>&1 && set "OLLAMA=ollama"
if not defined OLLAMA if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA goto done
choice /m "Also remove the models from Ollama, up to 11 GB? Other apps may use them"
if errorlevel 2 goto done
"%OLLAMA%" rm qwen3:1.7b >nul 2>&1
"%OLLAMA%" rm qwen3.5:4b >nul 2>&1
"%OLLAMA%" rm qwen3.5:9b >nul 2>&1
echo Removed the models.

:done
echo Done. Delete this folder to finish; Ollama itself is removed in Settings, Apps.
pause
