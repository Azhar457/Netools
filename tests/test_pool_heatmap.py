"""Unit tests for the pool heatmap color mapping used by view_proxy."""
import unittest
from unittest.mock import MagicMock, patch

from netools.gui.view_proxy import _port_state_to_color


class TestHeatmapColorMatrix(unittest.TestCase):
    def test_alive_is_green(self):
        color, glyph = _port_state_to_color("alive")
        self.assertEqual(color, "#10b981")
        self.assertEqual(glyph, "●")

    def test_upstream_probe_failed_is_red(self):
        color, glyph = _port_state_to_color("upstream_probe_failed")
        self.assertEqual(color, "#ef4444")
        self.assertEqual(glyph, "✕")

    def test_spawn_failed_is_grey(self):
        color, glyph = _port_state_to_color("spawn_failed")
        self.assertEqual(color, "#6b7280")
        self.assertEqual(glyph, "○")

    def test_probe_exception_timeout_is_red(self):
        color, glyph = _port_state_to_color("probe_exception:TimeoutError")
        self.assertEqual(color, "#ef4444")

    def test_unknown_is_amber(self):
        color, _ = _port_state_to_color("something_we_dont_know_about")
        self.assertEqual(color, "#f59e0b")


class TestProxyViewFilter(unittest.TestCase):
    @patch("netools.gui.view_proxy.load_state")
    @patch("netools.gui.view_proxy.pac_service")
    @patch("netools.gui.view_proxy.platform_proxy")
    def test_populate_sync_filters_dead_instances(self, mock_plat, mock_pac, mock_load):
        mock_load.return_value = {
            "instances": {
                "sb-00": {"reason": "alive", "port": 11080, "server": "1.1.1.1", "server_port": 443},
                "sb-01": {"reason": "upstream_probe_failed", "port": 11081, "server": "2.2.2.2", "server_port": 443},
                "sb-02": {"reason": "spawn_failed", "port": 11082, "server": "3.3.3.3", "server_port": 443},
            }
        }
        mock_pac.is_pac_server_running.return_value = False
        mock_plat.get_system_proxy_status.return_value = {"enabled": False}

        view = MagicMock()
        view.tree = MagicMock()
        view.tree.get_children.return_value = []
        view.heatmap_cells = [MagicMock() for _ in range(20)]
        view.lbl_summary = MagicMock()

        from netools.gui.view_proxy import ProxyView
        ProxyView._populate_sync(view)

        # Only sb-00 (alive) should be inserted into tree
        self.assertEqual(view.tree.insert.call_count, 1)
        inserted_values = view.tree.insert.call_args[1]["values"]
        self.assertEqual(inserted_values[0], "sb-00")
        self.assertEqual(inserted_values[7], "🟢 Alive")

        # Summary label should count only 1 active instance
        summary_text = view.lbl_summary.configure.call_args[1]["text"]
        self.assertIn("Instances: 1 active", summary_text)

