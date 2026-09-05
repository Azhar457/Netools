"""
Network utilities: socket testing, port checking, ping, upstream curl test, HTTP fetching.
"""

import shutil
import socket
import ssl
import struct
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """Check if a local TCP port is listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def _socks5_connect(proxy_port: int, host: str, port: int, timeout: float = 5.0) -> socket.socket:
    """Open a SOCKS5 CONNECT tunnel via 127.0.0.1:proxy_port to host:port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(("127.0.0.1", proxy_port))
    s.sendall(b"\x05\x01\x00")  # version, 1 method, no-auth
    if s.recv(2)[1] == 0xFF:
        raise ConnectionError("SOCKS5 no acceptable auth method")
    host_b = host.encode("ascii")
    s.sendall(b"\x05\x01\x00\x03" + bytes([len(host_b)]) + host_b + struct.pack(">H", port))
    resp = s.recv(4)
    if len(resp) < 4 or resp[1] != 0:
        raise ConnectionError("SOCKS5 CONNECT failed")
    atyp = resp[3]
    if atyp == 1:
        s.recv(4)
        s.recv(2)
    elif atyp == 3:
        s.recv(1 + s.recv(1)[0] + 2)
    elif atyp == 4:
        s.recv(16 + 2)
    return s


def probe_socks_upstream_python(
    port: int, test_url: str = "https://www.gstatic.com/generate_204", timeout: float = 5.0
) -> bool:
    """Pure-Python SOCKS5h upstream probe (no curl): CONNECT then HTTPS GET."""
    if not is_port_open(port):
        return False
    parsed = urllib.parse.urlparse(test_url)
    host = parsed.hostname
    if not host:
        return False
    dport = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    s = None
    tls = None
    try:
        s = _socks5_connect(port, host, dport, timeout)
        if parsed.scheme == "https":
            ctx = ssl.create_default_context()
            tls = ctx.wrap_socket(s, server_hostname=host)
            sock = tls
        else:
            sock = s
        sock.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        status = data.split(b"\r\n", 1)[0].split(b" ", 2)[1].decode(errors="ignore")
        return status in ("200", "204", "301", "302")
    except Exception:
        return False
    finally:
        if tls:
            try:
                tls.close()
            except Exception:
                pass
        elif s:
            try:
                s.close()
            except Exception:
                pass


def probe_socks_upstream(
    port: int, test_url: str = "https://www.gstatic.com/generate_204", timeout: float = 5.0
) -> bool:
    """Validate that a local SOCKS5 proxy can route traffic upstream via curl socks5h (pure-Python fallback)."""
    if not is_port_open(port, timeout=0.1):
        return False
    if shutil.which("curl") is None:
        return probe_socks_upstream_python(port, test_url=test_url, timeout=timeout)
    try:
        res = subprocess.run(
            [
                "curl",
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "--proxy",
                f"socks5h://127.0.0.1:{port}",
                "--connect-timeout",
                str(int(timeout)),
                "--max-time",
                str(int(timeout) + 2),
                test_url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 3,
        )
        return res.stdout.strip() in ("200", "204", "301", "302")
    except Exception:
        return False


def check_ipv6_connectivity(timeout: float = 1.2) -> bool:
    """Check if the local network adapter and ISP have an active, routable IPv6 connection."""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.connect(("2606:4700:4700::1111", 53))
        return True
    except Exception:
        return False
    finally:
        if sock:
            sock.close()


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 3.0, interval: float = 0.1) -> bool:
    """Poll until a TCP port is listening or timeout expires."""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_port_open(port, host, timeout=0.3):
            return True
        time.sleep(interval)
    return False


def fetch_text(url: str, timeout: float = 15.0) -> str:
    """Fetch plain text via HTTP request."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def ping_dns_udp(ip: str, domain: str = "google.com", timeout: float = 2.0) -> Optional[float]:
    """Query UDP Port 53 for latency profiling (ms) supporting IPv4 and IPv6."""
    import time

    from netools.libs.dns_packet import build_dns_query_packet

    pkt = build_dns_query_packet(domain)
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    t0 = time.perf_counter()
    try:
        sock.sendto(pkt, (ip, 53))
        _data, _ = sock.recvfrom(512)
        lat = (time.perf_counter() - t0) * 1000.0
        return lat
    except Exception:
        return None
    finally:
        sock.close()


def ping_ip(ip: str, count: int = 1, timeout: float = 1.5) -> Optional[float]:
    """
    Measure ping latency (ms) to an IP address.
    Tries standard ICMP ping first, and falls back to UDP DNS port 53 probe if ICMP is filtered.
    """
    import time

    from netools.libs.env import get_os_type

    os_t = get_os_type()

    if not ip or ip.strip() == "":
        return None

    ip = ip.strip()
    try:
        if os_t == "windows":
            cmd = ["ping", "-n", str(count), "-w", str(int(timeout * 1000)), ip]
        elif os_t == "darwin":
            cmd = ["ping", "-c", str(count), "-W", str(int(timeout * 1000)), ip]
        else:
            cmd = ["ping", "-c", str(count), "-W", str(max(1, int(timeout))), ip]

        t0 = time.perf_counter()
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1.0)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if "time=" in line:
                    parts = line.split("time=")
                    if len(parts) > 1:
                        ms_str = parts[1].split()[0].replace("ms", "").strip()
                        return float(ms_str)
                elif "Average =" in line or "avg" in line:
                    import re

                    m = re.search(r"(\d+(\.\d+)?)ms", line)
                    if m:
                        return float(m.group(1))
            return (time.perf_counter() - t0) * 1000.0
    except Exception:
        pass

    # Fallback to UDP port 53 probe
    return ping_dns_udp(ip, timeout=timeout)


def measure_bandwidth_mbps(
    host: str = "127.0.0.1",
    port: int = 80,
    timeout_s: float = 3.0,
    max_bytes: int = 256 * 1024,
) -> Optional[float]:
    """Estimate a TCP peer's bandwidth by reading up to max_bytes of an HTTP 204 response.

    Returns Mbps (float) or None on any failure. Used for proxy pool ranking,
    not for benchmarking; precision is intentionally loose (~0.5Mbps).

    Note: this is HEAD-equivalent, no app-level payload. The 256KB cap keeps
    health-check traffic under ~0.5MB per probe * 20 instances = 10MB/min.
    """
    import socket
    import time

    if timeout_s <= 0:
        return None

    sock = None
    try:
        sock = socket.create_connection((host, port), timeout=timeout_s)
        sock.sendall(
            b"GET /generate_204 HTTP/1.1\r\n"
            b"Host: speed.cloudflare.com\r\n"
            b"Connection: close\r\n\r\n"
        )
        t0 = time.perf_counter()
        received = 0
        while received < max_bytes:
            chunk = sock.recv(min(65536, max_bytes - received))
            if not chunk:
                break
            received += len(chunk)
        dt = time.perf_counter() - t0
        if dt <= 0 or received == 0:
            return None
        # bits / seconds -> megabits / second
        return (received * 8) / (dt * 1_000_000)
    except Exception:
        return None
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
