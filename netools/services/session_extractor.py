"""
Browser Session & Token Extractor for AI Web Providers (Brave, Chrome, Firefox).
Extracts LocalStorage tokens and cookies with granular filtering and deduplication.
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

SUPPORTED_PROVIDERS = [
    ("all", "Semua Provider AI"),
    ("zai-web", "Z.ai Web (chat.z.ai)"),
    ("kimi-web", "Kimi Web (kimi.ai)"),
    ("deepseek-web", "DeepSeek Web (chat.deepseek.com)"),
    ("custom", "Kustom (Domain / Kata Kunci)"),
]


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


def extract_chromium_storage(
    profile_dir: Path,
    browser_name: str,
    provider_filter: str = "all",
    custom_keyword: str = "",
) -> List[Dict[str, Any]]:
    """Scan Chromium/Brave LevelDB for JWT tokens and session data with precise domain matching."""
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

                payload = decode_jwt_payload(token_str)
                if not payload:
                    continue

                # Precise Identification
                prov = "unknown"
                account = ""

                # 1. Kimi Web (aud: ["kimi.ai"], app_id: "kimi")
                if payload.get("app_id") == "kimi" or "kimi.ai" in payload.get("aud", []):
                    prov = "kimi-web"
                    account = payload.get("sub", "")
                    if payload.get("typ") == "refresh":
                        continue  # Keep only access token

                # 2. Z.ai Web (id + email only in payload)
                elif "email" in payload and "id" in payload and len(payload) <= 3:
                    prov = "zai-web"
                    account = payload.get("email", "")

                # 3. DeepSeek
                elif "deepseek" in str(raw).lower() and ("user" in payload or "id" in payload):
                    prov = "deepseek-web"
                    account = payload.get("email") or payload.get("id") or "DeepSeek User"

                # 4. Custom Keyword Filter
                elif custom_keyword and custom_keyword.lower() in str(raw).lower():
                    prov = f"custom:{custom_keyword}"
                    account = payload.get("email") or payload.get("id") or "Akun Kustom"

                # Apply Filter
                if provider_filter == "all":
                    if prov == "unknown":
                        continue
                elif provider_filter == "custom":
                    if not prov.startswith("custom:"):
                        continue
                else:
                    if prov != provider_filter:
                        continue

                seen_tokens.add(token_str)
                label = f"[{browser_name}] {prov} — {account}"
                found.append({
                    "browser": browser_name,
                    "provider": prov,
                    "account": account,
                    "label": label,
                    "token": token_str,
                    "payload": payload,
                })
        except Exception:
            continue

    return found


def extract_all_browser_sessions(
    browser_filter: str = "all",
    provider_filter: str = "all",
    custom_keyword: str = "",
) -> List[Dict[str, Any]]:
    """Extract filtered AI sessions from installed browsers on the system."""
    all_sessions = []
    selected_browsers = BROWSER_PATHS.keys() if browser_filter == "all" else [browser_filter]

    for b_name in selected_browsers:
        paths = BROWSER_PATHS.get(b_name, [])
        for p in paths:
            if p.exists():
                items = extract_chromium_storage(
                    p,
                    browser_name=b_name,
                    provider_filter=provider_filter,
                    custom_keyword=custom_keyword,
                )
                all_sessions.extend(items)
                break  # First profile found for this browser

    # Deduplicate by token and sort
    unique_sessions = []
    seen = set()
    for s in all_sessions:
        if s["token"] not in seen:
            seen.add(s["token"])
            unique_sessions.append(s)

    return unique_sessions
