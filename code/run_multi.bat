@echo off
REM ---------------------------------------------------------------------------
REM  Build the full 3-camera trajectory for one session (both feet + obstacle).
REM  This is the MAIN tool -> scripts\build_multi_trajectory.py
REM
REM  Use it either way:
REM    * Double-click this file  -> it asks for the session number, you type 15.
REM    * From a terminal:  run_multi 15      (or:  run_multi test15)
REM
REM  A bare number like 15 becomes test15. Put the three clips in
REM  videos\sessions\test15\ first, named cam1.mp4, cam2.mp4, cam3.mp4.
REM  Outputs (xlsx, plots, run.txt, synced_videos) land in results\sessions\test15\.
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

echo ==========================================
echo   Build 3-camera trajectory (feet + obstacle)
echo ==========================================
echo.

set "TEST=%~1"
if "%TEST%"=="" set /p "TEST=Enter session number or name (e.g. 15 or test15):  "
if "%TEST%"=="" (
    echo No session entered. Nothing to do.
    goto :end
)

echo.
echo --- Processing "%TEST%" ------------------------------------------------
echo.
".venv\Scripts\python.exe" "scripts\build_multi_trajectory.py" "%TEST%"

:end
echo.
pause
