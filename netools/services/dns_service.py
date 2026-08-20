"""
DNS Service: Database, GRC 3-Tier Latency Benchmark, Smart Mix Calculator, and System DNS Setter.
"""

import time
import asyncio
import concurrent.futures
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

import dns_jumper_db as db
import dns_jumper_benchmark as bm
from netools.adapters import systemd_dns as sys_dns

@dataclass
class GRCBenchmarkSummary:
    results: List[bm.GRCBenchmarkResult]
    fastest: Optional[bm.GRCBenchmarkResult]
    best_cached: Optional[bm.GRCBenchmarkResult]
    best_uncached: Optional[bm.GRCBenchmarkResult]
    best_tld: Optional[bm.GRCBenchmarkResult]

def get_providers(region: str = "all", category: str = "all") -> Dict[str, Any]:
    """Retrieve filtered DNS providers from database."""
    all_provs = db.load_providers()
    return db.filter_providers(all_provs, region=region, category=category)

def sync_cloud_database() -> Tuple[bool, str, int]:
    """Synchronize DNS resolvers database with cloud presets."""
    return db.sync_cloud_providers()

def calculate_smart_mix(results: List[bm.GRCBenchmarkResult], mode: str = "ipv4") -> Dict[str, Any]:
    """Compute 1 Cached + 1 Uncached + 1 TLD Smart Mix trio."""
    stable = [r for r in results if r.status == "Stable"] or results
    if not stable:
        return {}

    best_cached = min(stable, key=lambda x: x.cached_ms if x.cached_lats else 9999.0)
    cand_uncached = [r for r in stable if r.key != best_cached.key] or stable
    best_uncached = min(cand_uncached, key=lambda x: x.uncached_ms if x.uncached_lats else 9999.0)

    used = {best_cached.key, best_uncached.key}
    cand_tld = [r for r in stable if r.key not in used] or stable
    best_tld = min(cand_tld, key=lambda x: x.tld_ms if x.tld_lats else 9999.0)

    def _get_target(res):
        if mode == "ipv6" and res.ipv6:
            return res.ipv6[0]
        elif mode == "doh" and res.doh_url:
            return res.doh_url
        elif mode == "dot" and res.dot_host:
            return res.dot_host
        return res.ipv4[0] if res.ipv4 else ""

    return {
        "dns1_cached": best_cached,
        "dns2_uncached": best_uncached,
        "dns3_tld": best_tld,
        "ips": [
            _get_target(best_cached),
            _get_target(best_uncached),
            _get_target(best_tld)
        ]
    }
