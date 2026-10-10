@echo off
setlocal
cd /d "%~dp0community"
py -3 server.py
if errorlevel 1 python server.py
if errorlevel 1 pause
