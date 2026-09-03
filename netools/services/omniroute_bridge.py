"""
OmniRoute Bridge — Centralized DB injection, token TTL, and bulk session management.

All SQLite interactions with OmniRoute's storage.sqlite go through this module.
Provides reliable transaction handling, input validation, and TTL awareness.
"""

import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from netools.libs.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = Path.home() / ".omniroute" / "storage.sqlite"
_TTL_ACTIVE_THRESHOLD = 3600        # < 1 hour remaining → expiring_soon
_TOKEN_MAX_LENGTH = 16_384          # sanity cap for stored token

# Web-cookie providers use auth_type = "cookie" in OmniRoute (not "apikey")
_WEB_COOKIE_PROVIDERS = {
    "chatgpt-web", "chatgpt-web-codex", "claude-web", "deepseek-web",
    "grok-web", "gemini-web", "gemini-business", "perplexity-web",
    "blackbox-web", "muse-spark-web", "copilot-web", "copilot-m365-web",
    "t3-web", "inner-ai", "adapta-web", "lmarena", "yuanbao-web",
    "huggingchat", "poe-web", "venice-web", "v0-vercel-web",
    "kimi-web", "doubao-web", "zai-web", "zenmux-free",
    "tencent-aistudio-web", "tinycms-web", "notion-web",
    "hyperagent", "conol-web", "maxai", "uc",
}


# ---------------------------------------------------------------------------
# TTL Dataclass
# ---------------------------------------------------------------------------

@dataclass
class TokenTTL:
    """Computed time-to-live information for a JWT or session token."""

    status: str = "unknown"         # "active" | "expiring_soon" | "expired" | "unknown"
    remaining_secs: int = -1        # -1 = unknown
    expires_at: str = "N/A"         # ISO-ish human-readable or "N/A"
    label: str = "❓ Unknown"       # Ready-to-display label with emoji

    @property
    def is_usable(self) -> bool:
        """True when the token is still valid (active or expiring_soon)."""
        return self.status in ("active", "expiring_soon")


