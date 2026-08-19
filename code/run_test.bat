@echo off
REM ---------------------------------------------------------------------------
REM  Build a foot trajectory for one test.
REM
REM  Use it either way:
REM    * Double-click this file  -> it asks for the test number, you type 4.
REM    * From a terminal:  run_test 4        (or:  run_test test04)
REM
REM  A bare number like 4 becomes test04. Outputs land in experiments\test04\.
REM  (Put the two clips in that folder named cam1 and cam2 first; if the folder
REM   is missing the script creates it and tells you what to drop in.)
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

echo ==========================================
echo   Build a foot trajectory from a test
echo ==========================================
echo.

set "TEST=%~1"
if "%TEST%"=="" set /p "TEST=Enter test number or name (e.g. 4 or test04):  "
if "%TEST%"=="" (
    echo No test entered. Nothing to do.
    goto :end
)

echo.
echo --- Processing "%TEST%" ------------------------------------------------
echo.
".venv\Scripts\python.exe" "scripts\build_foot_trajectory.py" "%TEST%"

:end
echo.
pause
