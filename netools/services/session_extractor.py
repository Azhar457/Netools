"""
Browser Session & Token Extractor for AI Web Providers (Brave, Chrome, Firefox).
Extracts LocalStorage tokens (JWT) and httpOnly cookies via browser_cookie3,
with provider-aware formatting matching OmniRoute's webSessionCredentials.
"""

import base64
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from netools.libs.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Browser paths
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Provider registry — all 25 OmniRoute web-cookie providers
# ---------------------------------------------------------------------------

SUPPORTED_PROVIDERS = [
    ("all", "Semua Provider AI"),
    ("chatgpt-web", "ChatGPT Web (Plus/Pro)"),
    ("claude-web", "Claude Web"),
    ("deepseek-web", "DeepSeek Web"),
    ("gemini-web", "Gemini Web (Free)"),
    ("gemini-business", "Gemini Business (Enterprise)"),
    ("grok-web", "Grok Web (Subscription)"),
    ("kimi-web", "Kimi Web (Moonshot AI)"),
    ("copilot-web", "Microsoft Copilot Web"),
    ("copilot-m365-web", "Microsoft 365 Copilot (BizChat)"),
    ("perplexity-web", "Perplexity Web (Pro/Max)"),
    ("blackbox-web", "Blackbox Web (Subscription)"),
    ("muse-spark-web", "Muse Spark Web (Meta AI)"),
    ("zai-web", "Z.ai Web (Free)"),
    ("doubao-web", "Dola Web (ByteDance)"),
    ("t3-web", "t3.chat (Pro/Free)"),
    ("inner-ai", "Inner.ai (Subscription)"),
    ("adapta-web", "Adapta.org (Adapta One Web)"),
    ("lmarena", "Arena (Free)"),
    ("yuanbao-web", "Tencent Yuanbao (Free)"),
    ("huggingchat", "HuggingChat (Free)"),
    ("poe-web", "Poe Web (Subscription)"),
    ("venice-web", "Venice Web (Privacy)"),
    ("v0-vercel-web", "v0 Vercel Web (Code Gen)"),
    ("zenmux-free", "ZenMux Free (Web)"),
    ("custom", "Kustom (Domain / Kata Kunci)"),
]

# ---------------------------------------------------------------------------
# Cookie → provider mapping (domain pattern → provider key)
# ---------------------------------------------------------------------------

_COOKIE_PROVIDER_MAP = {
    ".chatgpt.com": ["__Secure-next-auth.session-token"],
    "chatgpt.com": ["__Secure-next-auth.session-token"],
    ".claude.ai": ["sessionKey", "sessionKeyV3"],
    "claude.ai": ["sessionKey", "sessionKeyV3"],
    ".google.com": ["__Secure-1PSID"],
    "google.com": ["__Secure-1PSID"],
    "gemini.google.com": ["__Secure-1PSID"],
    ".perplexity.ai": ["__Secure-next-auth.session-token"],
    "perplexity.ai": ["__Secure-next-auth.session-token"],
    ".blackbox.ai": ["__Secure-authjs.session-token"],
    "blackbox.ai": ["__Secure-authjs.session-token"],
    "poe.com": ["p-b"],
    ".poe.com": ["p-b"],
    "venice.ai": ["session"],
    ".venice.ai": ["session"],
    "v0.dev": ["__vercel_session"],
    ".v0.dev": ["__vercel_session"],
    "huggingface.co": ["hf-chat", "token"],
    ".huggingface.co": ["hf-chat", "token"],
    "yuanbao.tencent.com": ["hy_user", "hy_token"],
    ".kimi.ai": ["kimi-auth"],
    "kimi.ai": ["kimi-auth"],
    "meta.ai": ["ecto_1_sess"],
    ".meta.ai": ["ecto_1_sess"],
}

