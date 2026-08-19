"""
Tab 1: System Status & Live Dashboard View (CustomTkinter).
"""

import threading
import tkinter as tk
import customtkinter as ctk
from netools.state import load_state
from netools.services import proxy_service, pac_service
from netools.adapters import platform_dns as sys_dns
from netools.adapters import ninerouter as nr_adapt
from netools.gui.theme import Fonts, COLOR_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_ACCENT_BLUE, COLOR_ACCENT_GREEN, COLOR_ACCENT_PURPLE, COLOR_ACCENT_YELLOW

class DashboardView(ctk.CTkScrollableFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color="#181825", corner_radius=0)
        self.main_app = main_app
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="#181825")
        hdr.pack(fill="x", padx=16, pady=(12, 10))

        ctk.CTkLabel(
            hdr,
            text="📊 Netools Suite — Real-Time Operations",
            font=Fonts.title(15),
            text_color=COLOR_ACCENT_BLUE
        ).pack(side="left")

        ctk.CTkButton(
            hdr,
            text="🔄 Refresh Status",
            font=Fonts.bold(11),
            fg_color="#313244",
            text_color=COLOR_TEXT_PRIMARY,
            hover_color="#45475a",
            width=110,
            height=30,
            command=self.refresh
        ).pack(side="right")

        # Grid of Status Cards
        cards = ctk.CTkFrame(self, fg_color="#181825")
        cards.pack(fill="x", padx=16, pady=4)
        cards.grid_columnconfigure((0, 1), weight=1, uniform="dash_card")

        # Card 1: Proxy Pool
        self.card_proxy = ctk.CTkFrame(cards, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        self.card_proxy.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(
            self.card_proxy,
            text="🌐 Proxy Rotator Pool",
            font=Fonts.subtitle(12),
            text_color=COLOR_ACCENT_GREEN
        ).pack(anchor="w", padx=14, pady=(12, 4))

        self.lbl_proxy_stat = ctk.CTkLabel(
            self.card_proxy,
            text="Checking...",
            font=Fonts.regular(11),
            text_color=COLOR_TEXT_SECONDARY,
            justify="left"
        )
        self.lbl_proxy_stat.pack(anchor="w", padx=14, pady=(0, 12))

        # Card 2: PAC Server
        self.card_pac = ctk.CTkFrame(cards, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        self.card_pac.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(
            self.card_pac,
            text="📜 PAC Auto-Config Server",
            font=Fonts.subtitle(12),
            text_color=COLOR_ACCENT_BLUE
        ).pack(anchor="w", padx=14, pady=(12, 4))

        self.lbl_pac_stat = ctk.CTkLabel(
            self.card_pac,
            text="Checking...",
            font=Fonts.regular(11),
            text_color=COLOR_TEXT_SECONDARY,
            justify="left"
        )
        self.lbl_pac_stat.pack(anchor="w", padx=14, pady=(0, 12))

        # Card 3: DNS Resolver
        self.card_dns = ctk.CTkFrame(cards, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        self.card_dns.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(
            self.card_dns,
            text="⚡ Active System DNS",
            font=Fonts.subtitle(12),
            text_color=COLOR_ACCENT_YELLOW
        ).pack(anchor="w", padx=14, pady=(12, 4))

        self.lbl_dns_stat = ctk.CTkLabel(
            self.card_dns,
            text="Checking...",
            font=Fonts.regular(11),
            text_color=COLOR_TEXT_SECONDARY,
            justify="left"
        )
        self.lbl_dns_stat.pack(anchor="w", padx=14, pady=(0, 12))

        # Card 4: 9Router Gateway
        self.card_9r = ctk.CTkFrame(cards, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        self.card_9r.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(
            self.card_9r,
            text="🔌 9Router & AI Gateway",
            font=Fonts.subtitle(12),
            text_color=COLOR_ACCENT_PURPLE
        ).pack(anchor="w", padx=14, pady=(12, 4))

        self.lbl_9r_stat = ctk.CTkLabel(
            self.card_9r,
            text="Checking...",
            font=Fonts.regular(11),
            text_color=COLOR_TEXT_SECONDARY,
            justify="left"
        )
        self.lbl_9r_stat.pack(anchor="w", padx=14, pady=(0, 12))

        # Quick Actions Card
        qa = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        qa.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(
            qa,
            text="⚡ Quick 1-Click Operations",
            font=Fonts.subtitle(12),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", padx=14, pady=(12, 8))

        btn_row = ctk.CTkFrame(qa, fg_color=COLOR_CARD)
        btn_row.pack(fill="x", padx=14, pady=(0, 14))

        ctk.CTkButton(
            btn_row,
            text="🚀 Start Proxy Pool",
            font=Fonts.bold(11),
            fg_color=COLOR_ACCENT_GREEN,
            text_color="#11111b",
            hover_color="#94e2d5",
            height=32,
            command=self.on_start_pool
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_row,
            text="🛑 Stop Proxy Pool",
            font=Fonts.bold(11),
            fg_color="#f38ba8",
            text_color="#11111b",
            hover_color="#eba0ac",
            height=32,
            command=self.on_stop_pool
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_row,
            text="⚡ GRC Benchmark",
            font=Fonts.bold(11),
            fg_color=COLOR_ACCENT_YELLOW,
            text_color="#11111b",
            hover_color="#f5e0dc",
            height=32,
            command=lambda: self.main_app.dns_view.open_benchmark()
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_row,
            text="♻️ Flush DNS Cache",
            font=Fonts.bold(11),
            fg_color="#313244",
            text_color=COLOR_TEXT_PRIMARY,
            hover_color="#45475a",
            height=32,
            command=self.on_flush_dns
        ).pack(side="left", padx=6)

        # PAC Quick Card
        pac_quick = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        pac_quick.pack(fill="x", padx=16, pady=4)

        ctk.CTkLabel(
            pac_quick,
            text="🌐 System PAC Configuration (Proxy Auto-Configuration)",
            font=Fonts.subtitle(12),
            text_color=COLOR_ACCENT_BLUE
        ).pack(anchor="w", padx=14, pady=(12, 6))

        pac_url_frame = ctk.CTkFrame(pac_quick, fg_color=COLOR_CARD)
        pac_url_frame.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkLabel(
            pac_url_frame,
            text="PAC URL:",
            font=Fonts.bold(11),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left", padx=(0, 6))

        self.pac_entry = ctk.CTkEntry(
            pac_url_frame,
            width=320,
            height=30,
            font=Fonts.mono(11),
            fg_color="#11111b",
            border_color="#45475a",
            text_color=COLOR_ACCENT_BLUE
        )
        self.pac_entry.insert(0, "http://127.0.0.1:18080/proxy.pac")
        self.pac_entry.configure(state="readonly")
        self.pac_entry.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            pac_url_frame,
            text="📋 Copy PAC URL",
            font=Fonts.bold(11),
            fg_color=COLOR_ACCENT_BLUE,
            text_color="#11111b",
            hover_color="#b4befe",
            height=30,
            command=self.copy_pac_url
        ).pack(side="left", padx=4)

        self.btn_pac_toggle = ctk.CTkButton(
            pac_url_frame,
            text="🟢 Start PAC",
            font=Fonts.bold(11),
            fg_color=COLOR_ACCENT_GREEN,
            text_color="#11111b",
            hover_color="#94e2d5",
            height=30,
            command=self.toggle_pac_server
        )
        self.btn_pac_toggle.pack(side="left", padx=4)

    def refresh(self):
        def _bg():
            # 1. Proxy
            st = load_state()
            insts = st.get("instances", {})
            active_cnt = len(insts)
            prox_txt = f"Status: {'🟢 ' + str(active_cnt) + ' Proxies Active' if active_cnt > 0 else '⚪ Idle / Stopped'}\nPorts: 11080 - {11080 + max(0, active_cnt-1)}"

            # 2. PAC
            pac_active = pac_service.is_pac_server_running()
            pac_txt = f"Status: {'🟢 Active (Listening)' if pac_active else '⚪ Inactive (Stopped)'}\nEndpoint: http://127.0.0.1:18080/proxy.pac"

            # 3. DNS
            ifaces = sys_dns.get_network_interfaces()
            def_iface = ifaces[0]["device"] if ifaces else "default"
            dns_ips = sys_dns.get_interface_dns(def_iface)
            dns_txt = f"Interface: {def_iface}\nServers  : {', '.join(dns_ips) if dns_ips else 'DHCP Default'}"

            # 4. 9Router
            try:
                conns = nr_adapt.get_connections()
                conns_cnt = len(conns) if isinstance(conns, list) else 0
                nr_txt = f"Gateway: {'🟢 Connected (20128)' if conns_cnt > 0 else '⚪ Standalone / Offline'}\nBound Connections: {conns_cnt}"
            except Exception:
                nr_txt = "Gateway: ⚪ Standalone / Offline\nBound Connections: 0"

            try:
                self.after(0, lambda: self._update_ui_state(prox_txt, pac_txt, dns_txt, nr_txt, pac_active))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def _update_ui_state(self, prox_txt, pac_txt, dns_txt, nr_txt, pac_active):
        self.lbl_proxy_stat.configure(text=prox_txt)
        self.lbl_pac_stat.configure(text=pac_txt)
        self.lbl_dns_stat.configure(text=dns_txt)
        self.lbl_9r_stat.configure(text=nr_txt)
        if pac_active:
            self.btn_pac_toggle.configure(text="🛑 Stop PAC", fg_color="#f38ba8", hover_color="#eba0ac")
        else:
            self.btn_pac_toggle.configure(text="🟢 Start PAC", fg_color=COLOR_ACCENT_GREEN, hover_color="#94e2d5")

    def on_start_pool(self):
        self.main_app.show_toast("Memulai Turbo Proxy Pool...", level="info")
        def _bg():
            proxy_service.start_proxy_pool(max_instances=20, standalone=False)
            try:
                self.after(0, self.refresh)
                self.after(0, self.main_app.proxy_view.refresh)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def on_stop_pool(self):
        self.main_app.show_toast("Menghentikan Proxy Pool...", level="warning")
        def _bg():
            proxy_service.stop_proxy_pool()
            try:
                self.after(0, self.refresh)
                self.after(0, self.main_app.proxy_view.refresh)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def on_flush_dns(self):
        sys_dns.flush_dns_cache()
        self.main_app.show_toast("✓ DNS Cache berhasil dibersihkan!", level="success")
        self.refresh()

    def copy_pac_url(self):
        url = "http://127.0.0.1:18080/proxy.pac"
        self.clipboard_clear()
        self.clipboard_append(url)
        self.main_app.show_toast(f"✓ Copied PAC URL to clipboard:\n{url}", level="success")

    def toggle_pac_server(self):
        if pac_service.is_pac_server_running():
            pac_service.stop_pac_server()
            self.main_app.show_toast("PAC Server dihentikan.", level="warning")
        else:
            pac_service.start_pac_server()
            self.main_app.show_toast("✓ PAC Server aktif di http://127.0.0.1:18080/proxy.pac", level="success")
        self.refresh()
