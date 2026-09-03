"""
AI Session & Cookie Extractor View (Dedicated Tab in Netools GUI).
Supports:
1. Interactive Browser Login with Auto-Capture (OAuth-like flow).
2. Instant Local Storage Scanning for Brave, Chrome, and Firefox.
3. 1-Click Inject to OmniRoute.
"""

import threading
import customtkinter as ctk

from netools.gui.i18n import tr
from netools.gui.theme import Fonts, ThemeManager
from netools.services.browser_capture import (
    BrowserLoginSession,
    PROVIDER_URLS,
    find_browser_executable,
)
from netools.services.session_extractor import (
    SUPPORTED_PROVIDERS,
    extract_all_browser_sessions,
)


class SessionExtractorView(ctk.CTkFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color=ThemeManager.bg(), corner_radius=0)
        self.main_app = main_app
        self.active_login_session = None
        self.sessions = []
        self.selected_session = None

        self._build_ui()
        self.after(200, self._scan_existing_sessions)

    def apply_theme(self):
        self.configure(fg_color=ThemeManager.bg())
        if hasattr(self, "hdr"): self.hdr.configure(fg_color=ThemeManager.bg())
        if hasattr(self, "lbl_title"): self.lbl_title.configure(text_color=ThemeManager.primary())
        if hasattr(self, "card_interactive"): self.card_interactive.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "card_tokens"): self.card_tokens.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())
        if hasattr(self, "txt_token"): self.txt_token.configure(fg_color=ThemeManager.surface_alt(), border_color=ThemeManager.border(), text_color=ThemeManager.text())

    def _build_ui(self):
        # Header banner
        self.hdr = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        self.hdr.pack(fill="x", padx=16, pady=(12, 10))

        self.lbl_title = ctk.CTkLabel(
            self.hdr,
            text=tr("🍪 AI Web Session & Cookie Extractor"),
            font=Fonts.title(16),
            text_color=ThemeManager.primary()
        )
        self.lbl_title.pack(side="left")

        self.lbl_sub = ctk.CTkLabel(
            self.hdr,
            text=tr("Ambil token session web AI via Browser Profil atau Login Interaktif Otomatis"),
            font=Fonts.regular(11),
            text_color=ThemeManager.text_muted()
        )
        self.lbl_sub.pack(side="left", padx=(12, 0), pady=(3, 0))

        # Card 1: Interactive Login & Auto-Capture (OAuth-like)
        self.card_interactive = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.card_interactive.pack(fill="x", padx=16, pady=4)

        f_inter_hdr = ctk.CTkFrame(self.card_interactive, fg_color=ThemeManager.surface())
        f_inter_hdr.pack(fill="x", padx=14, pady=(10, 6))

        ctk.CTkLabel(
            f_inter_hdr,
            text=tr("🌐 Mode 1: Login Interaktif via Browser (Auto-Capture)"),
            font=Fonts.bold(13),
            text_color=ThemeManager.text()
        ).pack(side="left")

        ctk.CTkLabel(
            f_inter_hdr,
            text=tr("Buka browser popup, kamu cukup login, Netools otomatis menangkap token & menutup browser."),
            font=Fonts.regular(11),
            text_color=ThemeManager.text_muted()
        ).pack(side="left", padx=(10, 0))

        # Controls Row
        f_ctrl = ctk.CTkFrame(self.card_interactive, fg_color=ThemeManager.surface())
        f_ctrl.pack(fill="x", padx=14, pady=(4, 10))

        # Browser Picker
        ctk.CTkLabel(f_ctrl, text=tr("Browser:"), font=Fonts.bold(11), text_color=ThemeManager.text()).pack(side="left", padx=(0, 4))
        self.cbo_browser = ctk.CTkComboBox(
            f_ctrl,
            width=110,
            height=32,
            font=Fonts.regular(11),
            state="readonly",
            values=["Brave", "Chrome", "Firefox"]
        )
        self.cbo_browser.set("Brave" if find_browser_executable("Brave") else "Firefox")
        self.cbo_browser.pack(side="left", padx=(0, 12))

        # Provider Picker
        ctk.CTkLabel(f_ctrl, text=tr("Target AI:"), font=Fonts.bold(11), text_color=ThemeManager.text()).pack(side="left", padx=(0, 4))
        prov_labels = [label for k, label in SUPPORTED_PROVIDERS if k != "all"]
        self.cbo_prov = ctk.CTkComboBox(
            f_ctrl,
            width=180,
            height=32,
            font=Fonts.regular(11),
            state="readonly",
            values=prov_labels,
            command=self._on_prov_selected
        )
        self.cbo_prov.set(prov_labels[0])
        self.cbo_prov.pack(side="left", padx=(0, 10))

        # Target URL Entry
        self.entry_url = ctk.CTkEntry(
            f_ctrl,
            width=220,
            height=32,
            font=Fonts.mono(11),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            text_color=ThemeManager.text()
        )
        self.entry_url.insert(0, PROVIDER_URLS.get("zai-web", "https://chat.z.ai/"))
        self.entry_url.pack(side="left", padx=(0, 12))

        # Launch & Capture Button
        self.btn_launch = ctk.CTkButton(
            f_ctrl,
            text=tr("🌐 Buka & Tangkap"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.primary(),
            text_color="#FFFFFF",
            hover_color=ThemeManager.secondary(),
            width=130,
            height=32,
            command=self._start_browser_login
        )
        self.btn_launch.pack(side="left", padx=(0, 6))

        # Quick Scan Saved Profile Button
        self.btn_scan = ctk.CTkButton(
            f_ctrl,
            text=tr("🔍 Pindai Tersimpan"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            width=120,
            height=32,
            command=self._scan_existing_sessions
        )
        self.btn_scan.pack(side="left")

        # Live Status bar in Card 1
        self.lbl_capture_status = ctk.CTkLabel(
            self.card_interactive,
            text=tr("● Siap membuka browser atau memindai profil."),
            font=Fonts.bold(11),
            text_color=ThemeManager.accent(),
            anchor="w"
        )
        self.lbl_capture_status.pack(fill="x", padx=14, pady=(0, 10))

        # Card 2: Detected Sessions & Token Management
        self.card_tokens = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        self.card_tokens.pack(fill="both", expand=True, padx=16, pady=8)

        f_tok_hdr = ctk.CTkFrame(self.card_tokens, fg_color=ThemeManager.surface())
        f_tok_hdr.pack(fill="x", padx=14, pady=(10, 6))

        ctk.CTkLabel(
            f_tok_hdr,
            text=tr("📋 Sesi Akun Terdeteksi:"),
            font=Fonts.bold(13),
            text_color=ThemeManager.text()
        ).pack(side="left", padx=(0, 8))

        self.cbo_sessions = ctk.CTkComboBox(
            f_tok_hdr,
            width=460,
            height=32,
            font=Fonts.regular(11),
            state="readonly",
            values=["Sedang memindai..."],
            command=self._on_session_chosen
        )
        self.cbo_sessions.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Token Textbox
        self.txt_token = ctk.CTkTextbox(
            self.card_tokens,
            font=Fonts.mono(11),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            border_width=1,
            text_color=ThemeManager.text()
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
            command=self._copy_token
        )
        self.btn_copy.pack(side="left", padx=(0, 10))

        self.btn_inject = ctk.CTkButton(
            f_act,
            text=tr("🚀 Pasang Otomatis ke OmniRoute"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.secondary(),
            text_color="#FFFFFF",
            hover_color=ThemeManager.surface_alt(),
            height=36,
            command=self._inject_to_omniroute
        )
        self.btn_inject.pack(side="left", padx=(0, 10))

    def _on_prov_selected(self, choice):
        for k, lbl in SUPPORTED_PROVIDERS:
            if lbl == choice:
                url = PROVIDER_URLS.get(k, "")
                if url:
                    self.entry_url.delete(0, "end")
                    self.entry_url.insert(0, url)
                break

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
            text=tr(f"⏳ Meluncurkan {b_name}... Silakan login pada jendela popup yang terbuka."),
            text_color=ThemeManager.warning()
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
            on_status=_on_status
        )

        ok = self.active_login_session.start()
        if not ok:
            self.btn_launch.configure(state="normal")

    def _handle_capture_success(self, s):
        self.btn_launch.configure(state="normal")
        self.lbl_capture_status.configure(
            text=tr(f"✓ BERHASIL! Token {s['provider']} ({s['account']}) berhasil ditangkap."),
            text_color=ThemeManager.success()
        )
        self.main_app.show_toast(tr(f"✓ Token login {s['provider']} berhasil ditangkap otomatis!"), level="success")
        self._scan_existing_sessions()

    def _scan_existing_sessions(self):
        self.lbl_capture_status.configure(text=tr("Memindai sesi tersimpan..."), text_color=ThemeManager.text_muted())

        def _bg():
            sessions = extract_all_browser_sessions(browser_filter="all", provider_filter="all")
            self.after(0, lambda: self._display_sessions(sessions))

        threading.Thread(target=_bg, daemon=True).start()

    def _display_sessions(self, sessions):
        self.sessions = sessions
        if not sessions:
            self.cbo_sessions.configure(values=["(Tidak ada sesi tersimpan ditemukan)"])
            self.cbo_sessions.set("(Tidak ada sesi tersimpan ditemukan)")
            self.txt_token.delete("1.0", "end")
            self.selected_session = None
            self.lbl_capture_status.configure(text=tr("ℹ️ Belum ada sesi tersimpan. Klik 'Buka & Tangkap' untuk login."), text_color=ThemeManager.text_muted())
            return

        opts = [it["label"] for it in sessions]
        self.cbo_sessions.configure(values=opts)
        self.cbo_sessions.set(opts[0])
        self._on_session_chosen(opts[0])
        self.lbl_capture_status.configure(text=tr(f"✓ Ditemukan {len(sessions)} sesi login aktif di browser."), text_color=ThemeManager.success())

    def _on_session_chosen(self, choice):
        for it in self.sessions:
            if it["label"] == choice:
                self.selected_session = it
                self.txt_token.delete("1.0", "end")
                self.txt_token.insert("1.0", it["token"])
                break

    def _copy_token(self):
        tok = self.txt_token.get("1.0", "end").strip()
        if not tok:
            self.main_app.show_toast(tr("Token kosong!"), level="warning")
            return
        self.clipboard_clear()
        self.clipboard_append(tok)
        self.main_app.show_toast(tr("✓ Token berhasil disalin ke Clipboard!"), level="success")

    def _inject_to_omniroute(self):
        if not self.selected_session:
            self.main_app.show_toast(tr("Pilih akun terlebih dahulu!"), level="warning")
            return

        it = self.selected_session
        prov = it["provider"]
        tok = it["token"]
        name = it["account"]

        import sqlite3, time, uuid
        from pathlib import Path

        db_path = Path.home() / ".omniroute/storage.sqlite"
        if not db_path.exists():
            self.main_app.show_toast(tr("Database OmniRoute tidak ditemukan!"), level="error")
            return

        try:
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute("SELECT id FROM provider_connections WHERE provider=?", (prov,))
            row = cur.fetchone()
            now = time.strftime("%Y-%m-%d %H:%M:%S")

            if row:
                conn_id = row[0]
                cur.execute(
                    "UPDATE provider_connections SET api_key=?, is_active=1, last_error=NULL, error_code=NULL, backoff_level=0, updated_at=? WHERE id=?",
                    (tok, now, conn_id)
                )
            else:
                conn_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO provider_connections (id, provider, auth_type, name, is_active, api_key, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?, ?)",
                    (conn_id, prov, "apikey", name, tok, now, now)
                )

            con.commit()
            con.close()
            self.main_app.show_toast(tr(f"✓ Berhasil memasang {prov} ({name}) ke OmniRoute!"), level="success")
        except Exception as e:
            self.main_app.show_toast(tr(f"Gagal menginjeksi ke OmniRoute: {e}"), level="error")
