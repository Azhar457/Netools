#!/usr/bin/env bash
# ==============================================================================
# Netools Suite - macOS .app Bundle & Standalone Binary Builder
# ==============================================================================
set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

echo "==> [1/3] Preparing macOS build environment..."
if [ ! -d ".venv" ]; then
    uv venv .venv || python3 -m venv .venv
fi
uv pip install pyinstaller customtkinter pystray pillow packaging pyobjc-framework-Cocoa || .venv/bin/pip install pyinstaller customtkinter pystray pillow packaging pyobjc-framework-Cocoa

echo "==> [2/3] Building Netools for macOS..."
.venv/bin/pyinstaller   --name Netools   --windowed   --noconfirm   --clean   --strip   --optimize 2   --add-data "assets:assets"   --collect-data netools   --collect-data customtkinter   --hidden-import pystray._darwin   --hidden-import pystray._appindicator   --collect-submodules pyobjc   --exclude-module numpy   --exclude-module scipy   --exclude-module pandas   --exclude-module matplotlib   --exclude-module pytest   --exclude-module unittest   --exclude-module test   --exclude-module tkinter.test   --exclude-module sqlite3   --icon "assets/icon.ico"   netools/__main__.py

echo "==> [3/3] Done! macOS bundle created at: dist/Netools.app"
