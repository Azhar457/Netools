"""
Real-Time Streaming GRC 3-Tier DNS Benchmark Modal Dialog (CustomTkinter).
"""

import threading
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

import dns_jumper_db as db
import dns_jumper_benchmark as bm
from netools.gui.theme import Fonts, COLOR_CARD, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_ACCENT_BLUE, COLOR_ACCENT_GREEN, COLOR_ACCENT_PURPLE, COLOR_ACCENT_YELLOW

class GRCBenchmarkModal(ctk.CTkToplevel):
    def __init__(self, parent_app, dns_view):
        super().__init__(parent_app, className="netools")
        self.parent_app = parent_app
        self.dns_view = dns_view

        self.title("⚡ Netools — GRC 3-Tier Real-Time DNS Benchmark")
        self.geometry("980x640")
        self.minsize(850, 520)
        self.configure(fg_color="#181825")

        self.benchmark_running = False
        self.benchmark_cancelled = False
        self.results_map = {}

        self.providers = db.load_providers()
        self.target_tlds = db.TARGET_TLD_DOMAINS

        self._build_widgets()

    def _build_widgets(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="#181825")
        hdr.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(
            hdr,
            text="⚡ GRC 3-Tier Real-Time DNS Streaming Benchmark",
            font=Fonts.title(15),
            text_color=COLOR_ACCENT_YELLOW
        ).pack(side="left")

        # Filters Card
        card_filter = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        card_filter.pack(fill="x", padx=16, pady=4)

        r1 = ctk.CTkFrame(card_filter, fg_color=COLOR_CARD)
        r1.pack(fill="x", padx=14, pady=(8, 4))

        ctk.CTkLabel(r1, text="Mode:", font=Fonts.bold(11), text_color=COLOR_TEXT_PRIMARY).pack(side="left", padx=(0, 6))

        self.mode_var = ctk.StringVar(value="standard")
        ctk.CTkRadioButton(
            r1, text="Standard UDP (Port 53)", variable=self.mode_var, value="standard",
            font=Fonts.regular(11), text_color=COLOR_ACCENT_GREEN, fg_color=COLOR_ACCENT_GREEN
        ).pack(side="left", padx=4)

        ctk.CTkRadioButton(
            r1, text="Encrypted DoH (HTTPS)", variable=self.mode_var, value="doh",
            font=Fonts.regular(11), text_color=COLOR_ACCENT_BLUE, fg_color=COLOR_ACCENT_BLUE
        ).pack(side="left", padx=10)

        ctk.CTkLabel(r1, text="|  Region Filter:", font=Fonts.bold(11), text_color=COLOR_TEXT_PRIMARY).pack(side="left", padx=(10, 6))

        self.region_var = ctk.StringVar(value="🌏 All Curated Resolvers (50+)")
        self.region_cb = ctk.CTkComboBox(
            r1, variable=self.region_var,
            values=["🌏 All Curated Resolvers (50+)", "🇨🇳/🇸🇬/🇯🇵 Asia-Pacific", "🌍 Europe & UK", "🌎 North America", "🌐 Global Anycast"],
            width=250, font=Fonts.regular(11), dropdown_font=Fonts.regular(11)
        )
        self.region_cb.pack(side="left", padx=4)

        r2 = ctk.CTkFrame(card_filter, fg_color=COLOR_CARD)
        r2.pack(fill="x", padx=14, pady=(4, 10))

        ctk.CTkLabel(r2, text="TLD Target:", font=Fonts.bold(11), text_color=COLOR_TEXT_PRIMARY).pack(side="left", padx=(0, 6))

        self.tld_var = ctk.StringVar(value="id_national")
        tld_choices = [f"{v['name']} ({k})" for k, v in self.target_tlds.items()]
        self.tld_cb = ctk.CTkComboBox(
            r2, variable=self.tld_var, values=tld_choices,
            width=320, font=Fonts.regular(11), dropdown_font=Fonts.regular(11)
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
            r2, text="🛑 Stop", font=Fonts.bold(11),
            fg_color="#f38ba8", text_color="#11111b", hover_color="#eba0ac",
            height=30, width=80, state="disabled", command=self.stop_benchmark
        )
        self.btn_stop.pack(side="left", padx=4)

        # Progress bar & Status
        prog_frame = ctk.CTkFrame(self, fg_color="#181825")
        prog_frame.pack(fill="x", padx=16, pady=(4, 2))

        self.prog_bar = ctk.CTkProgressBar(prog_frame, height=8, corner_radius=4, fg_color="#313244", progress_color=COLOR_ACCENT_GREEN)
        self.prog_bar.set(0)
        self.prog_bar.pack(fill="x")

        self.lbl_status = ctk.CTkLabel(
            prog_frame,
            text="Ready to benchmark. Select mode and click 'Run Benchmark'.",
            font=Fonts.italic_small(11),
            text_color=COLOR_TEXT_SECONDARY
        )
        self.lbl_status.pack(anchor="w", pady=(2, 4))

        # Real-time Streaming Table
        tbl_frame = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        tbl_frame.pack(fill="both", expand=True, padx=16, pady=4)

        cols = ("rank", "flag", "name", "cached", "uncached", "dotcom", "score", "status")
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

        self.tree.heading("rank", text="#")
        self.tree.heading("flag", text="Region")
        self.tree.heading("name", text="DNS Resolver Name")
        self.tree.heading("cached", text="🟢 Cached")
        self.tree.heading("uncached", text="🔵 Uncached")
        self.tree.heading("dotcom", text="🟡 Dot-Com / TLD")
        self.tree.heading("score", text="Composite Score")
        self.tree.heading("status", text="Result")

        self.tree.column("rank", width=45, anchor="center")
        self.tree.column("flag", width=70, anchor="center")
        self.tree.column("name", width=230, anchor="w")
        self.tree.column("cached", width=105, anchor="center")
        self.tree.column("uncached", width=105, anchor="center")
        self.tree.column("dotcom", width=115, anchor="center")
        self.tree.column("score", width=120, anchor="center")
        self.tree.column("status", width=90, anchor="center")

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
            text="Run the benchmark to generate optimal GRC Smart Mix recommendations.",
            font=Fonts.mono(11),
            text_color="#bac2de",
            justify="left"
        )
        self.lbl_smart_rec.pack(anchor="w", padx=14, pady=(0, 8))

        btn_row = ctk.CTkFrame(smart_card, fg_color=COLOR_CARD)
        btn_row.pack(fill="x", padx=14, pady=(0, 10))

        self.btn_apply_smart = ctk.CTkButton(
            btn_row, text="⚡ Apply Smart Mix to DNS 1-2-3", font=Fonts.bold(11),
            fg_color=COLOR_ACCENT_GREEN, text_color="#11111b", hover_color="#94e2d5",
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
        ).pack(side="right")

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

        mode = self.mode_var.get()
        reg_text = self.region_var.get()
        region_key = "all"
        if "Asia" in reg_text: region_key = "asia"
        elif "Europe" in reg_text: region_key = "europe"
        elif "North America" in reg_text: region_key = "north_america"
        elif "Global" in reg_text: region_key = "global"

        tld_sel = self.tld_var.get()
        tld_key = "id_national"
        for k in self.target_tlds:
            if f"({k})" in tld_sel:
                tld_key = k
                break

        # Filter providers
        filtered = db.filter_providers(self.providers, region=region_key, only_doh=(mode == "doh"))
        total_count = len(filtered)
        self.prog_bar.set(0)
        self.lbl_status.configure(text=f"Benchmarking {total_count} DNS resolvers in real-time...")

        def _worker():
            idx = 0
            for p_id, p_info in filtered.items():
                if self.benchmark_cancelled:
                    break
                idx += 1
                prog = idx / max(1, total_count)

                # Test provider
                res = bm.benchmark_provider_full(p_id, p_info, tld_category=tld_key, mode=mode, timeout=2.5)
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

        self.tree.insert("", "end", values=(
            idx, res.get("country", "🌐"), res.get("name", "Unknown"),
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

            self.tree.insert("", "end", values=(
                rk, res.get("country", "🌐"), res.get("name", "Unknown"),
                c_ms, u_ms, d_ms, s_ms, stat
            ))

        self.lbl_status.configure(text=f"✓ Benchmark selesai! {len(sorted_res)} resolvers diurutkan berdasarkan composite score.")

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
        self.lbl_status.configure(text="Benchmark dihentikan oleh pengguna.")

    def apply_smart_mix(self):
        smart = bm.calculate_smart_mix(self.results_map)
        c_ips = smart.get("cached", {}).get("ipv4", [])
        u_ips = smart.get("uncached", {}).get("ipv4", [])
        d_ips = smart.get("dotcom", {}).get("ipv4", [])

        self.dns_view.dns1_entry.delete(0, "end")
        self.dns_view.dns2_entry.delete(0, "end")
        self.dns_view.dns3_entry.delete(0, "end")

        if c_ips: self.dns_view.dns1_entry.insert(0, c_ips[0])
        if u_ips: self.dns_view.dns2_entry.insert(0, u_ips[0])
        if d_ips: self.dns_view.dns3_entry.insert(0, d_ips[0])

        self.parent_app.show_toast("✓ GRC Smart Mix diterapkan ke form DNS 1-2-3!", level="success")
        self.dns_view.apply_dns()

    def apply_fastest_single(self):
        sorted_res = sorted(
            [r for r in self.results_map.values() if r.get("score") is not None],
            key=lambda x: x.get("score", 9999)
        )
        if not sorted_res:
            return
        top = sorted_res[0]
        ips = top.get("ipv4", [])

        self.dns_view.dns1_entry.delete(0, "end")
        self.dns_view.dns2_entry.delete(0, "end")
        self.dns_view.dns3_entry.delete(0, "end")

        if len(ips) > 0: self.dns_view.dns1_entry.insert(0, ips[0])
        if len(ips) > 1: self.dns_view.dns2_entry.insert(0, ips[1])
        if len(ips) > 2: self.dns_view.dns3_entry.insert(0, ips[2])

        self.parent_app.show_toast(f"✓ DNS #1 Tercepat ({top.get('name')}) diterapkan!", level="success")
        self.dns_view.apply_dns()
