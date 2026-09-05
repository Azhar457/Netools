"""Unit tests for the pool heatmap color mapping used by view_proxy."""
import unittest

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
