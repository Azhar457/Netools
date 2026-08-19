"""
Tab 4: 9Router AI Gateway & OmniRoute Connection Matrix View (CustomTkinter).
"""

import threading
import tkinter as tk
import customtkinter as ctk
from netools.adapters import ninerouter as nr_adapt
from netools.adapters import omniroute as omni_adapt
from netools.config import NINEROUTER_URL, NINEROUTER_CLI_TOKEN, OMNIROUTE_URL
from netools.gui.theme import Fonts, COLOR_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_ACCENT_BLUE, COLOR_ACCENT_GREEN, COLOR_ACCENT_PURPLE, COLOR_ACCENT_YELLOW

class SettingsView(ctk.CTkScrollableFrame):
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
        self.entry_nr_tok = ctk.CTkEntry(f_nr, width=170, height=30, font=Fonts.mono(11), fg_color="#11111b", border_color="#45475a", show="•")
        self.entry_nr_tok.insert(0, NINEROUTER_CLI_TOKEN)
        self.entry_nr_tok.pack(side="left", padx=4)

        self.lbl_gw_stat = ctk.CTkLabel(f_nr, text="Checking...", font=Fonts.bold(11), text_color=COLOR_TEXT_SECONDARY)
        self.lbl_gw_stat.pack(side="left", padx=(12, 0))

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
        self.card_conns = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        self.card_conns.pack(fill="both", expand=True, padx=16, pady=6)

        ctk.CTkLabel(
            self.card_conns,
            text="📋 Registered Provider Connections & Proxy Pools",
            font=Fonts.subtitle(12),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", padx=14, pady=(12, 6))

        # Matrix Headers
        hdr_m = ctk.CTkFrame(self.card_conns, fg_color="#1e1e2e")
        hdr_m.pack(fill="x", padx=14, pady=(0, 4))

        cols = [("Provider / Name", 200), ("Type", 110), ("Assigned Pool", 160), ("Status", 110)]
        for h, w in cols:
            ctk.CTkLabel(
                hdr_m,
                text=h,
                font=Fonts.bold(10),
                text_color="#a6adc8",
                fg_color="#313244",
                corner_radius=4,
                width=w,
                anchor="center"
            ).pack(side="left", padx=2)

        self.conns_container = ctk.CTkFrame(self.card_conns, fg_color=COLOR_CARD)
        self.conns_container.pack(fill="both", expand=True, padx=14, pady=(0, 12))

    def refresh(self):
        def _bg():
            conns = nr_adapt.get_connections()
            healthy = isinstance(conns, list) and len(conns) > 0

            def _update():
                for widget in self.conns_container.winfo_children():
                    widget.destroy()

                if not healthy:
                    self.lbl_gw_stat.configure(text="⚪ 9Router Offline / Standalone", text_color="#6c7086")
                    ctk.CTkLabel(
                        self.conns_container,
                        text="No active connections found (Backend is either offline or in standalone mode).",
                        font=Fonts.italic_small(11),
                        text_color="#6c7086"
                    ).pack(pady=20)
                    return

                self.lbl_gw_stat.configure(text=f"🟢 {len(conns)} Providers Online", text_color=COLOR_ACCENT_GREEN)

                for c in conns:
                    row = ctk.CTkFrame(self.conns_container, fg_color="#181825", corner_radius=6)
                    row.pack(fill="x", pady=2)

                    name = c.get("name", "Unknown")
                    c_type = c.get("provider", "openai")
                    pool_id = c.get("proxy_pool_id") or "—"
                    status = "🟢 Linked" if pool_id != "—" else "⚪ Direct"

                    ctk.CTkLabel(row, text=name, width=200, anchor="w", font=Fonts.bold(11), text_color=COLOR_TEXT_PRIMARY).pack(side="left", padx=8)
                    ctk.CTkLabel(row, text=c_type, width=110, anchor="center", font=Fonts.regular(10), text_color=COLOR_ACCENT_BLUE).pack(side="left", padx=2)
                    ctk.CTkLabel(row, text=str(pool_id), width=160, anchor="center", font=Fonts.mono(10), text_color=COLOR_ACCENT_GREEN if pool_id != "—" else "#6c7086").pack(side="left", padx=2)
                    ctk.CTkLabel(row, text=status, width=110, anchor="center", font=Fonts.bold(10), text_color=COLOR_ACCENT_GREEN if status == "🟢 Linked" else "#bac2de").pack(side="left", padx=2)

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
            pools = list(set([data.get("pool_id") for data in insts.values() if data.get("pool_id")]))

            if not pools:
                try:
                    self.after(0, lambda: self.main_app.show_toast("Tidak ada active pool. Mulai Proxy Pool terlebih dahulu.", level="warning"))
                except Exception:
                    pass
                return

            nr_adapt.assign_round_robin(pools)
            try:
                self.after(0, self.refresh)
                self.after(0, lambda: self.main_app.show_toast(f"✓ Berhasil menghubungkan {len(pools)} pools ke 9Router!", level="success"))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def clear_pools(self):
        self.main_app.show_toast("Menghapus seluruh proxy dari 9Router...", level="warning")
        def _bg():
            nr_adapt.clear_all_proxies()
            try:
                self.after(0, self.refresh)
                self.after(0, lambda: self.main_app.show_toast("✓ Seluruh proxy 9Router dikembalikan ke koneksi Direct.", level="info"))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()
