#!/usr/bin/env bash
# Start CodeFish locally, entirely from the bundled data.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    echo "No .venv found. Create one first:"
    echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

echo "Starting CodeFish on http://localhost:8000 (Ctrl+C to stop)"
USE_LOCAL_DATA=1 exec .venv/bin/python -m uvicorn backend.main:app --reload --port 8000
