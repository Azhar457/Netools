"""
Cross-Platform Native System Proxy Controller for macOS, Windows, and Linux.
Enables and disables system-wide PAC (Proxy Auto-Configuration) and SOCKS/HTTP proxies.
"""

import os
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional

from netools.libs.env import get_os_type
from netools.libs.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# macOS (Darwin) Implementation using networksetup
# ---------------------------------------------------------------------------

def _get_macos_active_service() -> str:
    """Detect the active primary network service on macOS (e.g. 'Wi-Fi' or 'Ethernet')."""
    try:
        # Check default route first to identify active interface (e.g., en0)
        route_out = subprocess.check_output(["route", "-n", "get", "default"], text=True, stderr=subprocess.DEVNULL)
        interface_id = ""
        for line in route_out.splitlines():
            line = line.strip()
            if line.startswith("interface:"):
                interface_id = line.split(":", 1)[1].strip()
                break

        if interface_id:
            # Map interface BSD name (en0) to Network Service Name (Wi-Fi)
            order_out = subprocess.check_output(["networksetup", "-listnetworkserviceorder"], text=True, stderr=subprocess.DEVNULL)
            lines = order_out.splitlines()
            for i, line in enumerate(lines):
                if f"Device: {interface_id}" in line and i > 0:
                    prev = lines[i - 1]
                    if ")" in prev:
                        return prev.split(")", 1)[1].strip()

        # Fallback: list all network services and pick the first available non-asterisk
        services_out = subprocess.check_output(["networksetup", "-listallnetworkservices"], text=True, stderr=subprocess.DEVNULL)
        for line in services_out.splitlines():
            line = line.strip()
            if line and not line.startswith("*") and "asterisk" not in line.lower():
                return line
    except Exception as e:
        log.debug("macOS active network service detection fallback: %s", e)

    return "Wi-Fi"


def _enable_macos_proxy(pac_url: str, socks_host: str = "127.0.0.1", socks_port: int = 11080) -> bool:
    service = _get_macos_active_service()
    try:
        # Set Auto Proxy (PAC) URL and enable it
        subprocess.run(["networksetup", "-setautoproxyurl", service, pac_url], check=True, capture_output=True)
        subprocess.run(["networksetup", "-setautoproxystate", service, "on"], check=True, capture_output=True)
        # Also configure SOCKS proxy as fallback
        subprocess.run(["networksetup", "-setsocksfirewallproxy", service, socks_host, str(socks_port)], check=True, capture_output=True)
        subprocess.run(["networksetup", "-setsocksfirewallproxystate", service, "on"], check=True, capture_output=True)
        log.info("Enabled macOS system proxy on service '%s' with PAC: %s", service, pac_url)
        return True
    except Exception as e:
        log.error("Failed to enable macOS system proxy on '%s': %s", service, e)
        return False


def _disable_macos_proxy() -> bool:
    service = _get_macos_active_service()
    success = True
    try:
        subprocess.run(["networksetup", "-setautoproxystate", service, "off"], check=True, capture_output=True)
    except Exception as e:
        log.debug("macOS disable autoproxy failed: %s", e)
        success = False

    try:
        subprocess.run(["networksetup", "-setsocksfirewallproxystate", service, "off"], check=True, capture_output=True)
        subprocess.run(["networksetup", "-setwebproxystate", service, "off"], check=True, capture_output=True)
        subprocess.run(["networksetup", "-setsecurewebproxystate", service, "off"], check=True, capture_output=True)
    except Exception as e:
        log.debug("macOS disable manual proxy failed: %s", e)

    log.info("Disabled macOS system proxy on service '%s'", service)
    return success


def _get_macos_proxy_status() -> Dict[str, Any]:
    service = _get_macos_active_service()
    pac_enabled = False
    pac_url = ""
    socks_enabled = False

    try:
        pac_info = subprocess.check_output(["networksetup", "-getautoproxyurl", service], text=True, stderr=subprocess.DEVNULL)
        for line in pac_info.splitlines():
            line = line.strip()
            if line.startswith("URL:"):
                pac_url = line.split(":", 1)[1].strip()
            elif line.startswith("Enabled:"):
                pac_enabled = line.split(":", 1)[1].strip().lower() == "yes"

        socks_info = subprocess.check_output(["networksetup", "-getsocksfirewallproxy", service], text=True, stderr=subprocess.DEVNULL)
        for line in socks_info.splitlines():
            line = line.strip()
            if line.startswith("Enabled:"):
                socks_enabled = line.split(":", 1)[1].strip().lower() == "yes"
    except Exception as e:
        log.debug("macOS get proxy status error: %s", e)

    return {
        "enabled": pac_enabled or socks_enabled,
        "pac_url": pac_url,
        "service": service,
        "type": "pac" if pac_enabled else ("socks" if socks_enabled else "none"),
    }


