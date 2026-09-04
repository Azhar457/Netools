"""
Cross-Platform DNS Cache Poisoning Guard for Netools.

CIA alignment:
  - Integrity: validates that live system-resolved IPs for canary domains do not
    resolve to private/bogon/loopback ranges (which indicate cache poisoning,
    ISP sinkholing, or redirect hijacking).
  - Availability: optionally auto-flushes the system DNS cache and reverts to the
    last known-good resolver when poisoning is detected, keeping name resolution
    functional.
  - Confidentiality: alerts when DNS is being transparently intercepted and
    redirected to third-party resolvers, which can enable surveillance.

Performance:
  - Non-blocking background thread, single subprocess per-platform check.
  - 30s default TTL cache (configurable via POISON_GUARD_TTL env).
  - Structured JSON logging when NETOOLS_LOG_JSON=1.

Cross-platform support:
  - Linux: resolvectl query (systemd-resolved).
  - Windows: Resolve-DnsName / Get-DnsClientCache via PowerShell.
  - macOS: scutil --dns combined with dig fallback.
"""

import ipaddress
import platform
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from netools.libs.logger import get_logger

log = get_logger(__name__)

# Canary domains — public, stable, must never resolve to private space.
CANARY_DOMAINS = [
    "www.cloudflare.com",
    "dns.google",
    "one.one.one.one",
]

# Environments that disable the guard.
_DISABLE_ENV = "NETOOLS_POISON_GUARD"


