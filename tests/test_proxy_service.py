import unittest
from unittest.mock import MagicMock, patch

from netools.services.proxy_service import fetch_and_parse_proxies, start_single_instance


class TestProxyService(unittest.TestCase):
    @patch("netools.services.proxy_service.fetch_text")
    def test_fetch_and_parse_proxies_empty_sources(self, mock_fetch_text):
        mock_fetch_text.return_value = ""
        proxies = fetch_and_parse_proxies()
        self.assertEqual(proxies, [])

    @patch("netools.services.proxy_service.fetch_text")
    def test_fetch_and_parse_proxies_valid_subscription(self, mock_fetch_text):
        mock_fetch_text.return_value = "ss://YWVzLTEyOC1nY206dGVzdA==@192.168.1.1:8388#test"
        proxies = fetch_and_parse_proxies()
        self.assertTrue(len(proxies) > 0)
        self.assertEqual(proxies[0]["server"], "192.168.1.1")
        self.assertEqual(proxies[0]["server_port"], 8388)

    @patch("netools.services.proxy_service.fetch_text")
    def test_fetch_and_parse_proxies_dedup(self, mock_fetch_text):
        # Return two identical proxies to test dedup
        mock_fetch_text.return_value = (
            "ss://YWVzLTEyOC1nY206dGVzdA==@192.168.1.1:8388#test\nss://YWVzLTEyOC1nY206dGVzdA==@192.168.1.1:8388#test2"
        )
        proxies = fetch_and_parse_proxies()
        self.assertEqual(len(proxies), 1)

    @patch("netools.services.proxy_service.sb_drv.start_singbox_instance")
    @patch("netools.services.proxy_service.probe_socks_upstream")
    @patch("time.sleep", return_value=None)
    def test_start_single_instance_upstream_fail(self, mock_sleep, mock_test_upstream, mock_start_instance):
        mock_proc = MagicMock()
        mock_start_instance.return_value = mock_proc
        mock_test_upstream.return_value = False

        res = start_single_instance("test-01", 1080, {"type": "ss", "server": "1.1.1.1", "server_port": 1234})

        self.assertIsNone(res)
        mock_proc.kill.assert_called_once()


if __name__ == "__main__":
    unittest.main()
