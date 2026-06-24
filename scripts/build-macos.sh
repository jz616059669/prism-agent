#!/bin/bash
set -e

echo "========================================"
echo "  PRISM Desktop macOS 打包"
echo "========================================"
echo ""

# 检查依赖
if ! command -v flet &> /dev/null; then
    echo "[安装] 正在安装 flet..."
    pip install flet[all]
fi

echo "[1/4] 构建 macOS 应用..."
cd prism-desktop

# 构建目录
BUILD_DIR="build/macos"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# 使用 flet build 打包
flet build macos \
    --name "PRISM Agent" \
    --output "$BUILD_DIR" \
    --icon ../assets/icon.png 2>/dev/null || \
flet build macos \
    --name "PRISM Agent" \
    --output "$BUILD_DIR"

echo "[2/4] 打包为 .tar.gz..."
cd "$BUILD_DIR"
tar -czf prism-desktop-macos.tar.gz PRISM*.app 2>/dev/null || \
tar -czf prism-desktop-macos.tar.gz *

echo "[3/4] 清理..."
cd ../..
rm -rf "$BUILD_DIR"

echo "[4/4] 完成"
echo ""
echo "输出文件："
ls -lh build/macos/*.tar.gz 2>/dev/null || echo "请检查 build/macos/ 目录"
echo ""
echo "安装方式："
echo "  tar -xzf prism-desktop-macos.tar.gz"
echo "  将 PRISM Agent.app 拖入 Applications 文件夹"