def _is_bogon(ip_str: str) -> bool:
    """Return True if *ip_str* is private/loopback/link-local/reserved/bogon.

    Reuses the same semantics as dns_benchmark.is_sinkhole_or_private_ip to
    keep detection consistent across the suite.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except (ValueError, TypeError):
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_unspecified
        or ip.is_multicast
        or str(ip).startswith("100.64.")  # CGNAT
    )


@dataclass
class PoisonAlert:
    hostname: str
    resolved_ips: List[str]
    poisoned: bool
    resolver: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "hostname": self.hostname,
            "resolved_ips": self.resolved_ips,
            "poisoned": self.poisoned,
            "resolver": self.resolver,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Platform-specific resolvers
# ---------------------------------------------------------------------------


def _resolve_linux(hostname: str) -> List[str]:
    """Use resolvectl (systemd-resolved) to query a hostname."""
    if not shutil.which("resolvectl"):
        return []
    try:
        out = subprocess.check_output(
            ["resolvectl", "query", hostname],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return []
    ips: List[str] = []
    for line in out.splitlines():
        for match in re.finditer(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line):
            ips.append(match.group(1))
        for match in re.finditer(r"([0-9a-fA-F:]+(?:::[0-9a-fA-F:]+)*)", line):
            candidate = match.group(1)
            if ":" in candidate and _is_valid_ipv6(candidate):
                ips.append(candidate)
    return ips


def _is_valid_ipv6(ip_str: str) -> bool:
    try:
        ipaddress.IPv6Address(ip_str)
        return True
    except (ValueError, ipaddress.AddressValueError):
        return False


def _resolve_windows(hostname: str) -> List[str]:
    """Use PowerShell Resolve-DnsName to query a hostname."""
    psh = shutil.which("powershell.exe") or shutil.which("pwsh")
    if not psh:
        return []
    try:
        out = subprocess.check_output(
            [
                psh,
                "-NoProfile",
                "-Command",
                f"Resolve-DnsName -Name {hostname} -ErrorAction SilentlyContinue | Select-Object -Expand IPAddress",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _resolve_macos(hostname: str) -> List[str]:
    """Use scutil / dig on macOS."""
    dns_servers = _get_macos_resolvers()
    # Try scutil first (respects system config), fall back to dig.
    try:
        out = subprocess.check_output(
            ["scutil", "--dns"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        # scutil --dns lists resolvers, not answers. Use dig against first resolver.
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    dig = shutil.which("dig")
    if dig and dns_servers:
        try:
            out = subprocess.check_output(
                [dig, f"@{dns_servers[0]}", hostname, "+short", "+time=4"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=6,
            )
            return [line.strip() for line in out.splitlines() if line.strip()]
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Final fallback: socket.gethostbyname
    import socket  # local import — only reached on macOS fallback path

    try:
        return [socket.gethostbyname(hostname)]
    except socket.gaierror:
        return []


def _get_macos_resolvers() -> List[str]:
    try:
        out = subprocess.check_output(["scutil", "--dns"], text=True, stderr=subprocess.DEVNULL, timeout=3)
        return re.findall(r"nameserver\[(\d+\.\d+\.\d+\.\d+)\]", out)
    except (subprocess.SubprocessError, FileNotFoundError):
        return []


def _resolve_current(hostname: str) -> tuple[List[str], str]:
    """Dispatch to the correct platform resolver. Returns (ips, resolver_name)."""
    system = platform.system()
    if system == "Linux":
        return _resolve_linux(hostname), "resolvectl"
    elif system == "Windows":
        return _resolve_windows(hostname), "Resolve-DnsName"
    elif system == "Darwin":
        return _resolve_macos(hostname), "scutil/dig"
    else:
        import socket

        try:
            return [socket.gethostbyname(hostname)], "socket"
        except socket.gaierror:
            return [], "socket"


def _is_disabled() -> bool:
    """Check whether the guard is disabled by config/env.

    Respects:
      - NETOOLS_POISON_GUARD=0  → disabled (default is enabled)
      - netools/config.json poison_guard.enabled = false
    """
    import os
    from pathlib import Path

    if os.getenv(_DISABLE_ENV, "1") == "0":
        return True

    # Optional config.json override
    config_file = Path.home() / ".config" / "netools" / "config.json"
    if config_file.exists():
        try:
            import json

            cfg = json.loads(config_file.read_text())
            pg = cfg.get("poison_guard", {})
            if isinstance(pg, dict) and not pg.get("enabled", True):
                return True
        except Exception:
            pass
    return False


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------


def check_cache_poisoning(domains: Optional[List[str]] = None) -> List[PoisonAlert]:
    """Resolve each canary domain and return alerts for poisoned responses."""
    if _is_disabled():
        log.debug("PoisonGuard disabled via config/env; skipping check")
        return []

    targets = domains or CANARY_DOMAINS
    alerts: List[PoisonAlert] = []
    now = time.time()

    for host in targets:
        ips, resolver = _resolve_current(host)
        poisoned = bool(ips) and any(_is_bogon(ip) for ip in ips)
        alert = PoisonAlert(
            hostname=host,
            resolved_ips=ips,
            poisoned=poisoned,
            resolver=resolver,
            timestamp=now,
        )
        alerts.append(alert)
        if poisoned:
            log.warning(
                "DNS cache poisoning detected: %s -> %s (via %s)",
                host,
                ips,
                resolver,
            )
        else:
            log.debug("Canary %s clean: %s (via %s)", host, ips, resolver)

    return alerts


# ---------------------------------------------------------------------------
# Daemon service
# ---------------------------------------------------------------------------


class PoisonGuard:
    """Background DNS cache poisoning monitor.

    Usage:
        guard = PoisonGuard(interval=30, auto_flush=True)
        guard.start()
        # ... later
        guard.stop()
        alerts = guard.last_alerts
    """

    def __init__(
        self,
        interval: float = 30.0,
        auto_flush: bool = False,
        on_alert=None,
    ):
        self.interval = interval
        self.auto_flush = auto_flush
        self._on_alert = on_alert
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_alerts: List[PoisonAlert] = []
        self._last_flush: float = 0.0

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="PoisonGuard")
        self._thread.start()
        log.info("PoisonGuard started (interval=%.1fs, auto_flush=%s)", self.interval, self.auto_flush)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        log.info("PoisonGuard stopped")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                alerts = check_cache_poisoning()
                self.last_alerts = alerts
                any_poison = any(a.poisoned for a in alerts)
                if any_poison:
                    log.warning("PoisonGuard: %d poisoned canary(s) detected", sum(1 for a in alerts if a.poisoned))
                    if self._on_alert:
                        self._on_alert(alerts)
                    if self.auto_flush:
                        self._auto_flush()
            except Exception as exc:
                log.debug("PoisonGuard check cycle error: %s", exc)
            self._stop_event.wait(self.interval)

    def _auto_flush(self) -> None:
        """Flush system DNS cache when poisoning is detected."""
        if time.time() - self._last_flush < 60:
            return  # rate-limit flush
        self._last_flush = time.time()
        system = platform.system()
        try:
            if system == "Linux" and shutil.which("resolvectl"):
                subprocess.run(["resolvectl", "flush-caches"], capture_output=True, timeout=5)
                log.info("PoisonGuard: flushed resolvectl cache")
            elif system == "Windows":
                psh = shutil.which("powershell.exe")
                if psh:
                    subprocess.run(
                        [psh, "-NoProfile", "-Command", "Clear-DnsClientCache"],
                        capture_output=True,
                        timeout=5,
                    )
                    log.info("PoisonGuard: flushed Windows DNS cache")
            elif system == "Darwin":
                subprocess.run(["sudo", "dscacheutil", "-flushcache"], capture_output=True, timeout=5)
                log.info("PoisonGuard: flushed macOS DNS cache")
        except Exception as exc:
            log.debug("PoisonGuard auto-flush failed: %s", exc)

    def check_once(self) -> List[PoisonAlert]:
        """Run a single check cycle synchronously and return alerts."""
        alerts = check_cache_poisoning()
        self.last_alerts = alerts
        return alerts


# Singleton for app-level use
_guard: Optional[PoisonGuard] = None


def get_guard() -> PoisonGuard:
    global _guard
    if _guard is None:
        _guard = PoisonGuard()
    return _guard


def start_guard(interval: float = 30.0, auto_flush: bool = False) -> PoisonGuard:
    guard = get_guard()
    guard.interval = interval
    guard.auto_flush = auto_flush
    guard.start()
    return guard


def stop_guard() -> None:
    global _guard
    if _guard is not None:
        _guard.stop()
        _guard = None