# Domain patterns for provider identification from cookie domain
_COOKIE_DOMAIN_TO_PROVIDER = {
    "chatgpt.com": "chatgpt-web",
    "claude.ai": "claude-web",
    "google.com": "gemini-web",
    "perplexity.ai": "perplexity-web",
    "blackbox.ai": "blackbox-web",
    "poe.com": "poe-web",
    "venice.ai": "venice-web",
    "v0.dev": "v0-vercel-web",
    "huggingface.co": "huggingchat",
    "yuanbao.tencent.com": "yuanbao-web",
    "kimi.ai": "kimi-web",
    "meta.ai": "muse-spark-web",
    "chat.deepseek.com": "deepseek-web",
    "chat.z.ai": "zai-web",
    "grok.com": "grok-web",
    "business.gemini.google": "gemini-business",
    "gemini.google": "gemini-business",
    "copilot.microsoft.com": "copilot-web",
    "m365.cloud.microsoft": "copilot-m365-web",
    "t3.chat": "t3-web",
    "inner.ai": "inner-ai",
    "app.innerai.com": "inner-ai",
    "agent.adapta.one": "adapta-web",
    "adapta.org": "adapta-web",
    "arena.ai": "lmarena",
    "lmarena.ai": "lmarena",
    "zenmux.ai": "zenmux-free",
    "dola.com": "doubao-web",
    "www.dola.com": "doubao-web",
    "doubao.com": "doubao-web",
}

# JWT refresh token signals — skip these for ALL providers
_REFRESH_SIGNALS = {"refresh", "refresh_token", "refreshToken"}


# ---------------------------------------------------------------------------
# JWT Helpers
# ---------------------------------------------------------------------------


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


def _is_refresh_token(payload: Dict[str, Any]) -> bool:
    """Heuristic: is this JWT a refresh/access-token rather than an access token?"""
    # Explicit refresh signals
    if payload.get("typ") == "refresh":
        return True
    if payload.get("token_type", "").lower() == "refresh":
        return True
    if payload.get("grant_type") == "refresh_token":
        return True
    # Check token_use claim (some providers)
    if payload.get("token_use") == "refresh":
        return True
    # Check for very long exp (> 30 days) — likely refresh token
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        remaining = exp - time.time()
        if remaining > 30 * 86400:
            # Token lasts > 30 days — almost certainly a refresh token
            return True
    # Check scope contains offline_access or refresh
    scope = payload.get("scope", "")
    if isinstance(scope, str) and "refresh" in scope.lower():
        return True
    return False


def _is_access_token(payload: Dict[str, Any]) -> bool:
    """Heuristic: is this a usable access token?"""
    # Must have exp claim
    exp = payload.get("exp")
    if exp is None or not isinstance(exp, (int, float)):
        return False
    # Must not be expired
    if exp <= time.time():
        return False
    # Must not be a refresh token
    if _is_refresh_token(payload):
        return False
    # Lifetime should be reasonable (1 min to 30 days)
    remaining = exp - time.time()
    if remaining < 60:
        return False
    return True


# ---------------------------------------------------------------------------
# Provider Identification from JWT payload
# ---------------------------------------------------------------------------


def _identify_provider_from_jwt(
    payload: Dict[str, Any],
    raw_bytes: bytes,
) -> Optional[str]:
    """Identify provider from decoded JWT payload. Returns provider key or None."""
    raw_lower = raw_bytes.decode("utf-8", errors="ignore").lower()

    # 1. ChatGPT Web (iss: "https://auth0.openai.com/")
    iss = payload.get("iss", "")
    if "openai" in str(iss).lower() or "chatgpt" in str(iss).lower():
        return "chatgpt-web"

    # 2. DeepSeek (user/id in payload + domain context)
    if "deepseek" in raw_lower and ("user" in payload or "id" in payload):
        return "deepseek-web"

    # 3. Kimi Web (aud: ["kimi.ai"], app_id: "kimi")
    if payload.get("app_id") == "kimi" or "kimi.ai" in payload.get("aud", []):
        return "kimi-web"

    # 4. Z.ai Web (id + email, small payload)
    if "email" in payload and "id" in payload and len(payload) <= 5:
        if "z.ai" in raw_lower or "zai" in raw_lower:
            return "zai-web"

    # 5. Gemini (google accounts)
    if "google" in str(payload.get("iss", "")).lower():
        if "google.com" in raw_lower:
            return "gemini-web"

    # 6. Perplexity (iss contains perplexity)
    if "perplexity" in str(payload.get("iss", "")).lower():
        return "perplexity-web"

    # 7. Blackbox
    if "blackbox" in raw_lower:
        return "blackbox-web"

    # 8. Copilot (Microsoft)
    if "copilot" in raw_lower or "microsoft" in raw_lower:
        return "copilot-web"

    return None


