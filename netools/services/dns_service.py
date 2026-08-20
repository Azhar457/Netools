"""
DNS Service: Database, GRC 3-Tier Latency Benchmark, Smart Mix Calculator, and System DNS Setter.
"""

from typing import Any, Dict, Tuple

from netools.libs import dns_benchmark as bm
from netools.libs import dns_db as db


def get_providers(region: str = "all", category: str = "all") -> Dict[str, Any]:
    """Retrieve filtered DNS providers from database."""
    all_provs = db.load_providers()
    return db.filter_providers(all_provs, region=region, category=category)

def sync_cloud_database() -> Tuple[bool, str, int]:
    """Synchronize DNS resolvers database with cloud presets."""
    return db.sync_cloud_providers()

def calculate_smart_mix(results: Any, mode: str = "ipv4") -> Dict[str, Any]:
    """Compute 1 Cached + 1 Uncached + 1 TLD Smart Mix trio with strict deduplication."""
    if isinstance(results, dict):
        return bm.calculate_smart_mix(results, mode=mode)
    elif isinstance(results, list):
        res_map = {}
        for idx, r in enumerate(results):
            k = getattr(r, "key", None) or (r.get("key") if isinstance(r, dict) else f"res_{idx}")
            if isinstance(r, dict):
                res_map[k] = r
            else:
                res_map[k] = {
                    "key": getattr(r, "key", k),
                    "name": getattr(r, "name", "Unknown"),
                    "ipv4": getattr(r, "ipv4", []),
                    "ipv6": getattr(r, "ipv6", []),
                    "doh_url": getattr(r, "doh_url", ""),
                    "dot_host": getattr(r, "dot_host", None),
                    "cached_ms": getattr(r, "cached_ms", None),
                    "uncached_ms": getattr(r, "uncached_ms", None),
                    "dotcom_ms": getattr(r, "dotcom_ms", None),
                    "score": getattr(r, "score", 9999.0),
                    "status": getattr(r, "status", "Stable"),
                }
        return bm.calculate_smart_mix(res_map, mode=mode)
    return {}
