"""
Tab 4: 9Router Gateway & OmniRoute Settings View (CustomTkinter).
"""

import customtkinter as ctk
import threading
from netools.adapters import ninerouter as nr_adapt
from netools.adapters import omniroute as omni_adapt


class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color="#181825")
        self.main_app = main_app
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text="🔌 AI Gateway Integrations & Provider Mappings",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#89b4fa"
        ).pack(anchor="w", pady=(0, 10))

        # Status Card
        card = ctk.CTkFrame(
            self,
            fg_color="#1e1e2e",
            corner_radius=8,
            border_width=1,
            border_color="#313244"
        )
        card.pack(fill="x", pady=6)

        ctk.CTkLabel(
            card,
            text="9Router Status (http://localhost:20128)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#cdd6f4"
        ).pack(anchor="w", padx=14, pady=(12, 2))
        self.lbl_status = ctk.CTkLabel(
            card,
            text="Detecting...",
            font=ctk.CTkFont(size=9),
            text_color="#a6adc8"
        )
        self.lbl_status.pack(anchor="w", padx=14, pady=(0, 8))

        btn_f = ctk.CTkFrame(card, fg_color="#1e1e2e")
        btn_f.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkButton(
            btn_f,
            text="🧹 Safe Unlink All Pools",
            font=ctk.CTkFont(size=8, weight="bold"),
            fg_color="#f38ba8", text_color="#11111b",
            hover_color="#89b4fa",
            height=28,
            command=self.unlink_all
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            btn_f,
            text="🔄 Reload Connections",
            font=ctk.CTkFont(size=8),
            fg_color="#313244", text_color="#cdd6f4",
            hover_color="#45475a",
            height=28,
            command=self.refresh
        ).pack(side="left", padx=2)

        # Connection List Title
        ctk.CTkLabel(
            self,
            text="Active 9Router Provider Connections:",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#cdd6f4"
        ).pack(anchor="w", pady=(10, 4))

        # Connection Table Frame
        table_f = ctk.CTkFrame(self, fg_color="#181825")
        table_f.pack(fill="both", expand=True)

        # Table Header
        hdr = ctk.CTkFrame(table_f, fg_color="#181825")
        hdr.pack(fill="x", padx=4, pady=(4, 0))
        headers = ["Connection Name", "Provider", "Auth Type", "Proxy Enabled", "Assigned Proxy URL"]
        for h in headers:
            lbl = ctk.CTkLabel(hdr, text=h, font=ctk.CTkFont(size=9, weight="bold"), text_color="#a6adc8", fg_color="#313244", corner_radius=4)
            lbl.pack(side="left", fill="x", expand=True, padx=2, pady=2)

        # Scrollable Content
        self.table_content = ctk.CTkFrame(table_f, fg_color="#181825")
        self.table_content.pack(fill="both", expand=True, padx=4, pady=2)
        self.connection_rows = []

    def refresh(self):
        def _bg():
            is_9r = nr_adapt.is_healthy()
            conns = nr_adapt.get_connections() if is_9r else []
            try:
                self.after(0, lambda: self._apply_data(is_9r, conns))
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def _apply_data(self, is_9r, conns):
        self.lbl_status.configure(
            text="✓ Online (REST API Ready)" if is_9r else "❌ Offline (Not running on port 20128)",
            text_color="#a6e3a1" if is_9r else "#f38ba8"
        )
        # Clear rows
        for row in self.connection_rows:
            row.destroy()
        self.connection_rows.clear()

        for c in conns:
            spec = c.get("providerSpecificData") or {}
            proxy_enabled = "🟢 Yes" if spec.get("connectionProxyEnabled") else "⚪ No"
            proxy_url = spec.get("connectionProxyUrl") or c.get("connectionProxyUrl") or "-"
            row_f = ctk.CTkFrame(self.table_content, fg_color="#1e1e2e", corner_radius=4, border_width=1, border_color="#313244")
            row_f.pack(fill="x", pady=1, padx=2)
            vals = [
                c.get("name", "Unnamed"),
                c.get("provider", "-"),
                c.get("authType", "-"),
                proxy_enabled,
                proxy_url
            ]
            for val in vals:
                lbl = ctk.CTkLabel(
                    row_f,
                    text=str(val),
                    font=ctk.CTkFont(size=9),
                    text_color="#cdd6f4",
                    fg_color="#1e1e2e",
                    anchor="w"
                )
                lbl.pack(side="left", fill="x", expand=True, padx=3, pady=4)
            self.connection_rows.append(row_f)

    def unlink_all(self):
        def _run():
            cleared = nr_adapt.clear_all_connection_proxies()
            pools = nr_adapt.get_existing_pools()
            for p_name, p_id in pools.items():
                if p_name.startswith("free-proxy-"):
                    nr_adapt.delete_proxy_pool(p_id)
            try:
                self.after(0, lambda: self.main_app.show_toast(f"✓ Berhasil unbind dan menghapus {cleared} pool 9Router!", level="success"))
                self.after(0, self.refresh)
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()
