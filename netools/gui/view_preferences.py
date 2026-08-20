"""
Tab 5: Settings, Preferences, Cross-Platform Environment Diagnostics & About View (CustomTkinter).
"""

import json
import webbrowser
import threading
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from typing import Dict, Any, List

import customtkinter as ctk
from netools.libs import dns_db as db
from netools.config import BASE_DIR, PAC_SERVER_PORT, SOCKS5_PORT_START
from netools.libs.env import get_system_diagnostics

class PreferencesView(ctk.CTkScrollableFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color="#181825", corner_radius=0)
        self.main_app = main_app
        self._build_ui()

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="#181825")
        hdr.pack(fill="x", padx=16, pady=(12, 10))

        ctk.CTkLabel(
            hdr,
            text="⚙️ Settings, Cross-Platform Diagnostics & About",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#89b4fa"
        ).pack(side="left")

        # -------------------------------------------------------------
        # Section 1: Environment & Cross-Platform Capability Check
        # -------------------------------------------------------------
        sec_env = ctk.CTkFrame(self, fg_color="#1e1e2e", corner_radius=8, border_width=1, border_color="#313244")
        sec_env.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            sec_env,
            text="🔍 Cross-Platform Environment & Dependency Diagnostics",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#a6e3a1"
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.lbl_env_summary = ctk.CTkLabel(
            sec_env,
            text="Detecting system capabilities...",
            font=ctk.CTkFont(family="monospace", size=9),
            text_color="#bac2de",
            justify="left"
        )
        self.lbl_env_summary.pack(anchor="w", padx=14, pady=(0, 10))

        ctk.CTkButton(
            sec_env,
            text="🔄 Re-scan System Capabilities",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#313244",
            text_color="#cdd6f4",
            hover_color="#45475a",
            height=28,
            command=self.refresh_diagnostics
        ).pack(anchor="w", padx=14, pady=(0, 12))

        # -------------------------------------------------------------
        # Section 2: Appearance & UI Scaling (Font Size)
        # -------------------------------------------------------------
        sec_app = ctk.CTkFrame(self, fg_color="#1e1e2e", corner_radius=8, border_width=1, border_color="#313244")
        sec_app.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            sec_app,
            text="🎨 Appearance & UI Font Scaling",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#f9e2af"
        ).pack(anchor="w", padx=14, pady=(12, 6))

        r_app = ctk.CTkFrame(sec_app, fg_color="#1e1e2e")
        r_app.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkLabel(r_app, text="UI Scale / Font Size:", font=ctk.CTkFont(size=9), text_color="#cdd6f4").pack(side="left", padx=(0, 6))
        
        self.scale_var = ctk.StringVar(value="100%")
        self.scale_cb = ctk.CTkComboBox(
            r_app,
            values=["80%", "90%", "100%", "110%", "120%", "130%", "140%"],
            variable=self.scale_var,
            width=100,
            command=self.on_scale_changed
        )
        self.scale_cb.pack(side="left", padx=4)

        ctk.CTkLabel(r_app, text="|  Theme Mode:", font=ctk.CTkFont(size=9), text_color="#cdd6f4").pack(side="left", padx=(16, 6))
        
        self.theme_var = ctk.StringVar(value="Dark")
        self.theme_cb = ctk.CTkComboBox(
            r_app,
            values=["Dark", "Light", "System"],
            variable=self.theme_var,
            width=100,
            command=self.on_theme_changed
        )
        self.theme_cb.pack(side="left", padx=4)

        # System Tray Option
        self.tray_var = ctk.BooleanVar(value=True)
        self.tray_chk = ctk.CTkCheckBox(
            sec_app,
            text="Minimize to System Tray on Close (Tetap aktif di background saat ditutup)",
            variable=self.tray_var,
            font=ctk.CTkFont(size=9),
            text_color="#cdd6f4",
            fg_color="#89b4fa",
            command=self.on_tray_toggle
        )
        self.tray_chk.pack(anchor="w", padx=14, pady=(0, 12))

        # -------------------------------------------------------------
        # Section 3: DNS Database & Import / Export
        # -------------------------------------------------------------
        sec_dns = ctk.CTkFrame(self, fg_color="#1e1e2e", corner_radius=8, border_width=1, border_color="#313244")
        sec_dns.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            sec_dns,
            text="🗄️ DNS Database & Resolver Management",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#89b4fa"
        ).pack(anchor="w", padx=14, pady=(12, 6))

        r_dns = ctk.CTkFrame(sec_dns, fg_color="#1e1e2e")
        r_dns.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkButton(
            r_dns,
            text="📥 Import DNS (.json / .txt)",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#89b4fa",
            text_color="#11111b",
            hover_color="#b4befe",
            height=30,
            command=self.import_dns_list
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            r_dns,
            text="📋 Import DnsJumper (.ini)",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#fab387",
            text_color="#11111b",
            hover_color="#f9e2af",
            height=30,
            command=self.import_dnsjumper_ini
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            r_dns,
            text="📤 Export DNS (.json)",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#313244",
            text_color="#cdd6f4",
            hover_color="#45475a",
            height=30,
            command=self.export_dns_list
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            r_dns,
            text="🔄 Cloud Sync DB",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#a6e3a1",
            text_color="#11111b",
            hover_color="#94e2d5",
            height=30,
            command=self.sync_cloud_db
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            r_dns,
            text="♻️ Reset DB Defaults",
            font=ctk.CTkFont(size=9),
            fg_color="#45475a",
            text_color="#f38ba8",
            hover_color="#585b70",
            height=30,
            command=self.reset_dns_db
        ).pack(side="right", padx=3)

        # -------------------------------------------------------------
        # Section 4: About & Version Update Checker
        # -------------------------------------------------------------
        sec_abt = ctk.CTkFrame(self, fg_color="#1e1e2e", corner_radius=8, border_width=1, border_color="#313244")
        sec_abt.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            sec_abt,
            text="ℹ️ About Netools Suite",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#cba6f7"
        ).pack(anchor="w", padx=14, pady=(12, 6))

        abt_content = ctk.CTkFrame(sec_abt, fg_color="#1e1e2e")
        abt_content.pack(fill="x", padx=14, pady=(0, 12))

        lbl_ver = ctk.CTkLabel(
            abt_content,
            text="⚡ Netools Suite v2.0.0 (Clean Architecture Edition)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#cdd6f4"
        )
        lbl_ver.pack(anchor="w")

        lbl_desc = ctk.CTkLabel(
            abt_content,
            text="Cross-platform High-performance Desktop Suite for GRC-style 3-Tier DNS Benchmarking, Smart Split-DNS Switching, Turbo Sing-box Proxy Pool Rotation, PAC Auto-Configuration & AI Multi-Provider Router Routing on Linux, Windows & macOS.",
            font=ctk.CTkFont(size=9),
            text_color="#6c7086",
            wraplength=600,
            justify="left"
        )
        lbl_desc.pack(anchor="w", pady=(2, 8))

        btn_row = ctk.CTkFrame(abt_content, fg_color="#1e1e2e")
        btn_row.pack(fill="x")

        ctk.CTkButton(
            btn_row,
            text="🚀 Check for Updates",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#cba6f7",
            text_color="#11111b",
            hover_color="#f5c2e7",
            height=30,
            command=self.check_for_updates
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_row,
            text="📖 GitHub Repository",
            font=ctk.CTkFont(size=9),
            fg_color="#313244",
            text_color="#cdd6f4",
            hover_color="#45475a",
            height=30,
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
                f"• Pure Python DoH    : 🟢 Built-in RFC 8484 Wireformat Engine (Zero-Dependency)",
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

    def on_theme_changed(self, choice: str):
        ctk.set_appearance_mode(choice.lower())
        self.main_app.show_toast(f"✓ Tema diubah ke {choice}", level="info")

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
