"""
PAC Activation Confirmation Modal Dialog.

Ensures explicit user consent and perimeter awareness before starting the
local PAC server and routing system/browser traffic through Netools proxies.
"""

from typing import Callable

import customtkinter as ctk

from netools.gui.i18n import tr
from netools.gui.theme import Fonts, ThemeManager
from netools.gui.wm import mark_dialog


def show_pac_confirmation(parent_widget: ctk.CTkBaseClass, on_confirm: Callable[[], None]) -> None:
    """Display an explicit perimeter warning dialog before starting PAC server."""
    win = ctk.CTkToplevel(parent_widget)
    win.title(tr("⚠️ Konfirmasi Aktivasi PAC Server"))
    win.geometry("520x260")
    win.minsize(460, 240)
    win.resizable(False, False)
    win.configure(fg_color=ThemeManager.bg())

    mark_dialog(win, parent_widget.winfo_toplevel())
    win.grab_set()

    card = ctk.CTkFrame(
        win,
        fg_color=ThemeManager.surface(),
        corner_radius=10,
        border_width=1,
        border_color=ThemeManager.warning(),
    )
    card.pack(fill="both", expand=True, padx=16, pady=16)

    ctk.CTkLabel(
        card,
        text=tr("⚠️ Peringatan Keamanan & Perimeter Jaringan"),
        font=Fonts.title(14),
        text_color=ThemeManager.warning(),
    ).pack(anchor="w", padx=16, pady=(14, 8))

    body_text = (
        tr(
            "Mengaktifkan Server PAC Lokal akan mengarahkan lalu lintas jaringan browser atau sistem melalui proxy lokal Netools.\n\n"
            "Pastikan Anda mempercayai proxy upstream yang sedang aktif sebelum melanjutkan.\n\n"
            "Apakah Anda yakin ingin menyalakan PAC Server?"
        )
    )

    ctk.CTkLabel(
        card,
        text=body_text,
        font=Fonts.regular(11),
        text_color=ThemeManager.text(),
        justify="left",
        wraplength=460,
    ).pack(anchor="w", padx=16, pady=(0, 14))

    btn_row = ctk.CTkFrame(card, fg_color="transparent")
    btn_row.pack(fill="x", padx=16, pady=(0, 12))

    def _on_accept():
        win.destroy()
        on_confirm()

    ctk.CTkButton(
        btn_row,
        text=tr("Batal"),
        font=Fonts.bold(11),
        fg_color=ThemeManager.border(),
        text_color=ThemeManager.text(),
        hover_color=ThemeManager.surface_alt(),
        width=100,
        height=32,
        command=win.destroy,
    ).pack(side="right", padx=(8, 0))

    ctk.CTkButton(
        btn_row,
        text=tr("Aktifkan PAC"),
        font=Fonts.bold(11),
        fg_color=ThemeManager.warning(),
        text_color=ThemeManager.get("on_primary"),
        hover_color=ThemeManager.accent(),
        width=120,
        height=32,
        command=_on_accept,
    ).pack(side="right")
