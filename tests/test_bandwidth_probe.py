"""Unit tests for the lightweight bandwidth probe in netools.libs.net."""
import unittest

from netools.libs.net import measure_bandwidth_mbps


class TestBandwidthProbe(unittest.TestCase):
    def test_returns_none_or_float(self):
        # Localhost port 1 should fail fast (no service listening)
        result = measure_bandwidth_mbps(host="127.0.0.1", port=1, timeout_s=1.0)
        self.assertTrue(result is None or isinstance(result, float))

    def test_zero_timeout_returns_none(self):
        # Zero timeout must not hang; should return None gracefully
        result = measure_bandwidth_mbps(host="127.0.0.1", port=80, timeout_s=0.0)
        self.assertIsNone(result)

    def test_unreachable_host_returns_none(self):
        # Reserved/blackhole address; should fail fast
        result = measure_bandwidth_mbps(host="0.0.0.0", port=80, timeout_s=0.5)
        self.assertIsNone(result)
