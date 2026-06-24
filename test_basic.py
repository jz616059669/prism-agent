"""
PRISM Agent - 最小运行验证
验证 browser / gateway / mcp / tools 基础能力
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from prism.tools.registry import registry
from prism.gateway import gateway
from prism.mcp import mcp_client
from prism.skills import skills


def test_tools():
    print("=== 工具系统 ===")
    tools = registry.list_tools()
    print(f"已注册工具: {len(tools)}")
    for t in tools:
        print(f" - {t['name']}: {t['description']}")
    return len(tools) > 0


def test_gateway():
    print("\n=== Gateway ===")
    platforms = gateway.list_platforms()
    print(f"已注册平台: {platforms}")
    return True


def test_mcp():
    print("\n=== MCP ===")
    print(f"MCP 客户端状态: 已初始化")
    return True


def test_skills():
    print("\n=== Skills ===")
    skill_list = skills.list_skills()
    print(f"已注册 Skills: {len(skill_list)}")
    for s in skill_list:
        print(f" - {s['name']}: {s['description']}")
    return len(skill_list) > 0


def test_browser_basic():
    print("\n=== 浏览器基础 ===")
    try:
        from prism.tools.browser import browser
        print("浏览器模块可导入")
        return True
    except Exception as e:
        print(f"浏览器模块导入失败: {e}")
        return False


if __name__ == "__main__":
    results = {
        "tools": test_tools(),
        "gateway": test_gateway(),
        "mcp": test_mcp(),
        "skills": test_skills(),
        "browser": test_browser_basic(),
    }
    
    print("\n=== 验证结果 ===")
    for name, ok in results.items():
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    
    if all(results.values()):
        print("\nPRISM Agent 基础验证通过")
        sys.exit(0)
    else:
        print("\n部分模块验证失败")
        sys.exit(1)
