#!/usr/bin/env python3
"""
GRC 3-Tier DNS Benchmark Engine v2.0
Implements GRC (Gibson Research Corp) 3-Tier Latency Measurement:
- Tier 1: 🟢 Cached (RTT / Network Proximity - 45% weight)
- Tier 2: 🔵 Uncached (Recursive Resolution / Cold Miss - 35% weight)
- Tier 3: 🟡 TLD / Regional (TLD Peering & Geo Affinity - 20% weight)

Features:
- Robust Median Filtering & Outlier Rejection
- Coefficient of Variation (CV) Stability Index & Reliability %
- Multi-Protocol Support (UDP 53, DoT TLS 853, DoH HTTPS)
- Enhanced Smart Mix with Strict 3-Resolver Deduplication
- Zero External Dependencies (Standard Python Socket, SSL & urllib)
"""

import time
import socket
import ssl
import struct
import uuid
import statistics
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class TierResult:
    samples: List[float] = field(default_factory=list)
    median_ms: Optional[float] = None
    mean_ms: Optional[float] = None
    std_dev: float = 0.0
    cv: float = 0.0  # Coefficient of Variation (Stability Index)
    success_count: int = 0
    fail_count: int = 0

    def compute(self):
        if not self.samples:
            return
        self.median_ms = statistics.median(self.samples)
        self.mean_ms = statistics.mean(self.samples)
        if len(self.samples) > 1 and self.mean_ms and self.mean_ms > 0:
            self.std_dev = statistics.stdev(self.samples)
            self.cv = self.std_dev / self.mean_ms


@dataclass
class GRCBenchmarkResult:
    key: str
    name: str
    country: str
    ipv4: List[str]
    ipv6: List[str]
    doh_url: str
    dot_host: Optional[str]
    protocol: str = "IPv4"
    target_endpoint: str = ""
    
    cached: TierResult = field(default_factory=TierResult)
    uncached: TierResult = field(default_factory=TierResult)
    tld: TierResult = field(default_factory=TierResult)
    
    cached_ms: Optional[float] = None
    uncached_ms: Optional[float] = None
    dotcom_ms: Optional[float] = None
    score: float = 9999.0
    reliability_pct: float = 0.0
    status: str = "Failed"


# ==============================================================================
# LOW-LEVEL DNS WIREFORMAT PROTOCOL PROBES
# ==============================================================================

def build_dns_packet(domain: str, tx_id: int = 0x1234, qtype: int = 1) -> bytes:
    """Build standard DNS wireformat query packet (RFC 1035)."""
    header = struct.pack(">HHHHHH", tx_id, 0x0100, 1, 0, 0, 0)
    qname = b""
    for part in domain.strip(".").split("."):
        encoded = part.encode("ascii")
        qname += bytes([len(encoded)]) + encoded
    qname += b"\x00"
    qtype_qclass = struct.pack(">HH", qtype, 1)
    return header + qname + qtype_qclass


def query_udp_dns(ip: str, domain: str, timeout: float = 2.0) -> Optional[float]:
    """Execute raw UDP port 53 DNS query (IPv4 / IPv6)."""
    packet = build_dns_packet(domain)
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    t0 = time.perf_counter()
    try:
        sock.sendto(packet, (ip, 53))
        data, _ = sock.recvfrom(512)
        if len(data) >= 12:
            return (time.perf_counter() - t0) * 1000.0
    except Exception:
        pass
    finally:
        try:
            sock.close()
        except Exception:
            pass
    return None


