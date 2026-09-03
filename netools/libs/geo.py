"""
Country auto-detection for region-aware TLD benchmark defaults.
One HTTPS request to Cloudflare's trace endpoint (no API key), cached
permanently in config.json. Fallback: system locale. Override: set
"country": "XX" in ~/.config/netools/config.json.
"""

import json
import locale
import logging
import urllib.request

from netools.config import USER_CONFIG_FILE, load_user_config

log = logging.getLogger(__name__)

TRACE_URL = "https://cloudflare.com/cdn-cgi/trace"


def _via_trace(timeout: float = 2.0) -> str:
    try:
        with urllib.request.urlopen(TRACE_URL, timeout=timeout) as r:
            for line in r.read().decode("utf-8", "replace").splitlines():
                if line.startswith("loc="):
                    cc = line[4:].strip().upper()
                    return cc if len(cc) == 2 and cc != "XX" else ""
    except Exception as e:
        log.debug(f"country trace failed: {e}")
    return ""


def _via_locale() -> str:
    try:
        loc = locale.getlocale()[0] or ""  # e.g. 'en_US' / 'id_ID'
        if "_" in loc:
            return loc.rsplit("_", 1)[1][:2].upper()
    except Exception:
        pass
    return ""


def detect_country() -> str:
    """ISO-3166 alpha-2 country code, or '' if undetectable.

    Priority: config override > cached detection > trace > locale.
    Detection runs at most once per install (result cached in config.json).
    """
    cfg = load_user_config()
    manual = cfg.get("country", "")
    if manual:
        return str(manual).upper()
    cached = cfg.get("detected_country", "")
    if cached:
        return str(cached).upper()

    cc = _via_trace() or _via_locale()
    if cc:
        try:
            cfg["detected_country"] = cc
            USER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            USER_CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        except Exception as e:
            log.debug(f"country cache write failed: {e}")
    return cc
