"""
Centralized Semantic Theme & Typography System for Netools Suite.
Provides 4 canonical palettes (Dark, Light, Orange, Sea) with WCAG AA compliance,
semantic color tokens, and reactive theme switching.
"""

from typing import Any, Dict, List, Optional

import customtkinter as ctk

# -----------------------------------------------------------------------------
# 4 Canonical Semantic Themes
# -----------------------------------------------------------------------------
THEMES: Dict[str, Dict[str, str]] = {
    "dark": {
        "name": "Dark (Catppuccin Mocha)",
        "mode": "dark",
        "bg": "#181825",
        "surface": "#1e1e2e",
        "surface_alt": "#11111b",
        "border": "#414559",
        "text": "#eef1f8",
        "text_muted": "#c0c7dd",
        "primary": "#89b4fa",
        "on_primary": "#11111b",
        "secondary": "#cba6f7",
        "on_secondary": "#11111b",
        "accent": "#89dceb",
        "success": "#a6e3a1",
        "warning": "#f9e2af",
        "danger": "#f38ba8",
    },
    "light": {
        "name": "Light (Modern Neutral)",
        "mode": "light",
        "bg": "#f5f5f7",
        "surface": "#ffffff",
        "surface_alt": "#e4e4e7",
        "border": "#d4d4d8",
        "text": "#18181b",
        "text_muted": "#71717a",
        "primary": "#2563eb",
        "on_primary": "#ffffff",
        "secondary": "#6366f1",
        "on_secondary": "#ffffff",
        "accent": "#0284c7",
        "success": "#16a34a",
        "warning": "#d97706",
        "danger": "#dc2626",
    },
    "orange": {
        "name": "Orange (Sunset Glow)",
        "mode": "dark",
        "bg": "#1c1917",
        "surface": "#292524",
        "surface_alt": "#141210",
        "border": "#44403c",
        "text": "#fafaf9",
        "text_muted": "#a8a29e",
        "primary": "#f97316",
        "on_primary": "#ffffff",
        "secondary": "#fb923c",
        "on_secondary": "#1c1917",
        "accent": "#facc15",
        "success": "#22c55e",
        "warning": "#f59e0b",
        "danger": "#ef4444",
    },
    "sea": {
        "name": "Sea (Deep Ocean)",
        "mode": "dark",
        "bg": "#0a192f",
        "surface": "#112240",
        "surface_alt": "#020c1b",
        "border": "#33507a",
        "text": "#e8f1ff",
        "text_muted": "#a9bcd8",
        "primary": "#64ffda",
        "on_primary": "#0a192f",
        "secondary": "#00b4d8",
        "on_secondary": "#0a192f",
        "accent": "#57cbff",
        "success": "#00f5d4",
        "warning": "#ffd166",
        "danger": "#ff6b6b",
    },
}

