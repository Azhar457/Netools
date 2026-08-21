#!/usr/bin/env python3
"""
DNS Leak & Protocol Integrity Engine for Netools.
Implements deep security and privacy audits:
1. Transparent DNS Proxy / Port 53 Interception Detection (TEST-NET-1 probe)
2. NXDOMAIN Hijacking & ISP Sinkhole Verification (RFC 8020 / RCODE 3 validation)
3. DNSSEC Enforcement & BOGUS Signature Rejection Test (RFC 4035)
4. EDNS0 Client Subnet (ECS / RFC 7871) Privacy Leak Inspection
5. EDNS0 Padding (RFC 7830 / RFC 8467) Traffic Fingerprinting Analysis
6. Comprehensive DNS Security & Privacy Scoring (0 - 100)
"""

import ipaddress
import socket
import ssl
import struct
import time
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class DNSResponse:
    raw_bytes: bytes = b""
    tx_id: int = 0
    qr: int = 0
    opcode: int = 0
    aa: bool = False
    tc: bool = False
    rd: bool = False
    ra: bool = False
    ad: bool = False  # Authentic Data (DNSSEC validation succeeded upstream)
    cd: bool = False
    rcode: int = 0    # 0=NOERROR, 2=SERVFAIL, 3=NXDOMAIN, etc.
    qdcount: int = 0
    ancount: int = 0
    nscount: int = 0
    arcount: int = 0
    ips: List[str] = field(default_factory=list)
    ttl_list: List[int] = field(default_factory=list)
    has_rrsig: bool = False
    has_edns: bool = False
    edns_udp_size: int = 0
    edns_has_do: bool = False
    edns_options: Dict[int, bytes] = field(default_factory=dict)
    has_ecs_leak: bool = False
    ecs_family: int = 0
    ecs_source_prefix: int = 0
    ecs_scope_prefix: int = 0
    ecs_ip: Optional[str] = None
    has_padding: bool = False
    padding_len: int = 0


# ==============================================================================
# WIREFORMAT BUILDER & EXTENDED PARSER
# ==============================================================================

def build_dns_query_packet(
    domain: str,
    tx_id: int = 0x5A5A,
    qtype: int = 1,
    want_dnssec: bool = True,
    with_ecs: bool = False,
    with_padding_len: int = 0
) -> bytes:
    """Build DNS wireformat query packet with configurable EDNS0, DO bit, ECS, or Padding."""
    header = struct.pack(">HHHHHH", tx_id, 0x0100, 1, 0, 0, 1 if (want_dnssec or with_ecs or with_padding_len > 0) else 0)
    
    qname = b""
    for part in domain.strip(".").split("."):
        if not part:
            continue
        encoded = part.encode("ascii")
        qname += bytes([len(encoded)]) + encoded
    qname += b"\x00"
    qtype_qclass = struct.pack(">HH", qtype, 1)  # QTYPE, IN CLASS
    pkt = header + qname + qtype_qclass

    if want_dnssec or with_ecs or with_padding_len > 0:
        rdata = bytearray()
        
        # Option 8: EDNS Client Subnet (ECS) probe
        if with_ecs:
            # Example query prefix: family=1(IPv4), source=24, scope=0, addr=203.0.113.0
            ecs_data = struct.pack(">HBB", 1, 24, 0) + socket.inet_aton("203.0.113.0")[:3]
            rdata.extend(struct.pack(">HH", 8, len(ecs_data)) + ecs_data)

        # Option 12: EDNS Padding (RFC 7830)
        if with_padding_len > 0:
            pad = b"\x00" * with_padding_len
            rdata.extend(struct.pack(">HH", 12, len(pad)) + pad)

        do_flag = 0x8000 if want_dnssec else 0x0000
        # OPT RR: Name=0, Type=41(OPT), UDP_size=4096, ExtRcode=0, Version=0, Flags (DO bit), Rdlen
        opt_rr = b"\x00" + struct.pack(">HHBBHH", 41, 4096, 0, 0, do_flag, len(rdata)) + bytes(rdata)
        pkt += opt_rr

    return pkt


