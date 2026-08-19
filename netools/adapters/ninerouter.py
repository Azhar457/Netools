"""
9Router AI Gateway REST API Adapter (Fail-Safe with Complete proxyPoolId Unlink).
"""

import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from netools.config import NINEROUTER_URL, NINEROUTER_CLI_TOKEN

def api_request(method: str, path: str, body: Optional[Dict[str, Any]] = None, timeout: float = 4.0) -> Dict[str, Any]:
    """Send authenticated HTTP request to 9Router REST API."""
    url = f"{NINEROUTER_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if NINEROUTER_CLI_TOKEN:
        headers["x-9r-cli-token"] = NINEROUTER_CLI_TOKEN

    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

def is_healthy() -> bool:
    """Check if 9Router is currently alive and reachable."""
    res = api_request("GET", "/api/proxy-pools")
    return "error" not in res

def get_connections() -> List[Dict[str, Any]]:
    """Retrieve all provider connections from 9Router."""
    res = api_request("GET", "/api/providers")
    return res.get("connections", [])

def get_existing_pools() -> Dict[str, str]:
    """Retrieve existing 9Router proxy pools: {name: id}."""
    res = api_request("GET", "/api/proxy-pools")
    pools = res.get("proxyPools", res.get("proxy_pools", []))
    return {p["name"]: p["id"] for p in pools}

def assign_proxy_to_connection(conn_id: str, proxy_url: str) -> Optional[Dict[str, Any]]:
    """Assign a proxy URL to a connection."""
    res = api_request("PUT", f"/api/providers/{conn_id}", {
        "connectionProxyEnabled": True,
        "connectionProxyUrl": proxy_url,
        "connectionNoProxy": "localhost,127.0.0.1",
    })
    return res.get("connection") if "connection" in res else None

def remove_proxy_from_connection(conn_id: str) -> Optional[Dict[str, Any]]:
    """Disable proxy on a connection and completely clear proxy URL and proxyPoolId."""
    res = api_request("PUT", f"/api/providers/{conn_id}", {
        "connectionProxyEnabled": False,
        "connectionProxyUrl": "",
        "connectionNoProxy": "",
        "proxyPoolId": None,
    })
    return res.get("connection") if "connection" in res else None

def clear_all_connection_proxies() -> int:
    """Unlink and disable proxy on ALL connections in 9Router."""
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
            print(f"[OK] Proxy cleared: {name} ({conn['id'][:12]})")
    return cleared

def add_proxy_pool(name: str, proxy_url: str) -> Optional[str]:
    """Register a new proxy pool in 9Router."""
    delete_pools_by_url(proxy_url)
    res = api_request("POST", "/api/proxy-pools", {
        "name": name,
        "proxyUrl": proxy_url,
        "noProxy": "localhost,127.0.0.1",
        "strictProxy": False,
        "isActive": True,
    })
    pool = res.get("proxyPool", {})
    return pool.get("id")

def delete_proxy_pool(pool_id: str) -> bool:
    """Delete proxy pool from 9Router."""
    res = api_request("DELETE", f"/api/proxy-pools/{pool_id}")
    return res.get("success", False) or "error" not in res

def delete_pools_by_url(proxy_url: str) -> None:
    """Delete all pools with matching proxy URL."""
    res = api_request("GET", "/api/proxy-pools")
    for p in res.get("proxyPools", res.get("proxy_pools", [])):
        if p.get("proxyUrl") == proxy_url:
            delete_proxy_pool(p["id"])
