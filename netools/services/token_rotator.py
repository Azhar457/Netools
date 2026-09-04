"""
Token Auto-Rotator — Monitors token expiry and automatically captures fresh tokens.

When a provider's access token is about to expire, the rotator:
1. Re-scans the browser's LocalStorage for a fresh token
2. If a newer token is found, injects it into OmniRoute
3. Logs the rotation event

This solves the common issue where browser tokens appear "expired" in
Netools even though the browser session is still valid — the browser
silently refreshes tokens via cookies, but LevelDB may hold an older copy.
"""

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from netools.libs.logger import get_logger
from netools.services.omniroute_bridge import (
    compute_token_ttl,
    inject_session_to_omniroute,
)
from netools.services.session_extractor import extract_all_browser_sessions

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_SCAN_INTERVAL = 30  # seconds between scans
_RESCAN_THRESHOLD = 300  # re-scan when < 5 min remaining
_MAX_ROTATIONS_PER_HOUR = 20  # rate limit rotations
_ROTATION_COOLDOWN = 60  # min seconds between rotations per provider


# ---------------------------------------------------------------------------
# Rotation Event
# ---------------------------------------------------------------------------


@dataclass
class RotationEvent:
    """Record of a single token rotation."""

    timestamp: float = 0.0
    provider: str = ""
    account: str = ""
    old_token_preview: str = ""  # first 20 chars
    new_token_preview: str = ""
    success: bool = False
    message: str = ""

    @property
    def time_str(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime(self.timestamp))


# ---------------------------------------------------------------------------
# Token Auto-Rotator
# ---------------------------------------------------------------------------


