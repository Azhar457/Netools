#!/usr/bin/env python3
"""
DNS Leak & Security Audit Service.
Orchestrates high-level security audits for active system DNS resolvers and curated presets.
"""

from typing import Any, Dict, List, Optional

from netools.adapters import platform_dns
from netools.libs import dns_db, dns_leak
from netools.libs.logger import get_logger

log = get_logger(__name__)


def quick_transparent_proxy_check() -> Dict[str, Any]:
    """Execute quick check for middlebox / ISP transparent DNS proxy interception."""
    return dns_leak.check_transparent_dns_proxy()


def audit_provider(provider_key: str, mode: str = "ipv4") -> Dict[str, Any]:
    """
    Run comprehensive DNS leak and protocol integrity audit against a preset resolver key.
    """
    providers = dns_db.load_providers()
    prov = providers.get(provider_key)
    if not prov:
        return {
            "error": f"Provider '{provider_key}' not found in database.",
            "security_score": 0,
            "overall_rating": "🔴 Unknown",
        }

    mode_clean = mode.lower()
    if "doh" in mode_clean:
        endpoint = prov.get("doh_url", "")
    elif "dot" in mode_clean:
        endpoint = prov.get("dot_host") or (prov.get("ipv4", [""])[0] if prov.get("ipv4") else "")
    elif "ipv6" in mode_clean:
        v6_list = prov.get("ipv6", [])
        endpoint = v6_list[0] if v6_list else ""
    else:  # ipv4
        v4_list = prov.get("ipv4", [])
        endpoint = v4_list[0] if v4_list else ""

    if not endpoint:
        return {
            "error": f"Provider '{provider_key}' has no valid endpoint for mode '{mode}'.",
            "security_score": 0,
            "overall_rating": "🔴 Unavailable",
        }

    audit_res = dns_leak.run_comprehensive_dns_leak_audit(endpoint, mode=mode)
    audit_res["provider_name"] = prov.get("name", provider_key)
    audit_res["country"] = prov.get("country", "🌐")
    return audit_res


def audit_active_system_dns(device: Optional[str] = None) -> Dict[str, Any]:
    """
    Audit all active DNS resolvers currently configured on the specified network adapter.
    """
    if not device:
        ifaces = platform_dns.get_network_interfaces()
        device = ifaces[0]["device"] if ifaces else "default"

    active_dns = platform_dns.get_interface_dns(device)
    if not active_dns:
        return {
            "device": device,
            "status": "No active static DNS detected (Using DHCP/System Default)",
            "resolvers_audited": [],
            "transparent_proxy": dns_leak.check_transparent_dns_proxy(),
            "overall_score": 50,
            "overall_rating": "🟡 Unaudited (DHCP Default)",
        }

    reports: List[Dict[str, Any]] = []
    total_score = 0

    for ip in active_dns:
        mode = "ipv6" if ":" in ip else "ipv4"
        res = dns_leak.run_comprehensive_dns_leak_audit(ip, mode=mode)
        reports.append(res)
        total_score += res.get("security_score", 0)

    avg_score = int(total_score / max(1, len(reports)))

    if avg_score >= 90:
        rating = "🟢 Excellent (Secure & Private)"
    elif avg_score >= 70:
        rating = "🟡 Good (Minor Warnings)"
    elif avg_score >= 45:
        rating = "🟠 Fair (Security Risks)"
    else:
        rating = "🔴 Critical Risk"

    return {
        "device": device,
        "active_dns": active_dns,
        "resolvers_audited": reports,
        "overall_score": avg_score,
        "overall_rating": rating,
    }
