"""
Local DoH Forwarder Service: UDP DNS -> DoH (RFC 8484) proxy on 127.0.0.1.
"""

import socketserver
import ssl
import threading
import urllib.request
from typing import Optional

from netools.config import DOH_PROXY_PORT
from netools.libs import dns_db
from netools.libs.logger import get_logger

log = get_logger(__name__)

_doh_url = ""
_active_provider: Optional[str] = None
_doh_server: Optional[socketserver.ThreadingUDPServer] = None
_doh_thread: Optional[threading.Thread] = None


class _ReusableUDPServer(socketserver.ThreadingUDPServer):
    allow_reuse_address = True
    daemon_threads = True


class _DoHHandler(socketserver.BaseRequestHandler):
    """Forward a single raw UDP DNS packet to the upstream DoH server."""

    def handle(self) -> None:
        data, sock = self.request
        resp = _forward_doh(data)
        if resp:
            sock.sendto(resp, self.client_address)


_ssl_ctx = ssl._create_unverified_context()


def _forward_doh(raw_packet: bytes, timeout: float = 5.0) -> Optional[bytes]:
    if not _doh_url:
        return None
    req = urllib.request.Request(
        _doh_url,
        data=raw_packet,
        headers={
            "Content-Type": "application/dns-message",
            "Accept": "application/dns-message",
            "User-Agent": "Netools-DoH-Forwarder/2.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as resp:
            if resp.status == 200:
                return resp.read()

    except Exception as e:
        log.warning(f"DoH forward error: {e}")
    return None


def is_doh_forwarder_running() -> bool:
    return _doh_server is not None


def get_active_provider() -> Optional[str]:
    """Provider id whose DoH endpoint the local forwarder currently targets."""
    return _active_provider if is_doh_forwarder_running() else None


def stop_doh_forwarder() -> bool:
    global _doh_server, _doh_thread, _active_provider
    if _doh_server:
        try:
            _doh_server.shutdown()
            _doh_server.server_close()
        except Exception:
            pass
        _doh_server = None
        _doh_thread = None
        _active_provider = None
        log.info("DoH forwarder stopped")
    return True


def start_doh_forwarder(provider: str = "alidns", port: int = DOH_PROXY_PORT) -> bool:
    """Start UDP->DoH forwarder on 127.0.0.1:port (background thread)."""
    global _doh_server, _doh_thread, _doh_url, _active_provider

    providers = dns_db.load_providers()
    p = providers.get(provider)
    if not p or not p.get("doh_url"):
        log.error(f"Unknown or unsupported DoH provider: {provider}")
        return False
    _doh_url = p["doh_url"]
    _active_provider = provider

    if _doh_server:
        log.info(f"DoH forwarder already running on udp://127.0.0.1:{port}")
        return True

    try:
        _doh_server = _ReusableUDPServer(("127.0.0.1", port), _DoHHandler)
    except OSError as e:
        log.error(f"Failed to bind DoH forwarder on udp://127.0.0.1:{port}: {e}")
        _doh_server = None
        return False

    _doh_thread = threading.Thread(target=_doh_server.serve_forever, daemon=True, name="doh-forwarder")
    _doh_thread.start()
    log.info(f"DoH forwarder running: udp://127.0.0.1:{port} -> {_doh_url} ({provider})")
    return True
