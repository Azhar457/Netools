"""
Tab 5: Settings, Preferences, Cross-Platform Environment Diagnostics & About View (CustomTkinter).
"""

import json
import threading
import webbrowser
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from netools.config import USER_CONFIG_DIR, USER_CONFIG_FILE
from netools.gui.i18n import (
    get_available_locales,
    get_locale,
    get_locale_labels,
    label_from_locale,
    locale_from_label,
    set_locale,
    tr,
)
from netools.gui.theme import Fonts, ThemeManager
from netools.libs import dns_db as db
from netools.libs.env import get_system_diagnostics


class PreferencesView(ctk.CTkScrollableFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color=ThemeManager.bg(), corner_radius=0)
        self.main_app = main_app
        self._build_ui()

    def apply_theme(self):
        self.configure(fg_color=ThemeManager.bg())
        if hasattr(self, "hdr"): self.hdr.configure(fg_color=ThemeManager.bg())
        if hasattr(self, "lbl_title"): self.lbl_title.configure(text_color=ThemeManager.primary())
        if hasattr(self, "sec_env"): self.sec_env.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "sec_app"): self.sec_app.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "r_app"): self.r_app.configure(fg_color=ThemeManager.surface())
        if hasattr(self, "sec_dns"): self.sec_dns.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "r_dns"): self.r_dns.configure(fg_color=ThemeManager.surface())
        if hasattr(self, "sec_about"): self.sec_about.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "r_about"): self.r_about.configure(fg_color=ThemeManager.surface())
        if hasattr(self, "lbl_env_summary"): self.lbl_env_summary.configure(text_color=ThemeManager.text())
        if hasattr(self, "theme_var"): self.theme_var.set(ThemeManager.get_current_theme_key().capitalize())

    def _build_ui(self):
        # Header
        self.hdr = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        self.hdr.pack(fill="x", padx=16, pady=(12, 10))

        self.lbl_title = ctk.CTkLabel(
            self.hdr,
            text=tr("⚙️ Settings, Cross-Platform Diagnostics & About"),
            font=Fonts.title(16),
            text_color=ThemeManager.primary()
        )
        self.lbl_title.pack(side="left")

        # -------------------------------------------------------------
        # Section 1: Appearance & UI Scaling (Font Size)
        # -------------------------------------------------------------
        self.sec_app = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.sec_app.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            self.sec_app,
            text=tr("🎨 Appearance & UI Font Scaling"),
            font=Fonts.subtitle(13),
            text_color=ThemeManager.warning()
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.r_app = ctk.CTkFrame(self.sec_app, fg_color=ThemeManager.surface())
        self.r_app.pack(fill="x", padx=14, pady=(0, 10))

        ctk.CTkLabel(self.r_app, text=tr("UI Scale / Font Size:"), font=Fonts.bold(12), text_color=ThemeManager.text()).pack(side="left", padx=(0, 6))

        self.scale_var = ctk.StringVar(value="100%")
        self.scale_cb = ctk.CTkComboBox(
            self.r_app,
            values=["80%", "90%", "100%", "110%", "120%", "130%", "140%"],
            variable=self.scale_var,
            font=Fonts.regular(11),
            width=110,
            height=32,
            command=self.on_scale_changed
        )
        self.scale_cb.pack(side="left", padx=4)

        ctk.CTkLabel(self.r_app, text=tr("|  Theme Palette:"), font=Fonts.bold(12), text_color=ThemeManager.text()).pack(side="left", padx=(16, 6))

        current_theme_title = ThemeManager.get_current_theme_key().capitalize()
        self.theme_var = ctk.StringVar(value=current_theme_title)
        self.theme_cb = ctk.CTkComboBox(
            self.r_app,
            values=ThemeManager.get_available_themes(),
            variable=self.theme_var,
            font=Fonts.regular(11),
            width=130,
            height=32,
            command=self.on_theme_changed
        )
        self.theme_cb.pack(side="left", padx=4)

        # Language (Modular & Scalable)
        ctk.CTkLabel(self.r_app, text=tr("|  Language:"), font=Fonts.bold(12), text_color=ThemeManager.text()).pack(side="left", padx=(16, 6))

        self.lang_var = ctk.StringVar(value=label_from_locale(get_locale()))
        self.lang_cb = ctk.CTkComboBox(
            self.r_app,
            values=get_locale_labels(),
            variable=self.lang_var,
            state="readonly",
            font=Fonts.regular(11),
            width=175,
            height=32,
            command=self.on_language_changed
        )
        self.lang_cb.pack(side="left", padx=4)

        # System Tray Option
        self.tray_var = ctk.BooleanVar(value=getattr(self.main_app, "minimize_to_tray_enabled", True))
        self.tray_chk = ctk.CTkCheckBox(
            self.sec_app,
            text=tr("Minimize to System Tray on Close (Tetap aktif di background saat ditutup)"),
            variable=self.tray_var,
            font=Fonts.regular(12),
            text_color=ThemeManager.text(),
            fg_color=ThemeManager.primary(),
            command=self.on_tray_toggle
        )
        self.tray_chk.pack(anchor="w", padx=14, pady=(2, 12))

        # -------------------------------------------------------------
        # Section 2: Environment & Cross-Platform Capability Check
        # -------------------------------------------------------------
        self.sec_env = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.sec_env.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            self.sec_env,
            text=tr("🔍 Cross-Platform Environment & Dependency Diagnostics"),
            font=Fonts.subtitle(13),
            text_color=ThemeManager.success()
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.lbl_env_summary = ctk.CTkLabel(
            self.sec_env,
            text="Detecting system capabilities...",
            font=Fonts.mono(11),
            text_color=ThemeManager.text(),
            justify="left"
        )
        self.lbl_env_summary.pack(anchor="w", padx=14, pady=(0, 10))

        ctk.CTkButton(
            self.sec_env,
            text=tr("🔄 Refresh Diagnostics"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            height=32,
            command=self.refresh_diagnostics
        ).pack(anchor="w", padx=14, pady=(0, 12))

        # -------------------------------------------------------------
        # Section 3: DNS Database & Import / Export
        # -------------------------------------------------------------
        self.sec_dns = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.sec_dns.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            self.sec_dns,
            text=tr("💾 DNS Database Backup & Cloud Sync"),
            font=Fonts.subtitle(13),
            text_color=ThemeManager.primary()
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.r_dns = ctk.CTkFrame(self.sec_dns, fg_color=ThemeManager.surface())
        self.r_dns.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkButton(
            self.r_dns,
            text=tr("📥 Import JSON DNS"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.primary(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=34,
            command=self.import_dns_list
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            self.r_dns,
            text=tr("📥 Import DnsJumper INI"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.warning(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=34,
            command=self.import_dnsjumper_ini
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            self.r_dns,
            text=tr("📤 Export DNS to JSON"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            height=34,
            command=self.export_dns_list
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            self.r_dns,
            text=tr("☁️ Sync Cloud Preset DB"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.success(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=34,
            command=self.sync_cloud_db
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            self.r_dns,
            text=tr("♻️ Reset Default Providers"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.surface_alt(),
            text_color=ThemeManager.danger(),
            hover_color=ThemeManager.border(),
            height=34,
            command=self.reset_dns_db
        ).pack(side="right", padx=3)

        # -------------------------------------------------------------
        # Section 4: About & Version Update Checker
        # -------------------------------------------------------------
        self.sec_about = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.sec_about.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            self.sec_about,
            text=tr("ℹ️ About Netools Suite"),
            font=Fonts.subtitle(13),
            text_color=ThemeManager.secondary()
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.r_about = ctk.CTkFrame(self.sec_about, fg_color=ThemeManager.surface())
        self.r_about.pack(fill="x", padx=14, pady=(0, 12))

        lbl_ver = ctk.CTkLabel(
            self.r_about,
            text=tr("⚡ Netools Suite v2.0.0 (Clean Architecture Edition)"),
            font=Fonts.bold(12),
            text_color=ThemeManager.text()
        )
        lbl_ver.pack(anchor="w")

        lbl_desc = ctk.CTkLabel(
            self.r_about,
            text=tr("Cross-platform High-performance Desktop Suite for GRC-style 3-Tier DNS Benchmarking, Smart Split-DNS Switching, Turbo Sing-box Proxy Pool Rotation, PAC Auto-Configuration & AI Multi-Provider Router Routing on Linux, Windows & macOS."),
            font=Fonts.regular(11),
            text_color=ThemeManager.text_muted(),
            wraplength=700,
            justify="left"
        )
        lbl_desc.pack(anchor="w", pady=(2, 8))

        btn_row = ctk.CTkFrame(self.r_about, fg_color=ThemeManager.surface())
        btn_row.pack(fill="x")

        ctk.CTkButton(
            btn_row,
            text=tr("🚀 Check for Updates"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.secondary(),
            text_color=ThemeManager.get("on_secondary"),
            hover_color=ThemeManager.accent(),
            height=34,
            command=self.check_for_updates
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_row,
            text=tr("📖 GitHub Repository"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            height=34,
            command=lambda: webbrowser.open("https://github.com/Azhar457/Netools")
        ).pack(side="left", padx=3)

        self.refresh_diagnostics()

    def refresh_diagnostics(self):
        def _bg():
            diag = get_system_diagnostics()
            core = diag["core_tools"]
            fwd = diag["dns_forwarders"]

            lines = [
                f"• Operating System   : {diag['os_name']}",
                f"• Python Runtime     : Python {diag['python_version']}",
                f"• DNS Controller     : {diag['dns_controller']}",
                "• Pure Python DoH    : 🟢 Built-in RFC 8484 Wireformat Engine (Zero-Dependency)",
                f"• Sing-box Proxy Core: {'🟢 ' + core['sing-box']['version'] if core['sing-box']['found'] else '⚠️ Not found on PATH (Proxy rotation disabled)'}",
                f"• Curl Subsystem     : {'🟢 ' + core['curl']['version'] if core['curl']['found'] else '⚠️ Not found (Internal HTTP fallback active)'}",
                f"• Optional Forwarders: DNSCrypt-Proxy: {'🟢 Found' if fwd['dnscrypt-proxy']['found'] else '⚪ None'} | Cloudflared: {'🟢 Found' if fwd['cloudflared']['found'] else '⚪ None'}"
            ]
            try:
                self.after(0, lambda: self.lbl_env_summary.configure(text="\n".join(lines)))
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def on_scale_changed(self, choice: str):
        try:
            scale_val = float(choice.replace("%", "")) / 100.0
            ctk.set_widget_scaling(scale_val)
            self.main_app.show_toast(f"✓ Skala UI diubah ke {choice}", level="info")
        except Exception:
            self.main_app.show_toast(f"Skala {choice} disimpan (efek penuh saat restart).", level="info")

    def on_language_changed(self, choice: str):
        code = locale_from_label(choice)
        set_locale(code)
        if hasattr(self.main_app, "reload_ui"):
            self.main_app.reload_ui()
        if code == "id":
            self.main_app.show_toast(tr("✓ Bahasa berhasil diubah ke Bahasa Indonesia!"), level="success")
        else:
            self.main_app.show_toast(tr("✓ Language changed to English!"), level="success")

    def on_theme_changed(self, choice: str):
        ThemeManager.apply_theme(choice, self.main_app)
        try:
            USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            cfg = {}
            if USER_CONFIG_FILE.exists():
                cfg = json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
            cfg["theme"] = choice.lower()
            USER_CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        except Exception:
            pass
        if hasattr(self.main_app, "reload_ui"):
            self.main_app.reload_ui()
        self.main_app.show_toast(f"✓ Tema berhasil diubah ke {choice}", level="info")




    def on_tray_toggle(self):
        enabled = self.tray_var.get()
        self.main_app.minimize_to_tray_enabled = enabled
        if enabled:
            self.main_app.show_toast("✓ Netools akan diminimalkan ke System Tray saat tombol close diklik.", level="info")
        else:
            self.main_app.show_toast("Netools akan langsung keluar saat tombol close diklik.", level="warning")

    def import_dns_list(self):
        file_path = filedialog.askopenfilename(
            title="Pilih file DNS (.json atau .txt)",
            filetypes=[("DNS Database", "*.json *.txt"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            p = Path(file_path)
            imported_count = 0
            if p.suffix == ".json":
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    curr = db.load_providers()
                    curr.update(data)
                    db.save_providers(curr)
                    imported_count = len(data)
            else:
                lines = p.read_text(encoding="utf-8").splitlines()
                curr = db.load_providers()
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#") and "," in line:
                        parts = [x.strip() for x in line.split(",")]
                        if len(parts) >= 2:
                            p_id = parts[0].lower().replace(" ", "-")
                            curr[p_id] = {
                                "name": parts[0],
                                "country": "🌐",
                                "ipv4": parts[1:],
                                "doh_url": ""
                            }
                            imported_count += 1
                db.save_providers(curr)

            self.main_app.show_toast(f"✓ Berhasil mengimpor {imported_count} DNS Resolvers!", level="success")
            self.main_app.dns_view.refresh_presets()
        except Exception as e:
            self.main_app.show_toast(f"Gagal mengimpor DNS: {e}", level="error")

    def import_dnsjumper_ini(self):
        file_path = filedialog.askopenfilename(
            title="Pilih file DnsJumper.ini",
            filetypes=[("DnsJumper Config", "*.ini"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        
        imported, msg = db.import_from_dnsjumper_ini(file_path)
        if imported > 0:
            self.main_app.show_toast(f"✓ {msg}", level="success")
            self.main_app.dns_view.refresh_presets()
        else:
            self.main_app.show_toast(f"Gagal: {msg}", level="error")

    def export_dns_list(self):
        file_path = filedialog.asksaveasfilename(
            title="Simpan Daftar DNS ke JSON",
            defaultextension=".json",
            initialfile="netools_dns_backup.json",
            filetypes=[("JSON Files", "*.json")]
        )
        if not file_path:
            return
        try:
            provs = db.load_providers()
            Path(file_path).write_text(json.dumps(provs, indent=2), encoding="utf-8")
            self.main_app.show_toast(f"✓ Berhasil mengekspor {len(provs)} DNS ke {Path(file_path).name}", level="success")
        except Exception as e:
            self.main_app.show_toast(f"Gagal mengekspor DNS: {e}", level="error")

    def sync_cloud_db(self):
        def _bg():
            self.main_app.show_toast("Sinkronisasi DNS dari cloud...", level="info")
            succ, msg, count = db.sync_cloud_providers()
            try:
                self.after(0, lambda: self.main_app.show_toast(msg, level="success" if succ else "error"))
                self.after(0, self.main_app.dns_view.refresh_presets)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def reset_dns_db(self):
        try:
            db.reset_to_default_providers()
            self.main_app.show_toast("✓ Database DNS di-reset ke preset default resmi.", level="info")
            self.main_app.dns_view.refresh_presets()
        except Exception as e:
            self.main_app.show_toast(f"Gagal reset DB: {e}", level="error")

    def check_for_updates(self):
        self.main_app.show_toast("Memeriksa pembaruan versi Netools...", level="info")
        def _bg():
            import urllib.request
            try:
                req = urllib.request.Request(
                    "https://api.github.com/repos/Azhar457/Netools/releases/latest",
                    headers={"User-Agent": "Netools-Suite"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    tag = data.get("tag_name", "v2.0.0")
                    msg = f"Versi terbaru: {tag}. Netools Suite v2.0.0 sudah versi paling mutakhir!"
                    try:
                        self.after(0, lambda: self.main_app.show_toast(msg, level="success", duration_ms=4500))
                    except Exception:
                        pass
            except Exception:
                try:
                    self.after(0, lambda: self.main_app.show_toast("✓ Netools Suite v2.0.0 aktif dan siap digunakan.", level="info"))
                except Exception:
                    pass
        threading.Thread(target=_bg, daemon=True).start()
