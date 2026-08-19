"""
Smart DNS Injector Middleware: Automatically injects fastest GRC benchmarked DoH into Sing-box configurations.
"""

from typing import List, Dict, Any, Optional

def get_smart_dns_servers(primary_doh: str = "https://223.5.5.5/dns-query", fallback_doh: str = "https://1.1.1.1/dns-query", proxy_tag: str = "proxy-out") -> List[Dict[str, Any]]:
    """Build Sing-box DNS server array with Smart Split-DNS routing."""
    return [
        {
            "tag": "dns-direct",
            "address": primary_doh,
            "detour": "direct"
        },
        {
            "tag": "dns-remote",
            "address": fallback_doh,
            "detour": proxy_tag
        }
    ]
