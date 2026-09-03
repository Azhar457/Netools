"""
GRC 3-Tier Real-Time Streaming DNS Benchmark Modal (CustomTkinter).
Evaluates Cached, Uncached, and Regional TLD Latency across 90+ DNS resolvers for IPv4, IPv6, DoH & DoT.
Features multi-column sorting, protocol indicators, live status, and 1-click system application.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import ttk

import customtkinter as ctk

from netools.gui.i18n import tr
from netools.gui.theme import (
    Fonts,
    ThemeManager,
)
from netools.gui.wm import mark_dialog
from netools.libs import dns_benchmark as bm
from netools.libs import dns_db as db


class GRCBenchmarkModal(ctk.CTkToplevel):
    def __init__(self, parent_app, dns_view):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.dns_view = dns_view

        self.title("⚡ Netools — GRC 3-Tier Real-Time DNS Benchmark (IPv4 / IPv6 / DoH / DoT)")
        self.geometry("1020x660")
        self.minsize(880, 540)
        self.configure(fg_color=ThemeManager.bg())

        self.benchmark_running = False
        self.benchmark_cancelled = False
        self.results_map = {}
        self.sort_directions = {}

        self.providers = db.load_providers()
        self.target_tlds = db.load_tld_presets()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        mark_dialog(self, parent_app)
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
        hdr = ctk.CTkFrame(self, fg_color=ThemeManager.surface_alt(), height=50)
        hdr.pack(fill="x", padx=0, pady=0)
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="🏆 Gibson Research Corp (GRC) 3-Tier DNS Benchmark Engine",
            font=Fonts.title(15),
            text_color=ThemeManager.warning()
        ).pack(side="left", padx=20, pady=10)

        # Filter & Execution Control Card
        card_filter = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        card_filter.pack(fill="x", padx=16, pady=8)

        r1 = ctk.CTkFrame(card_filter, fg_color=ThemeManager.surface())
        r1.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(r1, text="Test Protocol / IP:", font=Fonts.bold(11), text_color=ThemeManager.text()).pack(side="left", padx=(0, 6))

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

        ctk.CTkLabel(r1, text="|  Region:", font=Fonts.bold(11), text_color=ThemeManager.text()).pack(side="left", padx=(14, 6))

        self.region_var = ctk.StringVar(value="🌏 All Curated Resolvers (90+)")
        self.region_cb = ctk.CTkComboBox(
            r1, variable=self.region_var,
            values=["🌏 All Curated Resolvers (90+)", "🇨🇳/🇸🇬/🇯🇵 Asia-Pacific", "🌍 Europe & UK", "🌎 North America", "🌐 Global Anycast"],
            width=240, font=Fonts.regular(11), dropdown_font=Fonts.regular(11)
        )
        self.region_cb.pack(side="left", padx=4)

        r2 = ctk.CTkFrame(card_filter, fg_color=ThemeManager.surface())
        r2.pack(fill="x", padx=14, pady=(4, 10))

        ctk.CTkLabel(r2, text="TLD Target:", font=Fonts.bold(11), text_color=ThemeManager.text()).pack(side="left", padx=(0, 6))


        tld_choices = [f"{v['name']} ({k})" for k, v in self.target_tlds.items()]
        self.tld_var = ctk.StringVar(value=tld_choices[0] if tld_choices else "Indonesia (.id)")
        self.tld_cb = ctk.CTkComboBox(
            r2, variable=self.tld_var, values=tld_choices,
            width=240, font=Fonts.regular(11), dropdown_font=Fonts.regular(11)
        )
        self.tld_cb.pack(side="left", padx=4)
        self._auto_select_country_preset()

        # Manage TLD Categories (CRUD)
        ctk.CTkButton(
            r2, text=tr("🗂 Manage"), font=Fonts.bold(10),
            fg_color=ThemeManager.border(), text_color=ThemeManager.primary(),
            hover_color=ThemeManager.surface_alt(), height=30, width=90,
            command=self.open_tld_manager,
        ).pack(side="left", padx=(6, 0))

        # Turbo Mode Switch (Max Latency Cutoff)
        self.turbo_var = ctk.BooleanVar(value=True)
        self.turbo_switch = ctk.CTkSwitch(
            r2,
            text="⚡ Turbo (<200ms)",
            variable=self.turbo_var,
            font=Fonts.bold(10),
            text_color=ThemeManager.warning(),
            progress_color=ThemeManager.warning()
        )
        self.turbo_switch.pack(side="left", padx=(10, 4))

        # Action Buttons
        self.btn_start = ctk.CTkButton(
            r2, text="🚀 Run Benchmark", font=Fonts.bold(11),
            fg_color=ThemeManager.warning(), text_color=ThemeManager.get("on_primary"), hover_color=ThemeManager.border(),
            height=30, width=130, command=self.start_benchmark
        )
        self.btn_start.pack(side="left", padx=(10, 4))

        self.btn_stop = ctk.CTkButton(
            r2, text="🛑 Cancel", font=Fonts.bold(11),
            fg_color=ThemeManager.danger(), text_color=ThemeManager.get("on_primary"), hover_color=ThemeManager.warning(),
            height=30, width=90, state="disabled", command=self.stop_benchmark
        )
        self.btn_stop.pack(side="left", padx=4)

        # Progress / Status Frame
        prog_frame = ctk.CTkFrame(self, fg_color=ThemeManager.bg())
        prog_frame.pack(fill="x", padx=16, pady=2)

        self.prog_bar = ctk.CTkProgressBar(prog_frame, height=8, progress_color=ThemeManager.primary())
        self.prog_bar.pack(fill="x", pady=(2, 4))
        self.prog_bar.set(0)

        self.lbl_status = ctk.CTkLabel(
            prog_frame, text="Ready. Click 'Run Benchmark' to start real-time latency evaluation (Click column headers to sort).",
            font=Fonts.regular(11), text_color=ThemeManager.text_muted()
        )
        self.lbl_status.pack(anchor="w")

        # Results Table
        tbl_frame = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        tbl_frame.pack(fill="both", expand=True, padx=16, pady=4)

        cols = ("rank", "flag", "name", "proto", "cached", "uncached", "dotcom", "score", "status")
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", selectmode="browse")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=ThemeManager.surface(),
            foreground=ThemeManager.text(),
            fieldbackground=ThemeManager.surface(),
            rowheight=26,
            font=("sans-serif", 10)
        )
        style.configure(
            "Treeview.Heading",
            background=ThemeManager.surface_alt(),
            foreground=ThemeManager.text(),
            font=("sans-serif", 10, "bold")
        )
        style.map("Treeview", background=[("selected", ThemeManager.border())])

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
        smart_card = ctk.CTkFrame(self, fg_color=ThemeManager.surface(), corner_radius=8, border_width=1, border_color=ThemeManager.border())
        smart_card.pack(fill="x", padx=16, pady=(4, 12))

        ctk.CTkLabel(
            smart_card,
            text="🏆 Smart Mix Recommendation (GRC Optimum Triad)",
            font=Fonts.subtitle(13),
            text_color=ThemeManager.success()
        ).pack(anchor="w", padx=14, pady=(10, 4))

        self.lbl_smart_rec = ctk.CTkLabel(
            smart_card,
            text="• Run benchmark to generate composite latency recommendations for Slot 1, 2, and 3.",
            font=Fonts.mono(11),
            text_color=ThemeManager.text_muted(),
            justify="left"
        )
        self.lbl_smart_rec.pack(anchor="w", padx=14, pady=(0, 8))

        btn_row = ctk.CTkFrame(smart_card, fg_color=ThemeManager.surface())
        btn_row.pack(fill="x", padx=14, pady=(0, 10))

        self.btn_apply_smart = ctk.CTkButton(
            btn_row, text="⚡ Apply GRC Smart Mix (Slots 1-3)", font=Fonts.bold(12),
            fg_color=ThemeManager.success(), text_color=ThemeManager.get("on_primary"), hover_color=ThemeManager.accent(),
            height=36, state="disabled", command=self.apply_smart_mix
        )
        self.btn_apply_smart.pack(side="left", padx=(0, 6))

        self.btn_apply_fastest = ctk.CTkButton(
            btn_row, text="🥇 Apply #1 Fastest Only", font=Fonts.bold(12),
            fg_color=ThemeManager.primary(), text_color=ThemeManager.get("on_primary"), hover_color=ThemeManager.accent(),
            height=36, state="disabled", command=self.apply_fastest_single
        )
        self.btn_apply_fastest.pack(side="left", padx=6)

        # Per-metric apply buttons (best Cached / Uncached / TLD)
        self.metric_buttons = []
        for label, metric in (
            ("🚀 Best Cached", "cached_ms"),
            ("🌐 Best Uncached", "uncached_ms"),
            ("🎯 Best TLD", "dotcom_ms"),
        ):
            b = ctk.CTkButton(
                btn_row, text=label, font=Fonts.bold(11),
                fg_color=ThemeManager.surface_alt(), text_color=ThemeManager.primary(),
                hover_color=ThemeManager.border(), border_width=1, border_color=ThemeManager.border(),
                height=36, width=120, state="disabled",
                command=lambda m=metric, l=label: self.apply_best_metric(m, l),
            )
            b.pack(side="left", padx=4)
            self.metric_buttons.append(b)

        ctk.CTkButton(
            btn_row, text="Tutup", font=Fonts.bold(11),
            fg_color=ThemeManager.border(), text_color=ThemeManager.text(), hover_color=ThemeManager.surface_alt(),
            height=36, width=90, command=self.destroy
        ).pack(side="right")

    def sort_column(self, col: str):
        """Sort Treeview rows by clicking column headers (Numeric & String)."""
        reverse = self.sort_directions.get(col, False)
        self.sort_directions[col] = not reverse

        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

        def _val_key(v):
            if v is None:
                return (1, 999999.0, "")
            v_str = str(v).strip()
            clean = v_str.replace(" ms", "").replace("#", "").strip()
            if clean in ("", "—", "Timeout", "Failed", "Cutoff", "N/A", "null", "None", "-"):
                return (1, 999999.0, v_str.lower())
            try:
                return (0, float(clean), "")
            except ValueError:
                return (2, 0.0, v_str.lower())

        items.sort(key=lambda t: _val_key(t[0]), reverse=reverse)


        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

    def _get_benchmark_mode_key(self) -> str:
        m = self.mode_var.get().lower()
        if "ipv6" in m: return "ipv6"
        if "doh" in m: return "doh"
        if "dot" in m: return "dot"
        return "ipv4"

    def _tld_choices(self):
        return [f"{v['name']} ({k})" for k, v in self.target_tlds.items()]

    def _auto_select_country_preset(self):
        """Default the TLD combobox to the preset matching the detected country.

        Detection runs off the UI thread (first run does one HTTPS request);
        result is cached in config.json so subsequent opens are instant.
        """
        def worker():
            try:
                from netools.libs.geo import detect_country
                key = db.preset_key_for_country(detect_country(), self.target_tlds)
                if key:
                    label = f"{self.target_tlds[key]['name']} ({key})"
                    self.after(0, lambda: self.winfo_exists() and self.tld_var.set(label))
            except Exception:
                pass  # keep default preset on any failure

        threading.Thread(target=worker, daemon=True).start()

    def open_tld_manager(self):
        """CRUD manager for GRC Tier-3 TLD categories."""
        win = ctk.CTkToplevel(self)
        win.title("TLD Category Manager")
        win.geometry("560x560")
        mark_dialog(win, self.winfo_toplevel())
        win.after(120, win.lift)

        ctk.CTkLabel(win, text="Categories:", font=Fonts.bold(12),
                     text_color=ThemeManager.text()).pack(anchor="w", padx=14, pady=(12, 2))
        cat_box = ctk.CTkTextbox(win, height=90, font=Fonts.mono(11),
                                 fg_color=ThemeManager.surface_alt(),
                                 text_color=ThemeManager.text())
        cat_box.pack(fill="x", padx=14)

        row1 = ctk.CTkFrame(win, fg_color="transparent")
        row1.pack(fill="x", padx=14, pady=(8, 0))
        ctk.CTkLabel(row1, text="Key:", font=Fonts.bold(11),
                     text_color=ThemeManager.text()).pack(side="left")
        key_entry = ctk.CTkEntry(row1, width=130, font=Fonts.mono(11),
                                 fg_color=ThemeManager.surface(),
                                 border_color=ThemeManager.border(),
                                 text_color=ThemeManager.text())
        key_entry.pack(side="left", padx=6)
        ctk.CTkLabel(row1, text="Name:", font=Fonts.bold(11),
                     text_color=ThemeManager.text()).pack(side="left", padx=(8, 0))
        name_entry = ctk.CTkEntry(row1, width=200, font=Fonts.regular(11),
                                  fg_color=ThemeManager.surface(),
                                  text_color=ThemeManager.text())
        name_entry.pack(side="left", padx=6)

        ctk.CTkLabel(win, text="Domains (one per line):", font=Fonts.bold(11),
                     text_color=ThemeManager.text()).pack(anchor="w", padx=14, pady=(8, 2))
        dom_box = ctk.CTkTextbox(win, font=Fonts.mono(11),
                                 fg_color=ThemeManager.surface_alt(),
                                 text_color=ThemeManager.text())
        dom_box.pack(fill="both", expand=True, padx=14, pady=(0, 6))

        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(0, 12))

        state = {"current_key": ""}

        def _refresh_cat_list():
            cats = db.load_tld_presets()
            cat_box.configure(state="normal")
            cat_box.delete("1.0", "end")
            for k, v in cats.items():
                tag = " [modified]" if v.get("modified") else ""
                cat_box.insert("end", f"{k:22s} {len(v['domains'])} domains{tag}\n")
            cat_box.configure(state="disabled")

        def _load_key(key):
            cats = db.load_tld_presets()
            info = cats.get(key)
            key_entry.delete(0, "end"); name_entry.delete(0, "end")
            dom_box.delete("1.0", "end")
            if not info:
                return
            state["current_key"] = key
            key_entry.insert(0, key)
            name_entry.insert(0, info["name"])
            for d in info["domains"]:
                dom_box.insert("end", d + "\n")

        def _on_cat_click(event=None):
            try:
                line = cat_box.get("insert linestart", "insert lineend").strip()
                key = line.split()[0] if line else ""
                if key:
                    _load_key(key)
            except Exception:
                pass
        cat_box.bind("<ButtonRelease-1>", _on_cat_click)

        def _new():
            state["current_key"] = ""
            key_entry.delete(0, "end"); name_entry.delete(0, "end")
            dom_box.delete("1.0", "end")
            key_entry.focus_set()

        def _save():
            key = key_entry.get().strip().lower().replace(" ", "_")
            name = name_entry.get().strip()
            raw = dom_box.get("1.0", "end").splitlines()
            domains = [d.strip() for d in raw if d.strip()]
            if not key or not name or not domains:
                self.dns_view.main_app.show_toast(
                    "Key, Name, and at least 1 domain required.", level="warning")
                return
            if db.save_tld_category(key, name, domains):
                self.target_tlds = db.load_tld_presets()
                self.tld_cb.configure(values=self._tld_choices())
                _refresh_cat_list()
                self.dns_view.main_app.show_toast(
                    f"✓ TLD category '{key}' saved.", level="success")
            else:
                self.dns_view.main_app.show_toast(f"Failed to save '{key}'.", level="error")

        def _delete():
            key = (state["current_key"] or key_entry.get().strip()).lower()
            if not key:
                return
            if db.delete_tld_category(key):
                self.target_tlds = db.load_tld_presets()
                choices = self._tld_choices()
                self.tld_cb.configure(values=choices)
                if choices:
                    self.tld_var.set(choices[0])
                _refresh_cat_list(); _new()
                self.dns_view.main_app.show_toast(
                    f"🗑 TLD category '{key}' deleted/hidden.", level="info")
            else:
                self.dns_view.main_app.show_toast(f"Not found: '{key}'", level="warning")

        def _reset_all():
            db.reset_tld_presets()
            self.target_tlds = db.load_tld_presets()
            choices = self._tld_choices()
            self.tld_cb.configure(values=choices)
            if choices:
                self.tld_var.set(choices[0])
            _refresh_cat_list(); _new()
            self.dns_view.main_app.show_toast("TLD presets reset to defaults.", level="info")

        ctk.CTkButton(btns, text="➕ New", width=80, height=30, font=Fonts.bold(11),
                      fg_color=ThemeManager.primary(), text_color=ThemeManager.get("on_primary"),
                      hover_color=ThemeManager.accent(), command=_new).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btns, text="💾 Save", width=90, height=30, font=Fonts.bold(11),
                      fg_color=ThemeManager.success(), text_color=ThemeManager.get("on_primary"),
                      hover_color=ThemeManager.accent(), command=_save).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btns, text="🗑 Delete", width=90, height=30, font=Fonts.bold(11),
                      fg_color=ThemeManager.danger(), text_color=ThemeManager.get("on_primary"),
                      hover_color=ThemeManager.accent(), command=_delete).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btns, text="↺ Reset Defaults", width=130, height=30, font=Fonts.bold(11),
                      fg_color=ThemeManager.border(), text_color=ThemeManager.text(),
                      hover_color=ThemeManager.surface_alt(), command=_reset_all).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btns, text="Close", width=80, height=30, font=Fonts.bold(11),
                      fg_color=ThemeManager.border(), text_color=ThemeManager.text(),
                      hover_color=ThemeManager.surface_alt(), command=win.destroy).pack(side="right")

        _refresh_cat_list()

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
        for b in self.metric_buttons:
            b.configure(state="disabled")

        for item in self.tree.get_children():
            self.tree.delete(item)

        mode_key = self._get_benchmark_mode_key()

        # Pre-flight check for IPv6
        if mode_key == "ipv6":
            from netools.libs.net import check_ipv6_connectivity
            if not check_ipv6_connectivity():
                self.lbl_status.configure(
                    text="⚠️ ISP/Jaringan lokal Anda tidak memiliki koneksi IPv6 (Network Unreachable). Silakan pilih mode IPv4 atau DoH/DoT.",
                    text_color=ThemeManager.danger()
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
        is_turbo = self.turbo_var.get()
        self.prog_bar.set(0)
        mode_desc = f"{mode_key.upper()} (⚡ Turbo <200ms)" if is_turbo else mode_key.upper()
        self.lbl_status.configure(text=f"Benchmarking {total_count} DNS resolvers in real-time ({mode_desc})...", text_color=ThemeManager.text())

        def _worker():
            # Parallel benchmark: spawn N workers (capped to provider count) so
            # latency-bound queries fan-out concurrently.  Sequential execution
            # wasted ~3-5x wall-clock time on 90+ providers; this is the main
            # perf win for the engine.  We still stream results in completion
            # order so the UI remains responsive.
            providers = list(filtered.items())
            total_count = len(providers)
            max_workers = min(8, total_count)
            done_count = 0

            def _run_one(p_id, p_info):
                if self.benchmark_cancelled:
                    return None
                return bm.benchmark_provider_full(
                    p_id, p_info,
                    tld_category=tld_key,
                    mode=mode_key,
                    timeout=2.5,
                    turbo_mode=is_turbo,
                    max_latency_threshold=200.0,
                )

            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="dns-bench") as ex:
                futures = {ex.submit(_run_one, p_id, p_info): p_id for p_id, p_info in providers}
                for fut in as_completed(futures):
                    if self.benchmark_cancelled:
                        break
                    res = fut.result()
                    if res is None:
                        continue
                    p_id = futures[fut]
                    done_count += 1
                    self.results_map[p_id] = res
                    prog = done_count / max(1, total_count)
                    try:
                        self.after(0, lambda r=res, p=prog, i=done_count, tot=total_count: self._stream_row(r, p, i, tot))
                    except Exception:
                        pass

            try:
                self.after(0, self._finalize_benchmark)
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _stream_row(self, res: dict, progress: float, idx: int, total: int):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        try:
            self.prog_bar.set(progress)
            self.lbl_status.configure(text=f"Testing [{idx}/{total}]: {res.get('country', '')} {res.get('name', '')}...")
        except Exception:
            return


        c_ms = f"{res['cached_ms']:.1f} ms" if res.get('cached_ms') is not None else "Timeout"
        u_ms = f"{res['uncached_ms']:.1f} ms" if res.get('uncached_ms') is not None else ("Cutoff" if "Cutoff" in res.get("status", "") else "—")
        d_ms = f"{res['dotcom_ms']:.1f} ms" if res.get('dotcom_ms') is not None else ("Cutoff" if "Cutoff" in res.get("status", "") else "—")
        s_ms = f"{res['score']:.1f} ms" if res.get('score') is not None and res['score'] < 9000 else "—"
        
        if res.get("hijack_detected"):
            stat = "🔴 Hijacked"
        elif "Cutoff" in res.get("status", ""):
            stat = "🟡 Cutoff (>200ms)"
        elif res.get("status") == "Stable" and res.get('score', 9999) < 60:
            stat = "🟢 Fast"
        elif res.get("status") == "Stable" or (res.get('score', 9999) < 150 and res.get('score', 9999) > 0):
            stat = "🟡 OK"
        elif res.get("status") == "Partial":
            stat = "🟡 Partial"
        else:
            stat = "🔴 Slow / Timeout"

        proto = res.get("protocol", "IPv4")

        self.tree.insert("", "end", values=(
            idx, res.get("country", "🌐"), res.get("name", "Unknown"), proto,
            c_ms, u_ms, d_ms, s_ms, stat
        ))

    def _finalize_benchmark(self):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        self.benchmark_running = False
        try:
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
        except Exception:
            return

        if not self.results_map:
            try:
                self.lbl_status.configure(text="Benchmark selesai (0 hasil).")
            except Exception:
                pass
            return


        sorted_res = sorted(
            [r for r in self.results_map.values() if r.get("score") is not None],
            key=lambda x: (
                0 if x.get("status") == "Stable" else (1 if x.get("status") == "Partial" else 2),
                x.get("score", 9999),
                x.get("cached_ms") or 9999.0
            )
        )

        for item in self.tree.get_children():
            self.tree.delete(item)

        for rk, res in enumerate(sorted_res, 1):
            c_ms = f"{res['cached_ms']:.1f} ms" if res.get('cached_ms') is not None else "Timeout"
            u_ms = f"{res['uncached_ms']:.1f} ms" if res.get('uncached_ms') is not None else ("Cutoff" if "Cutoff" in res.get("status", "") else "—")
            d_ms = f"{res['dotcom_ms']:.1f} ms" if res.get('dotcom_ms') is not None else ("Cutoff" if "Cutoff" in res.get("status", "") else "—")
            s_ms = f"{res['score']:.1f} ms" if res.get('score') is not None and res['score'] < 9000 else "—"
            
            if res.get("hijack_detected"):
                stat = "🔴 Hijacked"
            elif "Cutoff" in res.get("status", ""):
                stat = "🟡 Cutoff (>200ms)"
            elif res.get("status") == "Stable" and res.get('score', 9999) < 60:
                stat = "🟢 Fast"
            elif res.get("status") == "Stable" or (res.get('score', 9999) < 150 and res.get('score', 9999) > 0):
                stat = "🟡 OK"
            elif res.get("status") == "Partial":
                stat = "🟡 Partial"
            else:
                stat = "🔴 Slow / Timeout"

            proto = res.get("protocol", "IPv4")

            self.tree.insert("", "end", values=(
                rk, res.get("country", "🌐"), res.get("name", "Unknown"), proto,
                c_ms, u_ms, d_ms, s_ms, stat
            ))

        self.lbl_status.configure(text=f"✓ Benchmark selesai! {len(sorted_res)} resolvers diurutkan (Klik header kolom untuk menyortir).", text_color=ThemeManager.success())

        if sorted_res:
            self.btn_apply_smart.configure(state="normal")
            self.btn_apply_fastest.configure(state="normal")
            for b in self.metric_buttons:
                b.configure(state="normal")

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
        self.lbl_status.configure(text="Benchmark dihentikan oleh pengguna.", text_color=ThemeManager.warning())

    def apply_smart_mix(self):
        smart = bm.calculate_smart_mix(self.results_map)
        mode_key = self._get_benchmark_mode_key()

        picks = [
            (smart.get("cached", {}).get("key"), smart.get("cached", {})),
            (smart.get("uncached", {}).get("key"), smart.get("uncached", {})),
            (smart.get("dotcom", {}).get("key"), smart.get("dotcom", {})),
        ]

        entries = self.dns_view.dns1_entry, self.dns_view.dns2_entry, self.dns_view.dns3_entry
        for entry in entries:
            entry.delete(0, "end")

        primary_provider_id = None
        for slot, (p_key, item) in enumerate(picks):
            if not item:
                continue
            provider = self.providers.get(p_key, {})
            ips = self.dns_view.compute_provider_ips(provider, p_key, self._family_label(mode_key))
            if not ips:
                continue
            if slot == 0:
                primary_provider_id = p_key
            if len(ips) > 0:
                entries[slot].insert(0, ips[0])

        self.dns_view.sync_after_external_apply(
            provider_id=primary_provider_id,
            mode_key=mode_key,
        )

        self.lbl_status.configure(text="⚡ Menerapkan GRC Smart Mix ke sistem jaringan...", text_color=ThemeManager.warning())

        def _bg():
            self.dns_view.apply_dns()
            try:
                self.after(0, lambda: self.lbl_status.configure(
                    text="✓ Berhasil! GRC Smart Mix aktif di sistem.",
                    text_color=ThemeManager.success()
                ))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    def _family_label(self, mode_key: str) -> str:
        return {
            "ipv4": "IPv4 (Standard)",
            "ipv6": "IPv6 (Next-Gen)",
            "doh": "DoH (HTTPS)",
            "dot": "DoT (TLS Port 853)",
        }.get(mode_key, "IPv4 (Standard)")

    def apply_fastest_single(self):
        self._apply_ranked("score", "#1 Fastest")

    def apply_best_metric(self, metric: str, label: str):
        """Fill slots 1-3 with the top providers ranked by one benchmark tier."""
        self._apply_ranked(metric, label)

    def _apply_ranked(self, metric: str, label: str):
        ranked = [r for r in self.results_map.values() if r.get(metric) is not None]
        ranked.sort(key=lambda x: x.get(metric, 9999))
        if not ranked:
            self.lbl_status.configure(
                text=f"Tidak ada hasil untuk metrik '{label}'.",
                text_color=ThemeManager.warning(),
            )
            return

        mode_key = self._get_benchmark_mode_key()
        family = self._family_label(mode_key)

        entries = self.dns_view.dns1_entry, self.dns_view.dns2_entry, self.dns_view.dns3_entry
        for entry in entries:
            entry.delete(0, "end")

        filled = 0
        primary_provider_id = None
        for res in ranked:
            if filled >= 3:
                break
            p_key = res.get("key")
            provider = self.providers.get(p_key, {})
            ips = self.dns_view.compute_provider_ips(provider, p_key, family)
            if not ips:
                continue
            if filled == 0:
                primary_provider_id = p_key
            entries[filled].insert(0, ips[0])
            filled += 1

        if filled == 0:
            return

        self.dns_view.sync_after_external_apply(
            provider_id=primary_provider_id,
            mode_key=mode_key,
        )

        best = ranked[0]
        self.lbl_status.configure(text=f"⚡ Menerapkan {label}: {best['name']} ...", text_color=ThemeManager.warning())

        def _bg():
            self.dns_view.apply_dns()
            try:
                self.after(0, lambda: self.lbl_status.configure(
                    text=f"✓ Berhasil! {label} '{best['name']}' aktif di sistem.",
                    text_color=ThemeManager.success()
                ))
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()
