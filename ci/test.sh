#!/bin/bash
set -euo pipefail

echo "=== Running tests ==="

cd "$(dirname "$0")/../app"

# Install test dependencies if needed
python -m pip install -q -e . 2>/dev/null || true
python -m pip install -q pytest httpx 2>/dev/null || true

echo "Running pytest..."
python -m pytest tests/ -v --tb=short

echo "✓ All tests passed"
