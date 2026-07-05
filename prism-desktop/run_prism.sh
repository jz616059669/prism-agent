#!/usr/bin/env bash
set -euo pipefail

cd "$(cd "$(dirname "$0")" && pwd)"

if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

export PRISM_SKIP_UPDATE_CHECK=1
mkdir -p logs

echo "Starting PRISM Desktop..."
flet run prism_desktop/main.py 2>&1 | tee logs/latest_launch.log
