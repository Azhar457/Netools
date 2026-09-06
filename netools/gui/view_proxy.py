"""
Tab 3: Turbo Sing-box Proxy Pool Rotator & Watchdog View (CustomTkinter).
"""

import threading
from tkinter import ttk

import customtkinter as ctk

from netools.adapters import platform_proxy
from netools.config import HTTP_PORT_OFFSET, MAX_INSTANCES, SOCKS5_PORT_START

from netools.gui.i18n import tr
from netools.gui.theme import (
    Fonts,
    ThemeManager,
)
from netools.services import pac_service, proxy_service, watchdog_service
from netools.state import load_state


# Pool heatmap color + glyph mapping. See tests/test_pool_heatmap.py.
_HEATMAP_COLORS = {
    "alive": ("#10b981", "●"),                              # green dot
    "spawn_failed": ("#6b7280", "○"),                        # grey empty
    "upstream_probe_failed": ("#ef4444", "✕"),               # red x
    "probe_exception:TimeoutError": ("#ef4444", "✕"),
    "probe_exception:ConnectionRefusedError": ("#ef4444", "✕"),
    "probe_exception:ConnectionResetError": ("#ef4444", "✕"),
    "probe_exception:OSError": ("#ef4444", "✕"),
}


def _port_state_to_color(reason: str) -> tuple:
    """Return (hex_color, glyph) for the pool heatmap.

    Pure function so it can be unit-tested without a Tk root.
    """
    return _HEATMAP_COLORS.get(reason, ("#f59e0b", "?"))  # amber = unknown