def _identify_provider_from_cookie(
    cookie_name: str,
    cookie_domain: str,
) -> Optional[str]:
    """Identify provider from browser cookie name and domain."""
    domain_lower = cookie_domain.lower().lstrip(".")

    # Direct domain mapping
    for pattern, prov in _COOKIE_DOMAIN_TO_PROVIDER.items():
        if domain_lower == pattern or domain_lower.endswith("." + pattern):
            return prov

    # Cookie name mapping
    name_map = {
        "__Secure-next-auth.session-token": {
            "chatgpt.com": "chatgpt-web",
            "perplexity.ai": "perplexity-web",
        },
        "__Secure-authjs.session-token": {"blackbox.ai": "blackbox-web"},
        "sessionKey": {"claude.ai": "claude-web"},
        "sessionKeyV3": {"claude.ai": "claude-web"},
        "__Secure-1PSID": {"google.com": "gemini-web"},
        "p-b": {"poe.com": "poe-web"},
        "session": {"venice.ai": "venice-web"},
        "__vercel_session": {"v0.dev": "v0-vercel-web"},
        "hf-chat": {"huggingface.co": "huggingchat"},
        "hy_user": {"yuanbao.tencent.com": "yuanbao-web"},
        "token": {"z.ai": "zai-web"},
        "kimi-auth": {"kimi.ai": "kimi-web"},
        "ecto_1_sess": {"meta.ai": "muse-spark-web"},
    }
    if cookie_name in name_map:
        for pat, prov in name_map[cookie_name].items():
            if pat in domain_lower:
                return prov

    return None


# ---------------------------------------------------------------------------
# LevelDB Scanner (Chromium/Brave Local Storage)
# ---------------------------------------------------------------------------


def extract_chromium_storage(
    profile_dir: Path,
    browser_name: str,
    provider_filter: str = "all",
    custom_keyword: str = "",
) -> List[Dict[str, Any]]:
    """Scan Chromium/Brave LevelDB for JWT tokens with provider identification."""
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

                # Skip refresh tokens for ALL providers
                if _is_refresh_token(payload):
                    continue

                # Identify provider
                prov = _identify_provider_from_jwt(payload, raw)
                if not prov:
                    # Try custom keyword
                    if custom_keyword and custom_keyword.lower() in raw.decode("utf-8", errors="ignore").lower():
                        prov = f"custom:{custom_keyword}"
                    else:
                        continue

                account = (
                    payload.get("email")
                    or payload.get("sub")
                    or payload.get("id")
                    or payload.get("user_id")
                    or "Unknown"
                )

                # Apply filter
                if provider_filter != "all":
                    if provider_filter == "custom":
                        if not prov.startswith("custom:"):
                            continue
                    elif prov != provider_filter:
                        continue

                # Compute TTL
                from netools.services.omniroute_bridge import compute_token_ttl

                ttl = compute_token_ttl(payload)

                seen_tokens.add(token_str)
                label = f"[{browser_name}] {prov} — {account}"
                found.append(
                    {
                        "browser": browser_name,
                        "provider": prov,
                        "account": account,
                        "label": label,
                        "token": token_str,
                        "payload": payload,
                        "source": "leveldb",
                        "ttl": ttl,
                    }
                )
        except Exception:
            continue

    return found


# ---------------------------------------------------------------------------
# Browser Cookie Scanner (browser_cookie3 — decrypts httpOnly cookies)
# ---------------------------------------------------------------------------


def _get_browser_cookies(browser_name: str) -> List[dict]:
    """Get all cookies from a browser using browser_cookie3."""
    try:
        import browser_cookie3
    except ImportError:
        log.warning("browser_cookie3 not installed — cookie extraction disabled")
        return []

    cj = None
    name_lower = browser_name.lower()
    try:
        if "brave" in name_lower:
            cj = browser_cookie3.brave()
        elif "chrome" in name_lower:
            cj = browser_cookie3.chrome()
        elif "firefox" in name_lower:
            cj = browser_cookie3.firefox()
    except Exception as e:
        log.debug("Could not read %s cookies: %s", browser_name, e)
        return []

    if cj is None:
        return []

    return [
        {
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
        }
        for c in cj
    ]


def _is_valid_session_cookie(value: Optional[str]) -> bool:
    """Filter out obvious non-session cookies (timestamps, counters, etc.)."""
    if not value or len(value) < 10:
        return False
    # Skip pure numeric/timestamp cookies
    if value.isdigit():
        return False
    # Skip very short tokens
    if len(value) < 12:
        return False
    return True


