"""
Modern In-App Snackbar / Toast Notification Component (CustomTkinter).
Implements Jakob Nielsen's Usability Heuristic #1: Visibility of System Status.
Provides clear, prominent, high-contrast visual feedback with auto-dismiss and manual close.
"""

import customtkinter as ctk
from typing import Optional
from netools.gui.theme import Fonts


class ToastManager:
    def __init__(self, root_window: ctk.CTk):
        self.root = root_window
        self.toast_frame: Optional[ctk.CTkFrame] = None
        self.dismiss_after_id = None

    def show(self, message: str, level: str = "success", duration_ms: int = 4000):
        self.hide()

        # High-contrast color mapping with luminous glowing borders
        colors = {
            "success": {
                "bg": "#11111b",
                "border": "#a6e3a1",
                "badge_bg": "#1e3a29",
                "badge_fg": "#a6e3a1",
                "badge_text": "✓ SUKSES",
            },
            "info": {
                "bg": "#11111b",
                "border": "#89b4fa",
                "badge_bg": "#1e293b",
                "badge_fg": "#89b4fa",
                "badge_text": "ℹ INFO",
            },
            "warning": {
                "bg": "#11111b",
                "border": "#f9e2af",
                "badge_bg": "#3e321e",
                "badge_fg": "#f9e2af",
                "badge_text": "⚠️ PERINGATAN",
            },
            "error": {
                "bg": "#11111b",
                "border": "#f38ba8",
                "badge_bg": "#3e1e28",
                "badge_fg": "#f38ba8",
                "badge_text": "❌ ERROR",
            },
        }
        cfg = colors.get(level, colors["info"])

        # Create floating pill with prominent 2px glowing border
        self.toast_frame = ctk.CTkFrame(
            self.root,
            fg_color=cfg["bg"],
            corner_radius=12,
            border_width=2,
            border_color=cfg["border"]
        )

        # Status badge pill
        badge = ctk.CTkLabel(
            self.toast_frame,
            text=cfg["badge_text"],
            font=Fonts.bold(10),
            text_color=cfg["badge_fg"],
            fg_color=cfg["badge_bg"],
            corner_radius=6,
            padx=8,
            pady=3
        )
        badge.pack(side="left", padx=(12, 10), pady=8)

        # Notification message
        lbl_msg = ctk.CTkLabel(
            self.toast_frame,
            text=message,
            font=Fonts.bold(11),
            text_color="#cdd6f4",
            fg_color="transparent",
            wraplength=520,
            justify="left"
        )
        lbl_msg.pack(side="left", padx=(0, 12), pady=8)

        # Close button
        btn_close = ctk.CTkButton(
            self.toast_frame,
            text="✕",
            font=Fonts.bold(11),
            text_color="#a6adc8",
            fg_color="#181825",
            hover_color="#313244",
            width=24,
            height=24,
            corner_radius=12,
            command=self.hide
        )
        btn_close.pack(side="right", padx=(4, 12), pady=8)

        # Place at Top-Center (Prominent notification position)
        self.toast_frame.place(relx=0.5, rely=0.06, anchor="n")
        self.toast_frame.lift()
        self.toast_frame.tkraise()

        # Schedule auto-dismiss
        self.dismiss_after_id = self.root.after(duration_ms, self.hide)

    def hide(self):
        if self.dismiss_after_id:
            try:
                self.root.after_cancel(self.dismiss_after_id)
            except Exception:
                pass
            self.dismiss_after_id = None
        if self.toast_frame and self.toast_frame.winfo_exists():
            try:
                self.toast_frame.destroy()
            except Exception:
                pass
            self.toast_frame = None
