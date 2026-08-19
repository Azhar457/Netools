# ==============================================================================
# Netools Suite - Windows PowerShell .EXE Builder Script
# ==============================================================================
Write-Host "==> [1/2] Compiling Netools for Windows..." -ForegroundColor Cyan

pyinstaller --name netools `
  --onefile `
  --windowed `
  --collect-all netools `
  --add-data "dns_jumper_db.py;." `
  --add-data "dns_jumper_benchmark.py;." `
  --clean `
  netools.py

Write-Host "==> [2/2] Done! Binary created at: dist\netools.exe" -ForegroundColor Green
