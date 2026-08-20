@echo off
REM ==============================================================================
REM Netools Suite - Windows Single .EXE Builder Script
REM Requires Python 3.10+ and PyInstaller (or uv) on Windows.
REM ==============================================================================

echo [1/3] Installing dependencies and PyInstaller...
pip install pyinstaller || uv pip install pyinstaller

echo [2/3] Building Netools.exe standalone executable...
pyinstaller --name netools ^
  --onefile ^
  --windowed ^
  --collect-all netools ^
  --clean ^
  netools/__main__.py

echo [3/3] Build complete!
echo Output executable located at: dist\netools.exe
pause
