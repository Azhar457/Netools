"""
Linux System DNS Adapter: resolvectl, systemd-resolved, and NetworkManager (nmcli).
Provides atomic batched execution to prevent multiple repetitive password / polkit prompts.
"""

import ipaddress
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional


def _split_host_port(ip: str):
    """Return (host, port) from 'host' or 'host:port' (IPv4 or [IPv6]:port)."""
    ip = ip.strip()
    if ip.startswith("["):  # [IPv6]:port
        end = ip.rfind("]")
        host = ip[1:end]
        port = ip[end + 2 :] if end + 1 < len(ip) and ip[end + 1] == ":" else None
        return host, port
    if ip.count(":") == 1:  # IPv4:port
        host, _, port = ip.partition(":")
        return host, (port or None)
    return ip, None


def _validate_ips(ips: list) -> list:
    """Validate and filter IP addresses (optionally with :port) to prevent injection."""
    validated = []
    for raw in ips:
        ip = (raw or "").strip()
        if not ip:
            continue
        host, port = _split_host_port(ip)
        try:
            ipaddress.ip_address(host)
        except ValueError:
            continue
        if port is not None and not port.isdigit():
            continue
        validated.append(ip)
    return validated


def _run_batched_commands(cmds: List[List[str]]) -> bool:
    """
    Execute a list of shell commands with minimal authentication prompts.
    First tries unprivileged execution. If any command requires elevated privileges,
    bundles the failed commands into a single pkexec / sudo call so the user is prompted AT MOST ONCE.
    """
    failed_cmds = []
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                failed_cmds.append(cmd)
        except Exception:
            failed_cmds.append(cmd)

    if not failed_cmds:
        return True

    # If commands failed due to permissions, execute all remaining commands in ONE single pkexec invocation
    pkexec_bin = shutil.which("pkexec")
    if pkexec_bin and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        script_parts = []
        for cmd in failed_cmds:
            escaped_args = " ".join(f"'{arg}'" for arg in cmd)
            script_parts.append(escaped_args)

        batch_script = " && ".join(script_parts)
        try:
            res = subprocess.run([pkexec_bin, "sh", "-c", batch_script], capture_output=True, text=True)
            return res.returncode == 0
        except Exception:
            pass

    # Fallback to sudo if pkexec is unavailable
    if shutil.which("sudo"):
        script_parts = [" ".join(f"'{arg}'" for arg in cmd) for cmd in failed_cmds]
        batch_script = " && ".join(script_parts)
        try:
            res = subprocess.run(["sudo", "sh", "-c", batch_script], capture_output=True, text=True)
            return res.returncode == 0
        except Exception:
            pass

    return False


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
                    is_def = dev == default_dev
                    label = f"{dev} ({conn or dev_type}){' [Default]' if is_def else ''}"
                    interfaces.append(
                        {"device": dev, "type": dev_type, "connection": conn, "label": label, "is_default": is_def}
                    )
    except Exception:
        pass

    if not interfaces and default_dev:
        interfaces.append(
            {
                "device": default_dev,
                "type": "ethernet",
                "connection": default_dev,
                "label": f"{default_dev} [Default]",
                "is_default": True,
            }
        )

    interfaces.sort(key=lambda x: 0 if x["is_default"] else 1)
    return interfaces


def get_interface_dns(device: str) -> List[str]:
    """Retrieve active DNS IPs for a given network device."""
    dns_servers = []
    try:
        out = subprocess.check_output(["resolvectl", "dns", device], text=True, stderr=subprocess.DEVNULL)
        if ":" in out:
            servers_part = out.split(":", 1)[1].strip()
            dns_servers = servers_part.split()
    except Exception:
        pass

    if not dns_servers:
        try:
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "IP4.DNS,IP6.DNS", "device", "show", device], text=True, stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                if ":" in line:
                    val = line.split(":", 1)[1].strip()
                    if val and val not in dns_servers:
                        dns_servers.append(val)
        except Exception:
            pass

    if not dns_servers:
        try:
            with open("/etc/resolv.conf") as f:
                for line in f:
                    if line.startswith("nameserver") and not line.split()[1].startswith("127.0.0.53"):
                        dns_servers.append(line.split()[1])
        except Exception:
            pass
    return dns_servers


def apply_system_dns(
    device: str,
    ips: List[str],
    connection_name: Optional[str] = None,
    enable_dot: bool = False,
    persistent: bool = True,
) -> bool:
    """Set DNS on interface via resolvectl and NetworkManager atomically with at most 1 auth prompt."""
    valid_ips = _validate_ips(ips)
    if not valid_ips or not device:
        return False

    cmds: List[List[str]] = []

    # 1. Update NetworkManager in a single combined command if persistent
    # Note: nmcli ipv4.dns/ipv6.dns strictly rejects custom ports (e.g. 127.0.0.1:5353).
    # Custom ports are routed at runtime by systemd-resolved (resolvectl) in step 2.
    if persistent and connection_name:
        nm_v4 = [
            _split_host_port(ip)[0]
            for ip in valid_ips
            if ":" not in _split_host_port(ip)[0] and _split_host_port(ip)[1] is None
        ]
        nm_v6 = [
            _split_host_port(ip)[0]
            for ip in valid_ips
            if ":" in _split_host_port(ip)[0] and _split_host_port(ip)[1] is None
        ]

        if nm_v4 or nm_v6:
            nm_args = ["nmcli", "connection", "modify", connection_name]
            if nm_v4:
                nm_args.extend(["ipv4.dns", " ".join(nm_v4), "ipv4.ignore-auto-dns", "yes"])
            if nm_v6:
                nm_args.extend(["ipv6.dns", " ".join(nm_v6), "ipv6.ignore-auto-dns", "yes"])
            cmds.append(nm_args)

    # 2. Runtime DNS via resolvectl (accepts <IP>[:PORT], e.g. 127.0.0.1:5353)
    cmds.append(["resolvectl", "dns", device, *valid_ips])

    # 3. Configure DNS-over-TLS (DoT)
    if enable_dot:
        cmds.append(["resolvectl", "dnsovertls", device, "opportunistic"])
        cmds.append(["resolvectl", "domain", device, "~."])
    else:
        cmds.append(["resolvectl", "dnsovertls", device, "no"])

    # 4. Flush caches
    cmds.append(["resolvectl", "flush-caches"])

    return _run_batched_commands(cmds)


def restore_default_dns(device: str, connection_name: Optional[str] = None) -> bool:
    """Revert interface back to DHCP DNS atomically."""
    if not device:
        return False
    cmds: List[List[str]] = [["resolvectl", "revert", device]]
    if connection_name:
        cmds.append(
            [
                "nmcli",
                "connection",
                "modify",
                connection_name,
                "ipv4.ignore-auto-dns",
                "no",
                "ipv4.dns",
                "",
                "ipv6.ignore-auto-dns",
                "no",
                "ipv6.dns",
                "",
            ]
        )
    cmds.append(["resolvectl", "flush-caches"])
    return _run_batched_commands(cmds)


def flush_dns_cache() -> None:
    """Flush systemd-resolved DNS cache."""
    try:
        subprocess.run(["resolvectl", "flush-caches"], capture_output=True)
        subprocess.run(["resolvectl", "reset-server-features"], capture_output=True)
    except Exception:
        pass
