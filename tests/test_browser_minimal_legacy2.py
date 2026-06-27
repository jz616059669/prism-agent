"""最小浏览器验证"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from prism.tools.browser import browser

def main():
    print("启动浏览器...")
    result = browser.navigate("https://example.com", headless=True)
    print(f"导航结果: success={result.get('success')}, url={result.get('url')}")
    print(f"标题: {result.get('title')}")
    print(f"状态码: {result.get('status')}")
    
    # 等待一下让页面完全加载
    import time
    time.sleep(2)
    
    snap = browser.snapshot(full=False)
    content = snap.get("content", "")
    print(f"页面文本长度: {len(content)}")
    if content:
        print(f"内容预览: {content[:300]}")
    else:
        print("内容为空，尝试获取页面HTML...")
        html = browser.evaluate("() => document.documentElement.outerHTML")
        html_content = html.get("result", "")
        print(f"HTML长度: {len(html_content)}")
        if html_content:
            print(f"HTML预览: {html_content[:300]}")
    
    browser.disconnect()
    print("浏览器已关闭")


if __name__ == "__main__":
    main()
