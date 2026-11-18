@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================================
echo    KHOI CHAY TU DONG VE 3D CAD TRUC TIEP TRONG AUTODESK INVENTOR 2027
echo ============================================================================
echo.
cscript.exe //NoLogo "build_inventor_agv.vbs"
echo.
pause
