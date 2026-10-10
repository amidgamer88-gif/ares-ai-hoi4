@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_mod.ps1"
if errorlevel 1 (
  echo.
  echo Установка не завершилась. См. сообщение выше.
  pause
  exit /b 1
)
echo.
echo Готово. Включите ARES AI в Paradox Launcher.
pause
