@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" git_helper.py pull
) else (
    python git_helper.py pull
)
echo.
pause
