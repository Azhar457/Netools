#!/usr/bin/env python3
"""
Local Network Threat & MiTM / Rogue Gateway Detector.
Implements heuristics and signature analysis for:
1. ARP Table Parsing & Gateway ARP Spoofing / Poisoning Detection (Bettercap / Ettercap / arpspoof)
2. Gateway MAC Address Flapping & Anomaly Tracking
3. Duplicate MAC / Multiple IPs per MAC Mapping Analysis
4. Rogue Gateway & Default Route Conflict Detection
5. Suspicious Local DNS Redirection (Local IP masquerading as DNS server)
"""

import os
import re
import socket
import struct
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from netools.libs.env import get_os_type

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class ARPEntry:
    ip: str
    mac: str
    interface: str = ""
    flags: str = ""
    is_gateway: bool = False
    is_static: bool = False


@dataclass
class NetworkThreatReport:
    timestamp: float = field(default_factory=time.time)
    gateway_ip: Optional[str] = None
    gateway_mac: Optional[str] = None
    arp_spoof_detected: bool = False
    arp_flapping_detected: bool = False
    duplicate_mac_detected: bool = False
    rogue_gateway_detected: bool = False
    suspicious_local_dns_detected: bool = False
    threat_level: str = "Low"  # None, Low, Medium, High, Critical
    threats_found: List[str] = field(default_factory=list)
    arp_table: List[ARPEntry] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# GATEWAY & ROUTE DISCOVERY
# ==============================================================================