class ProxyView(ctk.CTkFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color=ThemeManager.bg(), corner_radius=0)
        self.main_app = main_app
        self._build_ui()
        self.refresh()

    def apply_theme(self):
        self.configure(fg_color=ThemeManager.bg())
        if hasattr(self, "hdr"):
            self.hdr.configure(fg_color=ThemeManager.bg())
        if hasattr(self, "lbl_title"):
            self.lbl_title.configure(text_color=ThemeManager.success())
        if hasattr(self, "btn_refresh"):
            self.btn_refresh.configure(
                fg_color=ThemeManager.border(), text_color=ThemeManager.text(), hover_color=ThemeManager.surface_alt()
            )
        if hasattr(self, "btn_sys_proxy_toggle"):
            sys_status = platform_proxy.get_system_proxy_status()
            if not sys_status.get("enabled"):
                self.btn_sys_proxy_toggle.configure(
                    fg_color=ThemeManager.border(),
                    text_color=ThemeManager.text(),
                    hover_color=ThemeManager.surface_alt(),
                )
        if hasattr(self, "summary_card"):
            self.summary_card.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())

        if hasattr(self, "lbl_summary"):
            self.lbl_summary.configure(text_color=ThemeManager.text_muted())
        if hasattr(self, "tbl_frame"):
            self.tbl_frame.configure(fg_color=ThemeManager.surface(), border_color=ThemeManager.border())

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=ThemeManager.surface(),
            foreground=ThemeManager.text(),
            fieldbackground=ThemeManager.surface(),
        )
        style.configure("Treeview.Heading", background=ThemeManager.surface_alt(), foreground=ThemeManager.text())
        style.map("Treeview", background=[("selected", ThemeManager.border())])

    def _build_ui(self):
        # Header Controls
        self.hdr = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        self.hdr.pack(fill="x", padx=16, pady=(12, 8))

        self.lbl_title = ctk.CTkLabel(
            self.hdr,
            text=tr("🌐 Turbo Sing-box Proxy Rotator"),
            font=Fonts.title(16),
            text_color=ThemeManager.success(),
        )
        self.lbl_title.pack(side="left", padx=(0, 14))

        # Action Buttons
        self.btn_start = ctk.CTkButton(
            self.hdr,
            text=tr("🚀 Start Pool"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.success(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=36,
            command=self.on_start,
        )
        self.btn_start.pack(side="left", padx=4)

        self.btn_stop = ctk.CTkButton(
            self.hdr,
            text=tr("🛑 Stop Pool"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.danger(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.warning(),
            height=36,
            command=self.on_stop,
        )
        self.btn_stop.pack(side="left", padx=4)

        self.btn_refresh = ctk.CTkButton(
            self.hdr,
            text=tr("🔄 Refresh"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            height=36,
            command=self.on_refresh,
        )
        self.btn_refresh.pack(side="left", padx=4)

        self.watchdog_var = ctk.BooleanVar(value=False)
        self.chk_watchdog = ctk.CTkCheckBox(
            self.hdr,
            text=tr("Auto-Heal Watchdog"),
            variable=self.watchdog_var,
            font=Fonts.regular(12),
            text_color=ThemeManager.text(),
            fg_color=ThemeManager.success(),
            command=self.toggle_watchdog,
        )
        self.chk_watchdog.pack(side="left", padx=14)

        # System Proxy Toggle Button
        self.btn_sys_proxy_toggle = ctk.CTkButton(
            self.hdr,
            text=tr("⚡ OS Proxy: OFF"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.border(),
            text_color=ThemeManager.text(),
            hover_color=ThemeManager.surface_alt(),
            height=36,
            command=self.toggle_system_proxy,
        )
        self.btn_sys_proxy_toggle.pack(side="right", padx=(4, 0))

        # PAC Toggle Button
        self.btn_pac_toggle = ctk.CTkButton(
            self.hdr,
            text=tr("🟢 Start PAC"),
            font=Fonts.bold(12),
            fg_color=ThemeManager.primary(),
            text_color=ThemeManager.get("on_primary"),
            hover_color=ThemeManager.accent(),
            height=36,
            command=self.toggle_pac,
        )
        self.btn_pac_toggle.pack(side="right", padx=(4, 0))


        # Pool Heatmap: one cell per sing-box instance (up to MAX_INSTANCES).
        # Each cell shows the live state of that slot using the same color
        # palette as the diagnostic reasons (alive, spawn_failed, etc).
        self.heatmap_frame = ctk.CTkFrame(
            self, fg_color=ThemeManager.surface(), corner_radius=6,
            border_width=1, border_color=ThemeManager.border(),
        )
        self.heatmap_frame.pack(fill="x", padx=16, pady=(4, 0))
        self.heatmap_cells = []
        for i in range(MAX_INSTANCES):
            cell = ctk.CTkLabel(
                self.heatmap_frame, text="○", width=28, height=28,
                font=("Segoe UI Symbol", 14), text_color="#6b7280",
            )
            cell.grid(row=0, column=i, padx=2, pady=4)
            self.heatmap_cells.append(cell)

        # Status Summary Bar
        self.summary_card = ctk.CTkFrame(
            self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border()
        )
        self.summary_card.pack(fill="x", padx=16, pady=4)

        self.lbl_summary = ctk.CTkLabel(
            self.summary_card,
            text=tr("Instances: 0 active | SOCKS: 11080–11099 | HTTP: 21080–21099 | Upstream: gstatic 204"),
            font=Fonts.mono(12),
            text_color=ThemeManager.text_muted(),
        )
        self.lbl_summary.pack(padx=14, pady=8, anchor="w")

        # Treeview Table for Proxies
        self.tbl_frame = ctk.CTkFrame(
            self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border()
        )
        self.tbl_frame.pack(fill="both", expand=True, padx=16, pady=6)

        columns = ("slot", "protocol", "server", "socks", "http", "pool", "dns", "status", "age")
        self.tree = ttk.Treeview(self.tbl_frame, columns=columns, show="headings", selectmode="browse")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=ThemeManager.surface(),
            foreground=ThemeManager.text(),
            fieldbackground=ThemeManager.surface(),
            rowheight=26,
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
            ("slot", tr("Slot ID"), 80, "center"),
            ("protocol", tr("Protocol"), 110, "center"),
            ("server", tr("Upstream Node"), 200, "center"),
            ("socks", tr("SOCKS5 Port"), 110, "center"),
            ("http", tr("HTTP Port"), 110, "center"),
            ("pool", tr("Router Pool"), 130, "center"),
            ("dns", tr("DNS Engine"), 150, "center"),
            ("status", tr("Status"), 100, "center"),
            ("age", tr("Started At"), 160, "center"),
        ]

        self.sort_directions = {}
        for col_id, title, w, align in cols_config:
            self.tree.heading(col_id, text=f"{title} ↕", anchor=align, command=lambda c=col_id: self.sort_column(c))
            self.tree.column(col_id, width=w, minwidth=70, anchor=align, stretch=True)

        vsb = ttk.Scrollbar(self.tbl_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", padx=(0, 8), pady=8)

        # Instant initial sync render (0 ms delay)
        self._populate_sync()

    def sort_column(self, col: str):
        """Sort Proxy Treeview rows by clicking column headers."""
        reverse = self.sort_directions.get(col, False)
        self.sort_directions[col] = not reverse

        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

        def _val_key(v):
            if v is None:
                return (1, 999999.0, "")
            v_str = str(v).strip()
            clean = v_str.replace(" ms", "").replace("#", "").strip()
            if clean in ("", "—", "Timeout", "Failed", "Cutoff", "N/A", "null", "None"):
                return (1, 999999.0, v_str.lower())
            try:
                return (0, float(clean), "")
            except ValueError:
                return (2, 0.0, v_str.lower())

        items.sort(key=lambda t: _val_key(t[0]), reverse=reverse)

        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

    def _populate_sync(self):
        st = load_state()
        insts = st.get("instances", {})
        pac_running = pac_service.is_pac_server_running()

        for item in self.tree.get_children():
            self.tree.delete(item)

        for name, data in sorted(insts.items()):
            reason = data.get("reason", "alive")
            if reason != "alive":
                continue
            port = data.get("port", 11080)
            http_p = port + HTTP_PORT_OFFSET
            proto = data.get("proxy_type") or data.get("protocol") or "shadowsocks"
            srv = f"{data.get('server', '')}:{data.get('server_port', '')}"
            pool = data.get("pool_name") or data.get("pool_id") or "—"
            dns_engine = "SOCKS5h Remote"
            age = data.get("started_at", "Just now")
            status = "🟢 Alive"

            self.tree.insert("", "end", values=(name, proto, srv, port, http_p, pool, dns_engine, status, age))

        # Update heatmap cells: one per slot index
        for i in range(MAX_INSTANCES):
            slot_name = f"sb-{i:02d}"
            slot = insts.get(slot_name)
            reason = (slot or {}).get("reason", "spawn_failed")
            color, glyph = _port_state_to_color(reason)
            try:
                self.heatmap_cells[i].configure(text=glyph, text_color=color)
            except (IndexError, AttributeError):
                pass

        cnt = sum(1 for d in insts.values() if d.get("reason") == "alive")
        self.lbl_summary.configure(
            text=f"Instances: {cnt} active | SOCKS: {SOCKS5_PORT_START}–{SOCKS5_PORT_START + max(0, cnt - 1)} | HTTP: {SOCKS5_PORT_START + HTTP_PORT_OFFSET}–{SOCKS5_PORT_START + HTTP_PORT_OFFSET + max(0, cnt - 1)} | Upstream: gstatic 204"
        )

        if pac_running:
            self.btn_pac_toggle.configure(
                text=tr("🛑 Stop PAC"), fg_color=ThemeManager.danger(), hover_color=ThemeManager.warning()
            )
        else:
            self.btn_pac_toggle.configure(
                text=tr("🟢 Start PAC"), fg_color=ThemeManager.primary(), hover_color=ThemeManager.accent()
            )

        sys_status = platform_proxy.get_system_proxy_status()
        if sys_status.get("enabled"):
            self.btn_sys_proxy_toggle.configure(
                text=tr("⚡ OS Proxy: ON"),
                fg_color=ThemeManager.success(),
                hover_color=ThemeManager.accent(),
                text_color=ThemeManager.get("on_primary"),
            )
        else:
            self.btn_sys_proxy_toggle.configure(
                text=tr("⚡ OS Proxy: OFF"),
                fg_color=ThemeManager.border(),
                hover_color=ThemeManager.surface_alt(),
                text_color=ThemeManager.text(),
            )


    def refresh(self):
        try:
            self._populate_sync()
        except Exception:
            pass

    def on_start(self):
        self.main_app.show_toast(tr("Memulai Turbo Proxy Pool..."), level="info")

        def _bg():
            proxy_service.start_proxy_pool(max_instances=20, standalone=False)
            try:
                self.after(0, self.refresh)
                self.after(0, self.main_app.dashboard_view.refresh)
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def on_stop(self):
        self.main_app.show_toast(tr("Menghentikan seluruh instance Proxy..."), level="warning")

        def _bg():
            proxy_service.stop_proxy_pool()
            try:
                self.after(0, self.refresh)
                self.after(0, self.main_app.dashboard_view.refresh)
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def on_refresh(self):
        self.refresh()
        self.main_app.show_toast(tr("✓ Tabel proxy berhasil diperbarui."), level="info")

    def toggle_watchdog(self):
        if self.watchdog_var.get():
            watchdog_service.start_watchdog_thread(interval=15)
            self.main_app.show_toast(tr("✓ Auto-Heal Watchdog aktif (setiap 15s)!"), level="success")
        else:
            watchdog_service.stop_watchdog()
            self.main_app.show_toast(tr("Auto-Heal Watchdog dimatikan."), level="warning")

    def toggle_pac(self):
        if pac_service.is_pac_server_running():
            pac_service.stop_pac_server()
            self.main_app.show_toast(tr("PAC Server dihentikan."), level="warning")
            self.refresh()
        else:
            from netools.gui.dialog_pac import show_pac_confirmation

            def _start():
                pac_service.start_pac_server()
                self.main_app.show_toast(tr("✓ PAC Server aktif di http://127.0.0.1:18080/proxy.pac"), level="success")
                self.refresh()

            show_pac_confirmation(self, _start)

    def toggle_system_proxy(self):
        sys_status = platform_proxy.get_system_proxy_status()
        if sys_status.get("enabled"):
            platform_proxy.disable_system_proxy()
            self.main_app.show_toast(tr("System Proxy dinonaktifkan (kembali ke Direct)."), level="info")
        else:
            if not pac_service.is_pac_server_running():
                pac_service.start_pac_server()
            pac_url = pac_service.get_pac_url()
            ok = platform_proxy.enable_system_proxy(pac_url)
            if ok:
                self.main_app.show_toast(tr("✓ System Proxy aktif di seluruh OS (PAC & SOCKS5)!"), level="success")
            else:
                self.main_app.show_toast(tr("Gagal mengaktifkan System Proxy pada OS ini."), level="error")
        self.refresh()
        if hasattr(self.main_app, "dashboard_view"):
            self.main_app.dashboard_view.refresh()

