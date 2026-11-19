@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=python"
where python >nul 2>nul || set "PYTHON=py -3"

%PYTHON% VMTranslator.py examples\SimpleAdd.vm examples\SimpleAdd.asm
if errorlevel 1 goto end
%PYTHON% ..\hw9\Assembler.py examples\SimpleAdd.asm examples\SimpleAdd.hack
if errorlevel 1 goto end

echo.
echo --- generated assembly ---
type examples\SimpleAdd.asm

echo.
echo --- VM interpreter ---
%PYTHON% VMEmulator.py examples\SimpleAdd.vm

echo.
echo --- real Hack CPU running the assembled code ---
%PYTHON% HackCPU.py examples\SimpleAdd.hack

:end
echo.
pause
