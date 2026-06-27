"""直接 Playwright 验证"""
import asyncio
import sys
from pathlib import Path

async def main():
    from playwright.async_api import async_playwright
    
    print("启动 Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        page = await browser.new_page()
        
        print("导航到 example.com...")
        await page.goto("https://example.com", wait_until='domcontentloaded')
        await asyncio.sleep(1)
        
        title = await page.title()
        url = page.url
        text = await page.evaluate("() => document.body.textContent || ''")
        html = await page.evaluate("() => document.body.outerHTML || ''")
        
        print(f"标题: {title}")
        print(f"URL: {url}")
        print(f"文本长度: {len(text)}")
        print(f"HTML长度: {len(html)}")
        
        if text.strip():
            print(f"文本: {text[:300]}")
        elif html.strip():
            print(f"HTML前300: {html[:300]}")
        else:
            print("页面完全为空")
        
        await browser.close()
        print("浏览器已关闭")

if __name__ == "__main__":
    asyncio.run(main())
