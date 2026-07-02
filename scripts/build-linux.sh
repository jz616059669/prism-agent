#!/bin/bash
set -e

echo "========================================"
echo "  PRISM Desktop Linux 打包"
echo "========================================"
echo ""

VERSION="2.1.1"
OUTPUT_NAME="prism-desktop-${VERSION}-linux-amd64"

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
    --output "$BUILD_DIR" \
    --artifact-name "$OUTPUT_NAME" 2>/dev/null || \
flet build linux \
    --output "$BUILD_DIR"

echo "[2/3] 打包为 .tar.xz..."
cd "$BUILD_DIR"
BIN_DIR=$(find . -maxdepth 1 -type d -name "PRISM*" -o -type d -name "prism*" | head -n 1)
if [ -n "$BIN_DIR" ]; then
    mv "$BIN_DIR" "$OUTPUT_NAME"
    tar -cJf "${OUTPUT_NAME}.tar.xz" "$OUTPUT_NAME" 2>/dev/null || \
    tar -czf "${OUTPUT_NAME}.tar.gz" "$OUTPUT_NAME"
else
    tar -cJf "${OUTPUT_NAME}.tar.xz" . 2>/dev/null || \
    tar -czf "${OUTPUT_NAME}.tar.gz" .
fi

echo "[3/3] 完成"
echo ""
echo "输出文件："
ls -lh *.tar.* 2>/dev/null || ls -lh
echo ""
echo "安装方式："
echo "  tar -xf ${OUTPUT_NAME}.tar.xz"
echo "  ./${OUTPUT_NAME}/prism-desktop"
