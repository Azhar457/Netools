"""
AI Session & Web Token Extractor Modal (CustomTkinter).
Automatically extracts tokens/cookies from Brave, Chrome, and Firefox for OmniRoute with 1-click apply.
"""

import threading
import customtkinter as ctk

from netools.gui.i18n import tr
from netools.gui.theme import Fonts, ThemeManager
from netools.gui.wm import mark_dialog
from netools.services.session_extractor import extract_all_browser_sessions


class SessionExtractorModal(ctk.CTkToplevel):
    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.parent_app = parent_app

        self.title(tr("🍪 Browser AI Session & Token Extractor (1-Click)"))
        self.geometry("720x520")
        self.minsize(640, 440)
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
        hdr = ctk.CTkFrame(self, fg_color=ThemeManager.surface_alt(), height=50)
        hdr.pack(fill="x", padx=0, pady=0)
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text=tr("🍪 Browser AI Session Extractor (Brave / Chrome / Firefox)"),
            font=Fonts.title(15),
            text_color=ThemeManager.primary()
        ).pack(side="left", padx=20, pady=12)

        self.btn_rescan = ctk.CTkButton(
            hdr,
            text=tr("🔄 Scan Ulang"),
            font=Fonts.bold(11),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface(),
            width=100,
            height=28,
            command=self._scan_browser_sessions
        )
        self.btn_rescan.pack(side="right", padx=16, pady=10)

        # Body container
        self.body = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        self.body.pack(fill="both", expand=True, padx=20, pady=16)

        # Instruction label
        self.lbl_info = ctk.CTkLabel(
            self.body,
            text=tr("Mendeteksi session login aktif dari browser di komputermu (tanpa perlu buka F12)..."),
            font=Fonts.regular(12),
            text_color=ThemeManager.text_muted(),
            anchor="w",
            justify="left"
        )
        self.lbl_info.pack(fill="x", pady=(0, 10))

        # Selection frame
        f_sel = ctk.CTkFrame(self.body, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        f_sel.pack(fill="x", pady=6, padx=0)

        f_sel_inner = ctk.CTkFrame(f_sel, fg_color=ThemeManager.surface())
        f_sel_inner.pack(fill="x", padx=14, pady=12)

        ctk.CTkLabel(f_sel_inner, text=tr("Akun Terdeteksi:"), font=Fonts.bold(12), text_color=ThemeManager.text()).pack(side="left", padx=(0, 10))

        self.cbo_sessions = ctk.CTkComboBox(
            f_sel_inner,
            width=420,
            height=34,
            font=Fonts.regular(12),
            state="readonly",
            values=["Sedang memindai browser..."],
            command=self._on_session_picked
        )
        self.cbo_sessions.pack(side="left", fill="x", expand=True, padx=4)

        # Token preview frame
        ctk.CTkLabel(self.body, text=tr("Token Credential yang Dihasilkan:"), font=Fonts.bold(12), text_color=ThemeManager.text(), anchor="w").pack(fill="x", pady=(12, 4))

        self.txt_token = ctk.CTkTextbox(
            self.body,
            height=130,
            font=Fonts.mono(11),
            fg_color=ThemeManager.surface_alt(),
            border_color=ThemeManager.border(),
            border_width=1,
            text_color=ThemeManager.text()
        )
        self.txt_token.pack(fill="both", expand=True, pady=(0, 12))

        # Action Buttons
        f_actions = ctk.CTkFrame(self.body, fg_color=ThemeManager.bg())
        f_actions.pack(fill="x", pady=(4, 0))

        self.btn_copy = ctk.CTkButton(
            f_actions,
            text=tr("📋 Salin Token ke Clipboard"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.primary(),
            text_color="#FFFFFF",
            hover_color=ThemeManager.primary_hover(),
            height=38,
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
            height=38,
            command=self._inject_to_omniroute
        )
        self.btn_inject.pack(side="left", padx=0)

    def _scan_browser_sessions(self):
        self.lbl_info.configure(text=tr("Memindai profile Brave, Chrome, dan Firefox..."))
        def _worker():
            sessions = extract_all_browser_sessions()
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
            self.lbl_info.configure(text=tr("❌ Tidak menemukan session AI aktif di Brave / Chrome / Firefox. Pastikan sudah login di web AI."))
            self.cbo_sessions.configure(values=["(Tidak ada session terdeteksi)"])
            self.cbo_sessions.set("(Tidak ada session terdeteksi)")
            self.txt_token.delete("1.0", "end")
            return

        opts = [f"[{it['browser']}] {it['provider']} — {it['account']}" for it in sessions]
        self.cbo_sessions.configure(values=opts)
        self.cbo_sessions.set(opts[0])
        self._on_session_picked(opts[0])
        self.lbl_info.configure(text=tr(f"✓ Ditemukan {len(sessions)} session AI di browser. Pilih akun di bawah:"))

    def _on_session_picked(self, choice):
        for idx, it in enumerate(self.sessions):
            opt = f"[{it['browser']}] {it['provider']} — {it['account']}"
            if opt == choice:
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
        self.parent_app.show_toast(tr("✓ Token berhasil disalin ke Clipboard! Tinggal Ctrl+V di OmniRoute."), level="success")

    def _inject_to_omniroute(self):
        if not self.selected_session:
            self.parent_app.show_toast(tr("Pilih akun terlebih dahulu!"), level="warning")
            return

        it = self.selected_session
        prov = it["provider"]
        tok = it["token"]
        name = it["account"]

        # Directly update or insert connection into OmniRoute storage
        import sqlite3, json, time, uuid
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
