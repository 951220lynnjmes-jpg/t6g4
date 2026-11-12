@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=python"
where python >nul 2>nul || set "PYTHON=py -3"

%PYTHON% Assembler.py examples\Add.asm examples\Add.hack
if errorlevel 1 goto end

echo.
echo Generated machine code:
type examples\Add.hack

:end
echo.
pause
