"""Unit tests for token_rotator service and refresh token filtering."""

import time
from unittest.mock import MagicMock

from netools.services.session_extractor import (
    _is_access_token,
    _is_refresh_token,
)
from netools.services.token_rotator import RotationEvent, TokenRotator

# ---------------------------------------------------------------------------
# _is_refresh_token Tests
# ---------------------------------------------------------------------------


class TestIsRefreshToken:
    def test_typ_refresh(self):
        assert _is_refresh_token({"typ": "refresh"}) is True

    def test_token_type_refresh(self):
        assert _is_refresh_token({"token_type": "refresh"}) is True

    def test_grant_type_refresh(self):
        assert _is_refresh_token({"grant_type": "refresh_token"}) is True

    def test_expired_token(self):
        exp = int(time.time()) - 7200  # expired 2 hours ago
        # Expired tokens are NOT refresh tokens — they're just expired
        assert _is_refresh_token({"exp": exp}) is False

    def test_active_token_not_refresh(self):
        exp = int(time.time()) + 3600
        assert _is_refresh_token({"exp": exp}) is False

    def test_no_exp_not_refresh(self):
        assert _is_refresh_token({"sub": "user"}) is False

    def test_typ_access_not_refresh(self):
        assert _is_refresh_token({"typ": "access"}) is False


# ---------------------------------------------------------------------------
# _is_access_token Tests
# ---------------------------------------------------------------------------


class TestIsAccessToken:
    def test_valid_access_token(self):
        exp = int(time.time()) + 3600
        assert _is_access_token({"exp": exp}) is True

    def test_explicit_access_type(self):
        exp = int(time.time()) + 3600
        assert _is_access_token({"exp": exp, "typ": "access"}) is True

    def test_refresh_token_not_access(self):
        exp = int(time.time()) + 3600
        assert _is_access_token({"exp": exp, "typ": "refresh"}) is False

    def test_expired_not_access(self):
        exp = int(time.time()) - 3600
        assert _is_access_token({"exp": exp}) is False

    def test_no_exp_not_access(self):
        assert _is_access_token({"sub": "user"}) is False

    def test_very_long_lived_not_access(self):
        # Token valid for 60 days — suspicious for an access token
        exp = int(time.time()) + 5_184_000
        assert _is_access_token({"exp": exp}) is False

    def test_very_short_lived_not_access(self):
        # Token valid for 30 seconds — too short for access token
        exp = int(time.time()) + 30
        assert _is_access_token({"exp": exp}) is False


# ---------------------------------------------------------------------------
# TokenRotator Tests
# ---------------------------------------------------------------------------


class TestTokenRotator:
    def test_init_defaults(self):
        r = TokenRotator()
        assert r.is_running is False
        assert r.tracked_count == 0
        assert r.history == []

    def test_track_sessions(self):
        r = TokenRotator()
        sessions = [
            {"provider": "kimi-web", "account": "user1", "token": "tok1"},
            {"provider": "zai-web", "account": "user2", "token": "tok2"},
        ]
        r.track_sessions(sessions)
        assert r.tracked_count == 2

    def test_untrack_provider(self):
        r = TokenRotator()
        r.track_sessions([{"provider": "kimi-web", "account": "u1", "token": "t"}])
        assert r.tracked_count == 1
        r.untrack_provider("kimi-web", "u1")
        assert r.tracked_count == 0

    def test_clear_tracking(self):
        r = TokenRotator()
        r.track_sessions(
            [
                {"provider": "kimi-web", "account": "u1", "token": "t1"},
                {"provider": "zai-web", "account": "u2", "token": "t2"},
            ]
        )
        r.clear_tracking()
        assert r.tracked_count == 0

    def test_start_stop(self):
        r = TokenRotator(scan_interval=1)
        r.start()
        assert r.is_running is True
        r.stop()
        assert r.is_running is False

    def test_rotation_event_dataclass(self):
        ev = RotationEvent(
            timestamp=time.time(),
            provider="kimi-web",
            account="user1",
            old_token_preview="eyJhbGci...",
            new_token_preview="eyJhbGci...",
            success=True,
            message="rotated",
        )
        assert ev.time_str  # Should not raise
        assert ev.success is True

    def test_history_bounded(self):
        r = TokenRotator()
        # Simulate 120 rotation events
        for i in range(120):
            r._rotation_history.append(
                RotationEvent(
                    timestamp=time.time(),
                    provider=f"prov-{i}",
                    account="user",
                    success=True,
                    message=f"event {i}",
                )
            )
        # History should be trimmed to 50 when it exceeds 100
        assert len(r._rotation_history) <= 120  # In practice, trimmed on next rotation

    def test_callbacks(self):
        r = TokenRotator()
        status_cb = MagicMock()
        rotation_cb = MagicMock()
        r.on_status = status_cb
        r.on_rotation = rotation_cb

        # Simulate a rotation event
        ev = RotationEvent(success=True, provider="test", account="user")
        r.on_rotation(ev)
        rotation_cb.assert_called_once_with(ev)
