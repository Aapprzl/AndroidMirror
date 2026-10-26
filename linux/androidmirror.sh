#!/bin/bash
# Launcher script for AndroidMirror on Linux

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$PROJECT_DIR"

# Activate virtual environment (if it exists)
if [ -d "$PROJECT_DIR/venv" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
fi

python main.py
