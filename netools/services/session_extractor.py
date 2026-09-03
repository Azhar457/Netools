"""
Browser Session & Token Extractor for AI Web Providers (Brave, Chrome, Firefox).
Extracts LocalStorage tokens and cookies for Z.ai, Kimi, Claude, DeepSeek without opening DevTools.
"""

import base64
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


BROWSER_PATHS = {
    "Brave": [
        Path.home() / ".config/BraveSoftware/Brave-Browser/Default",
        Path.home() / ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser/Default",
    ],
    "Chrome": [
        Path.home() / ".config/google-chrome/Default",
        Path.home() / ".var/app/com.google.Chrome/config/google-chrome/Default",
    ],
    "Chromium": [
        Path.home() / ".config/chromium/Default",
        Path.home() / ".var/app/org.chromium.Chromium/config/chromium/Default",
    ],
    "Firefox": [
        Path.home() / ".mozilla/firefox",
        Path.home() / ".var/app/org.mozilla.firefox/.mozilla/firefox",
    ],
}


def decode_jwt_payload(token: str) -> Optional[Dict[str, Any]]:
    """Safely decode JWT payload without verification."""
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except Exception:
        return None


def extract_chromium_storage(profile_dir: Path) -> List[Dict[str, Any]]:
    """Scan Chromium/Brave LevelDB for JWT tokens and session data."""
    leveldb_dir = profile_dir / "Local Storage" / "leveldb"
    if not leveldb_dir.exists():
        return []

    found = []
    seen_tokens = set()

    files = list(leveldb_dir.glob("*.ldb")) + list(leveldb_dir.glob("*.log"))
    jwt_pattern = re.compile(rb"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")

    for f in files:
        try:
            raw = f.read_bytes()
            matches = jwt_pattern.findall(raw)
            for m in matches:
                token_str = m.decode("ascii")
                if token_str in seen_tokens:
                    continue
                seen_tokens.add(token_str)

                payload = decode_jwt_payload(token_str)
                if not payload:
                    continue

                email = payload.get("email") or ""
                uid = payload.get("id") or payload.get("user_id") or payload.get("sub") or ""

                # Identify Provider
                provider = "Unknown"
                if "chat.z.ai" in str(raw) or "z.ai" in str(raw):
                    provider = "zai-web"
                elif "kimi" in str(raw) or "moonshot" in str(raw):
                    provider = "kimi-web"
                elif "deepseek" in str(raw):
                    provider = "deepseek-web"

                # Check payload clues
                if not email and not uid:
                    continue

                label = f"{provider} ({email or uid})"
                found.append({
                    "provider": provider,
                    "label": label,
                    "account": email or str(uid),
                    "token": token_str,
                    "payload": payload,
                    "source": f.name,
                })
        except Exception:
            continue

    return found


def extract_all_browser_sessions() -> List[Dict[str, Any]]:
    """Extract all available AI sessions from installed browsers on the system."""
    all_sessions = []
    for browser_name, paths in BROWSER_PATHS.items():
        for p in paths:
            if p.exists():
                items = extract_chromium_storage(p)
                for it in items:
                    it["browser"] = browser_name
                    all_sessions.append(it)
                break  # Stop on first existing profile per browser

    # Sort so zai-web and kimi-web with real email come first
    def _sort_key(x):
        has_email = "@" in x.get("account", "")
        is_known = x.get("provider") in ("zai-web", "kimi-web", "deepseek-web")
        return (0 if (is_known and has_email) else (1 if is_known else 2), x.get("label", ""))

    all_sessions.sort(key=_sort_key)
    return all_sessions
