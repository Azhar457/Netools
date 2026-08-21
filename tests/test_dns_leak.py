"""
Unit tests for DNS Leak, Transparent Proxy, NXDOMAIN Hijacking, and DNSSEC Integrity Engine.
"""

import socket
import struct
import unittest

from netools.libs import dns_leak
from netools.services import dns_leak_service


class TestDNSLeakEngine(unittest.TestCase):
    def test_01_build_packet_variations(self):
        # 1. Plain query packet
        pkt_plain = dns_leak.build_dns_query_packet("example.com", tx_id=0x1111, want_dnssec=False)
        self.assertTrue(len(pkt_plain) > 12)
        tx_id, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", pkt_plain[:12])
        self.assertEqual(tx_id, 0x1111)
        self.assertEqual(qd, 1)
        self.assertEqual(ar, 0)

        # 2. DNSSEC + ECS + Padding packet
        pkt_full = dns_leak.build_dns_query_packet(
            "test.org",
            tx_id=0x2222,
            want_dnssec=True,
            with_ecs=True,
            with_padding_len=16
        )
        tx_id, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", pkt_full[:12])
        self.assertEqual(tx_id, 0x2222)
        self.assertEqual(ar, 1)
        self.assertIn(b"test", pkt_full)

    def test_02_parse_extended_wireformat(self):
        # Construct synthetic DNS response with A record and EDNS0
        header = struct.pack(">HHHHHH", 0x1234, 0x8180, 1, 1, 0, 1)  # QR=1, RA=1, RD=1, NOERROR
        # Question: google.com
        question = b"\x06google\x03com\x00\x00\x01\x00\x01"
        # Answer: pointer to name, Type 1(A), Class 1, TTL 300, Rdlen 4, IP 142.250.190.46
        answer = b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 300, 4) + socket.inet_aton("142.250.190.46")
        # Additional: OPT RR with ECS (code 8) and Padding (code 12)
        ecs_opt = struct.pack(">HH", 8, 7) + struct.pack(">HBB", 1, 24, 0) + socket.inet_aton("198.51.100.0")[:3]
        pad_opt = struct.pack(">HH", 12, 4) + b"\x00\x00\x00\x00"
        opt_rdata = ecs_opt + pad_opt
        opt_rr = b"\x00" + struct.pack(">HHBBHH", 41, 4096, 0, 0, 0x8000, len(opt_rdata)) + opt_rdata

        raw_resp = header + question + answer + opt_rr
        parsed = dns_leak.parse_dns_response_extended(raw_resp)

        self.assertEqual(parsed.tx_id, 0x1234)
        self.assertEqual(parsed.rcode, 0)
        self.assertEqual(parsed.ips, ["142.250.190.46"])
        self.assertEqual(parsed.ttl_list, [300])
        self.assertTrue(parsed.has_edns)
        self.assertEqual(parsed.edns_udp_size, 4096)
        self.assertTrue(parsed.edns_has_do)
        self.assertTrue(parsed.has_ecs_leak)
        self.assertEqual(parsed.ecs_ip, "198.51.100.0")
        self.assertEqual(parsed.ecs_source_prefix, 24)
        self.assertTrue(parsed.has_padding)
        self.assertEqual(parsed.padding_len, 4)

    def test_03_sinkhole_and_private_ip_detection(self):
        self.assertTrue(dns_leak.is_private_or_sinkhole_ip("192.168.1.1"))
        self.assertTrue(dns_leak.is_private_or_sinkhole_ip("10.0.0.1"))
        self.assertTrue(dns_leak.is_private_or_sinkhole_ip("172.16.0.1"))
        self.assertTrue(dns_leak.is_private_or_sinkhole_ip("127.0.0.1"))
        self.assertTrue(dns_leak.is_private_or_sinkhole_ip("100.64.0.1"))
        self.assertFalse(dns_leak.is_private_or_sinkhole_ip("1.1.1.1"))
        self.assertFalse(dns_leak.is_private_or_sinkhole_ip("8.8.8.8"))

    def test_04_transparent_proxy_and_nxdomain_heuristics(self):
        # Test transparent proxy check (mock/live)
        res = dns_leak.check_transparent_dns_proxy(test_ip="192.0.2.53", timeout=0.3)
        self.assertIn("intercepted", res)
        self.assertIn("status", res)
        self.assertIn("risk_level", res)

        # Test NXDOMAIN check
        nx_res = dns_leak.check_nxdomain_hijack("1.1.1.1", sample_count=1, timeout=1.0)
        self.assertIn("hijacked", nx_res)
        self.assertIn("status", nx_res)

    def test_05_comprehensive_audit_and_scoring(self):
        report = dns_leak.run_comprehensive_dns_leak_audit("1.1.1.1", mode="ipv4", timeout=1.5)
        self.assertEqual(report["resolver"], "1.1.1.1")
        self.assertIsInstance(report["security_score"], int)
        self.assertGreaterEqual(report["security_score"], 0)
        self.assertLessEqual(report["security_score"], 100)
        self.assertIn("overall_rating", report)
        self.assertIn("transparent_proxy", report)
        self.assertIn("nxdomain_hijack", report)
        self.assertIn("dnssec", report)
        self.assertIn("edns_privacy", report)

    def test_06_service_layer(self):
        proxy_check = dns_leak_service.quick_transparent_proxy_check()
        self.assertIn("intercepted", proxy_check)

        prov_audit = dns_leak_service.audit_provider("cloudflare", mode="ipv4")
        self.assertIn("security_score", prov_audit)
        self.assertIn("overall_rating", prov_audit)

        sys_audit = dns_leak_service.audit_active_system_dns()
        self.assertIn("overall_score", sys_audit)
        self.assertIn("overall_rating", sys_audit)


if __name__ == "__main__":
    unittest.main()
