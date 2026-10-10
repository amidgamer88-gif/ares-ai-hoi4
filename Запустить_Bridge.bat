@echo off
setlocal
cd /d "%~dp0bridge"
py -3 server.py
if errorlevel 1 python server.py
pause
