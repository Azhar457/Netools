"""
Tab 4: 9Router AI Gateway & OmniRoute Connection Matrix View (CustomTkinter).
Uses native ttk.Treeview for high-performance, flicker-free, and leak-free table rendering.
"""

import threading
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from netools.adapters import ninerouter as nr_adapt
from netools.adapters import omniroute as omni_adapt
from netools.config import NINEROUTER_URL, NINEROUTER_CLI_TOKEN, OMNIROUTE_URL
from netools.gui.theme import Fonts, COLOR_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_ACCENT_BLUE, COLOR_ACCENT_GREEN, COLOR_ACCENT_PURPLE, COLOR_ACCENT_YELLOW

class SettingsView(ctk.CTkFrame):
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
            text="🔌 9Router & AI Multi-Provider Gateway Binding",
            font=Fonts.title(15),
            text_color=COLOR_ACCENT_PURPLE
        ).pack(side="left")

        ctk.CTkButton(
            hdr,
            text="🔄 Sync Gateway",
            font=Fonts.bold(11),
            fg_color="#313244",
            text_color=COLOR_TEXT_PRIMARY,
            hover_color="#45475a",
            height=30,
            command=self.refresh
        ).pack(side="right")

        # Endpoint Config Card
        card_cfg = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        card_cfg.pack(fill="x", padx=16, pady=4)

        f_nr = ctk.CTkFrame(card_cfg, fg_color=COLOR_CARD)
        f_nr.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(f_nr, text="9Router API:", font=Fonts.bold(11), text_color=COLOR_TEXT_PRIMARY).pack(side="left", padx=(0, 6))
        self.entry_nr_url = ctk.CTkEntry(f_nr, width=220, height=30, font=Fonts.mono(11), fg_color="#11111b", border_color="#45475a")
        self.entry_nr_url.insert(0, NINEROUTER_URL)
        self.entry_nr_url.pack(side="left", padx=4)

        ctk.CTkLabel(f_nr, text="CLI Token:", font=Fonts.bold(11), text_color=COLOR_TEXT_PRIMARY).pack(side="left", padx=(12, 6))
        self.entry_nr_tok = ctk.CTkEntry(f_nr, width=150, height=30, font=Fonts.mono(11), fg_color="#11111b", border_color="#45475a", show="•")
        self.entry_nr_tok.insert(0, NINEROUTER_CLI_TOKEN)
        self.entry_nr_tok.pack(side="left", padx=4)

        def _do_autodetect():
            from netools.config import auto_detect_9router_token
            tok = auto_detect_9router_token()
            if tok:
                self.entry_nr_tok.delete(0, "end")
                self.entry_nr_tok.insert(0, tok)
                self.main_app.show_toast("✓ 9Router CLI Token berhasil dideteksi otomatis!", level="success")
                self.refresh()
            else:
                self.main_app.show_toast("Tidak dapat menemukan kredensial ~/.9router pada sistem ini.", level="warning")

        ctk.CTkButton(
            f_nr,
            text="🔍 Auto-Detect",
            font=Fonts.bold(10),
            fg_color="#313244",
            text_color=COLOR_TEXT_PRIMARY,
            hover_color="#45475a",
            width=90,
            height=28,
            command=_do_autodetect
        ).pack(side="left", padx=4)

        self.lbl_gw_stat = ctk.CTkLabel(f_nr, text="Checking...", font=Fonts.bold(11), text_color=COLOR_TEXT_SECONDARY)
        self.lbl_gw_stat.pack(side="left", padx=(10, 0))

        # Action Buttons Row
        actions = ctk.CTkFrame(self, fg_color="#181825")
        actions.pack(fill="x", padx=16, pady=8)

        ctk.CTkButton(
            actions,
            text="🔗 Bind Active Pools to Connections",
            font=Fonts.bold(11),
            fg_color=COLOR_ACCENT_PURPLE,
            text_color="#11111b",
            hover_color="#f5c2e7",
            height=32,
            command=self.bind_pools
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            actions,
            text="✂️ Unlink / Clear All Proxies from 9Router",
            font=Fonts.bold(11),
            fg_color="#45475a",
            text_color="#f38ba8",
            hover_color="#585b70",
            height=32,
            command=self.clear_pools
        ).pack(side="left", padx=6)

        # Connection Matrix Card
        card_conns = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        card_conns.pack(fill="both", expand=True, padx=16, pady=6)

        ctk.CTkLabel(
            card_conns,
            text="📋 Registered Provider Connections & Proxy Pools",
            font=Fonts.subtitle(12),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", padx=14, pady=(12, 6))

        # Treeview Matrix Table (High Performance, No Widget Destruction Errors)
        tbl_frame = ctk.CTkFrame(card_conns, fg_color=COLOR_CARD)
        tbl_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        cols = ("name", "type", "pool", "status")
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", selectmode="browse")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#1e1e2e",
            foreground="#cdd6f4",
            fieldbackground="#1e1e2e",
            rowheight=28,
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
            ("name", "Provider Connection Name", 260, "center"),
            ("type", "Provider Type", 140, "center"),
            ("pool", "Assigned Proxy Pool", 200, "center"),
            ("status", "Routing Status", 140, "center"),
        ]

        for col_id, title, w, align in cols_config:
            self.tree.heading(col_id, text=title, anchor=align)
            self.tree.column(col_id, width=w, minwidth=100, anchor=align, stretch=True)

        vsb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=4)
        vsb.pack(side="right", fill="y", padx=(0, 8), pady=4)

    def refresh(self):
        try:
            url = self.entry_nr_url.get().strip() if hasattr(self, "entry_nr_url") else ""
            tok = self.entry_nr_tok.get().strip() if hasattr(self, "entry_nr_tok") else ""
        except Exception:
            url, tok = "", ""

        def _bg(u=url, t=tok):
            if u or t:
                nr_adapt.set_credentials(url=u if u else None, token=t if t else None)

            conns = nr_adapt.get_connections()
            is_healthy = nr_adapt.is_healthy()
            healthy = isinstance(conns, list) and (len(conns) > 0 or is_healthy)

            def _update():
                try:
                    for item in self.tree.get_children():
                        self.tree.delete(item)

                    if not healthy:
                        self.lbl_gw_stat.configure(text="⚪ 9Router Offline / Standalone", text_color="#6c7086")
                        return

                    self.lbl_gw_stat.configure(text=f"🟢 {len(conns)} Providers Online", text_color=COLOR_ACCENT_GREEN)

                    for c in conns:
                        name = c.get("name", "Unknown")
                        c_type = c.get("provider", "openai")
                        proxy_url = c.get("connectionProxyUrl") or c.get("providerSpecificData", {}).get("connectionProxyUrl") or "—"
                        status = "🟢 Linked" if (c.get("connectionProxyEnabled") or proxy_url != "—") else "⚪ Direct"

                        self.tree.insert("", "end", values=(name, c_type, str(proxy_url), status))
                except Exception:
                    pass

            try:
                self.after(0, _update)
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def bind_pools(self):
        self.main_app.show_toast("Menghubungkan Proxy Pools ke 9Router...", level="info")
        def _bg():
            from netools.state import load_state
            st = load_state()
            insts = st.get("instances", {})
            proxy_urls = [data.get("socks_url") for data in insts.values() if data.get("socks_url")]

            if not proxy_urls:
                try:
                    self.after(0, lambda: self.main_app.show_toast("Tidak ada active proxy. Mulai Proxy Pool terlebih dahulu.", level="warning"))
                except Exception:
                    pass
                return

            assigned = nr_adapt.assign_round_robin(proxy_urls)
            try:
                self.after(0, self.refresh)
                if hasattr(self.main_app, "dashboard_view"):
                    self.after(0, self.main_app.dashboard_view.refresh)
                if hasattr(self.main_app, "proxy_view"):
                    self.after(0, self.main_app.proxy_view._populate_sync)
                self.after(0, lambda: self.main_app.show_toast(f"✓ Berhasil menghubungkan {assigned} koneksi ke 9Router!", level="success"))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def clear_pools(self):
        self.main_app.show_toast("Menghapus seluruh proxy dari 9Router...", level="warning")
        def _bg():
            cleared = nr_adapt.clear_all_proxies()
            try:
                self.after(0, self.refresh)
                if hasattr(self.main_app, "dashboard_view"):
                    self.after(0, self.main_app.dashboard_view.refresh)
                if hasattr(self.main_app, "proxy_view"):
                    self.after(0, self.main_app.proxy_view._populate_sync)
                self.after(0, lambda: self.main_app.show_toast(f"✓ {cleared} proxy 9Router dikembalikan ke koneksi Direct.", level="info"))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()