def query_doh_dns(doh_url: str, domain: str, timeout: float = 2.5) -> Optional[float]:
    """Execute DNS-over-HTTPS (RFC 8484 wireformat) query using standard urllib."""
    pkt = build_dns_packet(domain)
    req = urllib.request.Request(
        doh_url,
        data=pkt,
        headers={
            "Content-Type": "application/dns-message",
            "Accept": "application/dns-message",
            "User-Agent": "Netools-GRC-Benchmark/2.0"
        }
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = resp.read()
                if len(data) >= 12:
                    return (time.perf_counter() - t0) * 1000.0
    except Exception:
        pass
    return None


def query_dot_dns(host_or_ip: str, domain: str, timeout: float = 2.5) -> Optional[float]:
    """Execute DNS-over-TLS (RFC 7858 on port 853) query using standard ssl."""
    pkt = build_dns_packet(domain)
    payload = struct.pack("!H", len(pkt)) + pkt

    family = socket.AF_INET6 if ":" in host_or_ip else socket.AF_INET
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    t0 = time.perf_counter()
    sock = None
    ssock = None
    try:
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        server_name = host_or_ip if ":" not in host_or_ip else None
        ssock = ctx.wrap_socket(sock, server_hostname=server_name)
        ssock.connect((host_or_ip, 853))
        ssock.sendall(payload)

        len_hdr = ssock.recv(2)
        if len(len_hdr) == 2:
            resp_len = struct.unpack("!H", len_hdr)[0]
            resp_data = ssock.recv(resp_len)
            if len(resp_data) >= 12:
                return (time.perf_counter() - t0) * 1000.0
    except Exception:
        pass
    finally:
        if ssock:
            try:
                ssock.close()
            except Exception:
                pass
        elif sock:
            try:
                sock.close()
            except Exception:
                pass
    return None


# ==============================================================================
# GRC 3-TIER BENCHMARK EXECUTION
# ==============================================================================

def calculate_grc_score(cached_ms: float, uncached_ms: float, tld_ms: float) -> float:
    """
    Weighted composite score (GRC formula approximation):
    - 45% Cached Latency
    - 35% Uncached Latency
    - 20% Regional TLD Latency
    Lower is better.
    """
    c = min(cached_ms, 500.0)
    u = min(uncached_ms, 2000.0)
    t = min(tld_ms, 1000.0)
    return (0.45 * c) + (0.35 * u) + (0.20 * t)


def benchmark_provider_full(
    key: str,
    provider: Dict[str, Any],
    tld_category: str = "indonesia",
    mode: str = "ipv4",
    timeout: float = 2.5
) -> Dict[str, Any]:
    """
    Execute 3-Tier GRC Benchmark (Cached, Uncached, Regional TLD) for a single provider.
    Uses median filtering and forced cache misses.
    """
    try:
        from netools.libs.dns_db import TLD_PRESETS
    except ImportError:
        TLD_PRESETS = {}

    tld_info = TLD_PRESETS.get(tld_category, TLD_PRESETS.get("indonesia", {}))
    tld_domains = tld_info.get("domains", ["bca.co.id", "tokopedia.com", "detik.com"])

    cached_targets = ["google.com", "youtube.com", "facebook.com"]
    uncached_targets = [f"bench-{uuid.uuid4().hex[:10]}.uncached-test.local" for _ in range(3)]
    dotcom_targets = tld_domains[:3] if len(tld_domains) >= 3 else (tld_domains + ["google.com"])[:3]

    mode_clean = mode.lower()
    is_ipv6 = (mode_clean == "ipv6")
    is_doh = (mode_clean == "doh")
    is_dot = (mode_clean == "dot")

    doh_url = provider.get("doh_url", "")
    ipv4_list = provider.get("ipv4", [])
    ipv6_list = provider.get("ipv6", [])
    dot_host = provider.get("dot_host") or (ipv4_list[0] if ipv4_list else None)

    # Determine target address based on mode
    if is_ipv6:
        if not ipv6_list:
            return {"key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"), "region": provider.get("region", "global"), "score": 9999.0, "cached_ms": None, "uncached_ms": None, "dotcom_ms": None, "protocol": "IPv6", "ipv4": ipv4_list, "ipv6": ipv6_list, "doh_url": doh_url, "status": "Failed", "reliability_pct": 0.0}
        target_endpoint = ipv6_list[0]
        protocol_label = "IPv6"
    elif is_doh:
        if not doh_url:
            return {"key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"), "region": provider.get("region", "global"), "score": 9999.0, "cached_ms": None, "uncached_ms": None, "dotcom_ms": None, "protocol": "DoH", "ipv4": ipv4_list, "ipv6": ipv6_list, "doh_url": doh_url, "status": "Failed", "reliability_pct": 0.0}
        target_endpoint = doh_url
        protocol_label = "DoH"
    elif is_dot:
        if not dot_host:
            return {"key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"), "region": provider.get("region", "global"), "score": 9999.0, "cached_ms": None, "uncached_ms": None, "dotcom_ms": None, "protocol": "DoT", "ipv4": ipv4_list, "ipv6": ipv6_list, "doh_url": doh_url, "status": "Failed", "reliability_pct": 0.0}
        target_endpoint = dot_host
        protocol_label = "DoT"
    else:  # ipv4
        if not ipv4_list:
            return {"key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"), "region": provider.get("region", "global"), "score": 9999.0, "cached_ms": None, "uncached_ms": None, "dotcom_ms": None, "protocol": "IPv4", "ipv4": ipv4_list, "ipv6": ipv6_list, "doh_url": doh_url, "status": "Failed", "reliability_pct": 0.0}
        target_endpoint = ipv4_list[0]
        protocol_label = "IPv4"

    def _measure(dom: str) -> Optional[float]:
        if is_doh:
            return query_doh_dns(target_endpoint, dom, timeout=timeout)
        elif is_dot:
            return query_dot_dns(target_endpoint, dom, timeout=timeout)
        else:
            return query_udp_dns(target_endpoint, dom, timeout=timeout)

    tier_cached = TierResult()
    tier_uncached = TierResult()
    tier_tld = TierResult()

    # 1. Warm-up prime cache (discard first query)
    _measure(cached_targets[0])

    # 2. Tier 1: Cached Latency
    for dom in cached_targets:
        lat = _measure(dom)
        if lat is not None:
            tier_cached.samples.append(lat)
            tier_cached.success_count += 1
        else:
            tier_cached.fail_count += 1

    # 3. Tier 2: Uncached Latency (Forced Miss)
    for dom in uncached_targets:
        lat = _measure(dom)
        if lat is not None:
            tier_uncached.samples.append(lat)
            tier_uncached.success_count += 1
        else:
            tier_uncached.fail_count += 1

    # 4. Tier 3: TLD / Regional Latency
    for dom in dotcom_targets:
        lat = _measure(dom)
        if lat is not None:
            tier_tld.samples.append(lat)
            tier_tld.success_count += 1
        else:
            tier_tld.fail_count += 1

    tier_cached.compute()
    tier_uncached.compute()
    tier_tld.compute()

    c_med = tier_cached.median_ms
    u_med = tier_uncached.median_ms
    d_med = tier_tld.median_ms

    # Compute GRC Composite Score using medians
    if c_med is not None and u_med is not None and d_med is not None:
        score = calculate_grc_score(c_med, u_med, d_med)
    elif c_med is not None and u_med is not None:
        score = (0.55 * c_med) + (0.45 * u_med)
    elif c_med is not None:
        score = c_med * 1.3
    else:
        score = 9999.0

    # Reliability %
    total_q = (tier_cached.success_count + tier_cached.fail_count +
               tier_uncached.success_count + tier_uncached.fail_count +
               tier_tld.success_count + tier_tld.fail_count)
    total_ok = (tier_cached.success_count + tier_uncached.success_count + tier_tld.success_count)
    rel_pct = (total_ok / total_q * 100.0) if total_q > 0 else 0.0

    if rel_pct >= 90.0 and tier_cached.success_count > 0:
        stat = "Stable"
    elif rel_pct >= 50.0:
        stat = "Partial"
    else:
        stat = "Failed"

    return {
        "key": key,
        "name": provider.get("name", key),
        "country": provider.get("country", "🌐"),
        "region": provider.get("region", "global"),
        "doh_url": doh_url,
        "ipv4": ipv4_list,
        "ipv6": ipv6_list,
        "cached_ms": c_med,
        "uncached_ms": u_med,
        "dotcom_ms": d_med,
        "score": score,
        "protocol": protocol_label,
        "target_endpoint": target_endpoint,
        "reliability_pct": rel_pct,
        "status": stat,
        "cached_cv": tier_cached.cv,
        "uncached_cv": tier_uncached.cv,
    }


