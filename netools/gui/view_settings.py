import threading
from tkinter import ttk

import customtkinter as ctk

from netools.adapters import ninerouter as nr_adapt
from netools.config import NINEROUTER_URL, get_ninerouter_token
from netools.gui.i18n import tr
from netools.gui.theme import (
    Fonts,
    ThemeManager,
)


class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color=ThemeManager.bg(), corner_radius=0)
        self.main_app = main_app
        self._build_ui()
        self.refresh()

    def apply_theme(self):
        self.configure(fg_color=ThemeManager.bg())
        if hasattr(self, "hdr"): self.hdr.configure(fg_color=ThemeManager.bg())
        if hasattr(self, "lbl_title"): self.lbl_title.configure(text_color=ThemeManager.secondary())
        if hasattr(self, "btn_refresh"): self.btn_refresh.configure(fg_color=ThemeManager.border(), text_color=ThemeManager.text(), hover_color=ThemeManager.surface_alt())
        if hasattr(self, "card_cfg"): self.card_cfg.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "f_nr"): self.f_nr.configure(fg_color=ThemeManager.surface())
        if hasattr(self, "entry_nr_url"): self.entry_nr_url.configure(fg_color=ThemeManager.surface_alt(), border_color=ThemeManager.border(), text_color=ThemeManager.text())
        if hasattr(self, "entry_nr_tok"): self.entry_nr_tok.configure(fg_color=ThemeManager.surface_alt(), border_color=ThemeManager.border(), text_color=ThemeManager.text())
        if hasattr(self, "card_conns"): self.card_conns.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "tbl_frame"): self.tbl_frame.configure(fg_color=ThemeManager.surface())
        
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=ThemeManager.surface(), foreground=ThemeManager.text(), fieldbackground=ThemeManager.surface())
        style.configure("Treeview.Heading", background=ThemeManager.surface_alt(), foreground=ThemeManager.text())
        style.map("Treeview", background=[("selected", ThemeManager.border())])

    def _build_ui(self):
        # Header
        self.hdr = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        self.hdr.pack(fill="x", padx=16, pady=(12, 10))

        self.lbl_title = ctk.CTkLabel(
            self.hdr,
            text=tr("🔌 9Router & AI Multi-Provider Gateway Binding"),
            font=Fonts.title(16),
            text_color=ThemeManager.secondary()
        )
        self.lbl_title.pack(side="left")

        self.btn_refresh = ctk.CTkButton(
            self.hdr,
            text=tr("🔄 Refresh"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            width=100,
            height=34,
            command=self.refresh
        )
        self.btn_refresh.pack(side="right", padx=(6, 0))

        self.btn_extractor = ctk.CTkButton(
            self.hdr,
            text=tr("🍪 Buka Cookie Extractor"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.primary(),
            text_color="#FFFFFF",
            hover_color=ThemeManager.primary_hover(),
            width=175,
            height=34,
            command=self._open_extractor_modal
        )
        self.btn_extractor.pack(side="right", padx=(0, 6))




        # Endpoint Config Card
        self.card_cfg = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.card_cfg.pack(fill="x", padx=16, pady=4)

        self.f_nr = ctk.CTkFrame(self.card_cfg, fg_color=ThemeManager.surface())
        self.f_nr.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(self.f_nr, text=tr("9Router API:"), font=Fonts.bold(12), text_color=ThemeManager.text()).pack(side="left", padx=(0, 6))
        self.entry_nr_url = ctk.CTkEntry(self.f_nr, width=240, height=34, font=Fonts.mono(12), fg_color=ThemeManager.surface_alt(), border_color=ThemeManager.border(), text_color=ThemeManager.text())
        self.entry_nr_url.insert(0, NINEROUTER_URL)
        self.entry_nr_url.pack(side="left", padx=4)

        ctk.CTkLabel(self.f_nr, text=tr("CLI Token:"), font=Fonts.bold(12), text_color=ThemeManager.text()).pack(side="left", padx=(12, 6))
        self.entry_nr_tok = ctk.CTkEntry(self.f_nr, width=170, height=34, font=Fonts.mono(12), fg_color=ThemeManager.surface_alt(), border_color=ThemeManager.border(), text_color=ThemeManager.text(), show="•")
        self.entry_nr_tok.insert(0, get_ninerouter_token())
        self.entry_nr_tok.pack(side="left", padx=4)

        def _do_autodetect():
            from netools.config import auto_detect_9router_token
            tok = auto_detect_9router_token()
            if tok:
                self.entry_nr_tok.delete(0, "end")
                self.entry_nr_tok.insert(0, tok)
                self.main_app.show_toast(tr("✓ 9Router CLI Token berhasil dideteksi otomatis!"), level="success")
                self.refresh()
            else:
                self.main_app.show_toast(tr("Tidak dapat menemukan kredensial ~/.9router pada sistem ini."), level="warning")

        ctk.CTkButton(
            self.f_nr,
            text=tr("🔍 Auto-Detect"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            width=110,
            height=34,
            command=_do_autodetect
        ).pack(side="left", padx=6)

        self.lbl_gw_stat = ctk.CTkLabel(self.f_nr, text="Checking...", font=Fonts.bold(12), text_color=ThemeManager.text_muted())
        self.lbl_gw_stat.pack(side="left", padx=(10, 0))

        # Action Buttons Row
        self.actions = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        self.actions.pack(fill="x", padx=16, pady=8)

        ctk.CTkButton(
            self.actions,
            text=tr("🔗 Bind Active Pools to Connections"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.secondary(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=36,
            command=self.bind_pools
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            self.actions,
            text=tr("✂️ Unlink / Clear All Proxies from 9Router"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.surface_alt(),
            text_color=ThemeManager.danger(),
            hover_color=ThemeManager.border(),
            height=36,
            command=self.clear_pools
        ).pack(side="left", padx=6)

        # Connection Matrix Card
        self.card_conns = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.card_conns.pack(fill="both", expand=True, padx=16, pady=6)

        ctk.CTkLabel(
            self.card_conns,
            text=tr("📋 Registered Provider Connections & Proxy Pools"),
            font=Fonts.subtitle(13),
            text_color=ThemeManager.text()
        ).pack(anchor="w", padx=14, pady=(12, 6))

        # Treeview Matrix Table (High Performance, No Widget Destruction Errors)
        self.tbl_frame = ctk.CTkFrame(self.card_conns, fg_color=ThemeManager.surface())
        self.tbl_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        cols = ("name", "type", "pool", "status")
        self.tree = ttk.Treeview(self.tbl_frame, columns=cols, show="headings", selectmode="browse")


        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=ThemeManager.surface(),
            foreground=ThemeManager.text(),
            fieldbackground=ThemeManager.surface(),
            rowheight=28,
            font=("sans-serif", 10)
        )
        style.configure(
            "Treeview.Heading",
            background=ThemeManager.surface_alt(),
            foreground=ThemeManager.text(),
            font=("sans-serif", 10, "bold")
        )
        style.map("Treeview", background=[("selected", ThemeManager.border())])


        cols_config = [
            ("name", tr("Provider Connection Name"), 260, "center"),
            ("type", tr("Provider Type"), 140, "center"),
            ("pool", tr("Assigned Proxy Pool"), 200, "center"),
            ("status", tr("Routing Status"), 140, "center"),
        ]

        for col_id, title, w, align in cols_config:
            self.tree.heading(col_id, text=title, anchor=align)
            self.tree.column(col_id, width=w, minwidth=100, anchor=align, stretch=True)

        vsb = ttk.Scrollbar(self.tbl_frame, orient="vertical", command=self.tree.yview)
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
                        self.lbl_gw_stat.configure(text="⚪ 9Router Offline / Standalone", text_color=ThemeManager.text_muted())
                        return

                    self.lbl_gw_stat.configure(text=f"🟢 {len(conns)} Providers Online", text_color=ThemeManager.success())

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
        self.main_app.show_toast(tr("Menghubungkan Proxy Pools ke 9Router..."), level="info")
        def _bg():
            from netools.state import load_state
            st = load_state()
            insts = st.get("instances", {})
            proxy_urls = [data.get("socks_url") for data in insts.values() if data.get("socks_url")]

            if not proxy_urls:
                try:
                    self.after(0, lambda: self.main_app.show_toast(tr("Tidak ada active proxy. Mulai Proxy Pool terlebih dahulu."), level="warning"))
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
                self.after(0, lambda: self.main_app.show_toast(tr("✓ Berhasil menghubungkan {assigned} koneksi ke 9Router!").replace("{assigned}", str(assigned)), level="success"))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def clear_pools(self):
        self.main_app.show_toast(tr("Menghapus seluruh proxy dari 9Router..."), level="warning")
        def _bg():
            cleared = nr_adapt.clear_all_proxies()
            try:
                self.after(0, self.refresh)
                if hasattr(self.main_app, "dashboard_view"):
                    self.after(0, self.main_app.dashboard_view.refresh)
                if hasattr(self.main_app, "proxy_view"):
                    self.after(0, self.main_app.proxy_view._populate_sync)
                self.after(0, lambda: self.main_app.show_toast(tr("✓ {cleared} proxy 9Router dikembalikan ke koneksi Direct.").replace("{cleared}", str(cleared)), level="info"))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def _open_extractor_modal(self):
        # Switch directly to the dedicated Cookie Extractor tab (single source of truth)
        if hasattr(self.main_app, "tabview"):
            try:
                self.main_app.tabview.set(tr("🍪 Cookie Extractor"))
                return
            except Exception:
                pass


