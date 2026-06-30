@echo off
echo ========================================
echo   PRISM Desktop Windows 打包
echo ========================================
echo.

set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%prism-desktop
set BUILD_DIR=%SCRIPT_DIR%build-windows
set OUTPUT_DIR=%SCRIPT_DIR%dist-windows

if exist "%BUILD_DIR%" rd /s /q "%BUILD_DIR%"
if exist "%OUTPUT_DIR%" rd /s /q "%OUTPUT_DIR%"

mkdir "%BUILD_DIR%" >nul 2>&1
mkdir "%OUTPUT_DIR%" >nul 2>&1

echo [1/3] 使用 PyInstaller 打包...
cd /d "%PROJECT_DIR%"
uv run python -m PyInstaller ^
    --name "PRISM-Agent" ^
    --onefile ^
    --windowed ^
    --distpath "%OUTPUT_DIR%" ^
    --workpath "%BUILD_DIR%" ^
    --specpath "%BUILD_DIR%" ^
    prism_desktop\main.py

if %ERRORLEVEL% neq 0 (
    echo PyInstaller 打包失败
    pause
    exit /b 1
)

echo.
echo [2/3] 生成发布清单...
set VERSION=2.0.2
(
echo # PRISM Desktop Windows 本地发布包
echo.
echo 构建时间：%date% %time%
echo 版本：%VERSION%
echo.
echo 文件：
dir /b "%OUTPUT_DIR%"
) > "%OUTPUT_DIR%\RELEASE.txt"

echo.
echo [3/3] 完成
echo 输出目录：%OUTPUT_DIR%
dir /b "%OUTPUT_DIR%"
echo.
echo 下一步：
echo   1. 在 %OUTPUT_DIR% 中找到 exe
echo   2. 双击运行测试
pause
