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

if __name__ == "__main__":
    unittest.main(verbosity=2)
