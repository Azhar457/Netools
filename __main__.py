#!/usr/bin/env python3
"""
Netools Package Entrypoint (python3 -m netools or python3 netools).
"""

import sys
from pathlib import Path

# Add root directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Also ensure parent / Netools directory is in sys.path
ALT_DIR = BASE_DIR / "Netools"
if ALT_DIR.exists() and str(ALT_DIR) not in sys.path:
    sys.path.insert(0, str(ALT_DIR))

from netools.cli.main import main

if __name__ == "__main__":
    main()
