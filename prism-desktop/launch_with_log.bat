@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PRISM_SKIP_UPDATE_CHECK=1
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv\Scripts\python.exe not found > logs\latest_launch.log
  echo .venv\Scripts\python.exe not found
  pause
  exit /b 1
)
if not exist "prism_desktop\main.py" (
  echo [ERROR] prism_desktop\main.py not found > logs\latest_launch.log
  echo prism_desktop\main.py not found
  pause
  exit /b 1
)
if not exist logs mkdir logs
.venv\Scripts\python.exe -m prism_desktop.main > logs\latest_launch.log 2>&1
pause
endlocal
