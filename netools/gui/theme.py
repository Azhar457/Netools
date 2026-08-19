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
    """Standardized cross-platform font tuples (guaranteed 100% persistent, never GC'd)."""
    
    @staticmethod
    def title(size: int = 15):
        return ("sans-serif", size, "bold")
    
    @staticmethod
    def subtitle(size: int = 12):
        return ("sans-serif", size, "bold")
    
    @staticmethod
    def bold(size: int = 11):
        return ("sans-serif", size, "bold")
    
    @staticmethod
    def regular(size: int = 11):
        return ("sans-serif", size, "normal")
    
    @staticmethod
    def small(size: int = 10):
        return ("sans-serif", size, "normal")
    
    @staticmethod
    def italic_small(size: int = 10):
        return ("sans-serif", size, "italic")
    
    @staticmethod
    def mono(size: int = 11):
        return ("monospace", size, "normal")
    
    @staticmethod
    def mono_bold(size: int = 11):
        return ("monospace", size, "bold")
