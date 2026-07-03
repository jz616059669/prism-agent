@echo off
chcp 65001 >nul
echo ========================================
echo   PRISM Agent 本地发布
echo ========================================
echo.

REM 清理旧包
if exist dist rd /s /q dist
if exist build rd /s /q build

echo [1/4] 构建分发包...
uv build

echo [2/4] 校验包...
uv run python -c "
from pathlib import Path
d = Path('dist')
files = list(d.glob('*'))
print('生成文件：')
for f in files:
    print(' ', f.name, f.stat().st_size, 'bytes')
"

echo [3/4] 生成发布清单...
echo # PRISM Agent 本地发布包 > dist\RELEASE.txt
echo. >> dist\RELEASE.txt
echo 构建时间：%date% %time% >> dist\RELEASE.txt
echo 版本：2.1.2 >> dist\RELEASE.txt
echo. >> dist\RELEASE.txt
echo 文件： >> dist\RELEASE.txt
uv run python -c "
from pathlib import Path
d = Path('dist')
for f in sorted(d.glob('*')):
    if f.is_file() and f.name != 'RELEASE.txt':
        print(f'  {f.name}')
" >> dist\RELEASE.txt

echo [4/4] 完成
echo.
echo 输出目录：dist\
dir /b dist 2>nul
echo.
echo 下一步：
echo   1. 手动上传到 PyPI：twine upload dist/*
echo   2. 或保留本地包供内部分发
echo.
pause
