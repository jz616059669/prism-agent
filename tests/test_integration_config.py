"""
PRISM Agent - 集成测试：Config 校验 + 版本单源
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_version import EXPECTED, files


def test_version_file_is_single_source_of_truth():
    assert EXPECTED, "VERSION file must not be empty"
    assert len(EXPECTED.splitlines()) == 1, "VERSION must be a single line"


def test_pyproject_versions_match_version_file():
    bad = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        import re
        m = re.search(r"(?m)^version\s*=\s*['\"]([^'\"]+)['\"]", text)
        assert m, f"version missing in {path}"
        assert m.group(1) == EXPECTED, f"version mismatch in {path}: {m.group(1)} != {EXPECTED}"


def test_config_validate_raises_on_missing_required():
    from prism.config import Config, ConfigError
    cfg = Config.__new__(Config)
    cfg._config = {"model": {}}
    try:
        cfg.validate()
    except ConfigError:
        pass
    else:
        raise AssertionError("expected ConfigError for missing model.default")


def test_config_validate_passes_with_minimal_valid():
    from prism.config import Config
    cfg = Config.__new__(Config)
    cfg._config = {
        "model": {
            "default": "step-3.7-flash",
            "provider": "stepfun",
            "base_url": "https://api.stepfun.com/step_plan/v1",
            "api_key": "sk-test",
        }
    }
    cfg.validate()  # should not raise
