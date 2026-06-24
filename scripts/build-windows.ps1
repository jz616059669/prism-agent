@echo off
chcp 65001 >nul
echo ========================================
echo   PRISM Desktop Windows 打包
echo ========================================
echo.

REM 检查 flet
flet --version >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装 flet...
    pip install flet[all]
)

echo [1/4] 构建 Windows 可执行文件...
cd prism-desktop

REM 构建目录
set BUILD_DIR=build\windows
if exist "%BUILD_DIR%" rd /s /q "%BUILD_DIR%"
mkdir "%BUILD_DIR%"

REM 使用 flet build 打包
flet build windows ^
    --name "PRISM Agent" ^
    --output "%BUILD_DIR%" ^
    --icon ..\assets\icon.png 2>nul || ^
flet build windows ^
    --name "PRISM Agent" ^
    --output "%BUILD_DIR%"

echo [2/4] 压缩为 zip...
cd "%BUILD_DIR%"
powershell -Command "Compress-Archive -Path * -DestinationPath ..\prism-desktop-windows.zip -Force"
cd ..\..

echo [3/4] 清理临时文件...
rd /s /q "%BUILD_DIR%"

echo [4/4] 完成
echo.
echo 输出文件：
dir /b prism-desktop-windows.zip 2>nul || echo 请检查 build\windows\ 目录
echo.
echo 使用方式：
echo   解压 prism-desktop-windows.zip
echo   运行 PRISM Agent.exe
echo.
pause
