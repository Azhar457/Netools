#!/usr/bin/env python3
"""
DNS Jumper GRC 3-Tier Benchmark Engine
Implements GRC-style Cached, Uncached, and Custom TLD Latency Measurement for DoH & UDP DNS.
"""

import time
import socket
import struct
import uuid
import asyncio
from typing import Dict, List, Optional, Tuple, Any

try:
    import httpx
except ImportError:
    httpx = None

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


class GRCBenchmarkResult:
    def __init__(self, key: str, provider: Dict[str, Any]):
        self.key = key
        self.name = provider["name"]
        self.country = provider["country"]
        self.region = provider.get("region", "global")
        self.category = provider.get("category", "general")
        self.doh_url = provider.get("doh_url", "")
        self.ipv4 = provider.get("ipv4", [])

        # 3-Tier Latency Stats (in milliseconds)
        self.cached_ms: float = 0.0
        self.uncached_ms: float = 0.0
        self.tld_ms: float = 0.0
        self.grc_score: float = 9999.0

        # Detailed test results
        self.cached_lats: List[float] = []
        self.uncached_lats: List[float] = []
        self.tld_lats: List[float] = []
        self.status: str = "Pending"
        self.reliability_pct: float = 0.0

    def compute_grc_stats(self, total_expected: int):
        total_succ = len(self.cached_lats) + len(self.uncached_lats) + len(self.tld_lats)
        self.reliability_pct = (total_succ / max(1, total_expected)) * 100.0

        penalty_ms = 4000.0

        # 1. Cached Average
        if self.cached_lats:
            self.cached_ms = sum(self.cached_lats) / len(self.cached_lats)
        else:
            self.cached_ms = penalty_ms

        # 2. Uncached Average
        if self.uncached_lats:
            self.uncached_ms = sum(self.uncached_lats) / len(self.uncached_lats)
        else:
            self.uncached_ms = penalty_ms

        # 3. TLD Average
        if self.tld_lats:
            self.tld_ms = sum(self.tld_lats) / len(self.tld_lats)
        else:
            self.tld_ms = penalty_ms

        # GRC Combined Weighted Score (45% Cached, 35% Uncached, 20% TLD)
        self.grc_score = (0.45 * self.cached_ms) + (0.35 * self.uncached_ms) + (0.20 * self.tld_ms)

        if self.reliability_pct >= 95.0:
            self.status = "Stable"
        elif self.reliability_pct >= 50.0:
            self.status = f"Partial ({total_succ}/{total_expected})"
        else:
            self.status = "Failed"


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
        sock.close()
    return None


async def benchmark_provider_grc_doh(
    client: httpx.AsyncClient,
    key: str,
    provider: Dict[str, Any],
    tld_domains: List[str],
    timeout_sec: float = 3.0
) -> GRCBenchmarkResult:
    """Execute 3-Tier GRC Benchmark over DoH (HTTPS RFC 8484)."""
    result = GRCBenchmarkResult(key, provider)
    doh_url = provider.get("doh_url")
    if not doh_url:
        result.compute_grc_stats(1)
        return result

    # --- TIER 1: CACHED BENCHMARK ---
    cached_targets = ["google.com", "youtube.com", "facebook.com"]
    # Prime/warmup cache
    for dom in cached_targets:
        try:
            pkt = build_dns_packet(dom, 0x1111)
            await client.post(doh_url, content=pkt, timeout=timeout_sec)
        except Exception:
            pass

    # Measure Cached Response Time
    for dom in cached_targets:
        pkt = build_dns_packet(dom, 0x2222)
        t0 = time.perf_counter()
        try:
            res = await client.post(doh_url, content=pkt, timeout=timeout_sec)
            if res.status_code == 200 and len(res.content) >= 12:
                result.cached_lats.append((time.perf_counter() - t0) * 1000.0)
        except Exception:
            pass

    # --- TIER 2: UNCACHED BENCHMARK (Synthetic Random Subdomains) ---
    for _ in range(3):
        rand_dom = f"bench-{uuid.uuid4().hex[:8]}.example.org"
        pkt = build_dns_packet(rand_dom, 0x3333)
        t0 = time.perf_counter()
        try:
            res = await client.post(doh_url, content=pkt, timeout=timeout_sec)
            if res.status_code == 200 and len(res.content) >= 12:
                result.uncached_lats.append((time.perf_counter() - t0) * 1000.0)
        except Exception:
            pass

    # --- TIER 3: TLD SPECIFIC BENCHMARK (.id, .my.id, .com, etc.) ---
    for dom in tld_domains[:5]:
        pkt = build_dns_packet(dom, 0x4444)
        t0 = time.perf_counter()
        try:
            res = await client.post(doh_url, content=pkt, timeout=timeout_sec)
            if res.status_code == 200 and len(res.content) >= 12:
                result.tld_lats.append((time.perf_counter() - t0) * 1000.0)
        except Exception:
            pass

    total_expected = len(cached_targets) + 3 + min(5, len(tld_domains))
    result.compute_grc_stats(total_expected)
    return result


def benchmark_provider_grc_udp(
    key: str,
    provider: Dict[str, Any],
    tld_domains: List[str],
    timeout_sec: float = 2.0
) -> GRCBenchmarkResult:
    """Execute 3-Tier GRC Benchmark over Raw UDP port 53 (GRC Benchmark style)."""
    result = GRCBenchmarkResult(key, provider)
    ips = provider.get("ipv4", [])
    if not ips:
        result.compute_grc_stats(1)
        return result
    primary_ip = ips[0]

    # --- TIER 1: CACHED ---
    cached_targets = ["google.com", "youtube.com", "facebook.com"]
    for dom in cached_targets:
        query_udp_dns(primary_ip, dom, timeout=1.5)  # Prime
    for dom in cached_targets:
        lat = query_udp_dns(primary_ip, dom, timeout=timeout_sec)
        if lat is not None:
            result.cached_lats.append(lat)

    # --- TIER 2: UNCACHED ---
    for _ in range(3):
        rand_dom = f"bench-{uuid.uuid4().hex[:8]}.example.org"
        lat = query_udp_dns(primary_ip, rand_dom, timeout=timeout_sec)
        if lat is not None:
            result.uncached_lats.append(lat)

    # --- TIER 3: TLD BENCHMARK ---
    for dom in tld_domains[:5]:
        lat = query_udp_dns(primary_ip, dom, timeout=timeout_sec)
        if lat is not None:
            result.tld_lats.append(lat)

    total_expected = len(cached_targets) + 3 + min(5, len(tld_domains))
    result.compute_grc_stats(total_expected)
    return result
