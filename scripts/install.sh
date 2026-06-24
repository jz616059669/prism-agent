#!/bin/bash
set -e

echo "========================================"
echo "  PRISM Agent 一键安装"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 Python3，请先安装 Python 3.11+"
    exit 1
fi

# 检查 uv
if ! command -v uv &> /dev/null; then
    echo "[安装] 正在安装 uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source ~/.bashrc 2>/dev/null || true
fi

echo "[1/4] 安装 PRISM CLI..."
pip install -e .

echo "[2/4] 安装浏览器引擎..."
playwright install chromium

echo "[3/4] 初始化配置..."
mkdir -p ~/.prism
if [ ! -f ~/.prism/config.yaml ]; then
    cp config.example.yaml ~/.prism/config.yaml
    echo "[提示] 已创建默认配置，请编辑 ~/.prism/config.yaml 填入 API Key"
else
    echo "[跳过] 配置文件已存在"
fi

echo "[4/4] 安装桌面客户端..."
cd prism-desktop
uv tool install -e .
cd ..

echo ""
echo "========================================"
echo "  安装完成"
echo "========================================"
echo ""
echo "快速开始："
echo "  prism --help"
echo "  prism-desktop"
echo ""
