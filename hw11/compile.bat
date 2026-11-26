@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=python"
where python >nul 2>nul || set "PYTHON=py -3"

if "%~1"=="" (
  echo Drag a .jack file or a folder onto this script.
  pause
  exit /b 2
)

%PYTHON% JackCompiler.py "%~1"
echo.
pause
