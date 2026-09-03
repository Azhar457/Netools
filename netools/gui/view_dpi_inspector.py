"""
Visual Multi-Layer Censorship & Deep Packet Inspection (DPI) Flow Inspector Modal.
Presents an interactive 4-node flow diagram showing where a domain is blocked:
Node A (DNS) -> Node B (TCP 443) -> Node C (TLS SNI DPI) -> Node D (SSL MITM)
"""

import threading

import customtkinter as ctk

from netools.gui.i18n import tr
from netools.gui.theme import (
    Fonts,
    ThemeManager,
)
from netools.gui.wm import mark_dialog
from netools.libs import dpi_detector


class DPIInspectorModal(ctk.CTkToplevel):
    def __init__(self, parent_app, default_domain: str = "dashboard.ngrok.com"):
        super().__init__(parent_app)
        self.parent_app = parent_app

        self.title("🔍 Multi-Layer Censorship & DPI Flow Inspector — Netools")
        self.geometry("980x700")
        self.minsize(860, 580)
        self.configure(fg_color=ThemeManager.bg())

        self.is_running = False
        self.default_domain = default_domain

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        mark_dialog(self, parent_app)
        self._build_ui()

    def on_close(self):
        self.is_running = False
        try:
            if self in self.parent_app.child_windows:
                self.parent_app.child_windows.remove(self)
        except Exception:
            pass
        self.destroy()

    def _build_ui(self):
        # 1. Header Banner
        hdr = ctk.CTkFrame(self, fg_color=ThemeManager.surface_alt(), height=50)
        hdr.pack(fill="x", padx=0, pady=0)
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text=tr("🔬 Multi-Layer Censorship & Deep Packet Inspection (DPI) Flow Analyzer"),
            font=Fonts.title(15),
            text_color=ThemeManager.warning()
        ).pack(side="left", padx=20, pady=10)

        # 2. Input Control Card
        card_input = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        card_input.pack(fill="x", padx=16, pady=8)

        r1 = ctk.CTkFrame(card_input, fg_color=ThemeManager.surface())
        r1.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(r1, text=tr("Target Domain / Hostname:"), font=Fonts.bold(12), text_color=ThemeManager.text()).pack(side="left", padx=(0, 8))

        self.entry_domain = ctk.CTkEntry(
            r1,
            width=300,
            height=36,
            font=Fonts.mono(12),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            placeholder_text="e.g. dashboard.ngrok.com"
        )
        self.entry_domain.insert(0, self.default_domain)
        self.entry_domain.pack(side="left", padx=4)

        self.btn_run = ctk.CTkButton(
            r1,
            text=tr("🚀 Analyze Network Flow"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.warning(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=36,
            width=180,
            command=self.start_analysis
        )
        self.btn_run.pack(side="left", padx=8)

        # Quick Preset Chips
        r2 = ctk.CTkFrame(card_input, fg_color=ThemeManager.surface())
        r2.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(r2, text=tr("Quick Test Presets:"), font=Fonts.regular(11), text_color=ThemeManager.text_muted()).pack(side="left", padx=(0, 6))

        presets = ["dashboard.ngrok.com", "reddit.com", "discord.com", "cloudflare.com", "google.com"]
        for p in presets:
            ctk.CTkButton(
                r2,
                text=p,
                font=Fonts.regular(10),
                fg_color=ThemeManager.border(),
                text_color=ThemeManager.text(),
                hover_color=ThemeManager.surface_alt(),
                height=26,
                command=lambda val=p: self._set_preset(val)
            ).pack(side="left", padx=3)

        # 3. Interactive Visual Node Flow Pipeline Card
        self.card_nodes = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.card_nodes.pack(fill="x", padx=16, pady=4)

        ctk.CTkLabel(
            self.card_nodes,
            text=tr("📊 Network Handshake & OSI Stage Flow Diagram"),
            font=Fonts.subtitle(13),
            text_color=ThemeManager.primary()
        ).pack(anchor="w", padx=14, pady=(8, 4))

        self.flow_container = ctk.CTkFrame(self.card_nodes, fg_color=ThemeManager.surface())
        self.flow_container.pack(fill="x", padx=10, pady=(4, 12))

        # Build 4 Interactive Node Cards
        self.node_widgets = {}
        nodes_config = [
            ("A", tr("🌐 Node A\nDNS Resolution"), tr("Layer 7 (IP Lookup)")),
            ("B", tr("🔌 Node B\nTCP Port 443"), tr("Layer 4 (Routing & SYN)")),
            ("C", tr("🔒 Node C\nTLS SNI Handshake"), tr("Layer 7 DPI (ClientHello)")),
            ("D", tr("🛡️ Node D\nSSL & MITM Cert"), tr("Layer 7 (Encryption Cert)"))
        ]

        for idx, (nid, title, subtitle) in enumerate(nodes_config):
            card = ctk.CTkFrame(self.flow_container, fg_color=ThemeManager.surface_alt(), corner_radius=6, border_width=1, border_color=ThemeManager.border())
            card.pack(side="left", fill="both", expand=True, padx=4, pady=2)

            lbl_t = ctk.CTkLabel(card, text=title, font=Fonts.bold(11), text_color=ThemeManager.text(), justify="center")
            lbl_t.pack(pady=(6, 2))

            lbl_sub = ctk.CTkLabel(card, text=subtitle, font=Fonts.regular(9), text_color=ThemeManager.text_muted())
            lbl_sub.pack(pady=(0, 4))

            badge = ctk.CTkLabel(
                card,
                text="⚪ READY",
                font=Fonts.bold(9),
                fg_color=ThemeManager.border(),
                corner_radius=4,
                width=80,
                height=20
            )
            badge.pack(pady=(2, 6))

            self.node_widgets[nid] = {
                "card": card,
                "title": lbl_t,
                "badge": badge
            }

            if idx < len(nodes_config) - 1:
                arrow = ctk.CTkLabel(self.flow_container, text="▶", font=Fonts.bold(12), text_color=ThemeManager.text_muted())
                arrow.pack(side="left", padx=1)

        # 4. Details Breakdown Card (Scrollable)
        self.details_card = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.details_card.pack(fill="both", expand=True, padx=16, pady=4)

        ctk.CTkLabel(
            self.details_card,
            text=tr("📑 Stage-by-Stage Diagnostic Details"),
            font=Fonts.subtitle(11),
            text_color=ThemeManager.text()
        ).pack(anchor="w", padx=14, pady=(8, 4))

        self.details_scroll = ctk.CTkScrollableFrame(self.details_card, fg_color="transparent")
        self.details_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.lbl_initial_hint = ctk.CTkLabel(
            self.details_scroll,
            text=tr("Masukkan nama domain dan klik 'Analyze Network Flow' untuk memeriksa jalur koneksi secara bertahap."),
            font=Fonts.regular(10),
            text_color=ThemeManager.text_muted(),
            justify="left"
        )
        self.lbl_initial_hint.pack(anchor="w", padx=8, pady=6)

        # 5. Actionable Recommendation & Verdict Card
        self.rec_card = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.rec_card.pack(fill="x", padx=16, pady=(4, 12))

        self.lbl_headline = ctk.CTkLabel(
            self.rec_card,
            text=tr("⚪ Status: Siap melakukan analisis jaringan multi-layer."),
            font=Fonts.bold(11),
            text_color=ThemeManager.text(),
            anchor="w"
        )
        self.lbl_headline.pack(fill="x", padx=14, pady=(8, 2))

        self.lbl_recommendation = ctk.CTkLabel(
            self.rec_card,
            text=tr("• Masukkan domain untuk melihat analisis apakah blokir terjadi di level DNS, IP Firewall, SNI DPI, atau SSL MITM."),
            font=Fonts.regular(10),
            text_color=ThemeManager.text_muted(),
            justify="left",
            anchor="w",
            wraplength=850
        )
        self.lbl_recommendation.pack(fill="x", padx=14, pady=(0, 8))

        # Bottom Buttons Row
        btn_row = ctk.CTkFrame(self.rec_card, fg_color=ThemeManager.surface())
        btn_row.pack(fill="x", padx=14, pady=(0, 8))

        self.btn_proxy_shortcut = ctk.CTkButton(
            btn_row,
            text=tr("⚡ Buka Tab Proxy (Sing-box)"),
            font=Fonts.bold(10),
            fg_color=ThemeManager.secondary(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=28,
            command=self._go_to_proxy_tab
        )
        self.btn_proxy_shortcut.pack(side="left", padx=(0, 6))

        self.btn_dns_shortcut = ctk.CTkButton(
            btn_row,
            text=tr("⚡ Ganti DNS (Smart Mix)"),
            font=Fonts.bold(10),
            fg_color=ThemeManager.primary(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=28,
            command=self._go_to_dns_tab
        )
        self.btn_dns_shortcut.pack(side="left", padx=6)

        ctk.CTkButton(
            btn_row,
            text=tr("Close"),
            font=Fonts.regular(10),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            width=70,
            height=28,
            command=self.destroy
        ).pack(side="right")

    def _set_preset(self, dom: str):
        self.entry_domain.delete(0, "end")
        self.entry_domain.insert(0, dom)

    def start_analysis(self):
        if self.is_running:
            return

        domain = self.entry_domain.get().strip()
        if not domain:
            self.parent_app.show_toast("Masukkan nama domain yang valid!", level="warning")
            return

        self.is_running = True
        self.btn_run.configure(state="disabled", text="⏳ Analyzing...")

        # Reset node badges
        for nid in ("A", "B", "C", "D"):
            self.node_widgets[nid]["badge"].configure(text="⏳ TESTING...", fg_color=ThemeManager.warning())

        # Clear details frame
        for child in self.details_scroll.winfo_children():
            child.destroy()

        self.lbl_headline.configure(text=f"⏳ Sedang mendiagnosis koneksi ke '{domain}'...", text_color=ThemeManager.warning())
        self.lbl_recommendation.configure(text="Menguji Layer 7 DNS -> Layer 4 TCP -> Layer 7 TLS SNI -> SSL Certificate...")

        def _bg():
            report = dpi_detector.diagnose_domain_reachability(domain, timeout=3.0)

            def _update_ui():
                self.is_running = False
                self.btn_run.configure(state="normal", text="🚀 Analyze Network Flow")
                self._render_report(report)

            try:
                self.after(0, _update_ui)
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def _render_report(self, report: dpi_detector.DomainDiagnosticReport):
        # 1. Update Node Badges
        for nid, stage in report.stages.items():
            if nid not in self.node_widgets:
                continue
            badge = self.node_widgets[nid]["badge"]
            if stage.status == "PASS":
                badge.configure(text="🟢 PASS", fg_color=ThemeManager.success())
            elif stage.status == "BLOCKED":
                badge.configure(text="🔴 BLOCKED", fg_color=ThemeManager.danger())
            elif stage.status == "WARN":
                badge.configure(text="🟡 WARN", fg_color=ThemeManager.warning())
            else:
                badge.configure(text="⚪ SKIPPED", fg_color=ThemeManager.border())

        # 2. Render Details in Scrollable Frame
        for child in self.details_scroll.winfo_children():
            child.destroy()

        for nid in ("A", "B", "C", "D"):
            stage = report.stages.get(nid)
            if not stage:
                continue

            stage_frame = ctk.CTkFrame(self.details_scroll, fg_color=ThemeManager.surface_alt(), corner_radius=6)
            stage_frame.pack(fill="x", padx=4, pady=3)

            hdr_txt = f"{stage.name} — {stage.summary}"
            status_color = ThemeManager.success() if stage.status == "PASS" else (
                ThemeManager.danger() if stage.status == "BLOCKED" else (
                    ThemeManager.warning() if stage.status == "WARN" else ThemeManager.text_muted()
                )
            )

            ctk.CTkLabel(stage_frame, text=hdr_txt, font=Fonts.bold(10), text_color=status_color, anchor="w").pack(fill="x", padx=10, pady=(6, 2))

            for detail in stage.details:
                ctk.CTkLabel(stage_frame, text=detail, font=Fonts.regular(9), text_color=ThemeManager.text(), anchor="w", justify="left").pack(fill="x", padx=14, pady=1)

        # 3. Update Headline & Recommendation
        headline_color = ThemeManager.success() if report.verdict == "CLEAN_REACHABLE" else (
            ThemeManager.danger() if "BLOCKED" in report.verdict else ThemeManager.warning()
        )
        self.lbl_headline.configure(text=report.summary_headline, text_color=headline_color)
        self.lbl_recommendation.configure(text=f"💡 Rekomendasi Solusi: {report.recommendation}")

    def _go_to_proxy_tab(self):
        try:
            if hasattr(self.parent_app, "tab_nav"):
                self.parent_app.tab_nav.set("Proxy Rotator")
            elif hasattr(self.parent_app, "select_tab"):
                self.parent_app.select_tab("proxy")
            self.destroy()
        except Exception:
            pass

    def _go_to_dns_tab(self):
        try:
            if hasattr(self.parent_app, "tab_nav"):
                self.parent_app.tab_nav.set("DNS Suite")
            elif hasattr(self.parent_app, "select_tab"):
                self.parent_app.select_tab("dns")
            self.destroy()
        except Exception:
            pass
