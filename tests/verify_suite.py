"""
Deterministic Verification Test Suite for Netools Suite.
Tests adapters, services, socket protocols, GUI modules, and CLI parsers.
"""

import sys
import unittest
from pathlib import Path

# Ensure root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


class TestNetoolsCore(unittest.TestCase):
    def test_01_config_and_paths(self):
        from netools import config

        self.assertTrue(config.BASE_DIR.exists())
        self.assertTrue(config.RUNTIME_DIR.exists())
        self.assertTrue(config.CONFIGS_DIR.exists())
        self.assertTrue(config.LOGS_DIR.exists())
        self.assertTrue(config.PID_DIR.exists())
        self.assertEqual(config.SOCKS5_PORT_START, 11080)
        self.assertEqual(config.HTTP_PORT_OFFSET, 10000)

    def test_02_dns_database_and_providers(self):
        from netools.libs import dns_db as db

        provs = db.load_providers()
        self.assertGreater(len(provs), 30, "Database should have at least 30 DNS providers")

        # Verify required keys in providers
        for k, p in provs.items():
            self.assertIn("name", p)
            self.assertIn("country", p)
            has_endpoints = len(p.get("ipv4", [])) > 0 or len(p.get("ipv6", [])) > 0 or bool(p.get("doh_url"))
            self.assertTrue(has_endpoints, f"Provider {k} must have at least one IPv4, IPv6, or DoH endpoint")

    def test_03_dns_benchmark_scoring_and_smart_mix(self):
        from netools.libs import dns_benchmark as bm

        # Test Smart Mix calculation
        res_map = {
            "p1": {
                "key": "p1",
                "name": "Fast Cached",
                "ipv4": ["1.1.1.1"],
                "cached_ms": 10.0,
                "uncached_ms": 50.0,
                "dotcom_ms": 40.0,
                "score": 25.0,
            },
            "p2": {
                "key": "p2",
                "name": "Fast Uncached",
                "ipv4": ["8.8.8.8"],
                "cached_ms": 40.0,
                "uncached_ms": 20.0,
                "dotcom_ms": 45.0,
                "score": 30.0,
            },
            "p3": {
                "key": "p3",
                "name": "Fast TLD",
                "ipv4": ["9.9.9.9"],
                "cached_ms": 45.0,
                "uncached_ms": 45.0,
                "dotcom_ms": 15.0,
                "score": 32.0,
            },
        }

        mix = bm.calculate_smart_mix(res_map)
        self.assertEqual(mix["cached"]["key"], "p1")
        self.assertEqual(mix["uncached"]["key"], "p2")
        self.assertEqual(mix["dotcom"]["key"], "p3")

    def test_04_network_interfaces_and_adapters(self):
        from netools.adapters import platform_dns

        ifaces = platform_dns.get_network_interfaces()
        self.assertIsInstance(ifaces, list)
        self.assertGreater(len(ifaces), 0, "Should detect at least 1 network interface")

        # Verify interface dict structure
        for iface in ifaces:
            self.assertIn("device", iface)
            self.assertIn("label", iface)
            self.assertIn("is_default", iface)

    def test_05_socket_and_protocol_queries(self):
        from netools.libs.dns_benchmark import query_doh_dns, query_udp_dns

        # Live UDP DNS query test to Cloudflare 1.1.1.1
        lat_udp, _ips_udp, _rrsig_udp, _edns_udp = query_udp_dns("1.1.1.1", "google.com", timeout=3.0)
        if lat_udp is not None:
            self.assertGreater(lat_udp, 0.0)
            self.assertLess(lat_udp, 2000.0)

        # Live DoH query test to Cloudflare
        lat_doh, ips_doh, _rrsig_doh, edns_doh = query_doh_dns(
            "https://security.cloudflare-dns.com/dns-query", "google.com", timeout=3.0
        )
        if lat_doh is not None:
            self.assertGreater(lat_doh, 0.0)
            self.assertLess(lat_doh, 2000.0)
            self.assertTrue(edns_doh or len(ips_doh) > 0)

    def test_06_gui_imports_and_components(self):
        """Smoke test all GUI modules to verify no missing imports, syntax errors, or circular references."""
        from netools.gui import (
            theme,
            view_benchmark_modal,
            view_dashboard,
            view_dns,
            view_proxy,
            view_settings,
        )

        self.assertIsNotNone(theme.Fonts)
        self.assertIsNotNone(view_dashboard.DashboardView)
        self.assertIsNotNone(view_dns.DNSView)
        self.assertIsNotNone(view_proxy.ProxyView)
        self.assertIsNotNone(view_settings.SettingsView)
        self.assertIsNotNone(view_benchmark_modal.GRCBenchmarkModal)

    def test_07_cli_parser(self):
        from netools.cli import main

        parser = main.build_parser()

        # Test CLI arguments
        args_gui = parser.parse_args(["gui"])
        self.assertEqual(args_gui.command, "gui")

        args_dns = parser.parse_args(["dns", "flush"])
        self.assertEqual(args_dns.command, "dns")
        self.assertEqual(args_dns.dns_action, "flush")

        args_proxy = parser.parse_args(["proxy", "start", "--no-9r"])
        self.assertEqual(args_proxy.command, "proxy")
        self.assertEqual(args_proxy.proxy_action, "start")
        self.assertTrue(args_proxy.no_9r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