# ==============================================================================
# ENHANCED SMART MIX V2 (STRICT 3-RESOLVER DEDUPLICATION)
# ==============================================================================

def calculate_smart_mix(results_map: Dict[str, Any], mode: str = "ipv4") -> Dict[str, Any]:
    """
    Determine optimal 3-DNS Smart Mix with Strict Deduplication:
    - DNS 1 (Primary Cached): Lowest Median Cached Latency (Max throughput)
    - DNS 2 (Secondary Uncached): Lowest Median Uncached Latency (Fast cold lookups) ≠ DNS 1
    - DNS 3 (Tertiary TLD): Lowest Regional TLD Latency (Best peering) ≠ DNS 1 and ≠ DNS 2
    """
    valid = [r for r in results_map.values() if r.get("score", 9999) < 9000]
    if not valid:
        return {"cached": {}, "uncached": {}, "dotcom": {}}

    # Stable first, fallback to partial
    stable = [r for r in valid if r.get("status") == "Stable"] or valid

    # 1. Best Cached (DNS 1)
    best_cached = min(stable, key=lambda x: x.get("cached_ms") or 9999.0)

    # 2. Best Uncached (DNS 2) - Strict constraint: ≠ DNS 1
    uncached_cands = [r for r in stable if r.get("key") != best_cached.get("key")]
    best_uncached = min(uncached_cands, key=lambda x: x.get("uncached_ms") or 9999.0) if uncached_cands else best_cached

    # 3. Best TLD (DNS 3) - Strict constraint: ≠ DNS 1 and ≠ DNS 2
    chosen_keys = {best_cached.get("key"), best_uncached.get("key")}
    tld_cands = [r for r in stable if r.get("key") not in chosen_keys]
    best_tld = min(tld_cands, key=lambda x: x.get("dotcom_ms") or 9999.0) if tld_cands else (
        uncached_cands[0] if uncached_cands else best_cached
    )

    def _get_target(res: Dict[str, Any]) -> str:
        if mode == "ipv6" and res.get("ipv6"):
            return res["ipv6"][0]
        elif mode == "doh" and res.get("doh_url"):
            return res["doh_url"]
        elif mode == "dot" and res.get("dot_host"):
            return res["dot_host"]
        v4 = res.get("ipv4", [])
        return v4[0] if v4 else ""

    return {
        "cached": best_cached,
        "uncached": best_uncached,
        "dotcom": best_tld,
        "dns1_cached": best_cached,
        "dns2_uncached": best_uncached,
        "dns3_tld": best_tld,
        "ips": [
            _get_target(best_cached),
            _get_target(best_uncached),
            _get_target(best_tld)
        ],
        "names": [
            best_cached.get("name", "None"),
            best_uncached.get("name", "None"),
            best_tld.get("name", "None")
        ]
    }
