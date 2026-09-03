"""
Unit tests for Sing-box config builder & Supervisor adapter.
"""

import unittest

from netools.adapters import singbox


class TestSingboxAdapter(unittest.TestCase):
    def test_build_shadowsocks_config(self):
        proxy = {
            "type": "shadowsocks",
            "server": "1.2.3.4",
            "server_port": 8388,
            "method": "aes-256-gcm",
            "password": "secretpassword"
        }
        cfg = singbox.build_singbox_config(proxy, local_port=11080)
        self.assertEqual(cfg["inbounds"][0]["listen_port"], 11080)
        self.assertEqual(cfg["inbounds"][1]["listen_port"], 21080)
        self.assertEqual(cfg["outbounds"][0]["type"], "shadowsocks")
        self.assertEqual(cfg["outbounds"][0]["method"], "aes-256-gcm")

    def test_build_trojan_config(self):
        proxy = {
            "type": "trojan",
            "server": "trojan.test",
            "server_port": 443,
            "password": "pass",
            "tls": {"enabled": True, "server_name": "trojan.test"}
        }
        cfg = singbox.build_singbox_config(proxy, local_port=11081)
        self.assertEqual(cfg["outbounds"][0]["type"], "trojan")
        self.assertTrue(cfg["outbounds"][0]["tls"]["enabled"])

    def test_build_vless_config(self):
        proxy = {
            "type": "vless",
            "server": "vless.test",
            "server_port": 443,
            "uuid": "uuid-1234",
            "tls": {"enabled": True, "server_name": "vless.test"},
            "transport": {"type": "ws", "path": "/ws"}
        }
        cfg = singbox.build_singbox_config(proxy, local_port=11082)
        self.assertEqual(cfg["outbounds"][0]["type"], "vless")
        self.assertEqual(cfg["outbounds"][0]["uuid"], "uuid-1234")
        self.assertEqual(cfg["outbounds"][0]["transport"]["type"], "ws")


class TestOmnirouteAdapter(unittest.TestCase):
    def test_dns_packet_builder(self):
        from netools.adapters.omniroute import _build_dns_query
        query = _build_dns_query("api.openai.com")
        self.assertIsInstance(query, bytes)
        self.assertTrue(b"openai" in query)

    def test_credentials_setter(self):
        from netools.adapters import omniroute
        omniroute.set_credentials(url="http://localhost:20128", token="test-token")
        self.assertEqual(omniroute._CURRENT_URL, "http://localhost:20128")
        self.assertEqual(omniroute._CURRENT_TOKEN, "test-token")

    def test_health_check_offline(self):
        from netools.adapters import omniroute
        omniroute._health_cache["val"] = None
        # When omniroute port is not listening, safe_backend_call safely returns False without raising
        self.assertFalse(omniroute.is_healthy())


if __name__ == "__main__":
    unittest.main(verbosity=2)

