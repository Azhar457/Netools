#!/usr/bin/env python3
"""
Netools Suite v2.0 - Main CLI & GUI Entrypoint.
"""

import sys
from pathlib import Path

# Add package directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from netools.cli.main import main

if __name__ == "__main__":
    main()
