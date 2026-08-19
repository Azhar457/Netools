"""
Centralized Modern Theme & Typography System for Netools Suite.
Provides standard readable font sizes (11pt - 16pt) optimized for Linux, Windows & macOS High-DPI displays.
"""

import customtkinter as ctk

# Color Palette (Catppuccin Mocha Inspired)
COLOR_BG = "#181825"
COLOR_BG_DARK = "#11111b"
COLOR_CARD = "#1e1e2e"
COLOR_BORDER = "#313244"
COLOR_TEXT_PRIMARY = "#cdd6f4"
COLOR_TEXT_SECONDARY = "#a6adc8"
COLOR_TEXT_MUTED = "#6c7086"
COLOR_ACCENT_BLUE = "#89b4fa"
COLOR_ACCENT_GREEN = "#a6e3a1"
COLOR_ACCENT_YELLOW = "#f9e2af"
COLOR_ACCENT_RED = "#f38ba8"
COLOR_ACCENT_PURPLE = "#cba6f7"

class Fonts:
    """Standardized cross-platform font sizes (no more microscopic 9pt!)."""
    
    @staticmethod
    def title(size: int = 16) -> ctk.CTkFont:
        return ctk.CTkFont(size=size, weight="bold")
    
    @staticmethod
    def subtitle(size: int = 13) -> ctk.CTkFont:
        return ctk.CTkFont(size=size, weight="bold")
    
    @staticmethod
    def bold(size: int = 11) -> ctk.CTkFont:
        return ctk.CTkFont(size=size, weight="bold")
    
    @staticmethod
    def regular(size: int = 11) -> ctk.CTkFont:
        return ctk.CTkFont(size=size, weight="normal")
    
    @staticmethod
    def small(size: int = 10) -> ctk.CTkFont:
        return ctk.CTkFont(size=size, weight="normal")
    
    @staticmethod
    def italic_small(size: int = 10) -> ctk.CTkFont:
        return ctk.CTkFont(size=size, slant="italic")
    
    @staticmethod
    def mono(size: int = 11) -> ctk.CTkFont:
        return ctk.CTkFont(family="monospace", size=size)
    
    @staticmethod
    def mono_bold(size: int = 11) -> ctk.CTkFont:
        return ctk.CTkFont(family="monospace", size=size, weight="bold")
