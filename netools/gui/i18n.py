"""
Scalable & Modular i18n Localization Engine for Netools Suite.

Supports English ("en") and Bahasa Indonesia ("id") with one-line
extensibility for future languages via drop-in JSON files:

    netools/gui/i18n/translations/
      ├── en.json
      ├── id.json
      ├── canary_en.json
      └── canary_id.json

Usage:
    from netools.gui.i18n import tr, get_locale, set_locale
    tr("Check Now")                             # translated for current locale
    tr("Connected to {target}", target="1.1.1.1")  # formatting
    tr("Applied", lang="id")                    # explicit locale

Extensibility:
    echo '{"my_key": "translation"}' > netools/gui/i18n/translations/de.json
    register_locale("de", "🇩🇪 Deutsch", {"my_key": "Übersetzung"})

Performance:
    JSON loaded lazily per-locale (only active locale cached).
    Falls back to inline dict if file missing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from netools.config import USER_CONFIG_DIR, USER_CONFIG_FILE
from netools.libs.logger import get_logger

log = get_logger(__name__)

# Directory containing translation JSON files (i18n/translations/).
_TRANSLATIONS_DIR = Path(__file__).parent / "i18n" / "translations"

# Registry of supported locales: code -> display label
_LOCALE_REGISTRY: dict[str, str] = {
    "en": "🇬🇧 English",
    "id": "🇮🇩 Bahasa Indonesia",
}

_current_locale: Optional[str] = None

# Runtime translation cache: locale -> {key: translated_text}
_TRANSLATIONS_CACHE: dict[str, dict[str, str]] = {}

# Inline fallback used only if JSON files are missing (e.g. broken install).
_FALLBACK_TRANSLATIONS: dict[str, dict[str, str]] = {
    "⚡ Netools Suite v2.0": {"id": "⚡ Netools Suite v2.0"},
    "📊 Dashboard": {"id": "📊 Dasbor"},
    "⚡ DNS Suite": {"id": "⚡ DNS Suite"},
}

# Canary info fallback
_CANARY_INFO_FALLBACK: dict[str, list[str]] = {
    "en": ["What are canary domains?", "They detect DNS interception."],
    "id": ["Apa itu domain canary?", "Domain ini mendeteksi intersepsi DNS."],
}


def _load_translations_file(lang: str) -> dict[str, str]:
    """Load and cache a translation JSON file for the given locale."""
    if lang in _TRANSLATIONS_CACHE:
        return _TRANSLATIONS_CACHE[lang]

    file_path = _TRANSLATIONS_DIR / f"{lang}.json"
    if not file_path.exists():
        # File doesn't exist — return empty dict (register_locale or tr
        # will fall back to inline dict or key passthrough).
        _TRANSLATIONS_CACHE[lang] = {}
        return {}

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        _TRANSLATIONS_CACHE[lang] = data if isinstance(data, dict) else {}
        return _TRANSLATIONS_CACHE[lang]
    except Exception as e:
        log.warning(f"Failed to load translation file {file_path}: {e}")
        _TRANSLATIONS_CACHE[lang] = {}
        return {}


def _load_canary_info(lang: str) -> list[str]:
    """Load canary info paragraphs from JSON file."""
    file_path = _TRANSLATIONS_DIR / f"canary_{lang}.json"
    if not file_path.exists():
        return list(_CANARY_INFO_FALLBACK.get(lang, _CANARY_INFO_FALLBACK.get("en", [])))

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return list(data)
    except Exception as e:
        log.warning(f"Failed to load canary info {file_path}: {e}")
        return list(_CANARY_INFO_FALLBACK.get(lang, _CANARY_INFO_FALLBACK.get("en", [])))


def register_locale(code: str, label: str, strings: dict[str, str], canary_info: Optional[list[str]] = None) -> None:
    """
    Register a new locale dynamically (Scalability interface).
    Allows adding new languages (e.g. Japanese, Chinese, German) with 1 line.
    """
    code = code.lower().strip()
    _LOCALE_REGISTRY[code] = label

    # Merge into existing cache or fallback
    existing = _load_translations_file(code)
    existing.update(strings)
    _TRANSLATIONS_CACHE[code] = existing

    if canary_info:
        # Write canary info JSON for persistence
        canary_path = _TRANSLATIONS_DIR / f"canary_{code}.json"
        try:
            _TRANSLATIONS_DIR.mkdir(parents=True, exist_ok=True)
            canary_path.write_text(json.dumps(canary_info, indent=2), encoding="utf-8")
        except Exception as e:
            log.debug(f"Could not persist canary info for {code}: {e}")

    log.info(f"Registered new i18n locale: {code} ({label}) with {len(strings)} strings")


def get_available_locales() -> dict[str, str]:
    """Return dictionary of available locales {code: display_label}."""
    return dict(_LOCALE_REGISTRY)


def get_locale_labels() -> list[str]:
    """Return list of formatted locale display labels."""
    return list(_LOCALE_REGISTRY.values())


def locale_from_label(label: str) -> str:
    """Map display label or raw code to standardized locale code."""
    clean = label.strip()
    for code, lbl in _LOCALE_REGISTRY.items():
        if clean == lbl or clean.lower() == code:
            return code
    if "indo" in clean.lower() or "id" in clean.lower():
        return "id"
    return "en"


def label_from_locale(code: str) -> str:
    """Map standardized locale code to display label."""
    return _LOCALE_REGISTRY.get(code.lower(), _LOCALE_REGISTRY.get("en", "English"))


def get_locale() -> str:
    """Get active locale from memory or persist file (~/.config/netools/config.json)."""
    global _current_locale
    if _current_locale:
        return _current_locale

    try:
        if USER_CONFIG_FILE.exists():
            data = json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
            lang = str(data.get("language", "en")).lower().strip()
            if lang in _LOCALE_REGISTRY:
                _current_locale = lang
                return lang
    except Exception as e:
        log.debug(f"Failed reading locale from config: {e}")

    _current_locale = "en"
    return _current_locale


def set_locale(lang: str) -> None:
    """Set and persist active locale to ~/.config/netools/config.json."""
    global _current_locale
    code = locale_from_label(lang)
    _current_locale = code

    try:
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cfg: dict[str, Any] = {}
        if USER_CONFIG_FILE.exists():
            try:
                cfg = json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                cfg = {}
        cfg["language"] = code
        USER_CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        log.info(f"Persisted language preference: {code}")
    except Exception as e:
        log.warning(f"Failed persisting locale to {USER_CONFIG_FILE}: {e}")


def tr(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """
    Translate `key` (English canonical text) into the active locale.
    Supports dynamic string formatting using kwargs (e.g. tr("Hello {name}", name="User")).

    Lookup order:
      1. JSON translation file for active locale
      2. Inline fallback dict (only if JSON missing)
      3. Key itself (passthrough)
    """
    loc = (lang or get_locale()).lower()

    translations = _load_translations_file(loc)
    entry = translations.get(key)
    if entry is None and loc != "en":
        entry = _FALLBACK_TRANSLATIONS.get(key, {}).get(loc)
    text = entry if entry is not None else key

    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def canary_info_paragraphs(lang: Optional[str] = None) -> list[str]:
    """Localized explanatory paragraphs for the canary info dialog."""
    loc = (lang or get_locale()).lower()

    # Try JSON first
    paragraphs = _load_canary_info(lang) if lang else None
    if paragraphs is None:
        paragraphs = _load_canary_info(loc)

    return paragraphs if paragraphs else list(_CANARY_INFO_FALLBACK.get("en", []))