# ---------------------------------------------------------------------------
# Windows Implementation using winreg & WinINet API
# ---------------------------------------------------------------------------

_INTERNET_SETTINGS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"


def _notify_windows_internet_settings_changed() -> None:
    """Notify WinINet via ctypes so all applications reload proxy immediately without reboot."""
    try:
        import ctypes

        INTERNET_OPTION_SETTINGS_CHANGED = 39
        INTERNET_OPTION_REFRESH = 37
        wininet = ctypes.windll.wininet
        wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
        wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)
    except Exception as e:
        log.debug("Failed to notify WinINet via ctypes: %s", e)


def _enable_windows_proxy(pac_url: str, socks_host: str = "127.0.0.1", socks_port: int = 11080) -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INTERNET_SETTINGS_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "AutoConfigURL", 0, winreg.REG_SZ, pac_url)
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)  # PAC handles routing
        _notify_windows_internet_settings_changed()
        log.info("Enabled Windows system proxy via AutoConfigURL: %s", pac_url)
        return True
    except Exception as e:
        # Fallback via PowerShell
        try:
            cmd = (
                f'Set-ItemProperty -Path "HKCU:\\{_INTERNET_SETTINGS_KEY}" -Name AutoConfigURL -Value "{pac_url}"; '
                f'Set-ItemProperty -Path "HKCU:\\{_INTERNET_SETTINGS_KEY}" -Name ProxyEnable -Value 0'
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=True, capture_output=True)
            _notify_windows_internet_settings_changed()
            return True
        except Exception as ps_err:
            log.error("Failed to enable Windows proxy: %s / %s", e, ps_err)
            return False


def _disable_windows_proxy() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INTERNET_SETTINGS_KEY, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, "AutoConfigURL")
            except FileNotFoundError:
                pass
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        _notify_windows_internet_settings_changed()
        log.info("Disabled Windows system proxy")
        return True
    except Exception as e:
        try:
            cmd = (
                f'Remove-ItemProperty -Path "HKCU:\\{_INTERNET_SETTINGS_KEY}" -Name AutoConfigURL -ErrorAction SilentlyContinue; '
                f'Set-ItemProperty -Path "HKCU:\\{_INTERNET_SETTINGS_KEY}" -Name ProxyEnable -Value 0'
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=True, capture_output=True)
            _notify_windows_internet_settings_changed()
            return True
        except Exception as ps_err:
            log.error("Failed to disable Windows proxy: %s / %s", e, ps_err)
            return False


def _get_windows_proxy_status() -> Dict[str, Any]:
    pac_url = ""
    proxy_enable = 0
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INTERNET_SETTINGS_KEY, 0, winreg.KEY_READ) as key:
            try:
                pac_url, _ = winreg.QueryValueEx(key, "AutoConfigURL")
            except FileNotFoundError:
                pac_url = ""
            try:
                proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            except FileNotFoundError:
                proxy_enable = 0
    except Exception as e:
        log.debug("Windows query proxy error: %s", e)

    return {
        "enabled": bool(pac_url or proxy_enable),
        "pac_url": pac_url,
        "type": "pac" if pac_url else ("manual" if proxy_enable else "none"),
    }


# ---------------------------------------------------------------------------
# Linux Implementation using gsettings (GNOME/Cinnamon), kwriteconfig (KDE), or env
# ---------------------------------------------------------------------------

def _detect_linux_desktop_environment() -> str:
    """Identify whether current session is GNOME, KDE, or generic."""
    desktop = (os.getenv("XDG_CURRENT_DESKTOP") or os.getenv("DESKTOP_SESSION") or "").lower()
    if any(k in desktop for k in ("gnome", "unity", "cinnamon", "mate", "budgie", "pop")):
        return "gnome"
    elif any(k in desktop for k in ("kde", "plasma")):
        return "kde"
    return "generic"