def get_default_gateway() -> Tuple[Optional[str], Optional[str]]:
    """
    Retrieve default gateway IP address and interface name cross-platform.
    Returns: (gateway_ip, interface_name)
    """
    os_type = get_os_type()

    if os_type == "linux":
        # 1. Try /proc/net/route
        if os.path.exists("/proc/net/route"):
            try:
                with open("/proc/net/route", "r") as f:
                    for line in f:
                        fields = line.strip().split()
                        if len(fields) >= 3 and fields[1] == "00000000":
                            iface = fields[0]
                            gw_hex = fields[2]
                            gw_ip = socket.inet_ntoa(struct.pack("<L", int(gw_hex, 16)))
                            return gw_ip, iface
            except Exception:
                pass

        # 2. Try 'ip route' command
        try:
            out = subprocess.check_output(["ip", "route", "show", "default"], text=True, stderr=subprocess.DEVNULL)
            m = re.search(r"default via ([\d\.]+) dev (\S+)", out)
            if m:
                return m.group(1), m.group(2)
        except Exception:
            pass

    elif os_type == "darwin":
        try:
            out = subprocess.check_output(["route", "-n", "get", "default"], text=True, stderr=subprocess.DEVNULL)
            gw_ip = None
            iface = None
            for line in out.splitlines():
                if "gateway:" in line:
                    gw_ip = line.split(":", 1)[1].strip()
                elif "interface:" in line:
                    iface = line.split(":", 1)[1].strip()
            if gw_ip:
                return gw_ip, iface or "en0"
        except Exception:
            pass

    elif os_type == "windows":
        try:
            out = subprocess.check_output(["route", "print", "0.0.0.0"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                    return parts[2], parts[3]
        except Exception:
            pass

    return None, None


# ==============================================================================
# ARP TABLE PARSING
# ==============================================================================

def parse_arp_table() -> List[ARPEntry]:
    """
    Parse operating system ARP cache into structured ARPEntry records.
    Supports Linux (/proc/net/arp and ip neigh), macOS (arp -an), and Windows (arp -a).
    """
    entries: List[ARPEntry] = []
    os_type = get_os_type()

    if os_type == "linux":
        # Check /proc/net/arp first (fastest, no subshell)
        if os.path.exists("/proc/net/arp"):
            try:
                with open("/proc/net/arp", "r") as f:
                    lines = f.readlines()
                for line in lines[1:]:  # Skip header
                    parts = line.strip().split()
                    if len(parts) >= 6:
                        ip = parts[0]
                        flags = parts[2]
                        mac = parts[3].lower()
                        dev = parts[5]
                        if mac != "00:00:00:00:00:00" and len(mac) == 17:
                            entries.append(ARPEntry(ip=ip, mac=mac, interface=dev, flags=flags))
                if entries:
                    return entries
            except Exception:
                pass

        # Fallback to 'ip neigh'
        try:
            out = subprocess.check_output(["ip", "neigh", "show"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 4 and "lladdr" in parts:
                    idx = parts.index("lladdr")
                    if idx + 1 < len(parts):
                        ip = parts[0]
                        mac = parts[idx + 1].lower()
                        dev = parts[parts.index("dev") + 1] if "dev" in parts else ""
                        if len(mac) == 17:
                            entries.append(ARPEntry(ip=ip, mac=mac, interface=dev))
            if entries:
                return entries
        except Exception:
            pass

    # Generic / macOS / Windows fallback via 'arp -a'
    try:
        cmd = ["arp", "-an"] if os_type in ("linux", "darwin") else ["arp", "-a"]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            # Match IP and MAC pattern
            ip_m = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
            mac_m = re.search(r"([0-9a-fA-F]{1,2}[:-][0-9a-fA-F]{1,2}[:-][0-9a-fA-F]{1,2}[:-][0-9a-fA-F]{1,2}[:-][0-9a-fA-F]{1,2}[:-][0-9a-fA-F]{1,2})", line)
            if ip_m and mac_m:
                ip = ip_m.group(1)
                mac = mac_m.group(1).lower().replace("-", ":")
                # Normalize mac 1-digit segments (e.g. 0:a:36:... -> 00:0a:36:...)
                mac_parts = [p.zfill(2) for p in mac.split(":")]
                if len(mac_parts) == 6:
                    norm_mac = ":".join(mac_parts)
                    if norm_mac != "ff:ff:ff:ff:ff:ff" and not norm_mac.startswith("01:00:5e"):
                        entries.append(ARPEntry(ip=ip, mac=norm_mac))
    except Exception:
        pass

    return entries


# ==============================================================================
# THREAT DETECTION HEURISTICS
# ==============================================================================

class GatewayTracker:
    """Tracks historical Gateway MAC addresses to detect ARP Poisoning / Flapping over time."""
    _instance: Optional["GatewayTracker"] = None

    def __init__(self):
        self.last_known_gateway_ip: Optional[str] = None
        self.last_known_gateway_mac: Optional[str] = None
        self.mac_history: List[Tuple[float, str, str]] = []  # [(timestamp, ip, mac)]

    @classmethod
    def get_instance(cls) -> "GatewayTracker":
        if cls._instance is None:
            cls._instance = GatewayTracker()
        return cls._instance

    def update_and_check_flapping(self, current_gw_ip: str, current_gw_mac: str) -> bool:
        """
        Record gateway MAC and check if MAC has changed for the same IP (indicates active MITM).
        """
        now = time.time()
        flapping = False

        if (
            self.last_known_gateway_ip == current_gw_ip and
            self.last_known_gateway_mac is not None and
            self.last_known_gateway_mac != current_gw_mac
        ):
            flapping = True

        self.last_known_gateway_ip = current_gw_ip
        self.last_known_gateway_mac = current_gw_mac
        self.mac_history.append((now, current_gw_ip, current_gw_mac))
        if len(self.mac_history) > 50:
            self.mac_history.pop(0)

        return flapping


def detect_arp_spoofing(
    arp_entries: List[ARPEntry],
    gateway_ip: Optional[str] = None
) -> Tuple[bool, bool, Optional[str], List[str]]:
    """
    Analyze ARP table for spoofing signatures:
    1. Multiple distinct non-gateway IPs sharing the Gateway's MAC address (ARP Poisoning).
    2. Multiple distinct IPs sharing any single unicast MAC address.
    Returns: (is_spoof_detected, is_duplicate_mac, gateway_mac, threat_reasons)
    """
    reasons: List[str] = []
    mac_to_ips: Dict[str, Set[str]] = {}
    ip_to_mac: Dict[str, str] = {}

    for entry in arp_entries:
        mac_to_ips.setdefault(entry.mac, set()).add(entry.ip)
        ip_to_mac[entry.ip] = entry.mac

    gw_mac = ip_to_mac.get(gateway_ip) if gateway_ip else None
    spoof_detected = False
    duplicate_mac_detected = False

    # Check 1: Did an attacker spoof the Gateway? (Gateway MAC mapped to other client IPs)
    if gateway_ip and gw_mac:
        ips_with_gw_mac = mac_to_ips.get(gw_mac, set())
        other_ips = [ip for ip in ips_with_gw_mac if ip != gateway_ip]
        if other_ips:
            spoof_detected = True
            reasons.append(
                f"🚨 ARP Poisoning Signature Detected: Gateway ({gateway_ip}) MAC [{gw_mac}] "
                f"is also claimed by client host(s): {', '.join(other_ips)} (Bettercap/Ettercap MITM)."
            )

    # Check 2: General duplicate MAC anomaly (Multiple IP addresses for 1 physical NIC)
    for mac, ips in mac_to_ips.items():
        if len(ips) > 2 and mac != gw_mac:
            duplicate_mac_detected = True
            reasons.append(
                f"⚠️ Duplicate MAC Anomaly: MAC [{mac}] is responding for multiple IP addresses: {', '.join(ips)}."
            )

    return spoof_detected, duplicate_mac_detected, gw_mac, reasons


def check_suspicious_local_dns(
    gateway_ip: Optional[str],
    active_dns_ips: List[str]
) -> Tuple[bool, List[str]]:
    """
    Check if configured DNS servers are local LAN private IPs that are NOT the Default Gateway.
    (Common Ettercap / Rogue DHCP / DNS spoofing technique).
    """
    suspicious = False
    reasons: List[str] = []

    for dns_ip in active_dns_ips:
        if not dns_ip or ":" in dns_ip:
            continue
        # Check if private IP (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
        is_private = (
            dns_ip.startswith("192.168.") or
            dns_ip.startswith("10.") or
            (dns_ip.startswith("172.") and 16 <= int(dns_ip.split(".")[1]) <= 31)
        )
        if is_private:
            if gateway_ip and dns_ip != gateway_ip:
                suspicious = True
                reasons.append(
                    f"⚠️ Rogue Local DNS Warning: Active DNS server {dns_ip} is a private LAN IP "
                    f"distinct from Gateway {gateway_ip}. Potential local DNS hijacker / proxy."
                )

    return suspicious, reasons


# ==============================================================================
# MASTER SCANNER & AUDIT RUNNER
# ==============================================================================

def scan_local_network_threats() -> NetworkThreatReport:
    """
    Execute full scan of local network security posture:
    - Gateway discovery & ARP table extraction
    - Bettercap / Ettercap ARP spoofing signature detection
    - Gateway MAC flapping check
    - Rogue Gateway & Local DNS hijacking verification
    """
    report = NetworkThreatReport()
    gw_ip, gw_iface = get_default_gateway()
    report.gateway_ip = gw_ip
    report.details["gateway_interface"] = gw_iface

    arp_entries = parse_arp_table()
    report.arp_table = arp_entries

    # 1. ARP Spoof & Duplicate MAC Analysis
    is_spoof, is_dup_mac, gw_mac, spoof_reasons = detect_arp_spoofing(arp_entries, gateway_ip=gw_ip)
    report.arp_spoof_detected = is_spoof
    report.duplicate_mac_detected = is_dup_mac
    report.gateway_mac = gw_mac
    report.threats_found.extend(spoof_reasons)

    # 2. Gateway MAC Flapping Analysis
    if gw_ip and gw_mac:
        tracker = GatewayTracker.get_instance()
        flapping = tracker.update_and_check_flapping(gw_ip, gw_mac)
        report.arp_flapping_detected = flapping
        if flapping:
            report.threats_found.append(
                f"🚨 Gateway MAC Flapping Detected: Gateway {gw_ip} MAC address changed unexpectedly! Active MITM in progress."
            )

    # 3. Suspicious Local DNS Check
    from netools.adapters import platform_dns
    iface_dev = gw_iface or (platform_dns.get_network_interfaces()[0]["device"] if platform_dns.get_network_interfaces() else "default")
    active_dns = platform_dns.get_interface_dns(iface_dev)
    report.details["active_dns"] = active_dns

    susp_dns, susp_reasons = check_suspicious_local_dns(gw_ip, active_dns)
    report.suspicious_local_dns_detected = susp_dns
    report.threats_found.extend(susp_reasons)

    # Determine Threat Level
    if report.arp_spoof_detected or report.arp_flapping_detected:
        report.threat_level = "Critical"
    elif report.suspicious_local_dns_detected or report.duplicate_mac_detected:
        report.threat_level = "Medium"
    elif not gw_ip:
        report.threat_level = "Low"
    else:
        report.threat_level = "None"

    return report
