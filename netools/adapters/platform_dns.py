"""
Unified Cross-Platform System DNS Controller for Linux, Windows, and macOS.
Automatically delegates to the native OS networking subsystem.
"""

import ipaddress
import subprocess
from typing import Any, Dict, List, Optional

from netools.adapters import systemd_dns as linux_dns
from netools.libs.env import get_os_type


def _validate_ips(ips: list) -> list:
    """Validate and filter IP addresses to prevent injection attacks."""
    validated = []
    for ip in ips:
        ip = ip.strip()
        if not ip:
            continue
        try:
            ipaddress.ip_address(ip)
            validated.append(ip)
        except ValueError:
            pass
    return validated


def get_network_interfaces() -> List[Dict[str, Any]]:
    """Detect active network interfaces on Linux, Windows, or macOS."""
    os_type = get_os_type()

    if os_type == "linux":
        return linux_dns.get_network_interfaces()

    elif os_type == "windows":
        interfaces = []
        try:
            # Use PowerShell to list active network adapters
            ps_cmd = "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object -Property Name, InterfaceDescription, Status | ConvertTo-Json"
            out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd], text=True)
            import json

            data = json.loads(out)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                name = item.get("Name", "Ethernet")
                desc = item.get("InterfaceDescription", "")
                interfaces.append(
                    {
                        "device": name,
                        "type": "ethernet" if "wi-fi" not in name.lower() else "wifi",
                        "connection": name,
                        "label": f"{name} ({desc})" if desc else name,
                        "is_default": len(interfaces) == 0,
                    }
                )
        except Exception:
            # Fallback to standard interface names
            interfaces = [
                {
                    "device": "Ethernet",
                    "type": "ethernet",
                    "connection": "Ethernet",
                    "label": "Ethernet [Default]",
                    "is_default": True,
                },
                {"device": "Wi-Fi", "type": "wifi", "connection": "Wi-Fi", "label": "Wi-Fi", "is_default": False},
            ]
        return interfaces

    elif os_type == "darwin":
        # macOS networksetup
        interfaces = []
        try:
            out = subprocess.check_output(["networksetup", "-listallnetworkservices"], text=True)
            for line in out.splitlines():
                line = line.strip()
                if line and not line.startswith("*") and "an asterisk" not in line.lower():
                    is_def = len(interfaces) == 0
                    interfaces.append(
                        {
                            "device": line,
                            "type": "wifi" if "wi-fi" in line.lower() else "ethernet",
                            "connection": line,
                            "label": f"{line}{' [Default]' if is_def else ''}",
                            "is_default": is_def,
                        }
                    )
        except Exception:
            interfaces = [
                {
                    "device": "Wi-Fi",
                    "type": "wifi",
                    "connection": "Wi-Fi",
                    "label": "Wi-Fi [Default]",
                    "is_default": True,
                },
                {
                    "device": "Ethernet",
                    "type": "ethernet",
                    "connection": "Ethernet",
                    "label": "Ethernet",
                    "is_default": False,
                },
            ]
        return interfaces

    return [
        {
            "device": "default",
            "type": "ethernet",
            "connection": "default",
            "label": "Default Interface",
            "is_default": True,
        }
    ]


def get_interface_dns(device: str) -> List[str]:
    """Retrieve active DNS IPs for a given network device on any OS."""
    os_type = get_os_type()

    if os_type == "linux":
        return linux_dns.get_interface_dns(device)

    elif os_type == "windows":
        try:
            ps_cmd = f"(Get-DnsClientServerAddress -InterfaceAlias '{device}' -AddressFamily IPv4).ServerAddresses"
            out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd], text=True)
            servers = _validate_ips(out.splitlines())
            if servers:
                return servers
        except Exception:
            pass
        return []

    elif os_type == "darwin":
        try:
            out = subprocess.check_output(["networksetup", "-getdnsservers", device], text=True)
            if "aren't any dns servers" not in out.lower():
                return [s.strip() for s in out.splitlines() if s.strip()]
        except Exception:
            pass
        return []

    return []


def apply_system_dns(
    device: str,
    ips: List[str],
    connection_name: Optional[str] = None,
    enable_dot: bool = False,
    persistent: bool = True,
) -> bool:
    """Apply DNS settings across Linux, Windows, or macOS."""
    valid_ips = _validate_ips(ips)
    if not valid_ips:
        return False

    os_type = get_os_type()

    if os_type == "linux":
        return linux_dns.apply_system_dns(
            device, valid_ips, connection_name=connection_name, enable_dot=enable_dot, persistent=persistent
        )

    elif os_type == "windows":
        try:
            ips_formatted = ",".join([f"'{ip}'" for ip in valid_ips])
            ps_cmd = f"Set-DnsClientServerAddress -InterfaceAlias '{device}' -ServerAddresses ({ips_formatted})"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True)
            flush_dns_cache()
            return True
        except Exception:
            # Fallback to netsh
            try:
                subprocess.run(
                    [
                        "netsh",
                        "interface",
                        "ip",
                        "set",
                        "dns",
                        f"name={device}",
                        "source=static",
                        f"addr={valid_ips[0]}",
                    ],
                    capture_output=True,
                )
                for ip in valid_ips[1:]:
                    subprocess.run(
                        ["netsh", "interface", "ip", "add", "dns", f"name={device}", f"addr={ip}", "index=2"],
                        capture_output=True,
                    )
                flush_dns_cache()
                return True
            except Exception:
                return False

    elif os_type == "darwin":
        try:
            cmd = ["networksetup", "-setdnsservers", device, *valid_ips]
            subprocess.run(cmd, capture_output=True)
            flush_dns_cache()
            return True
        except Exception:
            return False

    return False


def restore_default_dns(device: str, connection_name: Optional[str] = None) -> bool:
    """Revert interface back to DHCP DNS on any OS."""
    os_type = get_os_type()

    if os_type == "linux":
        return linux_dns.restore_default_dns(device, connection_name)

    elif os_type == "windows":
        try:
            ps_cmd = f"Set-DnsClientServerAddress -InterfaceAlias '{device}' -ResetServerAddresses"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True)
            flush_dns_cache()
            return True
        except Exception:
            try:
                subprocess.run(
                    ["netsh", "interface", "ip", "set", "dns", f"name={device}", "source=dhcp"], capture_output=True
                )
                flush_dns_cache()
                return True
            except Exception:
                return False

    elif os_type == "darwin":
        try:
            subprocess.run(["networksetup", "-setdnsservers", device, "Empty"], capture_output=True)
            flush_dns_cache()
            return True
        except Exception:
            return False

    return False


def flush_dns_cache() -> bool:
    """Flush DNS cache on Linux, Windows, or macOS."""
    os_type = get_os_type()

    if os_type == "linux":
        return linux_dns.flush_dns_cache()

    elif os_type == "windows":
        try:
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True)
            return True
        except Exception:
            return False

    elif os_type == "darwin":
        try:
            subprocess.run(["dscacheutil", "-flushcache"], capture_output=True)
            subprocess.run(["killall", "-HUP", "mDNSResponder"], capture_output=True)
            return True
        except Exception:
            return False

    return False
