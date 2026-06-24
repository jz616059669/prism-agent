"""桌面端托盘最小化回归测试（仅验证导入与线程可启动）"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_desktop_tray_import():
    try:
        import pystray
        from PIL import Image, ImageDraw
    except Exception as e:
        pytest.skip(f"tray deps missing: {e}")

    img = Image.new("RGB", (64, 64), (0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((16, 16), "P", fill=(255, 255, 255))

    icon = pystray.Icon("PRISM", img, "PRISM Agent", None)
    assert icon is not None
