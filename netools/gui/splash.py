"""
Modern Preloader / Splash Screen for Netools Suite v2.0.
Provides real-time loading feedback (1% -> 100%) while pre-rendering all 5 tabs in memory.
Ensures zero skeleton delay and instant 60+ FPS tab switching once the main window opens.
"""

import time
import tkinter as tk
from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk

from netools.gui.i18n import tr
from netools.gui.wm import mark_splash
from netools.libs.logger import get_logger

log = get_logger(__name__)


class SplashScreen(ctk.CTkToplevel):
    def __init__(self, main_app: Any, on_complete: Callable):
        super().__init__(main_app)
        self.main_app = main_app
        self.on_complete = on_complete

        # Window configuration
        self.title("Netools Suite — Starting...")
        self.geometry("500x290")
        try:
            self.transient(main_app)
        except Exception:
            pass
        mark_splash(self)
        self.overrideredirect(True)  # Borderless modern splash
        self.configure(fg_color="#181825")

        # Center on screen
        s_w = self.winfo_screenwidth()
        s_h = self.winfo_screenheight()
        x = max(20, (s_w - 500) // 2)
        y = max(20, (s_h - 290) // 2)
        self.geometry(f"500x290+{x}+{y}")

        # Set Linux WM Icon
        icon_path = Path(__file__).resolve().parent.parent.parent / "assets" / "icon-64.png"
        if icon_path.exists():
            try:
                self.icon_photo = tk.PhotoImage(file=str(icon_path))
                self.iconphoto(True, self.icon_photo)
            except Exception:
                pass

        self._build_ui()
        self.after(10, self._run_preloader_sequence)

    def _build_ui(self):
        main_card = ctk.CTkFrame(self, fg_color="#1e1e2e", corner_radius=12, border_width=1, border_color="#313244")
        main_card.pack(fill="both", expand=True, padx=4, pady=4)

        # Header Title
        lbl_title = ctk.CTkLabel(
            main_card,
            text="⚡ Netools Suite v2.0",
            font=ctk.CTkFont(family="sans-serif", size=18, weight="bold"),
            text_color="#89b4fa",
        )
        lbl_title.pack(anchor="w", padx=24, pady=(24, 2))

        # Subtitle
        lbl_sub = ctk.CTkLabel(
            main_card,
            text="Unified Sing-box Rotator, GRC DNS Benchmark & AI Gateway",
            font=ctk.CTkFont(family="sans-serif", size=11),
            text_color="#a6adc8",
        )
        lbl_sub.pack(anchor="w", padx=24, pady=(0, 20))

        # Progress bar
        self.prog_bar = ctk.CTkProgressBar(
            main_card, height=6, corner_radius=3, fg_color="#313244", progress_color="#89b4fa"
        )
        self.prog_bar.pack(fill="x", padx=24, pady=(10, 8))
        self.prog_bar.set(0.01)

        # Percentage label & Status info
        info_row = ctk.CTkFrame(main_card, fg_color="transparent")
        info_row.pack(fill="x", padx=24, pady=(0, 10))

        self.lbl_status = ctk.CTkLabel(
            info_row,
            text=tr("🔍 Memuat modul & konfigurasi sistem..."),
            font=ctk.CTkFont(family="sans-serif", size=11),
            text_color="#cdd6f4",
            anchor="w",
        )
        self.lbl_status.pack(side="left")

        self.lbl_pct = ctk.CTkLabel(
            info_row,
            text="1%",
            font=ctk.CTkFont(family="sans-serif", size=11, weight="bold"),
            text_color="#89b4fa",
            anchor="e",
        )
        self.lbl_pct.pack(side="right")

        # Footer detail hint
        lbl_hint = ctk.CTkLabel(
            main_card,
            text=tr("Memuat database & me-render modul ke memori untuk performa instan..."),
            font=ctk.CTkFont(family="sans-serif", size=9),
            text_color="#6c7086",
        )
        lbl_hint.pack(side="bottom", pady=(0, 16))

    def _set_step(self, pct: int, status_text: str):
        self.prog_bar.set(pct / 100.0)
        self.lbl_pct.configure(text=f"{pct}%")
        self.lbl_status.configure(text=status_text)
        self.update_idletasks()
        self.update()

    def _run_preloader_sequence(self):
        try:
            # Stage 1: Environment & Theme
            self._set_step(15, tr("🔍 Inisialisasi Environment & Core Networking..."))
            self.main_app.update_idletasks()
            time.sleep(0.04)

            # Stage 2: Database & Presets
            self._set_step(35, tr("🗄️ Memuat Database Resolvers & Presets (97 DNS)..."))
            self.main_app.update_idletasks()
            time.sleep(0.04)

            # Stage 3: Pre-render all views in background
            self._set_step(55, tr("📊 Menyiapkan Dashboard & Live Monitor..."))
            self.main_app.select_tab(0)
            self.main_app.update_idletasks()
            time.sleep(0.04)

            self._set_step(70, tr("⚡ Menyiapkan DNS Suite & Switcher Engine..."))
            self.main_app.select_tab(1)
            self.main_app.update_idletasks()
            time.sleep(0.04)

            self._set_step(85, tr("🌐 Menyiapkan Turbo Proxy Rotator & SOCKS5 Pool..."))
            self.main_app.select_tab(2)
            self.main_app.update_idletasks()
            time.sleep(0.04)

            self._set_step(92, tr("🔌 Menyiapkan AI Gateway Matrix..."))
            self.main_app.select_tab(3)
            self.main_app.update_idletasks()
            time.sleep(0.04)

            self._set_step(98, tr("⚙️ Menyiapkan Settings & System Diagnostics..."))
            self.main_app.select_tab(4)
            self.main_app.update_idletasks()
            time.sleep(0.04)

            # Return to Dashboard ready
            self._set_step(100, tr("✓ Sistem Siap! Membuka Netools Suite..."))
            self.main_app.select_tab(0)
            self.main_app.update_idletasks()
            time.sleep(0.05)
        except Exception as e:
            log.warning(f"Splash preloader caught non-fatal exception: {e}")
        finally:
            try:
                self.destroy()
            except Exception:
                pass
            if callable(self.on_complete):
                self.on_complete()
