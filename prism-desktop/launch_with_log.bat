@echo off
chcp 65001 >nul
cd /d C:\Users\zd\prism\prism-desktop
set PRISM_SKIP_UPDATE_CHECK=1
.venv\Scripts\python.exe -m prism_desktop.main > C:\Users\zd\prism\prism-desktop\latest_launch.log 2>&1
pause
