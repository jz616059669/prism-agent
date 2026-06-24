@echo off
chcp 65001 >nul
echo ========================================
echo   PRISM Agent 一键安装
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.11+
    pause
    exit /b 1
)

REM 检查 uv
uv --version >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装 uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo [错误] uv 安装失败，请手动安装 https://docs.astral.sh/uv/
        pause
        exit /b 1
    )
)

echo [1/4] 安装 PRISM CLI...
pip install -e .

echo [2/4] 安装浏览器引擎...
playwright install chromium

echo [3/4] 初始化配置...
if not exist "%USERPROFILE%\.prism" mkdir "%USERPROFILE%\.prism"
if not exist "%USERPROFILE%\.prism\config.yaml" (
    copy config.example.yaml "%USERPROFILE%\.prism\config.yaml"
    echo [提示] 已创建默认配置，请编辑 %USERPROFILE%\.prism\config.yaml 填入 API Key
) else (
    echo [跳过] 配置文件已存在
)

echo [4/4] 安装桌面客户端...
cd prism-desktop
uv tool install -e .
cd ..

echo.
echo ========================================
echo   安装完成
echo ========================================
echo.
echo 快速开始：
echo   prism --help
echo   prism-desktop
echo.
pause
