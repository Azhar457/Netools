"""
Modern In-App Snackbar / Toast Notification Component (CustomTkinter).
Non-blocking, non-modal, auto-dismissing notification pill.
"""

import customtkinter as ctk
from typing import Optional


class ToastManager:
    def __init__(self, root_window: ctk.CTk):
        self.root = root_window
        self.toast_frame: Optional[ctk.CTkFrame] = None
        self.dismiss_after_id = None

    def show(self, message: str, level: str = "success", duration_ms: int = 3500):
        self.hide()

        colors = {
            "success": {"bg": "#181825", "border": "#a6e3a1", "fg": "#a6e3a1", "icon": "✓"},
            "info":    {"bg": "#181825", "border": "#89b4fa", "fg": "#89b4fa", "icon": "ℹ"},
            "warning": {"bg": "#181825", "border": "#f9e2af", "fg": "#f9e2af", "icon": "⚠️"},
            "error":   {"bg": "#181825", "border": "#f38ba8", "fg": "#f38ba8", "icon": "❌"},
        }
        cfg = colors.get(level, colors["info"])

        self.toast_frame = ctk.CTkFrame(
            self.root,
            fg_color=cfg["bg"],
            corner_radius=10,
            border_width=1,
            border_color=cfg["border"]
        )

        lbl_icon = ctk.CTkLabel(
            self.toast_frame,
            text=cfg["icon"],
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=cfg["fg"],
            fg_color="transparent"
        )
        lbl_icon.pack(side="left", padx=(14, 8))

        lbl_msg = ctk.CTkLabel(
            self.toast_frame,
            text=message,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#cdd6f4",
            fg_color="transparent",
            wraplength=450,
            justify="left"
        )
        lbl_msg.pack(side="left", padx=(0, 10))

        btn_close = ctk.CTkButton(
            self.toast_frame,
            text="✕",
            font=ctk.CTkFont(size=9),
            text_color="#6c7086",
            fg_color="transparent",
            hover_color="#313244",
            width=20,
            height=20,
            command=self.hide
        )
        btn_close.pack(side="right", padx=(4, 14))

        # Position at bottom center
        self.toast_frame.place(relx=0.5, rely=0.93, anchor="s")
        self.toast_frame.lift()

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
