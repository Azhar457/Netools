"""Tests for the DoH-on-laptop fix: host:port validation + forwarder addressing."""

from netools.adapters.systemd_dns import _split_host_port, _validate_ips


def test_split_host_port():
    assert _split_host_port("1.2.3.4") == ("1.2.3.4", None)
    assert _split_host_port("1.2.3.4:5353") == ("1.2.3.4", "5353")
    assert _split_host_port("::1") == ("::1", None)
    assert _split_host_port("[::1]:5353") == ("::1", "5353")
    assert _split_host_port("2606:4700:4700::1111") == ("2606:4700:4700::1111", None)


def test_validate_ips_accepts_port():
    assert _validate_ips(["127.0.0.1:5353", "8.8.8.8"]) == ["127.0.0.1:5353", "8.8.8.8"]
    assert _validate_ips(["[::1]:5353"]) == ["[::1]:5353"]


def test_validate_ips_rejects_garbage():
    assert _validate_ips(["example.com", "1.2.3.4:notaport", ""]) == []
    # valid bare IPv6 is kept (rejected later only from ipv4.dns by the v4/v6 split)
    assert _validate_ips(["fe80::1"]) == ["fe80::1"]


def test_doh_forwarder_returns_ported_localhost():
    """compute_provider_ips must return 127.0.0.1:DOH_PROXY_PORT for DoH,
    never a bare 127.0.0.1 (dead port 53) nor the raw doh_url."""
    from netools.config import DOH_PROXY_PORT
    from netools.gui.view_dns import DNSView

    # Build a minimal fake to call the pure path without a running GUI
    class FakeApp:
        def show_toast(self, *a, **k):
            pass

    class FakeView:
        main_app = FakeApp()
        providers = {
            "alidns": {"name": "AliDNS", "doh_url": "https://dns.alidns.com/dns-query",
                       "ipv4": ["223.5.5.5"], "ipv6": []}
        }

    v = FakeView()
    # Bind the unbound method to our duck-typed fake (only uses .main_app / .providers)
    ips = DNSView.compute_provider_ips.__get__(v)(v.providers["alidns"], "alidns", "DoH (HTTPS)")
    # When the forwarder cannot actually bind in CI, it falls back to ipv4.
    # The key assertion: when started, it is ported localhost, never a URL.
    if ips and ips[0].startswith("127.0.0.1"):
        assert ips[0] == f"127.0.0.1:{DOH_PROXY_PORT}"
    else:
        # fallback path returned the provider IPv4 (acceptable when no forwarder)
        assert ips[0] in ("223.5.5.5",)
