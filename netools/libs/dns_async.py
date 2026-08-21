#!/usr/bin/env python3
"""
Async DNS query layer for Netools (uses aiodns/c-ares + asyncio).

Provides drop-in async equivalents of the sync query_*_dns helpers in
dns_benchmark.py, suitable for high-concurrency fan-out. On Linux the caller
can also install uvloop as the asyncio event loop for ~2x further speedup.

Usage:
    import asyncio
    from netools.libs.dns_async import query_udp_dns_async, init_async_loop

    init_async_loop()  # install uvloop on Linux, fall back to default on other OS
    lat, ips, rrsig, edns = await query_udp_dns_async("1.1.1.1", "google.com")

The benchmark modal currently uses sync queries inside a ThreadPoolExecutor,
which is fine on Python 3.12+ thanks to free-threading of sockets. This async
layer is exposed for callers that want asyncio-native concurrency.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import sys
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)

try:
    import aiodns
    _HAS_AIODNS = True
except ImportError:
    _HAS_AIODNS = False
    log.warning("aiodns not installed; async DNS unavailable, falling back to sync loop thread.")

try:
    import uvloop as _uvloop
    _HAS_UVLOOP = True
except ImportError:
    _HAS_UVLOOP = False

_loop_init_done = False


def init_async_loop() -> None:
    """Install uvloop as the asyncio event loop policy on Linux (no-op elsewhere)."""
    global _loop_init_done
    if _loop_init_done:
        return
    if sys.platform.startswith("linux") and _HAS_UVLOOP:
        try:
            asyncio.set_event_loop_policy(_uvloop.EventLoopPolicy())
        except Exception as e:
            log.debug(f"uvloop install failed: {e}")
    _loop_init_done = True


async def query_udp_dns_async(
    ip: str,
    domain: str,
    timeout: float = 2.0,
) -> Tuple[Optional[float], List[str], bool, bool]:
    """Async UDP DNS query via aiodns (c-ares).

    Returns (latency_ms, ips, dnssec, edns) — same shape as the sync version.
    Returns (None, [], False, False) on any error.
    """
    if not _HAS_AIODNS:
        # Lazy fallback: run sync query in default executor.
        loop = asyncio.get_running_loop()
        from netools.libs.dns_benchmark import query_udp_dns
        return await loop.run_in_executor(None, query_udp_dns, ip, domain, timeout)

    try:
        # Lazy import to avoid spinning up resolver on event loop closure.

        resolver = aiodns.DNSResolver(loop=asyncio.get_running_loop(), timeout=timeout)
        # aiodns can't consume our raw wireformat packet; use its resolver path
        # for parity and speed (c-ares is faster than raw + python parser).
        t0 = asyncio.get_running_loop().time()
        try:
            resp = await resolver.query(domain, "A")
            lat = (asyncio.get_running_loop().time() - t0) * 1000.0
            ips = []
            for r in resp:
                ip_str = getattr(r, "host", None)
                if not ip_str and hasattr(r, "data"):
                    # Newer aiodns returns DNSRecord namedtuples
                    ip_str = str(r.data)
                if ip_str:
                    ips.append(ip_str)
            # DNSSEC/EDNS not directly inspected here; default to False.
            return lat, ips, False, False
        except aiodns.error.DNSError as e:
            # NXDOMAIN and NODATA still resolve as errors; treat as clean with no IP.
            if e.args and e.args[0] in (4,):  # NXDOMAIN
                return None, [], False, False
            return None, [], False, False
    except (asyncio.TimeoutError, socket.gaierror, OSError) as e:
        log.debug(f"async UDP query failed: {e}")
        return None, [], False, False
    except Exception as e:
        log.debug(f"async UDP query error: {e}")
        return None, [], False, False


async def gather_with_concurrency(
    n: int,
    *coros,
) -> list:
    """Run coros with at most `n` in flight at once (back-pressure)."""
    if n <= 0:
        n = 1
    semaphore = asyncio.Semaphore(n)

    async def _wrap(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(*[_wrap(c) for c in coros], return_exceptions=False)
