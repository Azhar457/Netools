"""
Environment & Dependency Diagnostics Engine for Netools Suite.
Detects OS platform (Linux, Windows, macOS), required binaries (sing-box, curl),
system DNS engines, and optional local DoH forwarders (dnscrypt-proxy, cloudflared).
"""

import platform
import shutil
import subprocess
import sys
from typing import Any, Dict


def get_os_type() -> str:
    """Return 'linux', 'windows', 'darwin' (macOS), or 'unknown'."""
    p = platform.system().lower()
    if "windows" in p or sys.platform == "win32":
        return "windows"
    elif "darwin" in p or "mac" in p:
        return "darwin"
    elif "linux" in p:
        return "linux"
    return "unknown"

def check_binary(name: str) -> Dict[str, Any]:
    """Check if a CLI executable exists on PATH or in standard directory."""
    path = shutil.which(name)
    if not path and get_os_type() == "windows" and not name.endswith(".exe"):
        path = shutil.which(f"{name}.exe")

    found = path is not None
    version_str = "Not installed"

    if found:
        try:
            flag = "-v" if name == "sing-box" else "--version"
            res = subprocess.run([path, flag], capture_output=True, text=True, timeout=0.4)
            out = (res.stdout.strip() or res.stderr.strip()).splitlines()
            if out:
                version_str = out[0][:45]
        except Exception:
            version_str = "Installed"
        if version_str == "Not installed":
            version_str = "Installed"

    return {
        "name": name,
        "found": found,
        "path": path or "",
        "version": version_str
    }

def get_system_diagnostics() -> Dict[str, Any]:
    """Run full platform environment & dependency diagnostics check."""
    os_type = get_os_type()
    os_name = f"{platform.system()} {platform.release()} ({platform.machine()})"

    # Core required / recommended tools
    core_tools = {
        "sing-box": check_binary("sing-box"),
        "curl": check_binary("curl"),
    }

    # Optional local DNS forwarders (e.g. dnscrypt-proxy, cloudflared, stubby)
    dns_forwarders = {
        "dnscrypt-proxy": check_binary("dnscrypt-proxy"),
        "cloudflared": check_binary("cloudflared"),
        "stubby": check_binary("stubby"),
    }

    # System DNS control capability
    dns_controller = "Unknown"
    if os_type == "linux":
        if shutil.which("resolvectl"):
            dns_controller = "systemd-resolved (resolvectl)"
        elif shutil.which("nmcli"):
            dns_controller = "NetworkManager (nmcli)"
        else:
            dns_controller = "Standard /etc/resolv.conf"
    elif os_type == "windows":
        dns_controller = "Windows PowerShell NetTCPIP (Set-DnsClientServerAddress)"
    elif os_type == "darwin":
        dns_controller = "macOS networksetup & scutil"

    return {
        "os_type": os_type,
        "os_name": os_name,
        "python_version": sys.version.split()[0],
        "dns_controller": dns_controller,
        "core_tools": core_tools,
        "dns_forwarders": dns_forwarders,
        "pure_python_doh": True,  # 100% Zero-dependency DoH via RFC 8484 wireformat
    }
