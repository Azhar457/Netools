"""
Unit tests for Netools MVC Controllers.
Tests asynchronous event dispatching, headless execution, and state coordination.
"""

import time
import unittest
from unittest.mock import patch

from netools.controllers import (
    BaseController,
    GatewayController,
    ProxyController,
    SystemProxyController,
)


class TestControllers(unittest.TestCase):
    def test_base_controller_async_execution(self):
        ctrl = BaseController()
        results = []

        def _task(val):
            return val * 2

        def _on_success(res):
            results.append(res)

        ctrl.run_async(_task, on_success=_on_success, val=21)
        time.sleep(0.1)

        self.assertEqual(results, [42])
        ctrl.shutdown()

    @patch("netools.services.proxy_service.get_proxy_status", return_value={"total": 5, "alive_count": 5})
    @patch("netools.services.watchdog_service.is_watchdog_running", return_value=True)
    def test_proxy_controller_status(self, mock_wd, mock_stat):
        ctrl = ProxyController()
        status = ctrl.get_status()
        self.assertEqual(status["total"], 5)
        self.assertTrue(ctrl.is_watchdog_active())
        ctrl.shutdown()

    @patch("netools.adapters.ninerouter.is_healthy", return_value=True)
    @patch("netools.adapters.omniroute.is_healthy", return_value=False)
    def test_gateway_controller_health(self, mock_or, mock_nr):
        ctrl = GatewayController()
        health = ctrl.check_health()
        self.assertTrue(health["9router"])
        self.assertFalse(health["omniroute"])
        ctrl.shutdown()

    @patch("netools.services.pac_service.is_pac_server_running", return_value=True)
    @patch("netools.adapters.platform_proxy.get_system_proxy_status", return_value={"enabled": True, "type": "pac"})
    def test_system_proxy_controller_status(self, mock_sys, mock_pac):
        ctrl = SystemProxyController()
        status = ctrl.get_status()
        self.assertTrue(status["pac_running"])
        self.assertTrue(status["system_proxy_enabled"])
        self.assertEqual(status["system_proxy_type"], "pac")
        ctrl.shutdown()


if __name__ == "__main__":
    unittest.main()