class ThemeManager:
    """Singleton Theme Manager for dynamic runtime skinning."""
    _current_theme = "dark"

    @classmethod
    def get_available_themes(cls) -> List[str]:
        return ["Dark", "Light", "Orange", "Sea"]

    @classmethod
    def get_current_theme_key(cls) -> str:
        return cls._current_theme

    @classmethod
    def get_tokens(cls) -> Dict[str, str]:
        return THEMES.get(cls._current_theme, THEMES["dark"])

    @classmethod
    def get(cls, token: str) -> str:
        return cls.get_tokens().get(token, "#ffffff")

    @classmethod
    def bg(cls) -> str: return cls.get("bg")
    @classmethod
    def surface(cls) -> str: return cls.get("surface")
    @classmethod
    def surface_alt(cls) -> str: return cls.get("surface_alt")
    @classmethod
    def border(cls) -> str: return cls.get("border")
    @classmethod
    def text(cls) -> str: return cls.get("text")
    @classmethod
    def text_muted(cls) -> str: return cls.get("text_muted")
    @classmethod
    def primary(cls) -> str: return cls.get("primary")
    @classmethod
    def secondary(cls) -> str: return cls.get("secondary")
    @classmethod
    def accent(cls) -> str: return cls.get("accent")
    @classmethod
    def success(cls) -> str: return cls.get("success")
    @classmethod
    def warning(cls) -> str: return cls.get("warning")
    @classmethod
    def danger(cls) -> str: return cls.get("danger")

    @classmethod
    def apply_theme(cls, theme_name: str, app_instance: Optional[Any] = None) -> None:
        key = theme_name.lower().strip()
        if key not in THEMES:
            key = "dark"
        cls._current_theme = key
        tokens = THEMES[key]

        from pathlib import Path
        theme_json = Path(__file__).resolve().parent.parent / "assets" / "themes" / f"{key}.json"
        if theme_json.exists():
            try:
                ctk.set_default_color_theme(str(theme_json))
            except Exception:
                pass

        ctk.set_appearance_mode(tokens["mode"])

        import sys
        mod = sys.modules.get(__name__)
        if mod:
            mod.COLOR_BG = tokens["bg"]
            mod.COLOR_BG_DARK = tokens["surface_alt"]
            mod.COLOR_CARD = tokens["surface"]
            mod.COLOR_BORDER = tokens["border"]
            mod.COLOR_TEXT_PRIMARY = tokens["text"]
            mod.COLOR_TEXT_SECONDARY = tokens["text_muted"]
            mod.COLOR_TEXT_MUTED = tokens["text_muted"]
            mod.COLOR_ACCENT_BLUE = tokens["primary"]
            mod.COLOR_ACCENT_GREEN = tokens["success"]
            mod.COLOR_ACCENT_YELLOW = tokens["warning"]
            mod.COLOR_ACCENT_RED = tokens["danger"]
            mod.COLOR_ACCENT_PURPLE = tokens["secondary"]

        if app_instance and hasattr(app_instance, "configure"):
            try:
                app_instance.configure(fg_color=tokens["bg"])
            except Exception:
                pass





# Backward-compatible global constants
COLOR_BG = THEMES["dark"]["bg"]
COLOR_BG_DARK = THEMES["dark"]["surface_alt"]
COLOR_CARD = THEMES["dark"]["surface"]
COLOR_BORDER = THEMES["dark"]["border"]
COLOR_TEXT_PRIMARY = THEMES["dark"]["text"]
COLOR_TEXT_SECONDARY = THEMES["dark"]["text_muted"]
COLOR_TEXT_MUTED = THEMES["dark"]["text_muted"]
COLOR_ACCENT_BLUE = THEMES["dark"]["primary"]
COLOR_ACCENT_GREEN = THEMES["dark"]["success"]
COLOR_ACCENT_YELLOW = THEMES["dark"]["warning"]
COLOR_ACCENT_RED = THEMES["dark"]["danger"]
COLOR_ACCENT_PURPLE = THEMES["dark"]["secondary"]


class Spacings:
    """Standard 4px base-grid layout constants."""
    PAD_CARD = 16
    PAD_ELEMENT = 12
    PAD_TIGHT = 8
    PAD_MICRO = 4

    BTN_HEIGHT_LG = 38   # Primary / Major CTA
    BTN_HEIGHT_MD = 34   # Standard action bar
    BTN_HEIGHT_SM = 28   # Filter chip / mini tool
    INPUT_HEIGHT = 34    # Inputs & ComboBoxes


class Fonts:
    """Standardized semantic typography hierarchy (comfortable readability across high-DPI/desktop screens)."""

    @staticmethod
    def display(size: int = 18):
        return ("sans-serif", size, "bold")

    @staticmethod
    def title(size: int = 15):
        return ("sans-serif", size, "bold")

    @staticmethod
    def subtitle(size: int = 13):
        return ("sans-serif", size, "bold")

    @staticmethod
    def bold(size: int = 12):
        return ("sans-serif", size, "bold")

    @staticmethod
    def regular(size: int = 12):
        return ("sans-serif", size, "normal")

    @staticmethod
    def small(size: int = 11):
        return ("sans-serif", size, "normal")

    @staticmethod
    def badge(size: int = 10):
        return ("sans-serif", size, "bold")

    @staticmethod
    def italic_small(size: int = 10):
        return ("sans-serif", size, "italic")

    @staticmethod
    def mono(size: int = 12):
        return ("monospace", size, "normal")

    @staticmethod
    def mono_bold(size: int = 12):
        return ("monospace", size, "bold")


