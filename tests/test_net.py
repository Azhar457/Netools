import unittest
from unittest.mock import MagicMock, patch

from netools.libs.net import check_ipv6_connectivity, is_port_open, probe_socks_upstream


class TestNet(unittest.TestCase):
    @patch("netools.libs.net.socket.socket")
    def test_is_port_open_success(self, mock_socket):
        mock_sock_inst = MagicMock()
        mock_sock_inst.connect_ex.return_value = 0
        mock_socket.return_value.__enter__.return_value = mock_sock_inst

        self.assertTrue(is_port_open(1080))

    @patch("netools.libs.net.socket.socket")
    def test_is_port_open_refused(self, mock_socket):
        mock_sock_inst = MagicMock()
        mock_sock_inst.connect_ex.return_value = 111
        mock_socket.return_value.__enter__.return_value = mock_sock_inst

        self.assertFalse(is_port_open(1080))

    @patch("netools.libs.net.is_port_open")
    @patch("netools.libs.net.subprocess.run")
    def test_probe_socks_upstream_success(self, mock_run, mock_is_open):
        mock_is_open.return_value = True
        mock_proc = MagicMock()
        mock_proc.stdout = "204\n"
        mock_run.return_value = mock_proc

        self.assertTrue(probe_socks_upstream(1080))

    @patch("netools.libs.net.is_port_open")
    @patch("netools.libs.net.subprocess.run")
    def test_probe_socks_upstream_port_closed(self, mock_run, mock_is_open):
        mock_is_open.return_value = False

        self.assertFalse(probe_socks_upstream(1080))
        mock_run.assert_not_called()

    @patch("netools.libs.net.socket.socket")
    def test_check_ipv6_no_leak(self, mock_socket):
        mock_sock_inst = MagicMock()
        mock_sock_inst.connect.side_effect = Exception("Network error")
        mock_socket.return_value = mock_sock_inst

        self.assertFalse(check_ipv6_connectivity())
        mock_sock_inst.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
