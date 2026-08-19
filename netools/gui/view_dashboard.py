"""
Tab 1: Live Status Dashboard View with PAC Server Controls (CustomTkinter).
"""

import threading
import customtkinter as ctk
from netools.state import load_state
from netools.services import proxy_service, pac_service
from netools.adapters import platform_dns as sys_dns
from netools.adapters import ninerouter as nr_adapt


class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color="#181825")
        self.main_app = main_app
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Title
        title_lbl = ctk.CTkLabel(
            self,
            text="📊 Live Network & Suite Dashboard",
            font=ctk.CTkFont(family="Sans", size=16, weight="bold"),
            text_color="#89b4fa"
        )
        title_lbl.pack(anchor="w", pady=(0, 12))

        # Status Cards Grid (2x2)
        grid_f = ctk.CTkFrame(self, fg_color="#181825")
        grid_f.pack(fill="x", pady=(0, 12))

        # Row 1
        r1 = ctk.CTkFrame(grid_f, fg_color="#181825")
        r1.pack(fill="x", pady=2)

        # Card 1: Proxy Pool
        self.c1 = ctk.CTkFrame(
            r1,
            fg_color="#1e1e2e",
            corner_radius=8,
            border_width=1,
            border_color="#313244"
        )
        self.c1.pack(side="left", fill="both", expand=True, padx=3)

        ctk.CTkLabel(
            self.c1,
            text="🌐 Sing-box Proxy Pool",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#a6adc8"
        ).pack(anchor="w", padx=14, pady=(12, 0))
        self.lbl_proxy_stat = ctk.CTkLabel(
            self.c1,
            text="0 / 20 Active",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#a6e3a1"
        )
        self.lbl_proxy_stat.pack(anchor="w", padx=14, pady=(4, 0))
        self.lbl_proxy_desc = ctk.CTkLabel(
            self.c1,
            text="SOCKS 11080-11099 | HTTP 21080-21099",
            font=ctk.CTkFont(size=9),
            text_color="#6c7086"
        )
        self.lbl_proxy_desc.pack(anchor="w", padx=14)

        # Card 2: PAC Server
        self.c2 = ctk.CTkFrame(
            r1,
            fg_color="#1e1e2e",
            corner_radius=8,
            border_width=1,
            border_color="#313244"
        )
        self.c2.pack(side="left", fill="both", expand=True, padx=3)

        ctk.CTkLabel(
            self.c2,
            text="📜 PAC Auto-Config Server",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#a6adc8"
        ).pack(anchor="w", padx=14, pady=(12, 0))
        self.lbl_pac_stat = ctk.CTkLabel(
            self.c2,
            text="⚪ Stopped",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#a6adc8"
        )
        self.lbl_pac_stat.pack(anchor="w", padx=14, pady=(4, 0))
        self.lbl_pac_desc = ctk.CTkLabel(
            self.c2,
            text="http://127.0.0.1:18080/proxy.pac",
            font=ctk.CTkFont(size=9),
            text_color="#6c7086"
        )
        self.lbl_pac_desc.pack(anchor="w", padx=14)

        # Row 2
        r2 = ctk.CTkFrame(grid_f, fg_color="#181825")
        r2.pack(fill="x", pady=(6, 2))

        # Card 3: System DNS
        self.c3 = ctk.CTkFrame(
            r2,
            fg_color="#1e1e2e",
            corner_radius=8,
            border_width=1,
            border_color="#313244"
        )
        self.c3.pack(side="left", fill="both", expand=True, padx=3)

        ctk.CTkLabel(
            self.c3,
            text="⚡ System DNS Resolver",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#a6adc8"
        ).pack(anchor="w", padx=14, pady=(12, 0))
        self.lbl_dns_stat = ctk.CTkLabel(
            self.c3,
            text="Loading...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#89b4fa"
        )
        self.lbl_dns_stat.pack(anchor="w", padx=14, pady=(4, 0))
        self.lbl_dns_desc = ctk.CTkLabel(
            self.c3,
            text="resolvectl / NetworkManager",
            font=ctk.CTkFont(size=9),
            text_color="#6c7086"
        )
        self.lbl_dns_desc.pack(anchor="w", padx=14)

        # Card 4: 9Router AI Gateway
        self.c4 = ctk.CTkFrame(
            r2,
            fg_color="#1e1e2e",
            corner_radius=8,
            border_width=1,
            border_color="#313244"
        )
        self.c4.pack(side="left", fill="both", expand=True, padx=3)

        ctk.CTkLabel(
            self.c4,
            text="🔌 9Router AI Gateway",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#a6adc8"
        ).pack(anchor="w", padx=14, pady=(12, 0))
        self.lbl_9r_stat = ctk.CTkLabel(
            self.c4,
            text="Detecting...",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#f9e2af"
        )
        self.lbl_9r_stat.pack(anchor="w", padx=14, pady=(4, 0))
        self.lbl_9r_desc = ctk.CTkLabel(
            self.c4,
            text="http://localhost:20128",
            font=ctk.CTkFont(size=9),
            text_color="#6c7086"
        )
        self.lbl_9r_desc.pack(anchor="w", padx=14)

        # Dedicated PAC Server Bar with Copy Button
        pac_card = ctk.CTkFrame(self, fg_color="#1e1e2e", corner_radius=8, border_width=1, border_color="#313244")
        pac_card.pack(fill="x", pady=6)

        p_hdr = ctk.CTkFrame(pac_card, fg_color="#1e1e2e")
        p_hdr.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(
            p_hdr,
            text="📜 PAC URL Settings (Taruh di Network Settings / Browser):",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#cdd6f4"
        ).pack(side="left")
        self.btn_pac_toggle = ctk.CTkButton(
            p_hdr,
            text="▶ Start PAC Server",
            font=ctk.CTkFont(size=8, weight="bold"),
            fg_color="#a6e3a1",
            text_color="#11111b",
            hover_color="#89b4fa",
            width=140,
            height=28,
            command=self.toggle_pac_server
        )
        self.btn_pac_toggle.pack(side="right")

        p_url_f = ctk.CTkFrame(pac_card, fg_color="#1e1e2e")
        p_url_f.pack(fill="x", padx=14, pady=(0, 6))
        self.ent_pac_url = ctk.CTkEntry(
            p_url_f,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#a6e3a1",
            fg_color="#313244",
            border_color="#45475a",
            height=30
        )
        self.ent_pac_url.insert(0, pac_service.get_pac_url())
        self.ent_pac_url.configure(state="readonly")
        self.ent_pac_url.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            p_url_f,
            text="📋 Copy PAC URL",
            font=ctk.CTkFont(size=8, weight="bold"),
            fg_color="#89b4fa",
            text_color="#11111b",
            hover_color="#6c7086",
            width=120,
            height=28,
            command=self.copy_pac_url
        ).pack(side="right")

        # Quick Actions Bar
        act_card = ctk.CTkFrame(self, fg_color="#1e1e2e", corner_radius=8, border_width=1, border_color="#313244")
        act_card.pack(fill="x", pady=6)
        ctk.CTkLabel(
            act_card,
            text="⚡ Quick 1-Click Operations",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#cdd6f4"
        ).pack(anchor="w", pady=(12, 8), padx=14)

        btn_row = ctk.CTkFrame(act_card, fg_color="#1e1e2e")
        btn_row.pack(fill="x", padx=14, pady=(0, 10))

        ctk.CTkButton(
            btn_row,
            text="🚀 Start Proxy Pool",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#a6e3a1",
            text_color="#11111b",
            hover_color="#89b4fa",
            height=30,
            command=self.quick_start_proxy
        ).pack(side="left", padx=3, fill="x", expand=True)

        ctk.CTkButton(
            btn_row,
            text="⏹ Stop Proxy Pool",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#f38ba8",
            text_color="#11111b",
            hover_color="#89b4fa",
            height=30,
            command=self.quick_stop_proxy
        ).pack(side="left", padx=3, fill="x", expand=True)

        ctk.CTkButton(
            btn_row,
            text="🧹 Flush DNS",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#f9e2af",
            text_color="#11111b",
            hover_color="#89b4fa",
            height=30,
            command=self.quick_flush_dns
        ).pack(side="left", padx=3, fill="x", expand=True)

        ctk.CTkButton(
            btn_row,
            text="🔄 Refresh All",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#89b4fa",
            text_color="#11111b",
            hover_color="#89b4fa",
            height=30,
            command=self.refresh
        ).pack(side="right", padx=3, fill="x", expand=True)

    def refresh(self):
        def _bg():
            p_stat = proxy_service.get_proxy_status()
            pac_running = pac_service.is_pac_server_running()
            ifaces = sys_dns.get_network_interfaces()
            dns_txt = "Default DHCP"
            if ifaces:
                active_ips = sys_dns.get_interface_dns(ifaces[0]["device"])
                if active_ips:
                    dns_txt = ", ".join(active_ips[:2])
            is_9r = nr_adapt.is_healthy()

            try:
                self.after(0, lambda: self._apply_data(p_stat, pac_running, dns_txt, is_9r))
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def _apply_data(self, p_stat, pac_running, dns_txt, is_9r):
        self.lbl_proxy_stat.configure(
            text=f"{p_stat['alive_count']} / {p_stat['total']} Active",
            text_color="#a6e3a1" if p_stat['alive_count'] > 0 else "#f38ba8"
        )
        if pac_running:
            self.lbl_pac_stat.configure(text="🟢 Running", text_color="#a6e3a1")
            self.btn_pac_toggle.configure(text="⏹ Stop PAC Server", fg_color="#f38ba8", text_color="#11111b")
        else:
            self.lbl_pac_stat.configure(text="⚪ Stopped", text_color="#a6adc8")
            self.btn_pac_toggle.configure(text="▶ Start PAC Server", fg_color="#a6e3a1", text_color="#11111b")
        self.lbl_dns_stat.configure(text=dns_txt)
        self.lbl_9r_stat.configure(text="✓ Online" if is_9r else "Standalone", text_color="#a6e3a1" if is_9r else "#a6adc8")

    def toggle_pac_server(self):
        if pac_service.is_pac_server_running():
            pac_service.stop_pac_server()
        else:
            pac_service.start_pac_server()
        self.refresh()

    def copy_pac_url(self):
        url = pac_service.get_pac_url()
        self.clipboard_clear()
        self.clipboard_append(url)
        self.main_app.show_toast(f"✓ PAC URL disalin: {url}", level="success")

    def quick_start_proxy(self):
        def _run():
            self.main_app.show_toast("Memulai Sing-box Proxy Pool...", level="info")
            proxy_service.start_proxy_pool()
            self.refresh()
            self.main_app.proxy_view.refresh()
            self.main_app.show_toast("✓ Proxy Pool aktif!", level="success")
        threading.Thread(target=_run, daemon=True).start()

    def quick_stop_proxy(self):
        def _run():
            proxy_service.stop_proxy_pool()
            self.refresh()
            self.main_app.proxy_view.refresh()
            self.main_app.show_toast("✓ Proxy Pool dihentikan.", level="info")
        threading.Thread(target=_run, daemon=True).start()

    def quick_flush_dns(self):
        sys_dns.flush_dns_cache()
        self.main_app.show_toast("✓ DNS Cache berhasil di-flush!", level="success")
        self.refresh()
