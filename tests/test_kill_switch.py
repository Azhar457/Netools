"""Unit tests for the privacy kill switch (iptables on Linux, stub elsewhere)."""
import unittest
from unittest.mock import patch

from netools.adapters import kill_switch


class TestKillSwitch(unittest.TestCase):
    @patch("netools.adapters.kill_switch._run_iptables")
    def test_arm_block_all_returns_callable_restore(self, mock_run):
        mock_run.return_value = (True, "")
        restore = kill_switch.arm_block_all()
        self.assertTrue(callable(restore))
        # At least one iptables call to insert the REJECT rule
        self.assertGreaterEqual(mock_run.call_count, 1)
        # Restoring must call iptables again
        restore()
        self.assertGreaterEqual(mock_run.call_count, 2)

    @patch("netools.adapters.kill_switch.get_os_type", return_value="darwin")
    @patch("netools.adapters.kill_switch._run_iptables")
    def test_arm_block_all_macos_is_safe_noop(self, mock_run, mock_os):
        # macOS: no iptables, restore must be a callable that doesn't raise
        restore = kill_switch.arm_block_all()
        self.assertTrue(callable(restore))
        restore()  # must not raise
        mock_run.assert_not_called()

    @patch("netools.adapters.kill_switch._run_iptables")
    def test_arm_block_all_iptables_failure_returns_noop_restore(self, mock_run):
        # If iptables is missing or returns error, restore must still be safe
        mock_run.return_value = (False, "iptables not found")
        restore = kill_switch.arm_block_all()
        restore()  # must not raise


class TestKillSwitchWiring(unittest.TestCase):
    """Kill switch kwarg flows through to firewall arming and watchdog restore."""

    @patch("netools.adapters.kill_switch._run_iptables")
    @patch("netools.services.watchdog_service.start_watchdog_thread")
    @patch("netools.services.proxy_service.sb_drv")
    @patch("netools.services.proxy_service.fetch_and_parse_proxies")
    def test_kill_switch_armed_when_pool_empty(
        self, mock_fetch, mock_sb, mock_wd, mock_ipt
    ):
        mock_ipt.return_value = (True, "")
        mock_fetch.return_value = []
        mock_sb.build_singbox_config.return_value = {}
        mock_sb.start_singbox_instance.return_value = None

        from netools.services.proxy_service import start_proxy_pool
        state = start_proxy_pool(max_instances=1, standalone=False, kill_switch=True)

        # Firewall must have been touched
        self.assertGreaterEqual(mock_ipt.call_count, 1)
        # Watchdog should also be armed
        mock_wd.assert_called_once()
        # Restore callable must be stashed in state
        self.assertIn("_kill_switch_restore", state)
        self.assertTrue(callable(state["_kill_switch_restore"]))

    @patch("netools.adapters.kill_switch._run_iptables")
    @patch("netools.services.watchdog_service.start_watchdog_thread")
    @patch("netools.services.proxy_service.sb_drv")
    @patch("netools.services.proxy_service.fetch_and_parse_proxies")
    def test_kill_switch_not_armed_when_kwarg_false(
        self, mock_fetch, mock_sb, mock_wd, mock_ipt
    ):
        mock_ipt.return_value = (True, "")
        mock_fetch.return_value = []
        mock_sb.build_singbox_config.return_value = {}
        mock_sb.start_singbox_instance.return_value = None

        from netools.services.proxy_service import start_proxy_pool
        state = start_proxy_pool(max_instances=1, standalone=False, kill_switch=False)

        # Default-off: no iptables touch, no restore callable stashed
        mock_ipt.assert_not_called()
        self.assertNotIn("_kill_switch_restore", state)
