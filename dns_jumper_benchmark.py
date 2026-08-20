#!/usr/bin/env python3
"""
Backward compatibility shim for netools.libs.dns_benchmark.
"""
from netools.libs.dns_benchmark import *

if __name__ == "__main__":
    import sys
    print("Netools GRC Benchmark Engine loaded from netools.libs.dns_benchmark")
