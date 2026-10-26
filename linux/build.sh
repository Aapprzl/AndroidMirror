#!/bin/bash
# Linux build script for AndroidMirror
# Produces a standalone executable using PyInstaller

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "==> Installing Python dependencies..."
pip install -r requirements.txt
pip install pyinstaller

echo "==> Building AndroidMirror for Linux..."
pyinstaller \
    --onefile \
    --windowed \
    --name "AndroidMirror" \
    --add-data "linux:linux" \
    --add-data "ui:ui" \
    --add-data "core/config_manager.py:core" \
    --add-data "icon.png:." \
    --icon "icon.png" \
    main.py

echo "==> Done! Executable at: dist/AndroidMirror"
