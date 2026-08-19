#!/usr/bin/env python3
"""
DNS Jumper GRC 3-Tier Benchmark Engine
Implements GRC-style Cached, Uncached, and Custom TLD Latency Measurement for DoH & UDP DNS.
Zero external dependencies (pure Python standard library).
"""

import time
import socket
import struct
import uuid
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple, Any

# Helper to build DNS wireformat packet
def build_dns_packet(domain: str, tx_id: int = 0x1234, qtype: int = 1) -> bytes:
    header = struct.pack(">HHHHHH", tx_id, 0x0100, 1, 0, 0, 0)
    qname = b""
    for part in domain.strip(".").split("."):
        encoded = part.encode("ascii")
        qname += bytes([len(encoded)]) + encoded
    qname += b"\x00"
    qtype_qclass = struct.pack(">HH", qtype, 1)
    return header + qname + qtype_qclass


def query_udp_dns(ip: str, domain: str, timeout: float = 2.0) -> Optional[float]:
    """Execute raw UDP port 53 DNS query (GRC Socket benchmark)."""
    packet = build_dns_packet(domain)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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


def benchmark_provider_full(
    key: str,
    provider: Dict[str, Any],
    tld_category: str = "indonesia",
    mode: str = "standard",
    timeout: float = 2.5
) -> Dict[str, Any]:
    """
    Execute 3-Tier GRC Benchmark (Cached, Uncached, Regional TLD) for a single provider.
    Returns composite score and individual tier latencies.
    """
    try:
        from dns_jumper_db import TLD_PRESETS
    except ImportError:
        TLD_PRESETS = {}

    tld_info = TLD_PRESETS.get(tld_category, TLD_PRESETS.get("indonesia", {}))
    tld_domains = tld_info.get("domains", ["bca.co.id", "tokopedia.com", "detik.com"])

    cached_targets = ["google.com", "youtube.com", "facebook.com"]
    uncached_targets = [f"bench-{uuid.uuid4().hex[:8]}.example.org" for _ in range(3)]
    dotcom_targets = tld_domains[:4]

    is_doh = (mode == "doh") or (not provider.get("ipv4") and bool(provider.get("doh_url")))
    doh_url = provider.get("doh_url", "")
    ips = provider.get("ipv4", [])
    primary_ip = ips[0] if ips else None

    def _measure(dom: str) -> Optional[float]:
        if is_doh and doh_url:
            return query_doh_dns(doh_url, dom, timeout=timeout)
        elif primary_ip:
            return query_udp_dns(primary_ip, dom, timeout=timeout)
        return None

    # 1. Warmup / Prime Cache
    for dom in cached_targets:
        _measure(dom)

    # 2. Tier 1: Cached Latency
    cached_lats = []
    for dom in cached_targets:
        lat = _measure(dom)
        if lat is not None:
            cached_lats.append(lat)

    # 3. Tier 2: Uncached Latency
    uncached_lats = []
    for dom in uncached_targets:
        lat = _measure(dom)
        if lat is not None:
            uncached_lats.append(lat)

    # 4. Tier 3: TLD / Regional Latency
    dotcom_lats = []
    for dom in dotcom_targets:
        lat = _measure(dom)
        if lat is not None:
            dotcom_lats.append(lat)

    c_avg = sum(cached_lats) / len(cached_lats) if cached_lats else None
    u_avg = sum(uncached_lats) / len(uncached_lats) if uncached_lats else None
    d_avg = sum(dotcom_lats) / len(dotcom_lats) if dotcom_lats else None

    # Weighted Composite GRC Score (45% Cached, 35% Uncached, 20% TLD)
    if c_avg is not None and u_avg is not None and d_avg is not None:
        score = (0.45 * c_avg) + (0.35 * u_avg) + (0.20 * d_avg)
    elif c_avg is not None and u_avg is not None:
        score = (0.55 * c_avg) + (0.45 * u_avg)
    elif c_avg is not None:
        score = c_avg * 1.3
    else:
        score = 9999.0

    return {
        "key": key,
        "name": provider.get("name", key),
        "country": provider.get("country", "🌐"),
        "region": provider.get("region", "global"),
        "doh_url": doh_url,
        "ipv4": ips,
        "cached_ms": c_avg,
        "uncached_ms": u_avg,
        "dotcom_ms": d_avg,
        "score": score,
        "is_doh": is_doh,
    }
