"""
Netools Suite v2.0 - Modern Desktop GUI All-In-One Container (CustomTkinter).
Featuring 1-100% Preloader Splash Screen and Native System Tray Integration.
"""

import sys
import tkinter as tk
from pathlib import Path
from typing import Any, List, Optional

import customtkinter as ctk

from netools.gui.i18n import tr
from netools.gui.splash import SplashScreen
from netools.gui.toast import ToastManager
from netools.gui.tray import TrayManager
from netools.gui.view_dashboard import DashboardView
from netools.gui.view_dns import DNSView
from netools.gui.view_preferences import PreferencesView
from netools.gui.view_proxy import ProxyView
from netools.gui.view_session_extractor import SessionExtractorView
from netools.gui.view_settings import SettingsView


def center_window(window: ctk.CTk, width: int = 920, height: int = 720):
    s_w = window.winfo_screenwidth()
    s_h = window.winfo_screenheight()
    x = max(20, (s_w - width) // 2)
    y = max(20, (s_h - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


class NetoolsApp(ctk.CTk):
    def __init__(self):
        super().__init__(className="netools")
        self.title("Netools Suite")
        self.minsize(850, 650)
        self.withdraw()  # Hidden initially during preloader sequence

        center_window(self, width=920, height=720)

        # Set Linux WM Icon safely
        icon_path = Path(__file__).resolve().parent.parent.parent / "assets" / "icon-64.png"
        if icon_path.exists():
            try:
                self.icon_photo = tk.PhotoImage(file=str(icon_path))
                self.iconphoto(True, self.icon_photo)
            except Exception:
                pass

        self.child_windows: List[ctk.CTkToplevel] = []
        self.minimize_to_tray_enabled = True
        self._last_canary_verdict: Optional[str] = None

        self.protocol("WM_DELETE_WINDOW", self.on_root_close)

        self.toast = ToastManager(self)
        self.tray = TrayManager(self)
        from netools.gui.tray import PYSTRAY_AVAILABLE

        if PYSTRAY_AVAILABLE:
            # Start tray eagerly so close-to-tray works from the first launch.
            # NOTE: do NOT gate this on tray.is_available(); that only becomes
            # true AFTER the icon thread is running.
            self.tray.start()

        from netools.config import _user_cfg
        from netools.gui.theme import ThemeManager

        saved_theme = _user_cfg.get("theme", "dark")
        ThemeManager.apply_theme(saved_theme, self)

        try:
            ctk.set_widget_scaling(float(_user_cfg.get("ui_scale", 1.0)))
        except Exception:
            pass

        self._build_ui()

    def show_toast(self, message: str, level: str = "success", duration_ms: int = 4000) -> None:
        self.toast.show(message, level=level, duration_ms=duration_ms)
        if hasattr(self, "lbl_header_status"):
            from netools.gui.theme import ThemeManager

            fg_map = {
                "success": ThemeManager.success(),
                "info": ThemeManager.primary(),
                "warning": ThemeManager.warning(),
                "error": ThemeManager.danger(),
            }
            clean_msg = message.split("\n")[0][:45]
            self.lbl_header_status.configure(
                text=f"● {clean_msg}", text_color=fg_map.get(level, ThemeManager.primary())
            )

    def _handle_canary_result(self, result):
        """Apply side-effects when DNS canary sweep completes.
        - Update tray icon color
        - Toast on verdict change (clean ↔ intercepted)
        - Optional auto-DoH toggle when doh_auto_canary=True in config.json
        """
        from netools.config import _user_cfg
        from netools.services import canary_service

        verdict = result.verdict if result else "indeterminate"
        # 1) Tray icon update
        if hasattr(self, "tray") and self.tray:
            self.tray.update_status_icon(verdict)

        # 2) Toast on state change (avoid spamming every check)
        if self._last_canary_verdict is not None and self._last_canary_verdict != verdict:
            if verdict == canary_service.VERDICT_INTERCEPTED:
                self.show_toast(
                    "⚠️ DNS Interception terdeteksi! DoH mungkin diblokir.",
                    level="warning",
                )
            elif verdict == canary_service.VERDICT_CLEAN:
                self.show_toast("✅ DNS bersih (no interception).", level="success")
        self._last_canary_verdict = verdict

        # 3) Optional auto-toggle DoH forwarder
        if _user_cfg.get("doh_auto_canary", False):
            from netools.services import doh_service

            if verdict == canary_service.VERDICT_CLEAN:
                if not doh_service.is_doh_forwarder_running():
                    doh_service.start_doh_forwarder(provider=_user_cfg.get("doh_provider", "alidns"))
            elif verdict == canary_service.VERDICT_INTERCEPTED:
                if doh_service.is_doh_forwarder_running():
                    doh_service.stop_doh_forwarder()

    def _apply_theme(self):
        from netools.gui.theme import ThemeManager

        ThemeManager.apply_theme(ThemeManager.get_current_theme_key(), self)

    def apply_theme_in_place(self):
        """In-place dynamic repaint without destroying or rebuilding widgets (0 ms lag, zero flicker)."""
        from netools.gui.theme import ThemeManager

        self.configure(fg_color=ThemeManager.bg())
        if hasattr(self, "header"):
            self.header.configure(fg_color=ThemeManager.surface_alt())
        if hasattr(self, "title_box"):
            self.title_box.configure(fg_color=ThemeManager.surface_alt())
        if hasattr(self, "title_label"):
            self.title_label.configure(text_color=ThemeManager.primary())
        if hasattr(self, "subtitle_label"):
            self.subtitle_label.configure(text_color=ThemeManager.text_muted())
        if hasattr(self, "status_box"):
            self.status_box.configure(fg_color=ThemeManager.bg(), border_color=ThemeManager.border())
        if hasattr(self, "lbl_header_status"):
            self.lbl_header_status.configure(text_color=ThemeManager.success())
        if hasattr(self, "tabview"):
            self.tabview.configure(
                fg_color=ThemeManager.surface(),
                segmented_button_fg_color=ThemeManager.surface_alt(),
                segmented_button_selected_color=ThemeManager.primary(),
                segmented_button_selected_hover_color=ThemeManager.primary(),
                segmented_button_unselected_color=ThemeManager.surface(),
                segmented_button_unselected_hover_color=ThemeManager.surface_alt(),
                text_color=ThemeManager.text(),
                text_color_disabled=ThemeManager.text_muted(),
            )
        if hasattr(self, "dashboard_view") and hasattr(self.dashboard_view, "apply_theme"):
            self.dashboard_view.apply_theme()
        if hasattr(self, "dns_view") and hasattr(self.dns_view, "apply_theme"):
            self.dns_view.apply_theme()
        if hasattr(self, "proxy_view") and hasattr(self.proxy_view, "apply_theme"):
            self.proxy_view.apply_theme()
        if hasattr(self, "settings_view") and hasattr(self.settings_view, "apply_theme"):
            self.settings_view.apply_theme()
        if hasattr(self, "extractor_view") and hasattr(self.extractor_view, "apply_theme"):
            self.extractor_view.apply_theme()
        if hasattr(self, "preferences_view") and hasattr(self.preferences_view, "apply_theme"):
            self.preferences_view.apply_theme()

    def _build_ui(self):
        from netools.gui.theme import Fonts, ThemeManager

        # Header banner
        self.header = ctk.CTkFrame(self, fg_color=ThemeManager.surface_alt(), height=64)
        self.header.pack(fill="x", padx=0, pady=0)
        self.header.pack_propagate(False)

        self.title_box = ctk.CTkFrame(self.header, fg_color=ThemeManager.surface_alt())
        self.title_box.pack(side="left", padx=20, pady=8)

        self.title_label = ctk.CTkLabel(
            self.title_box, text=tr("⚡ Netools Suite v2.0"), font=Fonts.display(17), text_color=ThemeManager.primary()
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            self.title_box,
            text=tr("Unified Sing-box Rotator, Real-Time GRC DNS Benchmark & AI Gateway Router"),
            font=Fonts.regular(11),
            text_color=ThemeManager.text_muted(),
        )
        self.subtitle_label.pack(anchor="w")

        # Right-side Live Status Pill (Visibility of System Status - Nielsen #1)
        self.status_box = ctk.CTkFrame(
            self.header,
            fg_color=ThemeManager.surface(),
            corner_radius=20,
            border_width=1,
            border_color=ThemeManager.border(),
        )
        self.status_box.pack(side="right", padx=20, pady=14)

        self.lbl_header_status = ctk.CTkLabel(
            self.status_box,
            text=tr("● System Ready"),
            font=Fonts.bold(11),
            text_color=ThemeManager.success(),
            padx=14,
            pady=5,
        )
        self.lbl_header_status.pack()

        # Tab View
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=ThemeManager.surface(),
            segmented_button_fg_color=ThemeManager.surface_alt(),
            segmented_button_selected_color=ThemeManager.primary(),
            segmented_button_selected_hover_color=ThemeManager.primary(),
            segmented_button_unselected_color=ThemeManager.surface(),
            segmented_button_unselected_hover_color=ThemeManager.surface_alt(),
            segmented_button_font=Fonts.bold(12),
            text_color=ThemeManager.text(),
            text_color_disabled=ThemeManager.text_muted(),
            corner_radius=10,
        )
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Tab 1: Dashboard
        self.tab_dashboard = self.tabview.add(tr("📊 Dashboard"))
        self.dashboard_view = DashboardView(self.tab_dashboard, self)
        self.dashboard_view.pack(fill="both", expand=True)

        # Tab 2: DNS Suite
        self.tab_dns = self.tabview.add(tr("⚡ DNS Suite"))
        self.dns_view = DNSView(self.tab_dns, self)
        self.dns_view.pack(fill="both", expand=True)

        # Tab 3: Proxy Rotator
        self.tab_proxy = self.tabview.add(tr("🌐 Proxy Rotator"))
        self.proxy_view = ProxyView(self.tab_proxy, self)
        self.proxy_view.pack(fill="both", expand=True)

        # Tab 4: Sync Router (OmniRoute & 9Router)
        self.tab_settings = self.tabview.add(tr("🔌 Sync Router"))
        self.settings_view = SettingsView(self.tab_settings, self)
        self.settings_view.pack(fill="both", expand=True)

        # Tab 5: AI Cookie & Session Extractor
        self.tab_extractor = self.tabview.add(tr("🍪 Cookie Extractor"))
        self.extractor_view = SessionExtractorView(self.tab_extractor, self)
        self.extractor_view.pack(fill="both", expand=True)

        # Tab 6: Settings & About
        self.tab_preferences = self.tabview.add(tr("⚙️ Settings & About"))
        self.preferences_view = PreferencesView(self.tab_preferences, self)
        self.preferences_view.pack(fill="both", expand=True)

    def reload_ui(self):
        """Rebuild entire UI with new theme colors or language while preserving active tab."""
        tab_names = [
            tr("📊 Dashboard"),
            tr("⚡ DNS Suite"),
            tr("🌐 Proxy Rotator"),
            tr("🔌 Sync Router"),
            tr("🍪 Cookie Extractor"),
            tr("⚙️ Settings & About"),
        ]

        active_idx = 4
        if hasattr(self, "tabview"):
            try:
                curr = self.tabview.get()
                for idx, t in enumerate(self.tabview._tab_dict.keys()):
                    if t == curr:
                        active_idx = idx
                        break
            except Exception:
                pass

        for widget in list(self.winfo_children()):
            try:
                widget.destroy()
            except Exception:
                pass

        self._apply_theme()
        self._build_ui()
        if hasattr(self, "tabview"):
            try:
                new_tab_name = tab_names[active_idx] if active_idx < len(tab_names) else tab_names[-1]
                self.tabview.set(new_tab_name)
            except Exception:
                pass

    def select_tab(self, target: Any):
        """Switch to tab by index (0-4), key ('dashboard', 'dns', 'proxy', 'settings', 'preferences'), or title."""
        key_map = {
            "dashboard": 0,
            "dns": 1,
            "proxy": 2,
            "settings": 3,
            "9router": 3,
            "preferences": 4,
            "about": 4,
        }
        if isinstance(target, str) and target.lower() in key_map:
            target = key_map[target.lower()]

        if hasattr(self, "tabview") and hasattr(self.tabview, "_tab_dict"):
            tabs = list(self.tabview._tab_dict.keys())
            if isinstance(target, int) and 0 <= target < len(tabs):
                try:
                    self.tabview.set(tabs[target])
                except Exception:
                    pass
            elif isinstance(target, str) and target in tabs:
                try:
                    self.tabview.set(target)
                except Exception:
                    pass
            elif isinstance(target, str):
                tr_name = tr(target)
                if tr_name in tabs:
                    try:
                        self.tabview.set(tr_name)
                    except Exception:
                        pass

    def restore_from_tray(self):
        """Restore window from System Tray."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def on_root_close(self):
        """Handle window close event (X button).
        Keep running in the System Tray if available; if tray is disabled or unavailable, minimize to taskbar or exit."""
        if hasattr(self, "tray") and self.tray and self.tray.is_running and self.minimize_to_tray_enabled:
            self.withdraw()
            self.show_toast(
                tr("Netools aktif di latar belakang (System Tray). PAC & proxy tetap berjalan."), level="info"
            )
        elif self.minimize_to_tray_enabled:
            # If user wants background persistence but tray daemon is not attached to this desktop session,
            # minimize to taskbar rather than vanishing completely or killing services!
            self.iconify()
            self.show_toast(tr("Netools diminimalkan ke taskbar. PAC & proxy tetap berjalan."), level="info")
        else:
            self.force_exit()

    def force_exit(self):
        """Completely exit the application (stops all background services)."""
        try:
            from netools.adapters import singbox
            from netools.services import doh_service, pac_service, proxy_service, watchdog_service

            pac_service.stop_pac_server()
            doh_service.stop_doh_forwarder()
            proxy_service.stop_proxy_pool()
            singbox.stop_all_singbox_instances()
            watchdog_service.stop_watchdog()
        except Exception:
            pass
        if hasattr(self, "tray") and self.tray:
            self.tray.stop()
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


def main(no_splash: bool = False):
    import os

    from netools.config import ensure_runtime_dirs

    ensure_runtime_dirs()
    app = NetoolsApp()

    skip_splash = no_splash or "--no-splash" in sys.argv or os.getenv("NETOOLS_NO_SPLASH") == "1"

    def on_splash_done():
        try:
            app.deiconify()
            app.update_idletasks()
            app.lift()
            app.focus_force()
        except Exception:
            pass

    if skip_splash:
        on_splash_done()
    else:
        # Failsafe watchdog timer: ensure window deiconifies even if splash fails or on slow XWayland
        app.after(1800, lambda: on_splash_done() if not app.winfo_viewable() else None)
        try:
            SplashScreen(main_app=app, on_complete=on_splash_done)
        except Exception:
            on_splash_done()

    app.mainloop()


if __name__ == "__main__":
    main()
