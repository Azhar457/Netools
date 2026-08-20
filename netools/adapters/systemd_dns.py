"""
Linux System DNS Adapter: resolvectl, systemd-resolved, and NetworkManager (nmcli).
"""

import subprocess
from typing import List, Dict, Any, Optional

def get_network_interfaces() -> List[Dict[str, Any]]:
    """Detect active network interfaces and their connection details."""
    interfaces = []
    default_dev = None
    try:
        out = subprocess.check_output(["ip", "route", "show", "default"], text=True)
        for line in out.splitlines():
            parts = line.split()
            if "dev" in parts:
                idx = parts.index("dev")
                if idx + 1 < len(parts):
                    default_dev = parts[idx + 1]
                    break
    except Exception:
        pass

    try:
        out = subprocess.check_output(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], text=True)
        for line in out.splitlines():
            parts = line.strip().split(":")
            if len(parts) >= 4:
                dev, dev_type, state, conn = parts[0], parts[1], parts[2], parts[3]
                if dev_type not in ("loopback", "bridge") and state in ("connected", "connecting"):
                    is_def = (dev == default_dev)
                    label = f"{dev} ({conn or dev_type}){' [Default]' if is_def else ''}"
                    interfaces.append({
                        "device": dev,
                        "type": dev_type,
                        "connection": conn,
                        "label": label,
                        "is_default": is_def
                    })
    except Exception:
        pass

    if not interfaces and default_dev:
        interfaces.append({
            "device": default_dev,
            "type": "ethernet",
            "connection": default_dev,
            "label": f"{default_dev} [Default]",
            "is_default": True
        })

    interfaces.sort(key=lambda x: 0 if x["is_default"] else 1)
    return interfaces

def get_interface_dns(device: str) -> List[str]:
    """Retrieve active DNS IPs for a given network device."""
    dns_servers = []
    try:
        out = subprocess.check_output(["resolvectl", "dns", device], text=True)
        if ":" in out:
            servers_part = out.split(":", 1)[1].strip()
            dns_servers = servers_part.split()
    except Exception:
        pass

    if not dns_servers:
        try:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    if line.startswith("nameserver") and not line.split()[1].startswith("127.0.0.53"):
                        dns_servers.append(line.split()[1])
        except Exception:
            pass
    return dns_servers

def apply_system_dns(device: str, ips: List[str], connection_name: Optional[str] = None, enable_dot: bool = False, persistent: bool = True) -> bool:
    """Set DNS on interface via resolvectl and NetworkManager."""
    valid_ips = [ip.strip() for ip in ips if ip and not ip.isspace()]
    if not valid_ips or not device:
        return False

    # 1. Update NetworkManager if persistent
    if persistent and connection_name:
        v4_ips = [ip for ip in valid_ips if ":" not in ip]
        v6_ips = [ip for ip in valid_ips if ":" in ip]
        if v4_ips:
            cmd_nm_v4 = ["nmcli", "connection", "modify", connection_name, "ipv4.dns", " ".join(v4_ips), "ipv4.ignore-auto-dns", "yes"]
            subprocess.run(cmd_nm_v4, capture_output=True)
        if v6_ips:
            cmd_nm_v6 = ["nmcli", "connection", "modify", connection_name, "ipv6.dns", " ".join(v6_ips), "ipv6.ignore-auto-dns", "yes"]
            subprocess.run(cmd_nm_v6, capture_output=True)
        subprocess.run(["nmcli", "connection", "up", connection_name], capture_output=True)

    # 2. Apply runtime DNS to systemd-resolved
    cmd = ["resolvectl", "dns", device] + valid_ips
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        subprocess.run(["sudo", "resolvectl", "dns", device] + valid_ips, capture_output=True)

    # 3. Configure DNS-over-TLS (DoT)
    if enable_dot:
        # Enable TLS (opportunistic encryption for IP resolvers) and route global domains (~.)
        subprocess.run(["resolvectl", "dnsovertls", device, "opportunistic"], capture_output=True)
        subprocess.run(["resolvectl", "domain", device, "~."], capture_output=True)
    else:
        subprocess.run(["resolvectl", "dnsovertls", device, "no"], capture_output=True)

    flush_dns_cache()
    return True

def restore_default_dns(device: str, connection_name: Optional[str] = None) -> bool:
    """Revert interface back to DHCP DNS."""
    if not device:
        return False
    subprocess.run(["resolvectl", "revert", device], capture_output=True)
    if connection_name:
        subprocess.run(["nmcli", "connection", "modify", connection_name, "ipv4.ignore-auto-dns", "no", "ipv4.dns", "", "ipv6.ignore-auto-dns", "no", "ipv6.dns", ""], capture_output=True)
        subprocess.run(["nmcli", "connection", "up", connection_name], capture_output=True)
    flush_dns_cache()
    return True

def flush_dns_cache() -> None:
    """Flush systemd-resolved DNS cache."""
    try:
        subprocess.run(["resolvectl", "flush-caches"], capture_output=True)
        subprocess.run(["resolvectl", "reset-server-features"], capture_output=True)
    except Exception:
        pass
