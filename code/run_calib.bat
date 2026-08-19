@echo off
REM ---------------------------------------------------------------------------
REM  Rebuild the camera calibration for one recording session
REM  (stereo extrinsics + world frame). Run this ONCE at the start of a session,
REM  after placing/locking the cameras, before recording any tests.
REM
REM  Use it either way:
REM    * Double-click this file  -> it asks for the calib number, you type 4.
REM    * From a terminal:  run_calib 4        (or:  run_calib calib04)
REM
REM  Put four clips in calibration\sessions\calib04\ first:
REM    cam1_ext,  cam2_ext     (board held STATIC at ~15-20 poses, both cameras)
REM    cam1_floor, cam2_floor  (board flat on the floor)
REM  If the folder is missing, running this creates it and tells you what to drop in.
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

echo ==========================================
echo   Rebuild camera calibration (session)
echo ==========================================
echo.

set "CID=%~1"
if "%CID%"=="" set /p "CID=Enter calibration number or name (e.g. 4 or calib04):  "
if "%CID%"=="" (
    echo No id entered. Nothing to do.
    goto :end
)

echo.
echo --- Calibrating "%CID%" -------------------------------------------------
echo.
".venv\Scripts\python.exe" "scripts\build_calibration.py" "%CID%"

:end
echo.
pause
