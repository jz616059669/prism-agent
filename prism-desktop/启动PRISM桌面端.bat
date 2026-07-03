@echo off
chcp 65001 >nul 2>&nul
cd /d "%~dp0"
call .venv\Scripts\activate.bat
echo Starting PRISM Desktop...
flet run prism_desktop\main.py
pause
