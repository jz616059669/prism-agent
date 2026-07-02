@echo off
chcp 65001 >nul
cd /d "%~dp0"
call .venv\Scripts\activate.bat
echo 正在启动 PRISM Desktop ...
flet run prism_desktop\main.py
pause
