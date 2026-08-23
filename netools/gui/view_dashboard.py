"""
Tab 1: System Status & Live Dashboard View (CustomTkinter).
"""

import threading

import customtkinter as ctk

from netools.adapters import ninerouter as nr_adapt
from netools.adapters import platform_dns as sys_dns
from netools.config import SOCKS5_PORT_START
from netools.gui.theme import (
    Fonts,
    ThemeManager,
)
from netools.services import pac_service, proxy_service
from netools.state import load_state


class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color=ThemeManager.bg(), corner_radius=0)
        self.main_app = main_app
        self._build_ui()
        self.refresh()

    def apply_theme(self):
        self.configure(fg_color=ThemeManager.bg())
        if hasattr(self, "hdr"): self.hdr.configure(fg_color=ThemeManager.bg())
        if hasattr(self, "lbl_title"): self.lbl_title.configure(text_color=ThemeManager.primary())
        if hasattr(self, "btn_refresh"): self.btn_refresh.configure(fg_color=ThemeManager.border(), text_color=ThemeManager.text(), hover_color=ThemeManager.surface_alt())
        if hasattr(self, "cards"): self.cards.configure(fg_color=ThemeManager.bg())
        if hasattr(self, "card_proxy"): self.card_proxy.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "card_pac"): self.card_pac.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "card_dns"): self.card_dns.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "card_9r"): self.card_9r.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "qa"): self.qa.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "btn_row"): self.btn_row.configure(fg_color=ThemeManager.surface())
        if hasattr(self, "pac_quick"): self.pac_quick.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "pac_url_frame"): self.pac_url_frame.configure(fg_color=ThemeManager.surface())
        if hasattr(self, "pac_entry"): self.pac_entry.configure(fg_color=ThemeManager.surface_alt(), border_color=ThemeManager.border(), text_color=ThemeManager.primary())
        if hasattr(self, "lbl_proxy_stat"): self.lbl_proxy_stat.configure(text_color=ThemeManager.text_muted())
        if hasattr(self, "lbl_pac_stat"): self.lbl_pac_stat.configure(text_color=ThemeManager.text_muted())
        if hasattr(self, "lbl_dns_stat"): self.lbl_dns_stat.configure(text_color=ThemeManager.text_muted())
        if hasattr(self, "lbl_9r_stat"): self.lbl_9r_stat.configure(text_color=ThemeManager.text_muted())

    def _build_ui(self):
        # Header
        self.hdr = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        self.hdr.pack(fill="x", padx=16, pady=(12, 10))

        self.lbl_title = ctk.CTkLabel(
            self.hdr,
            text="📊 Netools Suite — Real-Time Operations",
            font=Fonts.title(16),
            text_color=ThemeManager.primary()
        )
        self.lbl_title.pack(side="left")

        self.btn_refresh = ctk.CTkButton(
            self.hdr,
            text="🔄 Refresh Status",
            font=Fonts.bold(12),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            width=130,
            height=34,
            command=self.refresh
        )
        self.btn_refresh.pack(side="right")

        # Grid of Status Cards
        self.cards = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        self.cards.pack(fill="x", padx=16, pady=4)
        self.cards.grid_columnconfigure((0, 1), weight=1, uniform="dash_card")


        # Instant synchronous state (0 ms lag)
        st = load_state()
        insts = st.get("instances", {})
        active_cnt = len(insts)
        prox_init = f"Status: {'🟢 ' + str(active_cnt) + ' Proxies Active' if active_cnt > 0 else '⚪ Idle / Stopped'}\nPorts: {SOCKS5_PORT_START} - {SOCKS5_PORT_START + max(0, active_cnt-1)}"
        pac_active = pac_service.is_pac_server_running()
        pac_init = f"Status: {'🟢 Active (Listening)' if pac_active else '⚪ Inactive (Stopped)'}\nEndpoint: {pac_service.get_pac_url()}"

        # Card 1: Proxy Pool
        self.card_proxy = ctk.CTkFrame(self.cards, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.card_proxy.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")


        ctk.CTkLabel(
            self.card_proxy,
            text="🌐 Proxy Rotator Pool",
            font=Fonts.subtitle(13),
            text_color=ThemeManager.success()
        ).pack(anchor="w", padx=14, pady=(12, 4))

        self.lbl_proxy_stat = ctk.CTkLabel(
            self.card_proxy,
            text=prox_init,
            font=Fonts.regular(12),
            text_color=ThemeManager.text_muted(),
            justify="left"
        )
        self.lbl_proxy_stat.pack(anchor="w", padx=14, pady=(0, 12))

        # Card 2: PAC Server
        self.card_pac = ctk.CTkFrame(self.cards, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.card_pac.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(
            self.card_pac,
            text="📜 PAC Auto-Config Server",
            font=Fonts.subtitle(13),
            text_color=ThemeManager.primary()
        ).pack(anchor="w", padx=14, pady=(12, 4))

        self.lbl_pac_stat = ctk.CTkLabel(
            self.card_pac,
            text=pac_init,
            font=Fonts.regular(12),
            text_color=ThemeManager.text_muted(),
            justify="left"
        )
        self.lbl_pac_stat.pack(anchor="w", padx=14, pady=(0, 12))

        # Card 3: DNS Resolver
        self.card_dns = ctk.CTkFrame(self.cards, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.card_dns.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(
            self.card_dns,
            text="⚡ Active System DNS",
            font=Fonts.subtitle(13),
            text_color=ThemeManager.warning()
        ).pack(anchor="w", padx=14, pady=(12, 4))

        self.lbl_dns_stat = ctk.CTkLabel(
            self.card_dns,
            text="Interface: Auto-Detecting\nServers  : DHCP Default",
            font=Fonts.regular(12),
            text_color=ThemeManager.text_muted(),
            justify="left"
        )
        self.lbl_dns_stat.pack(anchor="w", padx=14, pady=(0, 12))

        # Card 4: 9Router Gateway
        self.card_9r = ctk.CTkFrame(self.cards, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.card_9r.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")


        ctk.CTkLabel(
            self.card_9r,
            text="🔌 9Router & AI Gateway",
            font=Fonts.subtitle(13),
            text_color=ThemeManager.secondary()
        ).pack(anchor="w", padx=14, pady=(12, 4))

        self.lbl_9r_stat = ctk.CTkLabel(
            self.card_9r,
            text="Gateway: ⚪ Standalone / Offline\nBound Connections: 0",
            font=Fonts.regular(12),
            text_color=ThemeManager.text_muted(),
            justify="left"
        )
        self.lbl_9r_stat.pack(anchor="w", padx=14, pady=(0, 12))

        # Quick Actions Card
        self.qa = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.qa.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(
            self.qa,
            text="⚡ Quick 1-Click Operations",
            font=Fonts.subtitle(13),
            text_color=ThemeManager.text()
        ).pack(anchor="w", padx=14, pady=(12, 8))

        self.btn_row = ctk.CTkFrame(self.qa, fg_color=ThemeManager.surface())
        self.btn_row.pack(fill="x", padx=14, pady=(0, 14))

        ctk.CTkButton(
            self.btn_row,
            text="🚀 Start Proxy Pool",
            font=Fonts.bold(12),
            fg_color=ThemeManager.success(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=36,
            command=self.on_start_pool
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            self.btn_row,
            text="🛑 Stop Proxy Pool",
            font=Fonts.bold(12),
            fg_color=ThemeManager.danger(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.warning(),
            height=36,
            command=self.on_stop_pool
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            self.btn_row,
            text="⚡ GRC Benchmark",
            font=Fonts.bold(12),
            fg_color=ThemeManager.warning(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=36,
            command=lambda: self.main_app.dns_view.open_benchmark()
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            self.btn_row,
            text="♻️ Flush DNS Cache",
            font=Fonts.bold(12),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            height=36,
            command=self.on_flush_dns
        ).pack(side="left", padx=6)

        # PAC Quick Card
        self.pac_quick = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.pac_quick.pack(fill="x", padx=16, pady=4)

        ctk.CTkLabel(
            self.pac_quick,
            text="🌐 System PAC Configuration (Proxy Auto-Configuration)",
            font=Fonts.subtitle(13),
            text_color=ThemeManager.primary()
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.pac_url_frame = ctk.CTkFrame(self.pac_quick, fg_color=ThemeManager.surface())
        self.pac_url_frame.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkLabel(
            self.pac_url_frame,
            text="PAC URL:",
            font=Fonts.bold(12),
            text_color=ThemeManager.text()
        ).pack(side="left", padx=(0, 6))

        self.pac_entry = ctk.CTkEntry(
            self.pac_url_frame,
            width=340,
            height=34,
            font=Fonts.mono(12),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            text_color=ThemeManager.primary()
        )
        self.pac_entry.insert(0, pac_service.get_pac_url())
        self.pac_entry.configure(state="readonly")
        self.pac_entry.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            self.pac_url_frame,
            text="📋 Copy PAC URL",
            font=Fonts.bold(12),
            fg_color=ThemeManager.primary(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=34,
            command=self.copy_pac_url
        ).pack(side="left", padx=4)

        self.btn_pac_action = ctk.CTkButton(
            self.pac_url_frame,
            text="🟢 Start PAC" if not pac_active else "🛑 Stop PAC",
            font=Fonts.bold(12),
            fg_color=ThemeManager.success() if not pac_active else ThemeManager.danger(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent() if not pac_active else ThemeManager.warning(),
            height=34,
            command=self.toggle_pac_server
        )
        self.btn_pac_action.pack(side="left", padx=4)


    def refresh(self):
        def _bg():
            # 1. Proxy
            st = load_state()
            insts = st.get("instances", {})
            active_cnt = len(insts)
            prox_txt = f"Status: {'🟢 ' + str(active_cnt) + ' Proxies Active' if active_cnt > 0 else '⚪ Idle / Stopped'}\nPorts: {SOCKS5_PORT_START} - {SOCKS5_PORT_START + max(0, active_cnt-1)}"

            # 2. PAC
            pac_active = pac_service.is_pac_server_running()
            pac_txt = f"Status: {'🟢 Active (Listening)' if pac_active else '⚪ Inactive (Stopped)'}\nEndpoint: {pac_service.get_pac_url()}"

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
            self.btn_pac_action.configure(text="🛑 Stop PAC", fg_color=ThemeManager.danger(), hover_color=ThemeManager.warning())
        else:
            self.btn_pac_action.configure(text="🟢 Start PAC", fg_color=ThemeManager.success(), hover_color=ThemeManager.accent())

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
        url = pac_service.get_pac_url()
        self.clipboard_clear()
        self.clipboard_append(url)
        self.main_app.show_toast(f"✓ Copied PAC URL to clipboard:\n{url}", level="success")

    def toggle_pac_server(self):
        if pac_service.is_pac_server_running():
            pac_service.stop_pac_server()
            self.main_app.show_toast("PAC Server dihentikan.", level="warning")
        else:
            pac_service.start_pac_server()
            self.main_app.show_toast("✓ PAC Server aktif di " + pac_service.get_pac_url(), level="success")
        self.refresh()
