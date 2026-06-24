<#
.SYNOPSIS
PRISM Desktop Windows 打包脚本
#>

param(
    [switch]$SkipFletInstall
)

$ErrorActionPreference = 'Stop'
$BuildDir = Join-Path $PSScriptRoot 'build-windows'
$OutputDir = Join-Path $PSScriptRoot 'dist-windows'

Write-Host '========================================'
Write-Host '  PRISM Desktop Windows 打包'
Write-Host '========================================'
Write-Host ''

# 清理旧包
if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
if (Test-Path $OutputDir) { Remove-Item $OutputDir -Recurse -Force }
New-Item -Path $BuildDir -ItemType Directory -Force | Out-Null
New-Item -Path $OutputDir -ItemType Directory -Force | Out-Null

# 检查 flet
if (-not $SkipFletInstall) {
    Write-Host '[1/4] 检查 flet...'
    $flet = Get-Command flet -ErrorAction SilentlyContinue
    if (-not $flet) {
        Write-Host '[安装] 正在安装 flet...'
        uv add --dev flet
    } else {
        Write-Host '       flet 已安装'
    }
} else {
    Write-Host '[1/4] 跳过 flet 安装'
}

# 打包
Write-Host '[2/4] 执行 flet build windows...'
Push-Location (Join-Path $PSScriptRoot '..\prism-desktop')
try {
    uv run flet build windows `
        --name "PRISM Agent" `
        --output $BuildDir `
        --icon "$PSScriptRoot\..\assets\icon.png" `
        2>&1 | Out-Null
} catch {
    Write-Host "       flet build 失败，尝试无图标打包..."
    uv run flet build windows `
        --name "PRISM Agent" `
        --output $BuildDir `
        2>&1 | Out-Null
}
Pop-Location

# 收集产物
Write-Host '[3/4] 收集产物...'
$built = Get-ChildItem $BuildDir -Recurse -File | Select-Object -First 5
if (-not $built) {
    Write-Host '      未找到构建产物，请检查 flet build 输出'
    exit 1
}
foreach ($item in $built) {
    $rel = $item.FullName.Substring($BuildDir.Length + 1)
    $dest = Join-Path $OutputDir $rel
    $destDir = Split-Path $dest -Parent
    if (-not (Test-Path $destDir)) { New-Item -Path $destDir -ItemType Directory -Force | Out-Null }
    Copy-Item $item.FullName $dest -Force
    Write-Host "      $rel"
}

# 生成发布清单
Write-Host '[4/4] 生成发布清单...'
$version = '0.2.1'
$manifest = @"
# PRISM Desktop Windows 本地发布包

构建时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
版本：$version

文件：
"@
Get-ChildItem $OutputDir -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($OutputDir.Length + 1)
    $manifest += "  $rel`n"
}
Set-Content -Path (Join-Path $OutputDir 'RELEASE.txt') -Value $manifest -Encoding UTF8

Write-Host ''
Write-Host '完成'
Write-Host "输出目录：$OutputDir"
Get-ChildItem $OutputDir -File | Format-Table Name, Length -AutoSize
Write-Host ''
Write-Host '下一步：'
Write-Host '  1. 在 build-windows/ 中找到 exe/打包结果'
Write-Host '  2. 或保留本地包供内部分发'
