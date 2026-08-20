"""
OmniRoute AI Gateway REST API Adapter.

STATUS: STUB — only api_request() and is_healthy() are implemented.
Full CRUD operations (add_proxy_pool, assign_proxy, etc.) are NOT yet available.
Use the ninerouter adapter for full backend integration.
"""

import json
import urllib.request
from typing import Any, Dict, Optional

from netools.config import OMNIROUTE_TOKEN, OMNIROUTE_URL


def api_request(method: str, path: str, body: Optional[Dict[str, Any]] = None, timeout: float = 0.5) -> Dict[str, Any]:
    """Send authenticated HTTP request to OmniRoute REST API."""
    url = f"{OMNIROUTE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if OMNIROUTE_TOKEN:
        headers["Authorization"] = f"Bearer {OMNIROUTE_TOKEN}"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

def is_healthy() -> bool:
    """Check if OmniRoute is currently alive and reachable."""
    res = api_request("GET", "/api/proxy-pools")
    return "error" not in res
