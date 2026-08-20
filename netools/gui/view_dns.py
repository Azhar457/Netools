"""
Tab 2: DNS Jumper, 3-Tier Switcher & Fast Benchmarker View (CustomTkinter).
"""

import customtkinter as ctk
import threading
from netools.adapters import platform_dns as sys_dns
from netools.services import dns_service
from netools.gui.view_benchmark_modal import GRCBenchmarkModal
from netools.gui.theme import Fonts, COLOR_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_ACCENT_BLUE, COLOR_ACCENT_GREEN, COLOR_ACCENT_PURPLE, COLOR_ACCENT_YELLOW
import dns_jumper_db as db

class DNSView(ctk.CTkScrollableFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color="#181825", corner_radius=0)
        self.main_app = main_app
        self.providers = db.load_providers()
        self.interfaces = sys_dns.get_network_interfaces()
        self.active_interface = self.interfaces[0]["device"] if self.interfaces else "default"
        self._build_ui()

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="#181825")
        hdr.pack(fill="x", padx=16, pady=(12, 10))

        ctk.CTkLabel(
            hdr,
            text="⚡ Smart DNS Switcher & Latency Profiler",
            font=Fonts.title(15),
            text_color=COLOR_ACCENT_YELLOW
        ).pack(side="left")

        # Network Adapter Selector Card
        card_iface = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        card_iface.pack(fill="x", padx=16, pady=4)

        f1 = ctk.CTkFrame(card_iface, fg_color=COLOR_CARD)
        f1.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(
            f1,
            text="Network Interface:",
            font=Fonts.bold(11),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left", padx=(0, 8))

        iface_labels = [i["label"] for i in self.interfaces] if self.interfaces else ["Default"]
        self.iface_var = ctk.StringVar(value=iface_labels[0])
        self.iface_cb = ctk.CTkComboBox(
            f1,
            variable=self.iface_var,
            values=iface_labels,
            state="readonly",
            font=Fonts.regular(11),
            width=260,
            dropdown_font=Fonts.regular(11)
        )
        self.iface_cb.pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkButton(
            f1,
            text="🔄 Refresh Adapters",
            font=Fonts.bold(11),
            fg_color="#313244",
            text_color=COLOR_TEXT_PRIMARY,
            hover_color="#45475a",
            height=30,
            command=self.refresh_adapters
        ).pack(side="left", padx=4)

        # Preset Provider Selector Card
        card_preset = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        card_preset.pack(fill="x", padx=16, pady=4)

        f2 = ctk.CTkFrame(card_preset, fg_color=COLOR_CARD)
        f2.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(
            f2,
            text="Choose DNS Preset :",
            font=Fonts.bold(11),
            text_color=COLOR_ACCENT_BLUE
        ).pack(side="left", padx=(0, 8))

        self.preset_var = ctk.StringVar(value="⚙️ Custom DNS Servers")
        preset_labels = [f"{p['country']} {p['name']}" for p in self.providers.values()]
        preset_labels.insert(0, "⚙️ Custom DNS Servers")
        self.preset_cb = ctk.CTkComboBox(
            f2,
            variable=self.preset_var,
            values=preset_labels,
            state="readonly",
            font=Fonts.regular(11),
            width=260,
            dropdown_font=Fonts.regular(11),
            command=self.on_preset_change
        )
        self.preset_cb.pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkLabel(
            f2,
            text="Protocol / IP:",
            font=Fonts.bold(11),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left", padx=(10, 6))

        self.ip_family_var = ctk.StringVar(value="IPv4 (Standard)")
        self.ip_family_cb = ctk.CTkComboBox(
            f2,
            variable=self.ip_family_var,
            values=["IPv4 (Standard)", "IPv6 (Next-Gen)", "DoH (HTTPS)", "DoT (TLS Port 853)"],
            state="readonly",
            font=Fonts.regular(11),
            width=160,
            dropdown_font=Fonts.regular(11),
            command=lambda _: self.on_preset_change(self.preset_var.get())
        )
        self.ip_family_cb.pack(side="left", padx=4)

        # 3-Slots Card
        slots_card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        slots_card.pack(fill="x", padx=16, pady=6)

        # Slot 1
        s1 = ctk.CTkFrame(slots_card, fg_color=COLOR_CARD)
        s1.pack(fill="x", pady=4, padx=14)
        ctk.CTkLabel(s1, text="DNS 1 (Primary)   :", font=Fonts.bold(11), width=130, anchor="w", text_color=COLOR_TEXT_PRIMARY).pack(side="left")
        self.dns1_entry = ctk.CTkEntry(s1, width=200, height=30, font=Fonts.mono(11), fg_color="#11111b", border_color="#45475a")
        self.dns1_entry.insert(0, "1.1.1.1")
        self.dns1_entry.pack(side="left", padx=4)

        self.btn_ping1 = ctk.CTkButton(s1, text="Ping", width=60, height=28, font=Fonts.bold(10), fg_color="#313244", hover_color="#45475a", command=lambda: self.ping_slot(1))
        self.btn_ping1.pack(side="left", padx=4)
        self.lbl_ping1 = ctk.CTkLabel(s1, text="", font=Fonts.bold(11), text_color=COLOR_ACCENT_GREEN)
        self.lbl_ping1.pack(side="left", padx=6)

        # Slot 2
        s2 = ctk.CTkFrame(slots_card, fg_color=COLOR_CARD)
        s2.pack(fill="x", pady=4, padx=14)
        ctk.CTkLabel(s2, text="DNS 2 (Secondary) :", font=Fonts.bold(11), width=130, anchor="w", text_color=COLOR_TEXT_PRIMARY).pack(side="left")
        self.dns2_entry = ctk.CTkEntry(s2, width=200, height=30, font=Fonts.mono(11), fg_color="#11111b", border_color="#45475a")
        self.dns2_entry.insert(0, "1.0.0.1")
        self.dns2_entry.pack(side="left", padx=4)

        self.btn_ping2 = ctk.CTkButton(s2, text="Ping", width=60, height=28, font=Fonts.bold(10), fg_color="#313244", hover_color="#45475a", command=lambda: self.ping_slot(2))
        self.btn_ping2.pack(side="left", padx=4)
        self.lbl_ping2 = ctk.CTkLabel(s2, text="", font=Fonts.bold(11), text_color=COLOR_ACCENT_GREEN)
        self.lbl_ping2.pack(side="left", padx=6)

        # Slot 3
        s3 = ctk.CTkFrame(slots_card, fg_color=COLOR_CARD)
        s3.pack(fill="x", pady=4, padx=14)
        ctk.CTkLabel(s3, text="DNS 3 (Tertiary)  :", font=Fonts.bold(11), width=130, anchor="w", text_color=COLOR_TEXT_PRIMARY).pack(side="left")
        self.dns3_entry = ctk.CTkEntry(s3, width=200, height=30, font=Fonts.mono(11), fg_color="#11111b", border_color="#45475a")
        self.dns3_entry.pack(side="left", padx=4)

        self.btn_ping3 = ctk.CTkButton(s3, text="Ping", width=60, height=28, font=Fonts.bold(10), fg_color="#313244", hover_color="#45475a", command=lambda: self.ping_slot(3))
        self.btn_ping3.pack(side="left", padx=4)
        self.lbl_ping3 = ctk.CTkLabel(s3, text="", font=Fonts.bold(11), text_color=COLOR_ACCENT_GREEN)
        self.lbl_ping3.pack(side="left", padx=6)

        # Options Row
        opt_card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        opt_card.pack(fill="x", padx=16, pady=4)

        opts = ctk.CTkFrame(opt_card, fg_color=COLOR_CARD)
        opts.pack(fill="x", padx=14, pady=8)

        self.dot_var = ctk.BooleanVar(value=False)
        self.dot_chk = ctk.CTkCheckBox(
            opts,
            text="Enable DNS-over-TLS (DoT / Opportunistic)",
            variable=self.dot_var,
            font=Fonts.regular(11),
            text_color=COLOR_TEXT_PRIMARY,
            fg_color=COLOR_ACCENT_BLUE
        )
        self.dot_chk.pack(side="left", padx=4)

        self.persist_var = ctk.BooleanVar(value=True)
        self.persist_chk = ctk.CTkCheckBox(
            opts,
            text="Persist across Network Reconnects",
            variable=self.persist_var,
            font=Fonts.regular(11),
            text_color=COLOR_TEXT_PRIMARY,
            fg_color=COLOR_ACCENT_BLUE
        )
        self.persist_chk.pack(side="left", padx=16)

        # Action Buttons Row
        actions = ctk.CTkFrame(self, fg_color="#181825")
        actions.pack(fill="x", padx=16, pady=10)

        ctk.CTkButton(
            actions,
            text="⚡ Apply DNS",
            font=Fonts.bold(11),
            fg_color=COLOR_ACCENT_GREEN,
            text_color="#11111b",
            hover_color="#94e2d5",
            height=34,
            command=self.apply_dns
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            actions,
            text="♻️ Flush DNS",
            font=Fonts.bold(11),
            fg_color="#313244",
            text_color=COLOR_TEXT_PRIMARY,
            hover_color="#45475a",
            height=34,
            command=self.flush_dns
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            actions,
            text="↩️ Restore DHCP",
            font=Fonts.bold(11),
            fg_color="#45475a",
            text_color="#f38ba8",
            hover_color="#585b70",
            height=34,
            command=self.restore_dhcp
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            actions,
            text="🏆 Fastest DNS Benchmark (GRC Engine)",
            font=Fonts.bold(11),
            fg_color=COLOR_ACCENT_YELLOW,
            text_color="#11111b",
            hover_color="#f5e0dc",
            height=34,
            command=self.open_benchmark
        ).pack(side="right", padx=(6, 0))

    def on_preset_change(self, choice: str):
        if "Custom" in choice:
            return
        family = self.ip_family_var.get() if hasattr(self, "ip_family_var") else "IPv4 (Standard)"
        # Find provider
        for p in self.providers.values():
            label = f"{p['country']} {p['name']}"
            if label == choice:
                self.dns1_entry.delete(0, "end")
                self.dns2_entry.delete(0, "end")
                self.dns3_entry.delete(0, "end")

                if "IPv6" in family:
                    ips = p.get("ipv6", [])
                    if not ips:
                        self.main_app.show_toast(f"Provider '{p['name']}' tidak menyediakan DNS IPv6 publik.", level="warning")
                        ips = p.get("ipv4", [])
                elif "DoH" in family:
                    doh = p.get("doh_url", "")
                    ips = [doh] if doh else p.get("ipv4", [])
                elif "DoT" in family:
                    dot = p.get("dot_host") or (p.get("ipv4", [])[0] if p.get("ipv4") else "")
                    ips = [dot] if dot else p.get("ipv4", [])
                else:
                    ips = p.get("ipv4", [])

                if len(ips) > 0: self.dns1_entry.insert(0, ips[0])
                if len(ips) > 1: self.dns2_entry.insert(0, ips[1])
                if len(ips) > 2: self.dns3_entry.insert(0, ips[2])
                break

    def refresh_adapters(self):
        self.interfaces = sys_dns.get_network_interfaces()
        labels = [i["label"] for i in self.interfaces] if self.interfaces else ["Default"]
        self.iface_cb.configure(values=labels)
        if labels:
            self.iface_var.set(labels[0])
            self.active_interface = self.interfaces[0]["device"] if self.interfaces else "default"
        self.main_app.show_toast(f"✓ {len(self.interfaces)} Network Adapters refreshed.", level="info")

    def ping_slot(self, slot_num: int):
        entry = [self.dns1_entry, self.dns2_entry, self.dns3_entry][slot_num - 1]
        lbl = [self.lbl_ping1, self.lbl_ping2, self.lbl_ping3][slot_num - 1]
        ip = entry.get().strip()
        if not ip:
            return
        lbl.configure(text="Pinging...", text_color="#cdd6f4")
        def _bg():
            from netools.libs.net import ping_ip
            lat = ping_ip(ip, timeout=1.5)
            try:
                self.after(0, lambda: lbl.configure(
                    text=f"{lat:.1f} ms" if lat else "Timeout",
                    text_color=COLOR_ACCENT_GREEN if lat else "#f38ba8"
                ))
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def apply_dns(self):
        ips = [self.dns1_entry.get().strip(), self.dns2_entry.get().strip(), self.dns3_entry.get().strip()]
        valid = [ip for ip in ips if ip]
        if not valid:
            self.main_app.show_toast("Isi minimal 1 IP DNS valid!", level="warning")
            return
        
        # Get active interface device
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
                dev,
                valid,
                connection_name=conn,
                enable_dot=self.dot_var.get(),
                persistent=self.persist_var.get()
            )
            try:
                if success:
                    self.after(0, lambda: self.main_app.show_toast(f"✓ DNS ({', '.join(valid)}) diterapkan ke '{dev}'!", level="success"))
                    self.after(0, self.main_app.dashboard_view.refresh)
                else:
                    self.after(0, lambda: self.main_app.show_toast(f"Gagal menerapkan DNS ke interface '{dev}'.", level="error"))
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def flush_dns(self):
        def _bg():
            sys_dns.flush_dns_cache()
            try:
                self.after(0, lambda: self.main_app.show_toast("✓ DNS Cache berhasil di-flush!", level="success"))
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
                self.after(0, lambda: self.main_app.show_toast(f"✓ Interface '{dev}' dikembalikan ke DHCP default.", level="info"))
                self.after(0, self.main_app.dashboard_view.refresh)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def refresh_presets(self):
        self.providers = db.load_providers()
        preset_labels = [f"{p['country']} {p['name']}" for p in self.providers.values()]
        preset_labels.insert(0, "⚙️ Custom DNS Servers")
        if hasattr(self, "preset_cb"):
            self.preset_cb.configure(values=preset_labels)

    def open_benchmark(self):
        modal = GRCBenchmarkModal(self.main_app, self)
        self.main_app.child_windows.append(modal)
