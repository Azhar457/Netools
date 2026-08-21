"""
Unit tests for Local Network Threat, MiTM, Gateway ARP Spoofing, and Rogue DNS Detection.
"""

import unittest

from netools.libs import threat_detector
from netools.services import threat_service


class TestThreatDetector(unittest.TestCase):
    def test_01_arp_entry_and_parse(self):
        entries = threat_detector.parse_arp_table()
        self.assertIsInstance(entries, list)
        for e in entries:
            self.assertIsInstance(e.ip, str)
            self.assertIsInstance(e.mac, str)

    def test_02_detect_arp_spoofing_heuristics(self):
        # Scenario A: Clean Network
        clean_table = [
            threat_detector.ARPEntry(ip="192.168.1.1", mac="00:11:22:33:44:01", is_gateway=True),
            threat_detector.ARPEntry(ip="192.168.1.10", mac="00:11:22:33:44:10"),
            threat_detector.ARPEntry(ip="192.168.1.20", mac="00:11:22:33:44:20"),
        ]
        is_spoof, is_dup, gw_mac, reasons = threat_detector.detect_arp_spoofing(clean_table, gateway_ip="192.168.1.1")
        self.assertFalse(is_spoof)
        self.assertFalse(is_dup)
        self.assertEqual(gw_mac, "00:11:22:33:44:01")
        self.assertEqual(len(reasons), 0)

        # Scenario B: Bettercap / Ettercap ARP Poisoning Attack
        # Attacker at 192.168.1.150 responds with Gateway's MAC or sets Gateway IP to attacker's MAC
        poisoned_table = [
            threat_detector.ARPEntry(ip="192.168.1.1", mac="aa:bb:cc:dd:ee:ff", is_gateway=True),
            threat_detector.ARPEntry(ip="192.168.1.150", mac="aa:bb:cc:dd:ee:ff"),  # Attacker sharing GW MAC
            threat_detector.ARPEntry(ip="192.168.1.20", mac="00:11:22:33:44:20"),
        ]
        is_spoof, is_dup, gw_mac, reasons = threat_detector.detect_arp_spoofing(poisoned_table, gateway_ip="192.168.1.1")
        self.assertTrue(is_spoof)
        self.assertGreater(len(reasons), 0)
        self.assertIn("ARP Poisoning", reasons[0])

        # Scenario C: Multiple IP per non-gateway MAC anomaly
        dup_table = [
            threat_detector.ARPEntry(ip="192.168.1.1", mac="00:11:22:33:44:01", is_gateway=True),
            threat_detector.ARPEntry(ip="192.168.1.51", mac="00:aa:bb:cc:dd:ee"),
            threat_detector.ARPEntry(ip="192.168.1.52", mac="00:aa:bb:cc:dd:ee"),
            threat_detector.ARPEntry(ip="192.168.1.53", mac="00:aa:bb:cc:dd:ee"),
        ]
        is_spoof, is_dup, gw_mac, reasons = threat_detector.detect_arp_spoofing(dup_table, gateway_ip="192.168.1.1")
        self.assertFalse(is_spoof)
        self.assertTrue(is_dup)
        self.assertIn("Duplicate MAC", reasons[0])

    def test_03_gateway_tracker_mac_flapping(self):
        tracker = threat_detector.GatewayTracker()
        
        # Initial registration
        flapping1 = tracker.update_and_check_flapping("192.168.1.1", "00:11:22:33:44:55")
        self.assertFalse(flapping1)

        # Same MAC (normal periodic poll)
        flapping2 = tracker.update_and_check_flapping("192.168.1.1", "00:11:22:33:44:55")
        self.assertFalse(flapping2)

        # MAC changed! (MITM / ARP Spoof in progress)
        flapping3 = tracker.update_and_check_flapping("192.168.1.1", "aa:bb:cc:11:22:33")
        self.assertTrue(flapping3)

    def test_04_suspicious_local_dns_check(self):
        # 1. Clean public DNS
        susp1, _ = threat_detector.check_suspicious_local_dns("192.168.1.1", ["1.1.1.1", "8.8.8.8"])
        self.assertFalse(susp1)

        # 2. Clean Gateway DNS (DNS points to Router/Gateway)
        susp2, _ = threat_detector.check_suspicious_local_dns("192.168.1.1", ["192.168.1.1"])
        self.assertFalse(susp2)

        # 3. Suspicious Rogue Local DNS (DNS points to rogue local client)
        susp3, reasons3 = threat_detector.check_suspicious_local_dns("192.168.1.1", ["192.168.1.105"])
        self.assertTrue(susp3)
        self.assertGreater(len(reasons3), 0)
        self.assertIn("Rogue Local DNS", reasons3[0])

    def test_05_full_threat_scan(self):
        report = threat_detector.scan_local_network_threats()
        self.assertIsInstance(report, threat_detector.NetworkThreatReport)
        self.assertIn(report.threat_level, ["None", "Low", "Medium", "High", "Critical"])
        self.assertIsInstance(report.threats_found, list)
        self.assertIsInstance(report.arp_table, list)

    def test_06_threat_service(self):
        # Immediate scan
        rep = threat_service.scan_threats_now()
        self.assertIsNotNone(rep)

        latest = threat_service.get_latest_threat_report()
        self.assertEqual(latest.timestamp, rep.timestamp)

        # Register callback
        received_reports = []
        def listener(r):
            received_reports.append(r)

        threat_service.register_threat_callback(listener)
        threat_service.start_threat_monitor(interval_sec=0.1)
        import time
        time.sleep(0.3)
        threat_service.stop_threat_monitor()
        threat_service.unregister_threat_callback(listener)


if __name__ == "__main__":
    unittest.main()