def parse_dns_response_extended(data: bytes) -> DNSResponse:
    """
    Exhaustively parse DNS wireformat response.
    Extracts RCODE, AD bit, IP addresses, TTLs, DNSSEC RRSIG, and EDNS0 options (ECS, Padding).
    """
    res = DNSResponse(raw_bytes=data)
    if len(data) < 12:
        return res

    tx_id, flags, qdcount, ancount, nscount, arcount = struct.unpack(">HHHHHH", data[:12])
    res.tx_id = tx_id
    res.qr = (flags >> 15) & 1
    res.opcode = (flags >> 11) & 0x0F
    res.aa = bool((flags >> 10) & 1)
    res.tc = bool((flags >> 9) & 1)
    res.rd = bool((flags >> 8) & 1)
    res.ra = bool((flags >> 7) & 1)
    res.ad = bool((flags >> 5) & 1)
    res.cd = bool((flags >> 4) & 1)
    res.rcode = flags & 0x0F
    res.qdcount = qdcount
    res.ancount = ancount
    res.nscount = nscount
    res.arcount = arcount

    offset = 12

    # Skip Question Section
    for _ in range(qdcount):
        if offset >= len(data):
            break
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

    def _parse_name(curr_offset: int) -> int:
        while curr_offset < len(data):
            length = data[curr_offset]
            if length == 0:
                return curr_offset + 1
            elif (length & 0xC0) == 0xC0:
                return curr_offset + 2
            else:
                curr_offset += 1 + length
        return curr_offset

    # Parse Answer Section
    for _ in range(ancount):
        if offset >= len(data):
            break
        offset = _parse_name(offset)
        if offset + 10 > len(data):
            break
        rtype, rclass, ttl, rdlength = struct.unpack(">HHIH", data[offset:offset+10])
        offset += 10
        res.ttl_list.append(ttl)
        if rtype == 1 and rdlength == 4 and offset + 4 <= len(data):  # A record
            res.ips.append(socket.inet_ntoa(data[offset:offset+4]))
        elif rtype == 28 and rdlength == 16 and offset + 16 <= len(data):  # AAAA record
            res.ips.append(socket.inet_ntop(socket.AF_INET6, data[offset:offset+16]))
        elif rtype == 46:  # RRSIG (DNSSEC)
            res.has_rrsig = True
        offset += rdlength

    # Parse Authority Section (Skip / Check for RRSIG)
    for _ in range(nscount):
        if offset >= len(data):
            break
        offset = _parse_name(offset)
        if offset + 10 > len(data):
            break
        rtype, rclass, ttl, rdlength = struct.unpack(">HHIH", data[offset:offset+10])
        offset += 10
        if rtype == 46:
            res.has_rrsig = True
        offset += rdlength

    # Parse Additional Section (EDNS0 OPT RR)
    for _ in range(arcount):
        if offset >= len(data):
            break
        offset = _parse_name(offset)
        if offset + 10 > len(data):
            break
        rtype, udp_payload_size, ext_rcode_flags, rdlength = struct.unpack(">HHIH", data[offset:offset+10])
        offset += 10
        if rtype == 41:  # OPT RR
            res.has_edns = True
            res.edns_udp_size = udp_payload_size
            res.edns_has_do = bool(ext_rcode_flags & 0x8000)

            # Parse EDNS Option RDATA
            opt_end = offset + rdlength
            opt_ptr = offset
            while opt_ptr + 4 <= opt_end and opt_ptr + 4 <= len(data):
                opt_code, opt_len = struct.unpack(">HH", data[opt_ptr:opt_ptr+4])
                opt_ptr += 4
                opt_val = data[opt_ptr:opt_ptr+opt_len]
                res.edns_options[opt_code] = opt_val
                
                if opt_code == 8 and len(opt_val) >= 4:  # ECS Option (RFC 7871)
                    res.has_ecs_leak = True
                    family, src_pfx, scp_pfx = struct.unpack(">HBB", opt_val[:4])
                    res.ecs_family = family
                    res.ecs_source_prefix = src_pfx
                    res.ecs_scope_prefix = scp_pfx
                    addr_bytes = opt_val[4:]
                    if family == 1:
                        full_addr = addr_bytes.ljust(4, b"\x00")
                        res.ecs_ip = socket.inet_ntoa(full_addr)
                    elif family == 2:
                        full_addr = addr_bytes.ljust(16, b"\x00")
                        res.ecs_ip = socket.inet_ntop(socket.AF_INET6, full_addr)
                elif opt_code == 12:  # EDNS Padding (RFC 7830)
                    res.has_padding = True
                    res.padding_len = opt_len

                opt_ptr += opt_len
        offset += rdlength

    return res


