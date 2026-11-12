@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY_CMD=python"
if exist "venv\Scripts\python.exe" set "PY_CMD=venv\Scripts\python.exe"
if exist "src\git_helper.py" (
    "%PY_CMD%" src\git_helper.py pull
) else (
    "%PY_CMD%" git_helper.py pull
)
echo.
pause
