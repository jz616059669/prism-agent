<#
.SYNOPSIS
PRISM Agent Windows 一键安装脚本
#>

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$UserProfile = [Environment]::GetFolderPath('UserProfile')
$PrismDir = Join-Path $UserProfile '.prism'

function Write-Info($msg) {
    Write-Host "[信息] $msg" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "[通过] $msg" -ForegroundColor Green
}

function Write-Fail($msg) {
    Write-Host "[错误] $msg" -ForegroundColor Red
}

function Test-Command($name) {
    Get-Command $name -ErrorAction SilentlyContinue | Where-Object { $_.Source }
}

# 1. 检查 Python
Write-Info "检查 Python..."
if (-not (Test-Command 'python')) {
    Write-Fail "未检测到 Python，请先安装 Python 3.11+：https://www.python.org/downloads/windows/"
    exit 1
}
$pyVersion = python --version 2>&1
Write-Ok "Python：$pyVersion"

# 2. 检查 uv
Write-Info "检查 uv..."
if (-not (Test-Command 'uv')) {
    Write-Fail "未检测到 uv，请先安装 uv：https://docs.astral.sh/uv/"
    exit 1
}
Write-Ok "uv 已安装"

# 3. 安装 PRISM CLI
Write-Info "安装 PRISM CLI..."
Set-Location $RepoRoot
try {
    uv pip install -e .
    Write-Ok "PRISM CLI 安装完成"
} catch {
    Write-Fail "PRISM CLI 安装失败：$_"
    Write-Host "建议：检查网络/代理，或运行 'uv pip install -e . --retries 3' 重试"
    exit 1
}

# 4. 安装 Playwright Chromium
Write-Info "安装 Playwright Chromium..."
try {
    playwright install chromium
    Write-Ok "Playwright Chromium 安装完成"
} catch {
    Write-Fail "Playwright Chromium 安装失败：$_"
    Write-Host "建议：先运行 'playwright install-deps'，再重试"
    exit 1
}

# 5. 初始化配置
Write-Info "初始化配置..."
if (-not (Test-Path $PrismDir)) {
    New-Item -Path $PrismDir -ItemType Directory | Out-Null
}
$ConfigFile = Join-Path $PrismDir 'config.yaml'
if (-not (Test-Path $ConfigFile)) {
    $Example = Join-Path $RepoRoot 'config.example.yaml'
    if (Test-Path $Example) {
        Copy-Item $Example $ConfigFile
        Write-Ok "已创建默认配置：$ConfigFile"
        Write-Host "提示：请编辑 $ConfigFile 填入 model.api_key / model.base_url"
    } else {
        Write-Fail "未找到 config.example.yaml，无法初始化配置"
        exit 1
    }
} else {
    Write-Ok "配置文件已存在：$ConfigFile"
}

# 6. 安装桌面客户端依赖
Write-Info "安装桌面客户端依赖..."
$DesktopDir = Join-Path $RepoRoot 'prism-desktop'
if (Test-Path $DesktopDir) {
    Set-Location $DesktopDir
    try {
        uv add flet
        Write-Ok "桌面客户端依赖安装完成"
    } catch {
        Write-Fail "桌面客户端依赖安装失败：$_"
        Write-Host "建议：手动在 prism-desktop 目录运行 'uv add flet'"
    }
} else {
    Write-Fail "未找到 prism-desktop 目录"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  安装完成" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "快速开始："
Write-Host "  prism --help"
Write-Host "  uv run flet run prism-desktop"
Write-Host ""
Read-Host "按回车键退出"
