"""
GRC 3-Tier Benchmark Modal Window (CustomTkinter UI + ttk dark table).
Hybrid approach: CTk widgets for controls, styled ttk.Treeview for dense table data
so live streaming updates stay fast (no full re-render per result).
"""

import threading
import concurrent.futures
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import Dict, List, Any, Optional

import dns_jumper_db as db
import dns_jumper_benchmark as bm
from netools.services import dns_service
from netools.gui.toast import ToastManager


def center_window(window: ctk.CTkToplevel, width: int = 1080, height: int = 700, parent: Optional[ctk.CTk] = None):
    window.update_idletasks()
    if parent and parent.winfo_exists():
        p_x = parent.winfo_rootx()
        p_y = parent.winfo_rooty()
        p_w = parent.winfo_width()
        p_h = parent.winfo_height()
        x = max(20, p_x + (p_w - width) // 2)
        y = max(20, p_y + (p_h - height) // 2)
    else:
        s_w = window.winfo_screenwidth()
        s_h = window.winfo_screenheight()
        x = max(20, (s_w - width) // 2)
        y = max(20, (s_h - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


class GRCBenchmarkModal(ctk.CTkToplevel):
    def __init__(self, parent, dns_view):
        super().__init__(parent)
        self.main_app = parent
        self.dns_view = dns_view
        self.title("⚡ GRC 3-Tier DNS Benchmark - Real-Time Live Streaming")
        self.minsize(900, 580)
        self.configure(fg_color="#1e1e2e")

        self.transient(parent)
        center_window(self, width=1080, height=700, parent=parent)
        self.lift()
        self.focus_force()

        self.toast = ToastManager(self)
        self.results_data: List[bm.GRCBenchmarkResult] = []
        self.checked_keys = set()
        self.is_running = False
        self.stop_event = threading.Event()
        self.sort_state = {"col": "score", "reverse": False}

        self.providers = db.load_providers()
        self._build_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def show_toast(self, message: str, level: str = "success", duration_ms: int = 3500):
        self.toast.show(message, level=level, duration_ms=duration_ms)

    def _safe_after(self, ms: int, func, *args):
        if not self.winfo_exists():
            return
        try:
            self.after(ms, func, *args)
        except Exception:
            pass

    def _build_widgets(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="#181825", corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(
            hdr,
            text="⚡ GRC 3-Tier DNS Benchmark (Real-Time Live Streaming)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#cdd6f4"
        ).pack(anchor="w", padx=16, pady=12)

        # Controls
        ctrl = ctk.CTkFrame(self, fg_color="#1e1e2e", corner_radius=8)
        ctrl.pack(fill="x", padx=16, pady=10)

        # Row 1: Mode & Region Filter
        r1 = ctk.CTkFrame(ctrl, fg_color="#1e1e2e")
        r1.pack(fill="x", pady=2)
        ctk.CTkLabel(r1, text="Mode:", font=ctk.CTkFont(size=9, weight="bold"), text_color="#cdd6f4").pack(side="left", padx=(0, 6))
        self.mode_var = ctk.StringVar(value="doh")
        ctk.CTkRadioButton(
            r1, text="🔒 DoH Turbo (HTTPS)", variable=self.mode_var, value="doh",
            font=ctk.CTkFont(size=9), text_color="#a6e3a1",
            fg_color="#313244", hover_color="#45475a"
        ).pack(side="left", padx=4)
        ctk.CTkRadioButton(
            r1, text="🌐 UDP Port 53 (GRC)", variable=self.mode_var, value="udp",
            font=ctk.CTkFont(size=9), text_color="#89b4fa",
            fg_color="#313244", hover_color="#45475a"
        ).pack(side="left", padx=4)

        ctk.CTkLabel(r1, text="|  Region Filter:", font=ctk.CTkFont(size=9, weight="bold"), text_color="#cdd6f4").pack(side="left", padx=(10, 6))
        self.region_var = ctk.StringVar(value="All Regions")
        reg_values = ["All Regions", "🌏 Asia-Pacific (ID/SG/JP/CN)", "🌍 Europe (EU/CH/DE)", "🌎 North America (US/CA)", "🛡️ Security Only", "🚫 Adblock Only"]
        reg_cb = ctk.CTkComboBox(
            r1, variable=self.region_var, values=reg_values, state="readonly",
            width=250, font=ctk.CTkFont(size=9), dropdown_font=ctk.CTkFont(size=9)
        )
        reg_cb.pack(side="left", padx=4)

        ctk.CTkButton(
            r1, text="🔄 Cloud Sync DB",
            font=ctk.CTkFont(size=8, weight="bold"),
            fg_color="#313244", text_color="#f9e2af",
            hover_color="#45475a", height=28,
            command=self.sync_db
        ).pack(side="right")

        # Row 2: TLD & Actions
        r2 = ctk.CTkFrame(ctrl, fg_color="#1e1e2e")
        r2.pack(fill="x", pady=(8, 2))
        ctk.CTkLabel(r2, text="TLD Target:", font=ctk.CTkFont(size=9, weight="bold"), text_color="#cdd6f4").pack(side="left", padx=(0, 6))
        tld_labels = [p["name"] for p in db.TLD_PRESETS.values()]
        self.tld_var = ctk.StringVar(value=tld_labels[0])
        self.tld_cb = ctk.CTkComboBox(
            r2, variable=self.tld_var, values=tld_labels, state="readonly",
            width=320, font=ctk.CTkFont(size=9), dropdown_font=ctk.CTkFont(size=9)
        )
        self.tld_cb.pack(side="left", padx=4)
        self.tld_cb.bind("<<ComboboxSelected>>", self.on_tld_changed)

        self.btn_start = ctk.CTkButton(
            r2, text="▶ Start 3-Tier Benchmark",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#a6e3a1", text_color="#11111b",
            hover_color="#89b4fa", height=34,
            command=self.start_benchmark
        )
        self.btn_start.pack(side="right", padx=4)
        self.btn_stop = ctk.CTkButton(
            r2, text="⏹ Stop",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#f38ba8", text_color="#11111b",
            hover_color="#89b4fa", height=34,
            state="disabled", command=self.stop_benchmark
        )
        self.btn_stop.pack(side="right", padx=4)

        # Progress
        self.prog_var = ctk.DoubleVar(value=0.0)
        self.progress_bar = ctk.CTkProgressBar(
            self, variable=self.prog_var, height=10,
            progress_color="#89b4fa", fg_color="#313244"
        )
        self.progress_bar.pack(fill="x", padx=16, pady=(4, 6))
        self.status_lbl = ctk.CTkLabel(
            self, text="Ready to benchmark.",
            font=ctk.CTkFont(size=9, slant="italic"),
            text_color="#bac2de"
        )
        self.status_lbl.pack(anchor="w", padx=16, pady=(0, 6))

        # Table container
        table_container = tk.Frame(self, bg="#181825")
        table_container.pack(fill="both", expand=True, padx=16, pady=4)

        # Dark style for ttk Treeview matching the CustomTkinter palette
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "GRC.Treeview",
            background="#181825",
            foreground="#cdd6f4",
            fieldbackground="#181825",
            rowheight=26,
            font=("Sans", 9),
            bordercolor="#313244",
            lightcolor="#181825",
            darkcolor="#181825"
        )
        style.configure(
            "GRC.Treeview.Heading",
            background="#313244",
            foreground="#cdd6f4",
            font=("Sans", 9, "bold"),
            bordercolor="#313244",
            relief="flat"
        )
        style.map(
            "GRC.Treeview",
            background=[("selected", "#45475a")],
            foreground=[("selected", "#f5e0dc")]
        )
        style.map(
            "GRC.Treeview.Heading",
            background=[("active", "#45475a")],
            relief=[("active", "flat")]
        )
        style.configure("Vertical.TScrollbar", background="#313244", troughcolor="#181825", bordercolor="#181825", arrowcolor="#cdd6f4")
        style.configure("Horizontal.TScrollbar", background="#313244", troughcolor="#181825", bordercolor="#181825", arrowcolor="#cdd6f4")

        cols = ("check", "rank", "name", "origin", "cached", "uncached", "tld", "score", "grc_bar", "status", "primary_ip")
        self.tree = ttk.Treeview(table_container, columns=cols, show="headings", style="GRC.Treeview")

        self.tree.heading("check", text="Pick [✔]", command=lambda: self.sort_by_col("check"))
        self.tree.heading("rank", text="Rank ↕", command=lambda: self.sort_by_col("rank"))
        self.tree.heading("name", text="DNS Provider ↕", command=lambda: self.sort_by_col("name"))
        self.tree.heading("origin", text="Region ↕", command=lambda: self.sort_by_col("origin"))
        self.tree.heading("cached", text="🟢 Cached (ms) ↕", command=lambda: self.sort_by_col("cached"))
        self.tree.heading("uncached", text="🔵 Uncached (ms) ↕", command=lambda: self.sort_by_col("uncached"))
        self.tree.heading("tld", text=self.get_tld_header(), command=lambda: self.sort_by_col("tld"))
        self.tree.heading("score", text="GRC Score ↕", command=lambda: self.sort_by_col("score"))
        self.tree.heading("grc_bar", text="GRC Response Bar")
        self.tree.heading("status", text="Status ↕", command=lambda: self.sort_by_col("status"))
        self.tree.heading("primary_ip", text="Primary IPv4")

        self.tree.column("check", width=65, anchor="center", stretch=False)
        self.tree.column("rank", width=60, anchor="center", stretch=False)
        self.tree.column("name", width=190, anchor="w", stretch=True)
        self.tree.column("origin", width=80, anchor="center", stretch=False)
        self.tree.column("cached", width=90, anchor="e", stretch=False)
        self.tree.column("uncached", width=95, anchor="e", stretch=False)
        self.tree.column("tld", width=95, anchor="e", stretch=False)
        self.tree.column("score", width=85, anchor="e", stretch=False)
        self.tree.column("grc_bar", width=140, anchor="w", stretch=False)
        self.tree.column("status", width=90, anchor="center", stretch=False)
        self.tree.column("primary_ip", width=120, anchor="w", stretch=False)

        v_scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview, style="Vertical.TScrollbar")
        h_scroll = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview, style="Horizontal.TScrollbar")
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Button-1>", self.on_tree_click)

        # Bottom Bar
        bot = ctk.CTkFrame(self, fg_color="#181825")
        bot.pack(fill="x", padx=16, pady=10)
        ctk.CTkButton(
            bot, text="🏆 Apply Fastest (Top 3)",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#f9e2af", text_color="#11111b",
            hover_color="#89b4fa", height=32,
            command=self.apply_fastest
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            bot, text="🎯 Apply Smart Mix (1 Cached + 1 Uncached + 1 TLD)",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#a6e3a1", text_color="#11111b",
            hover_color="#89b4fa", height=32,
            command=self.apply_smart_mix
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            bot, text="✅ Apply Checked",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#89b4fa", text_color="#11111b",
            hover_color="#89b4fa", height=32,
            command=self.apply_checked
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            bot, text="✕ Close",
            font=ctk.CTkFont(size=9),
            fg_color="#45475a", text_color="#cdd6f4",
            hover_color="#6c7086", height=32,
            command=self.on_close
        ).pack(side="right", padx=3)

    def get_tld_header(self) -> str:
        sel = self.tld_var.get()
        return "🟡 TLD (.id) ↕" if "Indonesia" in sel else ("🟡 TLD (.com) ↕" if "Global" in sel else "🟡 TLD Latency ↕")

    def on_tld_changed(self, event=None):
        if self.winfo_exists():
            self.tree.heading("tld", text=self.get_tld_header())

    def on_tree_click(self, event):
        if not self.winfo_exists():
            return
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            col = self.tree.identify_column(event.x)
            item_id = self.tree.identify_row(event.y)
            if item_id and col == "#1":
                if item_id in self.checked_keys:
                    self.checked_keys.remove(item_id)
                else:
                    if len(self.checked_keys) >= 3:
                        self.show_toast("Maksimal 3 DNS Server yang dapat dipilih.", level="warning")
                        return
                    self.checked_keys.add(item_id)
                self._render_all_rows()

    def sort_by_col(self, col: str):
        if not self.results_data or not self.winfo_exists():
            return
        if self.sort_state["col"] == col:
            self.sort_state["reverse"] = not self.sort_state["reverse"]
        else:
            self.sort_state["col"] = col
            self.sort_state["reverse"] = False
        rev = self.sort_state["reverse"]

        if col == "rank":
            self.results_data.sort(key=lambda x: x.grc_score, reverse=rev)
        elif col == "name":
            self.results_data.sort(key=lambda x: x.name.lower(), reverse=rev)
        elif col == "score":
            self.results_data.sort(key=lambda x: x.grc_score, reverse=rev)
        elif col == "cached":
            self.results_data.sort(key=lambda x: x.cached_ms if x.cached_lats else 9999.0, reverse=rev)
        elif col == "uncached":
            self.results_data.sort(key=lambda x: x.uncached_ms if x.uncached_lats else 9999.0, reverse=rev)
        elif col == "tld":
            self.results_data.sort(key=lambda x: x.tld_ms if x.tld_lats else 9999.0, reverse=rev)
        elif col == "check":
            self.results_data.sort(key=lambda x: 0 if x.key in self.checked_keys else 1, reverse=rev)
        self._render_all_rows()

    def sync_db(self):
        def _bg():
            self._safe_after(0, lambda: self.status_lbl.configure(text="Syncing resolvers from cloud..."))
            succ, msg, count = db.sync_cloud_providers()
            self.providers = db.load_providers()
            if self.winfo_exists():
                self._safe_after(0, lambda: self.show_toast(msg, level="success" if succ else "error"))
        threading.Thread(target=_bg, daemon=True).start()

    def start_benchmark(self):
        if self.is_running:
            return
        self.is_running = True
        self.stop_event.clear()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.tree.delete(*self.tree.get_children())
        self.results_data.clear()
        self.checked_keys.clear()

        sel_tld = self.tld_var.get()
        tld_domains = db.TLD_PRESETS.get("indonesia", {}).get("domains", ["bca.co.id", "tokopedia.com"])
        for p in db.TLD_PRESETS.values():
            if p["name"] == sel_tld:
                tld_domains = p["domains"]
                break

        provs = self.providers
        mode = self.mode_var.get()

        for idx, (k, p) in enumerate(provs.items()):
            self.tree.insert("", "end", iid=k, values=(
                "[   ]", f"#{idx+1}", p["name"], p["country"], "⏳", "⏳", "⏳", "Testing...", "⚡ Live...", "Testing", p.get("ipv4", [""])[0]
            ))

        def _worker():
            prov_list = list(provs.items())
            total = len(prov_list)
            completed = 0

            with concurrent.futures.ThreadPoolExecutor(max_workers=14) as executor:
                future_to_key = {
                    executor.submit(bm.benchmark_provider_grc_udp, k, p, tld_domains): k
                    for k, p in prov_list
                }
                for f in concurrent.futures.as_completed(future_to_key):
                    if self.stop_event.is_set():
                        break
                    try:
                        res = f.result()
                        completed += 1
                        self._safe_after(0, self._on_single_result, res, completed, total)
                    except Exception:
                        pass
            self._safe_after(0, self._on_finished)

        threading.Thread(target=_worker, daemon=True).start()

    def stop_benchmark(self):
        self.stop_event.set()
        self.status_lbl.configure(text="Stopping...")

    def _on_single_result(self, res: bm.GRCBenchmarkResult, completed: int, total: int):
        if not self.winfo_exists():
            return
        existing = [i for i, r in enumerate(self.results_data) if r.key == res.key]
        if existing:
            self.results_data[existing[0]] = res
        else:
            self.results_data.append(res)
        self.results_data.sort(key=lambda r: (0 if r.status == "Stable" else 1, r.grc_score))

        pct = (completed / max(1, total)) * 100.0
        self.prog_var.set(pct)
        top = self.results_data[0] if self.results_data else None
        top_txt = f" | #1: {top.name} ({top.grc_score:.1f})" if top else ""
        self.status_lbl.configure(text=f"⚡ Live Testing: {completed}/{total} ({pct:.0f}%){top_txt}")
        self._render_all_rows()

    def _render_all_rows(self):
        if not self.winfo_exists():
            return
        for idx, item in enumerate(self.results_data):
            rank_str = f"🥇 #{idx+1}" if idx == 0 else (f"🥈 #{idx+1}" if idx == 1 else (f"🥉 #{idx+1}" if idx == 2 else f"#{idx+1}"))
            check_str = "[ ✔ ]" if item.key in self.checked_keys else "[   ]"
            c_str = f"{item.cached_ms:.1f}" if item.cached_lats else "N/A"
            u_str = f"{item.uncached_ms:.1f}" if item.uncached_lats else "N/A"
            t_str = f"{item.tld_ms:.1f}" if item.tld_lats else "N/A"
            score_str = f"{item.grc_score:.1f}" if item.status != "Failed" else "FAIL"
            c_len = max(1, min(4, int(item.cached_ms / 30.0)))
            u_len = max(1, min(4, int(item.uncached_ms / 40.0)))
            t_len = max(1, min(4, int(item.tld_ms / 40.0)))
            bar_str = f"{'🟢'*c_len}{'🔵'*u_len}{'🟡'*t_len}"

            vals = (check_str, rank_str, item.name, item.country, c_str, u_str, t_str, score_str, bar_str, item.status, item.ipv4[0] if item.ipv4 else "")
            if self.tree.exists(item.key):
                self.tree.item(item.key, values=vals)
                self.tree.move(item.key, "", idx)
            else:
                self.tree.insert("", "end", iid=item.key, values=vals)

    def _on_finished(self):
        if not self.winfo_exists():
            return
        self.is_running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        if self.results_data:
            top = self.results_data[0]
            self.status_lbl.configure(text=f"✓ Benchmark finished! #1 Fastest: {top.name} ({top.grc_score:.1f} score)")

    def apply_fastest(self):
        if not self.results_data:
            self.show_toast("Jalankan benchmark terlebih dahulu.", level="warning")
            return
        top = self.results_data[0]
        self.dns_view.dns1_var.set(top.ipv4[0] if top.ipv4 else "")
        self.dns_view.dns2_var.set(top.ipv4[1] if len(top.ipv4) > 1 else top.ipv4[0])
        self.dns_view.preset_var.set(f"{top.country} {top.name}")
        self.dns_view.apply_dns()
        self.destroy()

    def apply_smart_mix(self):
        if not self.results_data:
            self.show_toast("Jalankan benchmark terlebih dahulu.", level="warning")
            return
        mix = dns_service.calculate_smart_mix(self.results_data)
        if not mix:
            return
        self.dns_view.dns1_var.set(mix["ips"][0])
        self.dns_view.dns2_var.set(mix["ips"][1])
        self.dns_view.dns3_var.set(mix["ips"][2])
        self.dns_view.preset_var.set("⚙️ Custom DNS Servers")
        self.dns_view.apply_dns()
        self.main_app.show_toast(
            f"🎯 Applied Smart Mix: {mix['dns1_cached'].name} + {mix['dns2_uncached'].name} + {mix['dns3_tld'].name}",
            level="success", duration_ms=4500
        )
        self.destroy()

    def apply_checked(self):
        if not self.checked_keys:
            self.show_toast("Centang [ ✔ ] minimal 1 DNS server.", level="warning")
            return
        items = [r for r in self.results_data if r.key in self.checked_keys]
        self.dns_view.dns1_var.set(items[0].ipv4[0] if items[0].ipv4 else "")
        self.dns_view.dns2_var.set(items[1].ipv4[0] if len(items) > 1 and items[1].ipv4 else "")
        self.dns_view.dns3_var.set(items[2].ipv4[0] if len(items) > 2 and items[2].ipv4 else "")
        self.dns_view.preset_var.set("⚙️ Custom DNS Servers")
        self.dns_view.apply_dns()
        self.destroy()

    def on_close(self):
        self.stop_event.set()
        self.is_running = False
        try:
            self.destroy()
        except Exception:
            pass
