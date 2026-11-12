@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY_CMD=python"
if exist "venv\Scripts\python.exe" set "PY_CMD=venv\Scripts\python.exe"
if exist "src\pack_update.py" (
    "%PY_CMD%" src\pack_update.py
) else (
    "%PY_CMD%" pack_update.py
)
echo.
pause