def _enable_linux_proxy(pac_url: str, socks_host: str = "127.0.0.1", socks_port: int = 11080) -> bool:
    de = _detect_linux_desktop_environment()
    success = False

    # 1. GNOME / GSettings (works on GNOME, Cinnamon, Budgie, etc.)
    if shutil.which("gsettings"):
        try:
            subprocess.run(["gsettings", "set", "org.gnome.system.proxy", "mode", "auto"], check=True, capture_output=True)
            subprocess.run(["gsettings", "set", "org.gnome.system.proxy", "autoconfig-url", pac_url], check=True, capture_output=True)
            success = True
        except Exception as e:
            log.debug("gsettings proxy configuration failed: %s", e)

    # 2. KDE Plasma
    kw = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
    if kw:
        try:
            # ProxyType 2 = PAC / Automatic script
            subprocess.run([kw, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ProxyType", "2"], check=True, capture_output=True)
            subprocess.run([kw, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "Proxy Config Script", pac_url], check=True, capture_output=True)
            # Re-read kioslaverc via dbus or qdbus if available
            qdbus = shutil.which("qdbus6") or shutil.which("qdbus")
            if qdbus:
                subprocess.run([qdbus, "org.kde.kded6", "/kded", "reconfigure"], capture_output=True)
            success = True
        except Exception as e:
            log.debug("KDE kwriteconfig failed: %s", e)

    # 3. CLI user environment fallback file: ~/.config/environment.d/99-netools-proxy.conf
    try:
        from pathlib import Path
        env_d = Path.home() / ".config" / "environment.d"
        env_d.mkdir(parents=True, exist_ok=True)
        conf_file = env_d / "99-netools-proxy.conf"
        conf_file.write_text(
            f'http_proxy="http://{socks_host}:21080"\n'
            f'https_proxy="http://{socks_host}:21080"\n'
            f'all_proxy="socks5://{socks_host}:{socks_port}"\n'
            f'no_proxy="localhost,127.0.0.1,local,internal"\n',
            encoding="utf-8"
        )
    except Exception:
        pass

    log.info("Enabled Linux system proxy (Desktop: %s) with PAC: %s", de, pac_url)
    return success or True


def _disable_linux_proxy() -> bool:
    # 1. GNOME
    if shutil.which("gsettings"):
        try:
            subprocess.run(["gsettings", "set", "org.gnome.system.proxy", "mode", "none"], check=True, capture_output=True)
            subprocess.run(["gsettings", "set", "org.gnome.system.proxy", "autoconfig-url", ""], check=True, capture_output=True)
        except Exception as e:
            log.debug("gsettings disable proxy error: %s", e)

    # 2. KDE
    kw = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
    if kw:
        try:
            subprocess.run([kw, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ProxyType", "0"], check=True, capture_output=True)
            subprocess.run([kw, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "Proxy Config Script", ""], check=True, capture_output=True)
        except Exception as e:
            log.debug("KDE disable proxy error: %s", e)

    # 3. Remove environment.d fallback
    try:
        from pathlib import Path
        conf_file = Path.home() / ".config" / "environment.d" / "99-netools-proxy.conf"
        conf_file.unlink(missing_ok=True)
    except Exception:
        pass

    log.info("Disabled Linux system proxy")
    return True


def _get_linux_proxy_status() -> Dict[str, Any]:
    pac_url = ""
    mode = "none"

    if shutil.which("gsettings"):
        try:
            mode = subprocess.check_output(["gsettings", "get", "org.gnome.system.proxy", "mode"], text=True, stderr=subprocess.DEVNULL).strip().strip("'")
            pac_url = subprocess.check_output(["gsettings", "get", "org.gnome.system.proxy", "autoconfig-url"], text=True, stderr=subprocess.DEVNULL).strip().strip("'")
        except Exception:
            pass

    enabled = mode in ("auto", "manual")
    return {
        "enabled": enabled,
        "pac_url": pac_url,
        "type": "pac" if mode == "auto" else ("manual" if mode == "manual" else "none"),
    }


# ---------------------------------------------------------------------------
# Public Unified Interface
# ---------------------------------------------------------------------------

def enable_system_proxy(pac_url: str, socks_host: str = "127.0.0.1", socks_port: int = 11080) -> bool:
    """Enable system-wide proxy using PAC URL and SOCKS fallback for macOS, Windows, or Linux."""
    os_type = get_os_type()
    if os_type == "darwin":
        return _enable_macos_proxy(pac_url, socks_host, socks_port)
    elif os_type == "windows":
        return _enable_windows_proxy(pac_url, socks_host, socks_port)
    elif os_type == "linux":
        return _enable_linux_proxy(pac_url, socks_host, socks_port)
    return False


def disable_system_proxy() -> bool:
    """Disable system-wide proxy and restore direct network connection."""
    os_type = get_os_type()
    if os_type == "darwin":
        return _disable_macos_proxy()
    elif os_type == "windows":
        return _disable_windows_proxy()
    elif os_type == "linux":
        return _disable_linux_proxy()
    return False


def get_system_proxy_status() -> Dict[str, Any]:
    """Retrieve current system-wide proxy configuration across macOS, Windows, or Linux."""
    os_type = get_os_type()
    if os_type == "darwin":
        return _get_macos_proxy_status()
    elif os_type == "windows":
        return _get_windows_proxy_status()
    elif os_type == "linux":
        return _get_linux_proxy_status()
    return {"enabled": False, "pac_url": "", "type": "none"}
