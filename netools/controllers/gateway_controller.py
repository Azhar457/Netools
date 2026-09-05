"""
Gateway Controller for Netools MVC.
Coordinates AI multi-provider gateway synchronization with 9Router and OmniRoute.
"""

from typing import Any, Callable, Dict, List, Optional

from netools.adapters import ninerouter as nr_adapt
from netools.adapters import omniroute as or_adapt
from netools.controllers.base_controller import BaseController
from netools.state import load_state


class GatewayController(BaseController):
    def __init__(self, ui_dispatcher: Optional[Callable[[Callable], None]] = None):
        super().__init__(ui_dispatcher=ui_dispatcher)

    def check_health(self) -> Dict[str, bool]:
        """Check availability of both 9Router and OmniRoute."""
        return {
            "9router": nr_adapt.is_healthy(),
            "omniroute": or_adapt.is_healthy(),
        }

    def fetch_all_connections(
        self,
        on_success: Optional[Callable[[Dict[str, List[Dict[str, Any]]]], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Fetch all registered provider connections from both gateways concurrently."""
        def _task():
            nr_conns = nr_adapt.get_connections() if nr_adapt.is_healthy() else []
            or_conns = or_adapt.get_connections() if or_adapt.is_healthy() else []
            return {"9router": nr_conns, "omniroute": or_conns}

        self.run_async(_task, on_success=on_success, on_error=on_error)

    def bind_active_pools(
        self,
        on_success: Optional[Callable[[Dict[str, int]], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Assign current active proxy ports across all provider connections in 9Router and OmniRoute."""
        def _task():
            state = load_state()
            instances = state.get("instances", {})
            if not instances:
                return {"9router": 0, "omniroute": 0, "error": "No active proxies in pool"}

            alive_socks = [f"socks5://127.0.0.1:{info['port']}" for info in instances.values()]
            nr_assigned = 0
            or_assigned = 0

            # 1. 9Router
            if nr_adapt.is_healthy():
                nr_conns = nr_adapt.get_connections()
                assignments = [
                    (c["id"], alive_socks[idx % len(alive_socks)])
                    for idx, c in enumerate(nr_conns)
                ]
                for cid, url in assignments:
                    if nr_adapt.assign_proxy_to_connection(cid, url):
                        nr_assigned += 1

            # 2. OmniRoute (atomic batch)
            if or_adapt.is_healthy():
                or_conns = or_adapt.get_connections()
                or_assignments = [
                    (c["id"], alive_socks[idx % len(alive_socks)])
                    for idx, c in enumerate(or_conns)
                ]
                or_assigned = or_adapt.assign_proxies_to_connections_batch(or_assignments)

            return {"9router": nr_assigned, "omniroute": or_assigned}

        self.run_async(_task, on_success=on_success, on_error=on_error)

    def unlink_all_proxies(
        self,
        on_success: Optional[Callable[[Dict[str, int]], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Clear proxy assignments from all provider connections across both gateways."""
        def _task():
            nr_cleared = nr_adapt.clear_all_connection_proxies() if nr_adapt.is_healthy() else 0
            or_cleared = or_adapt.clear_all_connection_proxies() if or_adapt.is_healthy() else 0
            or_adapt.clear_managed_pools()
            return {"9router": nr_cleared, "omniroute": or_cleared}

        self.run_async(_task, on_success=on_success, on_error=on_error)
