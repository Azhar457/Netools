import unittest
from unittest.mock import patch

from netools.services.watchdog_service import run_monitor_cycle


class TestWatchdogService(unittest.TestCase):
    @patch("netools.services.watchdog_service.load_state")
    def test_monitor_cycle_no_instances(self, mock_load_state):
        mock_load_state.return_value = {"instances": {}}
        res = run_monitor_cycle()
        self.assertEqual(res, 0)

    @patch("netools.services.watchdog_service.load_state")
    @patch("netools.services.watchdog_service.is_port_open")
    @patch("netools.services.watchdog_service.probe_socks_upstream")
    def test_monitor_cycle_all_alive(self, mock_upstream, mock_port_open, mock_load_state):
        mock_load_state.return_value = {"instances": {"inst1": {"port": 1080}, "inst2": {"port": 1081}}}
        mock_port_open.return_value = True
        mock_upstream.return_value = True

        res = run_monitor_cycle()
        self.assertEqual(res, 0)

    @patch("netools.services.watchdog_service.load_state")
    @patch("netools.services.watchdog_service.is_port_open")
    @patch("netools.services.watchdog_service.probe_socks_upstream")
    @patch("netools.services.watchdog_service.fetch_and_parse_proxies")
    @patch("netools.services.watchdog_service.start_single_instance")
    @patch("netools.services.watchdog_service.sb_drv")
    @patch("netools.services.watchdog_service.update_instance")
    @patch("netools.services.watchdog_service.remove_instance")
    def test_monitor_cycle_one_dead(
        self, mock_remove, mock_update, mock_sb, mock_start, mock_fetch, mock_upstream, mock_port_open, mock_load_state
    ):
        mock_load_state.return_value = {"instances": {"inst1": {"port": 1080}, "inst2": {"port": 1081}}}

        # Fail port 1081 only
        def port_open_side_effect(port):
            return port == 1080

        mock_port_open.side_effect = port_open_side_effect
        mock_upstream.return_value = True  # inst1 is True

        mock_fetch.return_value = [{"server": "new.server"}]
        mock_start.return_value = {"port": 1081, "server": "new.server"}

        res = run_monitor_cycle(standalone=True)
        self.assertEqual(res, 1)
        mock_start.assert_called_once()
        mock_update.assert_called_once()


if __name__ == "__main__":
    unittest.main()


class TestWatchdogAutoArm(unittest.TestCase):
    """start_proxy_pool must arm the watchdog so silent pool death is impossible."""

    @patch("netools.services.watchdog_service.start_watchdog_thread")
    @patch("netools.services.proxy_service.sb_drv")
    @patch("netools.services.proxy_service.fetch_and_parse_proxies")
    def test_pool_starts_arms_watchdog(self, mock_fetch, mock_sb, mock_arm):
        from netools.services.proxy_service import start_proxy_pool

        mock_fetch.return_value = []
        mock_sb.build_singbox_config.return_value = {}
        mock_sb.start_singbox_instance.return_value = None

        start_proxy_pool(max_instances=1, standalone=False)
        mock_arm.assert_called_once()
