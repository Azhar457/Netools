"""
Unit tests for Netools Enhancements (S2 Health Endpoint, S3 Caching, S4 JSON Logging, S5 Config Loading, S6 Retries).
"""

import json
import logging
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from netools.adapters import ninerouter
from netools.libs.logger import JsonFormatter
from netools.services import pac_service, proxy_service


class TestEnhancements(unittest.TestCase):
    def test_json_formatter(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_netools",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        out = formatter.format(record)
        data = json.loads(out)
        self.assertEqual(data["message"], "Test message")
        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["logger"], "test_netools")

    def test_pac_generate_pac_content(self):
        # Test generate_pac_content static logic directly on PACHandler class
        dummy_self = MagicMock()
        content = pac_service.PACHandler.generate_pac_content(dummy_self)
        self.assertIn("function FindProxyForURL", content)
        self.assertIn("DIRECT", content)

    @patch("urllib.request.urlopen")
    def test_ninerouter_retry_success_after_failure(self, mock_urlopen):
        # First call fails, second call succeeds with context manager
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"proxyPools": [{"id": "p1", "name": "pool1"}]}'
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None
        mock_urlopen.side_effect = [Exception("Transient network drop"), mock_resp]

        res = ninerouter.api_request("GET", "/api/proxy-pools", max_retries=2)
        self.assertIn("proxyPools", res)
        self.assertEqual(len(res["proxyPools"]), 1)
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("netools.services.proxy_service.fetch_text")
    def test_proxy_service_fallback_cache(self, mock_fetch):
        mock_fetch.side_effect = Exception("Connection refused to all GitHub sources")
        
        with patch("netools.services.proxy_service.RUNTIME_DIR", Path("/tmp")):
            cache_file = Path("/tmp/last_known_proxies.json")
            cached_data = [
                {"type": "shadowsocks", "server": "9.9.9.9", "server_port": 8388, "method": "aes-256-gcm", "password": "p"}
            ]
            cache_file.write_text(json.dumps(cached_data))
            
            try:
                proxies = proxy_service.fetch_and_parse_proxies(max_count=5)
                self.assertEqual(len(proxies), 1)
                self.assertEqual(proxies[0]["server"], "9.9.9.9")
            finally:
                cache_file.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
