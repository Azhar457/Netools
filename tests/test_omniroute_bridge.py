"""Unit tests for netools.services.omniroute_bridge."""

import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from netools.services.omniroute_bridge import (
    InjectionResult,
    TokenTTL,
    compute_token_ttl,
    get_db_path,
    inject_bulk_sessions,
    inject_session_to_omniroute,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(path: Path) -> Path:
    """Create a minimal OmniRoute-compatible SQLite DB."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute(
        "CREATE TABLE IF NOT EXISTS provider_connections ("
        "  id TEXT PRIMARY KEY,"
        "  provider TEXT NOT NULL,"
        "  auth_type TEXT,"
        "  name TEXT,"
        "  is_active INTEGER DEFAULT 0,"
        "  api_key TEXT,"
        "  last_error TEXT,"
        "  error_code TEXT,"
        "  backoff_level INTEGER DEFAULT 0,"
        "  created_at TEXT,"
        "  updated_at TEXT"
        ")"
    )
    con.commit()
    con.close()
    return path


def _make_jwt(exp_offset: int = 3600) -> str:
    """Create a minimal fake JWT with the given exp offset from now."""
    import base64, json
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b'=').decode()
    payload_data = {"sub": "user@test.com", "exp": int(time.time()) + exp_offset}
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b'=').decode()
    sig = "fake_signature"
    return f"{header}.{payload}.{sig}"


# ---------------------------------------------------------------------------
# TokenTTL Tests
# ---------------------------------------------------------------------------

class TestTokenTTL:
    def test_is_usable_active(self):
        ttl = TokenTTL(status="active")
        assert ttl.is_usable is True

    def test_is_usable_expiring(self):
        ttl = TokenTTL(status="expiring_soon")
        assert ttl.is_usable is True

    def test_not_usable_expired(self):
        ttl = TokenTTL(status="expired")
        assert ttl.is_usable is False

    def test_not_usable_unknown(self):
        ttl = TokenTTL(status="unknown")
        assert ttl.is_usable is False


# ---------------------------------------------------------------------------
# compute_token_ttl Tests
# ---------------------------------------------------------------------------

class TestComputeTokenTTL:
    def test_none_payload(self):
        result = compute_token_ttl(None)
        assert result.status == "unknown"
        assert result.remaining_secs == -1
        assert result.is_usable is False

    def test_no_exp_claim(self):
        result = compute_token_ttl({"sub": "user@test.com"})
        assert result.status == "unknown"

    def test_active_token(self):
        # Token valid for 2 hours
        payload = {"exp": int(time.time()) + 7200}
        result = compute_token_ttl(payload)
        assert result.status == "active"
        assert result.remaining_secs > 7100
        assert "✅" in result.label

    def test_expiring_soon_token(self):
        # Token valid for 30 minutes (< 1 hour threshold)
        payload = {"exp": int(time.time()) + 1800}
        result = compute_token_ttl(payload)
        assert result.status == "expiring_soon"
        assert 1700 < result.remaining_secs < 1900
        assert "⚠️" in result.label

    def test_active_23h(self):
        # Token valid for 23 hours (> 1h threshold → active)
        payload = {"exp": int(time.time()) + 82800}
        result = compute_token_ttl(payload)
        assert result.status == "active"
        assert "✅" in result.label

    def test_expired_token(self):
        # Token expired 1 hour ago
        payload = {"exp": int(time.time()) - 3600}
        result = compute_token_ttl(payload)
        assert result.status == "expired"
        assert result.remaining_secs < 0
        assert "❌" in result.label

    def test_non_numeric_exp(self):
        result = compute_token_ttl({"exp": "not-a-number"})
        assert result.status == "unknown"


# ---------------------------------------------------------------------------
# inject_session_to_omniroute Tests
# ---------------------------------------------------------------------------

class TestInjectSession:
    def test_empty_provider(self):
        result = inject_session_to_omniroute("", "tok", "name")
        assert result.success is False
        assert result.action == "error"
        assert "Provider kosong" in result.message

    def test_empty_token(self):
        result = inject_session_to_omniroute("kimi-web", "", "name")
        assert result.success is False
        assert "Token kosong" in result.message

    def test_whitespace_token(self):
        result = inject_session_to_omniroute("kimi-web", "   ", "name")
        assert result.success is False
        assert "Token kosong" in result.message

    def test_oversized_token(self):
        result = inject_session_to_omniroute("kimi-web", "x" * 20000, "name")
        assert result.success is False
        assert "terlalu panjang" in result.message

    def test_db_not_found(self, tmp_path):
        fake_db = tmp_path / "nonexistent" / "storage.sqlite"
        result = inject_session_to_omniroute("kimi-web", "valid_token", "name",
                                              db_path=fake_db)
        assert result.success is False
        assert "tidak ditemukan" in result.message

    def test_insert_new_provider(self, tmp_path):
        db = _make_db(tmp_path / "storage.sqlite")
        result = inject_session_to_omniroute("kimi-web", "tok123", "User",
                                              db_path=db)
        assert result.success is True
        assert result.action == "inserted"
        assert "kimi-web" in result.message

        # Verify in DB
        con = sqlite3.connect(str(db))
        row = con.execute("SELECT provider, api_key, is_active FROM provider_connections").fetchone()
        con.close()
        assert row == ("kimi-web", "tok123", 1)

    def test_update_existing_provider(self, tmp_path):
        db = _make_db(tmp_path / "storage.sqlite")
        # Insert first
        inject_session_to_omniroute("kimi-web", "old_token", "OldUser", db_path=db)
        # Update
        result = inject_session_to_omniroute("kimi-web", "new_token", "NewUser", db_path=db)
        assert result.success is True
        assert result.action == "updated"

        # Verify
        con = sqlite3.connect(str(db))
        rows = con.execute("SELECT api_key FROM provider_connections WHERE provider='kimi-web'").fetchall()
        con.close()
        assert len(rows) == 1
        assert rows[0][0] == "new_token"

    def test_multiple_providers(self, tmp_path):
        db = _make_db(tmp_path / "storage.sqlite")
        inject_session_to_omniroute("kimi-web", "tok1", "Kimi", db_path=db)
        inject_session_to_omniroute("zai-web", "tok2", "Zai", db_path=db)

        con = sqlite3.connect(str(db))
        count = con.execute("SELECT COUNT(*) FROM provider_connections").fetchone()[0]
        con.close()
        assert count == 2


# ---------------------------------------------------------------------------
# inject_bulk_sessions Tests
# ---------------------------------------------------------------------------

class TestBulkInject:
    def test_empty_list(self):
        results = inject_bulk_sessions([])
        assert results == []

    def test_bulk_all_success(self, tmp_path):
        db = _make_db(tmp_path / "storage.sqlite")
        sessions = [
            {"provider": "kimi-web", "token": "tok1", "account": "Kimi"},
            {"provider": "zai-web", "token": "tok2", "account": "Zai"},
        ]
        results = inject_bulk_sessions(sessions, db_path=db)
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_bulk_with_invalid(self, tmp_path):
        db = _make_db(tmp_path / "storage.sqlite")
        sessions = [
            {"provider": "kimi-web", "token": "tok1", "account": "Kimi"},
            {"provider": "", "token": "tok2", "account": "Bad"},
            {"provider": "zai-web", "token": "", "account": "Empty"},
        ]
        results = inject_bulk_sessions(sessions, db_path=db)
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is False

    def test_bulk_partial_valid(self, tmp_path):
        db = _make_db(tmp_path / "storage.sqlite")
        sessions = [
            {"provider": "kimi-web", "token": "tok1", "account": "Kimi"},
            {"provider": "deepseek-web", "token": "tok2", "account": "DS"},
        ]
        results = inject_bulk_sessions(sessions, db_path=db)
        ok = sum(1 for r in results if r.success)
        assert ok == 2

    def test_bulk_db_not_found(self, tmp_path):
        fake_db = tmp_path / "missing.sqlite"
        sessions = [
            {"provider": "kimi-web", "token": "tok1", "account": "Kimi"},
        ]
        results = inject_bulk_sessions(sessions, db_path=fake_db)
        assert len(results) == 1
        assert results[0].success is False


# ---------------------------------------------------------------------------
# get_db_path Tests
# ---------------------------------------------------------------------------

class TestGetDbPath:
    def test_returns_path(self):
        result = get_db_path()
        assert isinstance(result, Path)
        assert result.name == "storage.sqlite"
