"""
Tab 2: DNS Jumper, 3-Tier Switcher & Fast Benchmarker View (CustomTkinter).
"""

import customtkinter as ctk
import threading
from netools.adapters import platform_dns as sys_dns
from netools.services import dns_service
from netools.gui.view_benchmark_modal import GRCBenchmarkModal
from netools.gui.scrollable_dropdown import CTkScrollableDropdown
from netools.gui.theme import Fonts, COLOR_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_ACCENT_BLUE, COLOR_ACCENT_GREEN, COLOR_ACCENT_PURPLE, COLOR_ACCENT_YELLOW
from netools.libs import dns_db as db

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
            dropdown_font=Fonts.regular(11),
            command=self.on_interface_change
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
            text="Category:",
            font=Fonts.bold(11),
            text_color=COLOR_ACCENT_BLUE
        ).pack(side="left", padx=(0, 4))

        self.category_var = ctk.StringVar(value="📁 All Categories")
        self.category_cb = ctk.CTkComboBox(
            f2,
            variable=self.category_var,
            values=["📁 All Categories", "🛡️ Security & Privacy", "⚡ Gaming / Fast", "🚫 Ad-Blocking", "👨‍👩‍👧 Family Safe", "🌏 Asia-Pacific", "🌐 Global Anycast"],
            state="readonly",
            font=Fonts.regular(11),
            width=150,
            dropdown_font=Fonts.regular(11),
            command=self.on_category_filter_change
        )
        self.category_cb.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            f2,
            text="Preset:",
            font=Fonts.bold(11),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left", padx=(0, 4))

        self.preset_var = ctk.StringVar(value="⚙️ Custom DNS Servers")
        preset_labels = [f"{p['country']} {p['name']}" for p in self.providers.values()]
        preset_labels.insert(0, "⚙️ Custom DNS Servers")
        self.preset_cb = ctk.CTkComboBox(
            f2,
            variable=self.preset_var,
            values=preset_labels,
            state="readonly",
            font=Fonts.regular(11),
            width=220,
            dropdown_font=Fonts.regular(11),
            command=self.on_preset_change
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
            placeholder_text="🔍 Search 90+ DNS presets..."
        )

        ctk.CTkLabel(
            f2,
            text="Protocol / IP:",
            font=Fonts.bold(11),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left", padx=(8, 4))

        self.ip_family_var = ctk.StringVar(value="IPv4 (Standard)")
        self.ip_family_cb = ctk.CTkComboBox(
            f2,
            variable=self.ip_family_var,
            values=["IPv4 (Standard)", "IPv6 (Next-Gen)", "DoH (HTTPS)", "DoT (TLS Port 853)"],
            state="readonly",
            font=Fonts.regular(11),
            width=150,
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
            text="🔍 Verify DNS & DoH",
            font=Fonts.bold(11),
            fg_color="#313244",
            text_color=COLOR_ACCENT_BLUE,
            hover_color="#45475a",
            height=34,
            command=self.verify_dns_status
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

        # Auto-load active system DNS on startup
        self.load_active_interface_dns()

    def on_interface_change(self, choice: str):
        for i in self.interfaces:
            if i["label"] == choice:
                self.active_interface = i["device"]
                break
        self.load_active_interface_dns()

    def load_active_interface_dns(self, dev: str = None):
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
            
            # Check DoT state
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
                        if len(current_dns) > 0: self.dns1_entry.insert(0, current_dns[0])
                        if len(current_dns) > 1: self.dns2_entry.insert(0, current_dns[1])
                        if len(current_dns) > 2: self.dns3_entry.insert(0, current_dns[2])

                        # Match with known presets
                        matched = False
                        for p in self.providers.values():
                            p_ips = p.get("ipv4", [])
                            p_v6 = p.get("ipv6", [])
                            if (len(p_ips) > 0 and p_ips[0] == current_dns[0]) or (len(p_v6) > 0 and p_v6[0] == current_dns[0]):
                                self.preset_var.set(f"{p['country']} {p['name']}")
                                matched = True
                                break
                        if not matched:
                            self.preset_var.set("⚙️ Custom DNS Servers")

                        # Check IP family
                        if any(":" in ip for ip in current_dns):
                            self.ip_family_var.set("IPv6 (Next-Gen)")
                        else:
                            self.ip_family_var.set("IPv4 (Standard)")

                        # Ping active slots
                        if len(current_dns) > 0: self.ping_slot(1)
                        if len(current_dns) > 1: self.ping_slot(2)
                        if len(current_dns) > 2: self.ping_slot(3)
                    else:
                        self.preset_var.set("⚙️ Custom DNS Servers")

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
                    else:
                        def _check_v6():
                            from netools.libs.net import check_ipv6_connectivity
                            if not check_ipv6_connectivity():
                                self.after(0, lambda: self.main_app.show_toast(
                                     "⚠️ Perhatian: Jaringan/ISP Anda tidak memiliki rute IPv6 aktif. DNS IPv6 mungkin timeout.",
                                     level="warning"
                                ))
                        threading.Thread(target=_check_v6, daemon=True).start()
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
        self.load_active_interface_dns()
        self.main_app.show_toast(f"✓ {len(self.interfaces)} Network Adapters refreshed & DNS synced.", level="info")

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
                    self.after(0, self.load_active_interface_dns)
                    if hasattr(self.main_app, "dashboard_view"):
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

            if "All" in cat_name:
                filtered_labels.append(f"{p['country']} {p['name']}")
            elif "Security" in cat_name and (cat == "security" or "security" in desc or "privacy" in desc or "no-log" in desc):
                filtered_labels.append(f"{p['country']} {p['name']}")
            elif "Gaming" in cat_name and (cat == "gaming" or "gaming" in desc or "game" in name or "fast" in desc or region == "asia"):
                filtered_labels.append(f"{p['country']} {p['name']}")
            elif "Ad-Blocking" in cat_name and (cat == "adblock" or "ad" in desc or "block" in desc):
                filtered_labels.append(f"{p['country']} {p['name']}")
            elif "Family" in cat_name and (cat == "family" or "family" in desc or "parental" in desc or "safe" in desc):
                filtered_labels.append(f"{p['country']} {p['name']}")
            elif "Asia" in cat_name and region == "asia":
                filtered_labels.append(f"{p['country']} {p['name']}")
            elif "Global" in cat_name and (region == "global" or "anycast" in desc):
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

    def verify_dns_status(self):
        if hasattr(self, "verify_modal") and self.verify_modal is not None:
            try:
                if self.verify_modal.winfo_exists():
                    self.verify_modal.deiconify()
                    self.verify_modal.lift()
                    self.verify_modal.focus_force()
                    return
            except Exception:
                pass

        selected_label = self.iface_var.get()
        dev = self.active_interface
        for i in self.interfaces:
            if i["label"] == selected_label:
                dev = i["device"]
                break

        def _bg():
            current_dns = sys_dns.get_interface_dns(dev)
            if not current_dns:
                ips = [self.dns1_entry.get().strip(), self.dns2_entry.get().strip(), self.dns3_entry.get().strip()]
                current_dns = [ip for ip in ips if ip]

            # 1. Check OS-level DoT status
            dot_active = False
            dot_mode = "Disabled"
            try:
                import subprocess
                out = subprocess.check_output(["resolvectl", "status", dev], text=True, stderr=subprocess.DEVNULL)
                if "+DNSOverTLS" in out or "DNSOverTLS=yes" in out:
                    dot_active = True
                    dot_mode = "Strict (+DNSOverTLS)"
                elif "DNSOverTLS=opportunistic" in out:
                    dot_active = True
                    dot_mode = "Opportunistic (TLS 853)"
            except Exception:
                pass

            # 2. Test each individual active DNS server (UDP 53 and DoT TLS 853)
            from netools.libs.dns_benchmark import query_udp_dns, query_dot_dns, query_doh_dns
            server_reports = []
            target_doh_url = None

            for ip in current_dns:
                # Find provider name
                prov_name = "Custom"
                for p in self.providers.values():
                    if (p.get("ipv4") and ip in p["ipv4"]) or (p.get("ipv6") and ip in p["ipv6"]):
                        prov_name = p.get("name", "Unknown")
                        if not target_doh_url and p.get("doh_url"):
                            target_doh_url = p["doh_url"]
                        break

                udp_lat = query_udp_dns(ip, "google.com", timeout=1.5)
                dot_lat = query_dot_dns(ip, "google.com", timeout=2.0)

                udp_txt = f"{udp_lat:.1f} ms" if udp_lat else "Timeout"
                dot_txt = f"🟢 TLS {dot_lat:.1f} ms" if dot_lat else "⚪ No TLS"
                server_reports.append(f"• {ip} ({prov_name}): UDP {udp_txt} | {dot_txt}")

            # 3. Test DoH endpoint
            if not target_doh_url:
                target_doh_url = "https://security.cloudflare-dns.com/dns-query"

            doh_ms = query_doh_dns(target_doh_url, "google.com", timeout=2.5)
            doh_str = f"🟢 Connected ({doh_ms:.1f} ms)" if doh_ms else "🔴 Failed / Blocked"

            def _show():
                top = ctk.CTkToplevel(self)
                self.verify_modal = top
                top.title("🔍 Universal DNS & Encryption Inspector")
                top.geometry("540x400")
                top.configure(fg_color="#181825")
                top.transient(self.main_app)
                top.grab_set()

                def _close_verify():
                    self.verify_modal = None
                    top.destroy()

                top.protocol("WM_DELETE_WINDOW", _close_verify)

                ctk.CTkLabel(top, text="🔍 Universal DNS & Encryption Inspector", font=Fonts.title(14), text_color=COLOR_ACCENT_YELLOW).pack(pady=(14, 8))

                card = ctk.CTkFrame(top, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
                card.pack(fill="both", expand=True, padx=16, pady=4)

                ctk.CTkLabel(card, text=f"• Network Interface : {dev}", font=Fonts.bold(11), text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(fill="x", padx=14, pady=(8, 2))
                ctk.CTkLabel(card, text=f"• OS Transport      : {'🟢 ' + dot_mode if dot_active else '⚪ Plain UDP 53'}", font=Fonts.bold(11), text_color=COLOR_ACCENT_GREEN if dot_active else COLOR_TEXT_SECONDARY, anchor="w").pack(fill="x", padx=14, pady=2)
                ctk.CTkLabel(card, text=f"• DoH ({target_doh_url.split('/')[2]}) : {doh_str}", font=Fonts.bold(11), text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(fill="x", padx=14, pady=2)

                ctk.CTkLabel(card, text="── Active Resolvers Latency & TLS Capability ──", font=Fonts.bold(10), text_color=COLOR_ACCENT_BLUE, anchor="w").pack(fill="x", padx=14, pady=(8, 4))
                
                if server_reports:
                    for rep in server_reports:
                        ctk.CTkLabel(card, text=rep, font=Fonts.mono(10), text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(fill="x", padx=14, pady=1)
                else:
                    ctk.CTkLabel(card, text="• No active DNS servers detected (DHCP Default)", font=Fonts.mono(10), text_color=COLOR_TEXT_SECONDARY, anchor="w").pack(fill="x", padx=14, pady=2)

                btn_row = ctk.CTkFrame(top, fg_color="#181825")
                btn_row.pack(fill="x", padx=16, pady=12)

                def _open_leak_test():
                    import webbrowser
                    webbrowser.open("https://browserleaks.com/dns")

                def _open_cf_help():
                    import webbrowser
                    webbrowser.open("https://one.one.one.one/help")

                ctk.CTkButton(
                    btn_row,
                    text="🌐 Universal Leak Test",
                    font=Fonts.bold(11),
                    fg_color=COLOR_ACCENT_BLUE,
                    text_color="#11111b",
                    hover_color="#b4befe",
                    command=_open_leak_test
                ).pack(side="left", padx=(0, 6))

                ctk.CTkButton(
                    btn_row,
                    text="🌐 1.1.1.1/help",
                    font=Fonts.regular(11),
                    fg_color="#313244",
                    text_color=COLOR_TEXT_PRIMARY,
                    hover_color="#45475a",
                    command=_open_cf_help
                ).pack(side="left", padx=4)

                ctk.CTkButton(
                    btn_row,
                    text="Close",
                    font=Fonts.regular(11),
                    fg_color="#313244",
                    text_color=COLOR_TEXT_PRIMARY,
                    hover_color="#45475a",
                    width=70,
                    command=_close_verify
                ).pack(side="right")

            try:
                self.after(0, _show)
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()
