"""
AI Session & Cookie Extractor View (Dedicated Tab in Netools GUI).
Supports:
1. Interactive Browser Login with Auto-Capture (OAuth-like flow).
2. Instant Local Storage Scanning for Brave, Chrome, and Firefox.
3. Multi-session management with TTL indicators.
4. 1-Click or Bulk Inject to OmniRoute.
"""

import threading

import customtkinter as ctk

from netools.gui.i18n import tr
from netools.gui.theme import Fonts, ThemeManager
from netools.services.browser_capture import (
    PROVIDER_URLS,
    BrowserLoginSession,
    find_browser_executable,
)
from netools.services.omniroute_bridge import (
    inject_bulk_sessions,
    inject_session_to_omniroute,
)
from netools.services.session_extractor import (
    SUPPORTED_PROVIDERS,
    extract_all_browser_sessions,
)
from netools.services.token_rotator import TokenRotator


class SessionExtractorView(ctk.CTkFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color=ThemeManager.bg(), corner_radius=0)
        self.main_app = main_app
        self.active_login_session = None
        self.sessions = []
        self.selected_indices: set = set()

        # Auto-rotator
        self.rotator = TokenRotator(scan_interval=30, threshold=300)
        self.rotator.on_status = self._on_rotator_status
        self.rotator.on_rotation = self._on_rotator_event

        self._build_ui()
        self.after(200, self._scan_existing_sessions)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def apply_theme(self):
        self.configure(fg_color=ThemeManager.bg())
        for attr, key in [
            ("hdr", "fg_color"),
            ("card_interactive", "fg_color"),
            ("card_rotator", "fg_color"),
            ("card_tokens", "fg_color"),
        ]:
            if hasattr(self, attr):
                getattr(self, attr).configure(fg_color=getattr(ThemeManager, key)())

        if hasattr(self, "lbl_title"):
            self.lbl_title.configure(text_color=ThemeManager.primary())
        if hasattr(self, "txt_token"):
            self.txt_token.configure(
                fg_color=ThemeManager.surface_alt(),
                border_color=ThemeManager.border(),
                text_color=ThemeManager.text(),
            )

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ── Header ──
        self.hdr = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        self.hdr.pack(fill="x", padx=16, pady=(12, 10))

        self.lbl_title = ctk.CTkLabel(
            self.hdr,
            text=tr("🍪 AI Web Session & Cookie Extractor"),
            font=Fonts.title(16),
            text_color=ThemeManager.primary(),
        )
        self.lbl_title.pack(side="left")

        self.lbl_sub = ctk.CTkLabel(
            self.hdr,
            text=tr("Ambil token session web AI via Browser Profil atau Login Interaktif Otomatis"),
            font=Fonts.regular(11),
            text_color=ThemeManager.text_muted(),
        )
        self.lbl_sub.pack(side="left", padx=(12, 0), pady=(3, 0))

        # ── Card 1: Interactive Login & Auto-Capture ──
        self.card_interactive = ctk.CTkFrame(
            self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border()
        )
        self.card_interactive.pack(fill="x", padx=16, pady=4)

        f_inter_hdr = ctk.CTkFrame(self.card_interactive, fg_color=ThemeManager.surface())
        f_inter_hdr.pack(fill="x", padx=14, pady=(10, 6))

        ctk.CTkLabel(
            f_inter_hdr,
            text=tr("🌐 Mode 1: Login Interaktif via Browser (Auto-Capture)"),
            font=Fonts.bold(13),
            text_color=ThemeManager.text(),
        ).pack(side="left")

        ctk.CTkLabel(
            f_inter_hdr,
            text=tr("Buka browser popup, login, Netools otomatis menangkap token & menutup browser."),
            font=Fonts.regular(11),
            text_color=ThemeManager.text_muted(),
        ).pack(side="left", padx=(10, 0))

        # Controls Row
        f_ctrl = ctk.CTkFrame(self.card_interactive, fg_color=ThemeManager.surface())
        f_ctrl.pack(fill="x", padx=14, pady=(4, 10))

        # Browser Picker
        ctk.CTkLabel(f_ctrl, text=tr("Browser:"), font=Fonts.bold(11), text_color=ThemeManager.text()).pack(
            side="left", padx=(0, 4)
        )
        self.cbo_browser = ctk.CTkComboBox(
            f_ctrl,
            width=110,
            height=32,
            font=Fonts.regular(11),
            state="readonly",
            values=["Brave", "Chrome", "Firefox"],
        )
        self.cbo_browser.set("Brave" if find_browser_executable("Brave") else "Firefox")
        self.cbo_browser.pack(side="left", padx=(0, 12))

        # Provider Picker
        ctk.CTkLabel(f_ctrl, text=tr("Target AI:"), font=Fonts.bold(11), text_color=ThemeManager.text()).pack(
            side="left", padx=(0, 4)
        )
        prov_labels = [label for k, label in SUPPORTED_PROVIDERS if k != "all"]
        self.cbo_prov = ctk.CTkComboBox(
            f_ctrl,
            width=260,
            height=32,
            font=Fonts.regular(11),
            state="readonly",
            values=prov_labels,
            command=self._on_prov_selected,
        )
        self.cbo_prov.set(prov_labels[0])
        self.cbo_prov.pack(side="left", padx=(0, 10))

        # Custom Keyword Entry (hidden by default, shown when "Kustom" selected)
        self.entry_custom = ctk.CTkEntry(
            f_ctrl,
            width=180,
            height=32,
            font=Fonts.regular(11),
            placeholder_text="Domain / Kata Kunci...",
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
        )

        # Target URL Entry
        self.entry_url = ctk.CTkEntry(
            f_ctrl,
            width=220,
            height=32,
            font=Fonts.mono(11),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
        )
        self.entry_url.insert(0, PROVIDER_URLS.get("zai-web", "https://chat.z.ai/"))
        self.entry_url.pack(side="left", padx=(0, 12))

        # Launch Button
        self.btn_launch = ctk.CTkButton(
            f_ctrl,
            text=tr("🌐 Buka & Tangkap"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.primary(),
            text_color="#FFFFFF",
            hover_color=ThemeManager.secondary(),
            width=130,
            height=32,
            command=self._start_browser_login,
        )
        self.btn_launch.pack(side="left", padx=(0, 6))

        # Quick Scan Button
        self.btn_scan = ctk.CTkButton(
            f_ctrl,
            text=tr("🔍 Pindai Tersimpan"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            width=120,
            height=32,
            command=self._scan_existing_sessions,
        )
        self.btn_scan.pack(side="left")

        # Live Status bar
        self.lbl_capture_status = ctk.CTkLabel(
            self.card_interactive,
            text=tr("● Siap membuka browser atau memindai profil."),
            font=Fonts.bold(11),
            text_color=ThemeManager.accent(),
            anchor="w",
        )
        self.lbl_capture_status.pack(fill="x", padx=14, pady=(0, 10))

        # ── Card 1.5: Auto-Rotator ──
        self.card_rotator = ctk.CTkFrame(
            self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border()
        )
        self.card_rotator.pack(fill="x", padx=16, pady=4)

        f_rot = ctk.CTkFrame(self.card_rotator, fg_color=ThemeManager.surface())
        f_rot.pack(fill="x", padx=14, pady=(8, 6))

        ctk.CTkLabel(f_rot, text=tr("🔄 Auto-Rotator Token"), font=Fonts.bold(12), text_color=ThemeManager.text()).pack(
            side="left", padx=(0, 8)
        )

        ctk.CTkLabel(
            f_rot,
            text=tr("Otomatis putar token sebelum expiry."),
            font=Fonts.regular(10),
            text_color=ThemeManager.text_muted(),
        ).pack(side="left", padx=(0, 16))

        self.btn_rotator_toggle = ctk.CTkButton(
            f_rot,
            text=tr("▶ Mulai"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.success(),
            text_color="#FFFFFF",
            hover_color="#16a34a",
            width=90,
            height=28,
            command=self._toggle_rotator,
        )
        self.btn_rotator_toggle.pack(side="left", padx=(0, 6))

        self.btn_rotator_scan = ctk.CTkButton(
            f_rot,
            text=tr("🔍 Scan Sekarang"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            width=110,
            height=28,
            command=self._force_rotator_scan,
        )
        self.btn_rotator_scan.pack(side="left", padx=(0, 6))

        self.lbl_rotator_status = ctk.CTkLabel(
            f_rot, text=tr("⏹ Berhenti"), font=Fonts.bold(10), text_color=ThemeManager.text_muted()
        )
        self.lbl_rotator_status.pack(side="right", padx=(0, 4))

        self.lbl_rotator_count = ctk.CTkLabel(
            f_rot, text="", font=Fonts.regular(10), text_color=ThemeManager.text_muted()
        )
        self.lbl_rotator_count.pack(side="right", padx=(0, 10))

        # ── Card 2: Detected Sessions (multi-session with TTL) ──
        self.card_tokens = ctk.CTkFrame(
            self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border()
        )
        self.card_tokens.pack(fill="both", expand=True, padx=16, pady=8)

        f_tok_hdr = ctk.CTkFrame(self.card_tokens, fg_color=ThemeManager.surface())
        f_tok_hdr.pack(fill="x", padx=14, pady=(10, 6))

        ctk.CTkLabel(
            f_tok_hdr, text=tr("📋 Sesi Akun Terdeteksi:"), font=Fonts.bold(13), text_color=ThemeManager.text()
        ).pack(side="left", padx=(0, 8))

        self.lbl_summary = ctk.CTkLabel(f_tok_hdr, text="", font=Fonts.bold(11), text_color=ThemeManager.text_muted())
        self.lbl_summary.pack(side="left")

        # Bulk inject button
        self.btn_bulk_inject = ctk.CTkButton(
            f_tok_hdr,
            text=tr("🚀 Pasang Semua ke OmniRoute"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.secondary(),
            text_color="#FFFFFF",
            hover_color=ThemeManager.surface_alt(),
            height=30,
            width=200,
            command=self._bulk_inject,
        )
        self.btn_bulk_inject.pack(side="right", padx=(0, 4))

        # Scrollable session list
        self.session_list = ctk.CTkScrollableFrame(
            self.card_tokens, fg_color=ThemeManager.surface(), label_text="", label_font=Fonts.regular(1), height=180
        )
        self.session_list.pack(fill="both", expand=True, padx=14, pady=(4, 6))

        self.lbl_empty_sessions = ctk.CTkLabel(
            self.session_list,
            text=tr("Memindai sesi tersimpan..."),
            font=Fonts.regular(11),
            text_color=ThemeManager.text_muted(),
        )
        self.lbl_empty_sessions.pack(pady=20)

        # Token Display
        self.txt_token = ctk.CTkTextbox(
            self.card_tokens,
            font=Fonts.mono(11),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            border_width=1,
            text_color=ThemeManager.text(),
        )
        self.txt_token.pack(fill="both", expand=True, padx=14, pady=(4, 10))

        # Actions Row
        f_act = ctk.CTkFrame(self.card_tokens, fg_color=ThemeManager.surface())
        f_act.pack(fill="x", padx=14, pady=(0, 12))

        self.btn_copy = ctk.CTkButton(
            f_act,
            text=tr("📋 Salin Token ke Clipboard"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.primary(),
            text_color="#FFFFFF",
            hover_color=ThemeManager.secondary(),
            height=36,
            command=self._copy_token,
        )
        self.btn_copy.pack(side="left", padx=(0, 10))

        self.btn_inject = ctk.CTkButton(
            f_act,
            text=tr("🚀 Pasang ke OmniRoute"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.secondary(),
            text_color="#FFFFFF",
            hover_color=ThemeManager.surface_alt(),
            height=36,
            command=self._inject_single,
        )
        self.btn_inject.pack(side="left", padx=(0, 10))

    # ------------------------------------------------------------------
    # Provider Selection
    # ------------------------------------------------------------------

    def _on_prov_selected(self, choice):
        for k, lbl in SUPPORTED_PROVIDERS:
            if lbl == choice:
                # Show/hide custom keyword entry
                if k == "custom":
                    self.entry_custom.pack(side="left", padx=(0, 8))
                else:
                    self.entry_custom.pack_forget()

                url = PROVIDER_URLS.get(k, "")
                if url:
                    self.entry_url.delete(0, "end")
                    self.entry_url.insert(0, url)
                break

        # Re-scan with new filter
        self._scan_existing_sessions()

    # ------------------------------------------------------------------
    # Interactive Login
    # ------------------------------------------------------------------

    def _start_browser_login(self):
        b_name = self.cbo_browser.get()
        p_label = self.cbo_prov.get()
        p_key = "zai-web"
        for k, lbl in SUPPORTED_PROVIDERS:
            if lbl == p_label:
                p_key = k
                break
        target_url = self.entry_url.get().strip() or "https://chat.z.ai/"

        self.btn_launch.configure(state="disabled")
        self.lbl_capture_status.configure(
            text=tr(f"⏳ Meluncurkan {b_name}... Silakan login pada jendela popup."), text_color=ThemeManager.warning()
        )

        def _on_captured(session_dict):
            try:
                self.after(0, lambda: self._handle_capture_success(session_dict))
            except Exception:
                pass

        def _on_status(msg):
            try:
                self.after(0, lambda: self.lbl_capture_status.configure(text=msg))
            except Exception:
                pass

        self.active_login_session = BrowserLoginSession(
            browser_name=b_name,
            provider_key=p_key,
            target_url=target_url,
            on_captured=_on_captured,
            on_status=_on_status,
        )

        ok = self.active_login_session.start()
        if not ok:
            self.btn_launch.configure(state="normal")

    def _handle_capture_success(self, s):
        self.btn_launch.configure(state="normal")
        self.lbl_capture_status.configure(
            text=tr(f"✓ BERHASIL! Token {s['provider']} ({s['account']}) berhasil ditangkap."),
            text_color=ThemeManager.success(),
        )
        self.main_app.show_toast(tr(f"✓ Token login {s['provider']} berhasil ditangkap otomatis!"), level="success")
        self._scan_existing_sessions()

    # ------------------------------------------------------------------
    # Scanning & Display
    # ------------------------------------------------------------------

    def _scan_existing_sessions(self):
        self.lbl_capture_status.configure(text=tr("Memindai sesi tersimpan..."), text_color=ThemeManager.text_muted())

        # Determine provider filter and custom keyword from dropdown
        p_label = self.cbo_prov.get()
        p_key = "all"
        for k, lbl in SUPPORTED_PROVIDERS:
            if lbl == p_label:
                p_key = k
                break
        custom_kw = self.entry_custom.get().strip() if p_key == "custom" else ""

        def _bg():
            sessions = extract_all_browser_sessions(
                browser_filter="all",
                provider_filter=p_key,
                custom_keyword=custom_kw,
            )
            self.after(0, lambda: self._display_sessions(sessions))

        threading.Thread(target=_bg, daemon=True).start()

    def _display_sessions(self, sessions):
        self.sessions = sessions
        self.selected_indices.clear()

        # Clear previous rows
        for widget in self.session_list.winfo_children():
            widget.destroy()

        if not sessions:
            self.lbl_empty_sessions = ctk.CTkLabel(
                self.session_list,
                text=tr("ℹ️ Belum ada sesi tersimpan. Klik 'Buka & Tangkap' untuk login."),
                font=Fonts.regular(11),
                text_color=ThemeManager.text_muted(),
            )
            self.lbl_empty_sessions.pack(pady=20)
            self.lbl_summary.configure(text="")
            self.txt_token.delete("1.0", "end")
            self.lbl_capture_status.configure(
                text=tr("ℹ️ Belum ada sesi tersimpan."), text_color=ThemeManager.text_muted()
            )
            return

        # Compute summary
        active = sum(1 for s in sessions if s.get("ttl") and s["ttl"].status == "active")
        expiring = sum(1 for s in sessions if s.get("ttl") and s["ttl"].status == "expiring_soon")
        expired = sum(1 for s in sessions if s.get("ttl") and s["ttl"].status == "expired")
        unknown = len(sessions) - active - expiring - expired

        parts = []
        if active:
            parts.append(f"✅ {active} aktif")
        if expiring:
            parts.append(f"⚠️ {expiring} hampir habis")
        if expired:
            parts.append(f"❌ {expired} expired")
        if unknown:
            parts.append(f"❓ {unknown} unknown")
        self.lbl_summary.configure(text=" | ".join(parts))

        # Render rows
        for idx, s in enumerate(sessions):
            self._add_session_row(s, idx)

        if sessions:
            self._select_session(0)

        self.lbl_capture_status.configure(
            text=tr(f"✓ Ditemukan {len(sessions)} sesi login aktif di browser."), text_color=ThemeManager.success()
        )

        # Feed rotator with tracked sessions
        if self.rotator.is_running:
            self.rotator.track_sessions(sessions)
            self._update_rotator_count()

    def _add_session_row(self, session: dict, idx: int):
        """Render a single session row with checkbox, label, and TTL indicator."""
        ttl = session.get("ttl")
        ttl_label = ttl.label if ttl else "❓ Unknown"
        ttl_status = ttl.status if ttl else "unknown"

        color_map = {
            "active": ThemeManager.success(),
            "expiring_soon": ThemeManager.warning(),
            "expired": "#ef4444",
            "unknown": ThemeManager.text_muted(),
        }
        ttl_color = color_map.get(ttl_status, ThemeManager.text_muted())

        row = ctk.CTkFrame(
            self.session_list,
            fg_color=ThemeManager.surface(),
            corner_radius=6,
            border_width=1,
            border_color=ThemeManager.border(),
        )
        row.pack(fill="x", pady=2)

        # Checkbox for multi-select
        var = ctk.BooleanVar(value=False)
        cb = ctk.CTkCheckBox(
            row,
            text="",
            variable=var,
            width=24,
            fg_color=ThemeManager.primary(),
            hover_color=ThemeManager.secondary(),
            command=lambda i=idx, v=var: self._toggle_selection(i, v),
        )
        cb.pack(side="left", padx=(8, 4))

        # TTL dot
        ctk.CTkLabel(row, text="●", font=Fonts.bold(14), text_color=ttl_color, width=20).pack(side="left", padx=(0, 2))

        # Session label
        lbl = ctk.CTkLabel(
            row, text=session["label"], font=Fonts.regular(11), text_color=ThemeManager.text(), anchor="w"
        )
        lbl.pack(side="left", fill="x", expand=True, padx=4, pady=6)

        # TTL text
        ctk.CTkLabel(row, text=ttl_label, font=Fonts.bold(10), text_color=ttl_color, anchor="e").pack(
            side="right", padx=(4, 10)
        )

        # Bind click on row to select
        row.bind("<Button-1>", lambda e, i=idx: self._select_session(i))
        for child in row.winfo_children():
            child.bind("<Button-1>", lambda e, i=idx: self._select_session(i))

    def _select_session(self, idx: int):
        """Highlight and display token for the clicked session."""
        if idx < 0 or idx >= len(self.sessions):
            return

        # Visual highlight
        for i, row in enumerate(self.session_list.winfo_children()):
            if i == idx:
                row.configure(fg_color=ThemeManager.surface_alt(), border_color=ThemeManager.primary())
            else:
                row.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())

        self.txt_token.delete("1.0", "end")
        self.txt_token.insert("1.0", self.sessions[idx]["token"])

    def _toggle_selection(self, idx: int, var: ctk.BooleanVar):
        """Toggle multi-select for bulk inject."""
        if var.get():
            self.selected_indices.add(idx)
        else:
            self.selected_indices.discard(idx)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _copy_token(self):
        tok = self.txt_token.get("1.0", "end").strip()
        if not tok:
            self.main_app.show_toast(tr("Token kosong!"), level="warning")
            return
        self.clipboard_clear()
        self.clipboard_append(tok)
        self.main_app.show_toast(tr("✓ Token berhasil disalin ke Clipboard!"), level="success")

    def _inject_single(self):
        """Inject the currently selected/highlighted session into OmniRoute."""
        # Find which session is currently displayed
        displayed = self.txt_token.get("1.0", "end").strip()
        if not displayed:
            self.main_app.show_toast(tr("Pilih akun terlebih dahulu!"), level="warning")
            return

        # Find matching session
        target = None
        for s in self.sessions:
            if s["token"] == displayed:
                target = s
                break

        if not target:
            self.main_app.show_toast(tr("Pilih akun terlebih dahulu!"), level="warning")
            return

        result = inject_session_to_omniroute(provider=target["provider"], token=target["token"], name=target["account"])
        if result.success:
            self.main_app.show_toast(tr(f"✓ {result.message}"), level="success")
        else:
            self.main_app.show_toast(tr(f"❌ {result.message}"), level="error")

    # ------------------------------------------------------------------
    # Auto-Rotator Controls
    # ------------------------------------------------------------------

    def _toggle_rotator(self):
        """Start or stop the auto-rotator."""
        if self.rotator.is_running:
            self.rotator.stop()
            self.btn_rotator_toggle.configure(
                text=tr("▶ Mulai"),
                fg_color=ThemeManager.success(),
                hover_color="#16a34a",
            )
            self.lbl_rotator_status.configure(text=tr("⏹ Berhenti"), text_color=ThemeManager.text_muted())
        else:
            # Feed current sessions to the rotator
            self.rotator.track_sessions(self.sessions)
            self.rotator.start()
            self.btn_rotator_toggle.configure(
                text=tr("⏹ Stop"),
                fg_color="#ef4444",
                hover_color="#dc2626",
            )
            self.lbl_rotator_status.configure(text=tr("🔄 Aktif"), text_color=ThemeManager.success())
            self._update_rotator_count()

    def _force_rotator_scan(self):
        """Trigger an immediate rotator scan."""
        if not self.rotator.is_running:
            self.main_app.show_toast(tr("Mulai Auto-Rotator terlebih dahulu!"), level="warning")
            return
        self.rotator.track_sessions(self.sessions)
        self.rotator.force_scan_now()
        self.main_app.show_toast(tr("🔍 Scan dipicu oleh user..."), level="info")

    def _on_rotator_status(self, msg: str):
        """Callback from rotator thread — update UI safely."""
        try:
            self.after(0, lambda: self.lbl_rotator_status.configure(text=msg, text_color=ThemeManager.primary()))
        except Exception:
            pass

    def _on_rotator_event(self, event):
        """Callback when a rotation happens — refresh session list."""
        try:
            self.after(0, self._after_rotation)
        except Exception:
            pass

    def _after_rotation(self):
        """Refresh display after a rotation event."""
        self._update_rotator_count()
        self._scan_existing_sessions()

    def _update_rotator_count(self):
        """Update the rotation count label."""
        n = len(self.rotator.history)
        tracked = self.rotator.tracked_count
        if n > 0:
            self.lbl_rotator_count.configure(text=tr(f"{n} putaran | {tracked} dilacak"))
        else:
            self.lbl_rotator_count.configure(text=tr(f"{tracked} dilacak") if tracked else "")

    def _bulk_inject(self):
        """Inject all checked (or all, if none checked) sessions into OmniRoute."""
        if not self.sessions:
            self.main_app.show_toast(tr("Tidak ada sesi untuk dipasang!"), level="warning")
            return

        # Determine which sessions to inject
        if self.selected_indices:
            to_inject = [self.sessions[i] for i in sorted(self.selected_indices) if i < len(self.sessions)]
        else:
            # No checkbox selected → inject all active
            to_inject = [s for s in self.sessions if s.get("ttl") and s["ttl"].is_usable]

        if not to_inject:
            self.main_app.show_toast(tr("Tidak ada sesi aktif untuk dipasang!"), level="warning")
            return

        def _worker():
            results = inject_bulk_sessions(to_inject)
            ok = sum(1 for r in results if r.success)
            fail = len(results) - ok
            msg = f"✓ {ok} sesi berhasil dipasang"
            if fail:
                msg += f", {fail} gagal"
            try:
                self.after(0, lambda: self.main_app.show_toast(tr(msg), level="success" if ok else "error"))
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()
