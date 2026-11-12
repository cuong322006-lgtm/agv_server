@echo off
cd /d "%~dp0"
echo =================================================================
echo   DUONG HAM INTERNET BAO MAT (TU DONG DONG BO VOI ESP32-CAM & S3)
echo =================================================================
echo.
if not exist venv (
    echo [!] Chua tim thay moi truong ao venv. Dang tu dong chay cai dat...
    call install.bat
)
call venv\Scripts\activate.bat
python run_tunnel_sync.py
pause
