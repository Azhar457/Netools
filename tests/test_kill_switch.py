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
