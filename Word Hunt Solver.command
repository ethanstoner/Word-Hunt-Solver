#!/bin/bash
# Word Hunt Solver — double-click to launch on macOS
# Installs requirements if needed, then runs the solver

cd "$(dirname "$0")"

# Create venv if missing
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt 2>/dev/null

# Launch solver in background, then close this terminal window
cd src
python main.py &
SOLVER_PID=$!

# Close the Terminal window that opened this .command file
osascript -e 'tell application "Terminal" to close front window' &

# Wait for solver to finish so cleanup happens
wait $SOLVER_PID
