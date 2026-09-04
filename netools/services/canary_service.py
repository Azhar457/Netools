"""
DNS Recursive Canary Domain service.

Detects DNS interception / "managed network" tampering by querying well-known
canary hostnames that *should* resolve to NXDOMAIN/NODATA. Any A/AAAA answer
(including 0.0.0.0 or captive-portal IPs) means the upstream resolver is
returning a forged response.

References:
- Mozilla Firefox canary: use-application-dns.net (disables DoH if intercepted)
- Apple iCloud Private Relay: mask.icloud.com, mask-h2.icloud.com,
  mask.apple-dns.net, mask-canary.icloud.com
- Custom canary domains are user-configurable via canary.json

Pure logic, GUI-agnostic, testable. Side-effect free on import.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

import dns.exception
import dns.rcode
import dns.resolver

from netools.config import CONFIGS_DIR, USER_CONFIG_DIR
from netools.libs.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Built-in canary domains (always checked unless user disables them)
# ---------------------------------------------------------------------------

# Maps internal id -> {hostname, owner, why}
BUILTIN_CANARIES: dict[str, dict[str, str]] = {
    "mozilla_firefox_doh": {
        "hostname": "use-application-dns.net",
        "owner": "Mozilla Firefox",
        "purpose": "Disable DoH when network operator forges DNS response.",
    },
    "apple_private_relay_main": {
        "hostname": "mask.icloud.com",
        "owner": "Apple iCloud Private Relay",
        "purpose": "Detect resolver blocking iCloud Private Relay.",
    },
    "apple_private_relay_v4": {
        "hostname": "mask-h2.icloud.com",
        "owner": "Apple iCloud Private Relay",
        "purpose": "HTTP/2 mask endpoint.",
    },
    "apple_private_relay_apple": {
        "hostname": "mask.apple-dns.net",
        "owner": "Apple iCloud Private Relay",
        "purpose": "Apple-DNS canary endpoint.",
    },
    "apple_private_relay_canary": {
        "hostname": "mask-canary.icloud.com",
        "owner": "Apple iCloud Private Relay",
        "purpose": "Graceful-failure canary for Private Relay.",
    },
}

# Pre-check hostnames that should always be resolvable to a real A/AAAA record.
# If these also fail, the network is offline / has no DNS at all -> suppress
# canary results as false positives.
PRECHECK_HOSTNAMES: tuple[str, ...] = (
    "firefox.com",
    "mozilla.org",
)

# ---------------------------------------------------------------------------
# Status / result data classes
# ---------------------------------------------------------------------------

STATUS_CLEAN = "clean"  # NXDOMAIN or NODATA -> not intercepted
STATUS_INTERCEPTED = "intercepted"  # Got A/AAAA / SOA / CNAME -> forged
STATUS_TIMEOUT = "timeout"  # No response within timeout
STATUS_SERVFAIL = "servfail"  # Upstream reported SERVFAIL
STATUS_OFFLINE = "offline"  # Pre-check failed -> network likely down

VERDICT_CLEAN = "clean"  # All domains clean across all resolvers
VERDICT_INTERCEPTED = "intercepted"  # At least one domain intercepted
VERDICT_INDETERMINATE = "indeterminate"  # Offline / timeout / mixed errors
VERDICT_PARTIAL = "partial"  # Some clean, some intercepted (rare)


@dataclass
class CanaryProbe:
    """Single (hostname x resolver) probe result."""

    hostname: str
    resolver: str  # "system", "custom:1.1.1.1", "custom:9.9.9.9", ...
    status: str  # one of STATUS_*
    rcode: str = ""  # raw DNS RCODE if available
    latency_ms: float = 0.0
    answer_summary: str = ""  # e.g. "NXDOMAIN", "A=1.2.3.4", "SOA=ns1..."

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CanaryRunResult:
    """Result of one full canary sweep."""

    timestamp: float
    precheck_ok: bool
    probes: list[CanaryProbe] = field(default_factory=list)
    verdict: str = VERDICT_INDETERMINATE
    intercepted_domains: list[str] = field(default_factory=list)
    clean_domains: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "precheck_ok": self.precheck_ok,
            "verdict": self.verdict,
            "intercepted_domains": self.intercepted_domains,
            "clean_domains": self.clean_domains,
            "error": self.error,
            "probes": [p.to_dict() for p in self.probes],
        }


# ---------------------------------------------------------------------------
# Custom canary domains persistence
# ---------------------------------------------------------------------------

CANARY_CONFIG_FILE = USER_CONFIG_DIR / "canary.json"
DEFAULT_CUSTOM_CANARIES: list[str] = []  # users can add their own


_in_memory_custom_canaries: Optional[list[str]] = None


def _load_custom_canaries() -> list[str]:
    global _in_memory_custom_canaries
    if _in_memory_custom_canaries is not None:
        return list(_in_memory_custom_canaries)

    for cfg_path in (CANARY_CONFIG_FILE, CONFIGS_DIR / "canary.json"):
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                canaries = data.get("custom_canaries", [])
                if isinstance(canaries, list):
                    _in_memory_custom_canaries = [str(c).strip() for c in canaries if str(c).strip()]
                    return list(_in_memory_custom_canaries)
            except Exception as e:
                log.warning(f"{cfg_path} unreadable: {e}")

    _in_memory_custom_canaries = list(DEFAULT_CUSTOM_CANARIES)
    return list(_in_memory_custom_canaries)


def _save_custom_canaries(canaries: list[str]) -> None:
    global _in_memory_custom_canaries
    _in_memory_custom_canaries = list(canaries)
    saved = False
    for cfg_path in (CANARY_CONFIG_FILE, CONFIGS_DIR / "canary.json"):
        try:
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(
                json.dumps({"custom_canaries": canaries}, indent=2),
                encoding="utf-8",
            )
            saved = True
            break
        except Exception:
            pass
    if not saved:
        log.debug("Canary config stored in-memory")


def get_all_canary_hostnames(include_custom: bool = True) -> list[dict[str, str]]:
    """Return all canary hostnames as {id, hostname, owner, purpose} dicts."""
    out: list[dict[str, str]] = []
    for cid, info in BUILTIN_CANARIES.items():
        out.append({"id": cid, **info, "kind": "builtin"})
    if include_custom:
        for hostname in _load_custom_canaries():
            out.append(
                {
                    "id": f"custom:{hostname}",
                    "hostname": hostname,
                    "owner": "Custom",
                    "purpose": "User-defined canary domain.",
                    "kind": "custom",
                }
            )
    return out


# ---------------------------------------------------------------------------
# Resolver factory
# ---------------------------------------------------------------------------


def _make_resolver(target: str, timeout: float) -> dns.resolver.Resolver:
    """Build a dns.resolver.Resolver for `target`.

    target == "system" -> use OS resolver (/etc/resolv.conf or active interface DNS)
    target == "custom:IP" or "custom:IP#port" -> that specific upstream
    """
    if target == "system":
        try:
            r = dns.resolver.Resolver(configure=True)
        except Exception:
            r = dns.resolver.Resolver(configure=False)

        r.timeout = timeout
        r.lifetime = timeout

        if not r.nameservers:
            try:
                from netools.adapters import platform_dns

                ifaces = platform_dns.get_network_interfaces()
                dev = ifaces[0]["device"] if ifaces else "default"
                active_dns = platform_dns.get_interface_dns(dev)
                if active_dns:
                    r.nameservers = active_dns
            except Exception:
                pass

        if not r.nameservers:
            r.nameservers = ["1.1.1.1", "8.8.8.8"]
        return r

    r = dns.resolver.Resolver(configure=False)
    r.timeout = timeout
    r.lifetime = timeout
    addr = target.split(":", 1)[1]  # strip "custom:" prefix
    if "#" in addr:
        host, port_str = addr.split("#", 1)
        r.nameservers = [host]
        r.nameserver_ports = {host: int(port_str)}
    else:
        r.nameservers = [addr]
    return r


def _resolver_label(target: str) -> str:
    return target  # already human-friendly ("system", "custom:1.1.1.1")


# ---------------------------------------------------------------------------
# Single probe
# ---------------------------------------------------------------------------


def _probe(hostname: str, resolver_target: str, timeout: float) -> CanaryProbe:
    label = _resolver_label(resolver_target)
    started = time.perf_counter()
    # TLD canaries (".ai") are probed via a guaranteed-nonexistent subdomain:
    # random.<tld> must NXDOMAIN; any answer means the resolver forges wildcards.
    probe_host = (
        f"canary-probe-{int(time.time() * 1000):x}.{hostname.lstrip('.')}" if hostname.startswith(".") else hostname
    )
    try:
        res = _make_resolver(resolver_target, timeout)
        # Use UDP A first; if it answers, intercepted. Empty A + AAAA NXDOMAIN = clean.
        try:
            ans = res.resolve(probe_host, "A", raise_on_no_answer=False)
            rcode = ans.response.rcode() if ans.response else None
            if ans.rrset is not None and len(ans.rrset) > 0:
                sample = ", ".join(str(rdata) for rdata in list(ans.rrset)[:3])
                return CanaryProbe(
                    hostname=hostname,
                    resolver=label,
                    status=STATUS_INTERCEPTED,
                    rcode=str(rcode or "NOERROR"),
                    latency_ms=(time.perf_counter() - started) * 1000,
                    answer_summary=f"A={sample}",
                )
            # No A record -> check rcode
            if rcode == dns.rcode.NXDOMAIN:
                return CanaryProbe(
                    hostname, label, STATUS_CLEAN, "NXDOMAIN", (time.perf_counter() - started) * 1000, "NXDOMAIN"
                )
            if rcode == dns.rcode.NOERROR:
                return CanaryProbe(
                    hostname, label, STATUS_CLEAN, "NOERROR", (time.perf_counter() - started) * 1000, "NODATA"
                )
            return CanaryProbe(
                hostname, label, STATUS_SERVFAIL, str(rcode), (time.perf_counter() - started) * 1000, f"RCODE={rcode}"
            )
        except dns.resolver.NXDOMAIN:
            return CanaryProbe(
                hostname, label, STATUS_CLEAN, "NXDOMAIN", (time.perf_counter() - started) * 1000, "NXDOMAIN"
            )
        except dns.resolver.NoNameservers:
            return CanaryProbe(
                hostname,
                label,
                STATUS_SERVFAIL,
                "NoNameservers",
                (time.perf_counter() - started) * 1000,
                "NoNameservers",
            )
        except (dns.resolver.LifetimeTimeout, dns.exception.Timeout):
            return CanaryProbe(
                hostname, label, STATUS_TIMEOUT, "timeout", (time.perf_counter() - started) * 1000, "timeout"
            )
    except Exception as e:
        return CanaryProbe(
            hostname, label, STATUS_TIMEOUT, "exception", (time.perf_counter() - started) * 1000, str(e)[:80]
        )


def _probe_precheck(resolver_target: str, timeout: float) -> bool:
    """Returns True if at least one pre-check hostname resolved to a real A record."""
    try:
        res = _make_resolver(resolver_target, timeout)
        for host in PRECHECK_HOSTNAMES:
            try:
                ans = res.resolve(host, "A", raise_on_no_answer=False)
                if ans.rrset is not None and len(ans.rrset) > 0:
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Public API: full canary sweep
# ---------------------------------------------------------------------------


def run_canary_sweep(
    resolvers: Optional[list[str]] = None,
    timeout: float = 2.0,
    include_custom: bool = True,
) -> CanaryRunResult:
    """Run all canary probes across all resolvers in parallel.

    resolvers: list of resolver targets. Defaults to ["system"] + any user
               configured custom_resolver. Each item is "system" or "custom:IP[#PORT]".
    """
    if resolvers is None:
        resolvers = ["system"]
        # Optionally add user's custom upstream if they set one.
        try:
            from netools.config import _user_cfg  # type: ignore

            custom = _user_cfg.get("custom_dns_upstream", "").strip()
            if custom:
                resolvers.append(f"custom:{custom}")
        except Exception:
            pass

    timestamp = time.time()
    hostnames = [c["hostname"] for c in get_all_canary_hostnames(include_custom)]

    # Pre-check each resolver: if pre-check fails, that resolver's results are
    # suppressed (mark as offline) to avoid false positives.
    precheck_results: dict[str, bool] = {}
    for r in resolvers:
        precheck_results[r] = _probe_precheck(r, timeout)

    # Fan out probes across thread pool
    probes: list[CanaryProbe] = []
    tasks: list[tuple[str, str]] = [(h, r) for h in hostnames for r in resolvers]
    results: list[CanaryProbe] = [None] * len(tasks)  # type: ignore
    threads: list[threading.Thread] = []
    for i, (h, r) in enumerate(tasks):
        t = threading.Thread(
            target=lambda idx=i, host=h, res=r: results.__setitem__(
                idx,
                _probe(host, res, timeout)
                if precheck_results[res]
                else CanaryProbe(
                    hostname=host,
                    resolver=res,
                    status=STATUS_OFFLINE,
                    answer_summary="precheck-failed",
                ),
            ),
            daemon=True,
        )
        threads.append(t)
        t.start()
    for t in threads:
        t.join(timeout=timeout + 1.0)
    probes = [p for p in results if p is not None]

    # Aggregate verdict
    intercepted = sorted({p.hostname for p in probes if p.status == STATUS_INTERCEPTED})
    clean = sorted({p.hostname for p in probes if p.status == STATUS_CLEAN and precheck_results[p.resolver]})
    any_offline = any(not ok for ok in precheck_results.values())

    if any_offline and not intercepted:
        verdict = VERDICT_INDETERMINATE
    elif intercepted and clean:
        verdict = VERDICT_PARTIAL
    elif intercepted:
        verdict = VERDICT_INTERCEPTED
    elif clean:
        verdict = VERDICT_CLEAN
    else:
        verdict = VERDICT_INDETERMINATE

    return CanaryRunResult(
        timestamp=timestamp,
        precheck_ok=any(precheck_results.values()),
        probes=probes,
        verdict=verdict,
        intercepted_domains=intercepted,
        clean_domains=clean,
    )


# ---------------------------------------------------------------------------
# Convenience: run in background thread (UI-friendly)
# ---------------------------------------------------------------------------


def run_canary_sweep_async(
    on_done,  # callable(CanaryRunResult)
    resolvers: Optional[list[str]] = None,
    timeout: float = 2.0,
):
    """Fire-and-forget background sweep. Calls on_done(result) on completion."""

    def _runner():
        try:
            res = run_canary_sweep(resolvers=resolvers, timeout=timeout)
        except Exception as e:
            res = CanaryRunResult(timestamp=time.time(), precheck_ok=False, error=str(e))
        try:
            on_done(res)
        except Exception:
            log.exception("canary on_done callback failed")

    threading.Thread(target=_runner, daemon=True, name="canary-sweep").start()


# ---------------------------------------------------------------------------
# Custom canary helpers (used by Preferences UI later)
# ---------------------------------------------------------------------------


def add_custom_canary(hostname: str) -> bool:
    hostname = hostname.strip().lower().rstrip(".")
    if not hostname:
        return False
    # Accept either a full domain (use-application-dns.net) or a bare TLD
    # (".ai" / "ai") used as a canary suffix probe.
    is_tld = hostname.startswith(".") or ("." not in hostname)
    if is_tld:
        tld = hostname if hostname.startswith(".") else f".{hostname}"
        if not all(c.isalnum() for c in tld[1:]) or len(tld) < 3:
            return False
        hostname = tld
    elif not all(c.isalnum() or c in ".-" for c in hostname):
        return False
    existing = _load_custom_canaries()
    if hostname not in existing:
        existing.append(hostname)
        _save_custom_canaries(existing)
    return True


def remove_custom_canary(hostname: str) -> bool:
    hostname = hostname.strip().lower().rstrip(".")
    existing = _load_custom_canaries()
    variants = {hostname, hostname.lstrip(".")}
    hits = [h for h in existing if h in variants or h.lstrip(".") in variants]
    if not hits:
        return False
    for h in hits:
        existing.remove(h)
    _save_custom_canaries(existing)
    return True
