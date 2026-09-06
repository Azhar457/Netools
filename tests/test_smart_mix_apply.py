"""
Unit tests for GRC Smart Mix Apply IP deduplication and string integrity.
Ensures DNS entries are never doubled/concatenated and slots are populated cleanly.
"""

import ipaddress
import unittest
from unittest.mock import MagicMock, patch

from netools.gui.view_benchmark_modal import GRCBenchmarkModal


class MockEntry:
    def __init__(self):
        self.text = ""

    def get(self):
        return self.text

    def delete(self, start, end):
        self.text = ""

    def insert(self, idx, string):
        # Emulate Tkinter/CTkEntry behavior: insert at index without overwriting
        self.text = self.text[:idx] + str(string) + self.text[idx:]


class TestSmartMixApply(unittest.TestCase):
    def setUp(self):
        self.modal = object.__new__(GRCBenchmarkModal)
        self.modal.results_map = {}
        self.modal.providers = {
            "quad9": {
                "name": "Quad9",
                "country": "CH",
                "ipv4": ["9.9.9.9", "149.112.112.112", "149.112.112.9"],
            },
            "mullvad": {
                "name": "Mullvad",
                "country": "SE",
                "ipv4": ["194.242.2.3", "194.242.2.4"],
            },
            "cloudflare": {
                "name": "Cloudflare",
                "country": "US",
                "ipv4": ["1.1.1.1", "1.0.0.1"],
            },
        }

        self.entry1 = MockEntry()
        self.entry2 = MockEntry()
        self.entry3 = MockEntry()

        self.dns_view = MagicMock()
        self.dns_view.dns1_entry = self.entry1
        self.dns_view.dns2_entry = self.entry2
        self.dns_view.dns3_entry = self.entry3

        def _compute_provider_ips(provider, p_key, family):
            return provider.get("ipv4", [])

        self.dns_view.compute_provider_ips.side_effect = _compute_provider_ips
        self.modal.dns_view = self.dns_view
        self.modal.lbl_status = MagicMock()
        self.modal._get_benchmark_mode_key = MagicMock(return_value="ipv4")

    @patch("threading.Thread")
    @patch("netools.libs.dns_benchmark.calculate_smart_mix")
    def test_smart_mix_applies_deduplicated_quad9_and_mullvad(self, mock_calc, mock_thread):
        mock_calc.return_value = {
            "cached": {"key": "quad9", "name": "Quad9"},
            "uncached": {"key": "mullvad", "name": "Mullvad"},
            "dotcom": {"key": "mullvad", "name": "Mullvad"},
        }

        self.modal.apply_smart_mix()

        ip1 = self.entry1.get()
        ip2 = self.entry2.get()
        ip3 = self.entry3.get()

        self.assertEqual(ip1, "9.9.9.9")
        self.assertEqual(ip2, "194.242.2.3")
        self.assertEqual(ip3, "194.242.2.4")

        for ip in (ip1, ip2, ip3):
            self.assertIsInstance(ipaddress.ip_address(ip), ipaddress.IPv4Address)
            self.assertNotIn("3149", ip)
            self.assertNotIn("4149", ip)

    @patch("threading.Thread")
    @patch("netools.libs.dns_benchmark.calculate_smart_mix")
    def test_smart_mix_single_provider_backfill(self, mock_calc, mock_thread):
        mock_calc.return_value = {
            "cached": {"key": "quad9", "name": "Quad9"},
            "uncached": {"key": "quad9", "name": "Quad9"},
            "dotcom": {"key": "quad9", "name": "Quad9"},
        }

        self.modal.apply_smart_mix()

        ip1 = self.entry1.get()
        ip2 = self.entry2.get()
        ip3 = self.entry3.get()

        self.assertEqual(ip1, "9.9.9.9")
        self.assertEqual(ip2, "149.112.112.112")
        self.assertEqual(ip3, "149.112.112.9")

        self.assertEqual(len({ip1, ip2, ip3}), 3)
        for ip in (ip1, ip2, ip3):
            self.assertIsInstance(ipaddress.ip_address(ip), ipaddress.IPv4Address)

    @patch("threading.Thread")
    @patch("netools.libs.dns_benchmark.calculate_smart_mix")
    def test_smart_mix_three_distinct_providers(self, mock_calc, mock_thread):
        mock_calc.return_value = {
            "cached": {"key": "quad9", "name": "Quad9"},
            "uncached": {"key": "mullvad", "name": "Mullvad"},
            "dotcom": {"key": "cloudflare", "name": "Cloudflare"},
        }

        self.modal.apply_smart_mix()

        self.assertEqual(self.entry1.get(), "9.9.9.9")
        self.assertEqual(self.entry2.get(), "194.242.2.3")
        self.assertEqual(self.entry3.get(), "1.1.1.1")


if __name__ == "__main__":
    unittest.main()
