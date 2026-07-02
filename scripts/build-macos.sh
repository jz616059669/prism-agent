#!/bin/bash
set -e

echo "========================================"
echo "  PRISM Desktop macOS 打包"
echo "========================================"
echo ""

VERSION="2.1.1"
APP_NAME="PRISM Agent"
OUTPUT_NAME="prism-desktop-${VERSION}-macos"

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
    --output "$BUILD_DIR" \
    --artifact-name "$OUTPUT_NAME" 2>/dev/null || \
flet build macos \
    --output "$BUILD_DIR"

echo "[2/4] 打包为 .tar.gz..."
cd "$BUILD_DIR"
APP_BUNDLE=$(find . -maxdepth 1 -type d -name "*.app" | head -n 1)
if [ -n "$APP_BUNDLE" ]; then
    tar -czf "${OUTPUT_NAME}.tar.gz" "$APP_BUNDLE"
else
    tar -czf "${OUTPUT_NAME}.tar.gz" *
fi

echo "[3/4] 清理..."
cd ../..
rm -rf "$BUILD_DIR"

echo "[4/4] 完成"
echo ""
echo "输出文件："
ls -lh build/macos/*.tar.gz 2>/dev/null || echo "请检查 build/macos/ 目录"
echo ""
echo "安装方式："
echo "  tar -xzf ${OUTPUT_NAME}.tar.gz"
echo "  将 ${APP_NAME}.app 拖入 Applications 文件夹"
