@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================================
echo    KHOI CHAY TU DONG VE 3D CAD TRUC TIEP TRONG AUTODESK INVENTOR 2027
echo ============================================================================
echo.
if exist "Inventor_CAD_AGV\build_inventor_agv.vbs" (
    cscript.exe //NoLogo "Inventor_CAD_AGV\build_inventor_agv.vbs"
) else (
    cscript.exe //NoLogo "build_inventor_agv.vbs"
)
echo.
pause
