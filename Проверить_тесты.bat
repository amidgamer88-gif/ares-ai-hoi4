@echo off
setlocal
cd /d "%~dp0"
py -3 -c "import sys" >nul 2>&1
if errorlevel 1 (
    set "PYTHON=python"
) else (
    set "PYTHON=py -3"
)
%PYTHON% -m unittest discover -s tests -v
if errorlevel 1 goto failed
%PYTHON% -m unittest discover -s desktop_app\tests -v
if errorlevel 1 goto failed
%PYTHON% -m unittest discover -s community\tests -v
if errorlevel 1 goto failed
echo.
echo All ARES checks passed.
goto end
:failed
echo.
echo Some ARES checks failed.
pause
:end
