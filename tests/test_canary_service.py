import unittest

from netools.services.canary_service import (
    STATUS_INTERCEPTED,
    VERDICT_INTERCEPTED,
    CanaryProbe,
    CanaryRunResult,
    add_custom_canary,
    get_all_canary_hostnames,
    remove_custom_canary,
)


class TestCanaryServiceBasics(unittest.TestCase):
    def test_builtin_has_mozilla(self):
        ids = [c["id"] for c in get_all_canary_hostnames()]
        self.assertIn("mozilla_firefox_doh", ids)

    def test_custom_add_remove(self):
        self.assertTrue(add_custom_canary("test.my.canary"))
        self.assertIn("test.my.canary", [c["hostname"] for c in get_all_canary_hostnames()])
        self.assertTrue(remove_custom_canary("test.my.canary"))
        self.assertNotIn("test.my.canary", [c["hostname"] for c in get_all_canary_hostnames()])

    def test_result_structs(self):
        p = CanaryProbe(
            hostname="x.com",
            resolver="system",
            status=STATUS_INTERCEPTED,
            rcode="NOERROR",
            latency_ms=42.0,
            answer_summary="A=1.2.3.4",
        )
        self.assertEqual(p.status, STATUS_INTERCEPTED)
        d = p.to_dict()
        self.assertIn("hostname", d)

    def test_verdict_aggregation(self):
        r = CanaryRunResult(
            timestamp=0.0,
            precheck_ok=True,
            verdict=VERDICT_INTERCEPTED,
            intercepted_domains=["use-application-dns.net"],
            clean_domains=[],
        )
        d = r.to_dict()
        self.assertEqual(d["verdict"], VERDICT_INTERCEPTED)


if __name__ == "__main__":
    unittest.main()
