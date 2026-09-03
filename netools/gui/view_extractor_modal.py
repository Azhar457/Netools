"""
AI Session & Web Token Extractor Modal (CustomTkinter).
With granular Browser & Provider filters, Custom URL/Domain search, and explicit Close buttons.
"""

import threading
import customtkinter as ctk

from netools.gui.i18n import tr
from netools.gui.theme import Fonts, ThemeManager
from netools.gui.wm import mark_dialog
from netools.services.session_extractor import (
    SUPPORTED_PROVIDERS,
    extract_all_browser_sessions,
)


class SessionExtractorModal(ctk.CTkToplevel):
    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.parent_app = parent_app

        self.title(tr("🍪 Browser AI Session & Token Extractor"))
        self.geometry("760x580")
        self.minsize(680, 480)
        self.configure(fg_color=ThemeManager.bg())

        self.sessions = []
        self.selected_session = None

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        mark_dialog(self, parent_app)
        self._build_ui()
        self.after(100, self._scan_browser_sessions)

    def on_close(self):
        try:
            if hasattr(self.parent_app, "extractor_modal") and self.parent_app.extractor_modal == self:
                self.parent_app.extractor_modal = None
        except Exception:
            pass
        self.destroy()

    def _build_ui(self):
        # Header banner
        hdr = ctk.CTkFrame(self, fg_color=ThemeManager.surface_alt(), height=52)
        hdr.pack(fill="x", padx=0, pady=0)
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text=tr("🍪 Browser AI Session Extractor"),
            font=Fonts.title(15),
            text_color=ThemeManager.primary()
        ).pack(side="left", padx=20, pady=12)

        # Header Right Controls: Rescan & Close
        btn_close_top = ctk.CTkButton(
            hdr,
            text="✕ " + tr("Tutup"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface(),
            width=85,
            height=30,
            command=self.on_close
        )
        btn_close_top.pack(side="right", padx=(6, 16), pady=11)

        self.btn_rescan = ctk.CTkButton(
            hdr,
            text="🔄 " + tr("Pindai"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.primary(),
            text_color="#FFFFFF",
            hover_color=ThemeManager.secondary(),
            width=90,
            height=30,
            command=self._scan_browser_sessions
        )
        self.btn_rescan.pack(side="right", padx=6, pady=11)

        # Body container
        self.body = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        self.body.pack(fill="both", expand=True, padx=20, pady=14)

        # Filter Section Card
        card_filter = ctk.CTkFrame(self.body, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        card_filter.pack(fill="x", pady=(0, 10))

        f_filter_row = ctk.CTkFrame(card_filter, fg_color=ThemeManager.surface())
        f_filter_row.pack(fill="x", padx=14, pady=10)

        # Filter 1: Browser
        ctk.CTkLabel(f_filter_row, text=tr("Browser:"), font=Fonts.bold(11), text_color=ThemeManager.text()).pack(side="left", padx=(0, 6))
        self.cbo_browser = ctk.CTkComboBox(
            f_filter_row,
            width=140,
            height=30,
            font=Fonts.regular(11),
            state="readonly",
            values=["Semua Browser", "Brave", "Chrome", "Firefox"],
            command=lambda _: self._scan_browser_sessions()
        )
        self.cbo_browser.set("Semua Browser")
        self.cbo_browser.pack(side="left", padx=(0, 14))

        # Filter 2: Target Provider
        ctk.CTkLabel(f_filter_row, text=tr("Target AI:"), font=Fonts.bold(11), text_color=ThemeManager.text()).pack(side="left", padx=(0, 6))
        prov_labels = [label for _, label in SUPPORTED_PROVIDERS]
        self.cbo_provider = ctk.CTkComboBox(
            f_filter_row,
            width=190,
            height=30,
            font=Fonts.regular(11),
            state="readonly",
            values=prov_labels,
            command=self._on_provider_filter_changed
        )
        self.cbo_provider.set(prov_labels[0])
        self.cbo_provider.pack(side="left", padx=(0, 14))

        # Filter 3: Custom Keyword (if chosen)
        self.entry_custom = ctk.CTkEntry(
            f_filter_row,
            width=160,
            height=30,
            font=Fonts.regular(11),
            placeholder_text="Domain / Kata Kunci...",
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            text_color=ThemeManager.text()
        )

        # Info Status Text
        self.lbl_info = ctk.CTkLabel(
            self.body,
            text=tr("Pilih filter browser & provider di atas, lalu klik Pindai..."),
            font=Fonts.regular(11),
            text_color=ThemeManager.text_muted(),
            anchor="w"
        )
        self.lbl_info.pack(fill="x", pady=(2, 6))

        # Account Selection Card
        f_sel = ctk.CTkFrame(self.body, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        f_sel.pack(fill="x", pady=(0, 10))

        f_sel_inner = ctk.CTkFrame(f_sel, fg_color=ThemeManager.surface())
        f_sel_inner.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(f_sel_inner, text=tr("Sesi Ditemukan:"), font=Fonts.bold(12), text_color=ThemeManager.text()).pack(side="left", padx=(0, 10))

        self.cbo_sessions = ctk.CTkComboBox(
            f_sel_inner,
            width=460,
            height=34,
            font=Fonts.regular(12),
            state="readonly",
            values=["Sedang memindai browser..."],
            command=self._on_session_picked
        )
        self.cbo_sessions.pack(side="left", fill="x", expand=True, padx=4)

        # Token text display
        ctk.CTkLabel(self.body, text=tr("Token Credential (JWT / Session Cookie):"), font=Fonts.bold(12), text_color=ThemeManager.text(), anchor="w").pack(fill="x", pady=(2, 4))

        self.txt_token = ctk.CTkTextbox(
            self.body,
            height=120,
            font=Fonts.mono(11),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            border_width=1,
            text_color=ThemeManager.text()
        )
        self.txt_token.pack(fill="both", expand=True, pady=(0, 10))

        # Bottom Actions Bar
        f_actions = ctk.CTkFrame(self.body, fg_color=ThemeManager.bg())
        f_actions.pack(fill="x", pady=(0, 0))

        self.btn_copy = ctk.CTkButton(
            f_actions,
            text=tr("📋 Salin Token ke Clipboard"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.primary(),
            text_color="#FFFFFF",
            hover_color=ThemeManager.secondary(),
            height=36,
            command=self._copy_to_clipboard
        )
        self.btn_copy.pack(side="left", padx=(0, 10))

        self.btn_inject = ctk.CTkButton(
            f_actions,
            text=tr("🚀 Pasang Otomatis ke OmniRoute"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.secondary(),
            text_color="#FFFFFF",
            hover_color=ThemeManager.surface_alt(),
            height=36,
            command=self._inject_to_omniroute
        )
        self.btn_inject.pack(side="left", padx=(0, 10))

        btn_close_bottom = ctk.CTkButton(
            f_actions,
            text=tr("Tutup"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            height=36,
            width=90,
            command=self.on_close
        )
        btn_close_bottom.pack(side="right")

    def _on_provider_filter_changed(self, choice):
        if "Kustom" in choice:
            self.entry_custom.pack(side="left", padx=4)
        else:
            self.entry_custom.pack_forget()
        self._scan_browser_sessions()

    def _get_filter_keys(self):
        b_val = self.cbo_browser.get()
        b_key = "all" if "Semua" in b_val else b_val

        p_val = self.cbo_provider.get()
        p_key = "all"
        for k, lbl in SUPPORTED_PROVIDERS:
            if lbl == p_val:
                p_key = k
                break
        custom_kw = self.entry_custom.get().strip() if p_key == "custom" else ""
        return b_key, p_key, custom_kw

    def _scan_browser_sessions(self):
        b_key, p_key, custom_kw = self._get_filter_keys()
        self.lbl_info.configure(text=tr("Memindai profil browser..."))

        def _worker():
            sessions = extract_all_browser_sessions(
                browser_filter=b_key,
                provider_filter=p_key,
                custom_keyword=custom_kw
            )
            self.after(0, lambda s=sessions: self._populate_sessions(s))
        threading.Thread(target=_worker, daemon=True).start()

    def _populate_sessions(self, sessions):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        self.sessions = sessions
        if not sessions:
            self.lbl_info.configure(text=tr("❌ Tidak ditemukan sesi aktif untuk filter yang dipilih."))
            self.cbo_sessions.configure(values=["(Tidak ada sesi ditemukan)"])
            self.cbo_sessions.set("(Tidak ada sesi ditemukan)")
            self.txt_token.delete("1.0", "end")
            self.selected_session = None
            return

        opts = [it["label"] for it in sessions]
        self.cbo_sessions.configure(values=opts)
        self.cbo_sessions.set(opts[0])
        self._on_session_picked(opts[0])
        self.lbl_info.configure(text=tr(f"✓ Ditemukan {len(sessions)} sesi aktif:"))

    def _on_session_picked(self, choice):
        for idx, it in enumerate(self.sessions):
            if it["label"] == choice:
                self.selected_session = it
                self.txt_token.delete("1.0", "end")
                self.txt_token.insert("1.0", it["token"])
                break

    def _copy_to_clipboard(self):
        tok = self.txt_token.get("1.0", "end").strip()
        if not tok:
            self.parent_app.show_toast(tr("Token kosong!"), level="warning")
            return
        self.clipboard_clear()
        self.clipboard_append(tok)
        self.parent_app.show_toast(tr("✓ Token berhasil disalin ke Clipboard!"), level="success")

    def _inject_to_omniroute(self):
        if not self.selected_session:
            self.parent_app.show_toast(tr("Pilih sesi akun terlebih dahulu!"), level="warning")
            return

        it = self.selected_session
        prov = it["provider"]
        tok = it["token"]
        name = it["account"]

        # Directly update or insert connection into OmniRoute storage
        import sqlite3, time, uuid
        from pathlib import Path

        db_path = Path.home() / ".omniroute/storage.sqlite"
        if not db_path.exists():
            self.parent_app.show_toast(tr("Database OmniRoute tidak ditemukan!"), level="error")
            return

        try:
            con = sqlite3.connect(db_path)
            cur = con.cursor()

            # Check if connection for this provider exists
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
            self.parent_app.show_toast(tr(f"✓ Berhasil memasang {prov} ({name}) ke OmniRoute!"), level="success")
        except Exception as e:
            self.parent_app.show_toast(tr(f"Gagal menginjeksi ke OmniRoute: {e}"), level="error")