class TokenRotator:
    """Background service that monitors token TTL and auto-rotates expiring tokens.

    Usage::

        rotator = TokenRotator()
        rotator.on_rotation = my_callback  # Optional: called on each rotation
        rotator.start()
        # ... later ...
        rotator.stop()
    """

    def __init__(
        self,
        scan_interval: int = _DEFAULT_SCAN_INTERVAL,
        threshold: int = _RESCAN_THRESHOLD,
    ):
        self.scan_interval = scan_interval
        self.threshold = threshold  # seconds remaining to trigger re-scan

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # State
        self._tracked: Dict[str, Dict[str, Any]] = {}  # provider → session info
        self._rotation_history: List[RotationEvent] = []
        self._last_rotation: Dict[str, float] = {}  # provider → timestamp
        self._rotation_count_hour = 0
        self._hour_start = time.time()

        # Callback
        self.on_rotation: Optional[Callable[[RotationEvent], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None

    # ── Public API ──

    def start(self):
        """Start the background rotation monitor."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info("Token rotator started (interval=%ds, threshold=%ds)", self.scan_interval, self.threshold)
        if self.on_status:
            self.on_status("🔄 Auto-rotator aktif — memantau token...")

    def stop(self):
        """Stop the background rotation monitor."""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        log.info("Token rotator stopped")
        if self.on_status:
            self.on_status("⏹️ Auto-rotator dihentikan.")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def history(self) -> List[RotationEvent]:
        return list(self._rotation_history)

    @property
    def tracked_count(self) -> int:
        return len(self._tracked)

    def track_sessions(self, sessions: List[Dict[str, Any]]):
        """Update the set of sessions being monitored.

        Call this after a manual scan or after the rotator finds new tokens.
        """
        for s in sessions:
            key = f"{s.get('provider', '')}:{s.get('account', '')}"
            self._tracked[key] = s

    def untrack_provider(self, provider: str, account: str = ""):
        """Stop tracking a specific provider."""
        key = f"{provider}:{account}"
        self._tracked.pop(key, None)

    def clear_tracking(self):
        """Stop tracking all providers."""
        self._tracked.clear()

    def force_scan_now(self):
        """Trigger an immediate scan (outside the normal interval)."""
        if self._running:
            self._stop_event.set()  # interrupt sleep
            threading.Thread(target=self._scan_cycle, daemon=True).start()

    # ── Internal ──

    def _loop(self):
        """Main rotation loop."""
        while self._running:
            self._stop_event.clear()
            self._scan_cycle()
            # Sleep in small increments so we can be interrupted
            for _ in range(self.scan_interval * 2):
                if self._stop_event.is_set() or not self._running:
                    break
                time.sleep(0.5)

    def _scan_cycle(self):
        """One scan cycle: check TTL, re-scan, rotate if needed."""
        if not self._tracked:
            return

        # Rate limiting: max N rotations per hour
        now = time.time()
        if now - self._hour_start > 3600:
            self._rotation_count_hour = 0
            self._hour_start = now

        for key, tracked in list(self._tracked.items()):
            if not self._running:
                break

            provider = tracked.get("provider", "")
            account = tracked.get("account", "")
            current_token = tracked.get("token", "")
            payload = tracked.get("payload")
            ttl = tracked.get("ttl")

            # Compute fresh TTL
            if payload:
                ttl = compute_token_ttl(payload)
                tracked["ttl"] = ttl

            # Check if rotation is needed
            needs_rotation = False
            if ttl and ttl.status == "expired":
                needs_rotation = True
                reason = "expired"
            elif ttl and ttl.status == "expiring_soon" and ttl.remaining_secs < self.threshold:
                needs_rotation = True
                reason = f"expiring in {ttl.remaining_secs}s"
            elif not ttl or ttl.status == "unknown":
                # Unknown TTL — still try to find a fresher token periodically
                needs_rotation = True
                reason = "unknown TTL"
            else:
                continue  # Token is fine

            if not needs_rotation:
                continue

            # Cooldown check
            last_rot = self._last_rotation.get(key, 0)
            if now - last_rot < _ROTATION_COOLDOWN:
                continue

            # Rate limit check
            if self._rotation_count_hour >= _MAX_ROTATIONS_PER_HOUR:
                log.warning("Token rotator: rate limit reached (%d/hr)", _MAX_ROTATIONS_PER_HOUR)
                break

            log.info("Token rotator: %s (%s) needs rotation — %s", provider, account, reason)
            if self.on_status:
                self.on_status(f"🔄 Memutar token {provider} ({account}) — {reason}...")

            # Re-scan browser for fresh token
            fresh = self._find_fresh_token(provider, account, current_token)
            if fresh:
                self._inject_fresh(tracked, fresh, reason)
                self._last_rotation[key] = time.time()
                self._rotation_count_hour += 1
            else:
                log.info("Token rotator: no fresher token found for %s", provider)

    def _find_fresh_token(
        self,
        provider: str,
        account: str,
        current_token: str,
    ) -> Optional[Dict[str, Any]]:
        """Re-scan browser storage for a fresher token for the given provider."""
        try:
            sessions = extract_all_browser_sessions(
                browser_filter="all",
                provider_filter=provider,
            )
        except Exception as exc:
            log.error("Token rotator scan failed: %s", exc)
            return None

        # Find sessions for this account
        candidates = [s for s in sessions if s.get("account") == account or s.get("provider") == provider]

        if not candidates:
            return None

        # Prefer tokens that are different from current and have better TTL
        best = None
        best_ttl_remaining = -999

        for s in candidates:
            if s["token"] == current_token:
                continue  # Same token, skip

            s_ttl = s.get("ttl")
            if s_ttl and s_ttl.status in ("active", "expiring_soon"):
                remaining = s_ttl.remaining_secs if s_ttl.remaining_secs > 0 else 0
                if remaining > best_ttl_remaining:
                    best = s
                    best_ttl_remaining = remaining

        # If no better token found, accept any different token
        if not best and candidates:
            for s in candidates:
                if s["token"] != current_token:
                    best = s
                    break

        return best

    def _inject_fresh(
        self,
        tracked: Dict[str, Any],
        fresh: Dict[str, Any],
        reason: str,
    ):
        """Inject a fresh token into OmniRoute and update tracking."""
        provider = fresh.get("provider", tracked.get("provider", ""))
        account = fresh.get("account", tracked.get("account", ""))
        old_token = tracked.get("token", "")
        new_token = fresh.get("token", "")

        result = inject_session_to_omniroute(provider=provider, token=new_token, name=account)

        event = RotationEvent(
            timestamp=time.time(),
            provider=provider,
            account=account,
            old_token_preview=old_token[:20] + "..." if len(old_token) > 20 else old_token,
            new_token_preview=new_token[:20] + "..." if len(new_token) > 20 else new_token,
            success=result.success,
            message=f"{reason}: {result.message}",
        )
        self._rotation_history.append(event)

        # Keep history bounded
        if len(self._rotation_history) > 100:
            self._rotation_history = self._rotation_history[-50:]

        if result.success:
            # Update tracked with new token
            tracked["token"] = new_token
            tracked["payload"] = fresh.get("payload")
            tracked["ttl"] = fresh.get("ttl")
            log.info("Token rotator: rotated %s (%s) — %s", provider, account, reason)
            if self.on_status:
                self.on_status(f"✅ Token {provider} ({account}) berhasil diputar!")
        else:
            log.warning("Token rotator: failed to inject %s: %s", provider, result.message)
            if self.on_status:
                self.on_status(f"⚠️ Gagal memutar token {provider}: {result.message}")

        if self.on_rotation:
            try:
                self.on_rotation(event)
            except Exception:
                pass