# ==============================================================================
# TRANSPORT QUERY EXECUTORS
# ==============================================================================

def execute_dns_query(
    endpoint: str,
    domain: str,
    mode: str = "ipv4",
    qtype: int = 1,
    want_dnssec: bool = True,
    with_ecs: bool = False,
    timeout: float = 2.5
) -> Tuple[Optional[float], Optional[DNSResponse]]:
    """Execute DNS query across UDP, DoH, or DoT and return latency and parsed DNSResponse."""
    mode_clean = mode.lower()
    pkt = build_dns_query_packet(domain, qtype=qtype, want_dnssec=want_dnssec, with_ecs=with_ecs)
    t0 = time.perf_counter()

    if "doh" in mode_clean or endpoint.startswith("http://") or endpoint.startswith("https://"):
        req = urllib.request.Request(
            endpoint,
            data=pkt,
            headers={
                "Content-Type": "application/dns-message",
                "Accept": "application/dns-message",
                "User-Agent": "Netools-DNS-Leak-Engine/2.0"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    raw = resp.read()
                    lat = (time.perf_counter() - t0) * 1000.0
                    return lat, parse_dns_response_extended(raw)
        except Exception:
            return None, None

    elif "dot" in mode_clean or (":" not in endpoint and not endpoint.replace(".", "").isdigit()):
        family = socket.AF_INET6 if ":" in endpoint else socket.AF_INET
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        payload = struct.pack("!H", len(pkt)) + pkt
        sock = None
        ssock = None
        try:
            sock = socket.socket(family, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            server_name = endpoint if ":" not in endpoint else None
            ssock = ctx.wrap_socket(sock, server_hostname=server_name)
            ssock.connect((endpoint, 853))
            ssock.sendall(payload)
            len_hdr = ssock.recv(2)
            if len(len_hdr) == 2:
                resp_len = struct.unpack("!H", len_hdr)[0]
                resp_data = ssock.recv(resp_len)
                lat = (time.perf_counter() - t0) * 1000.0
                return lat, parse_dns_response_extended(resp_data)
        except Exception:
            return None, None
        finally:
            if ssock:
                try: ssock.close()
                except Exception: pass
            elif sock:
                try: sock.close()
                except Exception: pass

    else:  # UDP 53
        family = socket.AF_INET6 if ":" in endpoint else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(pkt, (endpoint, 53))
            raw, _ = sock.recvfrom(4096)
            lat = (time.perf_counter() - t0) * 1000.0
            return lat, parse_dns_response_extended(raw)
        except Exception:
            return None, None
        finally:
            try: sock.close()
            except Exception: pass

    return None, None


# ==============================================================================
# AUDIT & LEAK DETECTORS
# ==============================================================================

def is_private_or_sinkhole_ip(ip_str: str) -> bool:
    """Validate if an IP belongs to private/loopback/carrier-grade NAT sinkholes."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_unspecified or str(ip).startswith("100.64.")
    except Exception:
        return False


def check_transparent_dns_proxy(test_ip: str = "192.0.2.53", timeout: float = 1.8) -> Dict[str, Any]:
    """
    Check if port 53 UDP traffic is intercepted by a Transparent DNS Proxy / Firewall.
    Sends query to RFC 5737 TEST-NET-1 IP which does not host any DNS server.
    If a reply is received, a middlebox/ISP transparently hijacks UDP 53.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    pkt = build_dns_query_packet("google.com", tx_id=0x9999)
    try:
        sock.sendto(pkt, (test_ip, 53))
        data, sender = sock.recvfrom(512)
        if len(data) >= 12:
            resp = parse_dns_response_extended(data)
            return {
                "intercepted": True,
                "status": "🔴 Transparent DNS Proxy Interception Active",
                "details": f"UDP 53 query to non-existent IP {test_ip} was answered by middlebox (Sender: {sender[0]}). ISP forces plaintext DNS redirection.",
                "ips_returned": resp.ips,
                "risk_level": "High"
            }
    except socket.timeout:
        pass
    except Exception:
        pass
    finally:
        try: sock.close()
        except Exception: pass

    return {
        "intercepted": False,
        "status": "🟢 Clean (No Transparent DNS Interception)",
        "details": "Port 53 UDP packets to non-DNS addresses are cleanly dropped without middlebox hijacking.",
        "ips_returned": [],
        "risk_level": "None"
    }


def check_nxdomain_hijack(
    resolver: str,
    mode: str = "ipv4",
    sample_count: int = 3,
    timeout: float = 2.5
) -> Dict[str, Any]:
    """
    Verify RFC 8020 / RFC 1035 NXDOMAIN compliance.
    Checks if queries to random non-existent UUID domains are hijacked into advertising/search portal IPs.
    """
    hijacked_ips = []
    clean_nxdomain_count = 0

    for _ in range(sample_count):
        fake_domain = f"probe-{uuid.uuid4().hex[:12]}.invalid-nonexistent-domain.test"
        _, resp = execute_dns_query(resolver, fake_domain, mode=mode, timeout=timeout)
        if resp is None:
            continue
        
        # RCODE 3 is NXDOMAIN
        if resp.rcode == 3 and not resp.ips:
            clean_nxdomain_count += 1
        elif resp.ips or resp.rcode == 0:
            for ip in resp.ips:
                if ip not in hijacked_ips:
                    hijacked_ips.append(ip)

    if hijacked_ips:
        return {
            "hijacked": True,
            "status": "🔴 NXDOMAIN Hijacking Detected",
            "details": f"Resolver redirected non-existent domains to {', '.join(hijacked_ips)} (ISP search portal/sinkhole).",
            "sinkhole_ips": hijacked_ips,
            "rcode_compliant": False,
            "risk_level": "High"
        }

    return {
        "hijacked": False,
        "status": "🟢 RFC 8020 NXDOMAIN Compliant",
        "details": "Resolver correctly returns RCODE 3 (NXDOMAIN) for non-existent domains without injecting sinkhole IPs.",
        "sinkhole_ips": [],
        "rcode_compliant": (clean_nxdomain_count > 0),
        "risk_level": "None"
    }


def check_dnssec_enforcement(
    resolver: str,
    mode: str = "ipv4",
    timeout: float = 2.5
) -> Dict[str, Any]:
    """
    Test DNSSEC validation and BOGUS signature rejection.
    - Tests `dnssec-failed.org` (Intentionally invalid signature): Resolver MUST return SERVFAIL (RCODE 2) and NO IPs.
    - Tests `cloudflare.com` or `internic.net` (Valid DNSSEC): Resolver should provide RRSIG or AD (Authentic Data) flag.
    """
    # 1. Test BOGUS DNSSEC domain
    bogus_domain = "dnssec-failed.org"
    _, bogus_resp = execute_dns_query(resolver, bogus_domain, mode=mode, want_dnssec=True, timeout=timeout)

    # 2. Test VALID DNSSEC domain
    valid_domain = "cloudflare.com"
    _, valid_resp = execute_dns_query(resolver, valid_domain, mode=mode, want_dnssec=True, timeout=timeout)

    bogus_rejected = False
    if bogus_resp is not None:
        # A DNSSEC-validating resolver rejects bogus records with SERVFAIL (rcode 2) or returns 0 IPs
        if bogus_resp.rcode == 2 or (len(bogus_resp.ips) == 0 and bogus_resp.rcode != 0):
            bogus_rejected = True
        elif bogus_resp.rcode == 0 and len(bogus_resp.ips) > 0:
            bogus_rejected = False  # Resolver accepted forged/invalid DNSSEC record!

    ad_flag_present = bool(valid_resp and valid_resp.ad)
    rrsig_present = bool(valid_resp and valid_resp.has_rrsig)

    if bogus_rejected:
        return {
            "dnssec_enforced": True,
            "status": "🟢 Strict DNSSEC Validation Enforced",
            "details": "Resolver actively validates cryptographic signatures and strictly rejected the BOGUS DNSSEC domain (dnssec-failed.org).",
            "ad_flag": ad_flag_present,
            "rrsig_returned": rrsig_present,
            "risk_level": "None"
        }
    else:
        return {
            "dnssec_enforced": False,
            "status": "🟡 DNSSEC Inactive / Not Enforcing",
            "details": "Resolver did not reject forged BOGUS DNSSEC signatures (resolved dnssec-failed.org successfully). Vulnerable to upstream cache poisoning.",
            "ad_flag": ad_flag_present,
            "rrsig_returned": rrsig_present,
            "risk_level": "Medium"
        }


def check_edns0_ecs_and_padding_leak(
    resolver: str,
    mode: str = "ipv4",
    timeout: float = 2.5
) -> Dict[str, Any]:
    """
    Analyze EDNS0 options for Client Subnet (ECS RFC 7871) privacy leak and Padding (RFC 7830).
    """
    _, resp = execute_dns_query(
        resolver, "google.com",
        mode=mode, want_dnssec=True, with_ecs=True, timeout=timeout
    )

    if resp is None:
        return {
            "edns_supported": False,
            "ecs_leak": False,
            "ecs_details": "Resolver timed out or did not return EDNS response.",
            "padding_active": False,
            "risk_level": "Low"
        }

    ecs_leak = resp.has_ecs_leak
    ecs_ip = resp.ecs_ip
    ecs_pfx = resp.ecs_source_prefix

    padding_active = resp.has_padding or ("doh" in mode.lower() and resp.padding_len > 0)

    if ecs_leak:
        details = f"ECS Option detected in response (Prefix: {ecs_ip}/{ecs_pfx}). Resolver may broadcast client subnet to authoritative name servers."
        risk = "Medium"
        status = "🟡 EDNS Client Subnet (ECS) Broadcast Active"
    else:
        details = "No ECS client subnet forwarded. Enhanced user IP privacy."
        risk = "None"
        status = "🟢 High Privacy (No ECS Subnet Leak)"

    return {
        "edns_supported": resp.has_edns,
        "ecs_leak": ecs_leak,
        "ecs_ip": ecs_ip,
        "ecs_prefix": ecs_pfx,
        "ecs_details": details,
        "status": status,
        "padding_active": padding_active,
        "padding_len": resp.padding_len,
        "risk_level": risk
    }


# ==============================================================================
# MASTER AUDIT & SCORING
# ==============================================================================

def run_comprehensive_dns_leak_audit(
    resolver_endpoint: str,
    mode: str = "ipv4",
    timeout: float = 2.5
) -> Dict[str, Any]:
    """
    Execute full multi-tier DNS leak, interception, and protocol integrity inspection.
    Calculates composite Security & Privacy Score (0 - 100).
    """
    t_proxy = check_transparent_dns_proxy(timeout=1.5)
    nx_check = check_nxdomain_hijack(resolver_endpoint, mode=mode, timeout=timeout)
    dnssec_check = check_dnssec_enforcement(resolver_endpoint, mode=mode, timeout=timeout)
    edns_check = check_edns0_ecs_and_padding_leak(resolver_endpoint, mode=mode, timeout=timeout)

    # Calculate Security & Privacy Score (0 - 100)
    score = 100

    if t_proxy.get("intercepted"):
        score -= 40  # Major ISP MiTM / transparent proxy interception
    if nx_check.get("hijacked"):
        score -= 25  # ISP sinkhole / redirection
    if not dnssec_check.get("dnssec_enforced"):
        score -= 15  # Missing BOGUS rejection
    if edns_check.get("ecs_leak"):
        score -= 10  # ECS IP privacy leak

    # Bonus for encrypted transports (DoH / DoT) with padding
    if ("doh" in mode.lower() or "dot" in mode.lower()) and not t_proxy.get("intercepted"):
        if edns_check.get("padding_active"):
            score = min(100, score + 5)

    score = max(0, min(100, score))

    if score >= 90:
        overall_rating = "🟢 Excellent (Secure & Private)"
    elif score >= 70:
        overall_rating = "🟡 Good (Minor Security / Privacy Warnings)"
    elif score >= 45:
        overall_rating = "🟠 Fair (DNSSEC or Hijacking Issues)"
    else:
        overall_rating = "🔴 Critical Risk (ISP Interception / Poisoned DNS)"

    return {
        "resolver": resolver_endpoint,
        "protocol": mode.upper(),
        "security_score": score,
        "overall_rating": overall_rating,
        "transparent_proxy": t_proxy,
        "nxdomain_hijack": nx_check,
        "dnssec": dnssec_check,
        "edns_privacy": edns_check,
        "timestamp": time.time()
    }