def compute_token_ttl(payload: Optional[Dict[str, Any]]) -> TokenTTL:
    """Derive TTL status from a decoded JWT payload's ``exp`` claim.

    Returns ``TokenTTL`` with human-readable label and remaining seconds.
    If ``exp`` is missing or not numeric, returns ``status='unknown'``.
    """
    if not payload:
        return TokenTTL()

    exp = payload.get("exp")
    if exp is None or not isinstance(exp, (int, float)):
        return TokenTTL()

    now = time.time()
    remaining = int(exp - now)
    expires_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(exp))

    if remaining <= 0:
        return TokenTTL(
            status="expired",
            remaining_secs=remaining,
            expires_at=expires_iso,
            label=f"❌ Expired ({expires_iso})",
        )

    # Human-friendly countdown
    hours, remainder = divmod(remaining, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        countdown = f"{hours}h {minutes}m"
    else:
        countdown = f"{minutes}m {secs}s"

    if remaining < _TTL_ACTIVE_THRESHOLD:
        status = "expiring_soon"
        label = f"⚠️ Habis {countdown} ({expires_iso})"
    else:
        status = "active"
        label = f"✅ Aktif ({countdown})"

    return TokenTTL(
        status=status,
        remaining_secs=remaining,
        expires_at=expires_iso,
        label=label,
    )


# ---------------------------------------------------------------------------
# Injection Result
# ---------------------------------------------------------------------------

@dataclass
class InjectionResult:
    """Outcome of a single ``inject_session_to_omniroute`` call."""

    success: bool = False
    provider: str = ""
    account: str = ""
    message: str = ""
    action: str = ""  # "inserted" | "updated" | "skipped" | "error"


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------

def get_db_path() -> Path:
    """Return the OmniRoute database path (centralised, testable)."""
    return _DEFAULT_DB_PATH


def _validate_token(token: str) -> Optional[str]:
    """Return an error message if *token* is invalid, else ``None``."""
    if not token or not token.strip():
        return "Token kosong"
    if len(token) > _TOKEN_MAX_LENGTH:
        return f"Token terlalu panjang ({len(token)} > {_TOKEN_MAX_LENGTH})"
    return None


def inject_session_to_omniroute(
    provider: str,
    token: str,
    name: str,
    *,
    db_path: Optional[Path] = None,
) -> InjectionResult:
    """Insert or update a single provider connection in OmniRoute's SQLite DB.

    Uses a context-manager for the connection and wraps the write in a
    transaction with automatic rollback on failure.
    """
    if not provider:
        return InjectionResult(success=False, provider=provider, account=name,
                               message="Provider kosong", action="error")

    err = _validate_token(token)
    if err:
        return InjectionResult(success=False, provider=provider, account=name,
                               message=err, action="error")

    db = db_path or get_db_path()
    if not db.exists():
        return InjectionResult(success=False, provider=provider, account=name,
                               message=f"Database OmniRoute tidak ditemukan: {db}",
                               action="error")

    now = time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        with sqlite3.connect(str(db)) as con:
            cur = con.cursor()
            cur.execute("SELECT id FROM provider_connections WHERE provider=?", (provider,))
            row = cur.fetchone()

            if row:
                conn_id = row[0]
                auth_type = "cookie" if provider in _WEB_COOKIE_PROVIDERS else "apikey"
                cur.execute(
                    "UPDATE provider_connections "
                    "SET api_key=?, auth_type=?, is_active=1, last_error=NULL, error_code=NULL, "
                    "    backoff_level=0, updated_at=? "
                    "WHERE id=?",
                    (token, auth_type, now, conn_id),
                )
                action = "updated"
            else:
                conn_id = str(uuid.uuid4())
                auth_type = "cookie" if provider in _WEB_COOKIE_PROVIDERS else "apikey"
                cur.execute(
                    "INSERT INTO provider_connections "
                    "  (id, provider, auth_type, name, is_active, api_key, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 1, ?, ?, ?)",
                    (conn_id, provider, auth_type, name, token, now, now),
                )
                action = "inserted"

            con.commit()
            log.info("OmniRoute inject %s: provider=%s account=%s", action, provider, name)
            return InjectionResult(
                success=True, provider=provider, account=name,
                message=f"Berhasil {action} {provider} ({name})",
                action=action,
            )

    except sqlite3.Error as exc:
        log.error("OmniRoute inject failed: %s", exc)
        return InjectionResult(
            success=False, provider=provider, account=name,
            message=f"Gagal menginjeksi ke OmniRoute: {exc}",
            action="error",
        )
    except Exception as exc:
        log.error("OmniRoute inject unexpected error: %s", exc)
        return InjectionResult(
            success=False, provider=provider, account=name,
            message=f"Error tak terduga: {exc}",
            action="error",
        )


def inject_bulk_sessions(
    sessions: List[Dict[str, Any]],
    *,
    db_path: Optional[Path] = None,
) -> List[InjectionResult]:
    """Inject multiple sessions into OmniRoute in a single DB transaction.

    All writes succeed or all are rolled back (atomic bulk).
    """
    if not sessions:
        return []

    db = db_path or get_db_path()
    if not db.exists():
        return [
            InjectionResult(
                success=False,
                provider=s.get("provider", "?"),
                account=s.get("account", "?"),
                message=f"Database OmniRoute tidak ditemukan: {db}",
                action="error",
            )
            for s in sessions
        ]

    results: List[InjectionResult] = []
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        with sqlite3.connect(str(db)) as con:
            cur = con.cursor()

            for s in sessions:
                provider = s.get("provider", "")
                token = s.get("token", "")
                name = s.get("account", "")

                if not provider:
                    results.append(InjectionResult(
                        success=False, provider=provider, account=name,
                        message="Provider kosong", action="error",
                    ))
                    continue

                err = _validate_token(token)
                if err:
                    results.append(InjectionResult(
                        success=False, provider=provider, account=name,
                        message=err, action="error",
                    ))
                    continue

                cur.execute("SELECT id FROM provider_connections WHERE provider=?", (provider,))
                row = cur.fetchone()

                if row:
                    conn_id = row[0]
                    bulk_auth_type = "cookie" if provider in _WEB_COOKIE_PROVIDERS else "apikey"
                    cur.execute(
                        "UPDATE provider_connections "
                        "SET api_key=?, auth_type=?, is_active=1, last_error=NULL, error_code=NULL, "
                        "    backoff_level=0, updated_at=? "
                        "WHERE id=?",
                        (token, bulk_auth_type, now, conn_id),
                    )
                    action = "updated"
                else:
                    conn_id = str(uuid.uuid4())
                    bulk_auth_type = "cookie" if provider in _WEB_COOKIE_PROVIDERS else "apikey"
                    cur.execute(
                        "INSERT INTO provider_connections "
                        "  (id, provider, auth_type, name, is_active, api_key, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, 1, ?, ?, ?)",
                        (conn_id, provider, bulk_auth_type, name, token, now, now),
                    )
                    action = "inserted"

                results.append(InjectionResult(
                    success=True, provider=provider, account=name,
                    message=f"Berhasil {action} {provider} ({name})",
                    action=action,
                ))

            con.commit()
            log.info("OmniRoute bulk inject: %d sessions processed", len(results))

    except sqlite3.Error as exc:
        log.error("OmniRoute bulk inject failed (rolling back): %s", exc)
        # Mark everything as failed
        results = [
            InjectionResult(
                success=False,
                provider=s.get("provider", "?"),
                account=s.get("account", "?"),
                message=f"Rollback: {exc}",
                action="error",
            )
            for s in sessions
        ]

    except Exception as exc:
        log.error("OmniRoute bulk inject unexpected error: %s", exc)
        results = [
            InjectionResult(
                success=False,
                provider=s.get("provider", "?"),
                account=s.get("account", "?"),
                message=f"Error tak terduga: {exc}",
                action="error",
            )
            for s in sessions
        ]

    return results