def _format_cookie_header(cookies: List[dict]) -> str:
    """Format list of cookies into a Cookie header string: 'name1=val1; name2=val2'."""
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def extract_browser_cookies(
    browser_name: str,
    provider_filter: str = "all",
    custom_keyword: str = "",
) -> List[Dict[str, Any]]:
    """Scan browser httpOnly cookies for session tokens.

    Returns formatted tokens matching OmniRoute's webSessionCredentials format:
    - Token providers: raw token value
    - Cookie providers: full Cookie header string (name1=val1; name2=val2)
    """
    all_cookies = _get_browser_cookies(browser_name)
    if not all_cookies:
        return []

    # Group cookies by domain
    domain_cookies: Dict[str, List[dict]] = {}
    for c in all_cookies:
        domain = c["domain"].lower().lstrip(".")
        if domain not in domain_cookies:
            domain_cookies[domain] = []
        domain_cookies[domain].append(c)

    found = []
    seen_providers = set()

    for domain, cookies in domain_cookies.items():
        # Identify provider from domain
        prov = None
        for pat, p in _COOKIE_DOMAIN_TO_PROVIDER.items():
            if domain == pat or domain.endswith("." + pat):
                prov = p
                break

        if not prov:
            continue

        # Apply filter
        if provider_filter != "all":
            if provider_filter == "custom":
                if custom_keyword and custom_keyword.lower() in domain:
                    prov = f"custom:{custom_keyword}"
                else:
                    continue
            elif prov != provider_filter:
                continue

        # Skip if already found from same domain (deduplicate)
        dedup_key = f"{prov}:{domain}"
        if dedup_key in seen_providers:
            continue

        # Extract provider-specific cookies
        token_value = _extract_provider_cookie_value(prov, cookies)
        if not token_value:
            continue

        seen_providers.add(dedup_key)
        label = f"[{browser_name}] {prov} — {domain}"

        # For cookies, payload is None (not a JWT)
        found.append(
            {
                "browser": browser_name,
                "provider": prov,
                "account": domain,
                "label": label,
                "token": token_value,
                "payload": None,
                "source": "cookie",
                "ttl": None,  # Cookie TTL unknown without JWT exp
            }
        )

    return found


def _get_cookie_value(cookie_map: Dict[str, dict], name: str) -> Optional[str]:
    """Safe extraction of cookie value, tolerating missing entries."""
    cookie = cookie_map.get(name)
    if not isinstance(cookie, dict):
        return None
    return cookie.get("value")


