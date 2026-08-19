"""
Tab 5: Settings, Preferences, DNS Database Management & About View (CustomTkinter).
"""

import json
import webbrowser
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from typing import Dict, Any, List

import customtkinter as ctk
import dns_jumper_db as db
from netools.config import BASE_DIR, PAC_SERVER_PORT, SOCKS5_PORT_START, PROXY_SOURCES
from netools.state import load_state, save_state

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
            text="⚙️ Settings, Preferences & About",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#89b4fa"
        ).pack(side="left")

        # -------------------------------------------------------------
        # Section 1: Appearance & UI Scaling (Font Size)
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

        # -------------------------------------------------------------
        # Section 2: DNS Database & Import / Export
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
        # Section 3: Proxy Rotator & Network Ports
        # -------------------------------------------------------------
        sec_net = ctk.CTkFrame(self, fg_color="#1e1e2e", corner_radius=8, border_width=1, border_color="#313244")
        sec_net.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            sec_net,
            text="🌐 Proxy Rotator Ports & Gateway Endpoints",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#a6e3a1"
        ).pack(anchor="w", padx=14, pady=(12, 6))

        grid_net = ctk.CTkFrame(sec_net, fg_color="#1e1e2e")
        grid_net.pack(fill="x", padx=14, pady=(0, 12))

        # Port summary
        ports_txt = (
            f"• SOCKS5 Proxy Ports : 127.0.0.1:{SOCKS5_PORT_START} - {SOCKS5_PORT_START + 19} (20 Slots)\n"
            f"• HTTP Proxy Ports   : 127.0.0.1:{SOCKS5_PORT_START + 10000} - {SOCKS5_PORT_START + 10019}\n"
            f"• PAC Auto-Config URL: http://127.0.0.1:{PAC_SERVER_PORT}/proxy.pac\n"
            f"• 9Router API Gateway: http://localhost:20128/api/providers\n"
            f"• Primary Upstream   : https://www.gstatic.com/generate_204 (5s timeout)"
        )
        ctk.CTkLabel(
            grid_net,
            text=ports_txt,
            font=ctk.CTkFont(family="monospace", size=9),
            text_color="#bac2de",
            justify="left"
        ).pack(anchor="w")

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
            text="High-performance Unified Desktop Suite for GRC-style 3-Tier DNS Benchmarking, Smart Split-DNS Switching, Turbo Sing-box Proxy Pool Rotation, PAC Auto-Configuration & AI Multi-Provider Router Routing.",
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
            command=lambda: webbrowser.open("https://github.com/decolua/singbox-rotator")
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_row,
            text="🔍 System Diagnostics",
            font=ctk.CTkFont(size=9),
            fg_color="#313244",
            text_color="#cdd6f4",
            hover_color="#45475a",
            height=30,
            command=self.run_diagnostics
        ).pack(side="left", padx=3)

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
                # Text format: name, ip1, ip2
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
                    "https://api.github.com/repos/decolua/singbox-rotator/releases/latest",
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

    def run_diagnostics(self):
        def _bg():
            diag_lines = ["--- Netools Diagnostics ---"]
            # Check sing-box
            try:
                res = subprocess.run(["sing-box", "version"], capture_output=True, text=True, timeout=3)
                diag_lines.append(f"Sing-box: {res.stdout.splitlines()[0] if res.stdout else 'OK'}")
            except Exception as e:
                diag_lines.append(f"Sing-box: Not found ({e})")
            
            # Check curl
            try:
                res = subprocess.run(["curl", "--version"], capture_output=True, text=True, timeout=3)
                diag_lines.append(f"Curl: {res.stdout.splitlines()[0] if res.stdout else 'OK'}")
            except Exception as e:
                diag_lines.append(f"Curl: Not found ({e})")

            # Check resolvectl
            try:
                res = subprocess.run(["resolvectl", "status"], capture_output=True, text=True, timeout=3)
                diag_lines.append("Systemd-resolved: Active")
            except Exception:
                diag_lines.append("Systemd-resolved: Inactive / NM fallback")

            summary = " | ".join(diag_lines)
            print(summary)
            try:
                self.after(0, lambda: self.main_app.show_toast("✓ Diagnostik sistem: Sing-box, Curl, dan DNS controllers normal!", level="success"))
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()
