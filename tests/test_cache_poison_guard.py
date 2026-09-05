"""
Unit tests for the DNS Cache Poisoning Guard using standard unittest.
"""

import os
import time
import unittest
from unittest.mock import patch

from netools.services.cache_poison_guard import (
    PoisonAlert,
    PoisonGuard,
    _is_bogon,
    _is_disabled,
    check_cache_poisoning,
)


class TestIsBogon(unittest.TestCase):
    def test_bogon_detection(self):
        cases = [
            ("1.1.1.1", False),
            ("8.8.8.8", False),
            ("2606:4700:4700::1111", False),
            ("10.0.0.1", True),
            ("127.0.0.1", True),
            ("172.16.0.5", True),
            ("192.168.1.1", True),
            ("169.254.1.1", True),  # link-local
            ("0.0.0.0", True),  # unspecified
            ("100.64.0.1", True),  # CGNAT
            ("224.0.0.1", True),  # multicast
            ("not-an-ip", False),
            ("", False),
        ]
        for ip, expected in cases:
            with self.subTest(ip=ip):
                self.assertEqual(_is_bogon(ip), expected)


class TestPoisonAlert(unittest.TestCase):
    def test_to_dict(self):
        alert = PoisonAlert(
            hostname="evil.test",
            resolved_ips=["10.0.0.1"],
            poisoned=True,
            resolver="fakeDns",
        )
        d = alert.to_dict()
        self.assertEqual(d["hostname"], "evil.test")
        self.assertEqual(d["resolved_ips"], ["10.0.0.1"])
        self.assertTrue(d["poisoned"])
        self.assertEqual(d["resolver"], "fakeDns")


class TestCheckCachePoisoning(unittest.TestCase):
    def setUp(self):
        self.orig_env = os.getenv("NETOOLS_POISON_GUARD")
        os.environ["NETOOLS_POISON_GUARD"] = "1"

    def tearDown(self):
        if self.orig_env is not None:
            os.environ["NETOOLS_POISON_GUARD"] = self.orig_env
        else:
            os.environ.pop("NETOOLS_POISON_GUARD", None)

    @patch("netools.services.cache_poison_guard._resolve_current")
    def test_all_clean(self, mock_resolve):
        fake_ips = {
            "www.cloudflare.com": (["1.1.1.1"], "fakeResolver"),
            "dns.google": (["8.8.8.8"], "fakeResolver"),
            "one.one.one.one": (["1.1.1.1"], "fakeResolver"),
        }
        mock_resolve.side_effect = lambda host: fake_ips.get(host, ([], "fakeResolver"))

        alerts = check_cache_poisoning()
        self.assertEqual(len(alerts), 3)
        self.assertTrue(all(not a.poisoned for a in alerts))
        self.assertTrue(all(a.resolved_ips for a in alerts))

    @patch("netools.services.cache_poison_guard._resolve_current")
    def test_poisoned_detected(self, mock_resolve):
        fake_ips = {
            "www.cloudflare.com": (["192.168.1.1"], "fakeResolver"),
            "dns.google": (["8.8.8.8"], "fakeResolver"),
            "one.one.one.one": (["1.1.1.1"], "fakeResolver"),
        }
        mock_resolve.side_effect = lambda host: fake_ips.get(host, ([], "fakeResolver"))

        alerts = check_cache_poisoning()
        poisoned = [a for a in alerts if a.poisoned]
        self.assertEqual(len(poisoned), 1)
        self.assertEqual(poisoned[0].hostname, "www.cloudflare.com")
        self.assertIn("192.168.1.1", poisoned[0].resolved_ips)

    def test_disabled_returns_empty(self):
        os.environ["NETOOLS_POISON_GUARD"] = "0"
        alerts = check_cache_poisoning()
        self.assertEqual(alerts, [])


class TestPoisonGuardDaemon(unittest.TestCase):
    def setUp(self):
        self.orig_env = os.getenv("NETOOLS_POISON_GUARD")
        os.environ["NETOOLS_POISON_GUARD"] = "1"

    def tearDown(self):
        if self.orig_env is not None:
            os.environ["NETOOLS_POISON_GUARD"] = self.orig_env
        else:
            os.environ.pop("NETOOLS_POISON_GUARD", None)

    @patch("netools.services.cache_poison_guard.check_cache_poisoning")
    def test_start_stop(self, mock_check):
        triggered = []

        def fake_check():
            triggered.append(time.time())
            return [PoisonAlert("test", ["1.1.1.1"], False)]

        mock_check.side_effect = fake_check

        guard = PoisonGuard(interval=0.2)
        guard.start()
        time.sleep(0.6)
        guard.stop()

        self.assertIsNotNone(guard._thread)
        self.assertFalse(guard._thread.is_alive())
        self.assertGreaterEqual(len(triggered), 2)

    @patch("netools.services.cache_poison_guard.check_cache_poisoning")
    def test_check_once(self, mock_check):
        mock_check.return_value = [PoisonAlert("x", ["8.8.8.8"], False)]
        guard = PoisonGuard(interval=999)
        result = guard.check_once()
        self.assertEqual(result[0].hostname, "x")


class TestIsDisabled(unittest.TestCase):
    def test_enabled_by_default(self):
        os.environ.pop("NETOOLS_POISON_GUARD", None)
        self.assertFalse(_is_disabled())

    def test_disabled_via_env(self):
        os.environ["NETOOLS_POISON_GUARD"] = "0"
        self.assertTrue(_is_disabled())

    def test_enabled_via_env(self):
        os.environ["NETOOLS_POISON_GUARD"] = "1"
        self.assertFalse(_is_disabled())


if __name__ == "__main__":
    unittest.main()
