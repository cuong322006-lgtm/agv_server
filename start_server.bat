@echo off
cd /d "%~dp0"
echo =================================================================
echo       KHOI DONG AGV SERVER DASHBOARD (PORT 8000)
echo =================================================================
echo.
if not exist venv (
    echo [!] Chua tim thay moi truong ao venv. Dang tu dong chay cai dat...
    call install.bat
)
echo [*] Dang kich hoat moi truong ao va khoi dong FastAPI Server...
call venv\Scripts\activate.bat
python main.py
pause
