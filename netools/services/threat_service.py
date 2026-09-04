#!/usr/bin/env python3
"""
Threat Monitoring Service.
Provides on-demand and background network threat monitoring, alerting on ARP spoofing,
MITM attacks, and local DNS hijacking.
"""

import threading
from typing import Callable, List, Optional

from netools.libs.logger import get_logger
from netools.libs.threat_detector import NetworkThreatReport, scan_local_network_threats

log = get_logger(__name__)

_latest_report: Optional[NetworkThreatReport] = None
_monitor_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_callbacks: List[Callable[[NetworkThreatReport], None]] = []
_lock = threading.Lock()


def scan_threats_now() -> NetworkThreatReport:
    """Execute immediate network security & threat scan."""
    global _latest_report
    report = scan_local_network_threats()
    with _lock:
        _latest_report = report
    return report


def get_latest_threat_report() -> NetworkThreatReport:
    """Retrieve the most recent threat scan report or trigger a new one if not available."""
    global _latest_report
    with _lock:
        if _latest_report is not None:
            return _latest_report
    return scan_threats_now()


def register_threat_callback(callback: Callable[[NetworkThreatReport], None]) -> None:
    """Register a listener callback to receive threat alerts upon detection."""
    with _lock:
        if callback not in _callbacks:
            _callbacks.append(callback)


def unregister_threat_callback(callback: Callable[[NetworkThreatReport], None]) -> None:
    """Unregister a previously registered callback."""
    with _lock:
        if callback in _callbacks:
            _callbacks.remove(callback)


def _monitor_loop(interval_sec: float) -> None:
    log.info(f"Local Network Threat Monitoring Service started (Interval: {interval_sec}s)")
    while not _stop_event.is_set():
        try:
            report = scan_threats_now()
            if report.threat_level in ("High", "Critical", "Medium"):
                log.warning(f"Network threat alert: {report.threat_level} - {report.threats_found}")
                with _lock:
                    listeners = list(_callbacks)
                for cb in listeners:
                    try:
                        cb(report)
                    except Exception as e:
                        log.error(f"Error executing threat listener callback: {e}")
        except Exception as e:
            log.error(f"Error in threat monitor loop: {e}")

        _stop_event.wait(timeout=interval_sec)
    log.info("Local Network Threat Monitoring Service stopped.")


def start_threat_monitor(interval_sec: float = 15.0) -> bool:
    """Start background threat monitoring thread."""
    global _monitor_thread
    if _monitor_thread and _monitor_thread.is_alive():
        return True

    _stop_event.clear()
    _monitor_thread = threading.Thread(target=_monitor_loop, args=(interval_sec,), daemon=True, name="threat-monitor")
    _monitor_thread.start()
    return True


def stop_threat_monitor() -> bool:
    """Stop background threat monitoring thread."""
    global _monitor_thread
    _stop_event.set()
    if _monitor_thread:
        _monitor_thread.join(timeout=1.0)
        _monitor_thread = None
    return True
