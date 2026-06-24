"""
PRISM Agent - 端到端验证脚本
验证：配置 -> 提供商 -> 模型调用 -> 浏览器 -> 桌面端
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# desktop package lives under prism-desktop/prism_desktop
DESKTOP_ROOT = REPO_ROOT / "prism-desktop"
if str(DESKTOP_ROOT) not in sys.path:
    sys.path.insert(0, str(DESKTOP_ROOT))

from prism.config import config as prism_config, ConfigError
from prism.providers.manager import provider_pool
from prism.tools.browser_bridge import open_page, page_snapshot, close_browser


def check_config():
    print("[1/5] 检查配置...")
    try:
        prism_config.validate()
        print("      配置校验通过")
        return True
    except ConfigError as e:
        print(f"      配置缺失：{e}")
        return False


def check_providers():
    print("[2/5] 检查提供商...")
    providers = provider_pool.list_providers()
    if providers:
        print(f"      已加载提供商：{', '.join(providers)}")
        return True
    print("      未配置可用提供商")
    return False


def check_model_call():
    print("[3/5] 检查模型调用...")
    api_key = prism_config.get("model.api_key") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("      未配置 API Key，跳过真实调用")
        return None

    result = provider_pool.chat([{"role": "user", "content": "hi"}])
    if result.get("success"):
        print(f"      调用成功：{result.get('model')}")
        print(f"      响应：{result.get('content', '')[:60]}...")
        return True
    print(f"      调用失败：{result.get('error')}")
    return False


def check_browser():
    print("[4/5] 检查浏览器...")
    result = open_page("https://example.com", headless=True)
    if result.get("success"):
        print(f"      浏览器已打开：{result.get('url')}")
        snap = page_snapshot()
        if snap.get("success"):
            print(f"      页面快照成功：{snap.get('title', 'N/A')}")
        else:
            print(f"      快照失败：{snap.get('error')}")
        close_browser()
        return True
    print(f"      浏览器失败：{result.get('error')}")
    return False


def check_desktop_import():
    print("[5/5] 检查桌面端导入...")
    try:
        import prism_desktop.main
        print("      桌面端模块导入成功")
        return True
    except Exception as e:
        print(f"      导入失败：{e}")
        print("      可选安装：pip install prism-agent[desktop] 或安装 flet")
        return False


def main():
    print("=" * 50)
    print("  PRISM Agent 端到端验证")
    print("=" * 50)
    print()

    results = []
    results.append(("配置", check_config()))
    results.append(("提供商", check_providers()))
    results.append(("模型调用", check_model_call()))
    results.append(("浏览器", check_browser()))
    results.append(("桌面端", check_desktop_import()))

    print()
    print("=" * 50)
    print("  结果")
    print("=" * 50)
    for name, ok in results:
        status = "✓" if ok else "✗"
        print(f"  {status} {name}")
    print()

    failed = [name for name, ok in results if ok is False]
    if failed:
        print(f"失败项：{', '.join(failed)}")
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    main()
