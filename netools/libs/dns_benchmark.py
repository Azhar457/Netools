#!/usr/bin/env python3
"""
GRC 3-Tier DNS Benchmark Engine v2.0 (Gibson Research Corporation Standard)
Implements true 3-Tier Latency Measurement & Verification:
- Tier 1: 🟢 Cached (RTT / Proximity - 45% weight, warm-up + 3x samples + outlier rejection)
- Tier 2: 🔵 Uncached (Recursive Capacity / Cold Miss - 35% weight, random UUID forced miss)
- Tier 3: 🟡 TLD / Regional (Peering & Geo Affinity - 20% weight, regional TLDs)

Verification Layer:
- Hijack Detection (Anti-ISP Sinkhole / Private IP Redirection Check)
- EDNS0 & DNSSEC Support Validation (RFC 6891 OPT RR + DO bit)
- Coefficient of Variation (CV = σ / μ) Stability Index & Reliability %
- Turbo Mode / Max Latency Cutoff (< 200ms) for 5x Faster Benchmark
- Enhanced Smart Mix with Strict 3-Resolver Deduplication
- Zero External Dependencies (Standard Python Socket, SSL, struct & urllib)
"""

import ipaddress
import socket
import ssl
import statistics
import struct
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class TierResult:
    samples: List[float] = field(default_factory=list)
    clean_samples: List[float] = field(default_factory=list)
    median_ms: Optional[float] = None
    mean_ms: Optional[float] = None
    std_dev: float = 0.0
    cv: float = 0.0  # Coefficient of Variation (Stability Index)
    success_count: int = 0
    fail_count: int = 0

    def compute(self):
        if not self.samples:
            return
        
        # Outlier Rejection (> 2.5x median or > median + 120ms)
        raw_median = statistics.median(self.samples)
        if len(self.samples) >= 3:
            self.clean_samples = [
                s for s in self.samples 
                if s <= max(raw_median * 2.5, raw_median + 120.0)
            ]
            if not self.clean_samples:
                self.clean_samples = self.samples
        else:
            self.clean_samples = list(self.samples)

        self.median_ms = statistics.median(self.clean_samples)
        self.mean_ms = statistics.mean(self.clean_samples)
        if len(self.clean_samples) > 1 and self.mean_ms and self.mean_ms > 0:
            self.std_dev = statistics.stdev(self.clean_samples)
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
    hijack_detected: bool = False
    dnssec_supported: bool = False
    edns_supported: bool = False


# ==============================================================================
# LOW-LEVEL DNS WIREFORMAT PROTOCOL PROBES & PARSERS
# ==============================================================================

def build_dns_packet(domain: str, tx_id: int = 0x1234, qtype: int = 1, want_dnssec: bool = True) -> bytes:
    """Build standard DNS wireformat query packet with EDNS0 and DO (DNSSEC OK) bit."""
    arcount = 1 if want_dnssec else 0
    header = struct.pack(">HHHHHH", tx_id, 0x0100, 1, 0, 0, arcount)
    qname = b""
    for part in domain.strip(".").split("."):
        encoded = part.encode("ascii")
        qname += bytes([len(encoded)]) + encoded
    qname += b"\x00"
    qtype_qclass = struct.pack(">HH", qtype, 1)
    pkt = header + qname + qtype_qclass
    if want_dnssec:
        # OPT RR: Name=0, Type=41(OPT), UDP_size=4096, ExtRcode=0, Version=0, Flags=0x8000 (DO bit), Rdlen=0
        opt_rr = b"\x00" + struct.pack(">HHBBHH", 41, 4096, 0, 0, 0x8000, 0)
        pkt += opt_rr
    return pkt


def parse_dns_response(data: bytes) -> Tuple[List[str], bool, bool]:
    """
    Parse DNS response packet wireformat.
    Returns: (list_of_ips, has_rrsig_dnssec, has_edns)
    """
    if len(data) < 12:
        return [], False, False
    tx_id, flags, qdcount, ancount, nscount, arcount = struct.unpack(">HHHHHH", data[:12])
    
    offset = 12
    # Skip Question Section
    for _ in range(qdcount):
        while offset < len(data):
            length = data[offset]
            if length == 0:
                offset += 1
                break
            elif (length & 0xC0) == 0xC0:
                offset += 2
                break
            else:
                offset += 1 + length
        offset += 4  # qtype + qclass

    ips = []
    has_rrsig = False
    has_edns = (arcount > 0)

    # Parse Answer Section
    for _ in range(ancount):
        if offset >= len(data):
            break
        # Read name
        if (data[offset] & 0xC0) == 0xC0:
            offset += 2
        else:
            while offset < len(data):
                length = data[offset]
                if length == 0:
                    offset += 1
                    break
                elif (length & 0xC0) == 0xC0:
                    offset += 2
                    break
                else:
                    offset += 1 + length
        if offset + 10 > len(data):
            break
        rtype, rclass, ttl, rdlength = struct.unpack(">HHIH", data[offset:offset+10])
        offset += 10
        if rtype == 1 and rdlength == 4 and offset + 4 <= len(data):
            ips.append(socket.inet_ntoa(data[offset:offset+4]))
        elif rtype == 46:
            has_rrsig = True
        offset += rdlength

    return ips, has_rrsig, has_edns


