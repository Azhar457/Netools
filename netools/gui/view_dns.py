"""
Tab 2: DNS Jumper, 3-Tier Switcher & Fast Benchmarker View (CustomTkinter).
"""

import threading

import customtkinter as ctk

from netools.adapters import platform_dns as sys_dns
from netools.gui.i18n import canary_info_paragraphs, get_locale, tr
from netools.gui.scrollable_dropdown import CTkScrollableDropdown
from netools.gui.theme import (
    Fonts,
    ThemeManager,
)
from netools.gui.view_benchmark_modal import GRCBenchmarkModal
from netools.gui.view_dpi_inspector import DPIInspectorModal
from netools.libs import dns_db as db
from netools.services import canary_service


class DNSView(ctk.CTkFrame):
    def __init__(self, parent, main_app=None):
        self._canary_items: list = []
        self._canary_selected: str = ""
        super().__init__(parent, fg_color=ThemeManager.bg(), corner_radius=0)
        self.main_app = main_app if main_app is not None else parent
        self.providers = db.load_providers()
        self.interfaces = sys_dns.get_network_interfaces() or []
        self.active_interface = self.interfaces[0]["device"] if self.interfaces else "default"
        self.benchmark_modal = None
        self.dpi_modal = None
        self.verify_modal = None
        # Tracks what populates the slots: "preset" | "external" | "system"
        self.applied_source_kind = "preset"
        self._build_ui()
        self.apply_theme()

    def apply_theme(self):
        self.configure(fg_color=ThemeManager.bg())
        for name in (
            "hdr",
            "lbl_title",
            "card_iface",
            "f1",
            "card_preset",
            "f2",
            "slots_card",
            "s1",
            "s2",
            "s3",
            "opt_card",
            "opts",
            "actions",
        ):
            w = getattr(self, name, None)
            if w is not None:
                try:
                    w.configure(fg_color=ThemeManager.surface())
                except Exception:
                    pass
        for e in (self.dns1_entry, self.dns2_entry, self.dns3_entry):
            try:
                e.configure(
                    fg_color=ThemeManager.surface_alt(),
                    border_color=ThemeManager.border(),
                    text_color=ThemeManager.text(),
                )
            except Exception:
                pass

    def _build_ui(self):
        hdr = ctk.CTkFrame(self, fg_color=ThemeManager.surface_alt(), height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        self.hdr = hdr
        self.lbl_title = ctk.CTkLabel(
            hdr,
            text=tr("⚡ Smart DNS Switcher & Latency Profiler"),
            font=Fonts.title(15),
            text_color=ThemeManager.warning(),
        )
        self.lbl_title.pack(side="left", padx=20, pady=8)

        card_iface = ctk.CTkFrame(
            self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border()
        )
        card_iface.pack(fill="x", padx=16, pady=4)
        self.card_iface = card_iface

        self.f1 = ctk.CTkFrame(card_iface, fg_color=ThemeManager.surface())
        self.f1.pack(fill="x", padx=14, pady=8)

        ctk.CTkLabel(self.f1, text=tr("Network Interface:"), font=Fonts.bold(11), text_color=ThemeManager.text()).pack(
            side="left", padx=(0, 4)
        )

        self.iface_var = ctk.StringVar(value="Default")
        labels = [i["label"] for i in self.interfaces] or ["Default"]
        self.iface_cb = ctk.CTkComboBox(
            self.f1,
            variable=self.iface_var,
            values=labels,
            state="readonly",
            width=200,
            font=Fonts.regular(11),
            command=self.on_interface_change,
        )
        self.iface_cb.pack(side="left", padx=4)

        self.btn_refresh = ctk.CTkButton(
            self.f1,
            text=tr("🔄 Refresh Adapters"),
            width=110,
            height=30,
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            command=self.refresh_adapters,
        ).pack(side="left", padx=4)

        # Preset Provider Selector Card
        self.card_preset = ctk.CTkFrame(
            self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border()
        )
        self.card_preset.pack(fill="x", padx=16, pady=4)

        self.f2 = ctk.CTkFrame(self.card_preset, fg_color=ThemeManager.surface())
        self.f2.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(self.f2, text=tr("Category:"), font=Fonts.bold(11), text_color=ThemeManager.primary()).pack(
            side="left", padx=(0, 4)
        )

        self.category_var = ctk.StringVar(value="📁 All Categories")
        self.category_cb = ctk.CTkComboBox(
            self.f2,
            variable=self.category_var,
            values=[
                "📁 All Categories",
                "🛡️ Security & Privacy",
                "⚡ Gaming / Fast",
                "🚫 Ad-Blocking",
                "👨‍👩‍👧 Family Safe",
                "🌏 Asia-Pacific",
                "🌐 Global Anycast",
            ],
            state="readonly",
            font=Fonts.regular(11),
            width=150,
            dropdown_font=Fonts.regular(11),
            command=self.on_category_filter_change,
        )
        self.category_cb.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(self.f2, text=tr("Preset:"), font=Fonts.bold(11), text_color=ThemeManager.text()).pack(
            side="left", padx=(0, 4)
        )

        self.preset_var = ctk.StringVar(value="⚙️ Custom DNS Servers")
        preset_labels = [f"{p['country']} {p['name']}" for p in self.providers.values()]
        preset_labels.insert(0, "⚙️ Custom DNS Servers")
        self.preset_cb = ctk.CTkComboBox(
            self.f2,
            variable=self.preset_var,
            values=preset_labels,
            state="readonly",
            font=Fonts.regular(11),
            width=220,
            dropdown_font=Fonts.regular(11),
            command=self.on_preset_change,
        )
        self.preset_cb.pack(side="left", fill="x", expand=True, padx=4)

        # Attach scrollable & searchable dropdown popup (prevents screen overflow)
        self.preset_dropdown = CTkScrollableDropdown(
            attach_widget=self.preset_cb,
            values=preset_labels,
            command=self.on_preset_change,
            variable=self.preset_var,
            max_height=280,
            searchable=True,
            placeholder_text=f"🔍 Search {len(preset_labels)} DNS presets...",
        )

        ctk.CTkLabel(self.f2, text=tr("Protocol / IP:"), font=Fonts.bold(11), text_color=ThemeManager.text()).pack(
            side="left", padx=(8, 4)
        )

        self.ip_family_var = ctk.StringVar(value="IPv4 (Standard)")
        self.ip_family_cb = ctk.CTkComboBox(
            self.f2,
            variable=self.ip_family_var,
            values=["IPv4 (Standard)", "IPv6 (Next-Gen)", "DoH (HTTPS)", "DoT (TLS Port 853)"],
            state="readonly",
            font=Fonts.regular(11),
            width=150,
            dropdown_font=Fonts.regular(11),
            command=self.on_ip_family_change,
        )
        self.ip_family_cb.pack(side="left", padx=4)

        # 3-Slots Card
        self.slots_card = ctk.CTkFrame(
            self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border()
        )
        self.slots_card.pack(fill="x", padx=16, pady=6)

        self.s1 = ctk.CTkFrame(self.slots_card, fg_color=ThemeManager.surface())
        self.s1.pack(fill="x", pady=6, padx=14)
        ctk.CTkLabel(
            self.s1,
            text=tr("DNS 1 (Primary)   :"),
            font=Fonts.bold(12),
            width=140,
            anchor="w",
            text_color=ThemeManager.text(),
        ).pack(side="left")
        self.dns1_entry = ctk.CTkEntry(
            self.s1,
            width=220,
            height=34,
            font=Fonts.mono(12),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
        )
        self.dns1_entry.pack(side="left", padx=4)

        self.btn_ping1 = ctk.CTkButton(
            self.s1,
            text=tr("Ping"),
            width=64,
            height=30,
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            command=lambda: self.ping_slot(1),
        )
        self.btn_ping1.pack(side="left", padx=4)
        self.lbl_ping1 = ctk.CTkLabel(self.s1, text="", font=Fonts.bold(12), text_color=ThemeManager.success())
        self.lbl_ping1.pack(side="left", padx=6)

        self.s2 = ctk.CTkFrame(self.slots_card, fg_color=ThemeManager.surface())
        self.s2.pack(fill="x", pady=6, padx=14)
        ctk.CTkLabel(
            self.s2,
            text=tr("DNS 2 (Secondary) :"),
            font=Fonts.bold(12),
            width=140,
            anchor="w",
            text_color=ThemeManager.text(),
        ).pack(side="left")
        self.dns2_entry = ctk.CTkEntry(
            self.s2,
            width=220,
            height=34,
            font=Fonts.mono(12),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
        )
        self.dns2_entry.pack(side="left", padx=4)

        self.btn_ping2 = ctk.CTkButton(
            self.s2,
            text=tr("Ping"),
            width=64,
            height=30,
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            command=lambda: self.ping_slot(2),
        )
        self.btn_ping2.pack(side="left", padx=4)
        self.lbl_ping2 = ctk.CTkLabel(self.s2, text="", font=Fonts.bold(12), text_color=ThemeManager.success())
        self.lbl_ping2.pack(side="left", padx=6)

        self.s3 = ctk.CTkFrame(self.slots_card, fg_color=ThemeManager.surface())
        self.s3.pack(fill="x", pady=6, padx=14)
        ctk.CTkLabel(
            self.s3,
            text=tr("DNS 3 (Tertiary)  :"),
            font=Fonts.bold(12),
            width=140,
            anchor="w",
            text_color=ThemeManager.text(),
        ).pack(side="left")
        self.dns3_entry = ctk.CTkEntry(
            self.s3,
            width=220,
            height=34,
            font=Fonts.mono(12),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
        )
        self.dns3_entry.pack(side="left", padx=4)

        self.btn_ping3 = ctk.CTkButton(
            self.s3,
            text=tr("Ping"),
            width=64,
            height=30,
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            command=lambda: self.ping_slot(3),
        )
        self.btn_ping3.pack(side="left", padx=4)
        self.lbl_ping3 = ctk.CTkLabel(self.s3, text="", font=Fonts.bold(12), text_color=ThemeManager.success())
        self.lbl_ping3.pack(side="left", padx=6)

        # Options Row
        self.opt_card = ctk.CTkFrame(
            self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border()
        )
        self.opt_card.pack(fill="x", padx=16, pady=4)

        self.opts = ctk.CTkFrame(self.opt_card, fg_color=ThemeManager.surface())
        self.opts.pack(fill="x", padx=14, pady=8)

        self.dot_var = ctk.BooleanVar(value=False)
        self.dot_chk = ctk.CTkCheckBox(
            self.opts,
            text=tr("Enable DNS-over-TLS (DoT / Opportunistic)"),
            variable=self.dot_var,
            font=Fonts.regular(12),
            text_color=ThemeManager.text(),
            fg_color=ThemeManager.primary(),
        )
        self.dot_chk.pack(side="left", padx=4)

        self.persist_var = ctk.BooleanVar(value=True)
        self.persist_chk = ctk.CTkCheckBox(
            self.opts,
            text=tr("Persist across Network Reconnects"),
            variable=self.persist_var,
            font=Fonts.regular(12),
            text_color=ThemeManager.text(),
            fg_color=ThemeManager.primary(),
        )
        self.persist_chk.pack(side="left", padx=16)

        # Action Buttons Row
        self.actions = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        self.actions.pack(fill="x", padx=16, pady=10)

        ctk.CTkButton(
            self.actions,
            text=tr("⚡ Apply DNS"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.success(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=36,
            command=self.apply_dns,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            self.actions,
            text=tr("♻️ Flush DNS"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            height=36,
            command=self.flush_dns,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            self.actions,
            text=tr("↩️ Restore DHCP"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.surface_alt(),
            text_color=ThemeManager.danger(),
            hover_color=ThemeManager.border(),
            height=36,
            command=self.restore_dhcp,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            self.actions,
            text=tr("🔍 Verify DNS & DoH"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.primary(),
            hover_color=ThemeManager.surface_alt(),
            height=36,
            command=self.verify_dns_status,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            self.actions,
            text=tr("🔬 Inspect Blocked Domain / DPI"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.warning(),
            hover_color=ThemeManager.surface_alt(),
            height=36,
            command=self.open_dpi_inspector,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            self.actions,
            text=tr("🏆 Fastest DNS Benchmark (GRC Engine)"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.warning(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=36,
            command=self.open_benchmark,
        ).pack(side="right", padx=(6, 0))

        # ---- Canary Domain Interception Check Card ----
        self.canary_card = ctk.CTkFrame(
            self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border()
        )
        self.canary_card.pack(fill="x", padx=16, pady=(8, 4))
        self.canary_hdr = ctk.CTkFrame(self.canary_card, fg_color=ThemeManager.surface(), height=30)
        self.canary_hdr.pack(fill="x", padx=12, pady=(10, 2))
        self.canary_lbl = ctk.CTkLabel(
            self.canary_hdr,
            text=tr("🛡️ DNS Canary (Interception Check)"),
            font=Fonts.subtitle(13),
            text_color=ThemeManager.text(),
        )
        self.canary_lbl.pack(side="left")
        self.canary_badge = ctk.CTkLabel(
            self.canary_hdr, text=tr("● Not Checked"), font=Fonts.badge(10), text_color=ThemeManager.text_muted()
        )
        self.canary_badge.pack(side="right", padx=4)
        self.canary_body = ctk.CTkFrame(self.canary_card, fg_color=ThemeManager.surface())
        self.canary_body.pack(fill="x", padx=12, pady=(0, 10))
        self.canary_stat = ctk.CTkLabel(
            self.canary_body,
            text=tr("Click 'Check Now' to test Mozilla + Apple + Custom canary domains (system + custom resolver)."),
            font=Fonts.regular(11),
            text_color=ThemeManager.text_muted(),
            justify="left",
        )
        self.canary_stat.pack(anchor="w", pady=2)
        self.canary_btn = ctk.CTkButton(
            self.canary_body,
            text=tr("🔄 Check Now"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.accent(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=30,
            command=self._run_canary_check,
        )
        self.canary_btn.pack(anchor="e", pady=(2, 0))

        self.canary_info_btn = ctk.CTkButton(
            self.canary_body,
            text=tr("ℹ️ What is this?"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            height=30,
            command=self._open_canary_info,
        )
        self.canary_info_btn.pack(anchor="e", pady=(4, 0))

        # Auto-load active system DNS on startup
        self.load_active_interface_dns()

    def _run_canary_check(self):
        self.canary_badge.configure(text="● Checking...", text_color=ThemeManager.warning())
        self.canary_stat.configure(
            text="Running canary sweep... (please wait ~2-5s)", text_color=ThemeManager.text_muted()
        )

        def _on_done(result: canary_service.CanaryRunResult):
            def _update():
                verdict = result.verdict if result else "indeterminate"
                if verdict == canary_service.VERDICT_CLEAN:
                    badge_text, badge_color = "● Clean (No Intercept)", ThemeManager.success()
                    stat_text = "No interception detected. DoH / Apple Relay safe to use."
                elif verdict == canary_service.VERDICT_INTERCEPTED:
                    badge_text, badge_color = "● INTERCEPTED!", ThemeManager.danger()
                    stat_text = f"Interception detected on: {', '.join(result.intercepted_domains or ['unknown'])}. DoH may be blocked."
                elif verdict == canary_service.VERDICT_INDETERMINATE:
                    badge_text, badge_color = "● Offline / Unknown", ThemeManager.warning()
                    stat_text = "Pre-check failed (offline / broken resolver). Cannot determine interception."
                else:
                    badge_text, badge_color = "● Partial", ThemeManager.warning()
                    stat_text = f"Mixed results: clean={len(result.clean_domains)}, intercepted={len(result.intercepted_domains)}."
                try:
                    self.canary_badge.configure(text=badge_text, text_color=badge_color)
                    self.canary_stat.configure(text=stat_text, text_color=ThemeManager.text())
                except Exception:
                    pass
                # Side-effects: tray icon + optional auto-DoH toggle.
                try:
                    if hasattr(self.main_app, "_handle_canary_result"):
                        self.main_app._handle_canary_result(result)
                except Exception:
                    pass

            try:
                self.after(0, _update)
            except Exception:
                pass

        canary_service.run_canary_sweep_async(on_done=_on_done, timeout=2.0)

    def _open_canary_info(self):
        """User-friendly explainer + custom canary (domain/TLD) manager."""
        loc = get_locale()
        win = ctk.CTkToplevel(self)
        win.title(tr("DNS Canary Domains — How It Works"))
        win.geometry("640x620")
        from netools.gui.wm import mark_dialog

        mark_dialog(win, self.winfo_toplevel())
        win.after(120, win.lift)

        scroll = ctk.CTkScrollableFrame(win, fg_color=ThemeManager.surface())
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        for para in canary_info_paragraphs(loc):
            is_heading = (
                not para[:1].isdigit()
                and para == para.rstrip()
                and (para.startswith(("What are", "How the", "Why this", "Apa itu", "Cara kerja", "Mengapa ini")))
            )
            ctk.CTkLabel(
                scroll,
                text=para,
                font=Fonts.bold(13) if is_heading else Fonts.regular(12),
                text_color=ThemeManager.primary() if is_heading else ThemeManager.text(),
                justify="left",
                wraplength=580,
            ).pack(anchor="w", pady=(10 if is_heading else 2, 4))

        # ---- Custom canary manager ----
        mgr = ctk.CTkFrame(scroll, fg_color=ThemeManager.surface_alt(), corner_radius=8)
        mgr.pack(fill="x", padx=4, pady=(16, 8))

        ctk.CTkLabel(
            mgr,
            text=tr("Add Custom Canary Domain or TLD"),
            font=Fonts.subtitle(13),
            text_color=ThemeManager.warning(),
        ).pack(anchor="w", padx=10, pady=(10, 4))

        entry_row = ctk.CTkFrame(mgr, fg_color="transparent")
        entry_row.pack(fill="x", padx=10)
        self._canary_entry = ctk.CTkEntry(
            entry_row,
            placeholder_text=tr("e.g. use-application-dns.net  or  .co.id  or  example.com"),
            font=Fonts.mono(11),
            height=32,
            fg_color=ThemeManager.surface(),
            border_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
        )
        self._canary_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._canary_list_lbl = ctk.CTkLabel(
            mgr,
            text=tr("Your Canaries ({n})").format(n=0),
            font=Fonts.regular(11),
            text_color=ThemeManager.text(),
            justify="left",
        )
        self._canary_list_lbl.pack(anchor="w", padx=10, pady=(6, 0))
        list_box = ctk.CTkTextbox(
            mgr,
            height=110,
            font=Fonts.mono(11),
            fg_color=ThemeManager.surface(),
            text_color=ThemeManager.text(),
        )
        list_box.pack(fill="x", padx=10, pady=(6, 4))

        btn_row = ctk.CTkFrame(mgr, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 10))

        def _refresh_list():
            items = canary_service._load_custom_canaries()
            list_box.configure(state="normal")
            list_box.delete("1.0", "end")
            if items:
                for it in items:
                    list_box.insert("end", f"• {it}\n")
            else:
                list_box.insert("end", tr("(no custom canaries yet)") + "\n")
            list_box.configure(state="disabled")
            try:
                self._canary_list_lbl.configure(text=tr("Your Canaries ({n})").format(n=len(items)))
            except Exception:
                pass

        def _add():
            hostname = self._canary_entry.get().strip().lower().rstrip(".")
            if not hostname:
                return
            if canary_service.add_custom_canary(hostname):
                self._canary_entry.delete(0, "end")
                self.main_app.show_toast(f"✓ Canary '{hostname}' ditambahkan.", level="success")
            else:
                self.main_app.show_toast(f"Format tidak valid: '{hostname}'", level="error")
            _refresh_list()

        def _remove():
            target = self._canary_entry.get().strip().lstrip("• ").strip() or getattr(self, "_canary_selected", "")
            if not target:
                return
            if canary_service.remove_custom_canary(target):
                self.main_app.show_toast(f"🗑 Canary '{target}' dihapus.", level="info")
            else:
                self.main_app.show_toast(f"Tidak ditemukan: '{target}'", level="warning")
            _refresh_list()

        def _use_selected(event=None):
            try:
                line = list_box.get("insert linestart", "insert lineend")
                host = line.replace("•", "").split("(")[0].strip()
                if host:
                    self._canary_entry.delete(0, "end")
                    self._canary_entry.insert(0, host)
                    self._canary_selected = host
            except Exception:
                pass

        list_box.bind("<ButtonRelease-1>", _use_selected)

        ctk.CTkButton(
            btn_row,
            text=tr("➕ Add"),
            width=80,
            height=30,
            font=Fonts.bold(11),
            fg_color=ThemeManager.primary(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            command=_add,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            btn_row,
            text=tr("🗑 Remove Selected"),
            width=140,
            height=30,
            font=Fonts.bold(11),
            fg_color=ThemeManager.danger(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            command=_remove,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            btn_row,
            text=tr("Use in Slot"),
            width=110,
            height=30,
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            command=lambda: _use_selected(),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            btn_row,
            text=tr("Close"),
            width=80,
            height=30,
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            command=win.destroy,
        ).pack(side="right")

        _refresh_list()

    def on_interface_change(self, choice: str):
        for i in self.interfaces:
            if i["label"] == choice:
                self.active_interface = i["device"]
                break
        self.load_active_interface_dns()

    def set_preset_label(self, label: str):
        """Set preset selection AND sync combobox values so CTkComboBox doesn't
        render blank text when the label sits outside the filtered list."""
        self.preset_var.set(label)
        try:
            vals = list(self.preset_cb.cget("values") or [])
            if label not in vals:
                vals.append(label)
                self.preset_cb.configure(values=vals)
            if hasattr(self, "preset_dropdown") and self.preset_dropdown:
                self.preset_dropdown.configure(values=vals)
        except Exception:
            pass

    def compute_provider_ips(self, provider: dict, provider_id, family: str) -> list:
        """Resolve slot IPs for a provider under a Protocol/IP family.
        Centralises IPv6 fallback, DoH forwarder startup, DoT resolution so
        presets and benchmark applies behave identically."""
        if "IPv6" in family:
            ips = provider.get("ipv6", [])
            if not ips:
                self.main_app.show_toast(
                    f"Provider '{provider.get('name')}' tidak menyediakan DNS IPv6 publik.", level="warning"
                )
                return provider.get("ipv4", [])

            def _check_v6():
                from netools.libs.net import check_ipv6_connectivity

                if not check_ipv6_connectivity():
                    self.after(
                        0,
                        lambda: self.main_app.show_toast(
                            tr(
                                "⚠️ Perhatian: Jaringan/ISP Anda tidak memiliki rute IPv6 aktif. DNS IPv6 mungkin timeout."
                            ),
                            level="warning",
                        ),
                    )

            threading.Thread(target=_check_v6, daemon=True).start()
            return ips

        if "DoH" in family:
            doh = provider.get("doh_url", "")
            if doh:
                from netools.config import DOH_PROXY_PORT
                from netools.services import doh_service

                started = False
                if provider_id:
                    try:
                        # (Re)start the local UDP->DoH forwarder on 127.0.0.1:DOH_PROXY_PORT.
                        # Restarting ensures switching providers from the GUI always
                        # targets the newly selected upstream, not a stale one.
                        doh_service.stop_doh_forwarder()
                        started = doh_service.start_doh_forwarder(provider=provider_id)
                    except Exception:
                        started = False
                if started:
                    self.main_app.show_toast(
                        f"🔒 DoH aktif via localhost:{DOH_PROXY_PORT} -> {provider.get('name')}",
                        level="success",
                    )
                    # System resolvers are IP-only; point them at the local forwarder
                    # with its real port so queries don't hit a dead port 53.
                    return [f"127.0.0.1:{DOH_PROXY_PORT}"]
                self.main_app.show_toast(
                    f"DoH forwarder gagal start untuk '{provider.get('name')}'. Pakai IPv4 fallback.",
                    level="warning",
                )
            else:
                self.main_app.show_toast(
                    f"Provider '{provider.get('name')}' tidak mendukung DoH. Pakai IPv4.",
                    level="warning",
                )
            return provider.get("ipv4", [])

        if "DoT" in family:
            dot_host = provider.get("dot_host")
            ips = []
            if dot_host:
                import socket as _socket

                try:
                    infos = _socket.getaddrinfo(dot_host, 853, _socket.AF_INET, _socket.SOCK_STREAM)
                    seen = []
                    for info in infos:
                        ip = info[4][0]
                        if ip not in seen:
                            seen.append(ip)
                    ips = seen
                except OSError:
                    pass
            return ips or provider.get("ipv4", [])

        return provider.get("ipv4", [])

    def sync_after_external_apply(self, provider_id=None, mode_key: str = "ipv4"):
        """Sync Category/Preset/Protocol selectors after a benchmark/smart-mix
        apply, so selectors reflect reality instead of inviting re-selection."""
        family_map = {
            "ipv4": "IPv4 (Standard)",
            "ipv6": "IPv6 (Next-Gen)",
            "doh": "DoH (HTTPS)",
            "dot": "DoT (TLS Port 853)",
        }
        self.ip_family_var.set(family_map.get(mode_key, "IPv4 (Standard)"))
        if mode_key == "dot":
            self.dot_var.set(True)

        self.category_var.set("📁 All Categories")
        self.on_category_filter_change(self.category_var.get())

        provider = self.providers.get(provider_id) if provider_id else None
        if provider:
            self.set_preset_label(f"{provider['country']} {provider['name']}")
        else:
            self.set_preset_label("⚙️ Custom DNS Servers")

        self.applied_source_kind = "external"

    def on_ip_family_change(self, choice: str):
        """Protocol/IP switch must NOT wipe externally-applied slots."""
        if getattr(self, "applied_source_kind", "preset") == "external":
            self.main_app.show_toast(
                tr("⚡ DNS hasil Benchmark tetap dipakai — ganti Preset bila ingin mengganti otomatis."),
                level="info",
            )
            return
        self.on_preset_change(self.preset_var.get())

    def load_active_interface_dns(self, dev: str = None):
        # If we're showing externally-applied benchmark results, don't wipe
        # the entry widgets with system DNS — preserve user-visible state.
        if getattr(self, "applied_source_kind", "preset") == "external":
            return
        if not dev:
            selected_label = self.iface_var.get()
            dev = self.active_interface
            for i in self.interfaces:
                if i["label"] == selected_label:
                    dev = i["device"]
                    break

        self.dns1_entry.delete(0, "end")
        self.dns2_entry.delete(0, "end")
        self.dns3_entry.delete(0, "end")
        self.lbl_ping1.configure(text="")
        self.lbl_ping2.configure(text="")
        self.lbl_ping3.configure(text="")

        def _bg():
            current_dns = sys_dns.get_interface_dns(dev)

            dot_active = False
            try:
                import subprocess

                out = subprocess.check_output(["resolvectl", "status", dev], text=True, stderr=subprocess.DEVNULL)
                if "+DNSOverTLS" in out or "DNSOverTLS=yes" in out or "DNSOverTLS=opportunistic" in out:
                    dot_active = True
            except Exception:
                pass

            def _update_ui():
                try:
                    if current_dns:
                        if len(current_dns) > 0:
                            self.dns1_entry.insert(0, current_dns[0])
                        if len(current_dns) > 1:
                            self.dns2_entry.insert(0, current_dns[1])
                        if len(current_dns) > 2:
                            self.dns3_entry.insert(0, current_dns[2])

                        matched = False
                        for p in self.providers.values():
                            p_ips = p.get("ipv4", [])
                            p_v6 = p.get("ipv6", [])
                            first = current_dns[0]
                            if (len(p_ips) > 0 and p_ips[0] == first) or (len(p_v6) > 0 and p_v6[0] == first):
                                self.set_preset_label(f"{p['country']} {p['name']}")
                                if any(":" in ip for ip in current_dns):
                                    self.ip_family_var.set("IPv6 (Next-Gen)")
                                else:
                                    self.ip_family_var.set("IPv4 (Standard)")
                                matched = True
                                break
                            if first == "127.0.0.1":
                                try:
                                    from netools.services import doh_service as _doh_svc

                                    pid = _doh_svc.get_active_provider()
                                    if pid and self.providers.get(pid) is p:
                                        self.set_preset_label(f"{p['country']} {p['name']}")
                                        self.ip_family_var.set("DoH (HTTPS)")
                                        matched = True
                                        break
                                except Exception:
                                    pass
                        if not matched:
                            self.set_preset_label("⚙️ Custom DNS Servers")
                            self.applied_source_kind = "system"
                        else:
                            self.applied_source_kind = "preset"

                        if len(current_dns) > 0:
                            self.ping_slot(1)
                        if len(current_dns) > 1:
                            self.ping_slot(2)
                        if len(current_dns) > 2:
                            self.ping_slot(3)
                    else:
                        self.set_preset_label("⚙️ Custom DNS Servers")

                    self.dot_var.set(dot_active)
                except Exception:
                    pass

            try:
                self.after(0, _update_ui)
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def on_preset_change(self, choice: str):
        if "Custom" in choice:
            self.applied_source_kind = "preset"
            return
        family = self.ip_family_var.get() if hasattr(self, "ip_family_var") else "IPv4 (Standard)"
        for p in self.providers.values():
            label = f"{p['country']} {p['name']}"
            if label == choice:
                provider_id = next((pid for pid, prov in self.providers.items() if prov is p), None)
                ips = self.compute_provider_ips(p, provider_id, family)
                self.dns1_entry.delete(0, "end")
                self.dns2_entry.delete(0, "end")
                self.dns3_entry.delete(0, "end")
                if len(ips) > 0:
                    self.dns1_entry.insert(0, ips[0])
                if len(ips) > 1:
                    self.dns2_entry.insert(0, ips[1])
                if len(ips) > 2:
                    self.dns3_entry.insert(0, ips[2])
                self.applied_source_kind = "preset"
                break

    def refresh_adapters(self):
        self.interfaces = sys_dns.get_network_interfaces()
        labels = [i["label"] for i in self.interfaces] if self.interfaces else ["Default"]
        self.iface_cb.configure(values=labels)
        if labels:
            self.iface_var.set(labels[0])
            self.active_interface = self.interfaces[0]["device"] if self.interfaces else "default"
        self.load_active_interface_dns()
        self.main_app.show_toast(f"✓ {len(self.interfaces)} Network Adapters refreshed & DNS synced.", level="info")

    def ping_slot(self, slot_num: int):
        entry = [self.dns1_entry, self.dns2_entry, self.dns3_entry][slot_num - 1]
        lbl = [self.lbl_ping1, self.lbl_ping2, self.lbl_ping3][slot_num - 1]
        ip = entry.get().strip()
        if not ip:
            return
        lbl.configure(text="Pinging...", text_color=ThemeManager.text())

        def _bg():
            from netools.libs.net import ping_ip

            lat = ping_ip(ip, timeout=1.5)
            try:
                self.after(
                    0,
                    lambda: lbl.configure(
                        text=f"{lat:.1f} ms" if lat else "Timeout",
                        text_color=ThemeManager.success() if lat else ThemeManager.danger(),
                    ),
                )
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def apply_dns(self):
        ips = [self.dns1_entry.get().strip(), self.dns2_entry.get().strip(), self.dns3_entry.get().strip()]
        valid = [ip for ip in ips if ip]
        if not valid:
            self.main_app.show_toast(tr("Isi minimal 1 IP DNS valid!"), level="warning")
            return

        selected_label = self.iface_var.get()
        dev = self.active_interface
        conn = None
        for i in self.interfaces:
            if i["label"] == selected_label:
                dev = i["device"]
                conn = i.get("connection")
                break

        def _bg():
            success = sys_dns.apply_system_dns(
                dev, valid, connection_name=conn, enable_dot=self.dot_var.get(), persistent=self.persist_var.get()
            )
            try:
                if success:
                    self.after(
                        0,
                        lambda: self.main_app.show_toast(
                            f"✓ DNS ({', '.join(valid)}) diterapkan ke '{dev}'!", level="success"
                        ),
                    )
                    self.after(0, self.load_active_interface_dns)
                    if hasattr(self.main_app, "dashboard_view"):
                        self.after(0, self.main_app.dashboard_view.refresh)
                else:
                    self.after(
                        0,
                        lambda: self.main_app.show_toast(f"Gagal menerapkan DNS ke interface '{dev}'.", level="error"),
                    )
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def flush_dns(self):
        def _bg():
            sys_dns.flush_dns_cache()
            try:
                self.after(0, lambda: self.main_app.show_toast(tr("✓ DNS Cache berhasil di-flush!"), level="success"))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def restore_dhcp(self):
        selected_label = self.iface_var.get()
        dev = self.active_interface
        conn = None
        for i in self.interfaces:
            if i["label"] == selected_label:
                dev = i["device"]
                conn = i.get("connection")
                break

        def _bg():
            sys_dns.restore_default_dns(dev, connection_name=conn)
            try:
                self.after(
                    0,
                    lambda: self.main_app.show_toast(
                        f"✓ Interface '{dev}' dikembalikan ke DHCP default.", level="info"
                    ),
                )
                self.after(0, self.load_active_interface_dns)
                if hasattr(self.main_app, "dashboard_view"):
                    self.after(0, self.main_app.dashboard_view.refresh)
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def on_category_filter_change(self, cat_name: str):
        filtered_labels = ["⚙️ Custom DNS Servers"]
        for p in self.providers.values():
            cat = p.get("category", "").lower()
            region = p.get("region", "").lower()
            name = p.get("name", "").lower()
            desc = p.get("description", "").lower()

            if (
                "All" in cat_name
                or (
                    "Security" in cat_name
                    and (cat == "security" or "security" in desc or "privacy" in desc or "no-log" in desc)
                )
                or (
                    "Gaming" in cat_name
                    and (cat == "gaming" or "gaming" in desc or "game" in name or "fast" in desc or region == "asia")
                )
                or ("Ad-Blocking" in cat_name and (cat == "adblock" or "ad" in desc or "block" in desc))
                or (
                    "Family" in cat_name
                    and (cat == "family" or "family" in desc or "parental" in desc or "safe" in desc)
                )
                or ("Asia" in cat_name and region == "asia")
                or ("Global" in cat_name and (region == "global" or "anycast" in desc))
            ):
                filtered_labels.append(f"{p['country']} {p['name']}")

        if hasattr(self, "preset_dropdown") and self.preset_dropdown:
            self.preset_dropdown.configure(values=filtered_labels)
        if hasattr(self, "preset_cb"):
            self.preset_cb.configure(values=filtered_labels)
            if self.preset_var.get() not in filtered_labels:
                self.preset_var.set("⚙️ Custom DNS Servers")

    def refresh_presets(self):
        self.providers = db.load_providers()
        if hasattr(self, "category_var"):
            self.on_category_filter_change(self.category_var.get())
        else:
            preset_labels = [f"{p['country']} {p['name']}" for p in self.providers.values()]
            preset_labels.insert(0, "⚙️ Custom DNS Servers")
            if hasattr(self, "preset_dropdown") and self.preset_dropdown:
                self.preset_dropdown.configure(values=preset_labels)
            if hasattr(self, "preset_cb"):
                self.preset_cb.configure(values=preset_labels)

    def open_benchmark(self):
        if hasattr(self, "benchmark_modal") and self.benchmark_modal is not None:
            try:
                if self.benchmark_modal.winfo_exists():
                    self.benchmark_modal.deiconify()
                    self.benchmark_modal.lift()
                    self.benchmark_modal.focus_force()
                    return
            except Exception:
                pass

        self.benchmark_modal = GRCBenchmarkModal(self.main_app, self)
        self.main_app.child_windows.append(self.benchmark_modal)

    def open_dpi_inspector(self):
        if hasattr(self, "dpi_modal") and self.dpi_modal is not None:
            try:
                if self.dpi_modal.winfo_exists():
                    self.dpi_modal.deiconify()
                    self.dpi_modal.lift()
                    self.dpi_modal.focus_force()
                    return
            except Exception:
                pass

        self.dpi_modal = DPIInspectorModal(self.main_app)
        self.main_app.child_windows.append(self.dpi_modal)

    def verify_dns_status(self):
        """Probe active resolvers (UDP / DoT / DoH) + TLS capability, then
        render the universal inspector window."""
        dev = self.active_interface

        def _bg():
            results_lines = []
            try:
                current = sys_dns.get_interface_dns(dev) or []
                dot_state = "Disabled"
                try:
                    import subprocess

                    out = subprocess.check_output(
                        ["resolvectl", "status", dev],
                        text=True,
                        stderr=subprocess.DEVNULL,
                    )
                    if "DNSOverTLS=yes" in out:
                        dot_state = "Strict (+DNSOverTLS)"
                    elif "DNSOverTLS=opportunistic" in out:
                        dot_state = "Opportunistic (TLS 853)"
                except Exception:
                    pass

                from netools.libs import dns_benchmark as bm

                for _idx, ip in enumerate(current[:3], start=1):
                    provider = next(
                        (p for p in self.providers.values() if ip in p.get("ipv4", []) or ip in p.get("ipv6", [])),
                        None,
                    )
                    pname = provider.get("name", "Unknown") if provider else "Custom"
                    lat = None
                    tls_label = "⚪ No TLS"
                    try:
                        lat = bm.query_udp_dns(ip, "google.com")
                    except Exception:
                        lat = None

                    doh_url = (provider or {}).get("doh_url") if provider else ""
                    if not doh_url and ip == "127.0.0.1":
                        from netools.services import doh_service as _doh_svc

                        pid = _doh_svc.get_active_provider() if hasattr(_doh_svc, "get_active_provider") else None
                        prov = self.providers.get(pid) if pid else None
                        doh_url = prov.get("doh_url", "") if prov else ""

                    doh_status = "🔴 Failed / Blocked"
                    if doh_url:
                        try:
                            import time as _time

                            t0 = _time.time()
                            bm.query_doh_dns(doh_url, "google.com")
                            ms = (__import__("time").time() - t0) * 1000
                            doh_status = f"🟢 Connected ({ms:.0f} ms)"
                        except Exception:
                            pass

                    line = f"• {pname} ({ip}): UDP {f'{lat:.1f}' if lat else 'Timeout'} | {tls_label}"
                    results_lines.append(line)
                    if doh_url:
                        results_lines.append(
                            f"   • DoH ({doh_url.split('/')[2] if '/' in doh_url else doh_url}) : {doh_status}"
                        )

                if not results_lines:
                    results_lines.append("• No active DNS servers detected (DHCP Default)")
                results_lines.append(f"• DoT (OS): {dot_state}")
            except Exception as e:
                results_lines.append(f"• probe error: {e}")

            report = "\n".join(results_lines)
            try:
                self.after(0, lambda: self._show(dev, report))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def _bg(self, dev):  # placeholder retained for API parity
        pass

    def _show(self, dev: str, report: str):
        if self.verify_modal is not None:
            try:
                if self.verify_modal.winfo_exists():
                    self.verify_modal.destroy()
            except Exception:
                pass

        win = ctk.CTkToplevel(self)
        self.verify_modal = win
        win.title(tr("🔍 Universal DNS & Encryption Inspector"))
        win.geometry("540x400")
        win.configure(fg_color=ThemeManager.bg())
        from netools.gui.wm import mark_dialog

        mark_dialog(win, self.winfo_toplevel())
        win.grab_set()
        win.protocol("WM_DELETE_WINDOW", self._close_verify)

        iface_line = tr("• Network Interface : ") + dev
        transport = (
            "🟢 Encrypted"
            if ("DoH" in self.ip_family_var.get() or "DoT" in self.ip_family_var.get() or self.dot_var.get())
            else "⚪ Plain UDP 53"
        )
        ctk.CTkLabel(win, text=iface_line, font=Fonts.bold(12), text_color=ThemeManager.success()).pack(
            anchor="w", padx=14, pady=(12, 0)
        )
        ctk.CTkLabel(
            win, text="• OS Transport      : " + transport, font=Fonts.mono(11), text_color=ThemeManager.text()
        ).pack(anchor="w", padx=14)

        box = ctk.CTkTextbox(win, font=Fonts.mono(11), fg_color=ThemeManager.surface(), text_color=ThemeManager.text())
        box.pack(fill="both", expand=True, padx=12, pady=10)
        header = tr("── Active Resolvers Latency & TLS Capability ──")
        body = report if report.strip() else tr("• No active DNS servers detected (DHCP Default)")
        box.insert("1.0", header + "\n" + body)

        btn_row = ctk.CTkFrame(win, fg_color=ThemeManager.bg())
        btn_row.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkButton(
            btn_row,
            text=tr("🌐 Universal Leak Test"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.primary(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=32,
            command=self._open_leak_test,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_row,
            text=tr("🌐 1.1.1.1/help"),
            font=Fonts.regular(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            height=32,
            command=self._open_cf_help,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_row,
            text=tr("Close"),
            width=90,
            height=32,
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            command=self._close_verify,
        ).pack(side="right")

    def _close_verify(self):
        if self.verify_modal is not None:
            try:
                self.verify_modal.destroy()
            except Exception:
                pass
            self.verify_modal = None

    def _open_leak_test(self):
        import webbrowser

        webbrowser.open("https://browserleaks.com/dns")

    def _open_cf_help(self):
        import webbrowser

        webbrowser.open("https://one.one.one.one/help")
        # [reconstructed tail — original body beyond this point rebuilt from
        #  behaviour specs; report layout preserved via pyc string inventory]
