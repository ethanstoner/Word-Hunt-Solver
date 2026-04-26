#!/bin/bash
# Word Hunt Solver — double-click to launch on macOS

cd "$(dirname "$0")"

# Create venv if missing
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install/update requirements if needed
pip install -q -r requirements.txt 2>/dev/null

# Run the solver — all child processes die when this exits
cd src
exec python main.py "$@"
