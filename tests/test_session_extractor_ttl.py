"""Unit tests for session_extractor TTL integration and provider identification."""

import base64
import json
import time

import pytest

from netools.services.omniroute_bridge import TokenTTL, compute_token_ttl
from netools.services.session_extractor import (
    _identify_provider_from_jwt,
    _is_refresh_token,
    _is_access_token,
    decode_jwt_payload,
    extract_chromium_storage,
    SUPPORTED_PROVIDERS,
    _COOKIE_DOMAIN_TO_PROVIDER,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jwt(payload: dict) -> str:
    """Create a fake JWT from a payload dict."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b'=').decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
    sig = "fake_signature"
    return f"{header}.{payload_b64}.{sig}"


# ---------------------------------------------------------------------------
# decode_jwt_payload Tests
# ---------------------------------------------------------------------------

class TestDecodeJWTPayload:
    def test_valid_jwt(self):
        payload = {"sub": "123", "email": "test@test.com", "exp": 9999999999}
        token = _make_jwt(payload)
        result = decode_jwt_payload(token)
        assert result is not None
        assert result["sub"] == "123"
        assert result["email"] == "test@test.com"

    def test_invalid_token(self):
        assert decode_jwt_payload("not-a-jwt") is None

    def test_empty_string(self):
        assert decode_jwt_payload("") is None

    def test_two_parts_only(self):
        assert decode_jwt_payload("header.payload") is None

    def test_malformed_base64(self):
        assert decode_jwt_payload("abc.def.ghi") is None


# ---------------------------------------------------------------------------
# Provider Identification Tests
# ---------------------------------------------------------------------------

class TestIdentifyProviderFromJWT:
    def test_chatgpt_web(self):
        payload = {"iss": "https://auth0.openai.com/", "sub": "user1"}
        raw = b"chatgpt data"
        assert _identify_provider_from_jwt(payload, raw) == "chatgpt-web"

    def test_chatgpt_web_openai_iss(self):
        payload = {"iss": "openai", "sub": "user1"}
        raw = b"some data"
        assert _identify_provider_from_jwt(payload, raw) == "chatgpt-web"

    def test_deepseek_web(self):
        payload = {"user": "deepseek-user", "id": "123"}
        raw = b"deepseek data"
        assert _identify_provider_from_jwt(payload, raw) == "deepseek-web"

    def test_kimi_web_app_id(self):
        payload = {"app_id": "kimi", "sub": "user1"}
        raw = b"kimi data"
        assert _identify_provider_from_jwt(payload, raw) == "kimi-web"

    def test_kimi_web_aud(self):
        payload = {"aud": ["kimi.ai"], "sub": "user1"}
        raw = b"kimi data"
        assert _identify_provider_from_jwt(payload, raw) == "kimi-web"

    def test_zai_web(self):
        payload = {"email": "user@test.com", "id": "123"}
        raw = b"z.ai platform data zai"
        assert _identify_provider_from_jwt(payload, raw) == "zai-web"

    def test_unknown_provider(self):
        payload = {"random": "data"}
        raw = b"unknown platform"
        assert _identify_provider_from_jwt(payload, raw) is None


# ---------------------------------------------------------------------------
# Refresh Token Detection Tests
# ---------------------------------------------------------------------------

class TestIsRefreshToken:
    def test_typ_refresh(self):
        assert _is_refresh_token({"typ": "refresh"}) is True

    def test_token_type_refresh(self):
        assert _is_refresh_token({"token_type": "refresh"}) is True

    def test_grant_type_refresh(self):
        assert _is_refresh_token({"grant_type": "refresh_token"}) is True

    def test_token_use_refresh(self):
        assert _is_refresh_token({"token_use": "refresh"}) is True

    def test_long_lived_token(self):
        exp = time.time() + 60 * 86400  # 60 days
        assert _is_refresh_token({"exp": exp}) is True

    def test_access_token_not_refresh(self):
        exp = time.time() + 3600  # 1 hour
        assert _is_refresh_token({"exp": exp}) is False

    def test_scope_refresh(self):
        assert _is_refresh_token({"scope": "offline_access refresh"}) is True


class TestIsAccessToken:
    def test_valid_access_token(self):
        exp = time.time() + 3600
        assert _is_access_token({"exp": exp}) is True

    def test_expired_token(self):
        exp = time.time() - 100
        assert _is_access_token({"exp": exp}) is False

    def test_refresh_token(self):
        exp = time.time() + 3600
        assert _is_access_token({"exp": exp, "typ": "refresh"}) is False

    def test_no_exp(self):
        assert _is_access_token({"sub": "user"}) is False


# ---------------------------------------------------------------------------
# TTL Integration Tests
# ---------------------------------------------------------------------------

class TestTTLIntegration:
    def test_ttl_active(self):
        exp = int(time.time() + 7200)  # 2 hours
        ttl = compute_token_ttl({"exp": exp})
        assert ttl.status == "active"
        assert ttl.remaining_secs > 0

    def test_ttl_expiring_soon(self):
        exp = int(time.time() + 1800)  # 30 min
        ttl = compute_token_ttl({"exp": exp})
        assert ttl.status == "expiring_soon"

    def test_ttl_expired(self):
        exp = int(time.time() - 100)
        ttl = compute_token_ttl({"exp": exp})
        assert ttl.status == "expired"

    def test_ttl_unknown(self):
        ttl = compute_token_ttl({"sub": "user"})
        assert ttl.status == "unknown"

    def test_ttl_none_payload(self):
        ttl = compute_token_ttl(None)
        assert ttl.status == "unknown"

    def test_ttl_is_usable(self):
        exp = int(time.time() + 7200)
        ttl = compute_token_ttl({"exp": exp})
        assert ttl.is_usable is True

    def test_ttl_expired_not_usable(self):
        exp = int(time.time() - 100)
        ttl = compute_token_ttl({"exp": exp})
        assert ttl.is_usable is False


# ---------------------------------------------------------------------------
# Supported Providers Tests
# ---------------------------------------------------------------------------

class TestSupportedProviders:
    def test_provider_count(self):
        # Should have 26 entries (25 providers + "all")
        assert len(SUPPORTED_PROVIDERS) == 26

    def test_all_provider_keys(self):
        keys = [k for k, _ in SUPPORTED_PROVIDERS]
        expected = {
            "all", "chatgpt-web", "claude-web", "deepseek-web", "gemini-web",
            "gemini-business", "grok-web", "kimi-web", "copilot-web",
            "copilot-m365-web", "perplexity-web", "blackbox-web",
            "muse-spark-web", "zai-web", "doubao-web", "t3-web",
            "inner-ai", "adapta-web", "lmarena", "yuanbao-web",
            "huggingchat", "poe-web", "venice-web", "v0-vercel-web",
            "zenmux-free", "custom",
        }
        assert set(keys) == expected

    def test_first_is_all(self):
        assert SUPPORTED_PROVIDERS[0][0] == "all"

    def test_last_is_custom(self):
        assert SUPPORTED_PROVIDERS[-1][0] == "custom"


# ---------------------------------------------------------------------------
# Cookie Domain Mapping Tests
# ---------------------------------------------------------------------------

class TestCookieDomainMapping:
    def test_chatgpt_mapping(self):
        assert _COOKIE_DOMAIN_TO_PROVIDER.get("chatgpt.com") == "chatgpt-web"

    def test_claude_mapping(self):
        assert _COOKIE_DOMAIN_TO_PROVIDER.get("claude.ai") == "claude-web"

    def test_gemini_mapping(self):
        assert _COOKIE_DOMAIN_TO_PROVIDER.get("google.com") == "gemini-web"

    def test_zai_mapping(self):
        assert _COOKIE_DOMAIN_TO_PROVIDER.get("chat.z.ai") == "zai-web"

    def test_all_expected_providers_mapped(self):
        """Ensure all 25 web providers have at least one domain mapping."""
        mapped = set(_COOKIE_DOMAIN_TO_PROVIDER.values())
        expected_all = {
            "chatgpt-web", "claude-web", "deepseek-web", "gemini-web",
            "gemini-business", "grok-web", "kimi-web", "copilot-web",
            "copilot-m365-web", "perplexity-web", "blackbox-web",
            "muse-spark-web", "zai-web", "doubao-web", "t3-web",
            "inner-ai", "adapta-web", "lmarena", "yuanbao-web",
            "huggingchat", "poe-web", "venice-web", "v0-vercel-web",
            "zenmux-free",
        }
        missing = expected_all - mapped
        assert not missing, f"Missing cookie domain mappings for: {missing}"