def is_sinkhole_or_private_ip(ip_str: str) -> bool:
    """Check if resolved IP is private/loopback/bogon (indicating ISP hijack / block page)."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_unspecified or str(ip).startswith("100.64.")
    except Exception:
        return False


def query_udp_dns(ip: str, domain: str, timeout: float = 2.0) -> Tuple[Optional[float], List[str], bool, bool]:
    """Execute raw UDP port 53 DNS query (IPv4 / IPv6)."""
    packet = build_dns_packet(domain, want_dnssec=True)
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    t0 = time.perf_counter()
    try:
        sock.sendto(packet, (ip, 53))
        data, _ = sock.recvfrom(4096)
        lat = (time.perf_counter() - t0) * 1000.0
        ips, rrsig, edns = parse_dns_response(data)
        return lat, ips, rrsig, edns
    except Exception:
        return None, [], False, False
    finally:
        try:
            sock.close()
        except Exception:
            pass


_doh_ssl_ctx = ssl._create_unverified_context()

def query_doh_dns(doh_url: str, domain: str, timeout: float = 2.5) -> Tuple[Optional[float], List[str], bool, bool]:
    """Execute DNS-over-HTTPS (RFC 8484 wireformat) query using standard urllib."""
    pkt = build_dns_packet(domain, want_dnssec=True)
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
        with urllib.request.urlopen(req, timeout=timeout, context=_doh_ssl_ctx) as resp:
            if resp.status == 200:
                data = resp.read()

                lat = (time.perf_counter() - t0) * 1000.0
                ips, rrsig, edns = parse_dns_response(data)
                return lat, ips, rrsig, edns
    except Exception:
        pass
    return None, [], False, False


def query_dot_dns(host_or_ip: str, domain: str, timeout: float = 2.5) -> Tuple[Optional[float], List[str], bool, bool]:
    """Execute DNS-over-TLS (RFC 7858 on port 853) query using standard ssl."""
    pkt = build_dns_packet(domain, want_dnssec=True)
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
            lat = (time.perf_counter() - t0) * 1000.0
            ips, rrsig, edns = parse_dns_response(resp_data)
            return lat, ips, rrsig, edns
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
    return None, [], False, False


# ==============================================================================
# GRC 3-TIER BENCHMARK ENGINE
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
    timeout: float = 2.5,
    turbo_mode: bool = False,
    max_latency_threshold: float = 200.0
) -> Dict[str, Any]:
    """
    Execute 3-Tier GRC Benchmark (Cached, Uncached, Regional TLD) for a single provider.
    
    If turbo_mode is True:
    - Sets timeout to 1.0s
    - If initial cached query > max_latency_threshold (e.g. 200ms) or timeouts, immediately aborts
      further queries for that resolver to speed up overall scanning by up to 5x.
    """
    try:
        from netools.libs.dns_db import TLD_PRESETS
    except ImportError:
        TLD_PRESETS = {}

    effective_timeout = min(timeout, 1.0) if turbo_mode else timeout

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
            return {"key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"), "region": provider.get("region", "global"), "score": 9999.0, "cached_ms": None, "uncached_ms": None, "dotcom_ms": None, "protocol": "IPv6", "ipv4": ipv4_list, "ipv6": ipv6_list, "doh_url": doh_url, "status": "Failed", "reliability_pct": 0.0, "hijack_detected": False, "dnssec_supported": False, "edns_supported": False}
        target_endpoint = ipv6_list[0]
        protocol_label = "IPv6"
    elif is_doh:
        if not doh_url:
            return {"key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"), "region": provider.get("region", "global"), "score": 9999.0, "cached_ms": None, "uncached_ms": None, "dotcom_ms": None, "protocol": "DoH", "ipv4": ipv4_list, "ipv6": ipv6_list, "doh_url": doh_url, "status": "Failed", "reliability_pct": 0.0, "hijack_detected": False, "dnssec_supported": False, "edns_supported": False}
        target_endpoint = doh_url
        protocol_label = "DoH"
    elif is_dot:
        if not dot_host:
            return {"key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"), "region": provider.get("region", "global"), "score": 9999.0, "cached_ms": None, "uncached_ms": None, "dotcom_ms": None, "protocol": "DoT", "ipv4": ipv4_list, "ipv6": ipv6_list, "doh_url": doh_url, "status": "Failed", "reliability_pct": 0.0, "hijack_detected": False, "dnssec_supported": False, "edns_supported": False}
        target_endpoint = dot_host
        protocol_label = "DoT"
    else:  # ipv4
        if not ipv4_list:
            return {"key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"), "region": provider.get("region", "global"), "score": 9999.0, "cached_ms": None, "uncached_ms": None, "dotcom_ms": None, "protocol": "IPv4", "ipv4": ipv4_list, "ipv6": ipv6_list, "doh_url": doh_url, "status": "Failed", "reliability_pct": 0.0, "hijack_detected": False, "dnssec_supported": False, "edns_supported": False}
        target_endpoint = ipv4_list[0]
        protocol_label = "IPv4"

    def _measure(dom: str) -> Tuple[Optional[float], List[str], bool, bool]:
        if is_doh:
            return query_doh_dns(target_endpoint, dom, timeout=effective_timeout)
        elif is_dot:
            return query_dot_dns(target_endpoint, dom, timeout=effective_timeout)
        else:
            return query_udp_dns(target_endpoint, dom, timeout=effective_timeout)

    tier_cached = TierResult()
    tier_uncached = TierResult()
    tier_tld = TierResult()

    hijack_detected = False
    dnssec_supported = False
    edns_supported = False

    # 1. Warm-up prime cache (discard first measurement)
    warm_lat, warm_ips, warm_dnssec, warm_edns = _measure(cached_targets[0])
    if warm_dnssec:
        dnssec_supported = True
    if warm_edns:
        edns_supported = True
    if warm_ips and any(is_sinkhole_or_private_ip(ip) for ip in warm_ips):
        hijack_detected = True

    # Turbo Cutoff Check: If warm-up failed or > max_latency_threshold in turbo mode, abort early!
    if turbo_mode:
        if warm_lat is None:
            return {
                "key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"),
                "region": provider.get("region", "global"), "doh_url": doh_url, "ipv4": ipv4_list, "ipv6": ipv6_list,
                "cached_ms": None, "uncached_ms": None, "dotcom_ms": None, "score": 9999.0,
                "protocol": protocol_label, "target_endpoint": target_endpoint, "reliability_pct": 0.0,
                "status": "Timeout", "hijack_detected": False, "dnssec_supported": False, "edns_supported": False
            }
        elif warm_lat > max_latency_threshold:
            return {
                "key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"),
                "region": provider.get("region", "global"), "doh_url": doh_url, "ipv4": ipv4_list, "ipv6": ipv6_list,
                "cached_ms": warm_lat, "uncached_ms": None, "dotcom_ms": None, "score": 9999.0,
                "protocol": protocol_label, "target_endpoint": target_endpoint, "reliability_pct": 10.0,
                "status": "Slow / Cutoff (>200ms)", "hijack_detected": False, "dnssec_supported": False, "edns_supported": False
            }

    # 2. Tier 1: Cached Latency (3 samples)
    for dom in cached_targets:
        lat, ips, rrsig, edns = _measure(dom)
        if lat is not None:
            tier_cached.samples.append(lat)
            tier_cached.success_count += 1
            if rrsig:
                dnssec_supported = True
            if edns:
                edns_supported = True
            if ips and any(is_sinkhole_or_private_ip(ip) for ip in ips):
                hijack_detected = True
        else:
            tier_cached.fail_count += 1

    tier_cached.compute()

    # Second Turbo Cutoff Check: after Tier 1 median
    if turbo_mode and tier_cached.median_ms and tier_cached.median_ms > max_latency_threshold:
        return {
            "key": key, "name": provider.get("name", key), "country": provider.get("country", "🌐"),
            "region": provider.get("region", "global"), "doh_url": doh_url, "ipv4": ipv4_list, "ipv6": ipv6_list,
            "cached_ms": tier_cached.median_ms, "uncached_ms": None, "dotcom_ms": None, "score": 9999.0,
            "protocol": protocol_label, "target_endpoint": target_endpoint, "reliability_pct": 33.0,
            "status": "Slow / Cutoff (>200ms)", "hijack_detected": hijack_detected,
            "dnssec_supported": dnssec_supported, "edns_supported": edns_supported
        }

    # 3. Tier 2: Uncached Latency (Forced Miss with Random UUID Subdomains)
    for dom in uncached_targets:
        lat, ips, _, _ = _measure(dom)
        if lat is not None:
            tier_uncached.samples.append(lat)
            tier_uncached.success_count += 1
        else:
            tier_uncached.fail_count += 1

    tier_uncached.compute()

    # 4. Tier 3: TLD / Regional Latency (Regional Domains)
    for dom in dotcom_targets:
        lat, ips, _, _ = _measure(dom)
        if lat is not None:
            tier_tld.samples.append(lat)
            tier_tld.success_count += 1
            if ips and any(is_sinkhole_or_private_ip(ip) for ip in ips):
                hijack_detected = True
        else:
            tier_tld.fail_count += 1

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

    if hijack_detected:
        stat = "Hijacked"
    elif rel_pct >= 90.0 and tier_cached.success_count > 0:
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
        "hijack_detected": hijack_detected,
        "dnssec_supported": dnssec_supported,
        "edns_supported": edns_supported
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
    valid = [r for r in results_map.values() if r.get("score", 9999) < 9000 and not r.get("hijack_detected")]
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
