@echo off
REM ---------------------------------------------------------------------------
REM  Rebuild the camera calibration for one recording session
REM  (stereo extrinsics + world frame). Run this ONCE at the start of a session,
REM  after placing/locking the cameras, before recording any tests.
REM
REM  Use it either way:
REM    * Double-click this file  -> it asks for the calib number and the board.
REM    * From a terminal:  run_calib 4 normal   (or:  run_calib 4 large)
REM
REM  BOARD: 'normal' (small ~23x17cm board) or 'large' (big tiled ~50x38cm board).
REM  Use 'normal' when the cameras are close; 'large' when they are far.
REM
REM  Put the clips in videos\calibration\calib04\ first:
REM    cam1_ext,  cam2_ext,  cam3_ext  (board held STATIC at ~15-20 poses, all cameras)
REM    cam1_floor, cam2_floor          (board flat on the floor; cam3_floor not needed)
REM  Results (npz + run log) land in results\calibration\calib04\; the active
REM  calibration is promoted to results\calibration\active\.
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

set "BOARD=%~2"
if "%BOARD%"=="" set /p "BOARD=Which board? normal (close cameras) or large [default large]:  "
if "%BOARD%"=="" set "BOARD=large"

echo.
echo --- Calibrating "%CID%" with "%BOARD%" board ----------------------------
echo.
".venv\Scripts\python.exe" "scripts\build_calibration.py" "%CID%" "%BOARD%"

:end
echo.
pause
