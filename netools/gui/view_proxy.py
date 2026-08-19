"""
Tab 3: Proxy Rotator, DNS Optimization Guide & Watchdog View (CustomTkinter).
"""

import customtkinter as ctk
import threading
from netools.services import proxy_service, watchdog_service, pac_service


class ProxyView(ctk.CTkFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color="#181825")
        self.main_app = main_app
        self.standalone_var = ctk.BooleanVar(value=False)
        self.watchdog_active = False
        self.watchdog_stop_event = threading.Event()

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header & Info Row
        hdr = ctk.CTkFrame(self, fg_color="#181825")
        hdr.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            hdr,
            text="🌐 Sing-box Proxy Pool & Watchdog",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#89b4fa"
        ).pack(side="left")

        # Action Buttons Row
        act_f = ctk.CTkFrame(self, fg_color="#181825")
        act_f.pack(fill="x", pady=4)

        ctk.CTkButton(
            act_f,
            text="▶ Start Proxy Pool",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#a6e3a1", text_color="#11111b",
            hover_color="#89b4fa",
            height=32,
            command=self.start_pool
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            act_f,
            text="⏹ Stop Proxy Pool",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#f38ba8", text_color="#11111b",
            hover_color="#89b4fa",
            height=32,
            command=self.stop_pool
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            act_f,
            text="🔄 Refresh Pool",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#89b4fa", text_color="#11111b",
            hover_color="#89b4fa",
            height=32,
            command=self.refresh_pool
        ).pack(side="left", padx=2)

        self.btn_pac = ctk.CTkButton(
            act_f,
            text="📜 PAC Server: OFF",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#45475a", text_color="#cdd6f4",
            hover_color="#6c7086",
            height=32,
            width=140,
            command=self.toggle_pac
        )
        self.btn_pac.pack(side="left", padx=3)

        ctk.CTkButton(
            act_f,
            text="📋 Copy PAC URL",
            font=ctk.CTkFont(size=9),
            fg_color="#313244", text_color="#f9e2af",
            hover_color="#45475a",
            height=32,
            width=120,
            command=self.copy_pac_url
        ).pack(side="left", padx=2)

        self.btn_watchdog = ctk.CTkButton(
            act_f,
            text="🛡️ Auto-Heal: OFF",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#45475a", text_color="#cdd6f4",
            hover_color="#6c7086",
            height=32,
            width=150,
            command=self.toggle_watchdog
        )
        self.btn_watchdog.pack(side="right", padx=2)

        # DNS Optimization Guide Banner
        dns_guide = ctk.CTkFrame(
            self, fg_color="#1e1e2e",
            corner_radius=8, border_width=1, border_color="#313244"
        )
        dns_guide.pack(fill="x", pady=6)
        ctk.CTkLabel(
            dns_guide,
            text="💡 Rekomendasi DNS Optimal per Proxy:",
            font=ctk.CTkFont(size=8, weight="bold"),
            text_color="#f9e2af"
        ).pack(anchor="w", padx=12, pady=(8, 0))
        ctk.CTkLabel(
            dns_guide,
            text=(
                "• Model AI Global (OpenAI, Anthropic, DeepSeek, Nvidia NIM, OpenCode) → ⚡ Remote SOCKS5h\n"
                "• Model AI Regional Asia / China (Alibaba, Minimax, GLM) → 🟢 DoH AliDNS\n"
                "• Browsing Lokal Indonesia (.id / Banking) → 🟡 GRC Smart Mix Champion"
            ),
            font=ctk.CTkFont(size=8),
            text_color="#bac2de",
            justify="left"
        ).pack(anchor="w", padx=12, pady=(2, 8))

        # Instances Table (CustomTkinter Treeview via simple Frame + scrollable)
        table_f = ctk.CTkFrame(self, fg_color="#181825")
        table_f.pack(fill="both", expand=True, pady=6, padx=4)

        # Header row
        table_hdr = ctk.CTkFrame(table_f, fg_color="#181825")
        table_hdr.pack(fill="x")
        headers = ["Slot", "Protocol", "Upstream Node", "SOCKS5 Port", "HTTP Port", "DNS Engine", "Status", "Started At"]
        for i, h in enumerate(headers):
            lbl = ctk.CTkLabel(
                table_hdr, text=h,
                font=ctk.CTkFont(size=9, weight="bold"),
                text_color="#a6adc8",
                fg_color="#313244",
                corner_radius=4
            )
            lbl.pack(side="left", fill="x", expand=True, padx=1, pady=2)

        # Scrollable content area
        scroll_f = ctk.CTkFrame(table_f, fg_color="#181825")
        scroll_f.pack(fill="both", expand=True)
        self.table_container = scroll_f

        # Placeholder for data - we'll build rows dynamically in refresh()
        self.table_rows = []

    def refresh(self):
        stat = proxy_service.get_proxy_status()
        pac_running = pac_service.is_pac_server_running()

        if pac_running:
            self.btn_pac.configure(text="📜 PAC Server: ON", fg_color="#a6e3a1", text_color="#11111b")
        else:
            self.btn_pac.configure(text="📜 PAC Server: OFF", fg_color="#45475a", text_color="#cdd6f4")

        # Clear previous rows
        for row in self.table_rows:
            row.destroy()
        self.table_rows.clear()

        for inst in stat["instances"]:
            status_txt = "🟢 Online" if inst["alive"] else "❌ Dead"
            # Row frame
            row_f = ctk.CTkFrame(self.table_container, fg_color="#1e1e2e", corner_radius=4, border_width=1, border_color="#313244")
            row_f.pack(fill="x", pady=1, padx=2)

            data = [
                inst["name"],
                inst["proxy_type"],
                inst["server"],
                f"127.0.0.1:{inst['port']}",
                f"127.0.0.1:{inst['http_port']}",
                inst.get("dns", "⚡ Remote SOCKS5h"),
                status_txt,
                inst["started_at"]
            ]
            for i, val in enumerate(data):
                lbl = ctk.CTkLabel(
                    row_f,
                    text=str(val),
                    font=ctk.CTkFont(size=9),
                    text_color="#cdd6f4",
                    fg_color="#1e1e2e",
                    anchor="w"
                )
                lbl.pack(side="left", fill="x", expand=True, padx=2, pady=4)
            self.table_rows.append(row_f)

        # Auto-refresh watchdog button
        if self.watchdog_active:
            self.btn_watchdog.configure(text="🛡️ Auto-Heal: ON (15s)", fg_color="#a6e3a1", text_color="#11111b")
        else:
            self.btn_watchdog.configure(text="🛡️ Auto-Heal: OFF", fg_color="#45475a", text_color="#cdd6f4")

    def start_pool(self):
        def _run():
            proxy_service.start_proxy_pool(standalone=self.standalone_var.get())
            try:
                self.after(0, self.refresh)
                self.after(0, self.main_app.dashboard_view.refresh)
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()

    def stop_pool(self):
        def _run():
            proxy_service.stop_proxy_pool(standalone=self.standalone_var.get())
            try:
                self.after(0, self.refresh)
                self.after(0, self.main_app.dashboard_view.refresh)
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()

    def refresh_pool(self):
        def _run():
            proxy_service.refresh_proxy_pool(standalone=self.standalone_var.get())
            try:
                self.after(0, self.refresh)
                self.after(0, self.main_app.dashboard_view.refresh)
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()

    def toggle_pac(self):
        if pac_service.is_pac_server_running():
            pac_service.stop_pac_server()
        else:
            pac_service.start_pac_server()
        self.refresh()
        self.main_app.dashboard_view.refresh()

    def copy_pac_url(self):
        url = pac_service.get_pac_url()
        self.clipboard_clear()
        self.clipboard_append(url)
        self.main_app.show_toast(f"✓ PAC URL disalin: {url}", level="success")

    def toggle_watchdog(self):
        if self.watchdog_active:
            self.watchdog_active = False
            self.watchdog_stop_event.set()
            self.btn_watchdog.configure(text="🛡️ Auto-Heal: OFF", fg_color="#45475a", text_color="#cdd6f4")
        else:
            self.watchdog_active = True
            self.watchdog_stop_event.clear()
            self.btn_watchdog.configure(text="🛡️ Auto-Heal: ON (15s)", fg_color="#a6e3a1", text_color="#11111b")
            threading.Thread(
                target=watchdog_service.run_watchdog_loop,
                args=(15, self.standalone_var.get(), self.watchdog_stop_event),
                daemon=True
            ).start()
