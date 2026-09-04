"""
Unit tests for the DNS Cache Poisoning Guard.

Covers:
  - _is_bogon detection (private, loopback, CGNAT, public)
  - PoisonAlert dataclass serialization
  - check_cache_poisoning with monkeypatched resolver (no network needed)
  - PoisonGuard daemon lifecycle (start/stop/no-hang)
  - _is_disabled env override
"""

import time

import pytest

from netools.services.cache_poison_guard import (
    PoisonAlert,
    PoisonGuard,
    _is_bogon,
    _is_disabled,
    check_cache_poisoning,
)

# ---------------------------------------------------------------------------
# _is_bogon
# ---------------------------------------------------------------------------


class TestIsBogon:
    @pytest.mark.parametrize(
        "ip,expected",
        [
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
        ],
    )
    def test_bogon_detection(self, ip, expected):
        assert _is_bogon(ip) is expected


# ---------------------------------------------------------------------------
# PoisonAlert
# ---------------------------------------------------------------------------


class TestPoisonAlert:
    def test_to_dict(self):
        alert = PoisonAlert(
            hostname="evil.test",
            resolved_ips=["10.0.0.1"],
            poisoned=True,
            resolver="fakeDns",
        )
        d = alert.to_dict()
        assert d["hostname"] == "evil.test"
        assert d["resolved_ips"] == ["10.0.0.1"]
        assert d["poisoned"] is True
        assert d["resolver"] == "fakeDns"


# ---------------------------------------------------------------------------
# check_cache_poisoning (monkeypatched resolver — no network)
# ---------------------------------------------------------------------------


class TestCheckCachePoisoning:
    @pytest.fixture
    def patch_resolver(self, monkeypatch):
        """Patch _resolve_current to return controlled IPs."""
        fake_ips = {
            "www.cloudflare.com": ["1.1.1.1"],
            "dns.google": ["8.8.8.8"],
            "one.one.one.one": ["1.1.1.1"],
        }

        def fake_resolve(hostname):
            return (fake_ips.get(hostname, []), "fakeResolver")

        import netools.services.cache_poison_guard as mod

        monkeypatch.setattr(mod, "_resolve_current", fake_resolve)
        return fake_ips

    @pytest.fixture(autouse=True)
    def enable_guard(self, monkeypatch):
        monkeypatch.setenv("NETOOLS_POISON_GUARD", "1")

    def test_all_clean(self, patch_resolver):
        alerts = check_cache_poisoning()
        assert len(alerts) == 3
        assert all(not a.poisoned for a in alerts)
        assert all(a.resolved_ips for a in alerts)

    def test_poisoned_detected(self, monkeypatch, patch_resolver):
        # Override one canary to resolve to a bogon
        patch_resolver["www.cloudflare.com"] = ["192.168.1.1"]  # private!

        alerts = check_cache_poisoning()
        poisoned = [a for a in alerts if a.poisoned]
        assert len(poisoned) == 1
        assert poisoned[0].hostname == "www.cloudflare.com"
        assert "192.168.1.1" in poisoned[0].resolved_ips

    def test_disabled_returns_empty(self, monkeypatch):
        monkeypatch.setenv("NETOOLS_POISON_GUARD", "0")
        alerts = check_cache_poisoning()
        assert alerts == []


# ---------------------------------------------------------------------------
# PoisonGuard daemon lifecycle
# ---------------------------------------------------------------------------


class TestPoisonGuardDaemon:
    @pytest.fixture(autouse=True)
    def enable_guard(self, monkeypatch):
        monkeypatch.setenv("NETOOLS_POISON_GUARD", "1")

    def test_start_stop(self, monkeypatch):
        triggered = []

        def fake_check():
            triggered.append(time.time())
            from netools.services.cache_poison_guard import PoisonAlert

            return [PoisonAlert("test", ["1.1.1.1"], False)]

        import netools.services.cache_poison_guard as mod

        monkeypatch.setattr(mod, "check_cache_poisoning", fake_check)

        guard = PoisonGuard(interval=0.5)
        guard.start()
        time.sleep(1.2)
        guard.stop()

        assert guard._thread is not None
        assert not guard._thread.is_alive()
        assert len(triggered) >= 2  # at least 2 cycles in 1.2s

    def test_check_once(self, monkeypatch):
        def fake_check():
            return [PoisonAlert("x", ["8.8.8.8"], False)]

        import netools.services.cache_poison_guard as mod

        monkeypatch.setattr(mod, "check_cache_poisoning", fake_check)

        guard = PoisonGuard(interval=999)
        result = guard.check_once()
        assert result[0].hostname == "x"

    def test_no_hang_on_exit(self, monkeypatch):
        """Ensure stop() returns quickly even mid-cycle."""

        def slow_check():
            time.sleep(3)
            from netools.services.cache_poison_guard import PoisonAlert

            return [PoisonAlert("slow", [], False)]

        import netools.services.cache_poison_guard as mod

        monkeypatch.setattr(mod, "check_cache_poisoning", slow_check)

        guard = PoisonGuard(interval=0.1)
        guard.start()
        time.sleep(0.15)
        t0 = time.time()
        guard.stop()
        elapsed = time.time() - t0
        # stop should wait max 2s (join timeout) but the daemon is blocked
        # in slow_check — verify it exits cleanly within timeout
        assert elapsed < 2.5


# ---------------------------------------------------------------------------
# _is_disabled
# ---------------------------------------------------------------------------


class TestIsDisabled:
    def test_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv("NETOOLS_POISON_GUARD", raising=False)
        assert _is_disabled() is False

    def test_disabled_via_env(self, monkeypatch):
        monkeypatch.setenv("NETOOLS_POISON_GUARD", "0")
        assert _is_disabled() is True

    def test_enabled_via_env(self, monkeypatch):
        monkeypatch.setenv("NETOOLS_POISON_GUARD", "1")
        assert _is_disabled() is False
