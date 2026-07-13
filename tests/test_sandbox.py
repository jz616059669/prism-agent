"""
PRISM Agent - Code Interpreter Sandbox tests
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from prism.sandbox import run_sandbox, _ALLOWED_MODULES


def test_sandbox_math():
    res = run_sandbox("print(1 + 1)")
    assert res["success"] is True
    assert "2" in res["output"]


def test_sandbox_timeout():
    res = run_sandbox("import time; time.sleep(10)", timeout=1)
    assert res["success"] is False
    assert "timed out" in res["error"]


def test_sandbox_allowed_module():
    res = run_sandbox("import math; print(math.sqrt(16))")
    assert res["success"] is True
    assert "4.0" in res["output"]


def test_sandbox_blocked_module():
    res = run_sandbox("import os; print(os.listdir('.'))")
    assert res["success"] is False
    assert "not allowed" in res["error"]


def test_sandbox_plot_generation():
    res = run_sandbox("import matplotlib.pyplot as plt; fig = plt.figure(); plt.plot([1, 2, 3]); plt.savefig('/tmp/test.png')")
    assert res["success"] is True
    assert len(res["plots"]) >= 1
