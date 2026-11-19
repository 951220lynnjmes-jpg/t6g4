@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=python"
where python >nul 2>nul || set "PYTHON=py -3"

if "%~1"=="" (
  echo Drag a .vm file or a folder onto this script.
  pause
  exit /b 2
)

%PYTHON% VMEmulator.py "%~1" --steps 5000
echo.
pause
