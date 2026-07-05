#!/usr/bin/env python3
"""Version consistency checker.
Single source of truth is the VERSION file at repo root.
Both pyproject.toml files must match it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
EXPECTED = VERSION_FILE.read_text(encoding="utf-8").strip()

if not EXPECTED:
    print("VERSION file is empty")
    sys.exit(1)

files = [
    ROOT / "pyproject.toml",
    ROOT / "prism-desktop" / "pyproject.toml",
]

ok = True
for path in files:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"(?m)^version\s*=\s*['\"]([^'\"]+)['\"]", text)
    if not m:
        print(f"version missing in {path}")
        ok = False
        continue
    found = m.group(1)
    if found != EXPECTED:
        print(f"version mismatch in {path}: {found} != {EXPECTED}")
        ok = False
    else:
        print(f"version ok in {path}: {found}")

if not ok:
    sys.exit(1)
print(f"all versions match: {EXPECTED}")
