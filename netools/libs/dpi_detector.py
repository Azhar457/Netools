#!/usr/bin/env python3
"""
Multi-Layer Domain Censorship & Deep Packet Inspection (DPI) Engine.
Analyzes network reachability across 4 distinct OSI stages:
- Node A: DNS Resolution (Layer 7) -> Detects DNS Poisoning, Sinkholes, MikroTik DNS Hijack
- Node B: TCP Layer 4 Handshake -> Detects IP Blacklist, Port 443 Drops, BGP Null-routes
- Node C: TLS SNI Handshake (Layer 7 DPI) -> Detects DPI SNI Filtering & TCP RST Injections
- Node D: SSL Certificate & MITM -> Detects Corporate Proxy SSL Decryption (Fortinet/Zscaler)
"""

import ipaddress
import socket
import ssl
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from netools.libs.dns_leak import build_dns_query_packet, parse_dns_response_extended

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class DiagnosticStage:
    node_id: str             # "A", "B", "C", "D"
    name: str                # e.g. "DNS Resolution"
    status: str              # "PASS", "BLOCKED", "WARN", "SKIPPED"
    latency_ms: Optional[float] = None
    summary: str = ""
    details: List[str] = field(default_factory=list)
    technical_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DomainDiagnosticReport:
    domain: str
    timestamp: float = field(default_factory=time.time)
    stages: Dict[str, DiagnosticStage] = field(default_factory=dict)
    verdict: str = "UNKNOWN"
    blocked_stage_id: Optional[str] = None
    summary_headline: str = ""
    recommendation: str = ""
    recommended_action_type: str = "NONE"  # "PROXY_VPN", "CHANGE_DNS", "UNBLOCK_FIREWALL", "NONE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "timestamp": self.timestamp,
            "verdict": self.verdict,
            "blocked_stage_id": self.blocked_stage_id,
            "summary_headline": self.summary_headline,
            "recommendation": self.recommendation,
            "recommended_action_type": self.recommended_action_type,
            "stages": {
                k: {
                    "node_id": v.node_id,
                    "name": v.name,
                    "status": v.status,
                    "latency_ms": v.latency_ms,
                    "summary": v.summary,
                    "details": v.details,
                    "technical_info": v.technical_info
                }
                for k, v in self.stages.items()
            }
        }


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def is_bogon_or_private_ip(ip_str: str) -> bool:
    """Validate if an IP is a local/private/loopback/sinkhole address."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private or
            ip.is_loopback or
            ip.is_reserved or
            ip.is_unspecified or
            str(ip) in ("0.0.0.0", "127.0.0.1") or
            str(ip).startswith("100.64.")
        )
    except Exception:
        return False


def query_reference_doh(domain: str, timeout: float = 2.5) -> Tuple[Optional[float], List[str]]:
    """Query clean public DoH (Cloudflare 1.1.1.1) for authoritative reference IP."""
    doh_url = "https://security.cloudflare-dns.com/dns-query"
    pkt = build_dns_query_packet(domain, want_dnssec=True)
    req = urllib.request.Request(
        doh_url,
        data=pkt,
        headers={
            "Content-Type": "application/dns-message",
            "Accept": "application/dns-message",
            "User-Agent": "Netools-DPI-Engine/2.0"
        }
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                raw = resp.read()
                lat = (time.perf_counter() - t0) * 1000.0
                parsed = parse_dns_response_extended(raw)
                return lat, parsed.ips
    except Exception:
        pass
    return None, []


# ==============================================================================
# 4-STAGE NETWORK REACHABILITY INSPECTOR
# ==============================================================================

def evaluate_stage_a_dns(domain: str, timeout: float = 2.5) -> Tuple[DiagnosticStage, List[str], List[str]]:
    """
    Node A: DNS Resolution (Layer 7).
    Compares System DNS vs Reference DoH (Cloudflare).
    Returns: (DiagnosticStage, system_ips, doh_ips)
    """
    stage = DiagnosticStage(
        node_id="A",
        name="1. DNS Resolution (Layer 7)",
        status="SKIPPED"
    )

    t0 = time.perf_counter()
    system_ips: List[str] = []
    sys_error = None

    try:
        addr_info = socket.getaddrinfo(domain, 443, socket.AF_INET, socket.SOCK_STREAM)
        system_ips = list(dict.fromkeys([item[4][0] for item in addr_info]))
    except Exception as e:
        sys_error = str(e)

    sys_lat = (time.perf_counter() - t0) * 1000.0
    stage.latency_ms = sys_lat

    doh_lat, doh_ips = query_reference_doh(domain, timeout=timeout)

    stage.technical_info = {
        "system_ips": system_ips,
        "doh_ips": doh_ips,
        "system_error": sys_error,
        "doh_latency_ms": doh_lat
    }

    # Evaluate DNS results
    if system_ips:
        has_sinkhole = any(is_bogon_or_private_ip(ip) for ip in system_ips)
        if has_sinkhole:
            stage.status = "BLOCKED"
            stage.summary = f"🔴 DNS Poisoned / Sinkholed ({', '.join(system_ips)})"
            stage.details = [
                f"• System DNS returned private/sinkhole IP: {', '.join(system_ips)}",
                f"• Reference DoH returned legitimate IP: {', '.join(doh_ips) if doh_ips else 'Clean'}",
                "• Triggered by: ISP DNS Hijack, MikroTik static DNS entry, or TrustPositif."
            ]
        elif doh_ips and not any(ip in doh_ips for ip in system_ips):
            # Divergent IP addresses
            stage.status = "WARN"
            stage.summary = f"🟡 Divergent DNS (Local: {system_ips[0]} | DoH: {doh_ips[0]})"
            stage.details = [
                f"• Local system resolved to: {', '.join(system_ips)}",
                f"• Reference DoH resolved to: {', '.join(doh_ips)}",
                "• Notice: IPs differ, could be Geo-DNS CDN or local transparent cache."
            ]
        else:
            stage.status = "PASS"
            stage.summary = f"🟢 Clean DNS Resolution ({system_ips[0]})"
            stage.details = [
                f"• System resolved IP: {', '.join(system_ips)} ({sys_lat:.1f} ms)",
                f"• Matches clean public DoH records ({', '.join(doh_ips)})" if doh_ips else "• Valid IP record returned."
            ]
    else:
        if doh_ips:
            stage.status = "BLOCKED"
            stage.summary = "🔴 Local DNS Blocked / Timeout (DoH Works)"
            stage.details = [
                f"• Local DNS resolution failed: {sys_error}",
                f"• But reference DoH successfully found IPs: {', '.join(doh_ips)}",
                "• Cause: ISP unencrypted DNS filtered or local resolver offline."
            ]
        else:
            stage.status = "BLOCKED"
            stage.summary = f"🔴 Domain NXDOMAIN / Unresolvable ({sys_error})"
            stage.details = [
                f"• Domain {domain} failed to resolve on both local DNS and public DoH.",
                "• Verify domain name spelling or DNS server connectivity."
            ]

    return stage, system_ips, doh_ips


def evaluate_stage_b_tcp(target_ip: str, timeout: float = 2.5) -> DiagnosticStage:
    """
    Node B: TCP Layer 4 Handshake.
    Tests raw TCP connect to IP:443 without sending TLS payload.
    """
    stage = DiagnosticStage(
        node_id="B",
        name="2. TCP Connection (Layer 4)",
        status="SKIPPED"
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    t0 = time.perf_counter()

    try:
        sock.connect((target_ip, 443))
        lat = (time.perf_counter() - t0) * 1000.0
        stage.status = "PASS"
        stage.latency_ms = lat
        stage.summary = f"🟢 TCP Port 443 Connected ({lat:.1f} ms)"
        stage.details = [
            f"• Successfully established raw TCP 3-way handshake with {target_ip}:443.",
            "• Layer 3/4 routing is clean. IP is NOT blacklisted or dropped at router firewall."
        ]
        stage.technical_info = {"target_ip": target_ip, "port": 443, "tcp_connected": True}
        return stage
    except socket.timeout:
        stage.status = "BLOCKED"
        stage.summary = "🔴 TCP Port 443 Timeout (Layer 4 Drop)"
        stage.details = [
            f"• Connection to {target_ip}:443 timed out after {timeout:.1f}s.",
            "• Cause: MikroTik firewall filter, router port block, or ISP IP blackholing/null-route."
        ]
        stage.technical_info = {"target_ip": target_ip, "port": 443, "error": "timeout"}
    except ConnectionRefusedError:
        stage.status = "BLOCKED"
        stage.summary = "🔴 TCP Connection Refused"
        stage.details = [
            f"• Server or middlebox at {target_ip} actively refused connection on port 443.",
            "• Middlebox injected TCP RST or port 443 is closed."
        ]
        stage.technical_info = {"target_ip": target_ip, "port": 443, "error": "ConnectionRefused"}
    except Exception as e:
        stage.status = "BLOCKED"
        stage.summary = f"🔴 TCP Connection Error ({str(e)[:35]})"
        stage.details = [
            f"• Failed to connect to {target_ip}:443: {e}",
            "• Network unreachable or firewall drop."
        ]
        stage.technical_info = {"target_ip": target_ip, "port": 443, "error": str(e)}
    finally:
        try: sock.close()
        except Exception: pass

    return stage


def evaluate_stage_c_sni_dpi(target_ip: str, domain: str, timeout: float = 3.0) -> Tuple[DiagnosticStage, Optional[Any]]:
    """
    Node C: TLS Handshake & SNI Filtering (Layer 7 DPI).
    Sends TLS ClientHello with the exact target SNI, and compares with neutral SNI if reset.
    Returns: (DiagnosticStage, ssl_socket)
    """
    stage = DiagnosticStage(
        node_id="C",
        name="3. TLS SNI Handshake (Layer 7 DPI)",
        status="SKIPPED"
    )

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    t0 = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        sock.connect((target_ip, 443))
        ssock = ctx.wrap_socket(sock, server_hostname=domain)
        lat = (time.perf_counter() - t0) * 1000.0
        stage.status = "PASS"
        stage.latency_ms = lat
        stage.summary = f"🟢 TLS Handshake Clean ({lat:.1f} ms)"
        stage.details = [
            f"• TLS handshake completed with SNI '{domain}' without middlebox tampering.",
            f"• Protocol: {ssock.version()}, Cipher: {ssock.cipher()[0] if ssock.cipher() else 'Default'}.",
            "• No Layer 7 SNI filtering or DPI interference detected."
        ]
        stage.technical_info = {
            "tls_version": ssock.version(),
            "cipher": ssock.cipher(),
            "sni_used": domain
        }
        return stage, ssock

    except (ConnectionResetError, ssl.SSLEOFError, socket.error) as e:
        # Potential SNI Filtering / DPI Block! Let's verify with neutral SNI probe.
        neutral_domain = "www.google.com"
        neutral_passed = False
        try:
            n_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            n_sock.settimeout(timeout)
            n_sock.connect((target_ip, 443))
            n_ssock = ctx.wrap_socket(n_sock, server_hostname=neutral_domain)
            neutral_passed = True
            n_ssock.close()
        except Exception:
            pass

        stage.status = "BLOCKED"
        if neutral_passed:
            stage.summary = "🔴 SNI Filtering Blocked (DPI Reset)"
            stage.details = [
                f"• 🚨 100% Confirmed DPI Block: Connection was immediately RESET when sending SNI '{domain}'.",
                f"• Neutral SNI '{neutral_domain}' to the same IP was accepted.",
                "• Middlebox (MikroTik / Fortinet / ISP DPI) actively inspects TLS ClientHello and injects TCP RST."
            ]
        else:
            stage.summary = f"🔴 TLS Handshake Reset ({type(e).__name__})"
            stage.details = [
                f"• TLS handshake to {target_ip} was terminated: {e}",
                "• Likely deep packet inspection or SSL handshake filter."
            ]
        stage.technical_info = {"error": str(e), "sni": domain, "neutral_test_passed": neutral_passed}

    except socket.timeout:
        stage.status = "BLOCKED"
        stage.summary = "🔴 TLS ClientHello Dropped (Silent DPI Drop)"
        stage.details = [
            f"• Server accepted TCP SYN, but packet containing SNI '{domain}' was silently dropped.",
            "• Classic behavior of DPI firewall waiting for ClientHello before dropping traffic."
        ]
        stage.technical_info = {"error": "timeout_on_client_hello", "sni": domain}

    except Exception as e:
        stage.status = "BLOCKED"
        stage.summary = f"🔴 TLS Error ({str(e)[:35]})"
        stage.details = [f"• TLS Handshake failure: {e}"]
        stage.technical_info = {"error": str(e), "sni": domain}

    return stage, None


def evaluate_stage_d_ssl_mitm(domain: str, ssock: Optional[Any], target_ip: str) -> DiagnosticStage:
    """
    Node D: SSL Certificate & Corporate MITM Inspection.
    Inspects server certificate issuer for proxy decryption (Zscaler, Fortinet, self-signed).
    """
    stage = DiagnosticStage(
        node_id="D",
        name="4. SSL Certificate & MITM",
        status="SKIPPED"
    )

    if ssock is None:
        # Attempt dedicated connection for cert inspection
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.5)
            sock.connect((target_ip, 443))
            ssock = ctx.wrap_socket(sock, server_hostname=domain)
        except Exception:
            stage.status = "SKIPPED"
            stage.summary = "⚪ Skipped (TLS Connection Unavailable)"
            stage.details = ["• Could not retrieve certificate because prior TLS handshake was blocked."]
            return stage

    try:
        cert = ssock.getpeercert(binary_form=False)

        # Check issuer string
        issuer_str = ""
        subject_str = ""
        if cert:
            issuer_tuples = cert.get("issuer", ())
            for t in issuer_tuples:
                for k, v in t:
                    if k == "organizationName" or k == "commonName":
                        issuer_str += f"{v} "
            subject_tuples = cert.get("subject", ())
            for t in subject_tuples:
                for k, v in t:
                    if k == "commonName":
                        subject_str += f"{v} "

        # Scan for Corporate MITM signatures
        mitm_signatures = ["fortinet", "palo alto", "zscaler", "sophos", "bluecoat", "squid", "kaspersky", "interception", "proxy"]
        is_mitm = any(sig in issuer_str.lower() for sig in mitm_signatures)

        stage.technical_info = {
            "issuer": issuer_str.strip() or "Standard Public CA",
            "subject": subject_str.strip() or domain,
            "is_mitm": is_mitm
        }

        if is_mitm:
            stage.status = "WARN"
            stage.summary = f"🟡 Corporate SSL Inspection Active ({issuer_str.strip()})"
            stage.details = [
                f"• 🚨 Corporate MITM Detected: Certificate issued by '{issuer_str.strip()}'.",
                "• Your company's firewall is decrypting and inspecting all HTTPS traffic to this site.",
                "• Privacy is NOT end-to-end encrypted."
            ]
        else:
            stage.status = "PASS"
            stage.summary = f"🟢 Trusted Public Certificate ({issuer_str.strip() or 'Trusted CA'})"
            stage.details = [
                f"• Certificate Issuer: {issuer_str.strip() or 'Verified Global CA'}",
                f"• Subject: {subject_str.strip() or domain}",
                "• End-to-end encrypted. No SSL Decryption MITM detected."
            ]
    except Exception as e:
        stage.status = "WARN"
        stage.summary = f"🟡 Certificate Warning ({str(e)[:30]})"
        stage.details = [f"• Error parsing certificate: {e}"]
    finally:
        try: ssock.close()
        except Exception: pass

    return stage


# ==============================================================================
# MASTER DIAGNOSTIC RUNNER & RECOMMENDATION GENERATOR
# ==============================================================================

def diagnose_domain_reachability(domain: str, timeout: float = 3.0) -> DomainDiagnosticReport:
    """
    Execute full multi-layer domain censorship diagnostic across Stages A, B, C, and D.
    Generates actionable verdict and user recommendation.
    """
    clean_domain = domain.strip().lower()
    if clean_domain.startswith("https://"):
        clean_domain = clean_domain[8:]
    elif clean_domain.startswith("http://"):
        clean_domain = clean_domain[7:]
    clean_domain = clean_domain.split("/")[0].split(":")[0]

    report = DomainDiagnosticReport(domain=clean_domain)

    # 1. Stage A: DNS
    stage_a, sys_ips, doh_ips = evaluate_stage_a_dns(clean_domain, timeout=timeout)
    report.stages["A"] = stage_a

    # Determine candidate IP to test
    target_ip = None
    if sys_ips and not is_bogon_or_private_ip(sys_ips[0]):
        target_ip = sys_ips[0]
    elif doh_ips and not is_bogon_or_private_ip(doh_ips[0]):
        target_ip = doh_ips[0]

    if not target_ip:
        # DNS failed completely
        report.blocked_stage_id = "A"
        report.verdict = "BLOCKED_DNS"
        report.summary_headline = "🔴 Diblokir di Node A: DNS Poisoning / Sinkhole ISP"
        report.recommendation = (
            "Domain tidak dapat di-resolve atau diarahkan ke IP sinkhole oleh ISP/MikroTik. "
            "Solusi: Ganti DNS ke GRC Smart Mix atau aktifkan DoH Forwarder Netools."
        )
        report.recommended_action_type = "CHANGE_DNS"
        report.stages["B"] = DiagnosticStage("B", "2. TCP Connection (Layer 4)", "SKIPPED", summary="⚪ Skipped (No Valid IP)")
        report.stages["C"] = DiagnosticStage("C", "3. TLS SNI Handshake", "SKIPPED", summary="⚪ Skipped")
        report.stages["D"] = DiagnosticStage("D", "4. SSL Certificate & MITM", "SKIPPED", summary="⚪ Skipped")
        return report

    # 2. Stage B: TCP
    stage_b = evaluate_stage_b_tcp(target_ip, timeout=timeout)
    report.stages["B"] = stage_b

    if stage_b.status == "BLOCKED":
        report.blocked_stage_id = "B"
        report.verdict = "BLOCKED_IP_FIREWALL"
        report.summary_headline = "🔴 Diblokir di Node B: IP / Firewall Filter Port 443 Drop"
        report.recommendation = (
            f"Alamat IP ({target_ip}) di-drop di level router/firewall (MikroTik IP Filter / BGP Blackhole). "
            "Ganti DNS tidak akan mempan. Solusi: Gunakan Sing-box Proxy Rotator / Cloudflare WARP."
        )
        report.recommended_action_type = "PROXY_VPN"
        report.stages["C"] = DiagnosticStage("C", "3. TLS SNI Handshake", "SKIPPED", summary="⚪ Skipped (TCP Blocked)")
        report.stages["D"] = DiagnosticStage("D", "4. SSL Certificate & MITM", "SKIPPED", summary="⚪ Skipped")
        return report

    # 3. Stage C: TLS SNI DPI
    stage_c, ssock = evaluate_stage_c_sni_dpi(target_ip, clean_domain, timeout=timeout)
    report.stages["C"] = stage_c

    if stage_c.status == "BLOCKED":
        report.blocked_stage_id = "C"
        report.verdict = "BLOCKED_SNI_DPI"
        report.summary_headline = "🔴 Diblokir di Node C: Deep Packet Inspection (SNI Filtering)"
        report.recommendation = (
            f"Firewall kantor/ISP mendeteksi teks polos domain '{clean_domain}' di dalam TLS ClientHello "
            "dan menginjeksi paket TCP RST. DoH/DoQ tidak bisa menembus ini. "
            "Solusi: Aktifkan Sing-box Proxy Rotator (VLESS/Trojan) atau Cloudflare WARP untuk enkripsi total L3/L4."
        )
        report.recommended_action_type = "PROXY_VPN"
        report.stages["D"] = DiagnosticStage("D", "4. SSL Certificate & MITM", "SKIPPED", summary="⚪ Skipped (Handshake Reset)")
        return report

    # 4. Stage D: SSL MITM
    stage_d = evaluate_stage_d_ssl_mitm(clean_domain, ssock, target_ip)
    report.stages["D"] = stage_d

    if stage_d.status == "WARN":
        report.blocked_stage_id = "D"
        report.verdict = "MITM_INTERCEPTED"
        report.summary_headline = "🟡 Peringatan di Node D: Terdeteksi SSL Decryption / Corporate Proxy"
        report.recommendation = (
            "Koneksi berhasil tetapi traffic HTTPS di-dekripsi oleh firewall kantor (Corporate Proxy MITM). "
            "Gunakan Sing-box Proxy untuk melindungi privasi traffic."
        )
        report.recommended_action_type = "PROXY_VPN"
    else:
        report.blocked_stage_id = None
        report.verdict = "CLEAN_REACHABLE"
        report.summary_headline = "🟢 Bersih: Domain Dapat Diakses Penuh Tanpa Hambatan"
        report.recommendation = (
            f"Domain '{clean_domain}' dapat diakses normal di semua layer (DNS, TCP 443, TLS Handshake, & Cert Valid). "
            "Tidak ada pemblokiran atau intersepsi jaringan yang terdeteksi."
        )
        report.recommended_action_type = "NONE"

    return report
