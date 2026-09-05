"""
Unit tests for netools.adapters.platform_proxy.
Tests cross-platform system proxy enablement, disablement, and status retrieval.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

from netools.adapters import platform_proxy


class TestPlatformProxy(unittest.TestCase):
    def test_get_system_proxy_status_structure(self):
        status = platform_proxy.get_system_proxy_status()
        self.assertIsInstance(status, dict)
        self.assertIn("enabled", status)
        self.assertIn("pac_url", status)
        self.assertIn("type", status)

    @patch("netools.adapters.platform_proxy.get_os_type", return_value="darwin")
    @patch("netools.adapters.platform_proxy._get_macos_active_service", return_value="Wi-Fi")
    @patch("subprocess.run")
    def test_macos_enable_disable(self, mock_run, mock_service, mock_os):
        mock_run.return_value = MagicMock(returncode=0)
        pac_url = "http://127.0.0.1:18080/proxy.pac"

        res = platform_proxy.enable_system_proxy(pac_url)
        self.assertTrue(res)
        # Verify networksetup commands were called
        mock_run.assert_any_call(["networksetup", "-setautoproxyurl", "Wi-Fi", pac_url], check=True, capture_output=True)
        mock_run.assert_any_call(["networksetup", "-setautoproxystate", "Wi-Fi", "on"], check=True, capture_output=True)

        res_off = platform_proxy.disable_system_proxy()
        self.assertTrue(res_off)
        mock_run.assert_any_call(["networksetup", "-setautoproxystate", "Wi-Fi", "off"], check=True, capture_output=True)

    @patch("netools.adapters.platform_proxy.get_os_type", return_value="windows")
    def test_windows_enable_disable(self, mock_os):
        pac_url = "http://127.0.0.1:18080/proxy.pac"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with patch.dict(sys.modules, {"winreg": MagicMock()}):
                import winreg
                mock_key = MagicMock()
                winreg.OpenKey.return_value.__enter__.return_value = mock_key

                res = platform_proxy.enable_system_proxy(pac_url)
                self.assertTrue(res)

                res_off = platform_proxy.disable_system_proxy()
                self.assertTrue(res_off)

    @patch("netools.adapters.platform_proxy.get_os_type", return_value="linux")
    @patch("shutil.which")
    @patch("subprocess.run")
    def test_linux_enable_disable_gnome(self, mock_run, mock_which, mock_os):
        mock_which.side_effect = lambda cmd: "/usr/bin/gsettings" if cmd == "gsettings" else None
        mock_run.return_value = MagicMock(returncode=0)
        pac_url = "http://127.0.0.1:18080/proxy.pac"

        res = platform_proxy.enable_system_proxy(pac_url)
        self.assertTrue(res)
        mock_run.assert_any_call(["gsettings", "set", "org.gnome.system.proxy", "mode", "auto"], check=True, capture_output=True)
        mock_run.assert_any_call(["gsettings", "set", "org.gnome.system.proxy", "autoconfig-url", pac_url], check=True, capture_output=True)

        res_off = platform_proxy.disable_system_proxy()
        self.assertTrue(res_off)
        mock_run.assert_any_call(["gsettings", "set", "org.gnome.system.proxy", "mode", "none"], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
