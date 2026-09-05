"""
System Proxy Controller for Netools MVC.
Coordinates the local PAC HTTP server with OS-level native proxy settings (macOS, Windows, Linux).
"""

from typing import Any, Callable, Dict, Optional

from netools.adapters import platform_proxy
from netools.controllers.base_controller import BaseController
from netools.services import pac_service


class SystemProxyController(BaseController):
    def __init__(self, ui_dispatcher: Optional[Callable[[Callable], None]] = None):
        super().__init__(ui_dispatcher=ui_dispatcher)

    def toggle_pac_server(
        self,
        on_success: Optional[Callable[[bool], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Toggle local PAC HTTP server on/off."""
        def _task():
            if pac_service.is_pac_server_running():
                pac_service.stop_pac_server()
                # If PAC server stops, automatically disable system proxy if it was using it
                platform_proxy.disable_system_proxy()
                return False
            else:
                pac_service.start_pac_server()
                return True

        self.run_async(_task, on_success=on_success, on_error=on_error)

    def set_system_proxy(
        self,
        enable: bool,
        on_success: Optional[Callable[[bool], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Enable or disable native OS-level system proxy settings across macOS, Windows, and Linux."""
        def _task():
            if enable:
                # Ensure PAC server is active first
                if not pac_service.is_pac_server_running():
                    pac_service.start_pac_server()
                pac_url = pac_service.get_pac_url()
                return platform_proxy.enable_system_proxy(pac_url)
            else:
                return platform_proxy.disable_system_proxy()

        self.run_async(_task, on_success=on_success, on_error=on_error)

    def get_status(self) -> Dict[str, Any]:
        """Check status of PAC server and native OS system proxy."""
        pac_running = pac_service.is_pac_server_running()
        sys_status = platform_proxy.get_system_proxy_status()
        return {
            "pac_running": pac_running,
            "pac_url": pac_service.get_pac_url(),
            "system_proxy_enabled": sys_status.get("enabled", False),
            "system_proxy_type": sys_status.get("type", "none"),
        }
