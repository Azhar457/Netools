# ==============================================================================
# Netools Suite - Windows PowerShell .EXE Builder Script
# ==============================================================================
Write-Host "==> [1/2] Compiling Netools for Windows..." -ForegroundColor Cyan

pyinstaller --name netools `
  --onefile `
  --windowed `
  --strip `
  --optimize 2 `
  --add-data "assets;assets" `
  --collect-data netools `
  --collect-data customtkinter `
  --exclude-module numpy `
  --exclude-module scipy `
  --exclude-module pandas `
  --exclude-module matplotlib `
  --exclude-module pytest `
  --exclude-module unittest `
  --exclude-module test `
  --exclude-module tkinter.test `
  --icon "assets\icon.ico" `
  --clean `
  netools/__main__.py

Write-Host "==> [2/2] Done! Binary created at: dist\netools.exe" -ForegroundColor Green

