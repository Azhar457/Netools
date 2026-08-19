"""
Netools Suite v2.0 - Modern Desktop GUI All-In-One Container (CustomTkinter).
"""

import sys
import customtkinter as ctk
from typing import List

from netools.gui.view_dashboard import DashboardView
from netools.gui.view_dns import DNSView
from netools.gui.view_proxy import ProxyView
from netools.gui.view_settings import SettingsView
from netools.gui.view_preferences import PreferencesView

from netools.gui.toast import ToastManager


def center_window(window: ctk.CTk, width: int = 900, height: int = 720):
    window.update_idletasks()
    s_w = window.winfo_screenwidth()
    s_h = window.winfo_screenheight()
    x = max(20, (s_w - width) // 2)
    y = max(20, (s_h - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


from pathlib import Path


class NetoolsApp(ctk.CTk):
    def __init__(self):
        super().__init__(className="netools")
        self.title("Netools Suite")
        self.minsize(800, 650)

        # Set Linux WM Icon
        icon_path = Path(__file__).resolve().parent.parent.parent / "assets" / "icon-64.png"
        if icon_path.exists():
            try:
                self.icon_photo = ctk.CTkImage(file=str(icon_path))
                self.iconphoto(True, self.icon_photo)
            except Exception:
                pass

        center_window(self, width=900, height=720)

        self.child_windows: List[ctk.CTkToplevel] = []
        self.protocol("WM_DELETE_WINDOW", self.on_root_close)

        self.toast = ToastManager(self)
        self._apply_theme()
        self._build_ui()

    def show_toast(self, message: str, level: str = "success", duration_ms: int = 3500) -> None:
        self.toast.show(message, level=level, duration_ms=duration_ms)

    def _apply_theme(self):
        # Set appearance mode and color theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Custom color overrides for Catppuccin-like theme
        self._fg_color = "#181825"
        self.configure(fg_color=self._fg_color)

    def _build_ui(self):
        # Header banner
        header = ctk.CTkFrame(self, fg_color="#11111b", height=60)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        title_label = ctk.CTkLabel(
            header,
            text="⚡ Netools Suite v2.0",
            font=ctk.CTkFont(family="Sans", size=18, weight="bold"),
            text_color="#89b4fa"
        )
        title_label.pack(anchor="w", padx=20, pady=(10, 0))

        subtitle_label = ctk.CTkLabel(
            header,
            text="Unified Sing-box Rotator, Real-Time GRC DNS Benchmark & AI Gateway Router",
            font=ctk.CTkFont(family="Sans", size=11),
            text_color="#6c7086"
        )
        subtitle_label.pack(anchor="w", padx=20, pady=(2, 8))

        # Tab View (replaces Notebook)
        self.tabview = ctk.CTkTabview(self, fg_color="#1e1e2e", segmented_button_fg_color="#1e1e2e",
                                       segmented_button_selected_color="#313244",
                                       segmented_button_selected_hover_color="#45475a",
                                       segmented_button_unselected_color="#181825",
                                       segmented_button_unselected_hover_color="#313244",
                                       text_color="#a6adc8", text_color_disabled="#6c7086",
                                       corner_radius=8)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Tab 1: Dashboard
        self.tab_dashboard = self.tabview.add("📊 Dashboard")
        self.dashboard_view = DashboardView(self.tab_dashboard, self)
        self.dashboard_view.pack(fill="both", expand=True)

        # Tab 2: DNS Suite
        self.tab_dns = self.tabview.add("⚡ DNS Suite")
        self.dns_view = DNSView(self.tab_dns, self)
        self.dns_view.pack(fill="both", expand=True)

        # Tab 3: Proxy Rotator
        self.tab_proxy = self.tabview.add("🌐 Proxy Rotator")
        self.proxy_view = ProxyView(self.tab_proxy, self)
        self.proxy_view.pack(fill="both", expand=True)

        # Tab 4: 9Router & AI Gateway
        self.tab_settings = self.tabview.add("🔌 9Router & AI Sync")
        self.settings_view = SettingsView(self.tab_settings, self)
        self.settings_view.pack(fill="both", expand=True)

        # Tab 5: Settings & About
        self.tab_preferences = self.tabview.add("⚙️ Settings & About")
        self.preferences_view = PreferencesView(self.tab_preferences, self)
        self.preferences_view.pack(fill="both", expand=True)

    def on_root_close(self):
        for child in list(self.child_windows):
            try:
                child.destroy()
            except Exception:
                pass
        try:
            self.destroy()
        except Exception:
            pass
        sys.exit(0)


def main():
    app = NetoolsApp()
    app.mainloop()


if __name__ == "__main__":
    main()