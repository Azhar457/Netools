"""
Tab 3: Turbo Sing-box Proxy Pool Rotator & Watchdog View (CustomTkinter).
"""

import threading
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from netools.state import load_state
from netools.services import proxy_service, pac_service, watchdog_service
from netools.config import SOCKS5_PORT_START, HTTP_PORT_OFFSET
from netools.gui.theme import Fonts, COLOR_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_ACCENT_BLUE, COLOR_ACCENT_GREEN, COLOR_ACCENT_PURPLE, COLOR_ACCENT_YELLOW

class ProxyView(ctk.CTkFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color="#181825", corner_radius=0)
        self.main_app = main_app
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header Controls
        hdr = ctk.CTkFrame(self, fg_color="#181825")
        hdr.pack(fill="x", padx=16, pady=(12, 8))

        ctk.CTkLabel(
            hdr,
            text="🌐 Turbo Sing-box Proxy Rotator",
            font=Fonts.title(15),
            text_color=COLOR_ACCENT_GREEN
        ).pack(side="left")

        # Action Buttons
        self.btn_start = ctk.CTkButton(
            hdr,
            text="🚀 Start Pool",
            font=Fonts.bold(11),
            fg_color=COLOR_ACCENT_GREEN,
            text_color="#11111b",
            hover_color="#94e2d5",
            height=30,
            command=self.on_start
        )
        self.btn_start.pack(side="left", padx=(16, 4))

        self.btn_stop = ctk.CTkButton(
            hdr,
            text="🛑 Stop Pool",
            font=Fonts.bold(11),
            fg_color="#f38ba8",
            text_color="#11111b",
            hover_color="#eba0ac",
            height=30,
            command=self.on_stop
        )
        self.btn_stop.pack(side="left", padx=4)

        self.btn_refresh = ctk.CTkButton(
            hdr,
            text="🔄 Refresh",
            font=Fonts.bold(11),
            fg_color="#313244",
            text_color=COLOR_TEXT_PRIMARY,
            hover_color="#45475a",
            height=30,
            command=self.on_refresh
        )
        self.btn_refresh.pack(side="left", padx=4)

        self.watchdog_var = ctk.BooleanVar(value=False)
        self.chk_watchdog = ctk.CTkCheckBox(
            hdr,
            text="Auto-Heal Watchdog",
            variable=self.watchdog_var,
            font=Fonts.bold(11),
            text_color=COLOR_TEXT_PRIMARY,
            fg_color=COLOR_ACCENT_GREEN,
            command=self.toggle_watchdog
        )
        self.chk_watchdog.pack(side="left", padx=14)

        # PAC Toggle Button
        self.btn_pac_toggle = ctk.CTkButton(
            hdr,
            text="🟢 Start PAC",
            font=Fonts.bold(11),
            fg_color=COLOR_ACCENT_BLUE,
            text_color="#11111b",
            hover_color="#b4befe",
            height=30,
            command=self.toggle_pac
        )
        self.btn_pac_toggle.pack(side="right", padx=(4, 0))

        # Status Summary Bar
        summary_card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        summary_card.pack(fill="x", padx=16, pady=4)

        self.lbl_summary = ctk.CTkLabel(
            summary_card,
            text="Instances: 0 active | SOCKS: 11080–11099 | HTTP: 21080–21099 | Upstream: gstatic 204",
            font=Fonts.mono(11),
            text_color=COLOR_TEXT_SECONDARY
        )
        self.lbl_summary.pack(padx=14, pady=8, anchor="w")

        # Treeview Table for Proxies
        tbl_frame = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        tbl_frame.pack(fill="both", expand=True, padx=16, pady=6)

        columns = ("slot", "protocol", "server", "socks", "http", "pool", "dns", "status", "age")
        self.tree = ttk.Treeview(
            tbl_frame,
            columns=columns,
            show="headings",
            selectmode="browse"
        )

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#1e1e2e",
            foreground="#cdd6f4",
            fieldbackground="#1e1e2e",
            rowheight=26,
            font=("sans-serif", 10)
        )
        style.configure(
            "Treeview.Heading",
            background="#313244",
            foreground="#cdd6f4",
            font=("sans-serif", 10, "bold")
        )
        style.map("Treeview", background=[("selected", "#45475a")])

        cols_config = [
            ("slot", "Slot ID", 80, "center"),
            ("protocol", "Protocol", 110, "center"),
            ("server", "Upstream Node", 200, "center"),
            ("socks", "SOCKS5 Port", 110, "center"),
            ("http", "HTTP Port", 110, "center"),
            ("pool", "Router Pool", 130, "center"),
            ("dns", "DNS Engine", 150, "center"),
            ("status", "Status", 100, "center"),
            ("age", "Started At", 160, "center"),
        ]

        self.sort_directions = {}
        for col_id, title, w, align in cols_config:
            self.tree.heading(col_id, text=f"{title} ↕", anchor=align, command=lambda c=col_id: self.sort_column(c))
            self.tree.column(col_id, width=w, minwidth=70, anchor=align, stretch=True)

        vsb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", padx=(0, 8), pady=8)

        # Instant initial sync render (0 ms delay)
        self._populate_sync()

    def sort_column(self, col: str):
        """Sort Proxy Treeview rows by clicking column headers."""
        reverse = self.sort_directions.get(col, False)
        self.sort_directions[col] = not reverse

        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

        def _val_key(v):
            clean = str(v).strip()
            try:
                return float(clean)
            except ValueError:
                return clean.lower()

        items.sort(key=lambda t: _val_key(t[0]), reverse=reverse)

        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

    def _populate_sync(self):
        st = load_state()
        insts = st.get("instances", {})
        pac_running = pac_service.is_pac_server_running()

        for item in self.tree.get_children():
            self.tree.delete(item)

        for name, data in sorted(insts.items()):
            port = data.get("port", 11080)
            http_p = port + HTTP_PORT_OFFSET
            proto = data.get("proxy_type") or data.get("protocol") or "shadowsocks"
            srv = f"{data.get('server', '')}:{data.get('server_port', '')}"
            pool = data.get("pool_name") or data.get("pool_id") or "—"
            dns_engine = "SOCKS5h Remote"
            age = data.get("started_at", "Just now")
            status = "🟢 Alive"

            self.tree.insert("", "end", values=(
                name, proto, srv, port, http_p, pool, dns_engine, status, age
            ))

        cnt = len(insts)
        self.lbl_summary.configure(
            text=f"Instances: {cnt} active | SOCKS: {SOCKS5_PORT_START}–{SOCKS5_PORT_START + max(0, cnt-1)} | HTTP: {SOCKS5_PORT_START + HTTP_PORT_OFFSET}–{SOCKS5_PORT_START + HTTP_PORT_OFFSET + max(0, cnt-1)} | Upstream: gstatic 204"
        )

        if pac_running:
            self.btn_pac_toggle.configure(text="🛑 Stop PAC", fg_color="#f38ba8", hover_color="#eba0ac")
        else:
            self.btn_pac_toggle.configure(text="🟢 Start PAC", fg_color=COLOR_ACCENT_BLUE, hover_color="#b4befe")

    def refresh(self):
        try:
            self._populate_sync()
        except Exception:
            pass

    def on_start(self):
        self.main_app.show_toast("Mengunduh & memulai Turbo Proxy Pool...", level="info")
        def _bg():
            proxy_service.start_proxy_pool(max_instances=20, standalone=False)
            try:
                self.after(0, self.refresh)
                self.after(0, self.main_app.dashboard_view.refresh)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def on_stop(self):
        self.main_app.show_toast("Menghentikan seluruh instance Proxy...", level="warning")
        def _bg():
            proxy_service.stop_proxy_pool()
            try:
                self.after(0, self.refresh)
                self.after(0, self.main_app.dashboard_view.refresh)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def on_refresh(self):
        self.refresh()
        self.main_app.show_toast("✓ Proxy table refreshed.", level="info")

    def toggle_watchdog(self):
        if self.watchdog_var.get():
            watchdog_service.start_watchdog_thread(interval=15)
            self.main_app.show_toast("✓ Auto-Heal Watchdog aktif (setiap 15s)!", level="success")
        else:
            watchdog_service.stop_watchdog()
            self.main_app.show_toast("Auto-Heal Watchdog dimatikan.", level="warning")

    def toggle_pac(self):
        if pac_service.is_pac_server_running():
            pac_service.stop_pac_server()
            self.main_app.show_toast("PAC Server dihentikan.", level="warning")
        else:
            pac_service.start_pac_server()
            self.main_app.show_toast("✓ PAC Server aktif di http://127.0.0.1:18080/proxy.pac", level="success")
        self.refresh()