def _extract_provider_cookie_value(prov: str, cookies: List[dict]) -> Optional[str]:
    """Extract the credential value from cookies based on provider requirements.

    Returns either a raw token value (for token-kind providers) or a full
    Cookie header string (for cookie-kind providers).
    """
    cookie_map = {c["name"]: c for c in cookies}

    if prov == "chatgpt-web":
        # OmniRoute expects Playwright storage-state JSON format
        tok = _get_cookie_value(cookie_map, "__Secure-next-auth.session-token")
        if not _is_valid_session_cookie(tok):
            return None
        # Build valid Playwright storage-state JSON matching OmniRoute's expectation
        storage_cookies = []
        for c in cookies:
            if "chatgpt.com" in c["domain"] or "openai.com" in c["domain"]:
                storage_cookies.append(
                    {
                        "name": c["name"],
                        "value": c["value"],
                        "domain": c["domain"],
                        "path": c["path"] or "/",
                        "expires": int(time.time()) + 86400 * 30,
                        "httpOnly": True,
                        "secure": True,
                        "sameSite": "Lax",
                    }
                )
        if storage_cookies:
            import json

            return json.dumps(
                {
                    "cookies": storage_cookies,
                    "origins": [{"origin": "https://chatgpt.com", "localStorage": []}],
                }
            )
        return tok

    elif prov == "claude-web":
        # OmniRoute expects sessionKey or full Cookie header
        # Try sessionKey first, then sessionKeyV3
        for key_name in ["sessionKey", "sessionKeyV3"]:
            tok = _get_cookie_value(cookie_map, key_name)
            if tok and len(tok) > 10:
                return tok
        # Fallback: full cookie header
        relevant = [c for c in cookies if c["name"] in ("sessionKey", "sessionKeyV3", "__cf_bm")]
        if relevant:
            return _format_cookie_header(relevant)
        return None

    elif prov == "deepseek-web":
        # Token-based — but cookies don't contain userToken (it's in LevelDB)
        # Skip — LevelDB extraction handles this
        return None

    elif prov == "kimi-web":
        # Token-based — kimi-auth cookie is a fallback
        tok = _get_cookie_value(cookie_map, "kimi-auth")
        if tok and len(tok) > 10:
            return tok
        return None

    elif prov == "zai-web":
        # Token-based — "token" cookie
        tok = _get_cookie_value(cookie_map, "token")
        if not _is_valid_session_cookie(tok):
            return None
        return tok

    elif prov in ("gemini-web", "gemini-business"):
        # OmniRoute expects __Secure-1PSID + __Secure-1PSIDTS + __Secure-1PSIDCC
        psid = _get_cookie_value(cookie_map, "__Secure-1PSID")
        if not psid:
            return None
        parts = [f"__Secure-1PSID={psid}"]
        psidts = _get_cookie_value(cookie_map, "__Secure-1PSIDTS")
        if psidts:
            parts.append(f"__Secure-1PSIDTS={psidts}")
        psidcc = _get_cookie_value(cookie_map, "__Secure-1PSIDCC")
        if psidcc:
            parts.append(f"__Secure-1PSIDCC={psidcc}")
        return "; ".join(parts)

    elif prov == "grok-web":
        # sso + sso-rw cookies
        sso = _get_cookie_value(cookie_map, "sso")
        sso_rw = _get_cookie_value(cookie_map, "sso-rw")
        if not sso:
            return None
        parts = [f"sso={sso}"]
        if sso_rw:
            parts.append(f"sso-rw={sso_rw}")
        return "; ".join(parts)

    elif prov == "perplexity-web":
        tok = _get_cookie_value(cookie_map, "__Secure-next-auth.session-token")
        if not _is_valid_session_cookie(tok):
            return None
        return tok

    elif prov == "blackbox-web":
        tok = _get_cookie_value(cookie_map, "__Secure-authjs.session-token")
        if not tok:
            return None
        return f"__Secure-authjs.session-token={tok}"

    elif prov == "poe-web":
        tok = _get_cookie_value(cookie_map, "p-b")
        if not _is_valid_session_cookie(tok):
            return None
        return f"p-b={tok}"

    elif prov == "venice-web":
        tok = _get_cookie_value(cookie_map, "session")
        if not _is_valid_session_cookie(tok):
            return None
        return f"session={tok}"

    elif prov == "v0-vercel-web":
        tok = _get_cookie_value(cookie_map, "__vercel_session")
        if not tok:
            return None
        return f"__vercel_session={tok}"

    elif prov == "huggingchat":
        hf = cookie_map.get("hf-chat", {}).get("value")
        if not hf:
            return None
        parts = [f"hf-chat={hf}"]
        tok = cookie_map.get("token", {}).get("value")
        if tok:
            parts.append(f"token={tok}")
        return "; ".join(parts)

    elif prov == "yuanbao-web":
        hy_user = cookie_map.get("hy_user", {}).get("value")
        hy_token = cookie_map.get("hy_token", {}).get("value")
        if not hy_user or not hy_token:
            return None
        return f"hy_user={hy_user}; hy_token={hy_token}"

    elif prov == "muse-spark-web":
        ecto = cookie_map.get("ecto_1_sess", {}).get("value")
        if not ecto:
            return None
        return f"ecto_1_sess={ecto}"

    elif prov in ("copilot-web", "copilot-m365-web"):
        # These need access_token from network requests, not cookies
        return None

    elif prov == "t3-web":
        # convex-session-id + cookie header
        conv = cookie_map.get("convex-session-id", {}).get("value")
        if conv:
            return f"convex-session-id={conv}"
        return None

    elif prov == "inner-ai":
        tok = cookie_map.get("token", {}).get("value")
        if not tok:
            return None
        return f"{tok}"  # User needs to append email manually

    elif prov == "adapta-web":
        tok = cookie_map.get("__client", {}).get("value")
        if not tok:
            return None
        return f"__client={tok}"

    elif prov == "lmarena":
        # Full cookie header from arena.ai
        relevant = [c for c in cookies if "arena" in c["name"].lower() or c["name"] in ("cf_clearance", "__cf_bm")]
        if relevant:
            return _format_cookie_header(relevant)
        return None

    elif prov == "zenmux-free":
        # Full cookie header
        relevant = [c for c in cookies if len(c["value"]) > 5]
        if relevant:
            return _format_cookie_header(relevant[:5])  # Top 5
        return None

    elif prov == "doubao-web":
        sid = cookie_map.get("sessionid", {}).get("value")
        ttwid = cookie_map.get("ttwid", {}).get("value")
        if not sid:
            return None
        parts = [f"sessionid={sid}"]
        if ttwid:
            parts.append(f"ttwid={ttwid}")
        svwid = cookie_map.get("s_v_web_id", {}).get("value")
        if svwid:
            parts.append(f"s_v_web_id={svwid}")
        return "; ".join(parts)

    elif prov.startswith("custom:"):
        # For custom: provide full cookie header from matching domain
        keyword = prov.split(":", 1)[1]
        relevant = [c for c in cookies if keyword.lower() in c["domain"].lower()]
        if relevant:
            return _format_cookie_header(relevant)
        return None

    return None


