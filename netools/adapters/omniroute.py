from netools.libs.logger import get_logger

log = get_logger(__name__)

"""
OmniRoute AI Gateway REST API Adapter (Proxy & DNS Acceleration Support).
"""

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from netools.config import OMNIROUTE_TOKEN, OMNIROUTE_URL
from netools.middlewares.backend_guard import safe_backend_call

_CURRENT_URL = OMNIROUTE_URL
_CURRENT_TOKEN = OMNIROUTE_TOKEN
_HEALTH_TTL = 3.0
_health_cache: Dict[str, Any] = {"val": None, "ts": 0.0}


def set_credentials(url: Optional[str] = None, token: Optional[str] = None) -> None:
    """Dynamically update OmniRoute API endpoint and authentication token."""
    global _CURRENT_URL, _CURRENT_TOKEN
    if url is not None:
        _CURRENT_URL = url.rstrip("/")
    if token is not None:
        _CURRENT_TOKEN = token


def api_request(
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
    timeout: float = 5.0,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """Send authenticated HTTP request to OmniRoute REST API with retry on transient network error."""
    global _CURRENT_TOKEN
    url = f"{_CURRENT_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if _CURRENT_TOKEN:
        headers["Authorization"] = f"Bearer {_CURRENT_TOKEN}"

    last_err = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(0.3 * (2**attempt))

    return {"error": str(last_err)}


@safe_backend_call(fallback_return=False)
def is_healthy() -> bool:
    """Check if OmniRoute is currently alive and reachable (cached for _HEALTH_TTL seconds)."""
    now = time.monotonic()
    if _health_cache["val"] is not None and (now - _health_cache["ts"]) < _HEALTH_TTL:
        return _health_cache["val"]

    # Check TCP socket first
    healthy = False
    try:
        url_part = _CURRENT_URL.replace("http://", "").replace("https://", "").split("/")[0]
        host, port_str = url_part.split(":") if ":" in url_part else (url_part, "20128")
        with socket.create_connection((host, int(port_str)), timeout=0.6):
            healthy = True
    except Exception:
        healthy = False

    if not healthy:
        res = api_request("GET", "/api/providers")
        healthy = "error" not in res or "AUTH_001" in str(res)

    _health_cache["val"] = healthy
    _health_cache["ts"] = now
    return healthy


@safe_backend_call(fallback_return=[])
def get_connections() -> List[Dict[str, Any]]:
    """Retrieve all provider connections from OmniRoute with SQLite fallback."""
    res = api_request("GET", "/api/providers")
    conns = res.get("connections", [])
    if isinstance(conns, list) and len(conns) > 0:
        return conns

    # Fallback to local SQLite read if server requires dashboard session login
    try:
        import sqlite3

        from netools.services.omniroute_bridge import _DEFAULT_DB_PATH

        if _DEFAULT_DB_PATH.exists():
            with sqlite3.connect(_DEFAULT_DB_PATH) as db:
                db.row_factory = sqlite3.Row
                rows = db.execute(
                    "SELECT id, name, provider, is_active, test_status, proxy_enabled, provider_specific_data, auth_type FROM provider_connections ORDER BY created_at DESC"
                ).fetchall()
                parsed = []
                for r in rows:
                    psd = {}
                    if r["provider_specific_data"]:
                        try:
                            psd = json.loads(r["provider_specific_data"])
                        except Exception:
                            pass
                    proxy_url = psd.get("connectionProxyUrl") or ""
                    proxy_enabled = bool(psd.get("connectionProxyEnabled") or (r["proxy_enabled"] and proxy_url))
                    parsed.append(
                        {
                            "id": r["id"],
                            "name": r["name"] or r["provider"],
                            "provider": r["provider"],
                            "isActive": bool(r["is_active"]),
                            "testStatus": r["test_status"],
                            "connectionProxyUrl": proxy_url,
                            "connectionProxyEnabled": proxy_enabled,
                            "authType": r["auth_type"],
                        }
                    )
                return parsed
    except Exception:
        pass

    return []


@safe_backend_call(fallback_return={})
def get_existing_pools() -> Dict[str, str]:
    """Retrieve existing OmniRoute proxy pools: {name: id}."""
    res = api_request("GET", "/api/settings/proxies")
    proxies = res.get("proxies", res.get("items", []))
    if isinstance(proxies, list) and len(proxies) > 0:
        return {p.get("name", p.get("id", "")): p.get("id", "") for p in proxies if isinstance(p, dict)}

    # Fallback to local SQLite read if server requires dashboard session login
    try:
        import sqlite3

        from netools.services.omniroute_bridge import _DEFAULT_DB_PATH

        if _DEFAULT_DB_PATH.exists():
            with sqlite3.connect(_DEFAULT_DB_PATH) as db:
                db.row_factory = sqlite3.Row
                rows = db.execute("SELECT id, name FROM proxy_registry").fetchall()
                return {r["name"]: r["id"] for r in rows if r["name"]}
    except Exception:
        pass

    return {}


@safe_backend_call(fallback_return=None)
def assign_proxy_to_connection(conn_id: str, proxy_url: str) -> Optional[Dict[str, Any]]:
    """Assign a proxy URL to an OmniRoute provider connection."""
    res = api_request(
        "PUT",
        f"/api/providers/{conn_id}",
        {
            "connectionProxyEnabled": True,
            "connectionProxyUrl": proxy_url,
            "connectionNoProxy": "localhost,127.0.0.1",
        },
    )
    if "connection" in res:
        return res.get("connection")

    # Fallback: direct SQLite update
    try:
        import sqlite3

        from netools.services.omniroute_bridge import _DEFAULT_DB_PATH

        if _DEFAULT_DB_PATH.exists():
            with sqlite3.connect(_DEFAULT_DB_PATH) as db:
                row = db.execute(
                    "SELECT provider_specific_data FROM provider_connections WHERE id = ?", (conn_id,)
                ).fetchone()
                psd = {}
                if row and row[0]:
                    try:
                        psd = json.loads(row[0])
                    except Exception:
                        pass
                psd["connectionProxyEnabled"] = True
                psd["connectionProxyUrl"] = proxy_url
                psd["connectionNoProxy"] = "localhost,127.0.0.1"
                db.execute(
                    "UPDATE provider_connections SET proxy_enabled = 1, provider_specific_data = ? WHERE id = ?",
                    (json.dumps(psd), conn_id),
                )
                db.commit()
                return {"id": conn_id, "connectionProxyUrl": proxy_url, "connectionProxyEnabled": True}
    except Exception:
        pass
    return None


def remove_proxy_from_connection(conn_id: str) -> Optional[Dict[str, Any]]:
    """Disable proxy on a connection and clear proxy URL."""
    res = api_request(
        "PUT",
        f"/api/providers/{conn_id}",
        {
            "connectionProxyEnabled": False,
            "connectionProxyUrl": "",
            "connectionNoProxy": "",
            "proxyPoolId": None,
        },
    )
    if "connection" in res:
        return res.get("connection")

    # Fallback: direct SQLite update
    try:
        import sqlite3

        from netools.services.omniroute_bridge import _DEFAULT_DB_PATH

        if _DEFAULT_DB_PATH.exists():
            with sqlite3.connect(_DEFAULT_DB_PATH) as db:
                row = db.execute(
                    "SELECT provider_specific_data FROM provider_connections WHERE id = ?", (conn_id,)
                ).fetchone()
                psd = {}
                if row and row[0]:
                    try:
                        psd = json.loads(row[0])
                    except Exception:
                        pass
                psd["connectionProxyEnabled"] = False
                psd["connectionProxyUrl"] = ""
                psd["connectionNoProxy"] = ""
                db.execute(
                    "UPDATE provider_connections SET proxy_enabled = 0, provider_specific_data = ? WHERE id = ?",
                    (json.dumps(psd), conn_id),
                )
                db.commit()
                return {"id": conn_id, "connectionProxyUrl": "", "connectionProxyEnabled": False}
    except Exception:
        pass
    return None


def clear_all_connection_proxies() -> int:
    """Unlink and disable proxy on ALL connections in OmniRoute."""
    conns = get_connections()
    cleared = 0
    for conn in conns:
        spec = conn.get("providerSpecificData") or {}
        if (
            spec.get("connectionProxyEnabled")
            or conn.get("connectionProxyUrl")
            or spec.get("proxyPoolId")
            or conn.get("proxyPoolId")
        ):
            remove_proxy_from_connection(conn["id"])
            cleared += 1
            name = conn.get("name", conn.get("provider", "?"))
            log.info(f"Proxy cleared in OmniRoute: {name} ({conn['id'][:12]})")
    return cleared


clear_all_proxies = clear_all_connection_proxies


def assign_round_robin(proxies_or_pools: List[str]) -> int:
    """Distribute active proxies or pools round-robin across all OmniRoute provider connections."""
    conns = get_connections()
    if not conns or not proxies_or_pools:
        return 0
    assigned = 0
    for idx, c in enumerate(conns):
        target = proxies_or_pools[idx % len(proxies_or_pools)]
        if target.startswith("socks5://") or target.startswith("http://"):
            proxy_url = target
        else:
            proxy_url = f"socks5://127.0.0.1:{11080 + (idx % len(proxies_or_pools))}"
        res = assign_proxy_to_connection(c["id"], proxy_url)
        if res:
            assigned += 1
    return assigned


@safe_backend_call(fallback_return=None)
def add_proxy_pool(name: str, proxy_url: str) -> Optional[str]:
    """Register a new proxy entry in OmniRoute's Proxy Registry."""
    import urllib.parse

    parsed = urllib.parse.urlparse(proxy_url)
    scheme = parsed.scheme.lower() or "socks5"
    if scheme not in ("http", "https", "socks5"):
        scheme = "socks5"
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 11080
    username = parsed.username or ""
    password = parsed.password or ""

    # 1. Try REST API with schema matching createProxyRegistrySchema
    res = api_request(
        "POST",
        "/api/settings/proxies",
        {
            "name": name,
            "type": scheme,
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "status": "active",
            "source": "manual",
            "family": "auto",
            "notes": "Netools Sing-box Proxy Pool",
        },
    )
    proxy_id = res.get("id") or res.get("proxy", {}).get("id")
    if proxy_id:
        return str(proxy_id)

    # 2. Fallback to direct SQLite insertion into proxy_registry
    try:
        import datetime
        import sqlite3
        import uuid

        from netools.services.omniroute_bridge import _DEFAULT_DB_PATH

        if _DEFAULT_DB_PATH.exists():
            with sqlite3.connect(_DEFAULT_DB_PATH) as db:
                row = db.execute(
                    "SELECT id FROM proxy_registry WHERE host = ? AND port = ? AND username = ? LIMIT 1",
                    (host, port, username),
                ).fetchone()
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                if row:
                    proxy_id = row[0]
                    db.execute(
                        "UPDATE proxy_registry SET name = ?, status = 'active', updated_at = ? WHERE id = ?",
                        (name, now, proxy_id),
                    )
                else:
                    proxy_id = str(uuid.uuid4())
                    db.execute(
                        """INSERT INTO proxy_registry
                        (id, name, type, host, port, username, password, status, source, notes, family, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'active', 'manual', 'Netools Sing-box Proxy Pool', 'auto', ?, ?)""",
                        (proxy_id, name, scheme, host, port, username, password, now, now),
                    )
                db.commit()
                return proxy_id
    except Exception as e:
        log.debug("Failed SQLite fallback for add_proxy_pool: %s", e)

    return None


@safe_backend_call(fallback_return=False)
def delete_proxy_pool(pool_id: str) -> bool:
    """Delete a proxy entry from OmniRoute's Proxy Registry."""
    # 1. Try REST API
    res = api_request("DELETE", f"/api/settings/proxies?id={pool_id}&force=1")
    if res.get("success", False) or ("error" not in res and res):
        return True

    # 2. Fallback to direct SQLite deletion
    try:
        import sqlite3

        from netools.services.omniroute_bridge import _DEFAULT_DB_PATH

        if _DEFAULT_DB_PATH.exists():
            with sqlite3.connect(_DEFAULT_DB_PATH) as db:
                db.execute("DELETE FROM proxy_registry WHERE id = ?", (pool_id,))
                db.commit()
                return True
    except Exception as e:
        log.debug("Failed SQLite fallback for delete_proxy_pool: %s", e)

    return False


def benchmark_api_dns(
    hostname: str = "api.openai.com",
    dns_servers: Optional[List[str]] = None,
    timeout: float = 1.0,
) -> Dict[str, float]:
    """Benchmark DNS resolution latency for an upstream AI provider host across multiple DNS servers."""
    if dns_servers is None:
        dns_servers = ["1.1.1.1", "8.8.8.8", "9.9.9.9", "127.0.0.1"]

    results: Dict[str, float] = {}
    for server in dns_servers:
        start = time.perf_counter()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            query = _build_dns_query(hostname)
            sock.sendto(query, (server, 53))
            _data, _ = sock.recvfrom(512)
            latency_ms = (time.perf_counter() - start) * 1000.0
            results[server] = round(latency_ms, 2)
            sock.close()
        except Exception:
            results[server] = -1.0
    return results


def _build_dns_query(host: str) -> bytes:
    """Construct a minimalist standard DNS query packet for A record."""
    packet = bytearray()
    packet.extend(b"\xaa\xbb\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00")
    for part in host.split("."):
        packet.append(len(part))
        packet.extend(part.encode("ascii"))
    packet.append(0)
    packet.extend(b"\x00\x01\x00\x01")
    return bytes(packet)
