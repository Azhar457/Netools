#!/usr/bin/env python3
"""
Unit tests for Multi-Layer Domain Censorship & DPI Engine (dpi_detector.py).
"""

import socket
import unittest
from unittest.mock import MagicMock, patch

from netools.libs import dpi_detector


class TestDPIDetector(unittest.TestCase):
    def test_is_bogon_or_private_ip(self):
        self.assertTrue(dpi_detector.is_bogon_or_private_ip("127.0.0.1"))
        self.assertTrue(dpi_detector.is_bogon_or_private_ip("0.0.0.0"))
        self.assertTrue(dpi_detector.is_bogon_or_private_ip("192.168.1.1"))
        self.assertTrue(dpi_detector.is_bogon_or_private_ip("10.0.0.1"))
        self.assertTrue(dpi_detector.is_bogon_or_private_ip("172.16.0.1"))
        self.assertTrue(dpi_detector.is_bogon_or_private_ip("100.64.1.1"))

        self.assertFalse(dpi_detector.is_bogon_or_private_ip("1.1.1.1"))
        self.assertFalse(dpi_detector.is_bogon_or_private_ip("8.8.8.8"))
        self.assertFalse(dpi_detector.is_bogon_or_private_ip("104.21.23.45"))

    @patch("netools.libs.dpi_detector.query_reference_doh")
    @patch("socket.getaddrinfo")
    def test_stage_a_dns_poisoning(self, mock_addr, mock_doh):
        mock_addr.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        mock_doh.return_value = (15.0, ["104.16.2.3"])

        stage, sys_ips, doh_ips = dpi_detector.evaluate_stage_a_dns("blocked-site.com")
        self.assertEqual(stage.status, "BLOCKED")
        self.assertIn("Poisoned", stage.summary)
        self.assertEqual(sys_ips, ["127.0.0.1"])
        self.assertEqual(doh_ips, ["104.16.2.3"])

    @patch("netools.libs.dpi_detector.query_reference_doh")
    @patch("socket.getaddrinfo")
    def test_stage_a_dns_clean(self, mock_addr, mock_doh):
        mock_addr.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("104.16.2.3", 443))]
        mock_doh.return_value = (12.0, ["104.16.2.3"])

        stage, _sys_ips, _doh_ips = dpi_detector.evaluate_stage_a_dns("clean-site.com")
        self.assertEqual(stage.status, "PASS")
        self.assertIn("Clean", stage.summary)

    @patch("socket.socket")
    def test_stage_b_tcp_pass(self, mock_sock_cls):
        mock_sock = MagicMock()
        mock_sock.connect.return_value = None
        mock_sock_cls.return_value = mock_sock

        stage = dpi_detector.evaluate_stage_b_tcp("104.16.2.3")
        self.assertEqual(stage.status, "PASS")
        self.assertIn("Connected", stage.summary)

    @patch("socket.socket")
    def test_stage_b_tcp_timeout(self, mock_sock_cls):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = socket.timeout("timed out")
        mock_sock_cls.return_value = mock_sock

        stage = dpi_detector.evaluate_stage_b_tcp("104.16.2.3")
        self.assertEqual(stage.status, "BLOCKED")
        self.assertIn("Timeout", stage.summary)

    @patch("ssl.create_default_context")
    @patch("socket.socket")
    def test_stage_c_sni_dpi_blocked_and_confirmed(self, mock_sock_cls, mock_ssl_ctx):
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock

        mock_ctx = MagicMock()
        # First wrap (target SNI) raises ConnectionResetError (DPI RST)
        # Second wrap (neutral SNI) succeeds
        mock_ssock_neutral = MagicMock()
        mock_ctx.wrap_socket.side_effect = [ConnectionResetError("Connection reset by peer"), mock_ssock_neutral]
        mock_ssl_ctx.return_value = mock_ctx

        stage, ssock = dpi_detector.evaluate_stage_c_sni_dpi("104.16.2.3", "dashboard.ngrok.com")
        self.assertEqual(stage.status, "BLOCKED")
        self.assertIn("SNI Filtering", stage.summary)
        self.assertTrue(stage.technical_info.get("neutral_test_passed"))
        self.assertIsNone(ssock)

    def test_stage_d_ssl_mitm_detected(self):
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = {
            "issuer": ((("organizationName", "Fortinet Enterprise CA"),),),
            "subject": ((("commonName", "dashboard.ngrok.com"),),),
        }

        stage = dpi_detector.evaluate_stage_d_ssl_mitm("dashboard.ngrok.com", mock_ssock, "104.16.2.3")
        self.assertEqual(stage.status, "WARN")
        self.assertIn("Corporate SSL Inspection", stage.summary)
        self.assertTrue(stage.technical_info.get("is_mitm"))

    def test_stage_d_ssl_clean(self):
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = {
            "issuer": ((("organizationName", "Let's Encrypt Authority X3"),),),
            "subject": ((("commonName", "dashboard.ngrok.com"),),),
        }

        stage = dpi_detector.evaluate_stage_d_ssl_mitm("dashboard.ngrok.com", mock_ssock, "104.16.2.3")
        self.assertEqual(stage.status, "PASS")
        self.assertIn("Trusted Public Certificate", stage.summary)
        self.assertFalse(stage.technical_info.get("is_mitm"))

    @patch("netools.libs.dpi_detector.evaluate_stage_a_dns")
    @patch("netools.libs.dpi_detector.evaluate_stage_b_tcp")
    @patch("netools.libs.dpi_detector.evaluate_stage_c_sni_dpi")
    def test_diagnose_domain_reachability_sni_block_flow(self, mock_c, mock_b, mock_a):
        # Stage A: Clean DNS
        mock_a.return_value = (
            dpi_detector.DiagnosticStage("A", "DNS", "PASS", 10.0, "Clean"),
            ["104.16.2.3"],
            ["104.16.2.3"],
        )
        # Stage B: Clean TCP
        mock_b.return_value = dpi_detector.DiagnosticStage("B", "TCP", "PASS", 20.0, "Connected")
        # Stage C: Blocked SNI DPI
        mock_c.return_value = (dpi_detector.DiagnosticStage("C", "TLS SNI", "BLOCKED", 25.0, "SNI Reset"), None)

        report = dpi_detector.diagnose_domain_reachability("dashboard.ngrok.com")
        self.assertEqual(report.verdict, "BLOCKED_SNI_DPI")
        self.assertEqual(report.blocked_stage_id, "C")
        self.assertEqual(report.recommended_action_type, "PROXY_VPN")
        self.assertIn("Sing-box Proxy Rotator", report.recommendation)
        self.assertEqual(report.stages["D"].status, "SKIPPED")


if __name__ == "__main__":
    unittest.main()
