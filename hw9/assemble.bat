@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo Drag and drop an .asm file onto this file.
    echo.
    pause
    exit /b 1
)

set "PYTHON=python"
where python >nul 2>nul || set "PYTHON=py -3"

%PYTHON% Assembler.py "%~1"

echo.
pause
