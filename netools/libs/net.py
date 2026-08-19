"""
Network utilities: socket testing, port checking, ping, upstream curl test, HTTP fetching.
"""

import socket
import subprocess
import urllib.request
import urllib.error
from typing import Optional, List

def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """Check if a local TCP port is listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0

def fetch_text(url: str, timeout: int = 15) -> str:
    """Fetch plain text via HTTP request."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def test_socks_upstream(port: int, test_url: str = "https://www.gstatic.com/generate_204", timeout: float = 5.0) -> bool:
    """Validate that a local SOCKS5 proxy can route traffic upstream via curl socks5h."""
    if not is_port_open(port):
        return False
    try:
        res = subprocess.run(
            [
                "curl",
                "-s",
                "-o", "/dev/null",
                "-w", "%{http_code}",
                "--proxy", f"socks5h://127.0.0.1:{port}",
                "--connect-timeout", str(int(timeout)),
                "--max-time", str(int(timeout) + 2),
                test_url
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 3
        )
        return res.stdout.strip() in ("200", "204", "301", "302")
    except Exception:
        return False

def ping_dns_udp(ip: str, domain: str = "google.com", timeout: float = 2.0) -> Optional[float]:
    """Query UDP Port 53 for latency profiling (ms)."""
    import time
    from netools.libs.dns_packet import build_dns_query_packet

    pkt = build_dns_query_packet(domain)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    t0 = time.perf_counter()
    try:
        sock.sendto(pkt, (ip, 53))
        data, _ = sock.recvfrom(512)
        lat = (time.perf_counter() - t0) * 1000.0
        return lat
    except Exception:
        return None
    finally:
        sock.close()
