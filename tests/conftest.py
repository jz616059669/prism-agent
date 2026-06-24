import pytest


def pytest_collection_modifyitems(config, items):
    # 已修复 browser pytest 兼容性，不再强制跳过
    pass
