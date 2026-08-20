#!/usr/bin/env python3
"""
Backward compatibility shim for netools.libs.dns_db.
"""
from netools.libs.dns_db import *

if __name__ == "__main__":
    import sys
    print(f"Loaded {len(load_providers())} DNS providers from netools.libs.dns_db")
