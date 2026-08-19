"""
Tab 2: DNS Jumper & Real-Time GRC 3-Tier Latency Benchmark View (CustomTkinter).
"""

import customtkinter as ctk
import threading
from netools.adapters import platform_dns as sys_dns
from netools.services import dns_service
from netools.gui.view_benchmark_modal import GRCBenchmarkModal
import dns_jumper_db as db


class DNSView(ctk.CTkFrame):
    def __init__(self, parent, main_app):
        super().__init__(parent, fg_color="#181825")
        self.main_app = main_app
        self.providers = db.load_providers()
        self.interfaces = sys_dns.get_network_interfaces()
        self.active_interface = self.interfaces[0]["device"] if self.interfaces else None
        self.active_connection = self.interfaces[0]["connection"] if self.interfaces else None

        self._init_vars()
        self._build_ui()
        self.refresh()

    def _init_vars(self):
        self.selected_iface_var = ctk.StringVar()
        if self.interfaces:
            self.selected_iface_var.set(self.interfaces[0]["label"])
        self.preset_var = ctk.StringVar(value="🇨🇳 CN/SG AliDNS (Alibaba Cloud)")
        self.dns1_var = ctk.StringVar(value="223.5.5.5")
        self.dns2_var = ctk.StringVar(value="223.6.6.6")
        self.dns3_var = ctk.StringVar(value="1.1.1.1")
        self.enable_dot_var = ctk.BooleanVar(value=False)
        self.persistent_var = ctk.BooleanVar(value=True)

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text="⚡ DNS Switcher & GRC Benchmark Suite",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#89b4fa"
        ).pack(anchor="w", pady=(0, 10))

        # Adapter Selection
        f1 = ctk.CTkFrame(self, fg_color="#181825")
        f1.pack(fill="x", pady=4)
        ctk.CTkLabel(
            f1,
            text="Network Adapter:",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#cdd6f4",
            width=130,
            anchor="w"
        ).pack(side="left", padx=(0, 6))
        iface_labels = [i["label"] for i in self.interfaces] if self.interfaces else ["No interface"]
        self.iface_cb = ctk.CTkComboBox(
            f1,
            variable=self.selected_iface_var,
            values=iface_labels,
            state="readonly",
            font=ctk.CTkFont(size=9),
            width=300,
            dropdown_font=ctk.CTkFont(size=9)
        )
        self.iface_cb.pack(side="left", fill="x", expand=True, padx=4)
        self.iface_cb.bind("<<ComboboxSelected>>", self.on_iface_change)

        # Presets
        f2 = ctk.CTkFrame(self, fg_color="#181825")
        f2.pack(fill="x", pady=4)
        ctk.CTkLabel(
            f2,
            text="Preset Provider:",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#cdd6f4",
            width=130,
            anchor="w"
        ).pack(side="left", padx=(0, 6))
        preset_labels = [f"{p['country']} {p['name']}" for p in self.providers.values()]
        preset_labels.insert(0, "⚙️ Custom DNS Servers")
        self.preset_cb = ctk.CTkComboBox(
            f2,
            variable=self.preset_var,
            values=preset_labels,
            state="readonly",
            font=ctk.CTkFont(size=9),
            width=300,
            dropdown_font=ctk.CTkFont(size=9)
        )
        self.preset_cb.pack(side="left", fill="x", expand=True, padx=4)
        self.preset_cb.bind("<<ComboboxSelected>>", self.on_preset_change)

        # 3-Slots Card
        slots_card = ctk.CTkFrame(
            self,
            fg_color="#1e1e2e",
            corner_radius=8,
            border_width=1,
            border_color="#313244"
        )
        slots_card.pack(fill="x", pady=8)

        # Slot 1
        s1 = ctk.CTkFrame(slots_card, fg_color="#1e1e2e")
        s1.pack(fill="x", pady=2, padx=12)
        ctk.CTkLabel(
            s1,
            text="DNS 1 (Primary)   :",
            font=ctk.CTkFont(size=9),
            text_color="#a6adc8",
            width=160,
            anchor="w"
        ).pack(side="left")
        ctk.CTkEntry(
            s1,
            textvariable=self.dns1_var,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#cdd6f4",
            fg_color="#313244",
            border_color="#45475a",
            height=28
        ).pack(side="left", fill="x", expand=True, padx=4)

        # Slot 2
        s2 = ctk.CTkFrame(slots_card, fg_color="#1e1e2e")
        s2.pack(fill="x", pady=2, padx=12)
        ctk.CTkLabel(
            s2,
            text="DNS 2 (Secondary) :",
            font=ctk.CTkFont(size=9),
            text_color="#a6adc8",
            width=160,
            anchor="w"
        ).pack(side="left")
        ctk.CTkEntry(
            s2,
            textvariable=self.dns2_var,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#cdd6f4",
            fg_color="#313244",
            border_color="#45475a",
            height=28
        ).pack(side="left", fill="x", expand=True, padx=4)

        # Slot 3
        s3 = ctk.CTkFrame(slots_card, fg_color="#1e1e2e")
        s3.pack(fill="x", pady=2, padx=12)
        ctk.CTkLabel(
            s3,
            text="DNS 3 (Tertiary)  :",
            font=ctk.CTkFont(size=9),
            text_color="#a6adc8",
            width=160,
            anchor="w"
        ).pack(side="left")
        ctk.CTkEntry(
            s3,
            textvariable=self.dns3_var,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#cdd6f4",
            fg_color="#313244",
            border_color="#45475a",
            height=28
        ).pack(side="left", fill="x", expand=True, padx=4)

        # Options
        opts_f = ctk.CTkFrame(self, fg_color="#181825")
        opts_f.pack(fill="x", pady=4)
        ctk.CTkCheckBox(
            opts_f,
            text="DNS-over-TLS (DoT systemd)",
            variable=self.enable_dot_var,
            font=ctk.CTkFont(size=9),
            text_color="#a6adc8",
            fg_color="#313244",
            hover_color="#45475a"
        ).pack(side="left", padx=(0, 12))
        ctk.CTkCheckBox(
            opts_f,
            text="Persistent (NetworkManager)",
            variable=self.persistent_var,
            font=ctk.CTkFont(size=9),
            text_color="#a6adc8",
            fg_color="#313244",
            hover_color="#45475a"
        ).pack(side="left")

        # Buttons
        btn_f = ctk.CTkFrame(self, fg_color="#181825")
        btn_f.pack(fill="x", pady=(8, 4))
        ctk.CTkButton(
            btn_f,
            text="🚀 Apply DNS",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#a6e3a1",
            text_color="#11111b",
            hover_color="#89b4fa",
            height=36,
            command=self.apply_dns
        ).pack(side="left", fill="x", expand=True, padx=3)
        ctk.CTkButton(
            btn_f,
            text="⚡ GRC Benchmark",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#89b4fa",
            text_color="#11111b",
            hover_color="#89b4fa",
            height=36,
            command=self.open_benchmark
        ).pack(side="left", fill="x", expand=True, padx=3)
        ctk.CTkButton(
            btn_f,
            text="🧹 Flush DNS",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#f9e2af",
            text_color="#11111b",
            hover_color="#89b4fa",
            height=36,
            command=self.flush_dns
        ).pack(side="left", fill="x", expand=True, padx=3)
        ctk.CTkButton(
            btn_f,
            text="🔄 Restore DHCP",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#45475a",
            text_color="#cdd6f4",
            hover_color="#6c7086",
            height=36,
            command=self.restore_dhcp
        ).pack(side="left", fill="x", expand=True, padx=3)

    def on_iface_change(self, event=None):
        sel_lbl = self.selected_iface_var.get()
        for i in self.interfaces:
            if i["label"] == sel_lbl:
                self.active_interface = i["device"]
                self.active_connection = i["connection"]
                break
        self.refresh()

    def on_preset_change(self, event=None):
        sel = self.preset_var.get()
        if sel.startswith("⚙️"):
            return
        for p in self.providers.values():
            if f"{p['country']} {p['name']}" == sel:
                ips = p.get("ipv4", [])
                self.dns1_var.set(ips[0] if len(ips) > 0 else "")
                self.dns2_var.set(ips[1] if len(ips) > 1 else "")
                self.dns3_var.set(ips[2] if len(ips) > 2 else "")
                break

    def apply_dns(self):
        ips = [self.dns1_var.get().strip(), self.dns2_var.get().strip(), self.dns3_var.get().strip()]
        valid = [ip for ip in ips if ip and not ip.isspace()]
        if not valid:
            self.main_app.show_toast("Masukkan minimal 1 DNS IP yang valid.", level="warning")
            return
        if not self.active_interface:
            self.main_app.show_toast("Tidak ada network interface aktif.", level="error")
            return
        sys_dns.apply_system_dns(
            self.active_interface,
            valid,
            connection_name=self.active_connection,
            enable_dot=self.enable_dot_var.get(),
            persistent=self.persistent_var.get()
        )
        self.main_app.show_toast(f"✓ DNS ({', '.join(valid)}) diterapkan ke '{self.active_interface}'!", level="success")
        self.main_app.dashboard_view.refresh()

    def flush_dns(self):
        sys_dns.flush_dns_cache()
        self.main_app.show_toast("✓ DNS Cache berhasil di-flush!", level="success")
        self.refresh()

    def restore_dhcp(self):
        if self.active_interface:
            sys_dns.restore_default_dns(self.active_interface, self.active_connection)
            self.main_app.show_toast(f"✓ Interface '{self.active_interface}' dikembalikan ke DHCP default.", level="info")
            self.main_app.dashboard_view.refresh()

    def refresh_presets(self):
        self.providers = db.load_providers()
        preset_labels = [f"{p['country']} {p['name']}" for p in self.providers.values()]
        preset_labels.insert(0, "⚙️ Custom DNS Servers")
        if hasattr(self, "preset_cb"):
            self.preset_cb.configure(values=preset_labels)

    def open_benchmark(self):
        modal = GRCBenchmarkModal(self.main_app, self)
        self.main_app.child_windows.append(modal)

    def refresh(self):
        self.interfaces = sys_dns.get_network_interfaces()
        labels = [i["label"] for i in self.interfaces] if self.interfaces else ["No interface"]
        self.iface_cb.configure(values=labels)
