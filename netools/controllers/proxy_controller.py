"""
Proxy Controller for Netools MVC.
Coordinates sing-box instance lifecycles, health testing, and watchdog background service.
"""

from typing import Any, Callable, Dict, Optional

from netools.controllers.base_controller import BaseController
from netools.services import proxy_service, watchdog_service


class ProxyController(BaseController):
    def __init__(self, ui_dispatcher: Optional[Callable[[Callable], None]] = None):
        super().__init__(ui_dispatcher=ui_dispatcher)

    def start_pool(
        self,
        standalone: bool = False,
        kill_switch: bool = False,
        on_success: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Asynchronously start all sing-box proxy instances and register with gateways.

        kill_switch: when True, if no proxy comes up alive, block all outbound
                     traffic at the firewall until a proxy recovers. Privacy
                     guarantee - the user is air-gapped instead of leaking.
        """
        self.run_async(
            proxy_service.start_proxy_pool,
            on_success=on_success,
            on_error=on_error,
            standalone=standalone,
            kill_switch=kill_switch,
        )

    def stop_pool(
        self,
        standalone: bool = False,
        on_success: Optional[Callable[[None], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Asynchronously stop all proxy instances and unbind gateways."""
        def _task():
            watchdog_service.stop_watchdog()
            proxy_service.stop_proxy_pool(standalone=standalone)

        self.run_async(_task, on_success=on_success, on_error=on_error)

    def refresh_pool(
        self,
        standalone: bool = False,
        on_success: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Stop and recreate proxy instances with fresh nodes."""
        self.run_async(
            proxy_service.refresh_proxy_pool,
            on_success=on_success,
            on_error=on_error,
            standalone=standalone,
        )

    def toggle_watchdog(
        self,
        enable: bool,
        on_success: Optional[Callable[[bool], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Enable or disable the background auto-heal watchdog monitor."""
        def _task():
            if enable:
                watchdog_service.start_watchdog()
            else:
                watchdog_service.stop_watchdog()
            return enable

        self.run_async(_task, on_success=on_success, on_error=on_error)

    def get_status(self) -> Dict[str, Any]:
        """Synchronously check live status of active instances."""
        return proxy_service.get_proxy_status()

    def is_watchdog_active(self) -> bool:
        """Check if watchdog service is currently running."""
        return watchdog_service.is_watchdog_running()
