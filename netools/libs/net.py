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
        data, _ = sock.recvfrom(512)
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
