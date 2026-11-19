@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=python"
where python >nul 2>nul || set "PYTHON=py -3"

%PYTHON% -m unittest discover -s tests -v

echo.
pause
