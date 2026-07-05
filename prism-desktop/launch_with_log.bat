@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PRISM_SKIP_UPDATE_CHECK=1
if not exist logs mkdir logs
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -m prism_desktop.main > logs\latest_launch.log 2>&1
) else (
  echo [ERROR] .venv\Scripts\python.exe not found > logs\latest_launch.log
  echo .venv\Scripts\python.exe not found
  pause
  exit /b 1
)
pause
