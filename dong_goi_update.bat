@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" pack_update.py
) else (
    python pack_update.py
)
echo.
pause
