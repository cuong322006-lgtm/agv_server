@echo off
cd /d "%~dp0"
echo =================================================================
echo       CAI DAT HE THONG AGV SERVER (FASTAPI + AI YOLOV8 + LIDAR)
echo =================================================================
echo.
echo [1/3] Kiem tra va tao moi truong ao (venv)...
if not exist venv (
    python -m venv venv
    if errorlevel 1 (
        echo [!] Khong the tao venv. Vui long kiem tra Python tren may da duoc them vao PATH chua!
        pause
        exit /b 1
    )
    echo [*] Da tao thanh cong moi truong ao venv.
) else (
    echo [*] Da ton tai thu muc venv.
)

echo.
echo [2/3] Kich hoat moi truong ao...
call venv\Scripts\activate.bat

echo.
echo [3/3] Cai dat cac thu vien AI (FastAPI, OpenCV, YOLOv8, pyzbar...)...
python -m pip install --upgrade pip
if exist "tools\requirements.txt" (
    pip install -r tools\requirements.txt
) else (
    pip install -r requirements.txt
)

echo.
echo =================================================================
echo   CAI DAT HOAN TAT 100%%! BAN CO THE CHAY START_SERVER.BAT DE DUNG!
echo =================================================================
pause
