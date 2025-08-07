@echo off
title ImmichOCR_Modular
echo Starting ImmichOCR_Modular v3.0.0...
cd /d "%~dp0"

if exist "dist\ImmichOCR_Modular.exe" (
    echo Launching application...
    start "" "dist\ImmichOCR_Modular.exe"
) else (
    echo ERROR: ImmichOCR_Modular.exe not found in dist folder!
    echo Please run build_system.py to build the application.
    pause
)
