#!/bin/bash
set -e

echo "========================================"
echo "  PRISM Agent 本地发布"
echo "========================================"
echo ""

# 清理旧包
rm -rf dist build

echo "[1/4] 构建分发包..."
uv build

echo "[2/4] 校验包..."
uv run python -c "
from pathlib import Path
d = Path('dist')
files = sorted([f for f in d.glob('*') if f.is_file()])
print('生成文件：')
for f in files:
    print(' ', f.name, f.stat().st_size, 'bytes')
"

echo "[3/4] 生成发布清单..."
{
  echo "# PRISM Agent 本地发布包"
  echo ""
  echo "构建时间：$(date '+%Y-%m-%d %H:%M:%S')"
  echo "版本：$(grep -E '^version' pyproject.toml | head -n1 | sed -E 's/version *= *\"([^\"]+)\".*/\1/')"
  echo ""
  echo "文件："
  uv run python -c "
from pathlib import Path
d = Path('dist')
for f in sorted([f for f in d.glob('*') if f.is_file()]):
    if f.name != 'RELEASE.txt':
        print(f'  {f.name}')
"
} > dist/RELEASE.txt

echo "[4/4] 完成"
echo ""
echo "输出目录：dist/"
ls -1 dist/ 2>/dev/null || true
echo ""
echo "下一步："
echo "  1. 手动上传到 PyPI：twine upload dist/*"
echo "  2. 或保留本地包供内部分发"
echo ""
