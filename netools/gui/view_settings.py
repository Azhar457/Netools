import threading
from tkinter import ttk
from typing import Any, Dict, List

import customtkinter as ctk

from netools.adapters import ninerouter as nr_adapt
from netools.adapters import omniroute as or_adapt
from netools.config import (
    NINEROUTER_URL,
    OMNIROUTE_TOKEN,
    OMNIROUTE_URL,
    auto_detect_9router_token,
    get_ninerouter_token,
)
from netools.gui.i18n import tr
from netools.gui.theme import Fonts, ThemeManager


class SettingsView(ctk.CTkFrame):
    """Sync Router View — Unified management for OmniRoute and 9Router AI Gateways."""

    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color=ThemeManager.bg(), corner_radius=0)
        self.main_app = main_app
        self.target_mode = "auto"  # "auto" | "omniroute" | "9router" | "dual"
        self._build_ui()
        self.refresh()

    def apply_theme(self):
        self.configure(fg_color=ThemeManager.bg())
        for attr in ("hdr", "actions"):
            if hasattr(self, attr):
                getattr(self, attr).configure(fg_color=ThemeManager.bg())

        if hasattr(self, "lbl_title"):
            self.lbl_title.configure(text_color=ThemeManager.secondary())
        if hasattr(self, "btn_refresh"):
            self.btn_refresh.configure(
                fg_color=ThemeManager.border(),
                text_color=ThemeManager.text(),
                hover_color=ThemeManager.surface_alt(),
            )
        if hasattr(self, "card_cfg"):
            self.card_cfg.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "card_conns"):
            self.card_conns.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "tbl_frame"):
            self.tbl_frame.configure(fg_color=ThemeManager.surface())
        if hasattr(self, "seg_target"):
            self.seg_target.configure(
                selected_color=ThemeManager.primary(),
                unselected_color=ThemeManager.surface_alt(),
                text_color=ThemeManager.text(),
            )

        for entry in ("entry_or_url", "entry_nr_url", "entry_nr_tok"):
            if hasattr(self, entry):
                getattr(self, entry).configure(
                    fg_color=ThemeManager.surface_alt(),
                    border_color=ThemeManager.border(),
                    text_color=ThemeManager.text(),
                )

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=ThemeManager.surface(),
            foreground=ThemeManager.text(),
            fieldbackground=ThemeManager.surface(),
        )
        style.configure(
            "Treeview.Heading",
            background=ThemeManager.surface_alt(),
            foreground=ThemeManager.text(),
        )
        style.map("Treeview", background=[("selected", ThemeManager.border())])

    def _build_ui(self):
        # Header
        self.hdr = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        self.hdr.pack(fill="x", padx=16, pady=(12, 10))

        self.lbl_title = ctk.CTkLabel(
            self.hdr,
            text=tr("🔌 Sync Router — Gateway Binding (OmniRoute & 9Router)"),
            font=Fonts.title(16),
            text_color=ThemeManager.secondary(),
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
            command=self.refresh,
        )
        self.btn_refresh.pack(side="right", padx=(6, 0))

        self.btn_extractor = ctk.CTkButton(
            self.hdr,
            text=tr("🍪 Buka Cookie Extractor"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.primary(),
            text_color="#FFFFFF",
            hover_color=ThemeManager.primary_hover(),
            width=180,
            height=34,
            command=self._open_extractor_tab,
        )
        self.btn_extractor.pack(side="right", padx=(0, 6))

        # Endpoint Config Card
        self.card_cfg = ctk.CTkFrame(
            self,
            fg_color=ThemeManager.surface(),
            corner_radius=8,
            border_width=1,
            border_color=ThemeManager.border(),
        )
        self.card_cfg.pack(fill="x", padx=16, pady=4)

        # Mode Selection Row
        f_mode = ctk.CTkFrame(self.card_cfg, fg_color=ThemeManager.surface())
        f_mode.pack(fill="x", padx=14, pady=(10, 6))

        ctk.CTkLabel(
            f_mode,
            text=tr("Target Router:"),
            font=Fonts.bold(12),
            text_color=ThemeManager.text(),
        ).pack(side="left", padx=(0, 8))

        self.seg_target = ctk.CTkSegmentedButton(
            f_mode,
            values=[
                tr("✨ Auto-Detect"),
                tr("🚀 OmniRoute"),
                tr("⚡ 9Router"),
                tr("🌐 Dual Sync"),
            ],
            font=Fonts.bold(11),
            selected_color=ThemeManager.primary(),
            unselected_color=ThemeManager.surface_alt(),
            text_color=ThemeManager.text(),
            command=self._on_target_changed,
        )
        self.seg_target.set(tr("✨ Auto-Detect"))
        self.seg_target.pack(side="left", padx=(0, 14))

        # Live Status Badges
        self.lbl_stat_or = ctk.CTkLabel(
            f_mode,
            text="🚀 OmniRoute: ⚪ Checking...",
            font=Fonts.bold(11),
            text_color=ThemeManager.text_muted(),
        )
        self.lbl_stat_or.pack(side="left", padx=(0, 10))

        self.lbl_stat_nr = ctk.CTkLabel(
            f_mode,
            text="⚡ 9Router: ⚪ Checking...",
            font=Fonts.bold(11),
            text_color=ThemeManager.text_muted(),
        )
        self.lbl_stat_nr.pack(side="left")

        # Endpoint Details Row
        self.f_endpoints = ctk.CTkFrame(self.card_cfg, fg_color=ThemeManager.surface())
        self.f_endpoints.pack(fill="x", padx=14, pady=(4, 10))

        # OmniRoute URL
        ctk.CTkLabel(
            self.f_endpoints,
            text=tr("OmniRoute (20128):"),
            font=Fonts.bold(11),
            text_color=ThemeManager.text(),
        ).pack(side="left", padx=(0, 4))
        self.entry_or_url = ctk.CTkEntry(
            self.f_endpoints,
            width=180,
            height=32,
            font=Fonts.mono(11),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
        )
        self.entry_or_url.insert(0, OMNIROUTE_URL)
        self.entry_or_url.pack(side="left", padx=(0, 10))

        # 9Router URL
        ctk.CTkLabel(
            self.f_endpoints,
            text=tr("9Router (20129):"),
            font=Fonts.bold(11),
            text_color=ThemeManager.text(),
        ).pack(side="left", padx=(0, 4))
        self.entry_nr_url = ctk.CTkEntry(
            self.f_endpoints,
            width=180,
            height=32,
            font=Fonts.mono(11),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
        )
        self.entry_nr_url.insert(0, NINEROUTER_URL)
        self.entry_nr_url.pack(side="left", padx=(0, 10))

        # 9Router Token
        ctk.CTkLabel(
            self.f_endpoints,
            text=tr("9R Token:"),
            font=Fonts.bold(11),
            text_color=ThemeManager.text(),
        ).pack(side="left", padx=(0, 4))
        self.entry_nr_tok = ctk.CTkEntry(
            self.f_endpoints,
            width=130,
            height=32,
            font=Fonts.mono(11),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            show="•",
        )
        self.entry_nr_tok.insert(0, get_ninerouter_token())
        self.entry_nr_tok.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            self.f_endpoints,
            text=tr("🔍 Deteksi Otomatis"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            width=130,
            height=32,
            command=self._do_autodetect,
        ).pack(side="left")

        # Action Buttons Row
        self.actions = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        self.actions.pack(fill="x", padx=16, pady=8)

        ctk.CTkButton(
            self.actions,
            text=tr("🔗 Hubungkan Proxy ke Router"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.secondary(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=36,
            command=self.bind_pools,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            self.actions,
            text=tr("✂️ Putuskan Seluruh Proxy dari Router"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.surface_alt(),
            text_color=ThemeManager.danger(),
            hover_color=ThemeManager.border(),
            height=36,
            command=self.clear_pools,
        ).pack(side="left", padx=6)

        # Connection Matrix Card
        self.card_conns = ctk.CTkFrame(
            self,
            fg_color=ThemeManager.surface(),
            corner_radius=8,
            border_width=1,
            border_color=ThemeManager.border(),
        )
        self.card_conns.pack(fill="both", expand=True, padx=16, pady=6)

        ctk.CTkLabel(
            self.card_conns,
            text=tr("📋 Koneksi Provider & Routing Proxy Terdaftar"),
            font=Fonts.subtitle(13),
            text_color=ThemeManager.text(),
        ).pack(anchor="w", padx=14, pady=(12, 6))

        # Treeview Matrix Table
        self.tbl_frame = ctk.CTkFrame(self.card_conns, fg_color=ThemeManager.surface())
        self.tbl_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        cols = ("gateway", "name", "type", "pool", "status")
        self.tree = ttk.Treeview(self.tbl_frame, columns=cols, show="headings", selectmode="browse")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=ThemeManager.surface(),
            foreground=ThemeManager.text(),
            fieldbackground=ThemeManager.surface(),
            rowheight=28,
            font=("sans-serif", 10),
        )
        style.configure(
            "Treeview.Heading",
            background=ThemeManager.surface_alt(),
            foreground=ThemeManager.text(),
            font=("sans-serif", 10, "bold"),
        )
        style.map("Treeview", background=[("selected", ThemeManager.border())])

        cols_config = [
            ("gateway", tr("Gateway"), 120, "center"),
            ("name", tr("Nama Koneksi"), 240, "center"),
            ("type", tr("Tipe Provider"), 140, "center"),
            ("pool", tr("Proxy Terhubung"), 200, "center"),
            ("status", tr("Status Routing"), 130, "center"),
        ]

        for col_id, title, w, align in cols_config:
            self.tree.heading(col_id, text=title, anchor=align)
            self.tree.column(col_id, width=w, minwidth=90, anchor=align, stretch=True)

        vsb = ttk.Scrollbar(self.tbl_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=4)
        vsb.pack(side="right", fill="y", padx=(0, 8), pady=4)

    def _open_extractor_tab(self):
        """Switch directly to the dedicated Cookie Extractor tab."""
        if hasattr(self.main_app, "tabview"):
            try:
                self.main_app.tabview.set(tr("🍪 Cookie Extractor"))
            except Exception:
                pass

    def _on_target_changed(self, value: str):
        val_str = str(value).lower()
        if "omni" in val_str:
            self.target_mode = "omniroute"
        elif "9router" in val_str:
            self.target_mode = "9router"
        elif "dual" in val_str or "keduanya" in val_str:
            self.target_mode = "dual"
        else:
            self.target_mode = "auto"
        self.refresh()

    def _do_autodetect(self):
        """Auto-detect credentials for both OmniRoute and 9Router."""
        nr_tok = auto_detect_9router_token()
        if nr_tok:
            self.entry_nr_tok.delete(0, "end")
            self.entry_nr_tok.insert(0, nr_tok)

        found_msgs = []
        if or_adapt.is_healthy():
            found_msgs.append("OmniRoute (Port 20128)")
        if nr_adapt.is_healthy():
            found_msgs.append("9Router (Port 20129)")

        if found_msgs:
            self.main_app.show_toast(
                tr("✓ Router aktif terdeteksi: ") + ", ".join(found_msgs),
                level="success",
            )
        else:
            self.main_app.show_toast(
                tr("Memeriksa localhost... Pastikan omniroute serve atau 9Router sedang berjalan."),
                level="info",
            )
        self.refresh()

    def refresh(self):
        """Refresh connections from OmniRoute, 9Router, or both."""
        try:
            or_url = self.entry_or_url.get().strip() if hasattr(self, "entry_or_url") else ""
            nr_url = self.entry_nr_url.get().strip() if hasattr(self, "entry_nr_url") else ""
            nr_tok = self.entry_nr_tok.get().strip() if hasattr(self, "entry_nr_tok") else ""
        except Exception:
            or_url, nr_url, nr_tok = "", "", ""

        def _bg():
            if or_url:
                or_adapt.set_credentials(url=or_url)
            if nr_url or nr_tok:
                nr_adapt.set_credentials(url=nr_url if nr_url else None, token=nr_tok if nr_tok else None)

            or_ok = or_adapt.is_healthy()
            or_conns = or_adapt.get_connections() if or_ok else []

            nr_ok = nr_adapt.is_healthy()
            nr_conns = nr_adapt.get_connections() if nr_ok else []

            def _update():
                try:
                    # Update Badges
                    if or_ok:
                        self.lbl_stat_or.configure(
                            text=f"🚀 OmniRoute: 🟢 Online ({len(or_conns)})",
                            text_color=ThemeManager.success(),
                        )
                    else:
                        self.lbl_stat_or.configure(
                            text="🚀 OmniRoute: ⚪ Offline",
                            text_color=ThemeManager.text_muted(),
                        )

                    if nr_ok:
                        self.lbl_stat_nr.configure(
                            text=f"⚡ 9Router: 🟢 Online ({len(nr_conns)})",
                            text_color=ThemeManager.success(),
                        )
                    else:
                        self.lbl_stat_nr.configure(
                            text="⚡ 9Router: ⚪ Offline",
                            text_color=ThemeManager.text_muted(),
                        )

                    # Clear Tree
                    for item in self.tree.get_children():
                        self.tree.delete(item)

                    # Decide which connections to display
                    items_to_show = []

                    show_or = self.target_mode in ("omniroute", "dual") or (
                        self.target_mode == "auto" and (or_ok or not nr_ok)
                    )
                    show_nr = self.target_mode in ("9router", "dual") or (
                        self.target_mode == "auto" and (nr_ok and not or_ok)
                    )

                    if self.target_mode == "auto" and or_ok and nr_ok:
                        show_or = True
                        show_nr = True

                    if show_or and or_conns:
                        for c in or_conns:
                            name = c.get("name", "Unknown")
                            c_type = c.get("provider", "web")
                            proxy_url = c.get("connectionProxyUrl") or "—"
                            status = "🟢 Linked" if (c.get("connectionProxyEnabled") or proxy_url != "—") else "⚪ Direct"
                            items_to_show.append(("🚀 OmniRoute", name, c_type, str(proxy_url), status))

                    if show_nr and nr_conns:
                        for c in nr_conns:
                            name = c.get("name", "Unknown")
                            c_type = c.get("provider", "openai")
                            proxy_url = (
                                c.get("connectionProxyUrl")
                                or c.get("providerSpecificData", {}).get("connectionProxyUrl")
                                or "—"
                            )
                            status = "🟢 Linked" if (c.get("connectionProxyEnabled") or proxy_url != "—") else "⚪ Direct"
                            items_to_show.append(("⚡ 9Router", name, c_type, str(proxy_url), status))

                    for row in items_to_show:
                        self.tree.insert("", "end", values=row)

                except Exception:
                    pass

            try:
                self.after(0, _update)
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def bind_pools(self):
        """Bind active sing-box proxies to selected router(s)."""
        self.main_app.show_toast(tr("Menghubungkan Proxy Pools ke Router..."), level="info")

        def _bg():
            from netools.state import load_state

            st = load_state()
            insts = st.get("instances", {})
            proxy_urls = [data.get("socks_url") for data in insts.values() if data.get("socks_url")]

            if not proxy_urls:
                try:
                    self.after(
                        0,
                        lambda: self.main_app.show_toast(
                            tr("Tidak ada active proxy. Mulai Proxy Pool terlebih dahulu."),
                            level="warning",
                        ),
                    )
                except Exception:
                    pass
                return

            assigned_total = 0
            targets_hit = []

            # OmniRoute
            if self.target_mode in ("omniroute", "dual", "auto"):
                if or_adapt.is_healthy():
                    cnt = or_adapt.assign_round_robin(proxy_urls)
                    if cnt > 0:
                        assigned_total += cnt
                        targets_hit.append(f"OmniRoute ({cnt})")

            # 9Router
            if self.target_mode in ("9router", "dual", "auto"):
                if nr_adapt.is_healthy():
                    cnt = nr_adapt.assign_round_robin(proxy_urls)
                    if cnt > 0:
                        assigned_total += cnt
                        targets_hit.append(f"9Router ({cnt})")

            try:
                self.after(0, self.refresh)
                if hasattr(self.main_app, "dashboard_view"):
                    self.after(0, self.main_app.dashboard_view.refresh)
                if hasattr(self.main_app, "proxy_view"):
                    self.after(0, self.main_app.proxy_view._populate_sync)

                if assigned_total > 0:
                    summary = ", ".join(targets_hit)
                    self.after(
                        0,
                        lambda: self.main_app.show_toast(
                            tr("✓ Berhasil menghubungkan proxy ke ") + summary,
                            level="success",
                        ),
                    )
                else:
                    self.after(
                        0,
                        lambda: self.main_app.show_toast(
                            tr("Tidak ada router aktif atau koneksi yang tersedia untuk di-bind."),
                            level="warning",
                        ),
                    )
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def clear_pools(self):
        """Unlink proxies from selected router(s)."""
        self.main_app.show_toast(tr("Menghapus proxy dari Router..."), level="warning")

        def _bg():
            cleared_total = 0
            targets_hit = []

            if self.target_mode in ("omniroute", "dual", "auto"):
                if or_adapt.is_healthy():
                    cnt = or_adapt.clear_all_proxies()
                    cleared_total += cnt
                    if cnt > 0:
                        targets_hit.append(f"OmniRoute ({cnt})")

            if self.target_mode in ("9router", "dual", "auto"):
                if nr_adapt.is_healthy():
                    cnt = nr_adapt.clear_all_proxies()
                    cleared_total += cnt
                    if cnt > 0:
                        targets_hit.append(f"9Router ({cnt})")

            try:
                self.after(0, self.refresh)
                if hasattr(self.main_app, "dashboard_view"):
                    self.after(0, self.main_app.dashboard_view.refresh)
                if hasattr(self.main_app, "proxy_view"):
                    self.after(0, self.main_app.proxy_view._populate_sync)

                summary = ", ".join(targets_hit) if targets_hit else "semua"
                self.after(
                    0,
                    lambda: self.main_app.show_toast(
                        tr("✓ Proxy dinonaktifkan dari ") + summary,
                        level="info",
                    ),
                )
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()
