@echo off
setlocal
cd /d "%~dp0desktop_app"
py -3 companion.py
if errorlevel 1 python companion.py
if errorlevel 1 pause
