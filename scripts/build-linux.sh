#!/bin/bash
set -e

echo "========================================"
echo "  PRISM Desktop Linux 打包"
echo "========================================"
echo ""

# 检查依赖
if ! command -v flet &> /dev/null; then
    echo "[安装] 正在安装 flet..."
    pip install flet[all]
fi

echo "[1/3] 构建 Linux 可执行文件..."
cd prism-desktop

# 构建目录
BUILD_DIR="build/linux"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# 使用 flet build 打包
flet build linux \
    --name "PRISM Agent" \
    --output "$BUILD_DIR" \
    --icon ../assets/icon.png 2>/dev/null || \
flet build linux \
    --name "PRISM Agent" \
    --output "$BUILD_DIR"

echo "[2/3] 打包为 .tar.xz..."
cd "$BUILD_DIR"
tar -cJf prism-desktop-linux.tar.xz prism-desktop 2>/dev/null || \
tar -czf prism-desktop-linux.tar.gz prism-desktop

echo "[3/3] 完成"
echo ""
echo "输出文件："
ls -lh *.tar.* 2>/dev/null || ls -lh
echo ""
echo "安装方式："
echo "  tar -xf prism-desktop-linux.tar.xz"
echo "  ./prism-desktop/prism-desktop"
