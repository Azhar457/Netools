"""
GRC 3-Tier Real-Time Streaming DNS Benchmark Modal (CustomTkinter).
Evaluates Cached, Uncached, and Regional TLD Latency across 90+ DNS resolvers for IPv4, IPv6, DoH & DoT.
Features multi-column sorting, protocol indicators, live status, and 1-click system application.
"""

import threading
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from netools.libs import dns_db as db
from netools.libs import dns_benchmark as bm
from netools.gui.theme import Fonts, COLOR_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_ACCENT_BLUE, COLOR_ACCENT_GREEN, COLOR_ACCENT_PURPLE, COLOR_ACCENT_YELLOW

class GRCBenchmarkModal(ctk.CTkToplevel):
    def __init__(self, parent_app, dns_view):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.dns_view = dns_view

        self.title("⚡ Netools — GRC 3-Tier Real-Time DNS Benchmark (IPv4 / IPv6 / DoH / DoT)")
        self.geometry("1020x660")
        self.minsize(880, 540)
        self.configure(fg_color="#181825")

        self.benchmark_running = False
        self.benchmark_cancelled = False
        self.results_map = {}
        self.sort_directions = {}

        self.providers = db.load_providers()
        self.target_tlds = getattr(db, "TLD_PRESETS", getattr(db, "TARGET_TLD_DOMAINS", {}))

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build_widgets()

    def on_close(self):
        self.benchmark_cancelled = True
        self.benchmark_running = False
        try:
            if self in self.parent_app.child_windows:
                self.parent_app.child_windows.remove(self)
            if hasattr(self.dns_view, "benchmark_modal") and self.dns_view.benchmark_modal == self:
                self.dns_view.benchmark_modal = None
        except Exception:
            pass
        self.destroy()

    def _build_widgets(self):
        # Header Banner
        hdr = ctk.CTkFrame(self, fg_color="#11111b", height=50)
        hdr.pack(fill="x", padx=0, pady=0)
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="🏆 Gibson Research Corp (GRC) 3-Tier DNS Benchmark Engine",
            font=Fonts.title(15),
            text_color=COLOR_ACCENT_YELLOW
        ).pack(side="left", padx=20, pady=10)

        # Filter & Execution Control Card
        card_filter = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        card_filter.pack(fill="x", padx=16, pady=8)

        r1 = ctk.CTkFrame(card_filter, fg_color=COLOR_CARD)
        r1.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(r1, text="Test Protocol / IP:", font=Fonts.bold(11), text_color=COLOR_TEXT_PRIMARY).pack(side="left", padx=(0, 6))

        self.mode_var = ctk.StringVar(value="IPv4 Standard (UDP 53)")
        self.mode_cb = ctk.CTkComboBox(
            r1,
            variable=self.mode_var,
            values=["IPv4 Standard (UDP 53)", "IPv6 Next-Gen (UDP 53)", "DNS-over-HTTPS (DoH)", "DNS-over-TLS (DoT 853)"],
            width=210,
            font=Fonts.regular(11),
            dropdown_font=Fonts.regular(11)
        )
        self.mode_cb.pack(side="left", padx=4)

        ctk.CTkLabel(r1, text="|  Region:", font=Fonts.bold(11), text_color=COLOR_TEXT_PRIMARY).pack(side="left", padx=(14, 6))

        self.region_var = ctk.StringVar(value="🌏 All Curated Resolvers (90+)")
        self.region_cb = ctk.CTkComboBox(
            r1, variable=self.region_var,
            values=["🌏 All Curated Resolvers (90+)", "🇨🇳/🇸🇬/🇯🇵 Asia-Pacific", "🌍 Europe & UK", "🌎 North America", "🌐 Global Anycast"],
            width=240, font=Fonts.regular(11), dropdown_font=Fonts.regular(11)
        )
        self.region_cb.pack(side="left", padx=4)

        r2 = ctk.CTkFrame(card_filter, fg_color=COLOR_CARD)
        r2.pack(fill="x", padx=14, pady=(4, 10))

        ctk.CTkLabel(r2, text="TLD Target:", font=Fonts.bold(11), text_color=COLOR_TEXT_PRIMARY).pack(side="left", padx=(0, 6))

        tld_choices = [f"{v['name']} ({k})" for k, v in self.target_tlds.items()]
        self.tld_var = ctk.StringVar(value=tld_choices[0] if tld_choices else "indonesia")
        self.tld_cb = ctk.CTkComboBox(
            r2, variable=self.tld_var, values=tld_choices,
            width=300, font=Fonts.regular(11), dropdown_font=Fonts.regular(11)
        )
        self.tld_cb.pack(side="left", padx=4)

        # Action Buttons
        self.btn_start = ctk.CTkButton(
            r2, text="🚀 Run Benchmark", font=Fonts.bold(11),
            fg_color=COLOR_ACCENT_YELLOW, text_color="#11111b", hover_color="#f5e0dc",
            height=30, width=140, command=self.start_benchmark
        )
        self.btn_start.pack(side="left", padx=(16, 4))

        self.btn_stop = ctk.CTkButton(
            r2, text="🛑 Cancel", font=Fonts.bold(11),
            fg_color="#f38ba8", text_color="#11111b", hover_color="#eba0ac",
            height=30, width=90, state="disabled", command=self.stop_benchmark
        )
        self.btn_stop.pack(side="left", padx=4)

        # Progress bar & Status
        prog_frame = ctk.CTkFrame(self, fg_color="#181825")
        prog_frame.pack(fill="x", padx=16, pady=(0, 4))

        self.prog_bar = ctk.CTkProgressBar(prog_frame, height=6, fg_color="#313244", progress_color=COLOR_ACCENT_YELLOW)
        self.prog_bar.pack(fill="x", pady=(2, 4))
        self.prog_bar.set(0)

        self.lbl_status = ctk.CTkLabel(
            prog_frame, text="Ready. Click 'Run Benchmark' to start real-time latency evaluation (Click column headers to sort).",
            font=Fonts.regular(11), text_color="#a6adc8"
        )
        self.lbl_status.pack(anchor="w")

        # Results Table
        tbl_frame = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        tbl_frame.pack(fill="both", expand=True, padx=16, pady=4)

        cols = ("rank", "flag", "name", "proto", "cached", "uncached", "dotcom", "score", "status")
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", selectmode="browse")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#1e1e2e",
            foreground="#cdd6f4",
            fieldbackground="#1e1e2e",
            rowheight=26,
            font=("sans-serif", 10)
        )
        style.configure(
            "Treeview.Heading",
            background="#313244",
            foreground="#cdd6f4",
            font=("sans-serif", 10, "bold")
        )
        style.map("Treeview", background=[("selected", "#45475a")])

        cols_config = [
            ("rank", "# ↕", 45, "center"),
            ("flag", "Region ↕", 75, "center"),
            ("name", "DNS Resolver Name ↕", 220, "center"),
            ("proto", "Type ↕", 70, "center"),
            ("cached", "🟢 Cached ↕", 100, "center"),
            ("uncached", "🔵 Uncached ↕", 100, "center"),
            ("dotcom", "🟡 Dot-Com / TLD ↕", 115, "center"),
            ("score", "Composite Score ↕", 125, "center"),
            ("status", "Result ↕", 95, "center"),
        ]

        for col_id, title, w, align in cols_config:
            self.tree.heading(col_id, text=title, anchor=align, command=lambda c=col_id: self.sort_column(c))
            self.tree.column(col_id, width=w, minwidth=40, anchor=align, stretch=True)

        vsb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="right", fill="y", padx=(0, 8), pady=8)

        # Smart Mix Recommendation Card & Apply Buttons
        smart_card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        smart_card.pack(fill="x", padx=16, pady=(4, 12))

        ctk.CTkLabel(
            smart_card,
            text="🏆 Smart Mix Recommendation (GRC Optimum Triad)",
            font=Fonts.subtitle(12),
            text_color=COLOR_ACCENT_GREEN
        ).pack(anchor="w", padx=14, pady=(10, 4))

        self.lbl_smart_rec = ctk.CTkLabel(
            smart_card,
            text="• Run benchmark to generate composite latency recommendations for Slot 1, 2, and 3.",
            font=Fonts.mono(10),
            text_color=COLOR_TEXT_SECONDARY,
            justify="left"
        )
        self.lbl_smart_rec.pack(anchor="w", padx=14, pady=(0, 8))

        btn_row = ctk.CTkFrame(smart_card, fg_color=COLOR_CARD)
        btn_row.pack(fill="x", padx=14, pady=(0, 10))

        self.btn_apply_smart = ctk.CTkButton(
            btn_row, text="⚡ Apply GRC Smart Mix (Slots 1-3)", font=Fonts.bold(11),
            fg_color=COLOR_ACCENT_GREEN, text_color="#11111b", hover_color="#a6e3a1",
            height=32, state="disabled", command=self.apply_smart_mix
        )
        self.btn_apply_smart.pack(side="left", padx=(0, 6))

        self.btn_apply_fastest = ctk.CTkButton(
            btn_row, text="🥇 Apply #1 Fastest Only", font=Fonts.bold(11),
            fg_color=COLOR_ACCENT_BLUE, text_color="#11111b", hover_color="#b4befe",
            height=32, state="disabled", command=self.apply_fastest_single
        )
        self.btn_apply_fastest.pack(side="left", padx=6)

        ctk.CTkButton(
            btn_row, text="Close", font=Fonts.regular(11),
            fg_color="#313244", text_color=COLOR_TEXT_PRIMARY, hover_color="#45475a",
            height=32, width=80, command=self.destroy
        )

    def sort_column(self, col: str):
        """Sort Treeview rows by clicking column headers (Numeric & String)."""
        reverse = self.sort_directions.get(col, False)
        self.sort_directions[col] = not reverse

        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

        def _val_key(v):
            if not v or v in ("Timeout", "Failed", "—"):
                return 999999.0
            clean = str(v).replace(" ms", "").replace("#", "").strip()
            try:
                return float(clean)
            except ValueError:
                return str(v).lower()

        items.sort(key=lambda t: _val_key(t[0]), reverse=reverse)

        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

    def _get_benchmark_mode_key(self) -> str:
        m = self.mode_var.get().lower()
        if "ipv6" in m: return "ipv6"
        if "doh" in m: return "doh"
        if "dot" in m: return "dot"
        return "ipv4"

    def start_benchmark(self):
        if self.benchmark_running:
            return

        self.benchmark_running = True
        self.benchmark_cancelled = False
        self.results_map.clear()

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_apply_smart.configure(state="disabled")
        self.btn_apply_fastest.configure(state="disabled")

        for item in self.tree.get_children():
            self.tree.delete(item)

        mode_key = self._get_benchmark_mode_key()

        # Pre-flight check for IPv6
        if mode_key == "ipv6":
            from netools.libs.net import check_ipv6_connectivity
            if not check_ipv6_connectivity():
                self.lbl_status.configure(
                    text="⚠️ ISP/Jaringan lokal Anda tidak memiliki koneksi IPv6 (Network Unreachable). Silakan pilih mode IPv4 atau DoH/DoT.",
                    text_color="#f38ba8"
                )
                self.btn_start.configure(state="normal")
                self.btn_stop.configure(state="disabled")
                self.benchmark_running = False
                return

        reg_text = self.region_var.get()
        region_key = "all"
        if "Asia" in reg_text: region_key = "asia"
        elif "Europe" in reg_text: region_key = "europe"
        elif "North America" in reg_text: region_key = "north_america"
        elif "Global" in reg_text: region_key = "global"

        tld_sel = self.tld_var.get()
        tld_key = "indonesia"
        for k in self.target_tlds:
            if f"({k})" in tld_sel:
                tld_key = k
                break

        # Filter providers
        filtered = db.filter_providers(self.providers, region=region_key, only_doh=(mode_key == "doh"))
        total_count = len(filtered)
        self.prog_bar.set(0)
        self.lbl_status.configure(text=f"Benchmarking {total_count} DNS resolvers in real-time ({mode_key.upper()})...", text_color="#cdd6f4")

        def _worker():
            idx = 0
            for p_id, p_info in filtered.items():
                if self.benchmark_cancelled:
                    break
                idx += 1
                prog = idx / max(1, total_count)

                # Test provider
                res = bm.benchmark_provider_full(p_id, p_info, tld_category=tld_key, mode=mode_key, timeout=2.5)
                self.results_map[p_id] = res

                # Stream update to UI
                try:
                    self.after(0, lambda r=res, p=prog, i=idx, tot=total_count: self._stream_row(r, p, i, tot))
                except Exception:
                    pass

            try:
                self.after(0, self._finalize_benchmark)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _stream_row(self, res: dict, progress: float, idx: int, total: int):
        self.prog_bar.set(progress)
        self.lbl_status.configure(text=f"Testing [{idx}/{total}]: {res.get('country', '')} {res.get('name', '')}...")

        c_ms = f"{res['cached_ms']:.1f} ms" if res.get('cached_ms') is not None else "Timeout"
        u_ms = f"{res['uncached_ms']:.1f} ms" if res.get('uncached_ms') is not None else "Timeout"
        d_ms = f"{res['dotcom_ms']:.1f} ms" if res.get('dotcom_ms') is not None else "Timeout"
        s_ms = f"{res['score']:.1f} ms" if res.get('score') is not None and res['score'] < 9999 else "Failed"
        stat = "🟢 Fast" if res.get('score', 9999) < 60 else ("🟡 OK" if res.get('score', 9999) < 150 else "🔴 Slow")
        proto = res.get("protocol", "IPv4")

        self.tree.insert("", "end", values=(
            idx, res.get("country", "🌐"), res.get("name", "Unknown"), proto,
            c_ms, u_ms, d_ms, s_ms, stat
        ))

    def _finalize_benchmark(self):
        self.benchmark_running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

        if not self.results_map:
            self.lbl_status.configure(text="Benchmark selesai (0 hasil).")
            return

        sorted_res = sorted(
            [r for r in self.results_map.values() if r.get("score") is not None],
            key=lambda x: x.get("score", 9999)
        )

        for item in self.tree.get_children():
            self.tree.delete(item)

        for rk, res in enumerate(sorted_res, 1):
            c_ms = f"{res['cached_ms']:.1f} ms" if res.get('cached_ms') is not None else "Timeout"
            u_ms = f"{res['uncached_ms']:.1f} ms" if res.get('uncached_ms') is not None else "Timeout"
            d_ms = f"{res['dotcom_ms']:.1f} ms" if res.get('dotcom_ms') is not None else "Timeout"
            s_ms = f"{res['score']:.1f} ms" if res.get('score') is not None and res['score'] < 9999 else "Failed"
            stat = "🟢 Fast" if res.get('score', 9999) < 60 else ("🟡 OK" if res.get('score', 9999) < 150 else "🔴 Slow")
            proto = res.get("protocol", "IPv4")

            self.tree.insert("", "end", values=(
                rk, res.get("country", "🌐"), res.get("name", "Unknown"), proto,
                c_ms, u_ms, d_ms, s_ms, stat
            ))

        self.lbl_status.configure(text=f"✓ Benchmark selesai! {len(sorted_res)} resolvers diurutkan otomatis (Klik header kolom untuk menyortir).", text_color="#a6e3a1")

        if sorted_res:
            self.btn_apply_smart.configure(state="normal")
            self.btn_apply_fastest.configure(state="normal")

            smart = bm.calculate_smart_mix(self.results_map)
            c_name = smart.get('cached', {}).get('name', 'None')
            u_name = smart.get('uncached', {}).get('name', 'None')
            d_name = smart.get('dotcom', {}).get('name', 'None')

            rec_txt = (
                f"• DNS 1 (Primary Cached)   : {c_name} ({smart.get('cached', {}).get('cached_ms', 0):.1f} ms)\n"
                f"• DNS 2 (Secondary Uncached): {u_name} ({smart.get('uncached', {}).get('uncached_ms', 0):.1f} ms)\n"
                f"• DNS 3 (Tertiary TLD/Com) : {d_name} ({smart.get('dotcom', {}).get('dotcom_ms', 0):.1f} ms)"
            )
            self.lbl_smart_rec.configure(text=rec_txt)

    def stop_benchmark(self):
        self.benchmark_cancelled = True
        self.lbl_status.configure(text="Benchmark dihentikan oleh pengguna.", text_color="#f9e2af")

    def apply_smart_mix(self):
        smart = bm.calculate_smart_mix(self.results_map)
        is_ipv6 = (self._get_benchmark_mode_key() == "ipv6")

        def _get_ips(item):
            if is_ipv6:
                return item.get("ipv6", []) or item.get("ipv4", [])
            return item.get("ipv4", [])

        c_ips = _get_ips(smart.get("cached", {}))
        u_ips = _get_ips(smart.get("uncached", {}))
        d_ips = _get_ips(smart.get("dotcom", {}))

        self.dns_view.dns1_entry.delete(0, "end")
        self.dns_view.dns2_entry.delete(0, "end")
        self.dns_view.dns3_entry.delete(0, "end")

        if c_ips: self.dns_view.dns1_entry.insert(0, c_ips[0])
        if u_ips: self.dns_view.dns2_entry.insert(0, u_ips[0])
        if d_ips: self.dns_view.dns3_entry.insert(0, d_ips[0])

        self.lbl_status.configure(text="⚡ Menerapkan GRC Smart Mix ke sistem jaringan...", text_color="#f9e2af")

        def _bg():
            self.dns_view.apply_dns()
            try:
                self.after(0, lambda: self.lbl_status.configure(
                    text="✓ Berhasil! GRC Smart Mix aktif di sistem.",
                    text_color="#a6e3a1"
                ))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def apply_fastest_single(self):
        sorted_res = sorted(
            [r for r in self.results_map.values() if r.get("score") is not None],
            key=lambda x: x.get("score", 9999)
        )
        if not sorted_res:
            return

        fastest = sorted_res[0]
        is_ipv6 = (self._get_benchmark_mode_key() == "ipv6")
        ips = fastest.get("ipv6", []) if (is_ipv6 and fastest.get("ipv6")) else fastest.get("ipv4", [])
        if not ips:
            return

        self.dns_view.dns1_entry.delete(0, "end")
        self.dns_view.dns2_entry.delete(0, "end")
        self.dns_view.dns3_entry.delete(0, "end")

        if len(ips) > 0: self.dns_view.dns1_entry.insert(0, ips[0])
        if len(ips) > 1: self.dns_view.dns2_entry.insert(0, ips[1])

        self.lbl_status.configure(text=f"⚡ Menerapkan #{fastest['name']} ke sistem jaringan...", text_color="#f9e2af")

        def _bg():
            self.dns_view.apply_dns()
            try:
                self.after(0, lambda: self.lbl_status.configure(
                    text=f"✓ Berhasil! DNS '{fastest['name']}' aktif di sistem.",
                    text_color="#a6e3a1"
                ))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()