# ---------------------------------------------------------------------------
# Firefox Multi-Profile Scanner
# ---------------------------------------------------------------------------


def _firefox_profile_dirs() -> List[Path]:
    """Find all Firefox profile directories."""
    profiles = []
    for base in BROWSER_PATHS.get("Firefox", []):
        profiles_ini = base / "profiles.ini"
        if not profiles_ini.exists():
            continue
        try:
            content = profiles_ini.read_text()
            for line in content.splitlines():
                if line.startswith("Path="):
                    path_str = line.split("=", 1)[1].strip()
                    full = base / path_str
                    if full.exists():
                        profiles.append(full)
        except Exception:
            continue
    if not profiles:
        # Fallback: scan Default-release, etc.
        for base in BROWSER_PATHS.get("Firefox", []):
            for sub in base.glob("*.default*"):
                if sub.is_dir():
                    profiles.append(sub)
    return profiles


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------


def extract_all_browser_sessions(
    browser_filter: str = "all",
    provider_filter: str = "all",
    custom_keyword: str = "",
) -> List[Dict[str, Any]]:
    """Extract filtered AI sessions from installed browsers.

    Scans both LevelDB (Local Storage JWT tokens) and httpOnly cookies
    (via browser_cookie3) for all providers, formats tokens to match
    OmniRoute's webSessionCredentials expectations.
    """
    all_sessions = []
    selected_browsers = list(BROWSER_PATHS.keys()) if browser_filter == "all" else [browser_filter]

    for b_name in selected_browsers:
        paths = BROWSER_PATHS.get(b_name, [])

        if b_name == "Firefox":
            # Multi-profile support for Firefox
            for fp in _firefox_profile_dirs():
                items = extract_chromium_storage(
                    fp,
                    browser_name=b_name,
                    provider_filter=provider_filter,
                    custom_keyword=custom_keyword,
                )
                all_sessions.extend(items)
        else:
            for p in paths:
                if p.exists():
                    items = extract_chromium_storage(
                        p,
                        browser_name=b_name,
                        provider_filter=provider_filter,
                        custom_keyword=custom_keyword,
                    )
                    all_sessions.extend(items)
                    break  # First profile found

        # Cookie extraction (works for all Chromium-based browsers)
        if b_name != "Firefox":
            cookie_items = extract_browser_cookies(
                b_name,
                provider_filter=provider_filter,
                custom_keyword=custom_keyword,
            )
            all_sessions.extend(cookie_items)

    # Deduplicate: prefer LevelDB tokens over cookies for same provider
    # (LevelDB tokens are more structured/verified)
    dedup: Dict[str, Dict] = {}
    for s in all_sessions:
        prov = s["provider"]
        source = s.get("source", "unknown")
        existing = dedup.get(prov)
        if existing is None:
            dedup[prov] = s
        elif source == "leveldb" and existing.get("source") != "leveldb":
            # LevelDB beats cookie
            dedup[prov] = s
        # else keep existing (first found or already leveldb)

    unique_sessions = list(dedup.values())

    # Sort by TTL status: active first, expiring soon, expired, unknown
    priority = {"active": 0, "expiring_soon": 1, "expired": 2, "unknown": 3}
    unique_sessions.sort(key=lambda s: priority.get(s["ttl"].status if s.get("ttl") else "unknown", 3))

    return unique_sessions
