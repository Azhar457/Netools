"""
Unit tests for Proxy URI Parsers (Shadowsocks, Trojan, VMess, VLESS).
"""

import base64
import json
import unittest

from netools.libs import parsers


class TestProxyParsers(unittest.TestCase):
    def test_parse_shadowsocks(self):
        # ss://base64(method:password)@server:port#tag
        auth = base64.b64encode(b"aes-256-gcm:secret123").decode()
        uri = f"ss://{auth}@1.2.3.4:8388#MySSProxy"
        res = parsers.parse_proxy_uri(uri)
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "shadowsocks")
        self.assertEqual(res["server"], "1.2.3.4")
        self.assertEqual(res["server_port"], 8388)
        self.assertEqual(res["method"], "aes-256-gcm")
        self.assertEqual(res["password"], "secret123")
        self.assertEqual(res["tag"], "MySSProxy")

    def test_parse_trojan(self):
        uri = "trojan://password123@trojan.example.com:443?sni=trojan.example.com#MyTrojan"
        res = parsers.parse_proxy_uri(uri)
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "trojan")
        self.assertEqual(res["server"], "trojan.example.com")
        self.assertEqual(res["server_port"], 443)
        self.assertEqual(res["password"], "password123")
        self.assertEqual(res["tls"]["server_name"], "trojan.example.com")
        self.assertEqual(res["tag"], "MyTrojan")

    def test_parse_vmess(self):
        v_data = {
            "v": "2",
            "ps": "MyVMess",
            "add": "vmess.example.com",
            "port": "443",
            "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "aid": "0",
            "net": "ws",
            "type": "none",
            "host": "vmess.example.com",
            "path": "/vmesspath",
            "tls": "tls",
            "sni": "vmess.example.com",
        }
        b64_str = base64.b64encode(json.dumps(v_data).encode()).decode()
        uri = f"vmess://{b64_str}"
        res = parsers.parse_proxy_uri(uri)
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "vmess")
        self.assertEqual(res["server"], "vmess.example.com")
        self.assertEqual(res["server_port"], 443)
        self.assertEqual(res["uuid"], "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        self.assertEqual(res["transport"]["type"], "ws")
        self.assertEqual(res["transport"]["path"], "/vmesspath")

    def test_parse_vless(self):
        uri = "vless://a1b2c3d4-e5f6-7890-abcd-ef1234567890@vless.example.com:443?type=ws&security=tls&path=%2Fvlesspath&sni=vless.example.com#MyVLESS"
        res = parsers.parse_proxy_uri(uri)
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "vless")
        self.assertEqual(res["server"], "vless.example.com")
        self.assertEqual(res["server_port"], 443)
        self.assertEqual(res["uuid"], "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        self.assertEqual(res["tls"]["server_name"], "vless.example.com")
        self.assertEqual(res["transport"]["type"], "ws")
        self.assertEqual(res["transport"]["path"], "/vlesspath")
        self.assertEqual(res["tag"], "MyVLESS")

    def test_extract_all_proxies_dedup(self):
        auth = base64.b64encode(b"aes-256-gcm:pass").decode()
        raw = f"ss://{auth}@1.1.1.1:8388#One\nss://{auth}@1.1.1.1:8388#Duplicate\ntrojan://p@2.2.2.2:443#Two"
        proxies = parsers.extract_all_proxies(raw)
        self.assertEqual(len(proxies), 2)
        self.assertEqual(proxies[0]["server"], "1.1.1.1")
        self.assertEqual(proxies[1]["server"], "2.2.2.2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
