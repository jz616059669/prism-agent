"""代码执行测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from prism.tools.registry import registry


def test_code_execution():
    result = registry.execute("code_execution", code="print('hello prism')\nassert 1+1==2", timeout=15)
    assert result["success"] is True
    assert "hello prism" in result["output"]
