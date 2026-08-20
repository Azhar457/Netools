#!/usr/bin/env python3
"""
DNS Jumper GRC 3-Tier Benchmark Engine
Implements GRC-style Cached, Uncached, and Custom TLD Latency Measurement for IPv4, IPv6, DoH & DoT.
Zero external dependencies (pure Python standard library).
"""

import time
import socket
import ssl
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
    """Execute raw UDP port 53 DNS query (Supports both IPv4 and IPv6)."""
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


def benchmark_provider_full(
    key: str,
    provider: Dict[str, Any],
    tld_category: str = "indonesia",
    mode: str = "ipv4",
    timeout: float = 2.5
) -> Dict[str, Any]:
    """
    Execute 3-Tier GRC Benchmark (Cached, Uncached, Regional TLD) for a single provider.
    Supports mode: 'ipv4', 'ipv6', 'doh', 'dot', 'standard'.
    """
    try:
        from netools.libs.dns_db import TLD_PRESETS
    except ImportError:
        TLD_PRESETS = {}

    tld_info = TLD_PRESETS.get(tld_category, TLD_PRESETS.get("indonesia", {}))
    tld_domains = tld_info.get("domains", ["bca.co.id", "tokopedia.com", "detik.com"])

    cached_targets = ["google.com", "youtube.com", "facebook.com"]
    uncached_targets = [f"bench-{uuid.uuid4().hex[:8]}.example.org" for _ in range(3)]
    dotcom_targets = tld_domains[:4]

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
            return {"key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"), "region": provider.get("region", "global"), "score": 9999.0, "cached_ms": None, "uncached_ms": None, "dotcom_ms": None, "protocol": "IPv6", "ipv4": ipv4_list, "ipv6": ipv6_list, "doh_url": doh_url}
        target_endpoint = ipv6_list[0]
        protocol_label = "IPv6"
    elif is_doh:
        if not doh_url:
            return {"key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"), "region": provider.get("region", "global"), "score": 9999.0, "cached_ms": None, "uncached_ms": None, "dotcom_ms": None, "protocol": "DoH", "ipv4": ipv4_list, "ipv6": ipv6_list, "doh_url": doh_url}
        target_endpoint = doh_url
        protocol_label = "DoH"
    elif is_dot:
        if not dot_host:
            return {"key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"), "region": provider.get("region", "global"), "score": 9999.0, "cached_ms": None, "uncached_ms": None, "dotcom_ms": None, "protocol": "DoT", "ipv4": ipv4_list, "ipv6": ipv6_list, "doh_url": doh_url}
        target_endpoint = dot_host
        protocol_label = "DoT"
    else:  # ipv4 / standard
        if not ipv4_list:
            return {"key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"), "region": provider.get("region", "global"), "score": 9999.0, "cached_ms": None, "uncached_ms": None, "dotcom_ms": None, "protocol": "IPv4", "ipv4": ipv4_list, "ipv6": ipv6_list, "doh_url": doh_url}
        target_endpoint = ipv4_list[0]
        protocol_label = "IPv4"

    def _measure(dom: str) -> Optional[float]:
        if is_doh:
            return query_doh_dns(target_endpoint, dom, timeout=timeout)
        elif is_dot:
            return query_dot_dns(target_endpoint, dom, timeout=timeout)
        else:
            return query_udp_dns(target_endpoint, dom, timeout=timeout)

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
        "ipv4": ipv4_list,
        "ipv6": ipv6_list,
        "cached_ms": c_avg,
        "uncached_ms": u_avg,
        "dotcom_ms": d_avg,
        "score": score,
        "protocol": protocol_label,
        "target_endpoint": target_endpoint
    }


def calculate_smart_mix(results_map: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine the optimal 3-DNS Smart Mix:
    - Primary (DNS 1): Lowest Cached Latency (Max throughput for frequent domains)
    - Secondary (DNS 2): Lowest Uncached Latency (Fast cold lookups)
    - Tertiary (DNS 3): Lowest Regional TLD / Dot-Com Latency (Best peering)
    """
    valid = [r for r in results_map.values() if r.get("score", 9999) < 9000]
    if not valid:
        return {"cached": {}, "uncached": {}, "dotcom": {}}

    # 1. Best Cached
    best_cached = min(valid, key=lambda x: x.get("cached_ms") or 9999)

    # 2. Best Uncached (prefer distinct provider)
    uncached_cands = [r for r in valid if r.get("key") != best_cached.get("key")]
    best_uncached = min(uncached_cands, key=lambda x: x.get("uncached_ms") or 9999) if uncached_cands else best_cached

    # 3. Best TLD (prefer distinct provider)
    chosen_keys = {best_cached.get("key"), best_uncached.get("key")}
    tld_cands = [r for r in valid if r.get("key") not in chosen_keys]
    best_tld = min(tld_cands, key=lambda x: x.get("dotcom_ms") or 9999) if tld_cands else best_uncached

    return {
        "cached": best_cached,
        "uncached": best_uncached,
        "dotcom": best_tld
    }
